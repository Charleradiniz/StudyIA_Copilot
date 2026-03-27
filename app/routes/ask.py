from fastapi import APIRouter
from app.services.query import search_similar_documents
from app.services.llm import generate_answer

router = APIRouter()

@router.post("/api/ask")
def ask(payload: dict):
    question = payload["question"]
    doc_id = payload["doc_id"]

    # 1. RAG (busca contexto)
    context = search_similar_documents(question, doc_id)

    # 2. LLM (gera resposta)
    answer = generate_answer(
        question=question,
        context="\n\n".join(context)
    )

    return {
        "question": question,
        "answer": answer,
        "context": context
    }