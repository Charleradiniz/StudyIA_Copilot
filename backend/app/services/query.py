from collections import defaultdict, deque
from pathlib import Path
from time import perf_counter
import logging
import re
import traceback

from fastapi import APIRouter, Depends, HTTPException

from pydantic import BaseModel

from app.config import RAG_MODE
from app.db.deps import get_current_user
from app.models.user import User
from app.services.embeddings import model
from app.services.llm import generate_answer
from app.services.reranker import rerank
from app.services.similarity import search
from app.services.storage import iter_saved_documents, load_document

router = APIRouter()
logger = logging.getLogger("studyiacopilot.query")

DOCUMENTS = {}
STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no",
    "na", "nos", "nas", "um", "uma", "uns", "umas", "para", "por", "com",
    "sem", "sobre", "que", "se", "ao", "aos", "à", "às", "ou", "como",
    "mais", "menos", "muito", "muita", "muitos", "muitas", "ser", "estar",
    "fala", "falar", "documento", "esse", "essa", "isso", "ele", "ela",
}
SUMMARY_HINTS = {
    "resuma", "resumo", "sumario", "sumário", "sobre", "arquivo", "curriculo",
    "currículo", "perfil", "geral", "visao", "visão", "overview", "describe",
}
FOLLOW_UP_HINTS = {
    "mais", "melhor", "detalhe", "detalhes", "isso", "essa", "esse", "aquilo",
    "tambem", "também", "aprofunde", "continue", "continua", "complementa",
    "explique", "explica", "fale", "fala",
}


STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no",
    "na", "nos", "nas", "um", "uma", "uns", "umas", "para", "por", "com",
    "sem", "sobre", "que", "se", "ao", "aos", "ou", "como", "mais", "menos",
    "muito", "muita", "muitos", "muitas", "ser", "estar", "fala", "falar",
    "documento", "esse", "essa", "isso", "ele", "ela",
}
SUMMARY_HINTS = {
    "resuma", "resumo", "sumario", "sobre", "arquivo", "curriculo", "perfil",
    "geral", "visao", "overview", "describe",
}
FOLLOW_UP_HINTS = {
    "mais", "melhor", "detalhe", "detalhes", "isso", "essa", "esse", "aquilo",
    "tambem", "aprofunde", "continue", "continua", "complementa", "explique",
    "explica", "fale", "fala",
}
COMPARISON_HINTS = {
    "compare", "comparar", "comparacao", "comparativo", "comparison",
    "comparisons", "similar", "similarity", "similarities", "difference",
    "differences", "different", "differs", "distinguish", "contrast",
    "contraste", "contrastar", "versus", "vs", "relacao", "relationship",
    "relationships", "between", "ambos", "ambas", "common", "comum",
}
COMPARISON_PHRASES = (
    "side by side",
    "em comum",
    "lado a lado",
    "quais as diferencas",
    "quais as semelhancas",
    "how do",
    "what is the relationship",
)
VECTOR_SEARCH_K = 12
LEXICAL_SEARCH_K = 8
PER_DOC_RESULT_LIMIT = 12
MERGED_RESULT_LIMIT = 36
RERANK_TOP_K = 12
DEFAULT_SOURCE_COUNT = 5
DEFAULT_CONTEXT_COUNT = 8
NEIGHBOR_OFFSETS = (1, -1, 2, -2)


class AskRequest(BaseModel):
    question: str
    doc_id: str | None = None
    doc_ids: list[str] | None = None
    history: list[dict] | None = None


# =========================
# NORMALIZATION
# =========================
def rewrite_query(question: str):
    return question.strip() if question else ""


def tokenize(text: str):
    if not text:
        return []

    tokens = re.findall(r"\w+", text.lower())
    return [token for token in tokens if len(token) > 2 and token not in STOPWORDS]


def is_summary_query(question: str):
    raw_tokens = re.findall(r"\w+", (question or "").lower())
    return any(token in SUMMARY_HINTS for token in raw_tokens)


def is_follow_up_question(question: str):
    raw_tokens = re.findall(r"\w+", (question or "").lower())
    if len(raw_tokens) <= 4:
        return True
    return any(token in FOLLOW_UP_HINTS for token in raw_tokens)


