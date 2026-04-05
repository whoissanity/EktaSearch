"""
app/main.py  —  FastAPI app factory.
Run with: uvicorn app.main:app --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.routers import search, compare, builder, cart
from app.db.database import init_db

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title="PC Bangladesh API",
        version="1.0.0",
        docs_url="/api/docs" if settings.debug else None,
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
    app.include_router(cart.router,    prefix="/api/cart",    tags=["Cart"])

    @app.on_event("startup")
    async def startup():
        await init_db()

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "shops": 8}

    return app


app = create_app()
