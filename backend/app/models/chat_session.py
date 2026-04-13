import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, UniqueConstraint

from app.db.database import Base


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "chat_id", name="uq_chat_sessions_user_chat"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    chat_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    active_doc_ids_json = Column(Text, nullable=False, default="[]")
    messages_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=utcnow_naive, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
