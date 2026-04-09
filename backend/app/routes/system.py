import os

from fastapi import APIRouter, HTTPException

from app.config import GEMINI_API_KEY, GEMINI_MODEL, RAG_MODE
from app.services.embeddings import model as embedding_model
from app.services.query import get_document
from app.services.reranker import reranker_model
from app.services.storage import faiss as faiss_module
from app.services.storage import iter_saved_documents

router = APIRouter()


def serialize_document(record: dict):
    metadata = record.get("metadata") or {}
    documents = record.get("documents") or []
    page_numbers = [
        int(chunk["page"])
        for chunk in documents
        if isinstance(chunk.get("page"), int)
    ]

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
    }


@router.get("/documents")
def list_documents():
    documents = [serialize_document(record) for record in iter_saved_documents()]

    documents.sort(
        key=lambda item: item.get("uploaded_at") or "",
        reverse=True,
    )

    return {"documents": documents}


@router.get("/documents/{doc_id}")
def get_document_details(doc_id: str):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    payload = {
        "doc_id": doc_id,
        "documents": doc.get("documents", []),
        "index": doc.get("index"),
        "metadata": doc.get("metadata", {}),
    }
    return serialize_document(payload)


@router.get("/system/status")
def get_system_status():
    indexed_documents = sum(1 for _ in iter_saved_documents())

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
