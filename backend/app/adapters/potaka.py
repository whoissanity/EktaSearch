"""
app/adapters/potaka.py  —  PoTaka IT
Search URL : https://potakait.com/product/search?search={query}
Card sel   : div.product-item
"""
from __future__ import annotations
from typing import Optional
from bs4 import BeautifulSoup, Tag
from app.adapters.base import BaseRetailerAdapter
from app.models.product import ProductResult


class PotakaAdapter(BaseRetailerAdapter):
    retailer_id = "potaka"
    shop_name   = "PoTaka IT"
    base_url    = "https://potakait.com"

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
        return [p for card in soup.select("div.product-item")
                if (p := self._parse(card)) is not None]

    def _parse(self, card: Tag) -> Optional[ProductResult]:
        try:
            title_a = card.select_one("h2.title a")
            if not title_a:
                return None
            title = title_a.get_text(strip=True)
            link  = self._abs(title_a.get("href", ""))

            img_el = card.select_one("div.product-img img")
            image  = self._abs(img_el.get("src", "") if img_el else "")

            # Current price — first p.price (not .old)
            prices = card.select("p.price")
            price, orig = 0.0, None
            for p_el in prices:
                if "old" in p_el.get("class", []):
                    orig = self._price(p_el.get_text()) or None
                else:
                    price = self._price(p_el.get_text())

            # Short description
            desc_el = card.select_one("div.product-info__short-description")
            desc: Optional[str] = None
            if desc_el:
                items = [li.get_text(strip=True) for li in desc_el.select("li")]
                desc  = ProductResult.truncate(" | ".join(items))

            # Availability from cart button text
            cart_btn  = card.select_one("a.btn.add-to-cart")
            btn_txt   = cart_btn.get_text(strip=True).lower() if cart_btn else ""
            available = "out" not in btn_txt

            return ProductResult(
                title=title, price=price, original_price=orig,
                description=desc, link=link, image=image,
                shop_name=self.shop_name, availability=available,
            )
        except Exception:
            return None
