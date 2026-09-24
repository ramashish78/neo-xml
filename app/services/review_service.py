from app.core.access import Access
from app.core.errors import AppError
from app.core.permissions import DM_APPROVED, DM_AUTHOR, DM_REVIEW, DM_VALIDATE
from app.repositories.base import (
    DataModules,
    ReviewComments,
    ReviewTasks,
    Revisions,
    TrackChanges,
    Users,
)
from app.services.audit_service import AuditService


class ReviewService:
    def __init__(self, db):
        self.db = db
        self.tasks = ReviewTasks(db)
        self.comments = ReviewComments(db)
        self.changes = TrackChanges(db)
        self.modules = DataModules(db)
        self.revisions = Revisions(db)
        self.users = Users(db)
        self.access = Access(db)
        self.audit = AuditService(db)

    def create(self, user: dict, body, ip: str) -> dict:
        module = self.modules.get(body.object_id)
        if not module:
            raise AppError(404, "Resource not found")
        self.access.require_workspace(user, module["workspace_id"])
        if module["status"] != DM_VALIDATE:
            raise AppError(409, "Validation must pass before review")
        from app.repositories.base import ValidationResults

        latest = ValidationResults(self.db).latest_for(str(module["_id"]))
        if not latest:
            raise AppError(409, "Validation result is required before review")
        if latest.get("errors"):
            raise AppError(409, "Validation errors must be resolved before review")
        assignee = self.users.get(body.assigned_to)
        if not assignee or not self.access.can_see_workspace(assignee, module["workspace_id"]):
            raise AppError(422, "Assignee cannot access this workspace")
        task = self.tasks.insert(
            {
                "object_id": str(module["_id"]),
                "object_type": "data_module",
                "workspace_id": module["workspace_id"],
                "assigned_to": str(assignee["_id"]),
                "status": "open",
                "due_date": body.due_date,
                "created_by": str(user["_id"]),
            }
        )
        self.modules.update(str(module["_id"]), {"status": DM_REVIEW})
        self.audit.record(str(user["_id"]), "review.create", "review", str(task["_id"]), ip)
        return task

    def get(self, user: dict, review_id: str) -> dict:
        return self._visible(user, review_id)

    def list_tasks(self, user: dict, workspace_id: str | None, object_id: str | None, limit: int, skip: int):
        query: dict = {}
        if workspace_id:
            self.access.require_workspace(user, workspace_id)
            query["workspace_id"] = workspace_id
        elif not self.access.is_super(user):
            query["workspace_id"] = {"$in": [str(item) for item in user.get("workspace_ids") or []]}
        if object_id:
            query["object_id"] = object_id
        if not self._sees_all(user):
            query["$or"] = [{"assigned_to": str(user["_id"])}, {"created_by": str(user["_id"])}]
        return self.tasks.list(query, limit, skip, [("created_at", -1)])

    def comment(self, user: dict, review_id: str, body, ip: str) -> dict:
        task = self._visible(user, review_id)
        doc = self.comments.insert(
            {
                "review_id": review_id,
                "object_id": task["object_id"],
                "author_id": str(user["_id"]),
                "location": body.location,
                "text": body.text,
                "status": "open",
            }
        )
        self.audit.record(str(user["_id"]), "review.comment", "review", review_id, ip)
        return doc

    def list_comments(self, user: dict, review_id: str) -> list:
        self._visible(user, review_id)
        return self.comments.for_review(review_id)

    def decide(self, user: dict, review_id: str, body, ip: str) -> dict:
        task = self._visible(user, review_id)
        if task["status"] != "open":
            raise AppError(409, "Review is already closed")
        if not self._can_decide(user, task):
            raise AppError(404, "Resource not found")
        module = self.modules.get(task["object_id"])
        if not module:
            raise AppError(404, "Resource not found")
        if body.decision == "approve":
            revision = self.revisions.by_number(str(module["_id"]), module["current_revision"])
            self.modules.update(
                str(module["_id"]),
                {"status": DM_APPROVED, "approved_revision": module["current_revision"]},
            )
            self.tasks.update(review_id, {"status": "approved", "decision_by": str(user["_id"])})
            self.audit.record(str(user["_id"]), "review.approve", "data_module", str(module["_id"]), ip)
            if revision is None:
                raise AppError(404, "Resource not found")
        else:
            self.modules.update(str(module["_id"]), {"status": DM_AUTHOR})
            self.tasks.update(review_id, {"status": "changes_requested", "decision_by": str(user["_id"])})
            self.audit.record(str(user["_id"]), "review.changes_requested", "data_module", str(module["_id"]), ip)
        if body.comment:
            self.comments.insert(
                {
                    "review_id": review_id,
                    "object_id": task["object_id"],
                    "author_id": str(user["_id"]),
                    "location": None,
                    "text": body.comment,
                    "status": "open",
                }
            )
        return self.tasks.get(review_id)

    def add_change(self, user: dict, review_id: str, body, ip: str) -> dict:
        task = self._visible(user, review_id)
        revision = self.revisions.get(body.revision_id)
        if not revision or revision.get("data_module_id") != task["object_id"]:
            raise AppError(404, "Resource not found")
        doc = self.changes.insert(
            {
                "review_id": review_id,
                "object_id": task["object_id"],
                "revision_id": body.revision_id,
                "author_id": str(user["_id"]),
                "change_type": body.change_type,
                "location": body.location,
                "original_text": body.original_text,
                "new_text": body.new_text,
                "status": "pending",
            }
        )
        self.audit.record(str(user["_id"]), "review.track_change", "review", review_id, ip)
        return doc

    def list_changes(self, user: dict, review_id: str) -> list:
        self._visible(user, review_id)
        return self.changes.for_review(review_id)

    def set_change_status(self, user: dict, review_id: str, change_id: str, status: str, ip: str) -> dict:
        task = self._visible(user, review_id)
        if not self._can_decide(user, task):
            raise AppError(404, "Resource not found")
        change = self.changes.get(change_id)
        if not change or change.get("review_id") != review_id:
            raise AppError(404, "Resource not found")
        if change.get("status") != "pending":
            raise AppError(409, "Track change is already decided")
        updated = self.changes.update(change_id, {"status": status, "decided_by": str(user["_id"])})
        self.audit.record(str(user["_id"]), f"review.change_{status}", "track_change", change_id, ip)
        return updated

    def _visible(self, user: dict, review_id: str) -> dict:
        task = self.tasks.get(review_id)
        if not task:
            raise AppError(404, "Resource not found")
        self.access.require_workspace(user, task["workspace_id"])
        if self._sees_all(user):
            return task
        user_id = str(user["_id"])
        if task.get("assigned_to") == user_id or task.get("created_by") == user_id:
            return task
        raise AppError(404, "Resource not found")

    def _sees_all(self, user: dict) -> bool:
        return self.access.is_super(user) or "csdb.manage" in self.access.permissions_for(user)

    def _can_decide(self, user: dict, task: dict) -> bool:
        if "review.approve" not in self.access.permissions_for(user):
            return False
        if self._sees_all(user):
            return True
        return task.get("assigned_to") == str(user["_id"])
