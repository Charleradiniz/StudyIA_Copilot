from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil
import os
from uuid import uuid4

from app.services.pdf_reader import extract_text_from_pdf
from app.services.chunker import chunk_text
from app.services.embeddings import generate_embeddings
from app.services.query import DOCUMENTS
from app.services.database import save_document  # 🔥 NOVO

import faiss
import numpy as np

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def create_faiss_index(embeddings):
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
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Apenas PDFs são permitidos")

        file_extension = file.filename.split(".")[-1]
        unique_name = f"{uuid4()}.{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)

        # salva arquivo
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # extrai texto
        text = extract_text_from_pdf(file_path)

        if not text:
            return {
                "filename": unique_name,
                "chunks": 0,
                "preview": "PDF sem texto detectado"
            }

        # 🔥 chunking
        chunks = chunk_text(text)

        if not chunks:
            return {
                "filename": unique_name,
                "chunks": 0,
                "preview": "Erro ao gerar chunks"
            }

        # 🔥 estrutura documentos
        documents = [
            {"text": chunk, "id": i}
            for i, chunk in enumerate(chunks)
        ]

        # 🔥 embeddings
        embeddings = generate_embeddings([doc["text"] for doc in documents])

        if not embeddings:
            return {
                "filename": unique_name,
                "error": "Erro ao gerar embeddings"
            }

        # 🔥 FAISS
        index = create_faiss_index(embeddings)

        # 🔥 memória (cache)
        DOCUMENTS[unique_name] = {
            "documents": documents,
            "index": index
        }

        # 🔥 persistência (AQUI É O DIFERENCIAL)
        save_document(unique_name, documents, index)

        return {
            "filename": unique_name,
            "chunks": len(documents),
            "preview": documents[0]["text"]
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 