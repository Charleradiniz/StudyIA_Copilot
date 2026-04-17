import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.user import User
from app.services.document_registry import get_document_record
from app.services.storage import load_document, resolve_upload_path

router = APIRouter()
logger = logging.getLogger("studyiacopilot.pdf")


def load_document_record_safe(db: Session, user_id: str, doc_id: str):
    try:
        return get_document_record(db, user_id, doc_id)
    except Exception:
        logger.exception(
            "document_registry_read_failed user_id=%s doc_id=%s",
            user_id,
            doc_id,
        )
        return None


@router.get("/pdf/{file_id}")
def get_pdf(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    normalized_file_id = file_id.replace(".pdf", "").strip()
    loaded = load_document(normalized_file_id, current_user.id, load_index=False)
    document_record = load_document_record_safe(db, current_user.id, normalized_file_id)
    if not loaded:
        if not document_record or not document_record.storage_path:
            raise HTTPException(
                status_code=404,
                detail=f"PDF not found: {normalized_file_id}",
            )
        metadata = {
            "path": document_record.storage_path,
        }
    else:
        metadata = loaded.get("metadata", {}) if loaded else {}
        if document_record and document_record.storage_path and not metadata.get("path"):
            metadata["path"] = document_record.storage_path
    file_path = resolve_upload_path(normalized_file_id, current_user.id, metadata)

    if file_path is None or not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"PDF not found: {normalized_file_id}",
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"{normalized_file_id}.pdf",
        headers={
            "Content-Disposition": f'inline; filename="{normalized_file_id}.pdf"',
            "X-Content-Type-Options": "nosniff",
        },
    )
