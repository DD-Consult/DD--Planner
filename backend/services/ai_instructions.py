"""
AI Instructions Service
=======================
Fetches and formats custom AI instructions for injection into prompts.
"""
from typing import Optional
from database import ai_instructions_collection, ai_feedback_collection

async def get_instructions_for_prompt(
    category: str = "all",
    project_id: Optional[str] = None,
) -> str:
    """
    Fetch applicable AI instructions and format them for prompt injection.
    
    Priority order:
    1. Global instructions for this category
    2. Global instructions for "all" categories
    3. Project-specific instructions for this category (if project_id provided)
    4. Project-specific instructions for "all" categories (if project_id provided)
    
    Returns a formatted string to append to system prompts.
    Returns empty string if no instructions found.
    """
    instructions = []
    
    # Fetch global instructions
    query = {"scope": "global", "is_active": {"$ne": False}}
    if category != "all":
        query["category"] = {"$in": [category, "all"]}
    else:
        query["category"] = "all"
    
    cursor = ai_instructions_collection.find(query).sort("created_at", 1)
    global_instructions = await cursor.to_list(length=50)
    
    for inst in global_instructions:
        text = inst.get("instructions", "").strip()
        if text:
            instructions.append(text)
    
    # Fetch project-specific instructions (if project_id provided)
    if project_id:
        proj_query = {"scope": "project", "project_id": project_id, "is_active": {"$ne": False}}
        if category != "all":
            proj_query["category"] = {"$in": [category, "all"]}
        else:
            proj_query["category"] = "all"
        
        proj_cursor = ai_instructions_collection.find(proj_query).sort("created_at", 1)
        proj_instructions = await proj_cursor.to_list(length=50)
        
        for inst in proj_instructions:
            text = inst.get("instructions", "").strip()
            if text:
                instructions.append(text)
    
    if not instructions:
        return ""
    
    # Format as a clear section for the AI
    formatted = "\n\n--- USER-PROVIDED GUIDANCE ---\n"
    formatted += "The following instructions were provided by the project manager. Follow them carefully:\n"
    for i, inst in enumerate(instructions, 1):
        formatted += f"\n{i}. {inst}"
    formatted += "\n--- END GUIDANCE ---\n"
    
    return formatted



async def get_feedback_guidance_for_prompt(feature: str, project_id: Optional[str] = None, limit: int = 8) -> str:
    """Fold recent thumbs-up/down feedback for THIS feature into prompt guidance
    (the lightweight self-improving loop, MVP). Prioritises feedback with notes.

    Returns a formatted guidance string, or "" if there's nothing useful.
    """
    try:
        query = {"feature": feature}
        if project_id:
            # include both project-specific and global feedback for the feature
            query = {"feature": feature, "$or": [{"project_id": project_id}, {"project_id": None}]}
        cursor = ai_feedback_collection.find(query).sort("created_at", -1)
        rows = await cursor.to_list(length=50)
    except Exception:
        return ""
    if not rows:
        return ""

    # Prefer entries that include a written note; cap to `limit`.
    with_notes = [r for r in rows if (r.get("feedback_text") or "").strip()]
    chosen = (with_notes or rows)[:limit]

    likes, dislikes = [], []
    for r in chosen:
        note = (r.get("feedback_text") or "").strip()
        out = (r.get("output_summary") or "").strip()
        snippet = note or (f"(re: {out[:80]})" if out else "")
        if not snippet:
            continue
        if r.get("rating") == "thumbs_down":
            dislikes.append(snippet)
        else:
            likes.append(snippet)

    if not likes and not dislikes:
        return ""

    parts = ["\n\n--- TEAM FEEDBACK (learn from these ratings) ---"]
    if dislikes:
        parts.append("AVOID what this team disliked:")
        for i, d in enumerate(dislikes[:5], 1):
            parts.append(f"  - {d}")
    if likes:
        parts.append("PREFER what this team liked:")
        for i, l in enumerate(likes[:5], 1):
            parts.append(f"  - {l}")
    parts.append("--- END TEAM FEEDBACK ---\n")
    return "\n".join(parts)
