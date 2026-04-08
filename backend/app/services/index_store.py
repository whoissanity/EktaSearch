from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import delete, select, text

from app.db.database import AsyncSessionLocal
from app.db.models import IndexedProduct


async def rebuild_from_snapshot(snapshot: dict) -> int:
    rows = []
    now = datetime.now(timezone.utc)
    for site, payload in snapshot.get("sites", {}).items():
        for p in payload.get("products", []):
            rows.append(
                IndexedProduct(
                    site=site,
                    category_url="",
                    title=p.get("title", "")[:600],
                    title_lc=p.get("title", "").lower()[:600],
                    price=float(p.get("price", 0) or 0),
                    link=p.get("link", "")[:800],
                    scraped_at=now,
                )
            )
    async with AsyncSessionLocal() as db:
        await db.execute(delete(IndexedProduct))
        db.add_all(rows)
        await db.commit()
        # Build SQLite FTS5 shadow index (safe no-op on non-SQLite engines).
        try:
            await db.execute(
                text(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS indexed_products_fts
                    USING fts5(title, link UNINDEXED, site UNINDEXED, content='');
                    """
                )
            )
            await db.execute(text("DELETE FROM indexed_products_fts;"))
            await db.execute(
                text(
                    """
                    INSERT INTO indexed_products_fts(title, link, site)
                    SELECT title, link, site FROM indexed_products;
                    """
                )
            )
            await db.commit()
        except Exception:
            # Postgres/non-FTS5 path will use tsvector query fallback.
            pass
    return len(rows)


async def query_index(query: str, limit: int = 200) -> list[IndexedProduct]:
    q = (query or "").strip().lower()
    async with AsyncSessionLocal() as db:
        dialect = db.bind.dialect.name if db.bind is not None else ""
        if q and dialect == "sqlite":
            try:
                rows = await db.execute(
                    text(
                        """
                        SELECT p.id
                        FROM indexed_products_fts f
                        JOIN indexed_products p ON p.link = f.link
                        WHERE f MATCH :q
                        ORDER BY bm25(f), p.price ASC
                        LIMIT :limit
                        """
                    ),
                    {"q": q, "limit": limit},
                )
                ids = [r[0] for r in rows.fetchall()]
                if ids:
                    res = await db.execute(select(IndexedProduct).where(IndexedProduct.id.in_(ids)))
                    by_id = {x.id: x for x in res.scalars().all()}
                    return [by_id[i] for i in ids if i in by_id]
                return []
            except Exception:
                # fallback to LIKE path if query syntax is incompatible with MATCH
                pass

        if q and dialect in {"postgresql", "postgres"}:
            rows = await db.execute(
                text(
                    """
                    SELECT id
                    FROM indexed_products
                    WHERE to_tsvector('simple', coalesce(title, '')) @@ plainto_tsquery('simple', :q)
                    ORDER BY ts_rank_cd(to_tsvector('simple', coalesce(title, '')), plainto_tsquery('simple', :q)) DESC, price ASC
                    LIMIT :limit
                    """
                ),
                {"q": q, "limit": limit},
            )
            ids = [r[0] for r in rows.fetchall()]
            if ids:
                res = await db.execute(select(IndexedProduct).where(IndexedProduct.id.in_(ids)))
                by_id = {x.id: x for x in res.scalars().all()}
                return [by_id[i] for i in ids if i in by_id]
            return []

        stmt = select(IndexedProduct)
        if q:
            for tok in [t for t in q.split(" ") if t]:
                stmt = stmt.where(IndexedProduct.title_lc.like(f"%{tok}%"))
        stmt = stmt.order_by(IndexedProduct.price.asc()).limit(limit)
        return list((await db.execute(stmt)).scalars().all())
