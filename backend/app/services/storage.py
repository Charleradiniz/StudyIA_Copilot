import json
from pathlib import Path

from app.config import DATA_DIR, UPLOAD_DIR

try:
    import faiss
except Exception:
    faiss = None


DATA_ROOT = Path(DATA_DIR)
DATA_ROOT.mkdir(parents=True, exist_ok=True)
UPLOAD_ROOT = Path(UPLOAD_DIR)
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


def get_user_data_path(user_id: str) -> Path:
    path = DATA_ROOT / user_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_user_upload_path(user_id: str) -> Path:
    path = UPLOAD_ROOT / user_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def iter_doc_id_candidates(doc_id: str):
    raw_doc_id = (doc_id or "").strip()
    if not raw_doc_id:
        return []

    normalized_doc_id = (
        raw_doc_id[:-4]
        if raw_doc_id.lower().endswith(".pdf")
        else raw_doc_id
    )

    candidates = []
    for candidate in (
        raw_doc_id,
        normalized_doc_id,
        f"{normalized_doc_id}.pdf",
    ):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    return candidates


def get_paths(doc_id: str, user_id: str):
    data_path = get_user_data_path(user_id)
    faiss_path = data_path / f"{doc_id}.faiss"
    json_path = data_path / f"{doc_id}.json"
    return faiss_path, json_path


def find_saved_doc_id(doc_id: str, user_id: str):
    for candidate in iter_doc_id_candidates(doc_id):
        _, json_path = get_paths(candidate, user_id)
        if json_path.exists():
            return candidate

    return None


def iter_upload_paths(doc_id: str, user_id: str, metadata=None):
    paths = []

    file_path = (metadata or {}).get("path")
    if file_path:
        paths.append(Path(file_path))

    upload_path = get_user_upload_path(user_id)
    for candidate in iter_doc_id_candidates(doc_id):
        if candidate.lower().endswith(".pdf"):
            candidate_path = upload_path / candidate
        else:
            candidate_path = upload_path / f"{candidate}.pdf"

        if candidate_path not in paths:
            paths.append(candidate_path)

    return paths


def resolve_upload_path(doc_id: str, user_id: str, metadata=None):
    for upload_path in iter_upload_paths(doc_id, user_id, metadata):
        if upload_path.exists() and upload_path.is_file():
            return upload_path

    return None


def save_document(doc_id: str, documents, index, metadata=None, user_id: str = ""):
    faiss_path, json_path = get_paths(doc_id, user_id)

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


def load_document(doc_id: str, user_id: str, *, load_index: bool = True):
    faiss_path, json_path = get_paths(doc_id, user_id)

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


def delete_saved_document(doc_id: str, user_id: str):
    saved_doc_id = find_saved_doc_id(doc_id, user_id)
    if not saved_doc_id:
        return None

    loaded = load_document(saved_doc_id, user_id, load_index=False) or {}
    metadata = loaded.get("metadata", {})
    removed_files = []
    candidate_ids = []

    for candidate in iter_doc_id_candidates(doc_id) + iter_doc_id_candidates(saved_doc_id):
        if candidate not in candidate_ids:
            candidate_ids.append(candidate)

    for candidate in candidate_ids:
        faiss_path, json_path = get_paths(candidate, user_id)
        for target_path in (faiss_path, json_path):
            if target_path.exists():
                target_path.unlink()
                removed_files.append(str(target_path))

    for upload_path in iter_upload_paths(saved_doc_id, user_id, metadata):
        if upload_path.exists() and upload_path.is_file():
            upload_path.unlink()
            removed_files.append(str(upload_path))

    return {
        "doc_id": saved_doc_id,
        "metadata": metadata,
        "removed_files": sorted(set(removed_files)),
    }


def clear_saved_documents(user_id: str):
    removed_documents = []

    for record in list(iter_saved_documents(user_id)):
        deleted = delete_saved_document(record["doc_id"], user_id)
        if deleted:
            removed_documents.append(deleted)

    return removed_documents


def iter_saved_documents(user_id: str):
    for json_path in sorted(get_user_data_path(user_id).glob("*.json"), reverse=True):
        doc_id = json_path.stem
        loaded = load_document(doc_id, user_id, load_index=False)
        if not loaded:
            continue

        faiss_path, _ = get_paths(doc_id, user_id)

        yield {
            "doc_id": doc_id,
            "documents": loaded.get("documents", []),
            "index": loaded.get("index"),
            "metadata": loaded.get("metadata", {}),
            "has_index_file": faiss_path.exists(),
        }
