from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import admin, auth, dashboard, documents, gis, search, simulation, workspaces
from app.core.config import get_settings
from app.core.db import engine
from app.core.errors import install_error_handlers
from app.core.middleware import SecurityHeadersMiddleware


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title=s.app_name, version="1.0.0", docs_url="/docs" if not s.is_production else None, redoc_url=None)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in s.cors_origins.split(",") if o.strip()],
                       allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"])
    install_error_handlers(app)

    v1 = APIRouter(prefix="/api/v1")
    for r in (auth.router, search.router, documents.router, gis.router, simulation.router, workspaces.router, admin.router, dashboard.router):
        v1.include_router(r)

    @v1.get("/health", tags=["meta"])
    def health():
        try:
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            db_ok = True
        except Exception:  # noqa: BLE001
            db_ok = False
        return {"status": "ok" if db_ok else "degraded", "database": db_ok, "version": app.version,
                "providers": {"llm": s.llm_provider, "embedding": s.embedding_provider, "search": s.search_backend}}

    app.include_router(v1)
    return app


app = create_app()
