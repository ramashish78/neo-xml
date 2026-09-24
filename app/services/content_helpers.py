import re

from app.core.errors import AppError
from app.repositories.base import Graphics, Workspaces
from app.services.file_service import FileService

CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,40}$")


def require_active_workspace(db, user, access, workspace_id: str) -> dict:
    access.require_workspace(user, workspace_id)
    workspace = Workspaces(db).get(workspace_id)
    if not workspace:
        raise AppError(404, "Resource not found")
    if workspace.get("status") != "active":
        raise AppError(409, "Workspace is archived")
    return workspace


def check_code(value: str, label: str) -> str:
    if not CODE_RE.match(value):
        raise AppError(422, f"Invalid {label}")
    return value


def next_code(repo, workspace_id: str, field: str, prefix: str) -> str:
    count = repo.count({"workspace_id": workspace_id}) + 1
    return f"{prefix}-{count:05d}"


def xml_from_request(files: FileService, body, workspace_id: str) -> tuple[bytes, dict | None]:
    if body.xml_content:
        data = body.xml_content.encode("utf-8")
        if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
            raise AppError(422, "DOCTYPE and entities are not allowed")
        return data, None
    doc = files.repo.get(body.file_id)
    if not doc or doc.get("workspace_id") != workspace_id:
        raise AppError(404, "Resource not found")
    if not str(doc.get("original_name", "")).lower().endswith(".xml"):
        raise AppError(422, "File must be XML")
    return files.read_doc(doc), doc


def assert_graphics(db, workspace_id: str, graphic_ids: list[str]) -> None:
    graphics = Graphics(db)
    for graphic_id in graphic_ids:
        graphic = graphics.get(graphic_id)
        if not graphic or graphic.get("workspace_id") != workspace_id:
            raise AppError(404, "Resource not found")


def store_xml(files: FileService, category: str, data: bytes, name: str, workspace_id: str, user_id: str) -> dict:
    return files.save_generated(
        category,
        data,
        "xml",
        name,
        workspace_id,
        user_id,
        "application/xml",
    )
