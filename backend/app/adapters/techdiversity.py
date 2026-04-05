"""
app/adapters/techdiversity.py  —  Tech Diversity BD
Search URL : https://techdiversitybd.com/?s={query}&post_type=product
Card sel   : div.product-wrapper
Price from : data-gtm4wp_product_data JSON (same WooCommerce pattern as Vibe)
"""
from __future__ import annotations
import json
from typing import Optional
from bs4 import BeautifulSoup, Tag
from app.adapters.base import BaseRetailerAdapter
from app.models.product import ProductResult


class TechDiversityAdapter(BaseRetailerAdapter):
    retailer_id = "techdiversity"
    shop_name   = "Tech Diversity BD"
    base_url    = "https://techdiversitybd.com"

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
        return [p for card in soup.select("div.product-wrapper")
                if (p := self._parse(card)) is not None]

    def _parse(self, card: Tag) -> Optional[ProductResult]:
        try:
            title_a = card.select_one("h3.wd-entities-title a")
            if not title_a:
                return None
            title = title_a.get_text(strip=True)
            link  = self._abs(title_a.get("href", ""))

            img_el = card.select_one("img.hoverZoomLink")
            image  = self._abs(
                img_el.get("src", "") if img_el else ""
            )

            # GTM JSON data for price + stock
            gtm_el = card.select_one("span.gtm4wp_productdata")
            price, available = 0.0, True
            if gtm_el:
                try:
                    data      = json.loads(gtm_el.get("data-gtm4wp_product_data", "{}"))
                    price     = float(data.get("price", 0))
                    available = data.get("stockstatus", "instock") == "instock"
                except Exception:
                    pass

            # Stock label fallback
            if card.select_one("span.out-of-stock"):
                available = False

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
