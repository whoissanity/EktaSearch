from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.services.observability import prometheus_text, snapshot

router = APIRouter()


@router.get("/metrics")
async def metrics():
    return snapshot()


@router.get("/prometheus", response_class=PlainTextResponse)
async def metrics_prometheus():
    return prometheus_text()
