from fastapi import APIRouter
import os
import traceback

from app.config import RAG_MODE
from app.services.similarity import search
from app.services.embeddings import model
from app.services.llm import generate_answer
from app.services.reranker import rerank
from app.services.storage import load_document

router = APIRouter()

DOCUMENTS = {}
DATA_DIR = "data"


# =========================
# NORMALIZATION
# =========================
def rewrite_query(question: str):
    return question.strip().lower() if question else ""


# =========================
# SINGLE NORMALIZER (CRITICAL FIX)
# =========================
def normalize_loaded(doc_id: str, loaded: dict):
    return {
        "doc_id": doc_id,
        "documents": loaded.get("documents", []),
        "index": loaded.get("index"),
        "name": loaded.get("metadata", {}).get("filename"),
        "path": loaded.get("metadata", {}).get("path")
    }


# =========================
# CONTEXT
# =========================
def build_context(chunks):
    formatted = []

    for i, c in enumerate(chunks, 1):
        text = c.get("text", "")
        if text:
            formatted.append(f"[TRECHO {i}]\n{text}")

    return "\n\n".join(formatted)


# =========================
# SOURCES
# =========================
def format_sources(chunks):
    sources = []

    for i, chunk in enumerate(chunks, 1):
        sources.append({
            "id": i,
            "text": (chunk.get("text") or "")[:200],
            "doc_id": chunk.get("doc_id"),
            "score": round(chunk.get("score", 0), 4) if chunk.get("score") is not None else None,
            "chunk_id": chunk.get("id") or chunk.get("chunk_id"),
            "page": chunk.get("page"),
            "bbox": chunk.get("bbox"),
            "line_boxes": chunk.get("line_boxes", []),
        })

    return sources


# =========================
# LOAD DOCUMENT SAFE
# =========================
def get_document(doc_id: str):
    if doc_id in DOCUMENTS:
        return DOCUMENTS[doc_id]

    loaded = load_document(doc_id)

    if not loaded:
        return None

    doc = normalize_loaded(doc_id, loaded)

    if not doc.get("documents"):
        return None

    DOCUMENTS[doc_id] = doc
    return doc


# =========================
# SEARCH WRAPPER SAFE
# =========================
def run_search(doc, query):
    try:
        return search(
            query=query,
            model=model,
            index=doc["index"],
            documents=doc["documents"],
            k=10
        )
    except Exception as e:
        print("🔥 SEARCH ERROR:", e)
        return []


# =========================
# MAIN ENDPOINT
# =========================
@router.post("/ask")
async def ask_question(data: dict):
    try:
        question = rewrite_query(data.get("question"))
        doc_id = data.get("doc_id")

        if not question:
            return {"error": "question é obrigatório"}

        all_results = []

        # =========================
        # SINGLE DOC MODE
        # =========================
        if doc_id:
            doc = get_document(doc_id)

            if not doc:
                return {"error": "Documento não encontrado ou inválido"}

            all_results.extend(run_search(doc, question))

        # =========================
        # MULTI DOC MODE
        # =========================
        else:
            docs = []

            if not os.path.exists(DATA_DIR):
                return {"error": "DATA_DIR não encontrado"}

            for file in os.listdir(DATA_DIR):
                if file.endswith(".json"):
                    current_id = file.replace(".json", "")

                    doc = get_document(current_id)
                    if doc:
                        docs.append(doc)

            if not docs:
                return {"error": "Nenhum documento disponível"}

            for doc in docs:
                all_results.extend(run_search(doc, question))

        # =========================
        # NO RESULTS
        # =========================
        if not all_results:
            return {
                "question": question,
                "answer": "Não encontrei informações relevantes no documento.",
                "sources": []
            }

        # =========================
        # RERANK SAFE
        # =========================
        candidate_chunks = [
            c for c in all_results[:20]
            if c.get("text")
        ]

        top_chunks = (
            rerank(question, candidate_chunks, top_k=5)
            if candidate_chunks and RAG_MODE == "full"
            else candidate_chunks[:5]
        )

        # =========================
        # CONTEXT + LLM
        # =========================
        context = build_context(top_chunks)
        answer = generate_answer(question, context)

        # =========================
        # RESPONSE
        # =========================
        return {
            "question": question,
            "answer": answer,
            "sources": format_sources(top_chunks)
        }

    except Exception as e:
        print("🔥 ERRO NO /ASK")
        traceback.print_exc()

        return {"error": str(e)}


# =========================
# COMPAT LAYER (FIXED)
# =========================
def search_similar_documents(question: str, doc_id: str = None):
    try:
        if not doc_id:
            return []

        doc = get_document(doc_id)
        if not doc:
            return []

        return run_search(doc, question)

    except Exception as e:
        print("🔥 ERRO search_similar_documents:", e)
        return []
