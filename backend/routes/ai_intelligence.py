"""
AI Intelligence Endpoints (Phase 2)
===================================
Super-admin / admin-facing analytics endpoints:
  • Anomaly detection scans
  • Portfolio & per-project forecasting (slip-risk)
  • Project retrospective generation & history
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from auth.dependencies import get_current_user, require_admin, require_super_admin
from services.anomaly_detection import run_anomaly_scan, get_latest_anomaly_report
from services.forecasting import forecast_project, forecast_portfolio
from services.retrospective import (
    generate_retrospective, list_retrospectives, get_retrospective, delete_retrospective,
)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────
# Anomaly Detection
# ─────────────────────────────────────────────────────────────────────────

@router.post("/api/ai/anomaly/scan")
async def anomaly_scan(current_user: dict = Depends(require_admin)):
    """Trigger anomaly scan on demand. Admin+."""
    return await run_anomaly_scan(triggered_by=current_user.get("email", "manual"))


@router.get("/api/ai/anomaly/latest")
async def anomaly_latest(current_user: dict = Depends(require_admin)):
    """Return the most recent anomaly scan report."""
    report = await get_latest_anomaly_report()
    if not report:
        return {"findings": [], "summary": {"total_findings": 0}, "message": "No scan yet — trigger one."}
    return report


# ─────────────────────────────────────────────────────────────────────────
# Forecasting
# ─────────────────────────────────────────────────────────────────────────

@router.get("/api/ai/forecast/portfolio")
async def forecast_all(current_user: dict = Depends(require_admin)):
    """Return slip-risk forecast for all Active projects."""
    return await forecast_portfolio()


@router.get("/api/ai/forecast/project/{project_id}")
async def forecast_one(project_id: str, current_user: dict = Depends(get_current_user)):
    """Single project forecast. Leads/allocated users may also view their projects."""
    role = (current_user.get("role") or "").lower()
    is_admin = role in ("admin", "super_admin")
    if not is_admin:
        # Only allow if the user leads or is allocated to the project
        from utils import user_leads_project, find_user_resource
        allowed = await user_leads_project(current_user, project_id)
        if not allowed:
            res = await find_user_resource(current_user)
            if res:
                from database import allocations_collection
                alloc = await allocations_collection.find_one({
                    "project_id": project_id, "resource_id": str(res["_id"])
                })
                allowed = alloc is not None
        if not allowed:
            raise HTTPException(status_code=403, detail="Not authorised to view this project's forecast")
    result = await forecast_project(project_id)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


# ─────────────────────────────────────────────────────────────────────────
# Retrospectives
# ─────────────────────────────────────────────────────────────────────────

@router.post("/api/ai/retrospective/{project_id}")
async def create_retrospective(project_id: str, current_user: dict = Depends(require_admin)):
    """Generate and persist a retrospective. Admin+ (leads can generate for their projects too)."""
    result = await generate_retrospective(project_id, requested_by=current_user.get("email", "?"))
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.get("/api/ai/retrospective/list/{project_id}")
async def list_retros(project_id: str, current_user: dict = Depends(get_current_user)):
    """List retrospectives for a project (admin OR lead OR allocated resource can view)."""
    role = (current_user.get("role") or "").lower()
    is_admin = role in ("admin", "super_admin")
    if not is_admin:
        from utils import user_leads_project, find_user_resource
        allowed = await user_leads_project(current_user, project_id)
        if not allowed:
            res = await find_user_resource(current_user)
            if res:
                from database import allocations_collection
                alloc = await allocations_collection.find_one({
                    "project_id": project_id, "resource_id": str(res["_id"])
                })
                allowed = alloc is not None
        if not allowed:
            raise HTTPException(status_code=403, detail="Not authorised")
    return {"items": await list_retrospectives(project_id)}


@router.get("/api/ai/retrospective/{retro_id}")
async def get_retro(retro_id: str, current_user: dict = Depends(get_current_user)):
    r = await get_retrospective(retro_id)
    if not r:
        raise HTTPException(status_code=404, detail="Not found")
    # Same auth check as list
    role = (current_user.get("role") or "").lower()
    is_admin = role in ("admin", "super_admin")
    if not is_admin:
        from utils import user_leads_project, find_user_resource
        pid = r.get("project_id")
        allowed = await user_leads_project(current_user, pid) if pid else False
        if not allowed and pid:
            res = await find_user_resource(current_user)
            if res:
                from database import allocations_collection
                alloc = await allocations_collection.find_one({
                    "project_id": pid, "resource_id": str(res["_id"])
                })
                allowed = alloc is not None
        if not allowed:
            raise HTTPException(status_code=403, detail="Not authorised")
    return r


@router.delete("/api/ai/retrospective/{retro_id}")
async def delete_retro(retro_id: str, current_user: dict = Depends(require_admin)):
    ok = await delete_retrospective(retro_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}
