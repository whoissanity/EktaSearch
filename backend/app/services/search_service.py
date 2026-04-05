"""
app/services/search_service.py
Fans out to all 8 shops in parallel, merges, caches.
Returns list[ProductResult] — the unified JSON shape.
"""
from __future__ import annotations
import asyncio
import logging
from app.adapters import ALL_ADAPTERS
from app.models.product import ProductResult, SearchResponse
from app.core.cache import cache_get, cache_set, make_cache_key

logger = logging.getLogger(__name__)


async def search_all(query: str) -> SearchResponse:
    cache_key = make_cache_key("search", query.lower().strip())
    cached = await cache_get(cache_key)
    if cached:
        return SearchResponse(
            query=query,
            total=len(cached),
            results=[ProductResult(**p) for p in cached],
        )

    tasks = [_safe_search(A(), query) for A in ALL_ADAPTERS]
    per_shop: list[list[ProductResult]] = await asyncio.gather(*tasks)

    results: list[ProductResult] = [r for shop in per_shop for r in shop]

    # Sort: in-stock first, then by price ascending
    results.sort(key=lambda r: (not r.availability, r.price))

    await cache_set(cache_key, [r.model_dump() for r in results])
    return SearchResponse(query=query, total=len(results), results=results)


async def _safe_search(adapter, query: str) -> list[ProductResult]:
    try:
        return await adapter.search(query)
    except Exception as e:
        logger.warning("[%s] search failed: %s", adapter.shop_name, e)
        return []
    finally:
        await adapter.close()
