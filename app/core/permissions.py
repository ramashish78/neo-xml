ALL_PERMISSIONS = [
    "user.read",
    "user.manage",
    "role.manage",
    "dm.read",
    "dm.create",
    "dm.update",
    "dm.delete",
    "dm.revise",
    "graphic.upload",
    "validation.run",
    "review.create",
    "review.comment",
    "review.approve",
    "publish.run",
    "csdb.manage",
    "audit.read",
]

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "Super Admin": list(ALL_PERMISSIONS),
    "CSDB Admin": [item for item in ALL_PERMISSIONS if item not in {"user.manage", "role.manage"}],
    "Author": [
        "dm.read",
        "dm.create",
        "dm.update",
        "dm.revise",
        "graphic.upload",
        "validation.run",
        "review.create",
        "review.comment",
    ],
    "Reviewer": ["dm.read", "validation.run", "review.comment", "review.approve"],
    "Publisher": ["dm.read", "validation.run", "publish.run"],
    "Viewer": ["dm.read"],
}

ROLE_DESCRIPTIONS = {
    "Super Admin": "All permissions, all workspaces",
    "CSDB Admin": "CSDB and content administration for assigned workspaces",
    "Author": "Create and edit data modules and graphics",
    "Reviewer": "Review, comment, and approve assigned content",
    "Publisher": "Run transformations and publish approved content",
    "Viewer": "Read-only access to CSDB content",
}

UPLOAD_CATEGORIES = {
    "data_modules",
    "revisions",
    "graphics",
    "schemas",
    "brex",
    "templates",
    "transformations",
    "output",
    "tmp",
}

CATEGORY_PERMISSION = {
    "data_modules": "dm.update",
    "revisions": "dm.update",
    "graphics": "graphic.upload",
    "schemas": "csdb.manage",
    "brex": "csdb.manage",
    "templates": "csdb.manage",
    "transformations": "csdb.manage",
    "output": "publish.run",
    "tmp": "dm.update",
}

DM_DRAFT = "draft"
DM_AUTHOR = "author"
DM_VALIDATE = "validate"
DM_REVIEW = "review"
DM_APPROVED = "approved"
DM_PUBLISH = "publish"
DM_PUBLISHED = "published"
FROZEN_STATUSES = {DM_APPROVED, DM_PUBLISH, DM_PUBLISHED}
