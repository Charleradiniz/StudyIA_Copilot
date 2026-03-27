from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil
import os
from uuid import uuid4

from app.services.pdf_reader import extract_text_from_pdf
from app.services.chunker import chunk_text
from app.services.embeddings import generate_embeddings
from app.services.query import DOCUMENTS

router = APIRouter()

UPLOAD_DIR = "uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        if not file.filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Apenas PDFs são permitidos")

        file_extension = file.filename.split(".")[-1]
        unique_name = f"{uuid4()}.{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        try:
            text = extract_text_from_pdf(file_path)

            if not text:
                return {
                    "filename": unique_name,
                    "chunks": 0,
                    "embeddings": 0,
                    "preview": "PDF sem texto detectado"
                }

            chunks = chunk_text(text)

            if not chunks:
                return {
                    "filename": unique_name,
                    "chunks": 0,
                    "embeddings": 0,
                    "preview": "Erro ao gerar chunks"
                }

            embeddings = generate_embeddings(chunks)

            DOCUMENTS[unique_name] = {
                "chunks": chunks,
                "embeddings": embeddings
            }

            return {
                "filename": unique_name,
                "chunks": len(chunks),
                "embeddings": len(embeddings),
                "preview": chunks[0]
            }

        except Exception as e:
            return {
                "filename": unique_name,
                "error": f"Erro no processamento: {str(e)}"
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))