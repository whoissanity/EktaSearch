"""
app/db/models.py
SQLAlchemy ORM table definitions.
- SavedBuild    → user's PC builds (stored as JSON blob)
- CartSession   → guest cart (stored as JSON blob, keyed by session_id)
- ProductCache   → optional: cache scraped product data to DB if Redis is down
- CommunityPost  → forum posts (topic + optional retailer tag)
"""
import json
from datetime import datetime
from sqlalchemy import String, Text, Float, DateTime, Integer, func, ForeignKey, UniqueConstraint, Boolean
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


class AppUser(Base):
    __tablename__ = "app_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    password_salt: Mapped[str] = mapped_column(String(128))
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("app_users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class CommunityPost(Base):
    """
    User-submitted forum-style posts: reviews, issues, suggestions, or general chat.
    Optional retailer_id ties the post to a shop (rant, question about that store).
    """
    __tablename__ = "community_posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(String(32), index=True)
    retailer_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    author_name: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "topic": self.topic,
            "retailer_id": self.retailer_id,
            "author_name": self.author_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CommunityReply(Base):
    __tablename__ = "community_replies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    post_id: Mapped[str] = mapped_column(String(36), ForeignKey("community_posts.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    author_name: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "post_id": self.post_id,
            "body": self.body,
            "author_name": self.author_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CommunityVote(Base):
    __tablename__ = "community_votes"
    __table_args__ = (
        UniqueConstraint("post_id", "actor_key", name="uq_community_vote_actor_post"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[str] = mapped_column(String(36), ForeignKey("community_posts.id"), index=True)
    actor_key: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[int] = mapped_column(Integer)  # 1 like, -1 dislike
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class CommunityContentAuthor(Base):
    __tablename__ = "community_content_authors"
    __table_args__ = (
        UniqueConstraint("content_type", "content_id", name="uq_community_content_author"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_type: Mapped[str] = mapped_column(String(16), index=True)  # post | reply
    content_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("app_users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CommunityAttachment(Base):
    __tablename__ = "community_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    post_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("community_posts.id"), nullable=True, index=True)
    reply_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("community_replies.id"), nullable=True, index=True)
    file_url: Mapped[str] = mapped_column(String(500))
    file_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "post_id": self.post_id,
            "reply_id": self.reply_id,
            "file_url": self.file_url,
            "file_name": self.file_name,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
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


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255))
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    url: Mapped[str] = mapped_column(String(1000), unique=True, index=True)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(600), index=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    currency: Mapped[str] = mapped_column(String(16), default="BDT")
    url: Mapped[str] = mapped_column(String(1000), unique=True, index=True)
    image: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    in_stock: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
