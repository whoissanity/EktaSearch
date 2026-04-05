"""
app/adapters/skyland.py  —  Skyland
Search URL : https://www.skyland.com.bd/index.php?route=product/search&search={query}
Card sel   : div.product-thumb
"""
from __future__ import annotations
from typing import Optional
from bs4 import BeautifulSoup, Tag
from app.adapters.base import BaseRetailerAdapter
from app.models.product import ProductResult


class SkylandAdapter(BaseRetailerAdapter):
    retailer_id = "skyland"
    shop_name   = "Skyland"
    base_url    = "https://www.skyland.com.bd"

    async def search_page(self, query: str, page: int) -> list[ProductResult]:
        if page < 1:
            return []
        try:
            params: dict[str, str | int] = {"route": "product/search", "search": query}
            if page > 1:
                params["page"] = page
            resp = await self.client.get(f"{self.base_url}/index.php", params=params)
            resp.raise_for_status()
        except Exception:
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        return [p for card in soup.select("div.product-thumb")
                if (p := self._parse(card)) is not None]

    def _parse(self, card: Tag) -> Optional[ProductResult]:
        try:
            name_a = card.select_one("div.name a")
            if not name_a:
                return None
            title = name_a.get("title", "") or name_a.get_text(strip=True)
            link  = self._abs(name_a.get("href", ""))

            # First img (primary product image)
            img_el = card.select_one("div.image img.img-first")
            image  = self._abs(img_el.get("src", "") if img_el else "")

            price_el = card.select_one("span.price-new")
            price    = self._price(price_el.get_text() if price_el else "0")

            orig_el  = card.select_one("span.price-old")
            orig     = self._price(orig_el.get_text() if orig_el else "") or None

            desc_el  = card.select_one("div.description")
            desc: Optional[str] = None
            if desc_el:
                desc = ProductResult.truncate(desc_el.get_text(strip=True))

            # No explicit out-of-stock indicator on card; treat as available
            available = price > 0

            return ProductResult(
                title=title, price=price, original_price=orig,
                description=desc, link=link, image=image,
                shop_name=self.shop_name, availability=available,
            )
        except Exception:
            return None
