"""
app/routers/compare.py
GET /api/compare?q=RTX+4070
Same as search but groups results by title so you see all shops side by side.
"""
from fastapi import APIRouter, Query
from collections import defaultdict
from app.services.search_service import search_all

router = APIRouter()


@router.get("")
async def compare(q: str = Query(..., min_length=2)):
    resp = await search_all(q)
    # Group by normalised title
    groups: dict[str, list] = defaultdict(list)
    for r in resp.results:
        key = r.title.lower()[:60]
        groups[key].append(r.model_dump())
    return {"query": q, "groups": list(groups.values())}
