"""
app/main.py  —  FastAPI app factory.
Run with: uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
import logging
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.http import close_http_client, init_http_client
from app.db.database import init_db
from app.routers import search, compare, builder, cart, community, auth, prewarm, ops
from app.db import models as _db_models  # noqa: F401 — register ORM tables
from app.services.prewarm_bot import discover_and_scrape_once, run_prewarm_forever
from app.services.index_store import rebuild_from_snapshot

settings = get_settings()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger(__name__)
_rl_window = defaultdict(deque)


@asynccontextmanager
async def lifespan(app: FastAPI):
    prewarm_task = None
    startup_scrape_task = None
    await init_db()
    await init_http_client()

    async def _startup_scrape_job() -> None:
        t0 = time.perf_counter()
        logger.info("[startup-scrape] begin scraping all shops")
        try:
            snapshot = await discover_and_scrape_once()
            indexed_count = await rebuild_from_snapshot(snapshot)
            elapsed = int((time.perf_counter() - t0) * 1000)
            logger.info("[startup-scrape] done indexed=%s elapsed_ms=%s", indexed_count, elapsed)
        except Exception:
            logger.exception("[startup-scrape] failed")

    startup_scrape_task = asyncio.create_task(_startup_scrape_job())
    if settings.prewarm_enabled:
        # Avoid duplicate immediate scrape; startup job already performs first full cycle.
        prewarm_task = asyncio.create_task(
            run_prewarm_forever(settings.prewarm_interval_seconds, run_immediately=False)
        )
    yield
    if prewarm_task is not None:
        prewarm_task.cancel()
    if startup_scrape_task is not None and not startup_scrape_task.done():
        startup_scrape_task.cancel()
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

    @app.middleware("http")
    async def ip_rate_limiter(request: Request, call_next):
        # 50 requests / 10s per IP for search endpoints.
        if request.url.path.startswith("/api/search"):
            now = time.time()
            ip = request.client.host if request.client else "unknown"
            q = _rl_window[ip]
            while q and q[0] < now - 10.0:
                q.popleft()
            if len(q) >= 50:
                return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})
            q.append(now)
        return await call_next(request)

    app.include_router(search.router,  prefix="/api/search",  tags=["Search"])
    app.include_router(compare.router, prefix="/api/compare", tags=["Compare"])
    app.include_router(builder.router, prefix="/api/builder", tags=["Builder"])
    app.include_router(cart.router,       prefix="/api/cart",       tags=["Cart"])
    app.include_router(community.router,  prefix="/api/community",  tags=["Community"])
    app.include_router(auth.router,       prefix="/api/auth",       tags=["Auth"])
    app.include_router(prewarm.router,    prefix="/api/prewarm",    tags=["Prewarm"])
    app.include_router(ops.router,        prefix="/api/ops",        tags=["Ops"])
    app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "shops": 8}

    return app


app = create_app()
