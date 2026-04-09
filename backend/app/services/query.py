from fastapi import APIRouter, HTTPException
import logging
import os
import re
import traceback
from time import perf_counter

from pydantic import BaseModel

from app.config import DATA_DIR, RAG_MODE
from app.services.similarity import search
from app.services.embeddings import model
from app.services.llm import generate_answer
from app.services.reranker import rerank
from app.services.storage import load_document

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


class AskRequest(BaseModel):
    question: str
    doc_id: str | None = None
    history: list[dict] | None = None


# =========================
# NORMALIZATION
# =========================
def rewrite_query(question: str):
    return question.strip().lower() if question else ""


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
        "name": metadata.get("filename"),
        "path": metadata.get("path"),
        "metadata": metadata,
    }


# =========================
# CONTEXT
# =========================
def build_context(chunks):
    formatted = []

    for i, chunk in enumerate(chunks, 1):
        text = chunk.get("text", "")
        if text:
            formatted.append(f"[TRECHO {i}]\n{text}")

    return "\n\n".join(formatted)


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
def get_document(doc_id: str):
    if doc_id in DOCUMENTS:
        return DOCUMENTS[doc_id]

    loaded = load_document(doc_id)

    if not loaded:
        return None

    doc = normalize_loaded(doc_id, loaded)

    if not doc.get("documents"):
        return None

    DOCUMENTS[doc_id] = doc
    return doc


# =========================
# SEARCH WRAPPER SAFE
# =========================
def run_search(doc, query):
    if RAG_MODE != "full" or model is None or not doc.get("index"):
        return []

    try:
        return search(
            query=query,
            model=model,
            index=doc["index"],
            documents=doc["documents"],
            k=10,
        )
    except Exception as error:
        print("SEARCH ERROR:", error)
        return []


def lexical_search(documents, query, k=5):
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


# =========================
# MAIN ENDPOINT
# =========================
@router.post("/ask")
async def ask_question(data: AskRequest):
    request_started_at = perf_counter()
    try:
        question = rewrite_query(data.question)
        doc_id = data.doc_id
        effective_question = build_effective_query(question, data.history)

        if not question:
            raise HTTPException(status_code=400, detail="question é obrigatório")

        all_results = []
        retrieval_started_at = perf_counter()

        # =========================
        # SINGLE DOC MODE
        # =========================
        if doc_id:
            doc = get_document(doc_id)

            if not doc:
                raise HTTPException(status_code=404, detail="Documento não encontrado ou inválido")

            if RAG_MODE != "full" and len(doc.get("documents", [])) <= 12:
                all_results.extend(all_chunks(doc.get("documents", []), k=8))
            else:
                all_results.extend(run_search(doc, effective_question))
                if not all_results:
                    all_results.extend(lexical_search(doc.get("documents", []), effective_question))
                if not all_results and is_summary_query(question):
                    all_results.extend(first_chunks(doc.get("documents", []), k=5))

        # =========================
        # MULTI DOC MODE
        # =========================
        else:
            docs = []

            if not os.path.exists(DATA_DIR):
                raise HTTPException(status_code=500, detail="DATA_DIR não encontrado")

            for file in os.listdir(DATA_DIR):
                if file.endswith(".json"):
                    current_id = file.replace(".json", "")

                    doc = get_document(current_id)
                    if doc:
                        docs.append(doc)

            if not docs:
                raise HTTPException(status_code=404, detail="Nenhum documento disponível")

            for doc in docs:
                if RAG_MODE != "full" and len(doc.get("documents", [])) <= 12:
                    results = all_chunks(doc.get("documents", []), k=8)
                else:
                    results = run_search(doc, effective_question)
                    if not results:
                        results = lexical_search(doc.get("documents", []), effective_question)
                    if not results and is_summary_query(question):
                        results = first_chunks(doc.get("documents", []), k=5)
                all_results.extend(results)

        retrieval_ms = round((perf_counter() - retrieval_started_at) * 1000, 2)

        # =========================
        # NO RESULTS
        # =========================
        if not all_results:
            logger.info(
                "ask_no_results doc_id=%s question=%r effective_question=%r history_turns=%s retrieval_ms=%s",
                doc_id,
                question[:200],
                effective_question[:300],
                len(data.history or []),
                retrieval_ms,
            )
            return {
                "question": question,
                "answer": "Não encontrei informações relevantes no documento.",
                "sources": [],
            }

        # =========================
        # RERANK SAFE
        # =========================
        candidate_chunks = [chunk for chunk in all_results[:20] if chunk.get("text")]
        rerank_started_at = perf_counter()
        top_chunks = (
            rerank(effective_question, candidate_chunks, top_k=5)
            if candidate_chunks and RAG_MODE == "full"
            else candidate_chunks[:5]
        )
        if not top_chunks and doc_id:
            doc = get_document(doc_id)
            if doc:
                if RAG_MODE != "full" and len(doc.get("documents", [])) <= 12:
                    top_chunks = all_chunks(doc.get("documents", []), k=8)
                else:
                    top_chunks = lexical_search(doc.get("documents", []), effective_question)
                    if not top_chunks and is_summary_query(question):
                        top_chunks = first_chunks(doc.get("documents", []), k=5)
        rerank_ms = round((perf_counter() - rerank_started_at) * 1000, 2)

        if not top_chunks:
            logger.info(
                "ask_no_top_chunks doc_id=%s question=%r effective_question=%r history_turns=%s retrieval_ms=%s rerank_ms=%s",
                doc_id,
                question[:200],
                effective_question[:300],
                len(data.history or []),
                retrieval_ms,
                rerank_ms,
            )
            return {
                "question": question,
                "answer": "Não encontrei informações relevantes no documento.",
                "sources": [],
            }

        # =========================
        # CONTEXT + LLM
        # =========================
        context = build_context(top_chunks)
        llm_started_at = perf_counter()
        answer = generate_answer(question, context, data.history)
        llm_ms = round((perf_counter() - llm_started_at) * 1000, 2)
        total_ms = round((perf_counter() - request_started_at) * 1000, 2)

        logger.info(
            "ask_completed doc_id=%s rag_mode=%s question=%r effective_question=%r history_turns=%s retrieval_results=%s selected_chunks=%s retrieval_ms=%s rerank_ms=%s llm_ms=%s total_ms=%s",
            doc_id,
            RAG_MODE,
            question[:200],
            effective_question[:300],
            len(data.history or []),
            len(all_results),
            len(top_chunks),
            retrieval_ms,
            rerank_ms,
            llm_ms,
            total_ms,
        )

        # =========================
        # RESPONSE
        # =========================
        return {
            "question": question,
            "answer": answer,
            "sources": format_sources(top_chunks),
        }

    except Exception as error:
        if isinstance(error, HTTPException):
            logger.warning(
                "ask_http_error doc_id=%s question=%r status_code=%s detail=%r",
                data.doc_id,
                (data.question or "")[:200],
                error.status_code,
                error.detail,
            )
            raise
        print("ERRO NO /ASK")
        traceback.print_exc()
        logger.exception(
            "ask_unhandled_error doc_id=%s question=%r",
            data.doc_id,
            (data.question or "")[:200],
        )
        raise HTTPException(status_code=500, detail=str(error))


# =========================
# COMPAT LAYER
# =========================
def search_similar_documents(question: str, doc_id: str = None):
    try:
        if not doc_id:
            return []

        doc = get_document(doc_id)
        if not doc:
            return []

        return run_search(doc, question)

    except Exception as error:
        print("ERRO search_similar_documents:", error)
        return []
