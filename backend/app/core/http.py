"""
Shared httpx.AsyncClient for retailer adapters — one connection pool per process.
"""
from __future__ import annotations
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)
_client: Optional[httpx.AsyncClient] = None


async def init_http_client() -> None:
    global _client
    if _client is not None:
        return
    _client = httpx.AsyncClient(
        timeout=12.0,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
        follow_redirects=True,
        limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
    )
    logger.debug("HTTP client initialized")


async def close_http_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.debug("HTTP client closed")


def get_http_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("HTTP client not initialized — call init_http_client on startup")
    return _client
