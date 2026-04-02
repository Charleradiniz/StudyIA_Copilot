from fastapi import APIRouter
import os
import re
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
STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no",
    "na", "nos", "nas", "um", "uma", "uns", "umas", "para", "por", "com",
    "sem", "sobre", "que", "se", "ao", "aos", "à", "às", "ou", "como",
    "mais", "menos", "muito", "muita", "muitos", "muitas", "ser", "estar",
    "fala", "falar", "documento", "esse", "essa", "isso", "ele", "ela",
}


# =========================
# NORMALIZATION
# =========================
def rewrite_query(question: str):
    return question.strip().lower() if question else ""


def tokenize(text: str):
    if not text:
        return []

    tokens = re.findall(r"\w+", text.lower())
    return [token for token in tokens if len(token) > 2 and token not in STOPWORDS]


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


def lexical_search(documents, query, k=5):
    query_tokens = set(tokenize(query))

    if not query_tokens:
        return []

    scored = []

    for index, chunk in enumerate(documents):
        text = (chunk.get("text") or "").strip()
        if not text:
            continue

        text_tokens = set(tokenize(text))
        overlap = query_tokens & text_tokens
        if not overlap:
            continue

        coverage = len(overlap) / max(len(query_tokens), 1)
        density = len(overlap) / max(len(text_tokens), 1)
        score = round((coverage * 0.8) + (density * 0.2), 4)

        scored.append({
            "id": index,
            "text": text,
            "doc_id": chunk.get("doc_id"),
            "file_id": chunk.get("file_id"),
            "score": score,
            "chunk_id": chunk.get("id"),
            "page": chunk.get("page"),
            "bbox": chunk.get("bbox"),
            "line_boxes": chunk.get("line_boxes", []),
        })

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:k]


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
            if not all_results:
                all_results.extend(lexical_search(doc.get("documents", []), question))

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
                results = run_search(doc, question)
                if not results:
                    results = lexical_search(doc.get("documents", []), question)
                all_results.extend(results)

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
        if not top_chunks and doc_id:
            doc = get_document(doc_id)
            if doc:
                top_chunks = lexical_search(doc.get("documents", []), question)

        if not top_chunks:
            return {
                "question": question,
                "answer": "NÃ£o encontrei informaÃ§Ãµes relevantes no documento.",
                "sources": []
            }

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
