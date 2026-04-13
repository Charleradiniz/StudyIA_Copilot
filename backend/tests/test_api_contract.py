import os
import io
import json
import shutil
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import fitz
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["RAG_MODE"] = "lite"
os.environ["GEMINI_API_KEY"] = ""

from app.db import database as db_module
from app.routes import auth as auth_route
from app.routes import chats as chats_route
from app.routes import pdf as pdf_route
from app.routes import system as system_route
from app.routes import upload as upload_route
from app.services import llm as llm_module
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
    app.include_router(chats_route.router, prefix="/api")
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
            "send_password_reset_email": auth_route.send_password_reset_email,
        }

        db_module.configure_database("sqlite://")
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
        self.password_reset_emails: list[dict] = []

        def fake_generate_answer(question, context, history=None, **kwargs):
            self.llm_calls.append({
                "question": question,
                "context": context,
                "history": history or [],
                "kwargs": kwargs,
            })
            return "Mocked grounded answer."

        def fake_send_password_reset_email(**kwargs):
            token = kwargs["reset_token"]
            reset_url = f"http://127.0.0.1:5173/?reset_password_token={token}"
            self.password_reset_emails.append({
                **kwargs,
                "reset_url": reset_url,
            })
            return reset_url

        query_module.generate_answer = fake_generate_answer
        auth_route.send_password_reset_email = fake_send_password_reset_email
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
        auth_route.send_password_reset_email = self.originals["send_password_reset_email"]
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

    def save_document_fixture(
        self,
        *,
        user_id: str,
        doc_id: str,
        filename: str,
        texts: list[str],
    ) -> None:
        documents = [
            {
                "id": index,
                "text": text,
                "doc_id": doc_id,
                "file_id": doc_id,
                "page": index,
                "bbox": [0, 0, 100, 100],
                "line_boxes": [[0, 0, 100, 100]],
                "char_length": len(text),
            }
            for index, text in enumerate(texts)
        ]
        metadata = {
            "doc_id": doc_id,
            "user_id": user_id,
            "filename": filename,
            "path": str(self.upload_path / user_id / f"{doc_id}.pdf"),
            "chunk_count": len(documents),
            "page_count": len(documents),
            "rag_mode": "lite",
            "vector_ready": False,
            "uploaded_at": "2026-01-01T00:00:00+00:00",
            "preview": (documents[0]["text"] if documents else "")[:220],
        }

        storage_module.save_document(
            doc_id,
            documents,
            None,
            metadata=metadata,
            user_id=user_id,
        )
        query_module.DOCUMENTS.pop(
            query_module.get_document_cache_key(user_id, doc_id),
            None,
        )

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

    def test_password_reset_email_flow_updates_the_login_password(self) -> None:
        auth = self.register_user()
        old_token = auth["token"]

        request_response = self.client.post(
            "/api/auth/password-reset/request",
            json={"email": "charles@example.com"},
        )

        self.assertEqual(request_response.status_code, 200, request_response.text)
        self.assertEqual(len(self.password_reset_emails), 1)
        self.assertEqual(
            self.password_reset_emails[0]["recipient_email"],
            "charles@example.com",
        )

        reset_url = self.password_reset_emails[0]["reset_url"]
        token = parse_qs(urlparse(reset_url).query)["reset_password_token"][0]

        confirm_response = self.client.post(
            "/api/auth/password-reset/confirm",
            json={
                "token": token,
                "password": "new-password-456",
            },
        )

        self.assertEqual(confirm_response.status_code, 200, confirm_response.text)
        self.assertTrue(confirm_response.json()["password_reset"])

        old_me_response = self.client.get(
            "/api/auth/me",
            headers=self.auth_headers(old_token),
        )
        self.assertEqual(old_me_response.status_code, 401)

        old_login_response = self.client.post(
            "/api/auth/login",
            json={
                "email": "charles@example.com",
                "password": "password123",
            },
        )
        self.assertEqual(old_login_response.status_code, 401, old_login_response.text)

        new_login_response = self.client.post(
            "/api/auth/login",
            json={
                "email": "charles@example.com",
                "password": "new-password-456",
            },
        )
        self.assertEqual(new_login_response.status_code, 200, new_login_response.text)
        self.assertEqual(
            new_login_response.json()["user"]["email"],
            "charles@example.com",
        )

    def test_chat_history_syncs_across_sessions_for_the_same_user(self) -> None:
        auth = self.register_user()
        headers = self.auth_headers(auth["token"])
        chat_payload = {
            "id": "chat-shared",
            "title": "Shared Workspace History",
            "active_doc_ids": ["doc-1"],
            "messages": [
                {
                    "id": "msg-1",
                    "role": "assistant",
                    "content": "Welcome back.",
                    "sources": [],
                },
                {
                    "id": "msg-2",
                    "role": "user",
                    "content": "Continue the conversation from mobile.",
                    "sources": [],
                },
            ],
            "created_at": "2026-04-13T12:00:00+00:00",
            "updated_at": "2026-04-13T12:05:00+00:00",
        }

        sync_response = self.client.post(
            "/api/chats/sync",
            headers=headers,
            json={"chats": [chat_payload]},
        )

        self.assertEqual(sync_response.status_code, 200, sync_response.text)
        self.assertEqual(sync_response.json()["synced_chat_ids"], ["chat-shared"])

        second_login_response = self.client.post(
            "/api/auth/login",
            json={
                "email": "charles@example.com",
                "password": "password123",
            },
        )
        self.assertEqual(second_login_response.status_code, 200, second_login_response.text)
        second_headers = self.auth_headers(second_login_response.json()["token"])

        chats_response = self.client.get("/api/chats", headers=second_headers)

        self.assertEqual(chats_response.status_code, 200, chats_response.text)
        payload = chats_response.json()

        self.assertEqual(payload["deleted"], [])
        self.assertEqual(len(payload["chats"]), 1)
        self.assertEqual(payload["chats"][0]["id"], "chat-shared")
        self.assertEqual(payload["chats"][0]["title"], "Shared Workspace History")
        self.assertEqual(payload["chats"][0]["active_doc_ids"], ["doc-1"])
        self.assertEqual(
            payload["chats"][0]["messages"][1]["content"],
            "Continue the conversation from mobile.",
        )

    def test_deleted_chat_creates_a_tombstone_and_blocks_stale_resync(self) -> None:
        auth = self.register_user()
        headers = self.auth_headers(auth["token"])
        chat_payload = {
            "id": "chat-to-delete",
            "title": "Delete Me",
            "active_doc_ids": [],
            "messages": [
                {
                    "id": "msg-1",
                    "role": "assistant",
                    "content": "This should disappear everywhere.",
                    "sources": [],
                }
            ],
            "created_at": "2026-04-13T13:00:00+00:00",
            "updated_at": "2026-04-13T13:01:00+00:00",
        }

        first_sync_response = self.client.post(
            "/api/chats/sync",
            headers=headers,
            json={"chats": [chat_payload]},
        )
        self.assertEqual(first_sync_response.status_code, 200, first_sync_response.text)

        delete_response = self.client.delete("/api/chats/chat-to-delete", headers=headers)
        self.assertEqual(delete_response.status_code, 200, delete_response.text)
        self.assertTrue(delete_response.json()["deleted"])

        stale_sync_response = self.client.post(
            "/api/chats/sync",
            headers=headers,
            json={"chats": [chat_payload]},
        )
        self.assertEqual(stale_sync_response.status_code, 200, stale_sync_response.text)
        self.assertEqual(stale_sync_response.json()["synced_chat_ids"], [])
        self.assertEqual(stale_sync_response.json()["skipped_chat_ids"], ["chat-to-delete"])

        chats_response = self.client.get("/api/chats", headers=headers)
        self.assertEqual(chats_response.status_code, 200, chats_response.text)
        payload = chats_response.json()

        self.assertEqual(payload["chats"], [])
        self.assertEqual(payload["deleted"][0]["id"], "chat-to-delete")

    def test_prompt_instructions_encourage_more_developed_answers(self) -> None:
        prompt = llm_module.build_prompt(
            "Compare the documents",
            "[Doc A]\nExcerpt 1:\nAlpha\n\n[Doc B]\nExcerpt 1:\nBeta",
            history=[],
            prompt_mode="comparison",
        )

        self.assertIn("2 to 5 short paragraphs", prompt)
        self.assertIn("If several relevant excerpts exist", prompt)
        self.assertIn("compare several grounded points", prompt.lower())
        self.assertIn("extraction quality is insufficient", prompt)
        self.assertIn("do not infer the document theme", prompt)

    def test_summary_query_prefers_representative_chunks_over_leading_noise(self) -> None:
        auth = self.register_user()
        headers = self.auth_headers(auth["token"])
        doc_id = "mixed-quality-doc"
        self.save_document_fixture(
            user_id=auth["user"]["id"],
            doc_id=doc_id,
            filename="mixed-quality.pdf",
            texts=[
                "B&& B6B B7? B<B B?& 79G 7.B 7?? &<B &?& B&& B6B B7? B<B B?& 79G 7.B 7??",
                "BG' B9' B.< 7<' 7BB 7BG 76& 769 77? 79B 79? BG' B9' B.< 7<' 7BB 7BG 76&",
                "The document explains how the study workspace turns PDFs into grounded answers with retrieval, source metadata, and highlighted evidence in the viewer.",
                "It also describes the ingestion flow, from upload and extraction to chunking, retrieval, reranking, and final answer generation.",
                "A later section focuses on user experience, including multi-document chat, persistent sessions, and direct jumps back to the supporting excerpt.",
                "The overall theme is a fullstack AI application for reliable document analysis rather than a generic text generation demo.",
            ],
        )

        ask_response = self.client.post(
            "/api/ask",
            headers=headers,
            json={
                "question": "Sobre o que trata o documento?",
                "doc_id": doc_id,
                "history": [],
            },
        )

        self.assertEqual(ask_response.status_code, 200, ask_response.text)
        payload = ask_response.json()
        last_llm_call = self.llm_calls[-1]

        self.assertEqual(payload["answer"], "Mocked grounded answer.")
        self.assertIn("grounded answers", last_llm_call["context"])
        self.assertIn("fullstack AI application", last_llm_call["context"])
        self.assertNotIn("B&& B6B B7?", last_llm_call["context"])

    def test_ask_returns_safe_message_for_low_quality_extraction(self) -> None:
        auth = self.register_user()
        headers = self.auth_headers(auth["token"])
        doc_id = "low-quality-doc"
        self.save_document_fixture(
            user_id=auth["user"]["id"],
            doc_id=doc_id,
            filename="low-quality.pdf",
            texts=[
                "B&& B6B B7? B<B B?& 79G 7.B 7?? &<B &?& B&& B6B B7? B<B B?& 79G 7.B 7?? &<B &?&",
                "BG' B9' B.< 7<' 7BB 7BG 76& 769 77? 79B 79? BG' B9' B.< 7<' 7BB 7BG 76& 769 77?",
                "B&& B6B B7? B<B B?& 79G 7.B 7?? &<B &?& B&& B6B B7? B<B B?& 79G 7.B 7?? &<B &?&",
            ],
        )

        ask_response = self.client.post(
            "/api/ask",
            headers=headers,
            json={
                "question": "Sobre o que trata o documento?",
                "doc_id": doc_id,
                "history": [],
            },
        )

        self.assertEqual(ask_response.status_code, 200, ask_response.text)
        payload = ask_response.json()

        self.assertIn("texto extraído", payload["answer"])
        self.assertEqual(payload["sources"], [])
        self.assertEqual(self.llm_calls, [])

    def test_ensure_source_count_backfills_up_to_five_sources(self) -> None:
        primary = [
            {"doc_id": "doc-1", "chunk_id": 1, "page": 0, "text": "alpha"},
            {"doc_id": "doc-1", "chunk_id": 2, "page": 0, "text": "beta"},
        ]
        fallback = [
            {"doc_id": "doc-1", "chunk_id": 2, "page": 0, "text": "beta"},
            {"doc_id": "doc-1", "chunk_id": 3, "page": 1, "text": "gamma"},
            {"doc_id": "doc-2", "chunk_id": 4, "page": 0, "text": "delta"},
            {"doc_id": "doc-2", "chunk_id": 5, "page": 1, "text": "epsilon"},
            {"doc_id": "doc-3", "chunk_id": 6, "page": 0, "text": "zeta"},
        ]

        enriched = query_module.ensure_source_count(primary, fallback, target_count=5)

        self.assertEqual(len(enriched), 5)
        self.assertEqual(enriched[0]["text"], "alpha")
        self.assertEqual(enriched[1]["text"], "beta")
        self.assertEqual([chunk["text"] for chunk in enriched[2:]], ["gamma", "delta", "epsilon"])

    def test_ask_backfills_context_and_sources_when_retrieval_is_sparse(self) -> None:
        auth = self.register_user()
        headers = self.auth_headers(auth["token"])
        doc_id = "deep-context-doc"
        self.save_document_fixture(
            user_id=auth["user"]["id"],
            doc_id=doc_id,
            filename="deep-context.pdf",
            texts=[
                "Transit hubs coordinate regional buses and urban trains while concentrating passenger flow across connected districts and public access corridors.",
                "Stations also include ticketing corridors, waiting zones, and platform circulation details that explain how travelers move through the network.",
                "Operations planning emphasizes timing windows, signage, staff coordination, and crowd management during peaks and service changes.",
                "Secondary transit hubs integrate bicycle storage and bus transfers for last-mile access while extending the reach of the larger transport system.",
                "Wayfinding design keeps entrances legible, reduces transfer friction, and supports accessibility when multiple services meet in one place.",
                "Service summaries explain reliability metrics, maintenance schedules, and practical improvements that keep the overall experience consistent.",
            ],
        )

        ask_response = self.client.post(
            "/api/ask",
            headers=headers,
            json={
                "question": "transit hubs",
                "doc_id": doc_id,
                "history": [],
            },
        )

        self.assertEqual(ask_response.status_code, 200, ask_response.text)
        payload = ask_response.json()
        last_llm_call = self.llm_calls[-1]

        self.assertEqual(payload["answer"], "Mocked grounded answer.")
        self.assertEqual(len(payload["sources"]), 5)
        self.assertTrue(all(source["doc_id"] == doc_id for source in payload["sources"]))
        self.assertGreaterEqual(last_llm_call["context"].count("Chunk "), 5)
        self.assertIn("Documents: Deep Context", last_llm_call["context"])
        self.assertIn("[Topic 1:", last_llm_call["context"])

    def test_upload_populates_catalog_and_runtime_status(self) -> None:
        auth = self.register_user()
        headers = self.auth_headers(auth["token"])
        upload_payload = self.upload_sample_pdf(headers=headers)

        self.assertEqual(upload_payload["name"], "study-guide.pdf")
        self.assertGreaterEqual(upload_payload["chunks"], 1)
        self.assertEqual(upload_payload["pages"], 1)
        self.assertFalse(upload_payload["vector_ready"])
        self.assertEqual(upload_payload["rag_mode"], "lite")
        self.assertTrue(upload_payload["pdf_available"])

        documents_response = self.client.get("/api/documents", headers=headers)
        self.assertEqual(documents_response.status_code, 200)
        documents = documents_response.json()["documents"]

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["doc_id"], upload_payload["doc_id"])
        self.assertEqual(documents[0]["name"], "study-guide.pdf")
        self.assertGreaterEqual(documents[0]["chunks"], 1)
        self.assertIn("StudyIA Copilot", documents[0]["preview"])
        self.assertTrue(documents[0]["pdf_available"])

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
        self.assertIn("[Topic 1:", last_llm_call["context"])
        self.assertIn("Greek Architecture | page 1 | chunk 0", last_llm_call["context"])
        self.assertIn("Islamic Architecture | page 1 | chunk 0", last_llm_call["context"])
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
        self.assertIn("Civic Order | page 1 | chunk 0", last_llm_call["context"])
        self.assertIn("Sacred Space | page 1 | chunk 0", last_llm_call["context"])
        self.assertIn("[Cross-topic relationships]", last_llm_call["context"])

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
        self.assertGreaterEqual(len(payload["removed_files"]), 1)
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
        catalog_response = self.client.get("/api/documents", headers=headers)
        self.assertEqual(catalog_response.status_code, 200)
        self.assertEqual(catalog_response.json()["documents"], [])

    def test_documents_endpoint_supports_legacy_saved_payloads(self) -> None:
        auth = self.register_user()
        headers = self.auth_headers(auth["token"])
        legacy_document = [
            {
                "id": 0,
                "text": "Legacy storage format still needs to remain readable during system review. " * 3,
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
        self.assertFalse(payload[0]["pdf_available"])

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
