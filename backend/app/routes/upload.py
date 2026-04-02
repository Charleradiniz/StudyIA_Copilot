from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil
import os
from uuid import uuid4

from app.config import RAG_MODE, UPLOAD_DIR  # Import from the shared config module
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
        raise ValueError("FAISS dependencies are unavailable")

    embeddings_np = np.array(embeddings).astype("float32")

    if len(embeddings_np.shape) != 2:
        raise ValueError("Embeddings inválidos")

    dimension = embeddings_np.shape[1]

    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings_np)

    return index


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
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
            return {
                "doc_id": doc_id,
                "name": original_name,
                "chunks": 0,
                "preview": "PDF sem texto detectado"
            }

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

        # =========================
        # EMBEDDINGS
        # =========================
        index = None
        if RAG_MODE == "full":
            embeddings = generate_embeddings(
                [doc["text"] for doc in documents]
            )

            if embeddings is None or len(embeddings) == 0:
                return {
                    "doc_id": doc_id,
                    "name": original_name,
                    "error": "Erro ao gerar embeddings"
                }

            # =========================
            # FAISS INDEX
            # =========================
            index = create_faiss_index(embeddings)

        # =========================
        # IN-MEMORY CACHE
        # =========================
        DOCUMENTS[doc_id] = {
            "documents": documents,
            "index": index,
            "name": original_name,
            "path": file_path
        }

        # =========================
        # PERSISTENCE
        # =========================
        save_document(
            doc_id,
            documents,
            index,
            metadata={
                "filename": original_name,
                "path": file_path
            }
        )

        # =========================
        # RESPONSE
        # =========================
        return {
            "doc_id": doc_id,
            "name": original_name,
            "chunks": len(documents),
            "preview": documents[0]["text"][:200]
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
