from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import and_, func, select, text

from app.core.config import get_settings
from app.db.database import AsyncSessionLocal
from app.db.models import Product

settings = get_settings()


@dataclass
class ProductSearchRow:
    title: str
    price: float
    link: str
    image: Optional[str]
    site: str
    in_stock: bool


async def query_products(
    query: str,
    *,
    sort_by: str = "relevance",
    in_stock_only: bool = False,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    retailers: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 250,
) -> list[ProductSearchRow]:
    q = (query or "").strip().lower()
    category_filter = (category or "").strip().lower()
    retailer_set = {x.strip().lower() for x in (retailers or "").split(",") if x.strip()}
    is_postgres = "postgresql" in settings.database_url.lower()

    async with AsyncSessionLocal() as db:
        if q and is_postgres and sort_by == "relevance":
            where = []
            if category_filter:
                where.append(func.lower(func.coalesce(Product.category, "")).like(f"%{category_filter}%"))
            if retailer_set:
                where.append(func.lower(func.coalesce(Product.site, "")).in_(retailer_set))
            if in_stock_only:
                where.append(Product.in_stock.is_(True))
            if min_price is not None:
                where.append(Product.price >= int(min_price))
            if max_price is not None:
                where.append(Product.price <= int(max_price))
            rows = await db.execute(
                text(
                    """
                    SELECT id
                    FROM products
                    WHERE to_tsvector('english', coalesce(title, '')) @@ plainto_tsquery('english', :q)
                    ORDER BY ts_rank_cd(to_tsvector('english', coalesce(title, '')), plainto_tsquery('english', :q)) DESC,
                             coalesce(price, 999999999) ASC
                    LIMIT :limit
                    """
                ),
                {"q": q, "limit": limit},
            )
            ids = [r[0] for r in rows.fetchall()]
            if ids:
                stmt = select(Product).where(Product.id.in_(ids))
                if where:
                    stmt = stmt.where(and_(*where))
                products = list((await db.execute(stmt)).scalars().all())
                by_id = {p.id: p for p in products}
                ordered = [by_id[i] for i in ids if i in by_id]
                return [
                    ProductSearchRow(
                        title=p.title,
                        price=float(p.price or 0),
                        link=p.url,
                        image=p.image,
                        site=p.site or "Unknown",
                        in_stock=bool(p.in_stock),
                    )
                    for p in ordered
                ]

        stmt = select(Product)
        if q:
            for tok in [t for t in q.split(" ") if t]:
                stmt = stmt.where(func.lower(Product.title).like(f"%{tok}%"))
        if category_filter:
            stmt = stmt.where(func.lower(func.coalesce(Product.category, "")).like(f"%{category_filter}%"))
        if retailer_set:
            stmt = stmt.where(func.lower(func.coalesce(Product.site, "")).in_(retailer_set))
        if in_stock_only:
            stmt = stmt.where(Product.in_stock.is_(True))
        if min_price is not None:
            stmt = stmt.where(Product.price >= int(min_price))
        if max_price is not None:
            stmt = stmt.where(Product.price <= int(max_price))

        if sort_by == "price_desc":
            stmt = stmt.order_by(Product.in_stock.desc(), Product.price.desc().nullslast())
        elif sort_by == "price_asc":
            stmt = stmt.order_by(Product.in_stock.desc(), Product.price.asc().nullslast())
        else:
            stmt = stmt.order_by(Product.in_stock.desc(), Product.updated_at.desc().nullslast())
        stmt = stmt.limit(limit)

        products = list((await db.execute(stmt)).scalars().all())
        return [
            ProductSearchRow(
                title=p.title,
                price=float(p.price or 0),
                link=p.url,
                image=p.image,
                site=p.site or "Unknown",
                in_stock=bool(p.in_stock),
            )
            for p in products
        ]
