"""
Resource-Facing AI Endpoints (Phase 4)
======================================
Natural-language timesheet parsing + personal Monday briefing.
"""
from fastapi import APIRouter, Depends, HTTPException, Body

from auth.dependencies import get_current_user
from services.timesheet_assistant import parse_timesheet_phrase
from services.personal_briefing import get_personal_briefing

router = APIRouter()


@router.post("/api/ai/timesheet/parse")
async def ai_timesheet_parse(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Parse a natural-language phrase into a proposed timesheet entry.
    Does NOT create the entry — the frontend confirms with the user first."""
    phrase = (payload or {}).get("phrase")
    if not phrase or not str(phrase).strip():
        raise HTTPException(status_code=400, detail="Provide 'phrase' in the request body.")
    result = await parse_timesheet_phrase(str(phrase).strip(), current_user)
    return result


@router.get("/api/ai/briefing/personal")
async def ai_personal_briefing(current_user: dict = Depends(get_current_user)):
    """Personal Monday briefing for the current user."""
    result = await get_personal_briefing(current_user)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result
