from time import perf_counter

from app.services.context_reasoning import retrieve_chunks
from app.services.query_heuristics import (
    build_effective_query,
    build_low_quality_response,
    detect_prompt_mode,
    is_low_quality_chunk,
    rewrite_query,
)
from app.services.query_response import build_context, format_sources
from app.services.query_retrieval import (
    DEFAULT_CONTEXT_COUNT,
    DEFAULT_SOURCE_COUNT,
    MERGED_RESULT_LIMIT,
    apply_document_diversity,
    build_fallback_results,
    build_neighbor_results,
    ensure_source_count,
    gather_results,
    get_context_target_count,
    merge_unique_results,
    normalize_requested_doc_ids,
    prefer_usable_chunks,
    resolve_documents,
)


def build_sparse_response(question: str) -> dict:
    return {
        "question": question,
        "answer": "Nao consegui recuperar trechos suficientes para responder.",
        "sources": [],
    }


def answer_question(
    *,
    question: str,
    doc_id: str | None,
    doc_ids: list[str] | None,
    history: list[dict] | None,
    user_id: str,
    rag_mode: str,
    generate_answer_fn,
    rerank_fn,
    reasoning_fn,
    embedding_model,
    reranker_model_value,
    logger,
) -> dict:
    request_started_at = perf_counter()
    requested_doc_ids = normalize_requested_doc_ids(doc_id, doc_ids)
    rewritten_question = rewrite_query(question)

    if not rewritten_question:
        from fastapi import HTTPException  # local import keeps this module lightweight

        raise HTTPException(status_code=400, detail="question e obrigatorio")

    docs = resolve_documents(user_id, requested_doc_ids)
    prompt_mode = detect_prompt_mode(rewritten_question, len(docs))
    effective_question = build_effective_query(rewritten_question, history)

    retrieval_started_at = perf_counter()
    retrieval_bundle = retrieve_chunks(
        rewritten_question,
        docs,
        effective_question=effective_question,
        prompt_mode=prompt_mode,
        retriever=lambda local_docs, current_question, current_effective_question, current_prompt_mode: gather_results(
            local_docs,
            current_question,
            current_effective_question,
            current_prompt_mode,
            rag_mode=rag_mode,
        ),
        limit=MERGED_RESULT_LIMIT,
    )
    all_results = retrieval_bundle["all_results"]
    candidate_chunks = retrieval_bundle["candidate_chunks"]
    retrieval_ms = round((perf_counter() - retrieval_started_at) * 1000, 2)

    if not all_results:
        logger.info(
            "ask_no_results doc_ids=%s prompt_mode=%s question=%r effective_question=%r history_turns=%s retrieval_ms=%s",
            requested_doc_ids or None,
            prompt_mode,
            rewritten_question[:200],
            effective_question[:300],
            len(history or []),
            retrieval_ms,
        )
        return build_sparse_response(rewritten_question)

    usable_candidate_chunks = [chunk for chunk in candidate_chunks if not is_low_quality_chunk(chunk)]
    if usable_candidate_chunks:
        candidate_chunks = usable_candidate_chunks
    elif candidate_chunks:
        logger.info(
            "ask_low_quality_context doc_ids=%s prompt_mode=%s question=%r effective_question=%r history_turns=%s",
            requested_doc_ids or None,
            prompt_mode,
            rewritten_question[:200],
            effective_question[:300],
            len(history or []),
        )
        return build_low_quality_response(rewritten_question)

    rerank_started_at = perf_counter()
    reranked_chunks = (
        rerank_fn(effective_question, candidate_chunks, top_k=12)
        if candidate_chunks and rag_mode == "full"
        else candidate_chunks[:12]
    )
    fallback_chunks = prefer_usable_chunks(build_fallback_results(docs, prompt_mode))
    neighbor_chunks = prefer_usable_chunks(build_neighbor_results(
        docs,
        reranked_chunks or candidate_chunks,
        limit=max(DEFAULT_CONTEXT_COUNT, DEFAULT_SOURCE_COUNT),
    ))
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

    usable_context_chunks = [chunk for chunk in context_chunks if not is_low_quality_chunk(chunk)]
    if not usable_context_chunks:
        logger.info(
            "ask_low_quality_final_context doc_ids=%s prompt_mode=%s question=%r effective_question=%r history_turns=%s",
            requested_doc_ids or None,
            prompt_mode,
            rewritten_question[:200],
            effective_question[:300],
            len(history or []),
        )
        return build_low_quality_response(rewritten_question)

    context_chunks = usable_context_chunks[:desired_context_count]
    usable_source_chunks = [chunk for chunk in source_chunks if not is_low_quality_chunk(chunk)]
    source_chunks = usable_source_chunks[:desired_source_count] or context_chunks[:desired_source_count]

    reasoning_pool = merge_unique_results(
        reranked_chunks,
        candidate_chunks,
        neighbor_chunks,
        fallback_chunks,
        limit=max(desired_context_count + desired_source_count + 4, 14),
    )
    reasoning_started_at = perf_counter()
    reasoning_result = reasoning_fn(
        rewritten_question,
        reasoning_pool,
        semantic_model=embedding_model if rag_mode == "full" else None,
        cross_encoder=(
            reranker_model_value
            if rag_mode == "full" and reranker_model_value is not None and len(reasoning_pool) <= 14
            else None
        ),
        desired_source_count=desired_source_count,
        desired_context_count=desired_context_count,
        max_reasoning_chunks=max(desired_context_count + desired_source_count + 2, 12),
    )
    reasoning_ms = round((perf_counter() - reasoning_started_at) * 1000, 2)

    reasoned_context_chunks = reasoning_result.get("context_chunks") or []
    reasoned_source_chunks = reasoning_result.get("source_chunks") or []
    structured_context = (reasoning_result.get("structured_context") or "").strip()
    context_metrics = reasoning_result.get("metrics") or {}
    baseline_context_chunks = list(context_chunks)
    baseline_source_chunks = list(source_chunks)

    if reasoned_context_chunks:
        context_chunks = apply_document_diversity(
            reasoned_context_chunks,
            top_k=max(desired_context_count, 1),
        )
        context_chunks = ensure_source_count(
            context_chunks,
            baseline_context_chunks,
            desired_context_count,
        )

    if reasoned_source_chunks:
        source_chunks = apply_document_diversity(
            reasoned_source_chunks,
            top_k=max(desired_source_count, 1),
        )
        source_chunks = ensure_source_count(
            source_chunks,
            baseline_source_chunks,
            desired_source_count,
        )
        source_chunks = ensure_source_count(
            source_chunks,
            context_chunks,
            desired_source_count,
        )

    if not context_chunks or not source_chunks:
        logger.info(
            "ask_no_top_chunks doc_ids=%s prompt_mode=%s question=%r effective_question=%r history_turns=%s retrieval_ms=%s rerank_ms=%s reasoning_ms=%s",
            requested_doc_ids or None,
            prompt_mode,
            rewritten_question[:200],
            effective_question[:300],
            len(history or []),
            retrieval_ms,
            rerank_ms,
            reasoning_ms,
        )
        return build_sparse_response(rewritten_question)

    context = structured_context or build_context(context_chunks)
    llm_started_at = perf_counter()
    answer = generate_answer_fn(
        rewritten_question,
        context,
        history,
        prompt_mode=prompt_mode,
    )
    llm_ms = round((perf_counter() - llm_started_at) * 1000, 2)
    total_ms = round((perf_counter() - request_started_at) * 1000, 2)

    logger.info(
        "ask_completed doc_ids=%s rag_mode=%s prompt_mode=%s question=%r effective_question=%r history_turns=%s retrieval_results=%s selected_chunks=%s retrieval_ms=%s rerank_ms=%s reasoning_ms=%s llm_ms=%s total_ms=%s context_metrics=%s",
        requested_doc_ids or None,
        rag_mode,
        prompt_mode,
        rewritten_question[:200],
        effective_question[:300],
        len(history or []),
        len(all_results),
        len(source_chunks),
        retrieval_ms,
        rerank_ms,
        reasoning_ms,
        llm_ms,
        total_ms,
        context_metrics,
    )

    return {
        "question": rewritten_question,
        "answer": answer,
        "sources": format_sources(source_chunks),
    }
