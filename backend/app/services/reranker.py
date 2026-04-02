from sentence_transformers import CrossEncoder

reranker_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")


def extract_text(chunk):
    if not isinstance(chunk, dict):
        return ""

    return (
        chunk.get("text")
        or chunk.get("content")
        or chunk.get("document")
        or ""
    )


def rerank(query: str, chunks: list, top_k: int = 5):
    if not chunks or not query:
        return []

    valid_chunks = []
    pairs = []

    for c in chunks:
        text = extract_text(c)

        if isinstance(text, str) and text.strip():
            valid_chunks.append(c)
            pairs.append((query, text.strip()))

    if not pairs:
        return []

    try:
        scores = reranker_model.predict(pairs)
    except Exception as e:
        print("🔥 RERANK ERROR:", e)
        return valid_chunks[:top_k]

    scored = sorted(zip(valid_chunks, scores), key=lambda x: x[1], reverse=True)

    return [c for c, _ in scored[:top_k]]