"""
app/routers/cart.py
Guest cart stored in DB by session_id (sent as X-Session-Id header).
No login required. Cart just stores items — checkout opens the retailer's site.
"""
import json, uuid
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models import CartSession
from app.models.product import CartItem, Cart

router = APIRouter()


def _sid(x_session_id: str = Header(default="")) -> str:
    return x_session_id or uuid.uuid4().hex


@router.get("", response_model=Cart)
async def get_cart(sid: str = Depends(_sid), db: AsyncSession = Depends(get_db)):
    row = await db.get(CartSession, sid)
    items = json.loads(row.items_json) if row else []
    return Cart(items=[CartItem(**i) for i in items])


@router.post("/add", response_model=Cart)
async def add_item(item: CartItem, sid: str = Depends(_sid), db: AsyncSession = Depends(get_db)):
    row = await db.get(CartSession, sid)
    items: list[dict] = json.loads(row.items_json) if row else []
    for ex in items:
        if ex["product_id"] == item.product_id and ex["retailer"] == item.retailer:
            ex["quantity"] += item.quantity
            break
    else:
        items.append(item.model_dump())
    _upsert(db, row, sid, items)
    await db.commit()
    return Cart(items=[CartItem(**i) for i in items])


@router.delete("/item/{product_id}", response_model=Cart)
async def remove_item(
    product_id: str, retailer: str,
    sid: str = Depends(_sid), db: AsyncSession = Depends(get_db),
):
    row = await db.get(CartSession, sid)
    if not row:
        return Cart()
    items = [i for i in json.loads(row.items_json)
             if not (i["product_id"] == product_id and i["retailer"] == retailer)]
    row.items_json = json.dumps(items)
    await db.commit()
    return Cart(items=[CartItem(**i) for i in items])


@router.delete("")
async def clear_cart(sid: str = Depends(_sid), db: AsyncSession = Depends(get_db)):
    row = await db.get(CartSession, sid)
    if row:
        await db.delete(row)
        await db.commit()
    return {"message": "cleared"}


def _upsert(db, row, sid, items):
    if row:
        row.items_json = json.dumps(items)
    else:
        db.add(CartSession(session_id=sid, items_json=json.dumps(items)))
