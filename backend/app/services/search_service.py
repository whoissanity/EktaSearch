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
import time
from dataclasses import dataclass
from typing import AsyncIterator, Optional

from app.adapters import ALL_ADAPTERS
from app.adapters.base import BaseRetailerAdapter
from app.core.cache import cache_get, cache_set, make_cache_key
from app.core.config import get_settings
from app.models.product import ProductResult, SearchResponse
from app.services.index_store import query_index
from app.services.observability import record_adapter
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
    return p.query.strip()


def _normalized_category(p: SearchParams) -> Optional[str]:
    c = (p.category or "").strip().lower()
    if not c:
        return None
    if c != "storage":
        return c
    q = (p.query or "").lower()
    if any(x in q for x in ("hdd", "hard disk", "sata hdd", "7200rpm")):
        return "hdd"
    if any(x in q for x in ("ssd", "nvme", "m.2", "gen4", "gen 4")):
        return "ssd"
    return "ssd"


def _fetch_cache_key(p: SearchParams) -> str:
    eff = _effective_fetch_query(p).lower().strip()
    retailers_key = (p.retailers or "").strip().lower() or "all"
    category_key = _normalized_category(p) or "none"
    return make_cache_key("search_fetch", "v4", eff, retailers_key, category_key)


def _max_pages_for_request(p: SearchParams, settings) -> int:
    # Builder browse mode (category selected, empty text query) should be fast.
    if _normalized_category(p) and not (p.query or "").strip():
        return settings.search_browse_max_retailer_pages
    return settings.search_max_retailer_pages


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
    lo = min_price
    hi = max_price
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    if in_stock_only:
        out = [r for r in out if r.availability]
    if lo is not None:
        out = [r for r in out if r.price >= lo]
    if hi is not None:
        out = [r for r in out if r.price <= hi]
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


_STREAM_TAIL_DONE = object()


async def _safe_search_page(
    adapter_cls: type[BaseRetailerAdapter],
    fetch_query: str,
    category: Optional[str],
    page: int,
    timeout: float,
) -> list[ProductResult]:
    adapter = adapter_cls()
    t0 = time.perf_counter()
    try:
        if category:
            rows = await asyncio.wait_for(
                adapter.search_category_page(category, fetch_query, page),
                timeout=timeout,
            )
        else:
            rows = await asyncio.wait_for(adapter.search_page(fetch_query, page), timeout=timeout)
        record_adapter(adapter_cls.retailer_id, (time.perf_counter() - t0) * 1000.0, True)
        return rows
    except asyncio.TimeoutError:
        logger.warning("[%s] page %s timed out", adapter_cls.shop_name, page)
        record_adapter(adapter_cls.retailer_id, (time.perf_counter() - t0) * 1000.0, False)
        return []
    except Exception as e:
        logger.warning("[%s] page %s failed: %s", adapter_cls.shop_name, page, e)
        record_adapter(adapter_cls.retailer_id, (time.perf_counter() - t0) * 1000.0, False)
        return []


async def _safe_search_one(
    adapter_cls: type[BaseRetailerAdapter],
    fetch_query: str,
    category: Optional[str],
    timeout: float,
) -> list[ProductResult]:
    return await _safe_search_page(adapter_cls, fetch_query, category, 1, timeout)


async def _fetch_shop_all_pages(
    adapter_cls: type[BaseRetailerAdapter],
    fetch_query: str,
    category: Optional[str],
    timeout: float,
    max_pages: int,
) -> list[ProductResult]:
    out: list[ProductResult] = []
    prev_links: set[str] | None = None
    for page in range(1, max_pages + 1):
        rows = await _safe_search_page(adapter_cls, fetch_query, category, page, timeout)
        if not rows:
            break
        links = {r.link for r in rows}
        if prev_links is not None and links <= prev_links:
            break
        prev_links = links
        out.extend(rows)
    return out


