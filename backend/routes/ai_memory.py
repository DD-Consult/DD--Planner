"""
Agent Memory API — persistent per-project and global context for the AI agent.
Admins and project leads can save key decisions, preferences, and notes that are
automatically injected into future AI chat sessions.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from bson import ObjectId
from typing import Optional

from database import ai_memory_collection
from auth.dependencies import get_current_user, require_admin
from utils import serialize_doc

router = APIRouter(prefix="/api/ai/memory", tags=["ai-memory"])

VALID_CATEGORIES = {"decision", "preference", "context", "note"}
VALID_SCOPES = {"global", "project"}


@router.get("")
async def list_memories(
    scope: Optional[str] = None,
    project_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """List active memories. Admins see all; others see global + their project memories."""
    query: dict = {"active": {"$ne": False}}
    if scope:
        query["scope"] = scope
    if project_id:
        query["project_id"] = project_id
    cursor = ai_memory_collection.find(query).sort("created_at", -1)
    docs = await cursor.to_list(length=500)
    return serialize_doc(docs)


@router.get("/project/{project_id}")
async def get_project_memories(
    project_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get all memories for a specific project (including global ones)."""
    cursor = ai_memory_collection.find({
        "active": {"$ne": False},
        "$or": [{"scope": "global"}, {"project_id": project_id}]
    }).sort("created_at", -1)
    docs = await cursor.to_list(length=200)
    return serialize_doc(docs)


@router.post("")
async def create_memory(
    payload: dict,
    current_user: dict = Depends(get_current_user),
):
    """Create a new memory entry."""
    scope = payload.get("scope", "project")
    if scope not in VALID_SCOPES:
        raise HTTPException(status_code=400, detail=f"scope must be one of {VALID_SCOPES}")
    category = payload.get("category", "note")
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category must be one of {VALID_CATEGORIES}")
    title = (payload.get("title") or "").strip()
    content = (payload.get("content") or "").strip()
    if not title or not content:
        raise HTTPException(status_code=400, detail="title and content are required")

    doc = {
        "scope": scope,
        "project_id": payload.get("project_id") if scope == "project" else None,
        "title": title,
        "content": content,
        "category": category,
        "created_by": current_user.get("email"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "active": True,
    }
    result = await ai_memory_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


@router.put("/{memory_id}")
async def update_memory(
    memory_id: str,
    payload: dict,
    current_user: dict = Depends(get_current_user),
):
    """Update an existing memory."""
    if not ObjectId.is_valid(memory_id):
        raise HTTPException(status_code=400, detail="Invalid memory_id")
    update: dict = {}
    for f in ("title", "content", "category", "active"):
        if f in payload:
            update[f] = payload[f]
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await ai_memory_collection.update_one({"_id": ObjectId(memory_id)}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"message": "Memory updated"}


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Soft-delete a memory (sets active=False)."""
    if not ObjectId.is_valid(memory_id):
        raise HTTPException(status_code=400, detail="Invalid memory_id")
    result = await ai_memory_collection.update_one(
        {"_id": ObjectId(memory_id)},
        {"$set": {"active": False, "deleted_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"message": "Memory deleted"}
