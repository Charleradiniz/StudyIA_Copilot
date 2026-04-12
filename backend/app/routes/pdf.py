from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.db.deps import get_current_user
from app.models.user import User
from app.services.storage import load_document, resolve_upload_path

router = APIRouter()


@router.get("/pdf/{file_id}")
def get_pdf(
    file_id: str,
    current_user: User = Depends(get_current_user),
):
    normalized_file_id = file_id.replace(".pdf", "").strip()
    loaded = load_document(normalized_file_id, current_user.id, load_index=False)
    if not loaded:
        raise HTTPException(
            status_code=404,
            detail=f"PDF not found: {normalized_file_id}",
        )
    metadata = loaded.get("metadata", {}) if loaded else {}
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
