from __future__ import annotations
import json
from dataclasses import dataclass
from typing import AsyncIterator, Optional

from app.models.product import ProductResult, SearchResponse
from app.services.product_store import query_products
from app.services.relevance import relevance_score



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


def _score_products(user_query: str, items: list[ProductResult]) -> list[ProductResult]:
    uq = user_query.strip()
    return [
        r.model_copy(update={"relevance_score": relevance_score(uq, r.title, r.description)})
        for r in items
    ]


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


async def search_all(p: SearchParams) -> SearchResponse:
    q_display = p.query.strip()
    rows = await query_products(
        q_display,
        sort_by=p.sort_by,
        in_stock_only=p.in_stock_only,
        min_price=p.min_price,
        max_price=p.max_price,
        retailers=p.retailers,
        category=p.category,
    )
    results = [
        ProductResult(
            title=x.title,
            price=x.price,
            original_price=None,
            description=None,
            link=x.link,
            image=x.image,
            shop_name=x.site,
            availability=x.in_stock,
        )
        for x in rows
    ]
    results = _score_products(q_display, results)

    results = _apply_price_stock_filters(
        results,
        in_stock_only=p.in_stock_only,
        min_price=p.min_price,
        max_price=p.max_price,
    )
    _sort_results(results, p.sort_by)

    return SearchResponse(query=q_display, total=len(results), results=results)


async def search_stream(p: SearchParams) -> AsyncIterator[bytes]:
    merged = (await search_all(p)).results
    chunk = json.dumps(
        {"type": "chunk", "shop": "_db", "page": 1, "results": [x.model_dump() for x in merged]},
        ensure_ascii=False,
    )
    yield (chunk + "\n").encode("utf-8")
    done = json.dumps(
        {"type": "done", "total": len(merged), "query": p.query.strip()},
        ensure_ascii=False,
    )
    yield (done + "\n").encode("utf-8")
