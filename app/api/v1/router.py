from fastapi import APIRouter

from app.api.v1 import audit, auth, csdb, data_modules, files, graphics, publications, reviews, users, validation, workspaces

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(workspaces.router)
api_router.include_router(files.router)
api_router.include_router(data_modules.router)
api_router.include_router(graphics.router)
api_router.include_router(validation.router)
api_router.include_router(reviews.router)
api_router.include_router(csdb.router)
api_router.include_router(publications.router)
api_router.include_router(audit.router)
