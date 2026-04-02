import re
from typing import List, Dict


# =========================
# TEXT CLEANUP
# =========================
def clean_text(text: str) -> str:
    """
    Basic cleanup for text extracted from the PDF.
    """
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# =========================
# SPLIT INTO SENTENCES
# =========================
def split_by_sentences(text: str) -> List[str]:
    """
    Split text into sentences in a stable way.
    """
    return re.split(r'(?<=[.!?])\s+', text)


# =========================
# CHUNKING FOR RAG
# =========================
def chunk_text(
    text: str,
    doc_id: str,              # The doc_id is now required
    chunk_size: int = 800,
    overlap: int = 120
) -> List[Dict]:
    """
    Robust chunking for production-grade RAG.
    Each chunk carries doc_id for full traceability.
    """

    text = clean_text(text)

    # Structural split based on PDF paragraphs
    structural_splits = re.split(r'\n{2,}', text)

    chunks: List[Dict] = []

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

            # Very large sentence -> split directly
            if len(sentence) > chunk_size:
                for i in range(0, len(sentence), chunk_size):
                    chunks.append({
                        "text": sentence[i:i + chunk_size],
                        "doc_id": doc_id,
                        "page": None,
                        "bbox": None
                    })
                continue

            # Accumulate into the current chunk
            if len(current_chunk) + len(sentence) <= chunk_size:
                current_chunk += sentence + " "
            else:
                # Save the current chunk
                if current_chunk.strip():
                    chunks.append({
                        "text": current_chunk.strip(),
                        "doc_id": doc_id,
                        "page": None,
                        "bbox": None
                    })

                # Smart overlap
                words = current_chunk.split()
                overlap_words = words[-max(1, overlap // 10):]

                current_chunk = " ".join(overlap_words) + " " + sentence + " "

        # Save the last chunk from the block
        if current_chunk.strip():
            chunks.append({
                "text": current_chunk.strip(),
                "doc_id": doc_id,
                "page": None,
                "bbox": None
            })

    # Filter out noise (very small chunks)
    chunks = [
        c for c in chunks
        if len(c["text"].strip()) > 30
    ]

    return chunks