def is_comparison_query(question: str) -> bool:
    lowered_question = (question or "").lower()
    raw_tokens = re.findall(r"\w+", lowered_question)

    if any(token in COMPARISON_HINTS for token in raw_tokens):
        return True

    return any(phrase in lowered_question for phrase in COMPARISON_PHRASES)


def detect_prompt_mode(question: str, document_count: int) -> str:
    if document_count <= 1:
        return "grounded"

    if is_comparison_query(question):
        return "comparison"

    return "multi_document"


def build_effective_query(question: str, history: list[dict] | None = None) -> str:
    if not history or not is_follow_up_question(question):
        return question

    last_user = ""
    last_assistant = ""

    for turn in reversed(history):
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if not content:
            continue

        if role == "assistant" and not last_assistant:
            last_assistant = content[:500]
            continue

        if role == "user":
            last_user = content[:200]
            break

    contextual_parts = [part for part in [last_user, last_assistant, question] if part]
    return " ".join(contextual_parts)


# =========================
# SINGLE NORMALIZER
# =========================
def normalize_loaded(doc_id: str, loaded: dict):
    metadata = loaded.get("metadata", {})
    return {
        "doc_id": doc_id,
        "documents": loaded.get("documents", []),
        "index": loaded.get("index"),
        "name": metadata.get("filename") or doc_id,
        "path": metadata.get("path"),
        "metadata": metadata,
    }


def get_document_cache_key(user_id: str, doc_id: str) -> str:
    return f"{user_id}:{doc_id}"


def normalize_requested_doc_ids(data: AskRequest) -> list[str]:
    requested_doc_ids: list[str] = []

    for candidate in [data.doc_id, *(data.doc_ids or [])]:
        if not isinstance(candidate, str):
            continue

        normalized = candidate.strip()
        if normalized and normalized not in requested_doc_ids:
            requested_doc_ids.append(normalized)

    return requested_doc_ids


def get_document_name(doc: dict) -> str:
    metadata = doc.get("metadata", {})
    return metadata.get("filename") or doc.get("name") or doc.get("doc_id") or "Document"


def build_document_label(doc: dict) -> str:
    raw_name = get_document_name(doc)
    normalized = re.sub(r"[_-]+", " ", Path(raw_name).stem).strip()
    normalized = re.sub(r"\s+", " ", normalized)

    if not normalized:
        normalized = str(doc.get("doc_id") or "Document")

    return normalized.title() if normalized.islower() else normalized


def chunk_signature(chunk: dict):
    return (
        chunk.get("doc_id"),
        chunk.get("chunk_id") if chunk.get("chunk_id") is not None else chunk.get("id"),
        chunk.get("page"),
        (chunk.get("text") or "").strip(),
    )


def enrich_chunk(chunk: dict, doc: dict, rank: int) -> dict:
    enriched = dict(chunk)
    enriched["doc_id"] = doc.get("doc_id")
    enriched["file_id"] = chunk.get("file_id") or doc.get("doc_id")
    enriched["doc_name"] = get_document_name(doc)
    enriched["doc_label"] = build_document_label(doc)
    enriched["retrieval_rank"] = rank
    return enriched


def dedupe_chunks(chunks: list[dict]) -> list[dict]:
    unique_chunks = []
    seen_signatures = set()

    for chunk in chunks:
        signature = chunk_signature(chunk)
        if signature in seen_signatures:
            continue

        seen_signatures.add(signature)
        unique_chunks.append(chunk)

    return unique_chunks


def ensure_source_count(
    selected_chunks: list[dict],
    fallback_chunks: list[dict],
    target_count: int,
) -> list[dict]:
    if target_count <= 0:
        return []

    combined_chunks = []
    seen_signatures = set()

    for chunk in [*(selected_chunks or []), *(fallback_chunks or [])]:
        signature = chunk_signature(chunk)
        if signature in seen_signatures:
            continue

        seen_signatures.add(signature)
        combined_chunks.append(chunk)

        if len(combined_chunks) >= target_count:
            break

    return combined_chunks


def get_chunk_identifier(chunk: dict):
    if chunk.get("chunk_id") is not None:
        return chunk.get("chunk_id")

    return chunk.get("id")


def get_context_target_count(prompt_mode: str) -> int:
    if prompt_mode == "grounded":
        return 6

    return DEFAULT_CONTEXT_COUNT


def get_fallback_chunk_count(prompt_mode: str) -> int:
    if prompt_mode == "comparison":
        return 3
    if prompt_mode == "multi_document":
        return 2

    return 5


