"""
app/adapters/ryans.py  —  Ryans Computers
Search URL : https://www.ryans.com/search?search={query}
Card sel   : div.category-single-product  (wrapper class on outer div)
"""
from __future__ import annotations
from typing import Optional
from bs4 import BeautifulSoup, Tag
from app.adapters.base import BaseRetailerAdapter
from app.models.product import ProductResult


class RyansAdapter(BaseRetailerAdapter):
    retailer_id = "ryans"
    shop_name   = "Ryans Computers"
    base_url    = "https://www.ryans.com"

    async def search_page(self, query: str, page: int) -> list[ProductResult]:
        if page < 1:
            return []
        try:
            params: dict[str, str | int] = {"search": query}
            if page > 1:
                params["page"] = page
            resp = await self.client.get(f"{self.base_url}/search", params=params)
            resp.raise_for_status()
        except Exception:
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        return [p for card in soup.select("div.category-single-product")
                if (p := self._parse(card)) is not None]

    def _parse(self, card: Tag) -> Optional[ProductResult]:
        try:
            # Link + title  (from product-title anchor)
            title_a = card.select_one("h4.product-title a")
            if not title_a:
                return None
            title = title_a.get_text(strip=True).rstrip(".")
            link  = self._abs(title_a.get("href", ""))

            # Image
            img_el    = card.select_one("div.image-box img")
            image     = self._abs(img_el.get("src", "") if img_el else "")

            # Price  "Tk\n3,000"
            price_el  = card.select_one("p.pr-text")
            price     = self._price(price_el.get_text() if price_el else "0")

            # Original price from modal  (new-reg-text)
            orig_el   = card.select_one("span.new-reg-text")
            orig      = self._price(orig_el.get_text() if orig_el else "") or None

            # Description from Quick Overview in modal
            overview  = card.select_one("div.overview p")
            desc: Optional[str] = None
            if overview:
                desc = ProductResult.truncate(overview.get_text(" ", strip=True))

            # Availability — if "Add to Cart" button present and not disabled
            cart_btn  = card.select_one("button.cat-cart-btn")
            available = cart_btn is not None and not cart_btn.has_attr("disabled")

            return ProductResult(
                title=title, price=price, original_price=orig,
                description=desc, link=link, image=image,
                shop_name=self.shop_name, availability=available,
            )
        except Exception:
            return None
