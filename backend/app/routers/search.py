"""
app/routers/search.py
GET /api/search?q=rtx+4070
Returns SearchResponse with list of ProductResult (the unified JSON shape).
"""
from fastapi import APIRouter, Query
from app.models.product import SearchResponse
from app.services.search_service import search_all

router = APIRouter()


@router.get("", response_model=SearchResponse)
async def search(q: str = Query(..., min_length=2)):
    return await search_all(q)
