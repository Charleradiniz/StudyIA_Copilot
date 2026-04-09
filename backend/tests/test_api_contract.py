import os
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import fitz
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["RAG_MODE"] = "lite"
os.environ["GEMINI_API_KEY"] = ""

from app.routes import pdf as pdf_route
from app.routes import system as system_route
from app.routes import upload as upload_route
from app.services import query as query_module
from app.services import storage as storage_module


LONG_TEXT = (
    "StudyIA Copilot turns PDF files into grounded conversations with source-aware answers, "
    "retrieval metadata, and highlighted evidence in the viewer. This sample document exists "
    "to validate upload, catalog sync, lexical retrieval, and grounded answers without "
    "touching the real workspace data on disk. "
    * 4
)


def build_test_app() -> FastAPI:
    app = FastAPI(title="StudyIA Copilot Test API")
    app.include_router(upload_route.router, prefix="/api")
    app.include_router(query_module.router, prefix="/api")
    app.include_router(pdf_route.router, prefix="/api")
    app.include_router(system_route.router, prefix="/api")
    return app


def build_pdf_bytes(text: str = LONG_TEXT) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(48, 48, 545, 780), text, fontsize=12)
    payload = doc.tobytes()
    doc.close()
    return payload


class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace_temp_root = Path(__file__).resolve().parent / ".tmp"
        self.workspace_temp_root.mkdir(parents=True, exist_ok=True)
        self.root_path = Path(tempfile.mkdtemp(dir=self.workspace_temp_root))
        self.upload_path = self.root_path / "uploads"
        self.data_path = self.root_path / "data"
        self.upload_path.mkdir(parents=True, exist_ok=True)
        self.data_path.mkdir(parents=True, exist_ok=True)

        self.originals = {
            "upload_dir": upload_route.UPLOAD_DIR,
            "upload_rag_mode": upload_route.RAG_MODE,
            "pdf_upload_dir": pdf_route.UPLOAD_DIR,
            "query_data_dir": query_module.DATA_DIR,
            "query_rag_mode": query_module.RAG_MODE,
            "storage_data_path": storage_module.DATA_PATH,
            "system_rag_mode": system_route.RAG_MODE,
            "system_gemini_api_key": system_route.GEMINI_API_KEY,
            "system_gemini_model": system_route.GEMINI_MODEL,
            "system_embedding_model": system_route.embedding_model,
            "system_reranker_model": system_route.reranker_model,
            "system_faiss_module": system_route.faiss_module,
            "generate_answer": query_module.generate_answer,
        }

        upload_route.UPLOAD_DIR = str(self.upload_path)
        upload_route.RAG_MODE = "lite"
        pdf_route.UPLOAD_DIR = str(self.upload_path)
        query_module.DATA_DIR = str(self.data_path)
        query_module.RAG_MODE = "lite"
        storage_module.DATA_PATH = self.data_path
        storage_module.DATA_PATH.mkdir(parents=True, exist_ok=True)
        system_route.RAG_MODE = "lite"
        system_route.GEMINI_API_KEY = ""
        system_route.GEMINI_MODEL = "test-model"
        system_route.embedding_model = None
        system_route.reranker_model = None
        system_route.faiss_module = None
        query_module.generate_answer = lambda question, context, history: (
            "Mocked grounded answer."
        )
        query_module.DOCUMENTS.clear()

        self.client = TestClient(build_test_app())
        self.addCleanup(self.client.close)

    def tearDown(self) -> None:
        query_module.DOCUMENTS.clear()
        upload_route.UPLOAD_DIR = self.originals["upload_dir"]
        upload_route.RAG_MODE = self.originals["upload_rag_mode"]
        pdf_route.UPLOAD_DIR = self.originals["pdf_upload_dir"]
        query_module.DATA_DIR = self.originals["query_data_dir"]
        query_module.RAG_MODE = self.originals["query_rag_mode"]
        storage_module.DATA_PATH = self.originals["storage_data_path"]
        system_route.RAG_MODE = self.originals["system_rag_mode"]
        system_route.GEMINI_API_KEY = self.originals["system_gemini_api_key"]
        system_route.GEMINI_MODEL = self.originals["system_gemini_model"]
        system_route.embedding_model = self.originals["system_embedding_model"]
        system_route.reranker_model = self.originals["system_reranker_model"]
        system_route.faiss_module = self.originals["system_faiss_module"]
        query_module.generate_answer = self.originals["generate_answer"]
        shutil.rmtree(self.root_path, ignore_errors=True)

    def upload_sample_pdf(self, filename: str = "study-guide.pdf") -> dict:
        response = self.client.post(
            "/api/upload",
            files={
                "file": (
                    filename,
                    io.BytesIO(build_pdf_bytes()),
                    "application/pdf",
                )
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_upload_populates_catalog_and_runtime_status(self) -> None:
        upload_payload = self.upload_sample_pdf()

        self.assertEqual(upload_payload["name"], "study-guide.pdf")
        self.assertGreaterEqual(upload_payload["chunks"], 1)
        self.assertEqual(upload_payload["pages"], 1)
        self.assertFalse(upload_payload["vector_ready"])
        self.assertEqual(upload_payload["rag_mode"], "lite")

        documents_response = self.client.get("/api/documents")
        self.assertEqual(documents_response.status_code, 200)
        documents = documents_response.json()["documents"]

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["doc_id"], upload_payload["doc_id"])
        self.assertEqual(documents[0]["name"], "study-guide.pdf")
        self.assertGreaterEqual(documents[0]["chunks"], 1)
        self.assertIn("StudyIA Copilot", documents[0]["preview"])

        status_response = self.client.get("/api/system/status")
        self.assertEqual(status_response.status_code, 200)
        status = status_response.json()

        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["rag_mode"], "lite")
        self.assertFalse(status["vector_search_enabled"])
        self.assertEqual(status["documents_indexed"], 1)
        self.assertTrue(status["workspace_data_available"])

    def test_pdf_endpoint_serves_uploaded_document(self) -> None:
        upload_payload = self.upload_sample_pdf("viewer-proof.pdf")

        pdf_response = self.client.get(f"/api/pdf/{upload_payload['doc_id']}")

        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response.headers["content-type"], "application/pdf")
        self.assertGreater(len(pdf_response.content), 100)

    def test_ask_returns_grounded_sources_for_uploaded_document(self) -> None:
        upload_payload = self.upload_sample_pdf()

        ask_response = self.client.post(
            "/api/ask",
            json={
                "question": "Qual é o foco principal do documento?",
                "doc_id": upload_payload["doc_id"],
                "history": [],
            },
        )

        self.assertEqual(ask_response.status_code, 200, ask_response.text)
        payload = ask_response.json()

        self.assertEqual(payload["answer"], "Mocked grounded answer.")
        self.assertGreaterEqual(len(payload["sources"]), 1)
        self.assertEqual(payload["sources"][0]["doc_id"], upload_payload["doc_id"])
        self.assertEqual(payload["sources"][0]["page"], 0)
        self.assertIn("StudyIA Copilot", payload["sources"][0]["text"])

    def test_documents_endpoint_supports_legacy_saved_payloads(self) -> None:
        legacy_document = [
            {
                "id": 0,
                "text": "Legacy storage format still needs to remain readable for the portfolio review. " * 3,
                "doc_id": "legacy-doc",
                "file_id": "legacy-doc",
                "page": 0,
                "bbox": [0, 0, 12, 12],
                "line_boxes": [[0, 0, 12, 12]],
            }
        ]

        (self.data_path / "legacy-doc.json").write_text(
            json.dumps(legacy_document, ensure_ascii=False),
            encoding="utf-8",
        )

        response = self.client.get("/api/documents")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["documents"]

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["doc_id"], "legacy-doc")
        self.assertEqual(payload[0]["chunks"], 1)
        self.assertFalse(payload[0]["vector_ready"])
        self.assertIn("Legacy storage format", payload[0]["preview"])


if __name__ == "__main__":
    unittest.main()
