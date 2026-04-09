from __future__ import annotations

import json
from fastapi import APIRouter

from app.services.prewarm_bot import SNAPSHOT_PATH, run_full_scrape_if_stale

router = APIRouter()


@router.get("/snapshot")
async def snapshot():
    if SNAPSHOT_PATH.exists():
        return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return {"message": "no snapshot yet"}


@router.post("/run")
async def run_now():
    # Manual trigger should run immediately, regardless of freshness window.
    data = await run_full_scrape_if_stale(max_age_seconds=3600, force=True)
    return {
        "ok": True,
        "ran": data.get("ran", False),
        "reason": data.get("reason"),
        "sites": list(data.get("sites", {}).keys()),
        "products_upserted": data.get("products_upserted", 0),
    }
