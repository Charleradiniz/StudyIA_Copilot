import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import RAG_MODE
from app.db.deps import get_current_user
from app.models.user import User
from app.services.context_reasoning import run_context_aware_reasoning
from app.services.embeddings import model
from app.services.llm import generate_answer
from app.services.query_orchestration import answer_question
from app.services.query_retrieval import (
    DOCUMENTS,
    ensure_source_count,
    get_document,
    get_document_cache_key,
    normalize_requested_doc_ids,
    run_search,
)
from app.services.reranker import rerank, reranker_model


router = APIRouter()
logger = logging.getLogger("studyiacopilot.query")


class AskRequest(BaseModel):
    question: str
    doc_id: str | None = None
    doc_ids: list[str] | None = None
    history: list[dict] | None = None


@router.post("/ask")
async def ask_question(
    data: AskRequest,
    current_user: User = Depends(get_current_user),
):
    requested_doc_ids = normalize_requested_doc_ids(data.doc_id, data.doc_ids)

    try:
        return answer_question(
            question=data.question,
            doc_id=data.doc_id,
            doc_ids=data.doc_ids,
            history=data.history,
            user_id=current_user.id,
            rag_mode=RAG_MODE,
            generate_answer_fn=generate_answer,
            rerank_fn=rerank,
            reasoning_fn=run_context_aware_reasoning,
            embedding_model=model,
            reranker_model_value=reranker_model,
            logger=logger,
        )
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

        logger.exception(
            "ask_unhandled_error doc_ids=%s question=%r",
            requested_doc_ids or None,
            (data.question or "")[:200],
        )
        raise HTTPException(
            status_code=500,
            detail="The server could not complete this question right now.",
        ) from error


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

        return run_search(doc, question, rag_mode=RAG_MODE)

    except Exception as error:
        logger.warning(
            "search_similar_documents_failed user_id=%s doc_id=%s detail=%s",
            user_id,
            doc_id,
            error,
        )
        return []
