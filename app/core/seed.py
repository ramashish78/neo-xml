import logging

from app.core.config import get_settings
from app.core.permissions import ROLE_DESCRIPTIONS, ROLE_PERMISSIONS
from app.core.security import hash_password
from app.core.time import utcnow

logger = logging.getLogger("neo_xml")


def seed(db) -> None:
    now = utcnow()
    for name, permissions in ROLE_PERMISSIONS.items():
        db.roles.update_one(
            {"name": name},
            {
                "$set": {
                    "permissions": permissions,
                    "description": ROLE_DESCRIPTIONS[name],
                    "system_role": True,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    if db.workspaces.count_documents({}) == 0:
        db.workspaces.insert_one(
            {
                "name": "Default Workspace",
                "status": "active",
                "schema_file_id": None,
                "brex_file_id": None,
                "ste_file_id": None,
                "created_at": now,
                "updated_at": now,
            }
        )

    if db.users.count_documents({}) == 0:
        settings = get_settings()
        workspace = db.workspaces.find_one({"name": "Default Workspace"})
        db.users.insert_one(
            {
                "email": settings.admin_email.lower(),
                "name": settings.admin_name,
                "password_hash": hash_password(settings.admin_password),
                "roles": ["Super Admin"],
                "workspace_ids": [str(workspace["_id"])] if workspace else [],
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
        )
        logger.info("Seeded Super Admin %s", settings.admin_email.lower())