def build_neighbor_results(docs: list[dict], seed_chunks: list[dict], limit: int = 12) -> list[dict]:
    if not seed_chunks or limit <= 0:
        return []

    docs_by_id = {
        doc.get("doc_id"): doc
        for doc in docs
        if doc.get("doc_id") and doc.get("documents")
    }
    chunk_positions_by_doc = {}
    neighbor_results = []
    seen_signatures = {chunk_signature(chunk) for chunk in seed_chunks}

    for seed_chunk in seed_chunks:
        doc_id = seed_chunk.get("doc_id")
        doc = docs_by_id.get(doc_id)
        if not doc:
            continue

        documents = doc.get("documents", [])
        if not documents:
            continue

        chunk_positions = chunk_positions_by_doc.setdefault(
            doc_id,
            {
                get_chunk_identifier(chunk): index
                for index, chunk in enumerate(documents)
                if get_chunk_identifier(chunk) is not None
            },
        )
        seed_identifier = get_chunk_identifier(seed_chunk)
        seed_position = chunk_positions.get(seed_identifier)
        if seed_position is None:
            continue

        for offset in NEIGHBOR_OFFSETS:
            neighbor_position = seed_position + offset
            if neighbor_position < 0 or neighbor_position >= len(documents):
                continue

            neighbor_chunk = enrich_chunk(
                documents[neighbor_position],
                doc,
                rank=neighbor_position + 1,
            )
            signature = chunk_signature(neighbor_chunk)
            if signature in seen_signatures:
                continue

            seen_signatures.add(signature)
            neighbor_results.append(neighbor_chunk)

            if len(neighbor_results) >= limit:
                return neighbor_results

    return neighbor_results


# =========================
# CONTEXT
# =========================
def build_context(chunks: list[dict]) -> str:
    grouped_chunks: dict[str, list[dict]] = defaultdict(list)
    document_order: list[str] = []

    for chunk in chunks:
        text = (chunk.get("text") or "").strip()
        doc_id = chunk.get("doc_id") or "document"
        if not text:
            continue

        if doc_id not in grouped_chunks:
            document_order.append(doc_id)

        grouped_chunks[doc_id].append(chunk)

    sections = []

    for doc_id in document_order:
        doc_chunks = grouped_chunks[doc_id]
        if not doc_chunks:
            continue

        label = doc_chunks[0].get("doc_label") or doc_chunks[0].get("doc_name") or doc_id
        section_lines = [f"[{label}]"]

        for index, chunk in enumerate(doc_chunks, 1):
            page_number = chunk.get("page")
            page_suffix = f" (page {page_number + 1})" if isinstance(page_number, int) else ""
            section_lines.append(f"Excerpt {index}{page_suffix}:")
            section_lines.append((chunk.get("text") or "").strip())

        sections.append("\n".join(section_lines))

    return "\n\n".join(sections)


# =========================
# SOURCES
# =========================
def format_sources(chunks):
    sources = []

    for i, chunk in enumerate(chunks, 1):
        sources.append({
            "id": i,
            "text": (chunk.get("text") or "")[:200],
            "doc_id": chunk.get("doc_id"),
            "doc_name": chunk.get("doc_name"),
            "doc_label": chunk.get("doc_label"),
            "score": round(chunk.get("score", 0), 4) if chunk.get("score") is not None else None,
            "chunk_id": chunk.get("id") or chunk.get("chunk_id"),
            "page": chunk.get("page"),
            "bbox": chunk.get("bbox"),
            "line_boxes": chunk.get("line_boxes", []),
        })

    return sources


# =========================
# LOAD DOCUMENT SAFE
# =========================
def get_document(user_id: str, doc_id: str):
    cache_key = get_document_cache_key(user_id, doc_id)
    if cache_key in DOCUMENTS:
        cached_doc = DOCUMENTS[cache_key]
        if not cached_doc.get("doc_id"):
            cached_doc["doc_id"] = doc_id
        if not cached_doc.get("name"):
            cached_doc["name"] = get_document_name(cached_doc)
        return cached_doc

    loaded = load_document(doc_id, user_id)

    if not loaded:
        return None

    doc = normalize_loaded(doc_id, loaded)

    if not doc.get("documents"):
        return None

    DOCUMENTS[cache_key] = doc
    return doc


