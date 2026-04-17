import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import PDF_STORAGE_PROVIDER, RAG_MODE
from app.db.deps import get_current_user, get_db
from app.models.user import User
from app.services.document_registry import upsert_document_record
from app.services.pdf_reader import extract_chunks_with_positions
from app.services.embeddings import generate_embeddings
from app.services.query import DOCUMENTS, get_document_cache_key
from app.services.storage import get_user_upload_path, save_document

try:
    import faiss
    import numpy as np
except Exception:
    faiss = None
    np = None

router = APIRouter()
logger = logging.getLogger("studyiacopilot.upload")
PDF_FILE_SIGNATURE = b"%PDF-"
MAX_PDF_UPLOAD_BYTES = int(os.getenv("MAX_PDF_UPLOAD_BYTES", str(25 * 1024 * 1024)))


def create_faiss_index(embeddings):
    if faiss is None or np is None:
        return None

    embeddings_np = np.array(embeddings).astype("float32")

    if len(embeddings_np.shape) != 2:
        raise ValueError("Invalid embedding payload.")

    dimension = embeddings_np.shape[1]

    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings_np)

    return index


def build_document_metadata(
    doc_id: str,
    user_id: str,
    original_name: str,
    file_path: str,
    documents: list[dict],
    *,
    vector_ready: bool,
):
    page_numbers = [
        int(chunk["page"])
        for chunk in documents
        if isinstance(chunk.get("page"), int)
    ]

    return {
        "doc_id": doc_id,
        "user_id": user_id,
        "filename": original_name,
        "storage_provider": PDF_STORAGE_PROVIDER,
        "path": file_path,
        "chunk_count": len(documents),
        "page_count": (max(page_numbers) + 1) if page_numbers else 0,
        "rag_mode": RAG_MODE,
        "vector_ready": vector_ready,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "preview": (documents[0].get("text") or "")[:220] if documents else "",
    }


def build_upload_response(metadata: dict):
    return {
        "doc_id": metadata["doc_id"],
        "name": metadata["filename"],
        "chunks": metadata["chunk_count"],
        "pages": metadata["page_count"],
        "rag_mode": metadata["rag_mode"],
        "vector_ready": metadata["vector_ready"],
        "uploaded_at": metadata["uploaded_at"],
        "preview": metadata["preview"],
        "pdf_available": True,
    }


def validate_pdf_upload(file: UploadFile) -> None:
    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed.",
        )

    try:
        signature = file.file.read(len(PDF_FILE_SIGNATURE))
        file.file.seek(0)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Could not read the uploaded file.",
        ) from exc

    if signature != PDF_FILE_SIGNATURE:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid PDF.",
        )


def persist_upload_file(source_file, destination_path: str) -> None:
    bytes_written = 0

    with open(destination_path, "wb") as buffer:
        while True:
            chunk = source_file.read(1024 * 1024)
            if not chunk:
                break

            bytes_written += len(chunk)
            if bytes_written > MAX_PDF_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        "The PDF is too large. Upload files up to "
                        f"{MAX_PDF_UPLOAD_BYTES // (1024 * 1024)} MB."
                    ),
                )

            buffer.write(chunk)


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    file_path = None
    try:
        validate_pdf_upload(file)

        doc_id = str(uuid4())
        original_name = file.filename or "document.pdf"

        upload_path = get_user_upload_path(current_user.id)
        file_path = str(upload_path / f"{doc_id}.pdf")

        persist_upload_file(file.file, file_path)
        chunks = extract_chunks_with_positions(file_path)

        if not chunks:
            raise HTTPException(
                status_code=422,
                detail="The PDF does not contain extractable text for indexing.",
            )
        documents = [
            {
                "text": chunk["text"],
                "id": chunk["id"],
                "doc_id": doc_id,
                "file_id": doc_id,
                "page": chunk["page"],
                "bbox": chunk["bbox"],
                "line_boxes": chunk.get("line_boxes", []),
                "char_length": chunk.get("char_length", len(chunk["text"])),
            }
            for chunk in chunks
        ]

        index = None
        vector_ready = False
        if RAG_MODE == "full":
            embeddings = generate_embeddings(
                [doc["text"] for doc in documents]
            )

            if embeddings is not None and len(embeddings) > 0:
                index = create_faiss_index(embeddings)
                vector_ready = index is not None

        metadata = build_document_metadata(
            doc_id,
            current_user.id,
            original_name,
            file_path,
            documents,
            vector_ready=vector_ready,
        )

        DOCUMENTS[get_document_cache_key(current_user.id, doc_id)] = {
            "doc_id": doc_id,
            "documents": documents,
            "index": index,
            "name": original_name,
            "path": file_path,
            "metadata": metadata,
        }

        saved_paths = save_document(
            doc_id,
            documents,
            index,
            metadata=metadata,
            user_id=current_user.id,
        )

        upsert_document_record(
            db,
            doc_id=doc_id,
            user_id=current_user.id,
            filename=metadata["filename"],
            storage_provider=metadata["storage_provider"],
            storage_path=file_path,
            faiss_path=saved_paths.get("faiss_path"),
            json_path=saved_paths.get("json_path"),
            byte_size=os.path.getsize(file_path),
            chunk_count=metadata["chunk_count"],
            page_count=metadata["page_count"],
            rag_mode=metadata["rag_mode"],
            vector_ready=metadata["vector_ready"],
            preview=metadata["preview"],
            uploaded_at=metadata["uploaded_at"],
        )

        return build_upload_response(metadata)

    except HTTPException:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        raise

    except Exception as exc:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        logger.exception(
            "upload_processing_failed user_id=%s filename=%s",
            current_user.id,
            getattr(file, "filename", None),
        )
        raise HTTPException(
            status_code=500,
            detail="The server could not process this PDF upload.",
        ) from exc
