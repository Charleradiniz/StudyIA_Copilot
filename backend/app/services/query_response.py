from collections import defaultdict


def build_context(chunks: list[dict]) -> str:
    grouped_chunks: dict[str, list[dict]] = defaultdict(list)
    document_order: list[str] = []

    for chunk in chunks:
        text = (chunk.get("text") or "").strip()
        doc_id = chunk.get("doc_id") or "document"
        if not text:
            continue

        if doc_id not in grouped_chunks:
            document_order.append(doc_id)

        grouped_chunks[doc_id].append(chunk)

    sections = []

    for doc_id in document_order:
        doc_chunks = grouped_chunks[doc_id]
        if not doc_chunks:
            continue

        label = doc_chunks[0].get("doc_label") or doc_chunks[0].get("doc_name") or doc_id
        section_lines = [f"[{label}]"]

        for index, chunk in enumerate(doc_chunks, 1):
            page_number = chunk.get("page")
            page_suffix = f" (page {page_number + 1})" if isinstance(page_number, int) else ""
            section_lines.append(f"Excerpt {index}{page_suffix}:")
            section_lines.append((chunk.get("text") or "").strip())

        sections.append("\n".join(section_lines))

    return "\n\n".join(sections)


def format_sources(chunks: list[dict]) -> list[dict]:
    sources = []

    for index, chunk in enumerate(chunks, 1):
        sources.append({
            "id": index,
            "text": (chunk.get("text") or "")[:200],
            "doc_id": chunk.get("doc_id"),
            "doc_name": chunk.get("doc_name"),
            "doc_label": chunk.get("doc_label"),
            "score": round(chunk.get("score", 0), 4) if chunk.get("score") is not None else None,
            "chunk_id": chunk.get("id") or chunk.get("chunk_id"),
            "page": chunk.get("page"),
            "bbox": chunk.get("bbox"),
            "line_boxes": chunk.get("line_boxes", []),
        })

    return sources
