"""
app/services/compatibility.py
Checks whether PC parts in a build are compatible with each other.
Rules are data-driven — add more rules to RULES list without changing logic.
"""
from __future__ import annotations
from app.models.builder import PCBuild, CompatibilityResult, CompatibilityIssue


# ── Compatibility rules ──────────────────────────────────────────────────────
# Each rule is a function: (build) -> CompatibilityIssue | None
# Add new rules here; the checker runs all of them automatically.

def _check_cpu_motherboard_socket(build: PCBuild):
    cpu = _part(build, "cpu")
    mb  = _part(build, "motherboard")
    if not cpu or not mb:
        return None
    cpu_socket = cpu.specs.get("socket", "").upper()
    mb_socket  = mb.specs.get("socket", "").upper()
    if cpu_socket and mb_socket and cpu_socket != mb_socket:
        return CompatibilityIssue(
            severity="error",
            slot_a="cpu", slot_b="motherboard",
            message=f"CPU socket {cpu_socket} doesn't match motherboard socket {mb_socket}.",
        )
    return None


def _check_ram_ddr_generation(build: PCBuild):
    ram = _part(build, "ram")
    mb  = _part(build, "motherboard")
    if not ram or not mb:
        return None
    ram_gen = ram.specs.get("ddr", "").upper()
    mb_gen  = mb.specs.get("ddr", "").upper()
    if ram_gen and mb_gen and ram_gen != mb_gen:
        return CompatibilityIssue(
            severity="error",
            slot_a="ram", slot_b="motherboard",
            message=f"RAM is {ram_gen} but motherboard supports {mb_gen}.",
        )
    return None


def _check_m2_slot_availability(build: PCBuild):
    storage = _part(build, "storage")
    mb      = _part(build, "motherboard")
    if not storage or not mb:
        return None
    if storage.specs.get("interface", "").upper() == "M.2":
        m2_slots = int(mb.specs.get("m2_slots", "1") or "1")
        if m2_slots == 0:
            return CompatibilityIssue(
                severity="error",
                slot_a="storage", slot_b="motherboard",
                message="Motherboard has no M.2 slots but selected storage is M.2.",
            )
    return None


def _check_cooler_socket(build: PCBuild):
    cpu    = _part(build, "cpu")
    cooler = _part(build, "cooler")
    if not cpu or not cooler:
        return None
    cpu_socket     = cpu.specs.get("socket", "").upper()
    cooler_sockets = cooler.specs.get("supported_sockets", "").upper()
    if cpu_socket and cooler_sockets and cpu_socket not in cooler_sockets:
        return CompatibilityIssue(
            severity="warning",
            slot_a="cooler", slot_b="cpu",
            message=f"Cooler may not support {cpu_socket} socket. Verify mounting kit.",
        )
    return None


def _check_case_atx_form_factor(build: PCBuild):
    mb   = _part(build, "motherboard")
    case = _part(build, "case")
    if not mb or not case:
        return None
    mb_form   = mb.specs.get("form_factor", "").upper()
    case_form = case.specs.get("max_form_factor", "ATX").upper()
    order = ["ITX", "MATX", "ATX", "EATX"]
    if mb_form in order and case_form in order:
        if order.index(mb_form) > order.index(case_form):
            return CompatibilityIssue(
                severity="error",
                slot_a="case", slot_b="motherboard",
                message=f"Motherboard ({mb_form}) is too large for the case ({case_form}).",
            )
    return None


RULES = [
    _check_cpu_motherboard_socket,
    _check_ram_ddr_generation,
    _check_m2_slot_availability,
    _check_cooler_socket,
    _check_case_atx_form_factor,
]


# ── Public API ───────────────────────────────────────────────────────────────

def check_compatibility(build: PCBuild) -> CompatibilityResult:
    issues: list[CompatibilityIssue] = []
    for rule in RULES:
        issue = rule(build)
        if issue:
            issues.append(issue)
    errors = [i for i in issues if i.severity == "error"]
    return CompatibilityResult(compatible=len(errors) == 0, issues=issues)


def _part(build: PCBuild, slot: str):
    return next((p for p in build.parts if p.slot == slot), None)
