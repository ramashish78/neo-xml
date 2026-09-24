from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.rate_limit import client_ip, enforce_rate_limit
from app.core.serialize import to_public
from app.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", status_code=201)
def upload_file(
    request: Request,
    file: UploadFile = File(...),
    category: str = Form(...),
    workspace_id: str | None = Form(default=None),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    enforce_rate_limit(request, "upload", 30)
    saved = FileService(db).upload(user, file, category, workspace_id, client_ip(request))
    return to_public(saved)


@router.get("/{file_id}/download")
def download_file(file_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    service = FileService(db)
    doc = service.get_for_user(user, file_id)
    path = service.absolute_path(doc)
    return FileResponse(path, media_type=doc["mime_type"], filename=doc["original_name"])
