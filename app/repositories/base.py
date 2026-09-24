from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError

from app.core.errors import AppError
from app.core.time import utcnow


class MongoRepository:
    collection_name = ""

    def __init__(self, db):
        self.col = db[self.collection_name]

    def _oid(self, id_str: str) -> ObjectId | None:
        try:
            return ObjectId(id_str)
        except (InvalidId, TypeError):
            return None

    def get(self, id_str: str):
        oid = self._oid(id_str)
        if oid is None:
            return None
        return self.col.find_one({"_id": oid})

    def insert(self, doc: dict, duplicate_detail: str = "Duplicate value"):
        now = utcnow()
        doc.setdefault("created_at", now)
        doc["updated_at"] = now
        try:
            doc["_id"] = self.col.insert_one(doc).inserted_id
        except DuplicateKeyError as exc:
            raise AppError(409, duplicate_detail) from exc
        return doc

    def update(self, id_str: str, fields: dict):
        oid = self._oid(id_str)
        if oid is None:
            return None
        fields = dict(fields)
        fields["updated_at"] = utcnow()
        self.col.update_one({"_id": oid}, {"$set": fields})
        return self.col.find_one({"_id": oid})

    def delete(self, id_str: str) -> None:
        oid = self._oid(id_str)
        if oid is not None:
            self.col.delete_one({"_id": oid})

    def list(self, query: dict, limit: int = 50, skip: int = 0, sort=None):
        cursor = self.col.find(query)
        if sort:
            cursor = cursor.sort(sort)
        total = self.col.count_documents(query)
        return list(cursor.skip(skip).limit(limit)), total

    def count(self, query: dict) -> int:
        return self.col.count_documents(query)


class Users(MongoRepository):
    collection_name = "users"

    def by_email(self, email: str):
        return self.col.find_one({"email": email.lower()})


class Roles(MongoRepository):
    collection_name = "roles"

    def by_names(self, names: list[str]) -> list:
        return list(self.col.find({"name": {"$in": names}}))


class Workspaces(MongoRepository):
    collection_name = "workspaces"


class Files(MongoRepository):
    collection_name = "files"


class DataModules(MongoRepository):
    collection_name = "data_modules"

    def by_dmc(self, workspace_id: str, dmc: str):
        return self.col.find_one({"workspace_id": workspace_id, "dmc": dmc})


class Revisions(MongoRepository):
    collection_name = "data_module_revisions"

    def insert(self, doc: dict, duplicate_detail: str = "Duplicate revision"):
        doc["immutable"] = True
        return super().insert(doc, duplicate_detail)

    def update(self, id_str: str, fields: dict):
        raise AppError(409, "Revisions are immutable")

    def for_module(self, data_module_id: str) -> list:
        return list(self.col.find({"data_module_id": data_module_id}).sort("revision", 1))

    def by_number(self, data_module_id: str, revision: int):
        return self.col.find_one({"data_module_id": data_module_id, "revision": revision})

    def delete_for_module(self, data_module_id: str) -> None:
        self.col.delete_many({"data_module_id": data_module_id})


class Graphics(MongoRepository):
    collection_name = "graphics"


class GraphicRevisions(MongoRepository):
    collection_name = "graphic_revisions"

    def update(self, id_str: str, fields: dict):
        raise AppError(409, "Graphic revisions are immutable")


class ValidationResults(MongoRepository):
    collection_name = "validation_results"

    def latest_for(self, object_id: str):
        return self.col.find_one({"object_id": object_id}, sort=[("created_at", -1)])


class ReviewTasks(MongoRepository):
    collection_name = "review_tasks"


class ReviewComments(MongoRepository):
    collection_name = "review_comments"

    def for_review(self, review_id: str) -> list:
        return list(self.col.find({"review_id": review_id}).sort("created_at", 1))


class TrackChanges(MongoRepository):
    collection_name = "track_changes"

    def for_review(self, review_id: str) -> list:
        return list(self.col.find({"review_id": review_id}).sort("created_at", 1))


class AuditLogs(MongoRepository):
    collection_name = "audit_logs"

    def delete(self, id_str: str) -> None:
        raise AppError(409, "Audit logs cannot be deleted")


class RefreshTokens(MongoRepository):
    collection_name = "refresh_tokens"

    def by_jti(self, jti: str):
        return self.col.find_one({"jti": jti})

    def revoke(self, jti: str) -> None:
        self.col.update_one({"jti": jti}, {"$set": {"revoked": True, "updated_at": utcnow()}})

    def revoke_all(self, user_id: str) -> None:
        self.col.update_many(
            {"user_id": user_id, "revoked": False},
            {"$set": {"revoked": True, "updated_at": utcnow()}},
        )


class PublicationModules(MongoRepository):
    collection_name = "publication_modules"


class TransformationJobs(MongoRepository):
    collection_name = "transformation_jobs"


class Dmrl(MongoRepository):
    collection_name = "dmrl"


class Ddn(MongoRepository):
    collection_name = "ddn"
