from __future__ import annotations

import json
from fastapi import APIRouter

from app.services.prewarm_bot import SNAPSHOT_PATH, discover_and_scrape_once

router = APIRouter()


@router.get("/snapshot")
async def snapshot():
    if SNAPSHOT_PATH.exists():
        return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return {"message": "no snapshot yet"}


@router.post("/run")
async def run_now():
    data = await discover_and_scrape_once()
    return {"ok": True, "sites": list(data.get("sites", {}).keys())}