async def _fetch_merged_scored(p: SearchParams) -> list[ProductResult]:
    settings = get_settings()
    adapters = _adapters_for_retailers(p.retailers)
    fetch_q = _effective_fetch_query(p)
    timeout = settings.search_shop_timeout_seconds
    max_pages = _max_pages_for_request(p, settings)
    per_shop = await asyncio.gather(
        *[_fetch_shop_all_pages(A, fetch_q, _normalized_category(p), timeout, max_pages) for A in adapters]
    )
    flat: list[ProductResult] = []
    for shop_rows in per_shop:
        flat.extend(shop_rows)
    scored = _score_products(p.query, flat)
    by_link: dict[str, ProductResult] = {}
    for r in scored:
        by_link[r.link] = r
    return list(by_link.values())


async def search_all(p: SearchParams) -> SearchResponse:
    q_display = p.query.strip()
    if q_display:
        indexed = await query_index(q_display, limit=250)
        if indexed:
            results = [
                ProductResult(
                    title=x.title,
                    price=x.price,
                    original_price=None,
                    description=None,
                    link=x.link,
                    image=None,
                    shop_name=x.site,
                    availability=True,
                )
                for x in indexed
            ]
            results = _score_products(q_display, results)
            results = _apply_price_stock_filters(
                results,
                in_stock_only=p.in_stock_only,
                min_price=p.min_price,
                max_price=p.max_price,
            )
            _sort_results(results, p.sort_by)
            logger.info("Search initiated", extra={"query": q_display, "source": "indexed"})
            return SearchResponse(query=q_display, total=len(results), results=results)
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
    NDJSON: {type:'chunk', shop, page?, results}, ... then {type:'done', total, query}.
    Page 1 chunks are emitted as each shop finishes; page 2+ arrive in the background.
    """
    q_display = p.query.strip()
    ck = _fetch_cache_key(p)
    settings = get_settings()
    cached = await cache_get(ck)

    if cached:
        merged = _hydrate_from_cache(cached, q_display)
        line = json.dumps(
            {
                "type": "chunk",
                "shop": "_cache",
                "page": 1,
                "results": [x.model_dump() for x in merged],
            },
            ensure_ascii=False,
        )
        yield (line + "\n").encode("utf-8")
    else:
        adapters = _adapters_for_retailers(p.retailers)
        fetch_q = _effective_fetch_query(p)
        timeout = settings.search_shop_timeout_seconds
        max_pages = _max_pages_for_request(p, settings)
        by_link: dict[str, ProductResult] = {}

        def chunk_line(shop_name: str, page_no: int, scored: list[ProductResult]) -> str:
            for r in scored:
                by_link[r.link] = r
            return json.dumps(
                {
                    "type": "chunk",
                    "shop": shop_name,
                    "page": page_no,
                    "results": [x.model_dump() for x in scored],
                },
                ensure_ascii=False,
            )

        async def page_one(cls: type[BaseRetailerAdapter]) -> tuple[str, int, list[ProductResult]]:
            rows = await _safe_search_page(cls, fetch_q, _normalized_category(p), 1, timeout)
            return cls.shop_name, 1, _score_products(q_display, rows)

        first_tasks = [asyncio.create_task(page_one(A)) for A in adapters]
        for fut in asyncio.as_completed(first_tasks):
            shop_name, page_no, scored = await fut
            yield (chunk_line(shop_name, page_no, scored) + "\n").encode("utf-8")

        q: asyncio.Queue = asyncio.Queue()

        async def tail_pages(cls: type[BaseRetailerAdapter]) -> None:
            prev_links: set[str] | None = None
            page_no = 2
            while page_no <= max_pages:
                rows = await _safe_search_page(cls, fetch_q, _normalized_category(p), page_no, timeout)
                if not rows:
                    break
                links = {r.link for r in rows}
                if prev_links is not None and links <= prev_links:
                    break
                prev_links = links
                scored = _score_products(q_display, rows)
                await q.put((cls.shop_name, page_no, scored))
                page_no += 1
            await q.put(_STREAM_TAIL_DONE)

        tail_tasks = [asyncio.create_task(tail_pages(A)) for A in adapters]
        pending = len(tail_tasks)
        while pending > 0:
            item = await q.get()
            if item is _STREAM_TAIL_DONE:
                pending -= 1
                continue
            shop_name, page_no, scored = item
            yield (chunk_line(shop_name, page_no, scored) + "\n").encode("utf-8")

        await cache_set(ck, [r.model_dump() for r in by_link.values()])

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
