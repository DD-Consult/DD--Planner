"""
AI Instructions Service
=======================
Fetches and formats custom AI instructions for injection into prompts.
"""
from typing import Optional
from database import ai_instructions_collection

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
