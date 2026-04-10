import os
import io
import json
import shutil
import unittest
from pathlib import Path
from uuid import uuid4

import fitz
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["RAG_MODE"] = "lite"
os.environ["GEMINI_API_KEY"] = ""

from app.db import database as db_module
from app.routes import auth as auth_route
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
    app.include_router(auth_route.router, prefix="/api")
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
        self.workspace_temp_root = Path(__file__).resolve().parent / "_runtime"
        self.workspace_temp_root.mkdir(parents=True, exist_ok=True)
        self.root_path = self.workspace_temp_root / f"studyiacopilot-tests-{uuid4().hex}"
        self.root_path.mkdir(parents=True, exist_ok=False)
        self.db_path = self.root_path / "test.db"
        self.upload_path = self.root_path / "uploads"
        self.data_path = self.root_path / "data"
        self.upload_path.mkdir(parents=True, exist_ok=True)
        self.data_path.mkdir(parents=True, exist_ok=True)

        self.originals = {
            "database_url": str(db_module.engine.url) if db_module.engine is not None else None,
            "upload_rag_mode": upload_route.RAG_MODE,
            "query_rag_mode": query_module.RAG_MODE,
            "storage_data_root": storage_module.DATA_ROOT,
            "storage_upload_root": storage_module.UPLOAD_ROOT,
            "system_rag_mode": system_route.RAG_MODE,
            "system_gemini_api_key": system_route.GEMINI_API_KEY,
            "system_gemini_model": system_route.GEMINI_MODEL,
            "system_embedding_model": system_route.embedding_model,
            "system_reranker_model": system_route.reranker_model,
            "system_faiss_module": system_route.faiss_module,
            "generate_answer": query_module.generate_answer,
        }

        db_module.configure_database(f"sqlite:///{self.db_path.as_posix()}")
        db_module.Base.metadata.create_all(bind=db_module.engine)
        upload_route.RAG_MODE = "lite"
        query_module.RAG_MODE = "lite"
        storage_module.DATA_ROOT = self.data_path
        storage_module.UPLOAD_ROOT = self.upload_path
        storage_module.DATA_ROOT.mkdir(parents=True, exist_ok=True)
        storage_module.UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
        system_route.RAG_MODE = "lite"
        system_route.GEMINI_API_KEY = ""
        system_route.GEMINI_MODEL = "test-model"
        system_route.embedding_model = None
        system_route.reranker_model = None
        system_route.faiss_module = None
        self.llm_calls: list[dict] = []

        def fake_generate_answer(question, context, history=None, **kwargs):
            self.llm_calls.append({
                "question": question,
                "context": context,
                "history": history or [],
                "kwargs": kwargs,
            })
            return "Mocked grounded answer."

        query_module.generate_answer = fake_generate_answer
        query_module.DOCUMENTS.clear()

        self.client = TestClient(build_test_app())
        self.addCleanup(self.client.close)

    def tearDown(self) -> None:
        query_module.DOCUMENTS.clear()
        upload_route.RAG_MODE = self.originals["upload_rag_mode"]
        query_module.RAG_MODE = self.originals["query_rag_mode"]
        storage_module.DATA_ROOT = self.originals["storage_data_root"]
        storage_module.UPLOAD_ROOT = self.originals["storage_upload_root"]
        system_route.RAG_MODE = self.originals["system_rag_mode"]
        system_route.GEMINI_API_KEY = self.originals["system_gemini_api_key"]
        system_route.GEMINI_MODEL = self.originals["system_gemini_model"]
        system_route.embedding_model = self.originals["system_embedding_model"]
        system_route.reranker_model = self.originals["system_reranker_model"]
        system_route.faiss_module = self.originals["system_faiss_module"]
        query_module.generate_answer = self.originals["generate_answer"]
        db_module.configure_database(self.originals["database_url"])
        shutil.rmtree(self.root_path, ignore_errors=True)

    def upload_sample_pdf(
        self,
        headers: dict[str, str],
        filename: str = "study-guide.pdf",
        text: str = LONG_TEXT,
    ) -> dict:
        response = self.client.post(
            "/api/upload",
            headers=headers,
            files={
                "file": (
                    filename,
                    io.BytesIO(build_pdf_bytes(text)),
                    "application/pdf",
                )
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def register_user(
        self,
        *,
        full_name: str = "Charles Study",
        email: str = "charles@example.com",
        password: str = "password123",
    ) -> dict:
        response = self.client.post(
            "/api/auth/register",
            json={
                "full_name": full_name,
                "email": email,
                "password": password,
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("token", payload)
        return payload

    def auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def test_register_and_login_return_a_valid_session_payload(self) -> None:
        register_payload = self.register_user()
        login_response = self.client.post(
            "/api/auth/login",
            json={
                "email": "charles@example.com",
                "password": "password123",
            },
        )

        self.assertEqual(login_response.status_code, 200, login_response.text)
        login_payload = login_response.json()

        self.assertIn("token", register_payload)
        self.assertEqual(login_payload["user"]["email"], "charles@example.com")

        me_response = self.client.get(
            "/api/auth/me",
            headers=self.auth_headers(login_payload["token"]),
        )
        self.assertEqual(me_response.status_code, 200, me_response.text)
        self.assertEqual(me_response.json()["user"]["full_name"], "Charles Study")

    def test_upload_populates_catalog_and_runtime_status(self) -> None:
        auth = self.register_user()
        headers = self.auth_headers(auth["token"])
        upload_payload = self.upload_sample_pdf(headers=headers)

        self.assertEqual(upload_payload["name"], "study-guide.pdf")
        self.assertGreaterEqual(upload_payload["chunks"], 1)
        self.assertEqual(upload_payload["pages"], 1)
        self.assertFalse(upload_payload["vector_ready"])
        self.assertEqual(upload_payload["rag_mode"], "lite")

        documents_response = self.client.get("/api/documents", headers=headers)
        self.assertEqual(documents_response.status_code, 200)
        documents = documents_response.json()["documents"]

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["doc_id"], upload_payload["doc_id"])
        self.assertEqual(documents[0]["name"], "study-guide.pdf")
        self.assertGreaterEqual(documents[0]["chunks"], 1)
        self.assertIn("StudyIA Copilot", documents[0]["preview"])

        status_response = self.client.get("/api/system/status", headers=headers)
        self.assertEqual(status_response.status_code, 200)
        status = status_response.json()

        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["rag_mode"], "lite")
        self.assertFalse(status["vector_search_enabled"])
        self.assertEqual(status["documents_indexed"], 1)
        self.assertTrue(status["workspace_data_available"])

    def test_pdf_endpoint_serves_uploaded_document(self) -> None:
        auth = self.register_user()
        headers = self.auth_headers(auth["token"])
        upload_payload = self.upload_sample_pdf(headers=headers, filename="viewer-proof.pdf")

        pdf_response = self.client.get(
            f"/api/pdf/{upload_payload['doc_id']}",
            headers=headers,
        )

        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response.headers["content-type"], "application/pdf")
        self.assertGreater(len(pdf_response.content), 100)

    def test_ask_returns_grounded_sources_for_uploaded_document(self) -> None:
        auth = self.register_user()
        headers = self.auth_headers(auth["token"])
        upload_payload = self.upload_sample_pdf(headers=headers)

        ask_response = self.client.post(
            "/api/ask",
            headers=headers,
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

    def test_ask_accepts_multiple_active_documents(self) -> None:
        auth = self.register_user()
        headers = self.auth_headers(auth["token"])
        first_upload = self.upload_sample_pdf(
            headers=headers,
            filename="architecture.pdf",
            text=("Architecture evidence for multi PDF retrieval. " * 8),
        )
        second_upload = self.upload_sample_pdf(
            headers=headers,
            filename="operations.pdf",
            text=("Operations evidence for multi PDF retrieval. " * 8),
        )

        ask_response = self.client.post(
            "/api/ask",
            headers=headers,
            json={
                "question": "Compare the active PDFs",
                "doc_ids": [first_upload["doc_id"], second_upload["doc_id"]],
                "history": [],
            },
        )

        self.assertEqual(ask_response.status_code, 200, ask_response.text)
        payload = ask_response.json()
        returned_doc_ids = {source["doc_id"] for source in payload["sources"]}

        self.assertEqual(payload["answer"], "Mocked grounded answer.")
        self.assertTrue(returned_doc_ids.issubset({first_upload["doc_id"], second_upload["doc_id"]}))
        self.assertEqual(returned_doc_ids, {first_upload["doc_id"], second_upload["doc_id"]})

    def test_ask_groups_context_by_document_for_comparison_questions(self) -> None:
        auth = self.register_user()
        headers = self.auth_headers(auth["token"])
        first_upload = self.upload_sample_pdf(
            headers=headers,
            filename="greek-architecture.pdf",
            text=("Greek architecture relies on columns, pediments, and geometric proportion. " * 8),
        )
        second_upload = self.upload_sample_pdf(
            headers=headers,
            filename="islamic-architecture.pdf",
            text=("Islamic architecture relies on courtyards, arches, and geometric ornament. " * 8),
        )

        ask_response = self.client.post(
            "/api/ask",
            headers=headers,
            json={
                "question": "Compare the similarities and differences between the documents.",
                "doc_ids": [first_upload["doc_id"], second_upload["doc_id"]],
                "history": [],
            },
        )

        self.assertEqual(ask_response.status_code, 200, ask_response.text)
        payload = ask_response.json()
        last_llm_call = self.llm_calls[-1]
        returned_doc_ids = {source["doc_id"] for source in payload["sources"]}
        returned_labels = {source.get("doc_label") for source in payload["sources"]}

        self.assertEqual(payload["answer"], "Mocked grounded answer.")
        self.assertEqual(last_llm_call["kwargs"].get("prompt_mode"), "comparison")
        self.assertIn("[Greek Architecture]", last_llm_call["context"])
        self.assertIn("[Islamic Architecture]", last_llm_call["context"])
        self.assertIn("Excerpt 1", last_llm_call["context"])
        self.assertEqual(returned_doc_ids, {first_upload["doc_id"], second_upload["doc_id"]})
        self.assertIn("Greek Architecture", returned_labels)
        self.assertIn("Islamic Architecture", returned_labels)

    def test_ask_uses_cross_document_fallback_for_relational_questions(self) -> None:
        auth = self.register_user()
        headers = self.auth_headers(auth["token"])
        first_upload = self.upload_sample_pdf(
            headers=headers,
            filename="civic-order.pdf",
            text=("Doric colonnades and stone pediments organize civic temples. " * 8),
        )
        second_upload = self.upload_sample_pdf(
            headers=headers,
            filename="sacred-space.pdf",
            text=("Muqarnas vaults and interior courtyards organize sacred complexes. " * 8),
        )

        ask_response = self.client.post(
            "/api/ask",
            headers=headers,
            json={
                "question": "What is the relationship between the two documents?",
                "doc_ids": [first_upload["doc_id"], second_upload["doc_id"]],
                "history": [],
            },
        )

        self.assertEqual(ask_response.status_code, 200, ask_response.text)
        payload = ask_response.json()
        last_llm_call = self.llm_calls[-1]
        returned_doc_ids = {source["doc_id"] for source in payload["sources"]}

        self.assertEqual(payload["answer"], "Mocked grounded answer.")
        self.assertEqual(last_llm_call["kwargs"].get("prompt_mode"), "comparison")
        self.assertEqual(returned_doc_ids, {first_upload["doc_id"], second_upload["doc_id"]})
        self.assertIn("[Civic Order]", last_llm_call["context"])
        self.assertIn("[Sacred Space]", last_llm_call["context"])

    def test_delete_document_removes_assets_and_catalog_entry(self) -> None:
        auth = self.register_user()
        headers = self.auth_headers(auth["token"])
        upload_payload = self.upload_sample_pdf(headers=headers, filename="cleanup-proof.pdf")
        doc_id = upload_payload["doc_id"]
        user_id = auth["user"]["id"]
        pdf_path = self.upload_path / user_id / f"{doc_id}.pdf"
        _, json_path = storage_module.get_paths(doc_id, user_id)

        self.assertTrue(pdf_path.exists())
        self.assertTrue(json_path.exists())

        delete_response = self.client.delete(f"/api/documents/{doc_id}", headers=headers)

        self.assertEqual(delete_response.status_code, 200, delete_response.text)
        payload = delete_response.json()

        self.assertTrue(payload["removed"])
        self.assertEqual(payload["doc_id"], doc_id)
        self.assertFalse(pdf_path.exists())
        self.assertFalse(json_path.exists())
        self.assertNotIn(
            query_module.get_document_cache_key(user_id, doc_id),
            query_module.DOCUMENTS,
        )

        catalog_response = self.client.get("/api/documents", headers=headers)
        self.assertEqual(catalog_response.status_code, 200)
        self.assertEqual(catalog_response.json()["documents"], [])

        pdf_response = self.client.get(f"/api/pdf/{doc_id}", headers=headers)
        self.assertEqual(pdf_response.status_code, 404)

    def test_clear_documents_endpoint_removes_all_uploaded_assets(self) -> None:
        auth = self.register_user()
        headers = self.auth_headers(auth["token"])
        first_upload = self.upload_sample_pdf(headers=headers, filename="first.pdf")
        second_upload = self.upload_sample_pdf(headers=headers, filename="second.pdf")

        response = self.client.delete("/api/documents", headers=headers)

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()

        self.assertEqual(payload["removed_count"], 2)
        self.assertCountEqual(
            payload["removed_doc_ids"],
            [first_upload["doc_id"], second_upload["doc_id"]],
        )
        user_upload_path = self.upload_path / auth["user"]["id"]
        user_data_path = self.data_path / auth["user"]["id"]
        self.assertEqual(list(user_upload_path.iterdir()), [])
        self.assertEqual(list(user_data_path.iterdir()), [])

    def test_documents_endpoint_supports_legacy_saved_payloads(self) -> None:
        auth = self.register_user()
        headers = self.auth_headers(auth["token"])
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

        user_data_path = self.data_path / auth["user"]["id"]
        user_data_path.mkdir(parents=True, exist_ok=True)
        (user_data_path / "legacy-doc.json").write_text(
            json.dumps(legacy_document, ensure_ascii=False),
            encoding="utf-8",
        )

        response = self.client.get("/api/documents", headers=headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()["documents"]

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["doc_id"], "legacy-doc")
        self.assertEqual(payload[0]["chunks"], 1)
        self.assertFalse(payload[0]["vector_ready"])
        self.assertIn("Legacy storage format", payload[0]["preview"])

    def test_each_user_only_sees_their_own_documents(self) -> None:
        first_user = self.register_user(
            full_name="User One",
            email="user-one@example.com",
        )
        second_user = self.register_user(
            full_name="User Two",
            email="user-two@example.com",
        )
        first_headers = self.auth_headers(first_user["token"])
        second_headers = self.auth_headers(second_user["token"])
        first_upload = self.upload_sample_pdf(
            headers=first_headers,
            filename="tenant-safe.pdf",
        )

        first_docs_response = self.client.get("/api/documents", headers=first_headers)
        second_docs_response = self.client.get("/api/documents", headers=second_headers)
        forbidden_pdf_response = self.client.get(
            f"/api/pdf/{first_upload['doc_id']}",
            headers=second_headers,
        )
        forbidden_ask_response = self.client.post(
            "/api/ask",
            headers=second_headers,
            json={
                "question": "What does the hidden document say?",
                "doc_id": first_upload["doc_id"],
                "history": [],
            },
        )

        self.assertEqual(first_docs_response.status_code, 200)
        self.assertEqual(len(first_docs_response.json()["documents"]), 1)
        self.assertEqual(second_docs_response.status_code, 200)
        self.assertEqual(second_docs_response.json()["documents"], [])
        self.assertEqual(forbidden_pdf_response.status_code, 404)
        self.assertEqual(forbidden_ask_response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
