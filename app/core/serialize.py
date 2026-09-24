from datetime import datetime, timezone

from bson import ObjectId


def to_public(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key in {"password_hash"} or (key.startswith("_") and key != "_id"):
                continue
            if key == "_id":
                out["id"] = str(item)
            else:
                out[key] = to_public(item)
        return out
    if isinstance(value, list):
        return [to_public(item) for item in value]
    if isinstance(value, set):
        return sorted(to_public(item) for item in value)
    return value


def page(items: list, total: int) -> dict:
    return {"items": [to_public(item) for item in items], "total": total}
