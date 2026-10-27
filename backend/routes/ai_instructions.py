"""AI Instructions & Feedback API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId
import uuid

from database import (
    ai_instructions_collection,
    ai_feedback_collection,
    projects_collection,
)
from models.schemas import (
    AIInstructionCreate,
    AIInstructionUpdate,
    AIInstructionResponse,
    AIFeedbackCreate,
    AIFeedbackResponse,
)
from auth.dependencies import get_current_user, require_admin
from utils import serialize_doc

router = APIRouter()


# ============================================================
# AI Instructions Endpoints
# ============================================================

@router.get("/api/ai/instructions", response_model=List[AIInstructionResponse])
async def list_instructions(
    scope: Optional[str] = Query(None, description="Filter by scope: global or project"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    current_user: dict = Depends(get_current_user)
):
    """
    List all AI instructions with optional filters.
    
    Query Parameters:
    - scope: Filter by "global" or "project"
    - project_id: Filter by specific project ID
    - category: Filter by category (all, risk_polish, status_summary, wbs_generation, reschedule, chat)
    """
    query = {}
    
    if scope:
        query["scope"] = scope
    if project_id:
        query["project_id"] = project_id
    if category:
        query["category"] = category
    
    cursor = ai_instructions_collection.find(query).sort("created_at", -1)
    instructions = await cursor.to_list(length=500)
    
    return [serialize_doc(inst) for inst in instructions]


@router.get("/api/ai/instructions/project/{project_id}", response_model=List[AIInstructionResponse])
async def get_project_instructions(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all applicable instructions for a specific project.
    Includes both project-specific and global instructions.
    """
    # Verify project exists
    try:
        project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Fetch global instructions
    global_query = {"scope": "global", "is_active": {"$ne": False}}
    global_cursor = ai_instructions_collection.find(global_query).sort("created_at", 1)
    global_instructions = await global_cursor.to_list(length=100)
    
    # Fetch project-specific instructions
    project_query = {"scope": "project", "project_id": project_id, "is_active": {"$ne": False}}
    project_cursor = ai_instructions_collection.find(project_query).sort("created_at", 1)
    project_instructions = await project_cursor.to_list(length=100)
    
    # Combine and return
    all_instructions = global_instructions + project_instructions
    return [serialize_doc(inst) for inst in all_instructions]


@router.post("/api/ai/instructions", response_model=AIInstructionResponse, status_code=201)
async def create_instruction(
    instruction: AIInstructionCreate,
    current_user: dict = Depends(require_admin)
):
    """
    Create a new AI instruction.
    
    Admin only. Validates project exists if scope is "project".
    """
    # Validate scope and project_id consistency
    if instruction.scope == "project" and not instruction.project_id:
        raise HTTPException(
            status_code=400,
            detail="project_id is required when scope is 'project'"
        )
    
    if instruction.scope == "global" and instruction.project_id:
        raise HTTPException(
            status_code=400,
            detail="project_id must be null when scope is 'global'"
        )
    
    # Verify project exists if project-specific
    if instruction.project_id:
        try:
            project = await projects_collection.find_one({"_id": ObjectId(instruction.project_id)})
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid project ID format")
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    
    # Validate category
    valid_categories = ["all", "risk_polish", "status_summary", "wbs_generation", "reschedule", "chat"]
    if instruction.category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
        )
    
    # Create instruction document
    instruction_doc = {
        "id": str(uuid.uuid4()),
        "scope": instruction.scope,
        "project_id": instruction.project_id,
        "category": instruction.category,
        "instructions": instruction.instructions.strip(),
        "is_active": True,
        "created_by": current_user["email"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None
    }
    
    await ai_instructions_collection.insert_one(instruction_doc)
    
    return serialize_doc(instruction_doc)


@router.put("/api/ai/instructions/{instruction_id}", response_model=AIInstructionResponse)
async def update_instruction(
    instruction_id: str,
    update: AIInstructionUpdate,
    current_user: dict = Depends(require_admin)
):
    """
    Update an existing AI instruction.
    
    Admin only. Can update instructions text, category, or active status.
    """
    # Find instruction
    instruction = await ai_instructions_collection.find_one({"id": instruction_id})
    if not instruction:
        raise HTTPException(status_code=404, detail="Instruction not found")
    
    # Build update document
    update_doc = {}
    
    if update.instructions is not None:
        update_doc["instructions"] = update.instructions.strip()
    
    if update.category is not None:
        valid_categories = ["all", "risk_polish", "status_summary", "wbs_generation", "reschedule", "chat"]
        if update.category not in valid_categories:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
            )
        update_doc["category"] = update.category
    
    if update.is_active is not None:
        update_doc["is_active"] = update.is_active
    
    if not update_doc:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    update_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await ai_instructions_collection.update_one(
        {"id": instruction_id},
        {"$set": update_doc}
    )
    
    # Fetch and return updated document
    updated_instruction = await ai_instructions_collection.find_one({"id": instruction_id})
    return serialize_doc(updated_instruction)


