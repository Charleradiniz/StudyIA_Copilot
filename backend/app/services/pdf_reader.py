import fitz  # PyMuPDF

MIN_CHUNK_CHARS = 120
TARGET_CHUNK_CHARS = 700
OVERLAP_CHARS = 140


def clean_text(text: str) -> str:
    if not text:
        return ""

    return " ".join(text.split()).strip()


def merge_bbox(boxes: list[list[float]]) -> list[float] | None:
    valid_boxes = [box for box in boxes if box and len(box) == 4]

    if not valid_boxes:
        return None

    x0 = min(box[0] for box in valid_boxes)
    y0 = min(box[1] for box in valid_boxes)
    x1 = max(box[2] for box in valid_boxes)
    y1 = max(box[3] for box in valid_boxes)

    return [x0, y0, x1, y1]


def collect_page_lines(page) -> list[dict]:
    page_dict = page.get_text("dict")
    lines: list[dict] = []

    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue

        for line in block.get("lines", []):
            spans = line.get("spans", [])
            span_texts = [clean_text(span.get("text", "")) for span in spans]
            text = clean_text(" ".join(part for part in span_texts if part))

            if not text:
                continue

            bbox = merge_bbox([list(span.get("bbox", ())) for span in spans])
            if not bbox:
                continue

            lines.append({
                "text": text,
                "bbox": bbox,
            })

    return lines


def overlap_tail(items: list[dict], overlap_chars: int) -> list[dict]:
    if overlap_chars <= 0:
        return []

    selected: list[dict] = []
    total_chars = 0

    for item in reversed(items):
        selected.append(item)
        total_chars += len(item["text"])
        if total_chars >= overlap_chars:
            break

    return list(reversed(selected))


def build_chunk(chunk_id: int, page_num: int, items: list[dict]) -> dict | None:
    text = clean_text(" ".join(item["text"] for item in items))
    bbox = merge_bbox([item["bbox"] for item in items])
    line_boxes = [item["bbox"] for item in items if item.get("bbox")]

    if len(text) < MIN_CHUNK_CHARS or not bbox or not line_boxes:
        return None

    return {
        "id": chunk_id,
        "text": text,
        "page": page_num,
        "bbox": bbox,
        "line_boxes": line_boxes,
        "char_length": len(text),
    }


def extract_chunks_with_positions(pdf_path: str):
    doc = fitz.open(pdf_path)

    chunks = []
    chunk_id = 0

    for page_num, page in enumerate(doc):
        lines = collect_page_lines(page)
        current_items: list[dict] = []
        current_length = 0

        for line in lines:
            line_length = len(line["text"])

            if current_items and current_length + line_length > TARGET_CHUNK_CHARS:
                chunk = build_chunk(chunk_id, page_num, current_items)
                if chunk:
                    chunks.append(chunk)
                    chunk_id += 1

                current_items = overlap_tail(current_items, OVERLAP_CHARS)
                current_length = sum(len(item["text"]) for item in current_items)

            current_items.append(line)
            current_length += line_length

        if current_items:
            chunk = build_chunk(chunk_id, page_num, current_items)
            if chunk:
                chunks.append(chunk)
                chunk_id += 1

    return chunks


def extract_text_from_pdf(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)

    pages = []

    for page in doc:
        text = clean_text(page.get_text())
        if text:
            pages.append(text)

    return "\n\n".join(pages)
