"""
Knowledge Base API
==================
Endpoints for managing and querying the AI knowledge base built from
GUIDE.md, README.md, INTEGRATIONS.md.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from auth.dependencies import get_current_user, require_super_admin
from services.knowledge_base import reindex, status, retrieve

router = APIRouter()


@router.get("/api/ai/knowledge-base/status")
async def kb_status(current_user: dict = Depends(get_current_user)):
    """Any authenticated user can see indexing status."""
    return await status()


@router.post("/api/ai/knowledge-base/reindex")
async def kb_reindex(current_user: dict = Depends(require_super_admin)):
    """Super-admin only: rebuild the KB from disk."""
    return await reindex()


@router.get("/api/ai/knowledge-base/search")
async def kb_search(
    q: str,
    top_k: int = 4,
    current_user: dict = Depends(get_current_user),
):
    """Any authenticated user can query the KB (used by chat + help widgets)."""
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query 'q' is required")
    results = await retrieve(q, top_k=min(max(top_k, 1), 10))
    # Trim to lightweight response
    return {
        "query": q,
        "results": [
            {
                "source": r.get("source"),
                "section_path": r.get("section_path"),
                "title": r.get("title"),
                "content": r.get("content"),
                "score": r.get("_score"),
            }
            for r in results
        ],
    }
