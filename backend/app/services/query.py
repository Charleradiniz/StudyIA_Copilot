from fastapi import APIRouter
import os

from app.services.similarity import search
from app.services.embeddings import model
from app.services.llm import generate_answer
from app.services.database import load_document
from app.services.reranker import rerank

router = APIRouter()

DOCUMENTS = {}
DATA_DIR = "data"


# 🔥 melhora a query antes do embedding/search
def rewrite_query(question: str) -> str:
    """
    Normaliza a pergunta para melhorar retrieval.
    """
    return question.strip().lower()


# 🔥 reduz ruído antes de mandar pro LLM
def build_context(chunks):
    formatted = []

    for i, c in enumerate(chunks, 1):
        formatted.append(f"[TRECHO {i}]\n{c}")

    return "\n\n".join(formatted)


@router.post("/ask")
async def ask_question(data: dict):
    question = data.get("question")
    doc_id = data.get("doc_id")

    if not question:
        return {"error": "question é obrigatório"}

    question = rewrite_query(question)

    all_results = []

    # 🔥 CASO 1: documento específico
    if doc_id:
        if doc_id not in DOCUMENTS:
            loaded = load_document(doc_id)
            if not loaded:
                return {"error": "Documento não encontrado"}
            DOCUMENTS[doc_id] = loaded

        docs = [DOCUMENTS[doc_id]]

    # 🔥 CASO 2: todos documentos
    else:
        docs = []

        for file in os.listdir(DATA_DIR):
            if file.endswith(".faiss"):
                current_id = file.replace(".faiss", "")

                if current_id not in DOCUMENTS:
                    loaded = load_document(current_id)
                    if loaded:
                        DOCUMENTS[current_id] = loaded

                if current_id in DOCUMENTS:
                    docs.append(DOCUMENTS[current_id])

        if not docs:
            return {"error": "Nenhum documento disponível"}

    # 🔥 RETRIEVAL MAIS FORTE (top-k maior aqui)
    for doc in docs:
        results = search(
            query=question,
            model=model,
            index=doc["index"],
            documents=doc["documents"],
            k=10   # 🔥 mais candidatos = melhor rerank
        )
        all_results.extend(results)

    if not all_results:
        return {
            "question": question,
            "answer": "Não encontrei informações relevantes no documento.",
            "sources": []
        }

    # 🔥 rerank forte (fase final de seleção)
    candidate_chunks = all_results[:20]
    top_chunks = rerank(question, candidate_chunks, top_k=5)

    # 🔥 contexto limpo e estruturado
    context = build_context(top_chunks)

    # 🔥 geração com contexto melhor estruturado
    answer = generate_answer(question, context)

    return {
        "question": question,
        "answer": answer,
        "sources": top_chunks
    }


# 🔥 compatibilidade com código antigo
def search_similar_documents(question: str, doc_id: str = None):
    if not doc_id:
        return []

    if doc_id not in DOCUMENTS:
        loaded = load_document(doc_id)
        if not loaded:
            return []
        DOCUMENTS[doc_id] = loaded

    doc = DOCUMENTS[doc_id]

    results = search(
        query=question,
        model=model,
        index=doc["index"],
        documents=doc["documents"],
        k=8
    )

    return results