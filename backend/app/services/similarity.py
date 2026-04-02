def search(query, model, index, documents, k=3):
    # embedding da pergunta
    query_embedding = model.encode(
        [query],
        normalize_embeddings=True
    )

    # busca no FAISS
    distances, indices = index.search(query_embedding, k)

    # pega os melhores chunks
    results = [documents[i]["text"] for i in indices[0]]

    return results