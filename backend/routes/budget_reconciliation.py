"""Budget Reconciliation API endpoints.

Routes:
  GET  /api/projects/{id}/budget-reconciliation           — 4-number summary + warnings
  POST /api/projects/{id}/phases/{phase_id}/sync-to-wbs   — update phase dates to MIN/MAX of WBS

Permissions: read = any auth user; sync = admin / super_admin / project lead.
"""
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from auth.dependencies import get_current_user
from database import projects_collection
from services.budget_reconciliation import (
    reconciliation_summary,
    derive_phase_dates_from_wbs,
)

router = APIRouter()


async def _find_project(project_id: str) -> Optional[dict]:
    if ObjectId.is_valid(project_id):
        p = await projects_collection.find_one({"_id": ObjectId(project_id)})
        if p:
            return p
    return await projects_collection.find_one({"id": project_id})


async def _require_phase_write(project: dict, current_user: dict):
    """Admin / super_admin / project_lead only."""
    role = (current_user.get("role") or "").lower()
    if role in ("admin", "super_admin"):
        return
    lead_id = project.get("project_lead_id")
    user_id = current_user.get("id") or current_user.get("_id") or current_user.get("resource_id")
    if lead_id and user_id and str(lead_id) == str(user_id):
        return
    if lead_id and current_user.get("email") and str(lead_id).lower() == current_user["email"].lower():
        return
    raise HTTPException(status_code=403, detail="Admin or project lead access required")


@router.get("/api/projects/{project_id}/budget-reconciliation")
async def api_budget_reconciliation(project_id: str, current_user: dict = Depends(get_current_user)):
    """Returns the 4-number summary (Budget / Estimated / Allocated / Actual)
    plus per-phase breakdown and hierarchy warnings."""
    project = await _find_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    pid = str(project.get("_id")) if project.get("_id") else (project.get("id") or project_id)
    return await reconciliation_summary(pid)


@router.post("/api/projects/{project_id}/phases/{phase_id}/sync-to-wbs")
async def api_sync_phase_to_wbs(
    project_id: str,
    phase_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Update a phase's start_date and end_date to MIN/MAX of its WBS task dates.
    Returns the new phase dates (or 404 if no tasks have dates)."""
    project = await _find_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await _require_phase_write(project, current_user)
    pid = str(project.get("_id"))

    derived = await derive_phase_dates_from_wbs(pid, phase_id)
    if not derived.get("derived_start") or not derived.get("derived_end"):
        raise HTTPException(
            status_code=400,
            detail="Cannot sync — no WBS tasks with dates exist for this phase.",
        )

    # Update the phase inside the project's phases[] array
    phases = project.get("phases") or []
    updated_phase = None
    for ph in phases:
        if ph.get("id") == phase_id:
            ph["start_date"] = derived["derived_start"]
            ph["end_date"] = derived["derived_end"]
            updated_phase = ph
            break
    if not updated_phase:
        raise HTTPException(status_code=404, detail="Phase not found in project")

    await projects_collection.update_one(
        {"_id": project["_id"]},
        {"$set": {
            "phases": phases,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    # Log change via the change_log helper if available
    try:
        from services.baselines import log_change
        await log_change(
            project_id=pid,
            user_email=current_user.get("email"),
            entity_type="phase",
            entity_id=phase_id,
            action="update",
            field="dates (sync to WBS)",
            new_value={"start_date": derived["derived_start"], "end_date": derived["derived_end"]},
            reason="Phase dates synced to MIN/MAX of WBS task dates",
        )
    except Exception:
        pass

    return {
        "phase_id": phase_id,
        "phase_name": updated_phase.get("name"),
        "new_start_date": derived["derived_start"],
        "new_end_date": derived["derived_end"],
        "task_count": derived.get("task_count", 0),
    }
