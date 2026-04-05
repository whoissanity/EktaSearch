"""
app/adapters/base.py
Abstract base. Every retailer implements search_page(query, page) -> list[ProductResult].
search() is page 1 only. _abs() normalises relative URLs. _price() parses BDT strings.
Uses a process-wide httpx.AsyncClient (see app.core.http).
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from app.models.product import ProductResult
from app.core.http import get_http_client


class BaseRetailerAdapter(ABC):
    retailer_id: str = ""
    shop_name: str   = ""
    base_url: str    = ""

    @property
    def client(self):
        return get_http_client()

    @abstractmethod
    async def search_page(self, query: str, page: int) -> list[ProductResult]: ...

    async def search(self, query: str) -> list[ProductResult]:
        return await self.search_page(query, 1)

    async def is_healthy(self) -> bool:
        try:
            r = await self.client.get(self.base_url, timeout=5.0)
            return r.status_code < 500
        except Exception:
            return False

    async def close(self):
        """No-op: shared HTTP client is closed on app shutdown."""

    def _abs(self, url: str) -> str:
        if not url:
            return ""
        return url if url.startswith("http") else self.base_url.rstrip("/") + "/" + url.lstrip("/")

    @staticmethod
    def _price(raw: str) -> float:
        cleaned = raw.replace("\u09f3", "").replace("\u09f3", "").replace("৳", "").replace("Tk", "").replace(",", "").strip()
        digits = "".join(c for c in cleaned if c.isdigit() or c == ".")
        return float(digits) if digits else 0.0
