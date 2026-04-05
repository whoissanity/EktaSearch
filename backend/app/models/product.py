"""
app/models/product.py
Unified product model. Every adapter normalizes to ProductResult.
{
    "title": "Full product name",
    "price": 3000,
    "original_price": 3260,
    "description": "...",
    "link": "https://...",
    "image": "https://...",
    "shop_name": "Shop Name",
    "availability": true
}
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class ProductResult(BaseModel):
    title: str
    price: float
    original_price: Optional[float] = None
    description: Optional[str] = None
    link: str
    image: Optional[str] = None
    shop_name: str
    availability: bool

    @classmethod
    def truncate(cls, text: str, max_len: int = 150) -> str:
        text = " ".join(text.split())   # collapse whitespace
        return text[:max_len].rstrip() + "..." if len(text) > max_len else text


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[ProductResult]


# ── Cart models (kept here to avoid circular imports) ─────────────

class CartItem(BaseModel):
    product_id: str
    product_name: str
    retailer: str
    retailer_name: str
    price_bdt: float
    product_url: str
    quantity: int = 1
    image_url: Optional[str] = None


class Cart(BaseModel):
    items: list[CartItem] = []

    @property
    def total_bdt(self) -> float:
        return sum(i.price_bdt * i.quantity for i in self.items)
