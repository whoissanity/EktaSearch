"""
app/main.py  —  FastAPI app factory.
Run with: uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.http import close_http_client, init_http_client
from app.db.database import init_db
from app.routers import search, compare, builder, cart, community
from app.db import models as _db_models  # noqa: F401 — register ORM tables

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_http_client()
    yield
    await close_http_client()


def create_app() -> FastAPI:
    app = FastAPI(
        title="EktaSearch API",
        version="1.0.0",
        docs_url="/api/docs" if settings.debug else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(search.router,  prefix="/api/search",  tags=["Search"])
    app.include_router(compare.router, prefix="/api/compare", tags=["Compare"])
    app.include_router(builder.router, prefix="/api/builder", tags=["Builder"])
    app.include_router(cart.router,       prefix="/api/cart",       tags=["Cart"])
    app.include_router(community.router,  prefix="/api/community",  tags=["Community"])

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "shops": 8}

    return app


app = create_app()
