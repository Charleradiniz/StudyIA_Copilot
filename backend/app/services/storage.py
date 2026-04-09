import json
from pathlib import Path

from app.config import DATA_DIR

try:
    import faiss
except Exception:
    faiss = None


DATA_PATH = Path(DATA_DIR)
DATA_PATH.mkdir(parents=True, exist_ok=True)


def get_paths(doc_id: str):
    faiss_path = DATA_PATH / f"{doc_id}.faiss"
    json_path = DATA_PATH / f"{doc_id}.json"
    return faiss_path, json_path


def save_document(doc_id: str, documents, index, metadata=None):
    faiss_path, json_path = get_paths(doc_id)

    if index is not None and faiss is not None:
        faiss.write_index(index, str(faiss_path))

    payload = {
        "documents": documents,
        "metadata": metadata or {},
    }

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return {
        "faiss_path": str(faiss_path) if index is not None and faiss is not None else None,
        "json_path": str(json_path),
    }


def load_document(doc_id: str, *, load_index: bool = True):
    faiss_path, json_path = get_paths(doc_id)

    if not json_path.exists():
        return None

    index = None
    if load_index and faiss is not None and faiss_path.exists():
        index = faiss.read_index(str(faiss_path))

    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        data = {
            "documents": data,
            "metadata": {},
        }

    return {
        "documents": data.get("documents", []),
        "index": index,
        "metadata": data.get("metadata", {}),
    }


def iter_saved_documents():
    for json_path in sorted(DATA_PATH.glob("*.json"), reverse=True):
        doc_id = json_path.stem
        loaded = load_document(doc_id, load_index=False)
        if not loaded:
            continue

        faiss_path, _ = get_paths(doc_id)

        yield {
            "doc_id": doc_id,
            "documents": loaded.get("documents", []),
            "index": loaded.get("index"),
            "metadata": loaded.get("metadata", {}),
            "has_index_file": faiss_path.exists(),
        }
