import re
from typing import List


def clean_text(text: str) -> str:
    """
    Limpeza básica do texto extraído do PDF.
    """
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_by_sentences(text: str) -> List[str]:
    """
    Divide texto em frases de forma mais estável.
    """
    return re.split(r'(?<=[.!?])\s+', text)


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 120
) -> List[str]:
    """
    Chunking robusto para RAG nível produção.
    """

    text = clean_text(text)

    # 🔥 tentativa de split estrutural (caso PDF tenha headings)
    structural_splits = re.split(r'\n{2,}', text)

    chunks = []

    for block in structural_splits:
        block = block.strip()
        if not block:
            continue

        sentences = split_by_sentences(block)

        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # 🔥 caso sentença seja absurda (PDF ruim)
            if len(sentence) > chunk_size:
                for i in range(0, len(sentence), chunk_size):
                    chunks.append(sentence[i:i + chunk_size])
                continue

            # adiciona no chunk atual
            if len(current_chunk) + len(sentence) <= chunk_size:
                current_chunk += sentence + " "
            else:
                # salva chunk atual
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())

                # 🔥 overlap inteligente por palavras (não slicing bruto)
                words = current_chunk.split()
                overlap_words = words[-max(1, overlap // 10):]

                current_chunk = " ".join(overlap_words) + " " + sentence + " "

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

    # limpeza final (remove chunks minúsculos ruins)
    chunks = [c.strip() for c in chunks if len(c.strip()) > 30]

    return chunks