from fastapi import APIRouter
from app.services.embeddings import generate_embeddings
from app.services.similarity import find_most_similar
from app.services.llm import generate_answer  # 🔥 OLLAMA

router = APIRouter()

# TEMP: memória em RAM (MVP)
DOCUMENTS = {}


@router.post("/ask")
async def ask_question(data: dict):
    question = data.get("question")
    doc_id = data.get("doc_id")

    if not question or not doc_id:
        return {"error": "question e doc_id são obrigatórios"}

    if doc_id not in DOCUMENTS:
        return {"error": "Documento não encontrado"}

    chunks = DOCUMENTS[doc_id]["chunks"]
    embeddings = DOCUMENTS[doc_id]["embeddings"]

    # embedding da pergunta
    query_embedding = generate_embeddings([question])[0]

    # busca semântica
    results = find_most_similar(query_embedding, embeddings)

    # pega top chunks (melhorado)
    top_chunks = [chunks[i] for i, _ in results[:5]]  # 🔥 aumentei cobertura

    # contexto final
    context = "\n\n".join(top_chunks)

    # 🔥 AGORA USA OLLAMA
    answer = generate_answer(question, context)

    return {
        "question": question,
        "answer": answer,
        "context": top_chunks
    }


# 🔥 compatibilidade com imports antigos
def search_similar_documents(question: str, doc_id: str = None):
    if not doc_id or doc_id not in DOCUMENTS:
        return []

    chunks = DOCUMENTS[doc_id]["chunks"]
    embeddings = DOCUMENTS[doc_id]["embeddings"]

    query_embedding = generate_embeddings([question])[0]
    results = find_most_similar(query_embedding, embeddings)

    return [chunks[i] for i, _ in results]  