"""
app/routers/builder.py
PC Builder endpoints.
POST /api/builder/analyze  — run compat + wattage on a build (no save needed)
POST /api/builder/save     — persist build to DB, returns build_id
GET  /api/builder/{id}     — load a saved build
GET  /api/builder          — list all saved builds
DELETE /api/builder/{id}   — delete a build
"""
import uuid, json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_db
from app.db.models import SavedBuild
from app.models.builder import PCBuild, BuildAnalysis
from app.services.compatibility import check_compatibility
from app.services.wattage import calculate_wattage

router = APIRouter()


@router.post("/analyze", response_model=BuildAnalysis)
async def analyze_build(build: PCBuild):
    """Live compat + wattage check. Call on every part change."""
    return BuildAnalysis(
        build=build,
        compatibility=check_compatibility(build),
        wattage=calculate_wattage(build),
    )


@router.post("/save")
async def save_build(build: PCBuild, db: AsyncSession = Depends(get_db)):
    build_id = (build.id or uuid.uuid4().hex[:8]).upper()
    parts_json = json.dumps([p.model_dump() for p in build.parts])
    existing = await db.get(SavedBuild, build_id)
    if existing:
        existing.name = build.name
        existing.parts_json = parts_json
        existing.total_bdt = sum(p.price_bdt for p in build.parts)
    else:
        db.add(SavedBuild(
            id=build_id, name=build.name,
            parts_json=parts_json,
            total_bdt=sum(p.price_bdt for p in build.parts),
        ))
    await db.commit()
    return {"build_id": build_id}


@router.get("/{build_id}", response_model=PCBuild)
async def get_build(build_id: str, db: AsyncSession = Depends(get_db)):
    row = await db.get(SavedBuild, build_id.upper())
    if not row:
        raise HTTPException(404, "Build not found")
    d = row.to_dict()
    return PCBuild(id=d["id"], name=d["name"], parts=d["parts"])


@router.get("")
async def list_builds(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(SavedBuild).order_by(SavedBuild.updated_at.desc())
    )).scalars().all()
    return [{"id": r.id, "name": r.name, "total_bdt": r.total_bdt} for r in rows]


@router.delete("/{build_id}")
async def delete_build(build_id: str, db: AsyncSession = Depends(get_db)):
    row = await db.get(SavedBuild, build_id.upper())
    if not row:
        raise HTTPException(404, "Build not found")
    await db.delete(row)
    await db.commit()
    return {"message": "deleted"}
