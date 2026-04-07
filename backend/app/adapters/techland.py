"""
app/adapters/techland.py  —  Tech Land BD
Search URL : https://www.techlandbd.com/search/advance/product/result/{query}
Card sel   : div.bg-white.rounded-lg.shadow-sm  (the inner card)
"""
from __future__ import annotations
from typing import Optional
from bs4 import BeautifulSoup, Tag
from app.adapters.base import BaseRetailerAdapter
from app.models.product import ProductResult


class TechLandAdapter(BaseRetailerAdapter):
    retailer_id = "techland"
    shop_name   = "Tech Land BD"
    base_url    = "https://www.techlandbd.com"
    _CATEGORY_PATHS = {
        "cpu": "/pc-components/processor",
        "cooler": "/pc-components/cpu-cooler",
        "motherboard": "/pc-components/motherboard",
        "gpu": "/pc-components/graphics-card",
        "ram": "/pc-components/computer-ram",
        "ssd": "/pc-components/solid-state-drive",
        "psu": "/pc-components/power-supply",
        "case": "/pc-components/computer-casing",
        "storage": "/pc-components/solid-state-drive",
    }

    async def search_category_page(self, category: str, query: str, page: int) -> list[ProductResult]:
        path = self._CATEGORY_PATHS.get((category or "").lower())
        if not path or page < 1:
            return await self.search_page(query, page)
        try:
            params = {"page": page} if page > 1 else None
            resp = await self.client.get(f"{self.base_url}{path}", params=params)
            resp.raise_for_status()
        except Exception:
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.select("div.h-full > div.bg-white")
        rows = [p for card in cards if (p := self._parse(card)) is not None]
        return [r for r in rows if self._matches_query(r.title, query)]

    async def search_page(self, query: str, page: int) -> list[ProductResult]:
        if page < 1:
            return []
        try:
            import urllib.parse

            encoded = urllib.parse.quote(query)
            url = f"{self.base_url}/search/advance/product/result/{encoded}"
            resp = await self.client.get(
                url,
                params={"page": page} if page > 1 else None,
            )
            resp.raise_for_status()
        except Exception:
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.select("div.h-full > div.bg-white")
        return [p for card in cards if (p := self._parse(card)) is not None]

    def _parse(self, card: Tag) -> Optional[ProductResult]:
        try:
            # Title + link
            title_a = card.select_one("a.text-gray-800.font-semibold")
            if not title_a:
                return None
            title = title_a.get_text(strip=True)
            link  = self._abs(title_a.get("href", ""))

            # Image — inside the first <a> with <img>
            img_el = card.select_one("a.block img")
            image  = self._abs(img_el.get("src", "") if img_el else "")

            # Price  "৳ 3,900"
            price_el = card.select_one("span.text-lg.font-bold.text-red-600")
            price    = self._price(price_el.get_text() if price_el else "0")

            # Original price (line-through)
            orig_el  = card.select_one("span.text-sm.text-gray-500.line-through")
            orig     = self._price(orig_el.get_text() if orig_el else "") or None

            # Availability
            stock_el  = card.select_one("span.font-bold")
            avail_txt = stock_el.get_text(strip=True).lower() if stock_el else ""
            available = "out" not in avail_txt

            return ProductResult(
                title=title, price=price, original_price=orig,
                description=None, link=link, image=image,
                shop_name=self.shop_name, availability=available,
            )
        except Exception:
            return None