@router.delete("/api/ai/instructions/{instruction_id}", status_code=204)
async def delete_instruction(
    instruction_id: str,
    current_user: dict = Depends(require_admin)
):
    """
    Delete an AI instruction.
    
    Admin only. Permanently removes the instruction.
    """
    result = await ai_instructions_collection.delete_one({"id": instruction_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Instruction not found")
    
    return None


# ============================================================
# AI Feedback Endpoints
# ============================================================

@router.post("/api/ai/feedback", response_model=AIFeedbackResponse, status_code=201)
async def submit_feedback(
    feedback: AIFeedbackCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Submit feedback on an AI-generated output.
    
    Available to all authenticated users.
    """
    # Validate feature
    valid_features = ["risk_polish", "status_summary", "wbs_generation", "reschedule", "chat",
                      "budget_analysis", "proposal", "insights"]
    if feedback.feature not in valid_features:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid feature. Must be one of: {', '.join(valid_features)}"
        )
    
    # Validate rating
    if feedback.rating not in ["thumbs_up", "thumbs_down"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid rating. Must be 'thumbs_up' or 'thumbs_down'"
        )
    
    # Verify project exists if provided
    if feedback.project_id:
        try:
            project = await projects_collection.find_one({"_id": ObjectId(feedback.project_id)})
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid project ID format")
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    
    # Create feedback document
    feedback_doc = {
        "id": str(uuid.uuid4()),
        "feature": feedback.feature,
        "project_id": feedback.project_id,
        "rating": feedback.rating,
        "input_summary": feedback.input_summary,
        "output_summary": feedback.output_summary,
        "feedback_text": feedback.feedback_text,
        "user_email": current_user["email"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await ai_feedback_collection.insert_one(feedback_doc)
    
    return serialize_doc(feedback_doc)


@router.get("/api/ai/feedback/stats")
async def get_feedback_stats(
    current_user: dict = Depends(require_admin)
):
    """
    Get AI feedback statistics.
    
    Admin only. Returns:
    - Total feedback count
    - Count by feature
    - Count by rating
    - Recent feedback samples
    """
    # Total count
    total_count = await ai_feedback_collection.count_documents({})
    
    # Count by feature
    feature_pipeline = [
        {"$group": {"_id": "$feature", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    feature_stats = await ai_feedback_collection.aggregate(feature_pipeline).to_list(length=50)
    feature_counts = {item["_id"]: item["count"] for item in feature_stats}
    
    # Count by rating
    rating_pipeline = [
        {"$group": {"_id": "$rating", "count": {"$sum": 1}}}
    ]
    rating_stats = await ai_feedback_collection.aggregate(rating_pipeline).to_list(length=10)
    rating_counts = {item["_id"]: item["count"] for item in rating_stats}
    
    # Recent feedback (last 20)
    cursor = ai_feedback_collection.find({}).sort("created_at", -1).limit(20)
    recent_feedback = await cursor.to_list(length=20)
    recent_feedback_list = [serialize_doc(fb) for fb in recent_feedback]
    
    return {
        "total_count": total_count,
        "by_feature": feature_counts,
        "by_rating": rating_counts,
        "recent_feedback": recent_feedback_list
    }



# ============================================================
# FEEDBACK ANALYTICS + AUTO-TUNING SUGGESTIONS (Phase 3)
# ============================================================

@router.get("/api/ai/feedback/analytics")
async def get_feedback_analytics(current_user: dict = Depends(require_admin)):
    """Per-feature thumbs up/down breakdown with satisfaction % + recent notes.

    Admin only. Powers the feedback trends view.
    """
    rows = await ai_feedback_collection.find({}).sort("created_at", -1).to_list(length=5000)
    total = len(rows)
    features = {}
    for r in rows:
        f = r.get("feature", "other")
        feat = features.setdefault(f, {"feature": f, "up": 0, "down": 0, "total": 0, "recent_notes": []})
        feat["total"] += 1
        if r.get("rating") == "thumbs_down":
            feat["down"] += 1
        else:
            feat["up"] += 1
        note = (r.get("feedback_text") or "").strip()
        if note and len(feat["recent_notes"]) < 5:
            feat["recent_notes"].append({"rating": r.get("rating"), "note": note})

    per_feature = []
    for feat in features.values():
        t = feat["total"] or 1
        feat["satisfaction_pct"] = round(feat["up"] / t * 100)
        per_feature.append(feat)
    per_feature.sort(key=lambda x: (-x["total"], x["feature"]))

    up = sum(1 for r in rows if r.get("rating") != "thumbs_down")
    return {
        "total": total,
        "overall_satisfaction_pct": round(up / total * 100) if total else None,
        "by_feature": per_feature,
    }


@router.post("/api/ai/feedback/suggest-instructions")
async def suggest_instructions(current_user: dict = Depends(require_admin)):
    """Use the configured AI to propose refinements to the workspace's AI
    instructions, based on recent thumbs-down feedback (auto-tuning, Phase 3).

    Admin only. Returns {ok, suggestions:[{category, suggestion}], summary} —
    the admin reviews and can save them as instructions (we do NOT auto-apply).
    """
    rows = await ai_feedback_collection.find({}).sort("created_at", -1).to_list(length=400)
    if not rows:
        return {"ok": False, "summary": "No feedback captured yet — collect some thumbs up/down first.", "suggestions": []}

    # Build a compact digest grouped by feature, prioritising thumbs-down with notes.
    digest = {}
    for r in rows:
        f = r.get("feature", "other")
        d = digest.setdefault(f, {"up": 0, "down": 0, "down_notes": [], "up_notes": []})
        if r.get("rating") == "thumbs_down":
            d["down"] += 1
            n = (r.get("feedback_text") or "").strip()
            if n and len(d["down_notes"]) < 8:
                d["down_notes"].append(n)
        else:
            d["up"] += 1
            n = (r.get("feedback_text") or "").strip()
            if n and len(d["up_notes"]) < 4:
                d["up_notes"].append(n)

    import json as _json
    from services.ai_providers import call_ai_text
    system_prompt = (
        "You are an AI operations analyst for a project-management app. Given feedback on the app's "
        "AI features (thumbs up/down with optional notes), propose concise, actionable INSTRUCTIONS the "
        "team can add to steer the AI toward what they want. Focus on features with low satisfaction or "
        "repeated complaints. Each suggestion must be a single imperative sentence the AI can follow.\n\n"
        "Valid categories: all, chat, status_summary, wbs_generation, reschedule, risk_polish.\n"
        "Return ONLY valid JSON: {\"summary\": \"<1-2 sentence overview>\", "
        "\"suggestions\": [{\"category\": \"<one of the categories>\", \"suggestion\": \"<imperative instruction>\"}]}. "
        "Return at most 5 suggestions. If feedback is all positive, return an empty suggestions array with an encouraging summary."
    )
    user_message = "Feedback digest by feature:\n" + _json.dumps(digest, indent=2)

    text, provider = await call_ai_text(system_prompt, user_message, json_mode=True)
    if not text:
        return {"ok": False, "summary": "AI is unavailable right now — try again shortly.", "suggestions": []}
    # Parse robustly
    import re as _re
    cleaned = _re.sub(r'^```(?:json)?\s*', '', text.strip())
    cleaned = _re.sub(r'\s*```$', '', cleaned)
    try:
        parsed = _json.loads(cleaned)
        suggestions = parsed.get("suggestions", []) or []
        # sanitise categories
        valid = {"all", "chat", "status_summary", "wbs_generation", "reschedule", "risk_polish"}
        for s in suggestions:
            if s.get("category") not in valid:
                s["category"] = "all"
        return {"ok": True, "summary": parsed.get("summary", ""), "suggestions": suggestions[:5], "provider": provider}
    except Exception:
        return {"ok": False, "summary": "Couldn't parse the AI suggestion. Try again.", "suggestions": []}
