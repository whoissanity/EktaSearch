from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import and_, desc, func, select

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
    limit: int = 20,
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
            qvec = func.plainto_tsquery("english", q)
            tsv = func.to_tsvector("english", func.coalesce(Product.title, ""))
            rank = func.ts_rank(tsv, qvec).label("rank")
            stmt = select(Product, rank).where(tsv.op("@@")(qvec))
            if where:
                stmt = stmt.where(and_(*where))
            stmt = stmt.order_by(desc(rank), Product.price.asc().nullslast()).limit(limit)
            rows = (await db.execute(stmt)).all()
            if rows:
                return [
                    ProductSearchRow(
                        title=p.title,
                        price=float(p.price or 0),
                        link=p.url,
                        image=p.image,
                        site=p.site or "Unknown",
                        in_stock=bool(p.in_stock),
                    )
                    for p, _rank in rows
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
