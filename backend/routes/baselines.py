"""Baseline & Change-log API endpoints.

Routes:
  GET    /api/projects/{project_id}/baselines                — list baselines
  POST   /api/projects/{project_id}/baselines                — create baseline (snapshot)
  GET    /api/projects/{project_id}/baselines/current        — get current baseline (full snapshot)
  GET    /api/projects/{project_id}/baselines/{baseline_id}  — get a specific baseline (full snapshot)
  PATCH  /api/projects/{project_id}/baselines/{baseline_id}  — rename / set as current
  DELETE /api/projects/{project_id}/baselines/{baseline_id}  — delete (cannot delete current)
  GET    /api/projects/{project_id}/variance                 — compare current vs current baseline
  GET    /api/projects/{project_id}/variance/{baseline_id}   — compare current vs a specific baseline
  GET    /api/projects/{project_id}/change-log               — recent change-log entries

Permissions:
  • Read: any authenticated user with project access.
  • Write (create/patch/delete baseline): admin, super_admin, OR the
    project's project_lead_id.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from bson import ObjectId

from auth.dependencies import get_current_user
from database import projects_collection
from services.baselines import (
    create_baseline,
    list_baselines,
    get_baseline,
    get_current_baseline,
    set_current_baseline,
    rename_baseline,
    delete_baseline,
    compute_variance,
    list_change_log,
)


router = APIRouter()


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

async def _find_project(project_id: str) -> Optional[dict]:
    if ObjectId.is_valid(project_id):
        p = await projects_collection.find_one({"_id": ObjectId(project_id)})
        if p:
            return p
    return await projects_collection.find_one({"id": project_id})


async def _require_write_access(project_id: str, current_user: dict):
    """Allow admin / super_admin / project lead to mutate baselines."""
    role = (current_user.get("role") or "").lower()
    if role in ("admin", "super_admin"):
        return
    project = await _find_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    lead_id = project.get("project_lead_id")
    user_id = current_user.get("id") or current_user.get("_id") or current_user.get("resource_id")
    if lead_id and user_id and str(lead_id) == str(user_id):
        return
    # Fallback: match by email if the project_lead is stored as an email
    if lead_id and current_user.get("email") and str(lead_id).lower() == current_user["email"].lower():
        return
    raise HTTPException(
        status_code=403,
        detail="Only admins or the project lead can manage baselines.",
    )


# ────────────────────────────────────────────────────────────────────────────
# Request models
# ────────────────────────────────────────────────────────────────────────────

class BaselineCreate(BaseModel):
    name: str
    description: Optional[str] = None
    set_current: bool = True


class BaselinePatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    set_current: Optional[bool] = None


# ────────────────────────────────────────────────────────────────────────────
# Read endpoints
# ────────────────────────────────────────────────────────────────────────────

@router.get("/api/projects/{project_id}/baselines")
async def api_list_baselines(project_id: str, current_user: dict = Depends(get_current_user)):
    proj = await _find_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    pid = proj.get("id") or str(proj.get("_id"))
    items = await list_baselines(pid)
    return {"items": items, "count": len(items)}


@router.get("/api/projects/{project_id}/baselines/current")
async def api_get_current(project_id: str, current_user: dict = Depends(get_current_user)):
    proj = await _find_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    pid = proj.get("id") or str(proj.get("_id"))
    b = await get_current_baseline(pid)
    if not b:
        raise HTTPException(status_code=404, detail="No current baseline set")
    return b


@router.get("/api/projects/{project_id}/baselines/{baseline_id}")
async def api_get_baseline(project_id: str, baseline_id: str,
                           current_user: dict = Depends(get_current_user)):
    b = await get_baseline(baseline_id)
    if not b or b.get("project_id") not in (project_id,):
        # Fallback: look up project to allow ObjectId form
        proj = await _find_project(project_id)
        pid = proj.get("id") or str(proj.get("_id")) if proj else project_id
        if not b or b.get("project_id") != pid:
            raise HTTPException(status_code=404, detail="Baseline not found")
    return b


@router.get("/api/projects/{project_id}/variance")
async def api_variance_current(project_id: str, current_user: dict = Depends(get_current_user)):
    proj = await _find_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    pid = proj.get("id") or str(proj.get("_id"))
    return await compute_variance(pid)


@router.get("/api/projects/{project_id}/variance/{baseline_id}")
async def api_variance_specific(project_id: str, baseline_id: str,
                                current_user: dict = Depends(get_current_user)):
    proj = await _find_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    pid = proj.get("id") or str(proj.get("_id"))
    return await compute_variance(pid, baseline_id)


@router.get("/api/projects/{project_id}/change-log")
async def api_change_log(
    project_id: str,
    limit: int = Query(default=200, le=1000, ge=1),
    entity_type: Optional[str] = Query(default=None),
    since: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
):
    proj = await _find_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    pid = proj.get("id") or str(proj.get("_id"))
    items = await list_change_log(pid, limit=limit, entity_type=entity_type, since=since)
    return {"items": items, "count": len(items)}


# ────────────────────────────────────────────────────────────────────────────
# Write endpoints
# ────────────────────────────────────────────────────────────────────────────

@router.post("/api/projects/{project_id}/baselines")
async def api_create_baseline(
    project_id: str,
    payload: BaselineCreate,
    current_user: dict = Depends(get_current_user),
):
    proj = await _find_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    pid = proj.get("id") or str(proj.get("_id"))
    await _require_write_access(pid, current_user)

    if not (payload.name or "").strip():
        raise HTTPException(status_code=400, detail="Baseline name is required")

    b = await create_baseline(
        pid,
        name=payload.name.strip(),
        description=(payload.description or None),
        created_by=current_user.get("email") or "unknown",
        set_current=payload.set_current,
    )
    return b


@router.patch("/api/projects/{project_id}/baselines/{baseline_id}")
async def api_patch_baseline(
    project_id: str,
    baseline_id: str,
    payload: BaselinePatch,
    current_user: dict = Depends(get_current_user),
):
    proj = await _find_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    pid = proj.get("id") or str(proj.get("_id"))
    await _require_write_access(pid, current_user)

    b = await get_baseline(baseline_id)
    if not b or b.get("project_id") != pid:
        raise HTTPException(status_code=404, detail="Baseline not found")

    if payload.name is not None or payload.description is not None:
        await rename_baseline(
            baseline_id,
            name=payload.name,
            description=payload.description,
        )
    if payload.set_current is True:
        await set_current_baseline(pid, baseline_id)

    return await get_baseline(baseline_id)


@router.delete("/api/projects/{project_id}/baselines/{baseline_id}")
async def api_delete_baseline(
    project_id: str,
    baseline_id: str,
    current_user: dict = Depends(get_current_user),
):
    proj = await _find_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    pid = proj.get("id") or str(proj.get("_id"))
    await _require_write_access(pid, current_user)

    b = await get_baseline(baseline_id)
    if not b or b.get("project_id") != pid:
        raise HTTPException(status_code=404, detail="Baseline not found")
    try:
        ok = await delete_baseline(baseline_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail="Baseline not found")
    return {"deleted": True, "id": baseline_id}
