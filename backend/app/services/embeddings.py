from sentence_transformers import SentenceTransformer

# Modelo leve e rápido (PERFEITO pra você)
model = SentenceTransformer("all-MiniLM-L6-v2")

def generate_embeddings(chunks: list[str]):
    embeddings = model.encode(chunks)

    return embeddings.tolist()