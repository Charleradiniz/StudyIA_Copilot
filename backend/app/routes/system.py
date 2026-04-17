import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import GEMINI_API_KEY, GEMINI_MODEL, RAG_MODE
from app.db.deps import get_current_user, get_db
from app.models.user import User
from app.services.document_registry import (
    get_document_record,
    list_document_records,
    mark_document_deleted,
)
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


def evict_document_cache(user_id: str, doc_id: str) -> None:
    for candidate in iter_doc_id_candidates(doc_id):
        DOCUMENTS.pop(get_document_cache_key(user_id, candidate), None)


def serialize_document(record: dict, user_id: str, document_record=None) -> dict:
    metadata = record.get("metadata") or {}
    documents = record.get("documents") or []
    metadata_for_path = dict(metadata)

    if document_record is not None and document_record.storage_path:
        metadata_for_path["path"] = document_record.storage_path

    page_numbers = [
        int(chunk["page"])
        for chunk in documents
        if isinstance(chunk.get("page"), int)
    ]
    pdf_available = (
        resolve_upload_path(record["doc_id"], user_id, metadata_for_path) is not None
    )

    return {
        "doc_id": record["doc_id"],
        "name": (
            (document_record.filename if document_record is not None else None)
            or metadata.get("filename")
            or f"{record['doc_id']}.pdf"
        ),
        "chunks": (
            (document_record.chunk_count if document_record is not None else None)
            or metadata.get("chunk_count")
            or len(documents)
        ),
        "pages": (
            (document_record.page_count if document_record is not None else None)
            or metadata.get("page_count")
            or ((max(page_numbers) + 1) if page_numbers else 0)
        ),
        "rag_mode": (
            (document_record.rag_mode if document_record is not None else None)
            or metadata.get("rag_mode")
            or RAG_MODE
        ),
        "vector_ready": bool(
            (document_record.vector_ready if document_record is not None else None)
            or metadata.get("vector_ready")
            or record.get("has_index_file")
            or (RAG_MODE == "full" and record.get("index") is not None)
        ),
        "uploaded_at": (
            document_record.uploaded_at.isoformat()
            if document_record is not None and document_record.uploaded_at is not None
            else metadata.get("uploaded_at")
        ),
        "preview": (
            (document_record.preview if document_record is not None else None)
            or metadata.get("preview")
            or ((documents[0].get("text") or "")[:220] if documents else "")
        ),
        "pdf_available": pdf_available,
    }


@router.get("/documents")
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_records = {
        record.id: record
        for record in list_document_records(db, current_user.id)
    }
    saved_documents = {
        record["doc_id"]: serialize_document(
            record,
            current_user.id,
            document_records.get(record["doc_id"]),
        )
        for record in iter_saved_documents(current_user.id)
    }

    # Keep registry rows visible even if the in-memory cache was cleared and only
    # the persisted PDF metadata remains available.
    for doc_id, document_record in document_records.items():
        if doc_id in saved_documents:
            continue

        saved_documents[doc_id] = serialize_document(
            {
                "doc_id": doc_id,
                "documents": [],
                "index": None,
                "metadata": {
                    "filename": document_record.filename,
                    "path": document_record.storage_path,
                    "chunk_count": document_record.chunk_count,
                    "page_count": document_record.page_count,
                    "rag_mode": document_record.rag_mode,
                    "vector_ready": document_record.vector_ready,
                    "uploaded_at": (
                        document_record.uploaded_at.isoformat()
                        if document_record.uploaded_at is not None
                        else None
                    ),
                    "preview": document_record.preview,
                },
                "has_index_file": bool(document_record.faiss_path),
            },
            current_user.id,
            document_record,
        )

    documents = sorted(
        saved_documents.values(),
        key=lambda item: item.get("uploaded_at") or "",
        reverse=True,
    )
    return {"documents": documents}


@router.get("/documents/{doc_id}")
def get_document_details(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = get_document(current_user.id, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    payload = {
        "doc_id": doc_id,
        "documents": doc.get("documents", []),
        "index": doc.get("index"),
        "metadata": doc.get("metadata", {}),
    }
    return serialize_document(
        payload,
        current_user.id,
        get_document_record(db, current_user.id, doc_id),
    )


@router.delete("/documents/{doc_id}")
def delete_document_entry(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deleted = delete_saved_document(doc_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")

    evict_document_cache(current_user.id, deleted["doc_id"])
    mark_document_deleted(db, current_user.id, deleted["doc_id"])

    return {
        "doc_id": deleted["doc_id"],
        "removed": True,
        "removed_files": deleted["removed_files"],
    }


@router.delete("/documents")
def clear_document_library(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deleted_documents = clear_saved_documents(current_user.id)

    for deleted in deleted_documents:
        evict_document_cache(current_user.id, deleted["doc_id"])
        mark_document_deleted(db, current_user.id, deleted["doc_id"])

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
