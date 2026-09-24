def ensure_indexes(db) -> None:
    db.users.create_index("email", unique=True)
    db.roles.create_index("name", unique=True)
    db.workspaces.create_index("name", unique=True)
    db.data_modules.create_index([("workspace_id", 1), ("dmc", 1)], unique=True)
    db.data_module_revisions.create_index(
        [("data_module_id", 1), ("revision", 1)], unique=True
    )
    db.graphics.create_index([("workspace_id", 1), ("icn", 1), ("revision", 1)], unique=True)
    db.review_tasks.create_index([("assigned_to", 1), ("status", 1)])
    db.validation_results.create_index([("object_id", 1), ("created_at", 1)])
    db.audit_logs.create_index([("actor_id", 1), ("timestamp", 1)])
    db.audit_logs.create_index(
        [("resource_type", 1), ("resource_id", 1), ("timestamp", 1)]
    )
    db.transformation_jobs.create_index([("status", 1), ("created_at", 1)])
    db.refresh_tokens.create_index("jti", unique=True)
    db.publication_modules.create_index([("workspace_id", 1), ("pm_code", 1)], unique=True)
    db.dmrl.create_index([("workspace_id", 1), ("code", 1)], unique=True)
    db.ddn.create_index([("workspace_id", 1), ("code", 1)], unique=True)
    db.files.create_index("checksum")
