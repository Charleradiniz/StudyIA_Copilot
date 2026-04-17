from collections import deque
from pathlib import Path
import logging
import re

from fastapi import HTTPException

from app.services.embeddings import model
from app.services.query_heuristics import (
    MIN_USABLE_CONTEXT_QUALITY,
    analyze_text_quality,
    is_summary_query,
    tokenize,
)
from app.services.similarity import search
from app.services.storage import iter_saved_documents, load_document


logger = logging.getLogger("studyiacopilot.query")
DOCUMENTS: dict[str, dict] = {}
VECTOR_SEARCH_K = 12
LEXICAL_SEARCH_K = 8
PER_DOC_RESULT_LIMIT = 12
MERGED_RESULT_LIMIT = 36
DEFAULT_SOURCE_COUNT = 5
DEFAULT_CONTEXT_COUNT = 8
SUMMARY_SAMPLE_K = 6
NEIGHBOR_OFFSETS = (1, -1, 2, -2)


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


def normalize_requested_doc_ids(doc_id: str | None, doc_ids: list[str] | None) -> list[str]:
    requested_doc_ids: list[str] = []

    for candidate in [doc_id, *(doc_ids or [])]:
        if not isinstance(candidate, str):
            continue

        normalized = candidate.strip()
        if normalized and normalized not in requested_doc_ids:
            requested_doc_ids.append(normalized)

    return requested_doc_ids


def build_chunk_result(chunk: dict, index: int, score: float = 0.0) -> dict:
    return {
        "id": index,
        "text": (chunk.get("text") or "").strip(),
        "doc_id": chunk.get("doc_id"),
        "file_id": chunk.get("file_id"),
        "score": score,
        "chunk_id": chunk.get("id"),
        "page": chunk.get("page"),
        "bbox": chunk.get("bbox"),
        "line_boxes": chunk.get("line_boxes", []),
    }


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


def build_chunk_quality_map(chunks: list[dict]) -> dict[tuple, dict]:
    quality_map = {}
    for chunk in chunks:
        quality_map[chunk_signature(chunk)] = analyze_text_quality(chunk.get("text") or "")
    return quality_map


def prefer_usable_chunks(chunks: list[dict]) -> list[dict]:
    quality_map = build_chunk_quality_map(chunks)
    usable_chunks = [
        chunk
        for chunk in chunks
        if not quality_map.get(chunk_signature(chunk), {}).get("is_low_quality", True)
    ]
    return usable_chunks or chunks


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


def run_search(doc: dict, query: str, rag_mode: str):
    if rag_mode != "full" or model is None or not doc.get("index"):
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
        logger.warning("vector_search_failed doc_id=%s detail=%s", doc.get("doc_id"), error)
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
        scored.append(build_chunk_result(chunk, index, score=score))

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:k]


def first_chunks(documents, k=5):
    selected = []

    for index, chunk in enumerate(documents):
        text = (chunk.get("text") or "").strip()
        if not text:
            continue

        selected.append(build_chunk_result(chunk, index))

        if len(selected) >= k:
            break

    return selected


def all_chunks(documents, k=8):
    return first_chunks(documents, k=k)


def get_representative_chunk_cache(doc: dict) -> dict:
    metadata = doc.setdefault("_derived", {})
    cache = metadata.setdefault("representative_chunks", {})
    return cache


def representative_chunks(documents: list[dict], k: int = SUMMARY_SAMPLE_K) -> list[dict]:
    prepared_chunks = []

    for index, chunk in enumerate(documents):
        text = (chunk.get("text") or "").strip()
        if not text:
            continue

        quality = analyze_text_quality(text)
        length_bonus = min(len(text) / 700, 1.0) * 0.12
        sentence_bonus = 0.08 if any(marker in text for marker in ".!?") else 0.0
        summary_score = round(
            quality["quality_score"]
            + length_bonus
            + sentence_bonus
            - min(quality["code_like_ratio"], 0.6) * 0.25,
            4,
        )
        prepared_chunk = build_chunk_result(chunk, index)
        prepared_chunk["_position"] = index
        prepared_chunk["_quality_score"] = quality["quality_score"]
        prepared_chunk["_summary_score"] = summary_score
        prepared_chunks.append(prepared_chunk)

    if not prepared_chunks:
        return []

    readable_chunks = [
        chunk
        for chunk in prepared_chunks
        if chunk["_quality_score"] >= MIN_USABLE_CONTEXT_QUALITY
    ]
    pool = readable_chunks or prepared_chunks

    if len(pool) <= k:
        selected_chunks = pool
    else:
        selected_chunks = []
        used_signatures = set()
        for step in range(k):
            target_index = round(step * (len(pool) - 1) / max(k - 1, 1))
            window_start = max(0, target_index - 2)
            window_end = min(len(pool), target_index + 3)
            window = [
                chunk
                for chunk in pool[window_start:window_end]
                if chunk_signature(chunk) not in used_signatures
            ]
            if not window:
                continue

            target_position = pool[target_index]["_position"]
            chosen_chunk = max(
                window,
                key=lambda chunk: (
                    chunk["_summary_score"],
                    -abs(chunk["_position"] - target_position),
                ),
            )
            used_signatures.add(chunk_signature(chosen_chunk))
            selected_chunks.append(chosen_chunk)

        if len(selected_chunks) < k:
            for chunk in sorted(
                pool,
                key=lambda item: (item["_summary_score"], item["_quality_score"]),
                reverse=True,
            ):
                if chunk_signature(chunk) in used_signatures:
                    continue
                used_signatures.add(chunk_signature(chunk))
                selected_chunks.append(chunk)
                if len(selected_chunks) >= k:
                    break

    selected_chunks.sort(key=lambda chunk: chunk["_position"])
    return [
        {
            key: value
            for key, value in chunk.items()
            if not key.startswith("_")
        }
        for chunk in selected_chunks
    ]


def get_representative_chunks(doc: dict, k: int = SUMMARY_SAMPLE_K) -> list[dict]:
    cache = get_representative_chunk_cache(doc)
    cache_key = str(k)
    if cache_key not in cache:
        cache[cache_key] = representative_chunks(doc.get("documents", []), k=k)
    return list(cache[cache_key])


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
    *,
    rag_mode: str,
) -> list[dict]:
    documents = doc.get("documents", [])
    if not documents:
        return []

    vector_results = run_search(doc, effective_question, rag_mode=rag_mode)
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

    if is_summary_query(question):
        doc_results = merge_unique_results(
            doc_results,
            get_representative_chunks(doc, k=min(4, SUMMARY_SAMPLE_K)),
            limit=PER_DOC_RESULT_LIMIT,
        )

    if not doc_results and is_summary_query(question):
        doc_results = get_representative_chunks(doc, k=SUMMARY_SAMPLE_K)

    if not doc_results and prompt_mode == "comparison":
        doc_results = first_chunks(documents, k=2)
    elif not doc_results and prompt_mode == "multi_document":
        doc_results = first_chunks(documents, k=1)
    elif not doc_results and rag_mode != "full" and len(documents) <= 12:
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
    *,
    rag_mode: str,
) -> list[dict]:
    results_by_doc = []

    for doc in docs:
        results_by_doc.append((
            doc.get("doc_id"),
            gather_results_for_doc(
                doc,
                question,
                effective_question,
                prompt_mode,
                rag_mode=rag_mode,
            ),
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
