from datetime import datetime, timezone
import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.db.database import Base


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=True, index=True)
    filename = Column(String, nullable=False)
    storage_provider = Column(String, nullable=True, default="local")
    storage_path = Column(String, nullable=True)
    faiss_path = Column(String, nullable=True)
    json_path = Column(String, nullable=True)
    byte_size = Column(Integer, nullable=False, default=0)
    chunk_count = Column(Integer, nullable=False, default=0)
    page_count = Column(Integer, nullable=False, default=0)
    rag_mode = Column(String, nullable=False, default="lite")
    vector_ready = Column(Boolean, nullable=False, default=False)
    preview = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=utcnow_naive, nullable=False, index=True)
    uploaded_at = Column(DateTime, default=utcnow_naive, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
