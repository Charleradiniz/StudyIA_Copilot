from app.config import RAG_MODE

model = None

if RAG_MODE == "full":
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        model = None


def generate_embeddings(chunks: list[str]):
    if RAG_MODE != "full" or model is None:
        return []

    embeddings = model.encode(chunks, normalize_embeddings=True)
    return embeddings.tolist()
