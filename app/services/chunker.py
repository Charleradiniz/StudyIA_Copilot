import re

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100):
    sentences = re.split(r'(?<=[.!?]) +', text)

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= chunk_size:
            current_chunk += sentence + " "
        else:
            chunks.append(current_chunk.strip())

            # cria overlap inteligente
            overlap_text = current_chunk[-overlap:]
            current_chunk = overlap_text + sentence + " "

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks