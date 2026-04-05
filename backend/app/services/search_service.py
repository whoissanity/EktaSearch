"""
Fans out to retailer adapters in parallel, merges, scores, caches.

Tier C (consistent sub-100ms search): replace the live-scrape hot path with a
background indexer that writes into SQLite FTS / Postgres tsvector / Meilisearch
etc., and serve /api/search from that index; keep adapters as ingestion only.
"""
from __future__ import annotations
import asyncio
import json
import logging
from dataclasses import dataclass
from typing import AsyncIterator, Optional

from app.adapters import ALL_ADAPTERS
from app.adapters.base import BaseRetailerAdapter
from app.core.cache import cache_get, cache_set, make_cache_key
from app.core.config import get_settings
from app.models.product import ProductResult, SearchResponse
from app.services.relevance import relevance_score

logger = logging.getLogger(__name__)

_CATEGORY_SUFFIX: dict[str, str] = {
    "gpu": "graphics card GPU video card",
    "cpu": "processor CPU",
    "motherboard": "motherboard mainboard",
    "ram": "RAM memory DDR",
    "storage": "SSD HDD NVMe storage",
    "psu": "power supply PSU",
    "case": "PC case chassis",
    "cooler": "CPU cooler",
}


@dataclass
class SearchParams:
    """User-facing search; `query` is the original text (used for relevance)."""
    query: str
    sort_by: str = "relevance"
    in_stock_only: bool = False
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    retailers: Optional[str] = None
    category: Optional[str] = None


def _adapters_for_retailers(retailers_csv: Optional[str]) -> list[type[BaseRetailerAdapter]]:
    if not retailers_csv or not retailers_csv.strip():
        return list(ALL_ADAPTERS)
    want = {x.strip().lower() for x in retailers_csv.split(",") if x.strip()}
    sel = [A for A in ALL_ADAPTERS if A.retailer_id.lower() in want]
    return sel if sel else list(ALL_ADAPTERS)


def _effective_fetch_query(p: SearchParams) -> str:
    q = p.query.strip()
    if p.category and p.category.lower() in _CATEGORY_SUFFIX:
        return f"{q} {_CATEGORY_SUFFIX[p.category.lower()]}".strip()
    return q


def _fetch_cache_key(p: SearchParams) -> str:
    eff = _effective_fetch_query(p).lower().strip()
    retailers_key = (p.retailers or "").strip().lower() or "all"
    return make_cache_key("search_fetch", "v2", eff, retailers_key)


def _score_products(user_query: str, items: list[ProductResult]) -> list[ProductResult]:
    uq = user_query.strip()
    return [
        r.model_copy(update={"relevance_score": relevance_score(uq, r.title, r.description)})
        for r in items
    ]


def _hydrate_from_cache(cached: list[dict], user_query: str) -> list[ProductResult]:
    out: list[ProductResult] = []
    for x in cached:
        r = ProductResult(**x)
        if r.relevance_score is None:
            r = r.model_copy(
                update={"relevance_score": relevance_score(user_query, r.title, r.description)}
            )
        out.append(r)
    return out


def _apply_price_stock_filters(
    results: list[ProductResult],
    *,
    in_stock_only: bool,
    min_price: Optional[float],
    max_price: Optional[float],
) -> list[ProductResult]:
    out = results
    if in_stock_only:
        out = [r for r in out if r.availability]
    if min_price is not None:
        out = [r for r in out if r.price >= min_price]
    if max_price is not None:
        out = [r for r in out if r.price <= max_price]
    return out


def _sort_results(results: list[ProductResult], sort_by: str) -> None:
    if sort_by == "price_desc":
        results.sort(key=lambda r: (not r.availability, -r.price))
    elif sort_by == "price_asc":
        results.sort(key=lambda r: (not r.availability, r.price))
    else:
        results.sort(
            key=lambda r: (
                not r.availability,
                -(r.relevance_score or 0.0),
                r.price,
            )
        )