def resolve_documents(user_id: str, requested_doc_ids: list[str]):
    if requested_doc_ids:
        docs = []

        for requested_doc_id in requested_doc_ids:
            doc = get_document(user_id, requested_doc_id)
            if not doc:
                raise HTTPException(
                    status_code=404,
                    detail=f"Documento nao encontrado ou invalido: {requested_doc_id}",
                )
            docs.append(doc)

        return docs

    docs = []

    for record in iter_saved_documents(user_id):
        current_id = record["doc_id"]
        doc = get_document(user_id, current_id)
        if doc:
            docs.append(doc)

    if not docs:
        raise HTTPException(status_code=404, detail="Nenhum documento disponivel")

    return docs


# =========================
# SEARCH WRAPPER SAFE
# =========================
def run_search(doc: dict, query: str):
    if RAG_MODE != "full" or model is None or not doc.get("index"):
        return []

    try:
        return search(
            query=query,
            model=model,
            index=doc["index"],
            documents=doc["documents"],
            k=VECTOR_SEARCH_K,
        )
    except Exception as error:
        print("SEARCH ERROR:", error)
        return []


def lexical_search(documents: list[dict], query: str, k: int = 6):
    query_tokens = set(tokenize(query))

    if not query_tokens:
        return []

    scored = []

    for index, chunk in enumerate(documents):
        text = (chunk.get("text") or "").strip()
        if not text:
            continue

        text_tokens = set(tokenize(text))
        overlap = query_tokens & text_tokens
        if not overlap:
            continue

        coverage = len(overlap) / max(len(query_tokens), 1)
        density = len(overlap) / max(len(text_tokens), 1)
        score = round((coverage * 0.8) + (density * 0.2), 4)

        scored.append({
            "id": index,
            "text": text,
            "doc_id": chunk.get("doc_id"),
            "file_id": chunk.get("file_id"),
            "score": score,
            "chunk_id": chunk.get("id"),
            "page": chunk.get("page"),
            "bbox": chunk.get("bbox"),
            "line_boxes": chunk.get("line_boxes", []),
        })

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:k]


def first_chunks(documents, k=5):
    selected = []

    for index, chunk in enumerate(documents):
        text = (chunk.get("text") or "").strip()
        if not text:
            continue

        selected.append({
            "id": index,
            "text": text,
            "doc_id": chunk.get("doc_id"),
            "file_id": chunk.get("file_id"),
            "score": 0.0,
            "chunk_id": chunk.get("id"),
            "page": chunk.get("page"),
            "bbox": chunk.get("bbox"),
            "line_boxes": chunk.get("line_boxes", []),
        })

        if len(selected) >= k:
            break

    return selected


def all_chunks(documents, k=8):
    return first_chunks(documents, k=k)


def merge_unique_results(*collections: list[dict], limit: int | None = None) -> list[dict]:
    merged_results = []
    seen_signatures = set()

    for collection in collections:
        for chunk in collection:
            signature = chunk_signature(chunk)
            if signature in seen_signatures:
                continue

            seen_signatures.add(signature)
            merged_results.append(chunk)

            if limit is not None and len(merged_results) >= limit:
                return merged_results

    return merged_results


def gather_results_for_doc(
    doc: dict,
    question: str,
    effective_question: str,
    prompt_mode: str,
) -> list[dict]:
    documents = doc.get("documents", [])
    if not documents:
        return []

    vector_results = run_search(doc, effective_question)
    lexical_results = lexical_search(documents, effective_question, k=LEXICAL_SEARCH_K)
    original_lexical_results = (
        lexical_search(documents, question, k=LEXICAL_SEARCH_K)
        if effective_question != question
        else []
    )

    doc_results = merge_unique_results(
        vector_results,
        lexical_results,
        original_lexical_results,
        limit=PER_DOC_RESULT_LIMIT,
    )

    if not doc_results and is_summary_query(question):
        doc_results = all_chunks(documents, k=6 if RAG_MODE != "full" else 5)

    if not doc_results and prompt_mode == "comparison":
        doc_results = first_chunks(documents, k=2)
    elif not doc_results and prompt_mode == "multi_document":
        doc_results = first_chunks(documents, k=1)
    elif not doc_results and RAG_MODE != "full" and len(documents) <= 12:
        doc_results = all_chunks(documents, k=min(len(documents), 8))

    return [enrich_chunk(chunk, doc, rank) for rank, chunk in enumerate(doc_results, 1)]


