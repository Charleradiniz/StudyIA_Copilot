import os
import shutil
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import RAG_MODE, UPLOAD_DIR
from app.services.pdf_reader import extract_chunks_with_positions
from app.services.embeddings import generate_embeddings
from app.services.query import DOCUMENTS
from app.services.storage import save_document

try:
    import faiss
    import numpy as np
except Exception:
    faiss = None
    np = None

router = APIRouter()

os.makedirs(UPLOAD_DIR, exist_ok=True)


def create_faiss_index(embeddings):
    if faiss is None or np is None:
        return None

    embeddings_np = np.array(embeddings).astype("float32")

    if len(embeddings_np.shape) != 2:
        raise ValueError("Embeddings inválidos")

    dimension = embeddings_np.shape[1]

    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings_np)

    return index


def build_document_metadata(
    doc_id: str,
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
        "filename": original_name,
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
    }


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    file_path = None
    try:
        # =========================
        # VALIDATION
        # =========================
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail="Apenas PDFs são permitidos"
            )

        doc_id = str(uuid4())
        original_name = file.filename

        file_path = os.path.join(UPLOAD_DIR, f"{doc_id}.pdf")

        # =========================
        # SAVE FILE
        # =========================
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # =========================
        # PDF EXTRACTION
        # =========================
        chunks = extract_chunks_with_positions(file_path)

        if not chunks:
            raise HTTPException(
                status_code=422,
                detail="O PDF não possui texto extraível para indexação.",
            )

        # =========================
        # DOCUMENT STRUCTURE
        # =========================
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
            original_name,
            file_path,
            documents,
            vector_ready=vector_ready,
        )

        DOCUMENTS[doc_id] = {
            "doc_id": doc_id,
            "documents": documents,
            "index": index,
            "name": original_name,
            "path": file_path,
            "metadata": metadata,
        }

        save_document(
            doc_id,
            documents,
            index,
            metadata=metadata,
        )

        return build_upload_response(metadata)

    except HTTPException:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        raise

    except Exception as e:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