def _cap_lists(
    per_shop: list[list[ProductResult]],
    max_per_shop: int,
    max_total: int,
) -> list[ProductResult]:
    flat: list[ProductResult] = []
    for shop in per_shop:
        flat.extend(shop[:max_per_shop])
    return flat[:max_total]


async def _safe_search_one(
    adapter_cls: type[BaseRetailerAdapter],
    fetch_query: str,
    timeout: float,
) -> list[ProductResult]:
    adapter = adapter_cls()
    try:
        return await asyncio.wait_for(adapter.search(fetch_query), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("[%s] search timed out", adapter_cls.shop_name)
        return []
    except Exception as e:
        logger.warning("[%s] search failed: %s", adapter_cls.shop_name, e)
        return []


async def _fetch_merged_scored(p: SearchParams) -> list[ProductResult]:
    settings = get_settings()
    adapters = _adapters_for_retailers(p.retailers)
    fetch_q = _effective_fetch_query(p)
    timeout = settings.search_shop_timeout_seconds
    tasks = [_safe_search_one(A, fetch_q, timeout) for A in adapters]
    per_shop = await asyncio.gather(*tasks)
    merged = _cap_lists(
        per_shop,
        settings.search_max_per_shop,
        settings.search_max_total,
    )
    return _score_products(p.query, merged)


async def search_all(p: SearchParams) -> SearchResponse:
    q_display = p.query.strip()
    ck = _fetch_cache_key(p)

    cached = await cache_get(ck)
    if cached:
        results = _hydrate_from_cache(cached, q_display)
    else:
        results = await _fetch_merged_scored(p)
        await cache_set(ck, [r.model_dump() for r in results])

    results = _apply_price_stock_filters(
        results,
        in_stock_only=p.in_stock_only,
        min_price=p.min_price,
        max_price=p.max_price,
    )
    _sort_results(results, p.sort_by)

    return SearchResponse(query=q_display, total=len(results), results=results)


async def search_stream(p: SearchParams) -> AsyncIterator[bytes]:
    """
    NDJSON: {type:'chunk', shop, results}, ... then {type:'done', total, query}.
    """
    q_display = p.query.strip()
    ck = _fetch_cache_key(p)
    settings = get_settings()
    max_total = settings.search_max_total
    cached = await cache_get(ck)

    if cached:
        merged = _hydrate_from_cache(cached, q_display)
        line = json.dumps(
            {
                "type": "chunk",
                "shop": "_cache",
                "results": [x.model_dump() for x in merged],
            },
            ensure_ascii=False,
        )
        yield (line + "\n").encode("utf-8")
    else:
        adapters = _adapters_for_retailers(p.retailers)
        fetch_q = _effective_fetch_query(p)
        timeout = settings.search_shop_timeout_seconds
        max_ps = settings.search_max_per_shop

        async def one(cls: type[BaseRetailerAdapter]) -> tuple[str, list[ProductResult]]:
            rows = await _safe_search_one(cls, fetch_q, timeout)
            return cls.shop_name, rows[:max_ps]

        acc: list[ProductResult] = []
        tasks = [asyncio.create_task(one(A)) for A in adapters]
        for fut in asyncio.as_completed(tasks):
            shop_name, rows = await fut
            scored = _score_products(q_display, rows)
            acc.extend(scored)
            line = json.dumps(
                {
                    "type": "chunk",
                    "shop": shop_name,
                    "results": [x.model_dump() for x in scored],
                },
                ensure_ascii=False,
            )
            yield (line + "\n").encode("utf-8")

        acc = acc[:max_total]
        await cache_set(ck, [r.model_dump() for r in acc])

    final_raw = await cache_get(ck) or []
    merged = _hydrate_from_cache(final_raw, q_display)
    merged = _apply_price_stock_filters(
        merged,
        in_stock_only=p.in_stock_only,
        min_price=p.min_price,
        max_price=p.max_price,
    )
    _sort_results(merged, p.sort_by)
    done = json.dumps(
        {"type": "done", "total": len(merged), "query": q_display},
        ensure_ascii=False,
    )
    yield (done + "\n").encode("utf-8")