def interleave_results(results_by_doc: list[tuple[str, list[dict]]], limit: int = 24) -> list[dict]:
    queues = [(doc_id, deque(results)) for doc_id, results in results_by_doc if results]
    merged_results = []

    while queues and len(merged_results) < limit:
        progressed = False

        for _, queue in queues:
            if not queue:
                continue

            merged_results.append(queue.popleft())
            progressed = True

            if len(merged_results) >= limit:
                break

        if not progressed:
            break

    return merged_results


def build_fallback_results(docs: list[dict], prompt_mode: str) -> list[dict]:
    per_doc_fallback = []
    fallback_chunk_count = get_fallback_chunk_count(prompt_mode)

    for doc in docs:
        documents = doc.get("documents", [])
        if not documents:
            continue

        fallback_chunks = first_chunks(documents, k=fallback_chunk_count)

        per_doc_fallback.append((
            doc.get("doc_id"),
            [enrich_chunk(chunk, doc, rank) for rank, chunk in enumerate(fallback_chunks, 1)],
        ))

    return interleave_results(per_doc_fallback, limit=12)


def gather_results(
    docs: list[dict],
    question: str,
    effective_question: str,
    prompt_mode: str,
) -> list[dict]:
    results_by_doc = []

    for doc in docs:
        results_by_doc.append((
            doc.get("doc_id"),
            gather_results_for_doc(doc, question, effective_question, prompt_mode),
        ))

    merged_results = dedupe_chunks(interleave_results(results_by_doc, limit=MERGED_RESULT_LIMIT))

    if merged_results:
        return merged_results

    return dedupe_chunks(build_fallback_results(docs, prompt_mode))


def apply_document_diversity(chunks: list[dict], top_k: int) -> list[dict]:
    if len(chunks) <= 1:
        return chunks[:top_k]

    available_doc_ids = []

    for chunk in chunks:
        doc_id = chunk.get("doc_id")
        if doc_id and doc_id not in available_doc_ids:
            available_doc_ids.append(doc_id)

    if len(available_doc_ids) <= 1:
        return chunks[:top_k]

    selected_chunks = []
    selected_signatures = set()
    covered_doc_ids = set()

    for chunk in chunks:
        doc_id = chunk.get("doc_id")
        signature = chunk_signature(chunk)
        if not doc_id or doc_id in covered_doc_ids or signature in selected_signatures:
            continue

        selected_chunks.append(chunk)
        covered_doc_ids.add(doc_id)
        selected_signatures.add(signature)

        if len(selected_chunks) >= min(top_k, len(available_doc_ids)):
            break

    for chunk in chunks:
        signature = chunk_signature(chunk)
        if signature in selected_signatures:
            continue

        selected_chunks.append(chunk)
        selected_signatures.add(signature)

        if len(selected_chunks) >= top_k:
            break

    return selected_chunks[:top_k]


