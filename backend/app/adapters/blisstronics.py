"""
app/adapters/blisstronics.py  —  The Blisstronics
Search URL : https://theblisstronics.com/?s={query}&post_type=product
Card sel   : div.wd-product-wrapper
Note: price is often missing on card; we use what is available.
"""
from __future__ import annotations
from typing import Optional
from bs4 import BeautifulSoup, Tag
from app.adapters.base import BaseRetailerAdapter
from app.models.product import ProductResult


class BlisstronicsAdapter(BaseRetailerAdapter):
    retailer_id = "blisstronics"
    shop_name   = "The Blisstronics"
    base_url    = "https://theblisstronics.com"

    async def search_page(self, query: str, page: int) -> list[ProductResult]:
        if page < 1:
            return []
        try:
            base = self.base_url.rstrip("/")
            if page == 1:
                url, params = self.base_url, {"s": query, "post_type": "product"}
            else:
                url = f"{base}/page/{page}/"
                params = {"s": query, "post_type": "product"}
            resp = await self.client.get(url, params=params)
            resp.raise_for_status()
        except Exception:
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        return [p for card in soup.select("div.wd-product-wrapper")
                if (p := self._parse(card)) is not None]

    def _parse(self, card: Tag) -> Optional[ProductResult]:
        try:
            title_a = card.select_one("h3.wd-entities-title a")
            if not title_a:
                return None
            title = title_a.get_text(strip=True)
            link  = self._abs(title_a.get("href", ""))

            img_el = card.select_one("img.hoverZoomLink, img.attachment-woocommerce_thumbnail")
            image  = self._abs(img_el.get("src", "") if img_el else "")

            # Price — wrap-price span
            price_el = card.select_one("div.wrap-price span.woocommerce-Price-amount")
            price    = self._price(price_el.get_text() if price_el else "0")

            # Availability — no explicit label on card; default available if price > 0
            available = price > 0

            # Category as description
            cats_el = card.select_one("div.wd-product-cats")
            desc: Optional[str] = None
            if cats_el:
                desc = cats_el.get_text(" ", strip=True)

            return ProductResult(
                title=title, price=price, original_price=None,
                description=desc, link=link, image=image,
                shop_name=self.shop_name, availability=available,
            )
        except Exception:
            return None
