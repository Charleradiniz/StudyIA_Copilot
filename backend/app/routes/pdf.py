from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import UPLOAD_DIR

router = APIRouter()


@router.get("/pdf/{file_id}")
def get_pdf(file_id: str):
    normalized_file_id = file_id.replace(".pdf", "").strip()
    file_path = Path(UPLOAD_DIR) / f"{normalized_file_id}.pdf"

    if not file_path.is_file():
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
