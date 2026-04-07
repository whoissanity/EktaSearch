from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import OWNER_EMAIL, hash_password, make_session_expiry, make_token, verify_password
from app.db.database import get_db
from app.db.models import AppUser, AuthSession

router = APIRouter()


class RegisterIn(BaseModel):
    email: str
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=200)

    @field_validator("username")
    @classmethod
    def username_clean(cls, v: str) -> str:
        return v.strip()

    @field_validator("email")
    @classmethod
    def email_ok(cls, v: str) -> str:
        vv = v.strip().lower()
        if "@" not in vv or "." not in vv.split("@")[-1]:
            raise ValueError("invalid email")
        return vv


class LoginIn(BaseModel):
    email: str
    password: str = Field(..., min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def email_ok(cls, v: str) -> str:
        return v.strip().lower()


class UserOut(BaseModel):
    id: str
    email: str
    username: str
    is_owner: bool


class AuthOut(BaseModel):
    token: str
    user: UserOut


def _to_user_out(u: AppUser) -> UserOut:
    return UserOut(id=u.id, email=u.email, username=u.username, is_owner=bool(u.is_owner))


@router.post("/register", response_model=AuthOut)
async def register(payload: RegisterIn, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower().strip()
    username = payload.username.strip()
    exists_email = (await db.execute(select(AppUser).where(AppUser.email == email))).scalar_one_or_none()
    if exists_email:
        raise HTTPException(400, "email already used")
    exists_user = (await db.execute(select(AppUser).where(AppUser.username == username))).scalar_one_or_none()
    if exists_user:
        raise HTTPException(400, "username already used")
    digest, salt = hash_password(payload.password)
    user = AppUser(
        id=str(uuid.uuid4()),
        email=email,
        username=username,
        password_hash=digest,
        password_salt=salt,
        is_owner=(email == OWNER_EMAIL),
    )
    token = make_token()
    session = AuthSession(token=token, user_id=user.id, expires_at=make_session_expiry())
    db.add(user)
    db.add(session)
    await db.commit()
    return AuthOut(token=token, user=_to_user_out(user))


@router.post("/login", response_model=AuthOut)
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower().strip()
    user = (await db.execute(select(AppUser).where(AppUser.email == email))).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash, user.password_salt):
        raise HTTPException(401, "invalid credentials")
    token = make_token()
    db.add(AuthSession(token=token, user_id=user.id, expires_at=make_session_expiry()))
    await db.commit()
    return AuthOut(token=token, user=_to_user_out(user))


@router.post("/logout")
async def logout(
    x_auth_token: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    if x_auth_token:
        s = await db.get(AuthSession, x_auth_token)
        if s is not None:
            await db.delete(s)
            await db.commit()
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(
    x_auth_token: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not x_auth_token:
        raise HTTPException(401, "not logged in")
    now_user_session = (
        await db.execute(
            select(AuthSession).where(AuthSession.token == x_auth_token)
        )
    ).scalar_one_or_none()
    if now_user_session is None:
        raise HTTPException(401, "invalid session")
    user = await db.get(AppUser, now_user_session.user_id)
    if user is None:
        raise HTTPException(401, "invalid session")
    return _to_user_out(user)
