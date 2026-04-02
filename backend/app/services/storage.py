import os
import json

try:
    import faiss
except Exception:
    faiss = None

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


def get_paths(doc_id: str):
    faiss_path = os.path.join(DATA_DIR, f"{doc_id}.faiss")
    json_path = os.path.join(DATA_DIR, f"{doc_id}.json")
    return faiss_path, json_path


# =========================
# SAVE DOCUMENT
# =========================
def save_document(doc_id: str, documents, index, metadata=None):
    faiss_path, json_path = get_paths(doc_id)

    if index is not None and faiss is not None:
        # Save the FAISS index
        faiss.write_index(index, faiss_path)

    # Save documents and metadata (important for the PDF viewer)
    payload = {
        "documents": documents,
        "metadata": metadata or {}
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return {
        "faiss_path": faiss_path if index is not None and faiss is not None else None,
        "json_path": json_path
    }


# =========================
# LOAD DOCUMENT
# =========================
def load_document(doc_id: str):
    faiss_path, json_path = get_paths(doc_id)

    if not os.path.exists(json_path):
        return None

    index = None
    if faiss is not None and os.path.exists(faiss_path):
        # Load the FAISS index
        index = faiss.read_index(faiss_path)

    # Load JSON
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        "documents": data.get("documents", []),
        "index": index,
        "metadata": data.get("metadata", {})
    }
