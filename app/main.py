import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.db import get_client, get_db
from app.core.errors import register_handlers
from app.core.indexes import ensure_indexes
from app.core.seed import seed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("neo_xml")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db = get_db()
    ensure_indexes(db)
    seed(db)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Neo XML", version="1.0.0", lifespan=lifespan, debug=False)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_handlers(app)
    app.include_router(api_router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        try:
            get_client().admin.command("ping")
            return {"status": "ok"}
        except Exception:
            logger.warning("Readiness check failed")
            return JSONResponse(status_code=503, content={"status": "unavailable"})

    if settings.environment == "test":

        @app.get("/__boom")
        def boom():
            raise RuntimeError("secret stack token=abc")

    return app


app = create_app()
