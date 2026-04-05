"""
app/adapters/vibe.py  —  Vibe Gaming
Search URL : https://vibegaming.com.bd/?s={query}&post_type=product
Card sel   : div.product-wrapper
Price from : data-gtm4wp_product_data JSON attribute (most reliable)
"""
from __future__ import annotations
import json
from typing import Optional
from bs4 import BeautifulSoup, Tag
from app.adapters.base import BaseRetailerAdapter
from app.models.product import ProductResult


class VibeAdapter(BaseRetailerAdapter):
    retailer_id = "vibe"
    shop_name   = "Vibe Gaming"
    base_url    = "https://vibegaming.com.bd"

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
            title_a = card.select_one("h3.product-name a, h3.heading-title a")
            if not title_a:
                return None
            title = title_a.get_text(strip=True)
            link  = self._abs(title_a.get("href", ""))

            img_el = card.select_one("figure img")
            # prefer data-src (lazy-loaded) over src (placeholder)
            image  = self._abs(
                img_el.get("data-src") or img_el.get("src", "") if img_el else ""
            )

            # GTM data attribute has price + stock status as JSON
            gtm_el = card.select_one("span.gtm4wp_productdata")
            price, orig, available = 0.0, None, True
            if gtm_el:
                try:
                    data      = json.loads(gtm_el.get("data-gtm4wp_product_data", "{}"))
                    price     = float(data.get("price", 0))
                    available = data.get("stockstatus", "instock") == "instock"
                except Exception:
                    pass

            # Fallback: parse visible price spans
            if price == 0:
                ins_el  = card.select_one("span.price ins .amount")
                del_el  = card.select_one("span.price del .amount")
                raw_el  = card.select_one("span.price .amount")
                price   = self._price((ins_el or raw_el or Tag(name="span")).get_text())
                if del_el:
                    orig = self._price(del_el.get_text()) or None

            # Stock label fallback
            if card.select_one("span.out-of-stock"):
                available = False

            return ProductResult(
                title=title, price=price, original_price=orig,
                description=None, link=link, image=image,
                shop_name=self.shop_name, availability=available,
            )
        except Exception:
            return None
