"""
app/core/cache.py
Thin async Redis wrapper. Falls back gracefully if Redis is unavailable.
"""
import json
import logging
import time
from typing import Any, Optional
import redis.asyncio as aioredis
from app.core.config import get_settings
from app.services.observability import record_cache

logger = logging.getLogger(__name__)
_redis: Optional[aioredis.Redis] = None
_memory_cache: dict[str, tuple[float, Any]] = {}


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
        item = _memory_cache.get(key)
        if not item:
            record_cache(False)
            return None
        expires_at, value = item
        if expires_at < time.time():
            _memory_cache.pop(key, None)
            record_cache(False)
            return None
        record_cache(True)
        return value
    try:
        raw = await r.get(key)
        hit = bool(raw)
        record_cache(hit)
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.debug("Cache get error: %s", e)
        record_cache(False)
        return None


async def cache_set(key: str, value: Any, ttl: Optional[int] = None) -> None:
    r = await get_redis()
    settings = get_settings()
    ttl = ttl or settings.cache_ttl_seconds
    if r is None:
        # Fast local fallback when Redis is unavailable.
        _memory_cache[key] = (time.time() + ttl, value)
        # Keep map bounded.
        if len(_memory_cache) > 300:
            for k in list(_memory_cache.keys())[:80]:
                _memory_cache.pop(k, None)
        return
    try:
        await r.setex(key, ttl, json.dumps(value))
    except Exception as e:
        logger.debug("Cache set error: %s", e)


async def cache_delete(key: str) -> None:
    r = await get_redis()
    _memory_cache.pop(key, None)
    if r is None:
        return
    try:
        await r.delete(key)
    except Exception as e:
        logger.debug("Cache delete error: %s", e)


def make_cache_key(*parts: str) -> str:
    return ":".join(str(p) for p in parts)
