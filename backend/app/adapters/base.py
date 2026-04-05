"""
app/adapters/base.py
Abstract base. Every retailer implements search() -> list[ProductResult].
_abs() normalises relative URLs. _price() parses Bangladeshi price strings.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
import httpx
from app.models.product import ProductResult


class BaseRetailerAdapter(ABC):
    retailer_id: str = ""
    shop_name: str   = ""
    base_url: str    = ""

    def __init__(self):
        self.client = httpx.AsyncClient(
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
        )

    @abstractmethod
    async def search(self, query: str) -> list[ProductResult]: ...

    async def is_healthy(self) -> bool:
        try:
            r = await self.client.get(self.base_url, timeout=5.0)
            return r.status_code < 500
        except Exception:
            return False

    async def close(self):
        await self.client.aclose()

    def _abs(self, url: str) -> str:
        if not url:
            return ""
        return url if url.startswith("http") else self.base_url.rstrip("/") + "/" + url.lstrip("/")

    @staticmethod
    def _price(raw: str) -> float:
        cleaned = raw.replace("\u09f3", "").replace("\u09f3", "").replace("৳", "").replace("Tk", "").replace(",", "").strip()
        digits = "".join(c for c in cleaned if c.isdigit() or c == ".")
        return float(digits) if digits else 0.0
