from sentence_transformers import CrossEncoder

reranker_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")


def rerank(query: str, chunks: list[str], top_k: int = 5):
    pairs = [(query, chunk) for chunk in chunks]

    scores = reranker_model.predict(pairs)

    scored_chunks = list(zip(chunks, scores))
    scored_chunks.sort(key=lambda x: x[1], reverse=True)

    return [chunk for chunk, _ in scored_chunks[:top_k]]