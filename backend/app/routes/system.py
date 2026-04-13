import os

from fastapi import APIRouter, Depends, HTTPException

from app.config import GEMINI_API_KEY, GEMINI_MODEL, RAG_MODE
from app.db.deps import get_current_user
from app.models.user import User
from app.services.embeddings import model as embedding_model
from app.services.query import DOCUMENTS, get_document, get_document_cache_key
from app.services.reranker import reranker_model
from app.services.storage import faiss as faiss_module
from app.services.storage import (
    clear_saved_documents,
    delete_saved_document,
    iter_doc_id_candidates,
    iter_saved_documents,
    resolve_upload_path,
)

router = APIRouter()


def evict_document_cache(user_id: str, doc_id: str):
    for candidate in iter_doc_id_candidates(doc_id):
        DOCUMENTS.pop(get_document_cache_key(user_id, candidate), None)


def serialize_document(record: dict, user_id: str):
    metadata = record.get("metadata") or {}
    documents = record.get("documents") or []
    page_numbers = [
        int(chunk["page"])
        for chunk in documents
        if isinstance(chunk.get("page"), int)
    ]
    pdf_available = (
        resolve_upload_path(record["doc_id"], user_id, metadata) is not None
    )

    return {
        "doc_id": record["doc_id"],
        "name": metadata.get("filename") or f"{record['doc_id']}.pdf",
        "chunks": metadata.get("chunk_count", len(documents)),
        "pages": metadata.get("page_count", (max(page_numbers) + 1) if page_numbers else 0),
        "rag_mode": metadata.get("rag_mode", RAG_MODE),
        "vector_ready": bool(
            metadata.get("vector_ready")
            or record.get("has_index_file")
            or (RAG_MODE == "full" and record.get("index") is not None)
        ),
        "uploaded_at": metadata.get("uploaded_at"),
        "preview": metadata.get("preview") or ((documents[0].get("text") or "")[:220] if documents else ""),
        "pdf_available": pdf_available,
    }


@router.get("/documents")
def list_documents(current_user: User = Depends(get_current_user)):
    documents = [
        serialize_document(record, current_user.id)
        for record in iter_saved_documents(current_user.id)
    ]

    documents.sort(
        key=lambda item: item.get("uploaded_at") or "",
        reverse=True,
    )

    return {"documents": documents}


@router.get("/documents/{doc_id}")
def get_document_details(
    doc_id: str,
    current_user: User = Depends(get_current_user),
):
    doc = get_document(current_user.id, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    payload = {
        "doc_id": doc_id,
        "documents": doc.get("documents", []),
        "index": doc.get("index"),
        "metadata": doc.get("metadata", {}),
    }
    return serialize_document(payload, current_user.id)


@router.delete("/documents/{doc_id}")
def delete_document_entry(
    doc_id: str,
    current_user: User = Depends(get_current_user),
):
    deleted = delete_saved_document(doc_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    evict_document_cache(current_user.id, deleted["doc_id"])

    return {
        "doc_id": deleted["doc_id"],
        "removed": True,
        "removed_files": deleted["removed_files"],
    }


@router.delete("/documents")
def clear_document_library(current_user: User = Depends(get_current_user)):
    deleted_documents = clear_saved_documents(current_user.id)

    for deleted in deleted_documents:
        evict_document_cache(current_user.id, deleted["doc_id"])

    return {
        "removed_count": len(deleted_documents),
        "removed_doc_ids": [deleted["doc_id"] for deleted in deleted_documents],
    }


@router.get("/system/status")
def get_system_status(current_user: User = Depends(get_current_user)):
    indexed_documents = sum(1 for _ in iter_saved_documents(current_user.id))

    return {
        "status": "ok",
        "rag_mode": RAG_MODE,
        "gemini_model": GEMINI_MODEL,
        "llm_configured": bool(GEMINI_API_KEY),
        "embedding_model_loaded": embedding_model is not None,
        "reranker_loaded": reranker_model is not None,
        "vector_search_enabled": (
            RAG_MODE == "full"
            and embedding_model is not None
            and faiss_module is not None
        ),
        "documents_indexed": indexed_documents,
        "workspace_data_available": indexed_documents > 0,
        "pid": os.getpid(),
    }
