"""
Global Search & Command Palette API (Phase 5)
=============================================
Cross-collection search endpoint powering the ⌘K command palette and any
global search bar in the app.
"""
from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import get_current_user
from services.global_search import global_search

router = APIRouter()


@router.get("/api/search/global")
async def api_global_search(
    q: str,
    limit_per_type: int = 5,
    current_user: dict = Depends(get_current_user),
):
    """Cross-collection search. Any authenticated user; results are scoped
    to what they're allowed to see."""
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query 'q' is required")
    return await global_search(q, current_user, limit_per_type=min(max(limit_per_type, 1), 20))
