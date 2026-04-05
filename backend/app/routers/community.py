"""
app/routers/community.py
Forum-style posts with topic tags (review, issue, suggestion, general) and optional retailer.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, desc, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import CommunityPost

router = APIRouter()

TOPICS = frozenset({"review", "issue", "suggestion", "general"})
RETAILER_IDS = frozenset(
    {
        "ryans",
        "startech",
        "techland",
        "skyland",
        "vibe",
        "techdiversity",
        "blisstronics",
        "potaka",
    }
)


class CommunityPostCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    body: str = Field(..., min_length=10, max_length=10000)
    topic: str
    retailer_id: Optional[str] = None
    author_name: str = Field(..., min_length=1, max_length=64)

    @field_validator("topic")
    @classmethod
    def topic_ok(cls, v: str) -> str:
        t = v.strip().lower()
        if t not in TOPICS:
            raise ValueError("topic must be review, issue, suggestion, or general")
        return t

    @field_validator("retailer_id")
    @classmethod
    def retailer_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        rid = v.strip().lower()
        if rid not in RETAILER_IDS:
            raise ValueError("invalid retailer_id")
        return rid

    @field_validator("title", "body", "author_name")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip()


class CommunityPostOut(BaseModel):
    id: str
    title: str
    body: str
    topic: str
    retailer_id: Optional[str] = None
    author_name: str
    created_at: Optional[str] = None


class CommunityListResponse(BaseModel):
    posts: list[CommunityPostOut]
    total: int


def _list_conditions(topic: Optional[str], retailer_id: Optional[str]) -> list:
    conditions = []
    if topic:
        t_norm = topic.strip().lower()
        if t_norm not in TOPICS:
            raise HTTPException(400, "invalid topic")
        conditions.append(CommunityPost.topic == t_norm)
    if retailer_id:
        r_norm = retailer_id.strip().lower()
        if r_norm not in RETAILER_IDS:
            raise HTTPException(400, "invalid retailer_id")
        conditions.append(CommunityPost.retailer_id == r_norm)
    return conditions


@router.get("/posts", response_model=CommunityListResponse)
async def list_posts(
    topic: Optional[str] = Query(None, description="review, issue, suggestion, general"),
    retailer_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    conditions = _list_conditions(topic, retailer_id)

    count_q = select(func.count()).select_from(CommunityPost)
    q = select(CommunityPost).order_by(desc(CommunityPost.created_at)).offset(skip).limit(limit)
    if conditions:
        cond = and_(*conditions)
        count_q = count_q.where(cond)
        q = q.where(cond)

    total = int((await db.execute(count_q)).scalar_one())
    rows = (await db.execute(q)).scalars().all()
    posts = [CommunityPostOut(**row.to_dict()) for row in rows]
    return CommunityListResponse(posts=posts, total=total)


@router.post("/posts", response_model=CommunityPostOut)
async def create_post(payload: CommunityPostCreate, db: AsyncSession = Depends(get_db)):
    row = CommunityPost(
        id=str(uuid.uuid4()),
        title=payload.title,
        body=payload.body,
        topic=payload.topic,
        retailer_id=payload.retailer_id,
        author_name=payload.author_name,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return CommunityPostOut(**row.to_dict())


@router.get("/meta")
async def community_meta():
    return {
        "topics": sorted(TOPICS),
        "retailers": sorted(RETAILER_IDS),
    }
