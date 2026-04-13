from datetime import datetime, timezone
import json
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.chat_session import ChatSession
from app.models.user import User

router = APIRouter(prefix="/chats", tags=["chats"])


class ChatSourcePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | str
    text: str
    score: float | None = None
    doc_id: str | None = None
    chunk_id: int | None = None
    page: int | None = None
    bbox: list[float] | None = None
    line_boxes: list[list[float]] = Field(default_factory=list)


class ChatMessagePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    role: Literal["user", "assistant"]
    content: str
    sources: list[ChatSourcePayload] = Field(default_factory=list)


class ChatPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    active_doc_ids: list[str] = Field(default_factory=list)
    messages: list[ChatMessagePayload] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ChatSyncRequest(BaseModel):
    chats: list[ChatPayload] = Field(default_factory=list)


def serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value

    return value.astimezone(timezone.utc).replace(tzinfo=None)


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_active_doc_ids(values: list[str]) -> list[str]:
    normalized_ids: list[str] = []

    for value in values:
        if not isinstance(value, str):
            continue

        normalized = value.strip()
        if normalized and normalized not in normalized_ids:
            normalized_ids.append(normalized)

    return normalized_ids


def serialize_message(message: ChatMessagePayload) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "sources": [
            {
                "id": source.id,
                "text": source.text,
                "score": source.score,
                "doc_id": source.doc_id,
                "chunk_id": source.chunk_id,
                "page": source.page,
                "bbox": source.bbox,
                "line_boxes": source.line_boxes,
            }
            for source in message.sources
        ],
    }


def load_json_list(payload: str | None) -> list:
    if not payload:
        return []

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []

    return data if isinstance(data, list) else []


def serialize_chat(record: ChatSession) -> dict:
    return {
        "id": record.chat_id,
        "title": record.title,
        "active_doc_ids": load_json_list(record.active_doc_ids_json),
        "messages": load_json_list(record.messages_json),
        "created_at": serialize_datetime(record.created_at),
        "updated_at": serialize_datetime(record.updated_at),
    }


@router.get("")
def list_chats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    records = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )

    chats = []
    deleted = []

    for record in records:
        if record.deleted_at is None:
            chats.append(serialize_chat(record))
            continue

        deleted.append(
            {
                "id": record.chat_id,
                "deleted_at": serialize_datetime(record.deleted_at),
            }
        )

    return {
        "chats": chats,
        "deleted": deleted,
    }


@router.post("/sync")
def sync_chats(
    data: ChatSyncRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    requested_chats = {chat.id: chat for chat in data.chats}
    if not requested_chats:
        return {
            "synced_chat_ids": [],
            "skipped_chat_ids": [],
        }

    existing_records = (
        db.query(ChatSession)
        .filter(
            ChatSession.user_id == current_user.id,
            ChatSession.chat_id.in_(list(requested_chats.keys())),
        )
        .all()
    )
    existing_by_chat_id = {
        record.chat_id: record
        for record in existing_records
    }

    synced_chat_ids = []
    skipped_chat_ids = []

    for chat_id, chat in requested_chats.items():
        record = existing_by_chat_id.get(chat_id)
        incoming_created_at = normalize_datetime(chat.created_at)
        incoming_updated_at = normalize_datetime(chat.updated_at)
        if record is not None and record.deleted_at is not None:
            skipped_chat_ids.append(chat_id)
            continue

        if (
            record is not None
            and record.updated_at is not None
            and incoming_updated_at <= record.updated_at
        ):
            skipped_chat_ids.append(chat_id)
            continue

        if record is None:
            record = ChatSession(
                user_id=current_user.id,
                chat_id=chat.id,
            )
            db.add(record)
            existing_by_chat_id[chat_id] = record

        record.title = chat.title.strip() or "New conversation"
        record.active_doc_ids_json = json.dumps(
            normalize_active_doc_ids(chat.active_doc_ids),
            ensure_ascii=False,
        )
        record.messages_json = json.dumps(
            [serialize_message(message) for message in chat.messages],
            ensure_ascii=False,
        )
        record.created_at = incoming_created_at
        record.updated_at = incoming_updated_at
        record.deleted_at = None
        synced_chat_ids.append(chat_id)

    db.commit()

    return {
        "synced_chat_ids": synced_chat_ids,
        "skipped_chat_ids": skipped_chat_ids,
    }


@router.delete("/{chat_id}")
def delete_chat(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = (
        db.query(ChatSession)
        .filter(
            ChatSession.user_id == current_user.id,
            ChatSession.chat_id == chat_id,
        )
        .first()
    )

    tombstone_time = utcnow_naive()
    if record is None:
        record = ChatSession(
            user_id=current_user.id,
            chat_id=chat_id,
            title="Deleted conversation",
            created_at=tombstone_time,
        )
        db.add(record)

    record.active_doc_ids_json = "[]"
    record.messages_json = "[]"
    record.updated_at = tombstone_time
    record.deleted_at = tombstone_time
    db.commit()

    return {
        "chat_id": chat_id,
        "deleted": True,
    }


@router.delete("")
def clear_chats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    records = (
        db.query(ChatSession)
        .filter(
            ChatSession.user_id == current_user.id,
            ChatSession.deleted_at.is_(None),
        )
        .all()
    )

    tombstone_time = utcnow_naive()
    deleted_chat_ids = []

    for record in records:
        record.active_doc_ids_json = "[]"
        record.messages_json = "[]"
        record.updated_at = tombstone_time
        record.deleted_at = tombstone_time
        deleted_chat_ids.append(record.chat_id)

    db.commit()

    return {
        "deleted_count": len(deleted_chat_ids),
        "deleted_chat_ids": deleted_chat_ids,
    }
