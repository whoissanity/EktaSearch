"""
app/routers/search.py
GET /api/search?q=rtx+4070
GET /api/search/stream — NDJSON progressive chunks
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.cache import cache_get, cache_set, make_cache_key
from app.core.config import get_settings
from app.db.database import AsyncSessionLocal
from sqlalchemy import text
from app.models.product import SearchResponse
from app.services.search_service import SearchParams, search_all, search_stream

router = APIRouter()
settings = get_settings()

_SORT_CHOICES = frozenset({"relevance", "price_asc", "price_desc"})


def _params(
    q: str,
    sort_by: str,
    in_stock_only: bool,
    min_price: Optional[float],
    max_price: Optional[float],
    retailers: Optional[str],
    category: Optional[str],
) -> SearchParams:
    sb = sort_by if sort_by in _SORT_CHOICES else "relevance"
    return SearchParams(
        query=q,
        sort_by=sb,
        in_stock_only=in_stock_only,
        min_price=min_price,
        max_price=max_price,
        retailers=retailers,
        category=category,
    )


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(""),
    sort_by: str = Query("relevance"),
    in_stock_only: bool = Query(False),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    retailers: Optional[str] = Query(None, description="Comma-separated retailer ids"),
    category: Optional[str] = Query(
        None,
        description="cpu, gpu, motherboard, ram, storage, psu, case, cooler",
    ),
):
    if not q.strip() and not (category or "").strip():
        raise HTTPException(400, "q or category is required")
    return await search_all(
        _params(q, sort_by, in_stock_only, min_price, max_price, retailers, category)
    )


@router.get("/stream")
async def search_ndjson_stream(
    q: str = Query(""),
    sort_by: str = Query("relevance"),
    in_stock_only: bool = Query(False),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    retailers: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    if not q.strip() and not (category or "").strip():
        raise HTTPException(400, "q or category is required")
    p = _params(q, sort_by, in_stock_only, min_price, max_price, retailers, category)
    return StreamingResponse(
        search_stream(p),
        media_type="application/x-ndjson; charset=utf-8",
    )


@router.get("/categories/tree")
async def category_tree():
    key = make_cache_key("categories", "tree", "v1")
    cached = await cache_get(key)
    if isinstance(cached, dict):
        return cached

    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            text(
                """
                SELECT id, site, name, parent_id, url
                FROM categories
                ORDER BY site ASC, parent_id ASC NULLS FIRST, name ASC
                """
            )
        )
        data = rows.fetchall()

    by_id = {}
    for r in data:
        by_id[r[0]] = {
            "id": r[0],
            "site": r[1],
            "name": r[2],
            "parent_id": r[3],
            "url": r[4],
            "children": [],
        }
    roots = []
    for node in by_id.values():
        pid = node["parent_id"]
        if pid and pid in by_id:
            by_id[pid]["children"].append(node)
        else:
            roots.append(node)

    payload = {"total": len(by_id), "roots": roots}
    await cache_set(key, payload, ttl=settings.category_tree_cache_ttl_seconds)
    return payload
