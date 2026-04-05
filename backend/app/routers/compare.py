"""
app/routers/compare.py
GET /api/compare?q=RTX+4070
Same as search but groups results by title so you see all shops side by side.
"""
from typing import Optional

from fastapi import APIRouter, Query
from collections import defaultdict

from app.services.search_service import SearchParams, search_all

router = APIRouter()

_SORT_CHOICES = frozenset({"relevance", "price_asc", "price_desc"})


@router.get("")
async def compare(
    q: str = Query(..., min_length=2),
    sort_by: str = Query("relevance"),
    in_stock_only: bool = Query(False),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    retailers: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    sb = sort_by if sort_by in _SORT_CHOICES else "relevance"
    p = SearchParams(
        query=q,
        sort_by=sb,
        in_stock_only=in_stock_only,
        min_price=min_price,
        max_price=max_price,
        retailers=retailers,
        category=category,
    )
    resp = await search_all(p)
    groups: dict[str, list] = defaultdict(list)
    for r in resp.results:
        key = r.title.lower()[:60]
        groups[key].append(r.model_dump())
    return {"query": q, "groups": list(groups.values())}
