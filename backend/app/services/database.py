import os
import json
import faiss
import numpy as np

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


def get_paths(doc_id: str):
    faiss_path = os.path.join(DATA_DIR, f"{doc_id}.faiss")
    json_path = os.path.join(DATA_DIR, f"{doc_id}.json")
    return faiss_path, json_path


def save_document(doc_id: str, documents, index):
    faiss_path, json_path = get_paths(doc_id)

    # salva FAISS
    faiss.write_index(index, faiss_path)

    # salva documents
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)


def load_document(doc_id: str):
    faiss_path, json_path = get_paths(doc_id)

    if not os.path.exists(faiss_path) or not os.path.exists(json_path):
        return None

    # carrega FAISS
    index = faiss.read_index(faiss_path)

    # carrega documents
    with open(json_path, "r", encoding="utf-8") as f:
        documents = json.load(f)

    return {
        "documents": documents,
        "index": index
    }