import numpy as np


def search(query, model, index, documents, k=3):
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
