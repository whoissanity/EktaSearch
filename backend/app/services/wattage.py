"""
app/services/wattage.py
Estimates total system power draw and recommends minimum PSU wattage.
Uses TDP values from part specs, or falls back to category averages.
"""
from __future__ import annotations
from app.models.builder import PCBuild, WattageResult, WattageBreakdown

# Average TDP fallbacks per slot when spec is missing
AVERAGE_WATTS: dict[str, int] = {
    "cpu":         95,
    "gpu":        200,
    "motherboard": 50,
    "ram":         10,
    "storage":     10,
    "psu":          0,   # PSU itself not counted
    "case":         5,   # fans
    "cooler":      10,
}

PSU_HEADROOM = 1.30   # recommend 30% headroom above estimated draw


def calculate_wattage(build: PCBuild) -> WattageResult:
    breakdown: list[WattageBreakdown] = []

    for part in build.parts:
        # Try to read TDP from specs (e.g. "65W" or "65")
        raw_tdp = part.specs.get("tdp", "")
        watts = _parse_watts(raw_tdp) or AVERAGE_WATTS.get(part.slot, 20)
        breakdown.append(WattageBreakdown(
            slot=part.slot,
            component=part.product_name,
            estimated_watts=watts,
        ))

    total = sum(b.estimated_watts for b in breakdown)
    recommended = _round_up_psu(total * PSU_HEADROOM)

    return WattageResult(
        total_estimated_watts=total,
        recommended_psu_watts=recommended,
        breakdown=breakdown,
    )


def _parse_watts(raw: str) -> int | None:
    if not raw:
        return None
    digits = "".join(c for c in raw if c.isdigit())
    return int(digits) if digits else None


def _round_up_psu(watts: float) -> int:
    """Round up to nearest common PSU size: 450, 550, 650, 750, 850, 1000, 1200."""
    standard = [450, 550, 650, 750, 850, 1000, 1200, 1600]
    for size in standard:
        if size >= watts:
            return size
    return 1600
