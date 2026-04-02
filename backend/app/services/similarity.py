import math
import re

from app.config import RAG_MODE

if RAG_MODE == "full":
    try:
        import numpy as np
    except Exception:
        np = None
else:
    np = None


TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_PATTERN.findall(text or "")}


def lexical_score(query_tokens: set[str], text: str) -> float:
    if not query_tokens:
        return 0.0

    text_tokens = tokenize(text)
    if not text_tokens:
        return 0.0

    overlap = len(query_tokens & text_tokens)
    if overlap == 0:
        return 0.0

    return overlap / math.sqrt(len(text_tokens))


def search(query, model, index, documents, k=3):
    if RAG_MODE != "full" or model is None or index is None or np is None:
        return search_lite(query, documents, k)

    try:
        # =========================
        # VALIDATIONS
        # =========================
        if not query or index is None or not documents:
            return []

        if not hasattr(index, "search"):
            print("🔥 INDEX INVALID")
            return []

        # =========================
        # EMBEDDING SAFE
        # =========================
        query_embedding = model.encode(
            [query],
            normalize_embeddings=True
        )

        if query_embedding is None:
            return []

        query_embedding = np.array(query_embedding).astype("float32")

        # =========================
        # FAISS SEARCH
        # =========================
        distances, indices = index.search(query_embedding, k)

        if distances is None or indices is None:
            return []

        results = []

        # =========================
        # MAP RESULTS
        # =========================
        for score, idx in zip(distances[0], indices[0]):

            if idx is None:
                continue

            if not isinstance(idx, (int, np.integer)):
                continue

            if idx < 0 or idx >= len(documents):
                continue

            doc = documents[idx]

            if not isinstance(doc, dict):
                continue

            results.append({
                # RAG chunk
                "id": int(idx),

                # text
                "text": doc.get("text") or "",

                # RAG id
                "doc_id": doc.get("doc_id"),

                # Main fix: real PDF id
                "file_id": doc.get("file_id"),  # Essential

                "score": float(score) if score is not None else 0.0,
                "chunk_id": doc.get("id"),
                "page": doc.get("page"),
                "bbox": doc.get("bbox"),
                "line_boxes": doc.get("line_boxes", []),
            })

        return results

    except Exception as e:
        print(" SEARCH ERROR:", e)
        return []


def search_lite(query, documents, k=3):
    if not query or not documents:
        return []

    query_tokens = tokenize(query)
    results = []

    for idx, doc in enumerate(documents):
        if not isinstance(doc, dict):
            continue

        text = doc.get("text") or ""
        score = lexical_score(query_tokens, text)
        if score <= 0:
            continue

        results.append({
            "id": int(idx),
            "text": text,
            "doc_id": doc.get("doc_id"),
            "file_id": doc.get("file_id"),
            "score": float(score),
            "chunk_id": doc.get("id"),
            "page": doc.get("page"),
            "bbox": doc.get("bbox"),
            "line_boxes": doc.get("line_boxes", []),
        })

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:k]
