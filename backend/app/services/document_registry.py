from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.document import Document


def normalize_datetime(value: datetime | str | None) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    if isinstance(value, str) and value.strip():
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)

    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_document_record(db: Session, user_id: str, doc_id: str) -> Document | None:
    return (
        db.query(Document)
        .filter(
            Document.id == doc_id,
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
        )
        .first()
    )


def list_document_records(db: Session, user_id: str) -> list[Document]:
    return (
        db.query(Document)
        .filter(
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
        )
        .order_by(Document.uploaded_at.desc())
        .all()
    )


def upsert_document_record(
    db: Session,
    *,
    doc_id: str,
    user_id: str,
    filename: str,
    storage_provider: str,
    storage_path: str,
    faiss_path: str | None,
    json_path: str | None,
    byte_size: int,
    chunk_count: int,
    page_count: int,
    rag_mode: str,
    vector_ready: bool,
    preview: str,
    uploaded_at: datetime | str | None,
) -> Document:
    record = (
        db.query(Document)
        .filter(Document.id == doc_id)
        .first()
    )
    timestamp = normalize_datetime(uploaded_at)

    if record is None:
        record = Document(
            id=doc_id,
            user_id=user_id,
            created_at=timestamp,
        )
        db.add(record)

    record.user_id = user_id
    record.filename = filename
    record.storage_provider = storage_provider
    record.storage_path = storage_path
    record.faiss_path = faiss_path
    record.json_path = json_path
    record.byte_size = byte_size
    record.chunk_count = chunk_count
    record.page_count = page_count
    record.rag_mode = rag_mode
    record.vector_ready = vector_ready
    record.preview = preview
    record.uploaded_at = timestamp
    record.updated_at = timestamp
    record.deleted_at = None

    db.commit()
    db.refresh(record)
    return record


def mark_document_deleted(db: Session, user_id: str, doc_id: str) -> bool:
    record = (
        db.query(Document)
        .filter(
            Document.id == doc_id,
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
        )
        .first()
    )
    if record is None:
        return False

    timestamp = datetime.now(timezone.utc).replace(tzinfo=None)
    record.deleted_at = timestamp
    record.updated_at = timestamp
    db.commit()
    return True
