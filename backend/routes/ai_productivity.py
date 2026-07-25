"""
AI Productivity Endpoints (Phase 3)
====================================
Admin / Lead-focused productivity endpoints:
  • Status Update Drafter
  • Kickoff Wizard
  • Similar Projects finder
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Optional

from auth.dependencies import get_current_user, require_admin
from services.status_drafter import draft_status_update
from services.kickoff_wizard import suggest_kickoff
from services.similar_projects import find_similar_projects
from utils import user_leads_project

router = APIRouter()


@router.post("/api/ai/draft-status-update/{project_id}")
async def ai_draft_status_update(project_id: str, current_user: dict = Depends(get_current_user)):
    """Draft a status update. Admin OR lead of the project may generate."""
    role = (current_user.get("role") or "").lower()
    is_admin = role in ("admin", "super_admin")
    if not is_admin:
        allowed = await user_leads_project(current_user, project_id)
        if not allowed:
            raise HTTPException(status_code=403, detail="Only project leads/admins can draft status updates")
    result = await draft_status_update(project_id)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.post("/api/ai/kickoff-suggest")
async def ai_kickoff_suggest(payload: dict = Body(...), current_user: dict = Depends(require_admin)):
    """Kickoff wizard — suggest phases, WBS, roles, budget for a new project. Admin+."""
    if not payload.get("name") and not payload.get("goal"):
        raise HTTPException(status_code=400, detail="Provide at least 'name' or 'goal'")
    result = await suggest_kickoff(payload)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.get("/api/ai/similar-projects/{project_id}")
async def ai_similar_projects(project_id: str, limit: int = 5, current_user: dict = Depends(get_current_user)):
    """Find similar historic projects. Any authenticated user with access can view."""
    result = await find_similar_projects(project_id, limit=min(max(limit, 1), 20))
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result