# =========================
# MAIN ENDPOINT
# =========================
@router.post("/ask")
async def ask_question(
    data: AskRequest,
    current_user: User = Depends(get_current_user),
):
    request_started_at = perf_counter()
    requested_doc_ids = normalize_requested_doc_ids(data)

    try:
        question = rewrite_query(data.question)

        if not question:
            raise HTTPException(status_code=400, detail="question e obrigatorio")

        docs = resolve_documents(current_user.id, requested_doc_ids)
        prompt_mode = detect_prompt_mode(question, len(docs))
        effective_question = build_effective_query(question, data.history)

        retrieval_started_at = perf_counter()
        all_results = gather_results(docs, question, effective_question, prompt_mode)
        retrieval_ms = round((perf_counter() - retrieval_started_at) * 1000, 2)

        if not all_results:
            logger.info(
                "ask_no_results doc_ids=%s prompt_mode=%s question=%r effective_question=%r history_turns=%s retrieval_ms=%s",
                requested_doc_ids or None,
                prompt_mode,
                question[:200],
                effective_question[:300],
                len(data.history or []),
                retrieval_ms,
            )
            return {
                "question": question,
                "answer": "Nao consegui recuperar trechos suficientes para responder.",
                "sources": [],
            }

        candidate_chunks = [chunk for chunk in all_results[:MERGED_RESULT_LIMIT] if chunk.get("text")]
        rerank_started_at = perf_counter()
        reranked_chunks = (
            rerank(effective_question, candidate_chunks, top_k=RERANK_TOP_K)
            if candidate_chunks and RAG_MODE == "full"
            else candidate_chunks[:RERANK_TOP_K]
        )
        fallback_chunks = build_fallback_results(docs, prompt_mode)
        neighbor_chunks = build_neighbor_results(
            docs,
            reranked_chunks or candidate_chunks,
            limit=max(DEFAULT_CONTEXT_COUNT, DEFAULT_SOURCE_COUNT),
        )
        available_chunk_count = len(
            merge_unique_results(
                candidate_chunks,
                neighbor_chunks,
                fallback_chunks,
            )
        )
        desired_source_count = min(DEFAULT_SOURCE_COUNT, available_chunk_count)
        desired_context_count = min(
            get_context_target_count(prompt_mode),
            available_chunk_count,
        )

        context_chunks = apply_document_diversity(
            reranked_chunks,
            top_k=max(desired_context_count, 1),
        )
        context_chunks = ensure_source_count(context_chunks, reranked_chunks, desired_context_count)
        context_chunks = ensure_source_count(context_chunks, candidate_chunks, desired_context_count)
        context_chunks = ensure_source_count(context_chunks, neighbor_chunks, desired_context_count)
        context_chunks = ensure_source_count(context_chunks, fallback_chunks, desired_context_count)

        source_chunks = apply_document_diversity(
            context_chunks,
            top_k=max(desired_source_count, 1),
        )
        source_chunks = ensure_source_count(source_chunks, context_chunks, desired_source_count)
        source_chunks = ensure_source_count(source_chunks, neighbor_chunks, desired_source_count)
        source_chunks = ensure_source_count(source_chunks, fallback_chunks, desired_source_count)
        rerank_ms = round((perf_counter() - rerank_started_at) * 1000, 2)

        if not context_chunks or not source_chunks:
            logger.info(
                "ask_no_top_chunks doc_ids=%s prompt_mode=%s question=%r effective_question=%r history_turns=%s retrieval_ms=%s rerank_ms=%s",
                requested_doc_ids or None,
                prompt_mode,
                question[:200],
                effective_question[:300],
                len(data.history or []),
                retrieval_ms,
                rerank_ms,
            )
            return {
                "question": question,
                "answer": "Nao consegui recuperar trechos suficientes para responder.",
                "sources": [],
            }

        context = build_context(context_chunks)
        llm_started_at = perf_counter()
        answer = generate_answer(
            question,
            context,
            data.history,
            prompt_mode=prompt_mode,
        )
        llm_ms = round((perf_counter() - llm_started_at) * 1000, 2)
        total_ms = round((perf_counter() - request_started_at) * 1000, 2)

        logger.info(
            "ask_completed doc_ids=%s rag_mode=%s prompt_mode=%s question=%r effective_question=%r history_turns=%s retrieval_results=%s selected_chunks=%s retrieval_ms=%s rerank_ms=%s llm_ms=%s total_ms=%s",
            requested_doc_ids or None,
            RAG_MODE,
            prompt_mode,
            question[:200],
            effective_question[:300],
            len(data.history or []),
            len(all_results),
            len(source_chunks),
            retrieval_ms,
            rerank_ms,
            llm_ms,
            total_ms,
        )

        return {
            "question": question,
            "answer": answer,
            "sources": format_sources(source_chunks),
        }

    except Exception as error:
        if isinstance(error, HTTPException):
            logger.warning(
                "ask_http_error doc_ids=%s question=%r status_code=%s detail=%r",
                requested_doc_ids or None,
                (data.question or "")[:200],
                error.status_code,
                error.detail,
            )
            raise
        print("ERRO NO /ASK")
        traceback.print_exc()
        logger.exception(
            "ask_unhandled_error doc_ids=%s question=%r",
            requested_doc_ids or None,
            (data.question or "")[:200],
        )
        raise HTTPException(status_code=500, detail=str(error))


# =========================
# COMPAT LAYER
# =========================
def search_similar_documents(
    question: str,
    doc_id: str = None,
    user_id: str | None = None,
):
    try:
        if not doc_id or not user_id:
            return []

        doc = get_document(user_id, doc_id)
        if not doc:
            return []

        return run_search(doc, question)

    except Exception as error:
        print("ERRO search_similar_documents:", error)
        return []
