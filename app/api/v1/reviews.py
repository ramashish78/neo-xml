from fastapi import APIRouter, Depends, Query, Request

from app.core.db import get_db
from app.core.deps import require
from app.core.rate_limit import client_ip
from app.core.serialize import page, to_public
from app.schemas.dto import CommentCreate, ReviewCreate, ReviewDecision, TrackChangeCreate
from app.services.review_service import ReviewService

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("")
def list_reviews(
    workspace_id: str | None = None,
    object_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user=Depends(require("dm.read")),
    db=Depends(get_db),
):
    items, total = ReviewService(db).list_tasks(user, workspace_id, object_id, limit, skip)
    return page(items, total)


@router.post("", status_code=201)
def create_review(
    body: ReviewCreate,
    request: Request,
    user=Depends(require("review.create")),
    db=Depends(get_db),
):
    return to_public(ReviewService(db).create(user, body, client_ip(request)))


@router.get("/{review_id}")
def get_review(review_id: str, user=Depends(require("dm.read")), db=Depends(get_db)):
    return to_public(ReviewService(db).get(user, review_id))


@router.post("/{review_id}/comments", status_code=201)
def add_comment(
    review_id: str,
    body: CommentCreate,
    request: Request,
    user=Depends(require("review.comment")),
    db=Depends(get_db),
):
    return to_public(ReviewService(db).comment(user, review_id, body, client_ip(request)))


@router.post("/{review_id}/decision")
def decide(
    review_id: str,
    body: ReviewDecision,
    request: Request,
    user=Depends(require("review.approve")),
    db=Depends(get_db),
):
    return to_public(ReviewService(db).decide(user, review_id, body, client_ip(request)))


@router.get("/{review_id}/changes")
def list_changes(review_id: str, user=Depends(require("dm.read")), db=Depends(get_db)):
    return [to_public(item) for item in ReviewService(db).list_changes(user, review_id)]


@router.post("/{review_id}/changes", status_code=201)
def add_change(
    review_id: str,
    body: TrackChangeCreate,
    request: Request,
    user=Depends(require("review.comment")),
    db=Depends(get_db),
):
    return to_public(ReviewService(db).add_change(user, review_id, body, client_ip(request)))


@router.post("/{review_id}/changes/{change_id}/accept")
def accept_change(
    review_id: str,
    change_id: str,
    request: Request,
    user=Depends(require("review.approve")),
    db=Depends(get_db),
):
    return to_public(ReviewService(db).set_change_status(user, review_id, change_id, "accepted", client_ip(request)))


@router.post("/{review_id}/changes/{change_id}/reject")
def reject_change(
    review_id: str,
    change_id: str,
    request: Request,
    user=Depends(require("review.approve")),
    db=Depends(get_db),
):
    return to_public(ReviewService(db).set_change_status(user, review_id, change_id, "rejected", client_ip(request)))
