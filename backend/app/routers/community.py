"""Community threads, votes, replies, and attachments."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import OWNER_EMAIL, get_current_user_optional
from app.db.database import get_db
from app.db.models import (
    AppUser,
    CommunityAttachment,
    CommunityContentAuthor,
    CommunityPost,
    CommunityReply,
    CommunityVote,
)

router = APIRouter()
UPLOADS_COMMUNITY_DIR = Path(__file__).resolve().parents[2] / "uploads" / "community"

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
    author_name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    attachment_ids: list[str] = []

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

    @field_validator("title", "body")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip()


class AttachmentOut(BaseModel):
    id: str
    file_url: str
    file_name: str
    mime_type: str
    size_bytes: int


class CommunityPostOut(BaseModel):
    id: str
    title: str
    body: str
    topic: str
    retailer_id: Optional[str] = None
    author_name: str
    created_at: Optional[str] = None
    likes: int = 0
    dislikes: int = 0
    score: int = 0
    replies_count: int = 0
    user_vote: int = 0
    replies: list["CommunityReplyOut"] = []
    is_owner: bool = False
    attachments: list[AttachmentOut] = []


class CommunityReplyCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=3000)
    author_name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    attachment_ids: list[str] = []

    @field_validator("body")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip()


class CommunityReplyOut(BaseModel):
    id: str
    post_id: str
    body: str
    author_name: str
    created_at: Optional[str] = None
    is_owner: bool = False
    attachments: list[AttachmentOut] = []


class CommunityVoteIn(BaseModel):
    value: int = Field(..., description="1 for like, -1 for dislike, 0 to clear")

    @field_validator("value")
    @classmethod
    def value_ok(cls, v: int) -> int:
        if v not in (-1, 0, 1):
            raise ValueError("value must be -1, 0, or 1")
        return v


class CommunityListResponse(BaseModel):
    posts: list[CommunityPostOut]
    total: int


def _actor_key(request: Request) -> str:
    sid = (request.headers.get("x-session-id") or "").strip()
    if sid:
        return f"sid:{sid[:120]}"
    ip = request.client.host if request.client else "anon"
    ua = (request.headers.get("user-agent") or "")[:80]
    return f"ipua:{ip}:{ua}"


async def _replies_map(db: AsyncSession, post_ids: list[str]) -> dict[str, list[CommunityReplyOut]]:
    if not post_ids:
        return {}
    q = (
        select(CommunityReply)
        .where(CommunityReply.post_id.in_(post_ids))
        .order_by(CommunityReply.created_at.asc())
    )
    rows = (await db.execute(q)).scalars().all()
    attachments_by_reply = await _attachments_map(db, reply_ids=[r.id for r in rows])
    owner_by_reply = await _owner_flags_for_content(db, "reply", [r.id for r in rows])
    out: dict[str, list[CommunityReplyOut]] = {pid: [] for pid in post_ids}
    for r in rows:
        out.setdefault(r.post_id, []).append(
            CommunityReplyOut(
                **r.to_dict(),
                is_owner=owner_by_reply.get(r.id, False),
                attachments=attachments_by_reply.get(r.id, []),
            )
        )
    return out


async def _vote_stats_map(
    db: AsyncSession, post_ids: list[str], actor_key: str
) -> dict[str, dict[str, int]]:
    if not post_ids:
        return {}
    stats_q = (
        select(
            CommunityVote.post_id,
            func.sum(case((CommunityVote.value == 1, 1), else_=0)).label("likes"),
            func.sum(case((CommunityVote.value == -1, 1), else_=0)).label("dislikes"),
        )
        .where(CommunityVote.post_id.in_(post_ids))
        .group_by(CommunityVote.post_id)
    )
    user_q = (
        select(CommunityVote.post_id, CommunityVote.value)
        .where(CommunityVote.post_id.in_(post_ids), CommunityVote.actor_key == actor_key)
    )
    stats_rows = (await db.execute(stats_q)).all()
    user_rows = (await db.execute(user_q)).all()
    out: dict[str, dict[str, int]] = {
        pid: {"likes": 0, "dislikes": 0, "score": 0, "user_vote": 0} for pid in post_ids
    }
    for post_id, likes, dislikes in stats_rows:
        l = int(likes or 0)
        d = int(dislikes or 0)
        out[post_id] = {"likes": l, "dislikes": d, "score": l - d, "user_vote": 0}
    for post_id, value in user_rows:
        out.setdefault(post_id, {"likes": 0, "dislikes": 0, "score": 0, "user_vote": 0})
        out[post_id]["user_vote"] = int(value or 0)
    return out


async def _owner_flags_for_content(
    db: AsyncSession,
    content_type: str,
    content_ids: list[str],
) -> dict[str, bool]:
    if not content_ids:
        return {}
    q = (
        select(CommunityContentAuthor.content_id, AppUser.email)
        .join(AppUser, CommunityContentAuthor.user_id == AppUser.id)
        .where(
            CommunityContentAuthor.content_type == content_type,
            CommunityContentAuthor.content_id.in_(content_ids),
        )
    )
    rows = (await db.execute(q)).all()
    out = {cid: False for cid in content_ids}
    for cid, email in rows:
        out[cid] = (str(email).lower() == OWNER_EMAIL)
    return out


async def _attachments_map(
    db: AsyncSession,
    post_ids: Optional[list[str]] = None,
    reply_ids: Optional[list[str]] = None,
) -> dict[str, list[AttachmentOut]]:
    post_ids = post_ids or []
    reply_ids = reply_ids or []
    if not post_ids and not reply_ids:
        return {}
    q = select(CommunityAttachment)
    if post_ids and reply_ids:
        q = q.where(
            (CommunityAttachment.post_id.in_(post_ids)) | (CommunityAttachment.reply_id.in_(reply_ids))
        )
    elif post_ids:
        q = q.where(CommunityAttachment.post_id.in_(post_ids))
    else:
        q = q.where(CommunityAttachment.reply_id.in_(reply_ids))
    rows = (await db.execute(q.order_by(CommunityAttachment.created_at.asc()))).scalars().all()
    out: dict[str, list[AttachmentOut]] = {}
    for r in rows:
        key = r.post_id or r.reply_id
        if not key:
            continue
        out.setdefault(key, []).append(
            AttachmentOut(
                id=r.id,
                file_url=r.file_url,
                file_name=r.file_name,
                mime_type=r.mime_type,
                size_bytes=r.size_bytes,
            )
        )
    return out


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
    request: Request = None,
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
    post_ids = [r.id for r in rows]
    actor = _actor_key(request)
    replies_by_post = await _replies_map(db, post_ids)
    votes_by_post = await _vote_stats_map(db, post_ids, actor)
    owner_by_post = await _owner_flags_for_content(db, "post", post_ids)
    attachments_by_post = await _attachments_map(db, post_ids=post_ids)
    posts: list[CommunityPostOut] = []
    for row in rows:
        base = row.to_dict()
        votes = votes_by_post.get(row.id, {"likes": 0, "dislikes": 0, "score": 0, "user_vote": 0})
        replies = replies_by_post.get(row.id, [])
        posts.append(
            CommunityPostOut(
                **base,
                likes=votes["likes"],
                dislikes=votes["dislikes"],
                score=votes["score"],
                user_vote=votes["user_vote"],
                replies_count=len(replies),
                replies=replies,
                is_owner=owner_by_post.get(row.id, False),
                attachments=attachments_by_post.get(row.id, []),
            )
        )
    return CommunityListResponse(posts=posts, total=total)


@router.post("/posts", response_model=CommunityPostOut)
async def create_post(
    payload: CommunityPostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AppUser] = Depends(get_current_user_optional),
):
    author_name = (current_user.username if current_user else (payload.author_name or "")).strip()
    if not author_name:
        raise HTTPException(400, "author_name is required when not logged in")
    row = CommunityPost(
        id=str(uuid.uuid4()),
        title=payload.title,
        body=payload.body,
        topic=payload.topic,
        retailer_id=payload.retailer_id,
        author_name=author_name,
    )
    db.add(row)
    if current_user is not None:
        db.add(
            CommunityContentAuthor(content_type="post", content_id=row.id, user_id=current_user.id)
        )
    if payload.attachment_ids:
        att_rows = (
            await db.execute(
                select(CommunityAttachment).where(
                    CommunityAttachment.id.in_(payload.attachment_ids),
                    CommunityAttachment.post_id.is_(None),
                    CommunityAttachment.reply_id.is_(None),
                )
            )
        ).scalars().all()
        for a in att_rows:
            a.post_id = row.id
    await db.commit()
    await db.refresh(row)
    is_owner = bool(current_user and current_user.email.lower() == OWNER_EMAIL)
    attachments = await _attachments_map(db, post_ids=[row.id])
    return CommunityPostOut(**row.to_dict(), replies=[], is_owner=is_owner, attachments=attachments.get(row.id, []))


@router.post("/posts/{post_id}/replies", response_model=CommunityReplyOut)
async def create_reply(
    post_id: str,
    payload: CommunityReplyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AppUser] = Depends(get_current_user_optional),
):
    exists = await db.get(CommunityPost, post_id)
    if not exists:
        raise HTTPException(404, "post not found")
    author_name = (current_user.username if current_user else (payload.author_name or "")).strip()
    if not author_name:
        raise HTTPException(400, "author_name is required when not logged in")
    row = CommunityReply(
        id=str(uuid.uuid4()),
        post_id=post_id,
        body=payload.body,
        author_name=author_name,
    )
    db.add(row)
    if current_user is not None:
        db.add(
            CommunityContentAuthor(content_type="reply", content_id=row.id, user_id=current_user.id)
        )
    if payload.attachment_ids:
        att_rows = (
            await db.execute(
                select(CommunityAttachment).where(
                    CommunityAttachment.id.in_(payload.attachment_ids),
                    CommunityAttachment.post_id.is_(None),
                    CommunityAttachment.reply_id.is_(None),
                )
            )
        ).scalars().all()
        for a in att_rows:
            a.reply_id = row.id
    await db.commit()
    await db.refresh(row)
    is_owner = bool(current_user and current_user.email.lower() == OWNER_EMAIL)
    attachments = await _attachments_map(db, reply_ids=[row.id])
    return CommunityReplyOut(**row.to_dict(), is_owner=is_owner, attachments=attachments.get(row.id, []))


@router.post("/posts/{post_id}/vote")
async def vote_post(
    post_id: str,
    payload: CommunityVoteIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    exists = await db.get(CommunityPost, post_id)
    if not exists:
        raise HTTPException(404, "post not found")
    actor = _actor_key(request)
    current = (
        await db.execute(
            select(CommunityVote).where(
                CommunityVote.post_id == post_id,
                CommunityVote.actor_key == actor,
            )
        )
    ).scalar_one_or_none()
    if payload.value == 0:
        if current is not None:
            await db.delete(current)
    else:
        if current is None:
            db.add(CommunityVote(post_id=post_id, actor_key=actor, value=payload.value))
        else:
            current.value = payload.value
    await db.commit()

    stats = await _vote_stats_map(db, [post_id], actor)
    s = stats.get(post_id, {"likes": 0, "dislikes": 0, "score": 0, "user_vote": 0})
    return {
        "post_id": post_id,
        "likes": s["likes"],
        "dislikes": s["dislikes"],
        "score": s["score"],
        "user_vote": s["user_vote"],
    }


@router.post("/attachments")
async def upload_attachments(
    request: Request,
    db: AsyncSession = Depends(get_db),
    files: list[UploadFile] = File(...),
):
    UPLOADS_COMMUNITY_DIR.mkdir(parents=True, exist_ok=True)
    out: list[dict] = []
    for f in files[:5]:
        content = await f.read()
        if len(content) > 8 * 1024 * 1024:
            raise HTTPException(400, f"{f.filename} is too large (max 8MB)")
        ext = Path(f.filename or "").suffix
        fid = str(uuid.uuid4())
        filename = f"{fid}{ext}"
        path = UPLOADS_COMMUNITY_DIR / filename
        path.write_bytes(content)
        url = str(request.base_url).rstrip("/") + f"/uploads/community/{filename}"
        out.append(
            {
                "id": fid,
                "file_url": url,
                "file_name": f.filename or filename,
                "mime_type": f.content_type or "application/octet-stream",
                "size_bytes": len(content),
            }
        )
        db.add(
            CommunityAttachment(
                id=fid,
                post_id=None,
                reply_id=None,
                file_url=url,
                file_name=f.filename or filename,
                mime_type=f.content_type or "application/octet-stream",
                size_bytes=len(content),
            )
        )
    await db.commit()
    return {"files": out}


@router.get("/meta")
async def community_meta():
    return {
        "topics": sorted(TOPICS),
        "retailers": sorted(RETAILER_IDS),
    }
