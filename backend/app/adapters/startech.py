"""
app/adapters/startech.py  —  Star Tech
Search URL : https://www.startech.com.bd/product/search?search={query}
Card sel   : div.p-item
"""
from __future__ import annotations
from typing import Optional
from bs4 import BeautifulSoup, Tag
from app.adapters.base import BaseRetailerAdapter
from app.models.product import ProductResult


class StarTechAdapter(BaseRetailerAdapter):
    retailer_id = "startech"
    shop_name   = "Star Tech"
    base_url    = "https://www.startech.com.bd"
    _CATEGORY_PATHS = {
        "cpu": "/component/processor",
        "cooler": "/component/cooling-fan",
        "motherboard": "/component/motherboard",
        "gpu": "/component/graphics-card",
        "ram": "/component/ram",
        "ssd": "/component/ssd-msata",
        "hdd": "/component/hard-disk-drive",
        "psu": "/component/power-supply",
        "case": "/component/casing",
        "storage": "/component/ssd-msata",
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
        rows = [p for card in soup.select("div.p-item") if (p := self._parse(card)) is not None]
        return [r for r in rows if self._matches_query(r.title, query)]

    async def search_page(self, query: str, page: int) -> list[ProductResult]:
        if page < 1:
            return []
        try:
            params: dict[str, str | int] = {"search": query}
            if page > 1:
                params["page"] = page
            resp = await self.client.get(f"{self.base_url}/product/search", params=params)
            resp.raise_for_status()
        except Exception:
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        return [p for card in soup.select("div.p-item")
                if (p := self._parse(card)) is not None]

    def _parse(self, card: Tag) -> Optional[ProductResult]:
        try:
            name_a = card.select_one("h4.p-item-name a")
            if not name_a:
                return None
            title  = name_a.get_text(strip=True)
            link   = self._abs(name_a.get("href", ""))

            img_el = card.select_one("div.p-item-img img")
            image  = self._abs(img_el.get("src", "") if img_el else "")

            price_el = card.select_one("span.price-new")
            price    = self._price(price_el.get_text() if price_el else "0")

            orig_el  = card.select_one("span.price-old")
            orig     = self._price(orig_el.get_text() if orig_el else "") or None

            # Short description — list items joined
            desc_el  = card.select_one("div.short-description")
            desc: Optional[str] = None
            if desc_el:
                items = [li.get_text(strip=True) for li in desc_el.select("li")]
                desc  = ProductResult.truncate(" | ".join(items))

            available = card.select_one("span.btn-add-cart") is not None

            return ProductResult(
                title=title, price=price, original_price=orig,
                description=desc, link=link, image=image,
                shop_name=self.shop_name, availability=available,
            )
        except Exception:
            return None
