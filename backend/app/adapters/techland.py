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

    async def search(self, query: str) -> list[ProductResult]:
        try:
            import urllib.parse
            encoded = urllib.parse.quote(query)
            resp = await self.client.get(
                f"{self.base_url}/search/advance/product/result/{encoded}"
            )
            resp.raise_for_status()
        except Exception:
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        # Each product is wrapped in a div with h-full > bg-white card inside
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
