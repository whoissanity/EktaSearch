from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import AppUser, AuthSession

OWNER_EMAIL = "mdsowadabbus@gmail.com"


def hash_password(password: str, salt_hex: Optional[str] = None) -> tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return digest.hex(), salt.hex()


def verify_password(password: str, digest_hex: str, salt_hex: str) -> bool:
    got, _ = hash_password(password, salt_hex=salt_hex)
    return secrets.compare_digest(got, digest_hex)


def make_token() -> str:
    return secrets.token_urlsafe(36)


async def get_user_from_token(token: Optional[str], db: AsyncSession) -> Optional[AppUser]:
    if not token:
        return None
    now = datetime.now(timezone.utc)
    s = (
        await db.execute(
            select(AuthSession).where(
                AuthSession.token == token,
                AuthSession.expires_at > now,
            )
        )
    ).scalar_one_or_none()
    if s is None:
        return None
    return await db.get(AppUser, s.user_id)


async def get_current_user_optional(
    x_auth_token: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Optional[AppUser]:
    return await get_user_from_token(x_auth_token, db)


def make_session_expiry(days: int = 30) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)
