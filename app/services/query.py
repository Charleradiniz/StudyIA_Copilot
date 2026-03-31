from fastapi import APIRouter
import os

from app.services.similarity import search
from app.services.embeddings import model
from app.services.llm import generate_answer
from app.services.database import load_document
from app.services.reranker import rerank

router = APIRouter()

# 🔥 cache em memória
DOCUMENTS = {}

DATA_DIR = "data"


@router.post("/ask")
async def ask_question(data: dict):
    question = data.get("question")
    doc_id = data.get("doc_id")  # agora opcional

    if not question:
        return {"error": "question é obrigatório"}

    all_results = []

    # 🔥 CASO 1: busca em documento específico
    if doc_id:
        if doc_id not in DOCUMENTS:
            loaded = load_document(doc_id)
            if not loaded:
                return {"error": "Documento não encontrado"}
            DOCUMENTS[doc_id] = loaded

        docs = [DOCUMENTS[doc_id]]

    # 🔥 CASO 2: busca em TODOS os documentos
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

    # 🔥 busca em todos os docs
    for doc in docs:
        results = search(
            query=question,
            model=model,
            index=doc["index"],
            documents=doc["documents"],
            k=3
        )
        all_results.extend(results)

    # 🔥 limita os melhores (simples)
    candidate_chunks = all_results[:8]
    top_chunks = rerank(question, candidate_chunks, top_k=3)  # 🔥 menos contexto

    # contexto final
    context = "\n\n".join(top_chunks)

    # resposta do LLM
    answer = generate_answer(question, context)

    return {
        "question": question,
        "answer": answer,
        "sources": top_chunks
    }


# 🔥 compatibilidade com imports antigos
def search_similar_documents(question: str, doc_id: str = None):
    if not doc_id:
        return []

    if doc_id not in DOCUMENTS:
        loaded = load_document(doc_id)
        if not loaded:
            return []
        DOCUMENTS[doc_id] = loaded

    documents = DOCUMENTS[doc_id]["documents"]
    index = DOCUMENTS[doc_id]["index"]

    results = search(
        query=question,
        model=model,
        index=index,
        documents=documents,
        k=5
    )

    return results