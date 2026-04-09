"""
app/db/database.py
SQLAlchemy async setup. Works with SQLite locally and Postgres in production.
Just change DATABASE_URL in .env — zero code changes needed.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from app.core.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=settings.sql_echo)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Postgres-only full text index for products.title
        if conn.dialect.name in {"postgresql", "postgres"}:
            await conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_products_search
                    ON products USING GIN(to_tsvector('english', title));
                    """
                )
            )
