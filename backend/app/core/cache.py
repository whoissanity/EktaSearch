"""
app/core/cache.py
Thin async Redis wrapper. Falls back gracefully if Redis is unavailable.
"""
import json
import logging
from typing import Any, Optional
import redis.asyncio as aioredis
from app.core.config import get_settings

logger = logging.getLogger(__name__)
_redis: Optional[aioredis.Redis] = None


async def get_redis() -> Optional[aioredis.Redis]:
    global _redis
    if _redis is None:
        try:
            settings = get_settings()
            _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            await _redis.ping()
        except Exception as e:
            logger.warning("Redis unavailable, cache disabled: %s", e)
            _redis = None
    return _redis


async def cache_get(key: str) -> Optional[Any]:
    r = await get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.debug("Cache get error: %s", e)
        return None


async def cache_set(key: str, value: Any, ttl: Optional[int] = None) -> None:
    r = await get_redis()
    if r is None:
        return
    settings = get_settings()
    ttl = ttl or settings.cache_ttl_seconds
    try:
        await r.setex(key, ttl, json.dumps(value))
    except Exception as e:
        logger.debug("Cache set error: %s", e)


async def cache_delete(key: str) -> None:
    r = await get_redis()
    if r is None:
        return
    try:
        await r.delete(key)
    except Exception as e:
        logger.debug("Cache delete error: %s", e)


def make_cache_key(*parts: str) -> str:
    return ":".join(str(p) for p in parts)
