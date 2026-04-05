"""
app/db/models.py
SQLAlchemy ORM table definitions.
- SavedBuild    → user's PC builds (stored as JSON blob)
- CartSession   → guest cart (stored as JSON blob, keyed by session_id)
- ProductCache  → optional: cache scraped product data to DB if Redis is down
"""
import json
from datetime import datetime
from sqlalchemy import String, Text, Float, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class SavedBuild(Base):
    __tablename__ = "saved_builds"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="My Build")
    parts_json: Mapped[str] = mapped_column(Text)          # JSON array of BuildPart
    total_bdt: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "parts": json.loads(self.parts_json),
            "total_bdt": self.total_bdt,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CartSession(Base):
    __tablename__ = "cart_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    items_json: Mapped[str] = mapped_column(Text, default="[]")  # JSON array of CartItem
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "items": json.loads(self.items_json),
        }


class ProductCacheEntry(Base):
    """
    Fallback DB cache for product data — used when Redis is unavailable.
    Key = "retailer:query" or "retailer:product_id"
    """
    __tablename__ = "product_cache"

    cache_key: Mapped[str] = mapped_column(String(256), primary_key=True)
    data_json: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
