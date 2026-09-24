from fastapi import APIRouter, Depends, Query, Request

from app.core.db import get_db
from app.core.deps import require
from app.core.rate_limit import client_ip
from app.core.serialize import page, to_public
from app.schemas.dto import DdnCreate, DmrlCreate, PublicationCreate, PublicationPatch, TransformRequest
from app.services.csdb_service import CsdbService
from app.services.publishing_service import PublishingService

router = APIRouter(tags=["publishing"])


@router.post("/publication-modules", status_code=201)
def create_publication(
    body: PublicationCreate,
    request: Request,
    user=Depends(require("csdb.manage")),
    db=Depends(get_db),
):
    return to_public(PublishingService(db).create_publication(user, body, client_ip(request)))


@router.get("/publication-modules")
def list_publications(
    workspace_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user=Depends(require("dm.read")),
    db=Depends(get_db),
):
    items, total = PublishingService(db).list_publications(user, workspace_id, limit, skip)
    return page(items, total)


@router.get("/publication-modules/{publication_id}")
def get_publication(publication_id: str, user=Depends(require("dm.read")), db=Depends(get_db)):
    return to_public(PublishingService(db).get_publication(user, publication_id))


@router.patch("/publication-modules/{publication_id}")
def patch_publication(
    publication_id: str,
    body: PublicationPatch,
    request: Request,
    user=Depends(require("csdb.manage")),
    db=Depends(get_db),
):
    return to_public(PublishingService(db).patch_publication(user, publication_id, body, client_ip(request)))


@router.post("/transformations/run", status_code=201)
def run_transformation(
    body: TransformRequest,
    request: Request,
    user=Depends(require("publish.run")),
    db=Depends(get_db),
):
    return to_public(PublishingService(db).run(user, body, client_ip(request)))


@router.get("/transformations/{job_id}")
def get_transformation(job_id: str, user=Depends(require("dm.read")), db=Depends(get_db)):
    return to_public(PublishingService(db).get_job(user, job_id))


@router.post("/dmrl", status_code=201)
def create_dmrl(
    body: DmrlCreate,
    request: Request,
    user=Depends(require("csdb.manage")),
    db=Depends(get_db),
):
    return to_public(CsdbService(db).create_dmrl(user, body, client_ip(request)))


@router.get("/dmrl")
def list_dmrl(
    workspace_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user=Depends(require("dm.read")),
    db=Depends(get_db),
):
    items, total = CsdbService(db).list_dmrl(user, workspace_id, limit, skip)
    return page(items, total)


@router.get("/dmrl/{dmrl_id}")
def get_dmrl(dmrl_id: str, user=Depends(require("dm.read")), db=Depends(get_db)):
    return to_public(CsdbService(db).get_dmrl(user, dmrl_id))


@router.post("/ddn", status_code=201)
def create_ddn(
    body: DdnCreate,
    request: Request,
    user=Depends(require("csdb.manage")),
    db=Depends(get_db),
):
    return to_public(CsdbService(db).create_ddn(user, body, client_ip(request)))


@router.get("/ddn")
def list_ddn(
    workspace_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user=Depends(require("dm.read")),
    db=Depends(get_db),
):
    items, total = CsdbService(db).list_ddn(user, workspace_id, limit, skip)
    return page(items, total)


@router.get("/ddn/{ddn_id}")
def get_ddn(ddn_id: str, user=Depends(require("dm.read")), db=Depends(get_db)):
    return to_public(CsdbService(db).get_ddn(user, ddn_id))
