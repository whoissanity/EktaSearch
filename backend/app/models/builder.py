"""
app/models/builder.py
PC Builder schemas — build, compatibility, wattage.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class BuildPart(BaseModel):
    """A single selected part in a build."""
    slot: str              # cpu | gpu | motherboard | ram | storage | psu | case | cooler
    product_id: str
    product_name: str
    price_bdt: float
    retailer: str
    specs: dict[str, str] = {}


class PCBuild(BaseModel):
    id: Optional[str] = None
    name: str = "My Build"
    parts: list[BuildPart] = []

    @property
    def total_bdt(self) -> float:
        return sum(p.price_bdt for p in self.parts)

    @property
    def slots_filled(self) -> list[str]:
        return [p.slot for p in self.parts]


class CompatibilityIssue(BaseModel):
    severity: str          # error | warning
    slot_a: str
    slot_b: Optional[str] = None
    message: str


class CompatibilityResult(BaseModel):
    compatible: bool
    issues: list[CompatibilityIssue] = []


class WattageBreakdown(BaseModel):
    slot: str
    component: str
    estimated_watts: int


class WattageResult(BaseModel):
    total_estimated_watts: int
    recommended_psu_watts: int   # estimated * 1.3 headroom
    breakdown: list[WattageBreakdown]


class BuildAnalysis(BaseModel):
    build: PCBuild
    compatibility: CompatibilityResult
    wattage: WattageResult
    budget_remaining_bdt: Optional[float] = None


# ── Slot definitions ──────────────────────────────────────────────
SLOTS = ["cpu", "motherboard", "ram", "gpu", "storage", "psu", "case", "cooler"]

PC_CATEGORIES = {
    "cpu":         "Processor",
    "motherboard": "Motherboard",
    "ram":         "RAM",
    "gpu":         "Graphics Card",
    "storage":     "Storage",
    "psu":         "Power Supply",
    "case":        "Case",
    "cooler":      "CPU Cooler",
}
