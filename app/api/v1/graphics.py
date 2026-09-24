from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile

from app.core.db import get_db
from app.core.deps import require
from app.core.rate_limit import client_ip
from app.core.serialize import page, to_public
from app.services.graphic_service import GraphicService

router = APIRouter(prefix="/graphics", tags=["graphics"])


@router.get("")
def list_graphics(
    workspace_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user=Depends(require("dm.read")),
    db=Depends(get_db),
):
    items, total = GraphicService(db).list_graphics(user, workspace_id, limit, skip)
    return page(items, total)


@router.post("", status_code=201)
def create_graphic(
    request: Request,
    workspace_id: str = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
    icn: str | None = Form(default=None),
    applicability: str | None = Form(default=None),
    user=Depends(require("graphic.upload")),
    db=Depends(get_db),
):
    graphic = GraphicService(db).create(user, workspace_id, title, applicability, icn, file, client_ip(request))
    return to_public(graphic)


@router.post("/{graphic_id}/revisions", status_code=201)
def revise_graphic(
    graphic_id: str,
    request: Request,
    file: UploadFile = File(...),
    user=Depends(require("graphic.upload")),
    db=Depends(get_db),
):
    return to_public(GraphicService(db).revise(user, graphic_id, file, client_ip(request)))
