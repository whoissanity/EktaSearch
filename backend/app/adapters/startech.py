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

    async def search(self, query: str) -> list[ProductResult]:
        try:
            resp = await self.client.get(
                f"{self.base_url}/product/search", params={"search": query}
            )
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
