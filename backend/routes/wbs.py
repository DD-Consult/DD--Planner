"""WBS (Work Breakdown Structure) API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Response
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from bson import ObjectId
import json
import re
import uuid as uuid_module

from database import (
    projects_collection, resources_collection, timesheets_collection,
    settings_collection, wbs_tasks_collection, EMERGENT_LLM_KEY,
)
from models.schemas import (
    WBSTaskCreate, WBSTaskUpdate, WBSTaskResponse,
    AIGenerateWBSRequest, SaveGeneratedWBSRequest,
)
from auth.dependencies import get_current_user, require_admin
from utils import serialize_doc
from services.ai_providers import (
    get_ai_config, call_openai_api, call_gemini_api, call_emergent_fallback,
)
from services.ai_instructions import get_instructions_for_prompt

router = APIRouter()


# ============================================================
# Helper: parse AI response from different providers
# ============================================================

def _parse_openai_json(response) -> Optional[dict]:
    try:
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        print(f"[WBS] OpenAI parse error: {e}")
        return None


def _parse_gemini_json(response) -> Optional[dict]:
    try:
        result = response.json()
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        # Strip markdown code blocks if present
        cleaned = re.sub(r'^```(?:json)?\s*', '', text.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned)
        return json.loads(cleaned.strip())
    except Exception as e:
        print(f"[WBS] Gemini parse error: {e}")
        return None


async def _call_wbs_ai(request_provider: Optional[str], request_api_key: Optional[str],
                       system_prompt: str, user_message: str) -> Optional[dict]:
    """Call AI with priority: request key → app settings → emergent fallback."""

    # Priority 1: request-level provider + api_key (from frontend localStorage)
    if request_provider and request_api_key:
        try:
            if request_provider == "gemini":
                resp = await call_gemini_api(request_api_key, system_prompt, user_message)
                if resp.status_code == 200:
                    result = _parse_gemini_json(resp)
                    if result:
                        return result
            else:  # openai
                resp = await call_openai_api(request_api_key, system_prompt, user_message)
                if resp.status_code == 200:
                    result = _parse_openai_json(resp)
                    if result:
                        return result
        except Exception as e:
            print(f"[WBS] Request-level AI call error: {e}")

    # Priority 2: App-wide settings from DB
    try:
        config = await get_ai_config()
        if config["api_key"] and config["provider"] not in (None, "emergent"):
            if config["provider"] == "gemini":
                resp = await call_gemini_api(config["api_key"], system_prompt, user_message)
                if resp.status_code == 200:
                    result = _parse_gemini_json(resp)
                    if result:
                        return result
            else:
                resp = await call_openai_api(config["api_key"], system_prompt, user_message)
                if resp.status_code == 200:
                    result = _parse_openai_json(resp)
                    if result:
                        return result
    except Exception as e:
        print(f"[WBS] App-settings AI call error: {e}")

    # Priority 3: Emergent LLM fallback
    return await call_emergent_fallback(system_prompt, user_message)


# ============================================================
# WBS Budget Validation Helper
# ============================================================

async def validate_wbs_budget(project_id: str, new_task_hours: float = 0, exclude_task_id: str = None) -> dict:
    """
    Validate if WBS total hours would exceed project budget.
    
    Args:
        project_id: Project ID to validate
        new_task_hours: Hours for new/updated task (default 0)
        exclude_task_id: Task ID to exclude from total (for updates)
        
    Returns:
        dict with validation status and budget info
    """
    # Get project budget
    project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    if not project:
        return {
            "is_valid": True,
            "total_wbs_hours": 0,
            "project_budget": None,
            "remaining": None,
            "warning": "Project not found"
        }
    
    project_budget = project.get("budgeted_hours")
    
    # If no budget set, validation always passes
    if project_budget is None or project_budget == 0:
        return {
            "is_valid": True,
            "total_wbs_hours": new_task_hours,
            "project_budget": None,
            "remaining": None,
            "warning": None
        }
    
    # Get sum of all existing WBS task estimates (excluding the task being updated)
    query = {"project_id": project_id}
    if exclude_task_id:
        try:
            query["_id"] = {"$ne": ObjectId(exclude_task_id)}
        except Exception:
            pass  # Invalid ObjectId, skip exclusion
    
    tasks = await wbs_tasks_collection.find(query).to_list(length=10000)
    existing_total = sum(t.get("estimated_hours", 0) for t in tasks)
    
    # Calculate new total
    total_wbs_hours = existing_total + new_task_hours
    remaining = project_budget - total_wbs_hours
    is_valid = total_wbs_hours <= project_budget
    
    warning = None
    if not is_valid:
        over_by = abs(remaining)
        warning = f"WBS tasks exceed project budget by {over_by:.1f} hours"
    
    return {
        "is_valid": is_valid,
        "total_wbs_hours": round(total_wbs_hours, 2),
        "project_budget": round(project_budget, 2),
        "remaining": round(remaining, 2),
        "warning": warning
    }


# ============================================================
# WBS CRUD
# ============================================================

@router.get("/api/projects/{project_id}/wbs")
async def get_project_wbs(project_id: str, current_user: dict = Depends(get_current_user)):
    """Get all WBS tasks for a project (flat list, ordered)."""
    cursor = wbs_tasks_collection.find({"project_id": project_id}).sort("order", 1)
    tasks = await cursor.to_list(length=10000)

    # Build resource name map
    resources_cursor = resources_collection.find()
    resources_list = await resources_cursor.to_list(length=10000)
    resource_map = {str(r["_id"]): r.get("name", "") for r in resources_list}

    result = []
    for task in tasks:
        task_data = serialize_doc(task)
        if task_data.get("assigned_to"):
            task_data["assigned_to_name"] = resource_map.get(task_data["assigned_to"], "Unknown")
        task_data["children"] = []
        result.append(task_data)

    return result


@router.get("/api/projects/{project_id}/wbs/budget-status")
async def get_wbs_budget_status(project_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get current WBS budget status for a project.
    Returns total WBS hours vs project budget with validation status.
    """
    budget_status = await validate_wbs_budget(project_id)
    return budget_status


@router.post("/api/projects/{project_id}/wbs/tasks", response_model=WBSTaskResponse)
async def create_wbs_task(
    project_id: str,
    task: WBSTaskCreate,
    response: Response,
    current_user: dict = Depends(require_admin),
):
    """Create a new WBS task or milestone with budget validation.
    
    If is_milestone=True:
    - estimated_hours is forced to 0
    - start_date and end_date are set to milestone_date
    """
    task_doc = task.dict()
    task_doc["project_id"] = project_id
    task_doc["id"] = str(uuid_module.uuid4())
    task_doc["created_by"] = current_user.get("email", "")
    task_doc["created_at"] = datetime.now(timezone.utc).isoformat()
    task_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Handle milestone-specific logic
    if task_doc.get("is_milestone"):
        task_doc["estimated_hours"] = 0
        task_doc["actual_hours"] = 0
        task_doc["milestone_completed"] = False
        # Set start/end dates to milestone_date for consistency
        if task_doc.get("milestone_date"):
            task_doc["start_date"] = task_doc["milestone_date"]
            task_doc["end_date"] = task_doc["milestone_date"]

    result = await wbs_tasks_collection.insert_one(task_doc)
    task_doc["_id"] = result.inserted_id
    
    # NEW: Budget validation - add to response header
    try:
        budget_status = await validate_wbs_budget(project_id)
        import json as _json
        response.headers["X-WBS-Budget-Status"] = _json.dumps(budget_status)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Budget validation failed: {e}")

    # CHANGE-LOG: task creation
    try:
        from services.baselines import log_change
        await log_change(
            project_id=project_id, user_email=current_user.get("email"),
            entity_type="wbs_task", entity_id=task_doc["id"],
            action="create", new_value={
                "name": task_doc.get("name"),
                "phase_name": task_doc.get("phase_name"),
                "estimated_hours": task_doc.get("estimated_hours"),
                "start_date": task_doc.get("start_date"),
                "end_date": task_doc.get("end_date"),
                "is_milestone": task_doc.get("is_milestone"),
            },
        )
    except Exception:
        pass

    # Build resource name map for response
    resources_cursor = resources_collection.find()
    resources_list = await resources_cursor.to_list(length=10000)
    resource_map = {str(r["_id"]): r.get("name", "") for r in resources_list}

    serialized = serialize_doc(task_doc)
    if serialized.get("assigned_to"):
        serialized["assigned_to_name"] = resource_map.get(serialized["assigned_to"], "Unknown")
    serialized["children"] = []
    return serialized


@router.put("/api/wbs/tasks/{task_id}", response_model=WBSTaskResponse)
async def update_wbs_task(
    task_id: str,
    update: WBSTaskUpdate,
    response: Response,
    current_user: dict = Depends(require_admin),
):
    """Update a WBS task.

    SEAMLESS BEHAVIOURS:
      • If `end_date` changes, dependency dates are automatically cascaded
        downstream (transitive). No manual "cascade" click required.
      • Budget hierarchy is validated (sum of phase estimates vs phase budget);
        warnings are returned in X-Budget-Warnings header.
    """
    task = None
    try:
        task = await wbs_tasks_collection.find_one({"_id": ObjectId(task_id)})
    except Exception:
        pass

    if not task:
        task = await wbs_tasks_collection.find_one({"id": task_id})

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    before = dict(task)  # shallow copy for diff

    update_data = update.dict(exclude_unset=True)
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await wbs_tasks_collection.update_one(
        {"_id": task["_id"]},
        {"$set": update_data}
    )

    updated_task = await wbs_tasks_collection.find_one({"_id": task["_id"]})

    # ─── AUTO-CASCADE on end_date change ───
    end_date_changed = (
        "end_date" in update_data
        and update_data["end_date"]
        and str(update_data["end_date"])[:10] != str(before.get("end_date") or "")[:10]
    )
    cascaded_count = 0
    if end_date_changed:
        try:
            cascaded_count = await _auto_cascade_dependencies(
                str(task["_id"]),
                str(update_data["end_date"])[:10],
            )
            if cascaded_count > 0:
                response.headers["X-Cascade-Updated"] = str(cascaded_count)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Auto-cascade failed: {e}")

    # CHANGE-LOG: diff and write per-field entries
    try:
        from services.baselines import diff_and_log_wbs_update
        await diff_and_log_wbs_update(
            project_id=str(task.get("project_id") or ""),
            user_email=current_user.get("email"),
            task_id=task.get("id") or str(task["_id"]),
            before=before, after=updated_task,
        )
    except Exception:
        pass

    # ─── BUDGET HIERARCHY warnings ───
    try:
        from services.budget_reconciliation import gather_save_warnings
        warnings = await gather_save_warnings(str(task.get("project_id") or ""))
        if warnings:
            import json as _json
            response.headers["X-Budget-Warnings"] = _json.dumps(warnings)
    except Exception:
        pass
    
    # NEW: WBS Budget validation
    try:
        budget_status = await validate_wbs_budget(str(task.get("project_id") or ""))
        import json as _json
        response.headers["X-WBS-Budget-Status"] = _json.dumps(budget_status)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"WBS Budget validation failed: {e}")

    resources_cursor = resources_collection.find()
    resources_list = await resources_cursor.to_list(length=10000)
    resource_map = {str(r["_id"]): r.get("name", "") for r in resources_list}

    serialized = serialize_doc(updated_task)
    if serialized.get("assigned_to"):
        serialized["assigned_to_name"] = resource_map.get(serialized["assigned_to"], "Unknown")
    serialized["children"] = []
    return serialized


async def _auto_cascade_dependencies(task_id_str: str, end_date_str: str) -> int:
    """Internal helper used by update_wbs_task to auto-push dependent task
    start dates forward. Same recursive logic as the manual cascade endpoint."""
    visited: set = set()
    updated_count = 0

    async def _cascade(from_task_id_str: str, from_end_date: str):
        nonlocal updated_count
        if from_task_id_str in visited:
            return
        visited.add(from_task_id_str)

        dependents = await wbs_tasks_collection.find(
            {"dependencies": from_task_id_str}
        ).to_list(length=1000)

        for dep_task in dependents:
            try:
                end_d = datetime.strptime(from_end_date, "%Y-%m-%d").date()
                new_start = (end_d + timedelta(days=1)).isoformat()
                
                # Calculate and preserve task duration
                old_start = dep_task.get("start_date")
                old_end = dep_task.get("end_date")
                new_end = None
                
                if old_start and old_end:
                    try:
                        old_start_d = datetime.strptime(old_start, "%Y-%m-%d").date()
                        old_end_d = datetime.strptime(old_end, "%Y-%m-%d").date()
                        duration_days = (old_end_d - old_start_d).days
                        
                        # Calculate new end date preserving duration
                        new_start_d = datetime.strptime(new_start, "%Y-%m-%d").date()
                        new_end = (new_start_d + timedelta(days=duration_days)).isoformat()
                    except Exception:
                        pass
            except Exception:
                continue

            dep_id_str = str(dep_task["_id"])
            
            # Update both start and end dates to preserve duration
            update_fields = {
                "start_date": new_start,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            if new_end:
                update_fields["end_date"] = new_end
            
            await wbs_tasks_collection.update_one(
                {"_id": dep_task["_id"]},
                {"$set": update_fields}
            )
            updated_count += 1
            dep_end = new_end if new_end else dep_task.get("end_date", from_end_date)
            await _cascade(dep_id_str, dep_end)

    await _cascade(task_id_str, end_date_str)
    return updated_count


@router.delete("/api/wbs/tasks/{task_id}")
async def delete_wbs_task(task_id: str, current_user: dict = Depends(require_admin)):
    """Delete a WBS task and all recursive children."""
    task = None
    try:
        task = await wbs_tasks_collection.find_one({"_id": ObjectId(task_id)})
    except Exception:
        pass

    if not task:
        task = await wbs_tasks_collection.find_one({"id": task_id})

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task_obj_id_str = str(task["_id"])
    project_id_for_log = str(task.get("project_id") or "")

    # CHANGE-LOG: task deletion (before we actually delete)
    try:
        from services.baselines import log_change
        await log_change(
            project_id=project_id_for_log, user_email=current_user.get("email"),
            entity_type="wbs_task", entity_id=task.get("id") or task_obj_id_str,
            action="delete", old_value={
                "name": task.get("name"),
                "phase_name": task.get("phase_name"),
                "estimated_hours": task.get("estimated_hours"),
                "start_date": task.get("start_date"),
                "end_date": task.get("end_date"),
            },
        )
    except Exception:
        pass

    # Recursive delete of children
    async def _delete_recursive(t_id_str: str):
        children = await wbs_tasks_collection.find({"parent_id": t_id_str}).to_list(length=1000)
        for child in children:
            await _delete_recursive(str(child["_id"]))
        await wbs_tasks_collection.delete_one({"_id": ObjectId(t_id_str)})

    await _delete_recursive(task_obj_id_str)

    # Remove from other tasks' dependencies
    await wbs_tasks_collection.update_many(
        {"dependencies": task_obj_id_str},
        {"$pull": {"dependencies": task_obj_id_str}}
    )

    return {"message": "Task deleted successfully"}


@router.patch("/api/wbs/tasks/{task_id}/complete-milestone")
async def complete_milestone(
    task_id: str,
    completed: bool = True,
    current_user: dict = Depends(require_admin),
):
    """Mark a milestone as completed or uncompleted.
    
    This endpoint is specifically for milestones (is_milestone=True).
    Sets milestone_completed flag and updates status to 'done' when completed.
    """
    task = None
    try:
        task = await wbs_tasks_collection.find_one({"_id": ObjectId(task_id)})
    except Exception:
        pass

    if not task:
        task = await wbs_tasks_collection.find_one({"id": task_id})

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.get("is_milestone"):
        raise HTTPException(status_code=400, detail="This task is not a milestone")

    update_data = {
        "milestone_completed": completed,
        "status": "done" if completed else "todo",
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await wbs_tasks_collection.update_one(
        {"_id": task["_id"]},
        {"$set": update_data}
    )
    
    # CHANGE-LOG: milestone completion
    try:
        from services.baselines import log_change
        await log_change(
            project_id=str(task.get("project_id") or ""),
            user_email=current_user.get("email"),
            entity_type="wbs_task",
            entity_id=task.get("id") or str(task["_id"]),
            action="update",
            field="milestone_completed",
            old_value=task.get("milestone_completed"),
            new_value=completed,
        )
    except Exception:
        pass

    return {"message": f"Milestone {'completed' if completed else 'uncompleted'} successfully"}


@router.post("/api/wbs/tasks/{task_id}/cascade-dates")
async def cascade_task_dates(
    task_id: str,
    new_end_date: Optional[str] = Query(None),
    current_user: dict = Depends(require_admin),
):
    """Cascade end dates to dependent tasks."""
    task = None
    try:
        task = await wbs_tasks_collection.find_one({"_id": ObjectId(task_id)})
    except Exception:
        pass

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    end_date_str = new_end_date or task.get("end_date")
    if not end_date_str:
        raise HTTPException(status_code=400, detail="No end date specified")

    task_id_str = str(task["_id"])
    updated_count = 0
    visited: set = set()

    async def _cascade(from_task_id_str: str, from_end_date: str):
        nonlocal updated_count
        if from_task_id_str in visited:
            return
        visited.add(from_task_id_str)

        # Find tasks that list from_task_id_str in their dependencies
        dependents = await wbs_tasks_collection.find(
            {"dependencies": from_task_id_str}
        ).to_list(length=1000)

        for dep_task in dependents:
            try:
                end_d = datetime.strptime(from_end_date, "%Y-%m-%d").date()
                new_start = (end_d + timedelta(days=1)).isoformat()
                
                # Calculate and preserve task duration
                old_start = dep_task.get("start_date")
                old_end = dep_task.get("end_date")
                new_end = None
                
                if old_start and old_end:
                    try:
                        old_start_d = datetime.strptime(old_start, "%Y-%m-%d").date()
                        old_end_d = datetime.strptime(old_end, "%Y-%m-%d").date()
                        duration_days = (old_end_d - old_start_d).days
                        
                        # Calculate new end date preserving duration
                        new_start_d = datetime.strptime(new_start, "%Y-%m-%d").date()
                        new_end = (new_start_d + timedelta(days=duration_days)).isoformat()
                    except Exception:
                        pass
            except Exception:
                continue

            dep_id_str = str(dep_task["_id"])
            
            # Update both start and end dates to preserve duration
            update_fields = {
                "start_date": new_start,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            if new_end:
                update_fields["end_date"] = new_end
            
            await wbs_tasks_collection.update_one(
                {"_id": dep_task["_id"]},
                {"$set": update_fields}
            )
            updated_count += 1

            # Recurse with this dependent's new end_date
            dep_end = new_end if new_end else dep_task.get("end_date", from_end_date)
            await _cascade(dep_id_str, dep_end)

    await _cascade(task_id_str, end_date_str)

    return {"message": f"Cascaded dates to {updated_count} tasks", "updated_count": updated_count}


# ============================================================
# WBS Baseline (planned schedule snapshot)
# ============================================================

async def _find_wbs_task(task_id: str):
    """Find a WBS task by Mongo ObjectId or its UUID 'id' field."""
    task = None
    try:
        task = await wbs_tasks_collection.find_one({"_id": ObjectId(task_id)})
    except Exception:
        pass
    if not task:
        task = await wbs_tasks_collection.find_one({"id": task_id})
    return task


@router.post("/api/wbs/tasks/{task_id}/set-baseline")
async def set_wbs_task_baseline(
    task_id: str,
    current_user: dict = Depends(require_admin),
):
    """Snapshot the task's CURRENT start/end dates as its baseline (planned)
    schedule. Used both to set an initial baseline and to re-baseline after a
    legitimate scope change. The change is audit-logged."""
    task = await _find_wbs_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    new_baseline_start = task.get("start_date")
    new_baseline_end = task.get("end_date")

    await wbs_tasks_collection.update_one(
        {"_id": task["_id"]},
        {"$set": {
            "baseline_start_date": new_baseline_start,
            "baseline_end_date": new_baseline_end,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    # Audit log
    try:
        from services.baselines import log_change
        await log_change(
            project_id=str(task.get("project_id") or ""),
            user_email=current_user.get("email"),
            entity_type="wbs_task",
            entity_id=task.get("id") or str(task["_id"]),
            action="set_baseline",
            new_value={
                "baseline_start_date": new_baseline_start,
                "baseline_end_date": new_baseline_end,
            },
        )
    except Exception:
        pass

    updated = await wbs_tasks_collection.find_one({"_id": task["_id"]})
    return serialize_doc(updated)


@router.post("/api/projects/{project_id}/wbs/set-baseline")
async def set_project_wbs_baseline(
    project_id: str,
    current_user: dict = Depends(require_admin),
):
    """Snapshot ALL tasks' current start/end dates as their baseline in one
    action. Convenient after initial planning. Audit-logged at project level."""
    cursor = wbs_tasks_collection.find({"project_id": project_id})
    tasks = await cursor.to_list(length=10000)

    count = 0
    for task in tasks:
        await wbs_tasks_collection.update_one(
            {"_id": task["_id"]},
            {"$set": {
                "baseline_start_date": task.get("start_date"),
                "baseline_end_date": task.get("end_date"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        count += 1

    try:
        from services.baselines import log_change
        await log_change(
            project_id=project_id,
            user_email=current_user.get("email"),
            entity_type="wbs_project",
            entity_id=project_id,
            action="set_baseline_all",
            new_value={"tasks_baselined": count},
        )
    except Exception:
        pass

    return {"message": f"Baseline set for {count} task(s)", "tasks_baselined": count}



# ============================================================
# WBS Actuals Integration
# ============================================================

@router.get("/api/projects/{project_id}/wbs/actuals")
async def get_wbs_actuals(project_id: str, current_user: dict = Depends(get_current_user)):
    """
    Aggregate actual hours from timesheets by WBS task.
    FIX #3: NOW WITH HIERARCHICAL ROLLUP - Child task hours roll up to parents.
    """
    # 1. Get direct timesheet hours (leaf level)
    cursor = timesheets_collection.find({
        "project_id": project_id,
        "task_id": {"$exists": True, "$nin": [None, ""]}
    })
    timesheets = await cursor.to_list(length=10000)

    # Build resource name map
    resources_cursor = resources_collection.find()
    resources_list = await resources_cursor.to_list(length=10000)
    resource_map = {str(r["_id"]): r.get("name", "") for r in resources_list}

    # Build initial task actuals from direct timesheets
    task_actuals: dict = {}
    for ts in timesheets:
        task_id = ts.get("task_id")
        if not task_id:
            continue

        if task_id not in task_actuals:
            task_actuals[task_id] = {
                "task_id": task_id,
                "task_name": ts.get("task_name", ""),
                "actual_hours": 0.0,
                "direct_hours": 0.0,  # NEW: Hours from direct timesheets
                "child_hours": 0.0,   # NEW: Hours rolled up from children
                "timesheet_count": 0,
                "resource_breakdown": []
            }

        hours = float(ts.get("actual_hours", 0) or 0)
        task_actuals[task_id]["direct_hours"] += hours
        task_actuals[task_id]["actual_hours"] += hours
        task_actuals[task_id]["timesheet_count"] += 1

        resource_id = ts.get("resource_id", "")
        resource_name = resource_map.get(resource_id, "Unknown")

        found = False
        for rb in task_actuals[task_id]["resource_breakdown"]:
            if rb["resource_name"] == resource_name:
                rb["actual_hours"] += hours
                found = True
                break
        if not found:
            task_actuals[task_id]["resource_breakdown"].append({
                "resource_name": resource_name,
                "actual_hours": hours
            })

    # 2. Get all WBS tasks to build hierarchy
    all_tasks = await wbs_tasks_collection.find({
        "project_id": project_id
    }).to_list(length=10000)

    # Build parent-child relationships
    children_map = {}  # parent_id -> [child_ids]
    
    for task in all_tasks:
        task_id = str(task["_id"])
        parent_id = task.get("parent_id")
        
        # Initialize task actuals if not already present (tasks with no timesheets)
        if task_id not in task_actuals:
            task_actuals[task_id] = {
                "task_id": task_id,
                "task_name": task.get("name", ""),
                "actual_hours": 0.0,
                "direct_hours": 0.0,
                "child_hours": 0.0,
                "timesheet_count": 0,
                "resource_breakdown": []
            }
        
        if parent_id:
            if parent_id not in children_map:
                children_map[parent_id] = []
            children_map[parent_id].append(task_id)

    # 3. Recursive rollup function
    def get_total_hours_recursive(task_id: str) -> float:
        """Get hours for task + all descendants."""
        # Start with direct hours
        total = task_actuals.get(task_id, {}).get("direct_hours", 0.0)
        
        # Add hours from all children
        if task_id in children_map:
            for child_id in children_map[task_id]:
                total += get_total_hours_recursive(child_id)
        
        return total

    # 4. Calculate rollup for all tasks
    for task_id in task_actuals.keys():
        if task_id in children_map:
            # This task has children - calculate child hours
            child_hours = sum(
                get_total_hours_recursive(child_id) 
                for child_id in children_map[task_id]
            )
            task_actuals[task_id]["child_hours"] = child_hours
            task_actuals[task_id]["actual_hours"] = task_actuals[task_id]["direct_hours"] + child_hours

    # 5. Round all values and add metadata
    result = []
    for task_id, ta in task_actuals.items():
        ta["actual_hours"] = round(ta["actual_hours"], 2)
        ta["direct_hours"] = round(ta["direct_hours"], 2)
        ta["child_hours"] = round(ta["child_hours"], 2)
        ta["has_children"] = task_id in children_map
        ta["is_parent"] = task_id in children_map
        
        # Round resource breakdown
        for rb in ta["resource_breakdown"]:
            rb["actual_hours"] = round(rb["actual_hours"], 2)
        
        # Only return tasks with actual hours (direct or rolled up)
        if ta["actual_hours"] > 0:
            result.append(ta)

    return result


@router.get("/api/projects/{project_id}/wbs/tasks-for-timesheet")
async def get_wbs_tasks_for_timesheet(
    project_id: str,
    phase_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Lightweight task list for timesheet task dropdown."""
    query: dict = {"project_id": project_id}
    if phase_id:
        query["phase_id"] = phase_id

    cursor = wbs_tasks_collection.find(query).sort([("order", 1), ("name", 1)])
    tasks = await cursor.to_list(length=10000)

    result = []
    for task in tasks:
        result.append({
            "id": str(task["_id"]),
            "name": task.get("name", ""),
            "phase_name": task.get("phase_name", ""),
            "status": task.get("status", "todo"),
            "estimated_hours": task.get("estimated_hours", 0)
        })
    return result


# ============================================================
# AI WBS Generation
# ============================================================

@router.post("/api/ai/generate-wbs")
async def generate_wbs(
    request: AIGenerateWBSRequest,
    current_user: dict = Depends(require_admin),
):
    """AI-generate a WBS for a project. Returns preview (does NOT save to DB)."""
    # Load project
    project = await projects_collection.find_one({"_id": ObjectId(request.project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Load ONLY resources allocated to this project
    from database import allocations_collection
    allocations = await allocations_collection.find({
        "project_id": request.project_id
    }).to_list(length=10000)
    
    allocated_resource_ids = list(set(a.get("resource_id") for a in allocations if a.get("resource_id")))
    
    # Fetch allocated resources only
    if allocated_resource_ids:
        try:
            resources_list = await resources_collection.find({
                "_id": {"$in": [ObjectId(rid) for rid in allocated_resource_ids]}
            }).to_list(length=10000)
        except Exception:
            # Fallback to all resources if ObjectId conversion fails
            resources_list = await resources_collection.find().to_list(length=10000)
    else:
        # No allocations yet - use all resources as fallback
        resources_list = await resources_collection.find().to_list(length=10000)
    
    resource_names = [r.get("name", "") for r in resources_list]
    resource_map_by_name = {r.get("name", "").lower(): str(r["_id"]) for r in resources_list}

    # Extract project phases
    phases = project.get("phases", [])
    phase_names = [p.get("name", "") if isinstance(p, dict) else str(p) for p in phases]
    phase_map_by_name = {
        (p.get("name", "") if isinstance(p, dict) else str(p)).lower(): p.get("id", "") if isinstance(p, dict) else ""
        for p in phases
    }

    # NEW: Build phase-specific resource allocations for AI context
    from utils import get_allocation_for_phase
    
    phase_resource_info = []
    for p in phases:
        if isinstance(p, dict):
            phase_id = p.get("id", "")
            phase_name = p.get("name", "Unknown")
            
            # Get resources allocated to this phase
            phase_resources = []
            for alloc in allocations:
                phase_percentage = get_allocation_for_phase(alloc, phase_id)
                if phase_percentage > 0:
                    # Find resource name
                    resource_id = alloc.get("resource_id")
                    resource = next((r for r in resources_list if str(r["_id"]) == resource_id), None)
                    if resource:
                        phase_resources.append(f"{resource.get('name', 'Unknown')} ({phase_percentage}%)")
            
            resources_str = ', '.join(phase_resources) if phase_resources else 'No resources allocated'
            phase_resource_info.append(
                f"  - {phase_name} ({p.get('start_date', '?')} to {p.get('end_date', '?')}): {resources_str}"
            )
        else:
            phase_resource_info.append(f"  - {p}")

    # Build context
    phase_info = []
    for p in phases:
        if isinstance(p, dict):
            phase_info.append(f"  - {p.get('name', 'Unknown')} ({p.get('start_date', '?')} to {p.get('end_date', '?')})")
        else:
            phase_info.append(f"  - {p}")

    project_context = f"""
Project: {project.get('name', 'Unknown')}
Client: {project.get('client_name', 'Unknown')}
Start Date: {project.get('start_date', 'Unknown')}
End Date: {project.get('end_date', 'Unknown')}
Objective: {project.get('project_objective', 'Not specified')}

Phases:
{chr(10).join(phase_info) if phase_info else '  - No phases defined'}

Phase-Specific Resource Allocations:
{chr(10).join(phase_resource_info) if phase_resource_info else '  - No phase allocations defined'}

All Team Members (for reference): {', '.join(resource_names) if resource_names else 'No team members assigned yet'}

Additional Context: {request.additional_context or 'None'}
Primary Deliverables: {request.primary_deliverables or 'Not specified'}
Complexity: {request.complexity or 'standard'}
Include Sub-tasks: {request.include_subtasks}
"""

    complexity_guidance = {
        "simple": "5-8 main tasks, minimal sub-tasks",
        "standard": "8-15 main tasks, 2-3 sub-tasks per main task if include_subtasks=true",
        "detailed": "15-25 main tasks, 3-5 sub-tasks per main task if include_subtasks=true"
    }

    system_prompt = f"""You are a professional project management consultant who creates detailed Work Breakdown Structures (WBS).
Generate a comprehensive WBS for the given project.

RULES:
- Return ONLY valid JSON (no markdown, no code blocks, no explanation)
- Use exact phase names from the project (or null if no phases match)
- Use exact resource names from the team list (or null if unknown)
- **IMPORTANT**: Only assign resources to tasks in phases where they have an allocation > 0%
- If a resource has 0% allocation in a phase, DO NOT assign them to tasks in that phase
- Respect the allocation percentages when distributing work - higher % = more tasks/hours
- Complexity guidance: {complexity_guidance.get(request.complexity or 'standard', complexity_guidance['standard'])}
- Sub-tasks should have parent_temp_id set to their parent's temp_id
- estimated_hours must be a positive number
- status should be "todo" for all new tasks
- priorities: low, medium, high, critical
- start_date_offset is days from project start date

JSON FORMAT:
{{
  "tasks": [
    {{
      "temp_id": "t1",
      "name": "Task name",
      "description": "Brief description of what this task involves",
      "phase_name": "Phase name (exactly as listed) or null",
      "parent_temp_id": null,
      "assigned_to": "Resource full name or null",
      "status": "todo",
      "priority": "medium",
      "estimated_hours": 16,
      "duration_days": 3,
      "start_date_offset": 0,
      "dependencies": [],
      "labels": []
    }}
  ]
}}"""

    user_message = f"Create a WBS for this project:\n{project_context}"

    # Inject custom AI instructions for WBS generation
    custom_instructions = await get_instructions_for_prompt(category="wbs_generation", project_id=request.project_id)
    effective_prompt = system_prompt + custom_instructions

    ai_result = await _call_wbs_ai(request.provider, request.api_key, effective_prompt, user_message)

    if not ai_result:
        raise HTTPException(status_code=500, detail="AI service unavailable. Please configure an AI key in Settings.")

    raw_tasks = ai_result.get("tasks", [])
    if not raw_tasks:
        # Try top-level list
        if isinstance(ai_result, list):
            raw_tasks = ai_result
        else:
            raise HTTPException(status_code=500, detail="AI returned unexpected format. Please try again.")

    # Enrich tasks with phase_id and assigned_to_id
    enriched_tasks = []
    for task in raw_tasks:
        enriched = dict(task)
        # Map phase_name → phase_id
        phase_name = task.get("phase_name") or ""
        enriched["phase_id"] = phase_map_by_name.get(phase_name.lower(), "") or None

        # Map assigned_to name → resource_id
        assigned_name = task.get("assigned_to") or ""
        enriched["assigned_to_id"] = resource_map_by_name.get(assigned_name.lower()) or None

        enriched_tasks.append(enriched)

    return {
        "tasks": enriched_tasks,
        "project_id": request.project_id,
        "project_name": project.get("name", ""),
        "phases": phase_names,
        "team": resource_names,
    }


@router.post("/api/ai/generate-wbs/save")
async def save_generated_wbs(
    request: SaveGeneratedWBSRequest,
    current_user: dict = Depends(require_admin),
):
    """Save AI-generated WBS tasks to the database."""
    project_id = request.project_id
    tasks_input = request.tasks
    plan_start_date = request.start_date

    if not tasks_input:
        raise HTTPException(status_code=400, detail="No tasks provided")

    # Build temp_id → saved_id map
    temp_to_real: dict = {}

    # Two-pass save: root tasks first, then sub-tasks
    def _sort_key(t):
        """Sort root tasks before sub-tasks."""
        return 0 if not t.get("parent_temp_id") else 1

    sorted_tasks = sorted(tasks_input, key=_sort_key)

    saved_count = 0
    for task in sorted_tasks:
        temp_id = task.get("temp_id", str(uuid_module.uuid4()))
        parent_temp_id = task.get("parent_temp_id")

        # Calculate start_date from offset if provided
        start_date = task.get("start_date") or None
        if not start_date and plan_start_date and task.get("start_date_offset") is not None:
            try:
                from datetime import date as date_type
                base = datetime.strptime(plan_start_date, "%Y-%m-%d").date()
                offset = int(task.get("start_date_offset", 0))
                start_date = (base + timedelta(days=offset)).isoformat()
            except Exception:
                pass

        # Calculate end_date from start + duration
        end_date = task.get("end_date") or None
        if not end_date and start_date and task.get("duration_days"):
            try:
                start_d = datetime.strptime(start_date, "%Y-%m-%d").date()
                duration = int(task.get("duration_days", 1))
                end_date = (start_d + timedelta(days=duration - 1)).isoformat()
            except Exception:
                pass

        # Resolve parent_id from temp_to_real map
        parent_id = None
        if parent_temp_id and parent_temp_id in temp_to_real:
            parent_id = temp_to_real[parent_temp_id]

        # Resolve dependencies (filter to already-saved real IDs)
        dep_temp_ids = task.get("dependencies") or []
        dependencies = [temp_to_real[d] for d in dep_temp_ids if d in temp_to_real]

        task_doc = {
            "id": str(uuid_module.uuid4()),
            "project_id": project_id,
            "name": task.get("name", "Unnamed Task"),
            "description": task.get("description", ""),
            "phase_id": task.get("phase_id") or None,
            "phase_name": task.get("phase_name") or None,
            "parent_id": parent_id,
            "assigned_to": task.get("assigned_to_id") or task.get("assigned_to") or None,
            "status": task.get("status", "todo"),
            "priority": task.get("priority", "medium"),
            "estimated_hours": float(task.get("estimated_hours", 0) or 0),
            "actual_hours": 0.0,
            "start_date": start_date,
            "end_date": end_date,
            "order": saved_count,
            "dependencies": dependencies,
            "labels": task.get("labels") or [],
            "created_by": current_user.get("email", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        result = await wbs_tasks_collection.insert_one(task_doc)
        real_id = str(result.inserted_id)
        temp_to_real[temp_id] = real_id
        saved_count += 1

    return {"message": f"Saved {saved_count} tasks successfully", "saved_count": saved_count}



# ============================================================
# PROJECT WBS SUMMARY (FIX #2)
# ============================================================

@router.get("/api/projects/{project_id}/wbs/summary")
async def get_project_wbs_summary(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get project-level WBS summary with estimated vs actual hours.
    Connects WBS planning to project budget tracking.
    
    Returns:
    - Total estimated hours (sum of all WBS tasks)
    - Total actual hours (from timesheets linked to WBS tasks)
    - Completion percentage
    - Tasks completed vs total
    - Phase-level breakdown
    """
    
    # 1. Get all WBS tasks for this project
    wbs_tasks = await wbs_tasks_collection.find({
        "project_id": project_id
    }).to_list(length=10000)
    
    if not wbs_tasks:
        # No WBS tasks - return empty summary
        return {
            "project_id": project_id,
            "total_estimated_hours": 0,
            "total_actual_hours": 0,
            "completion_percentage": 0,
            "variance_hours": 0,
            "tasks_completed": 0,
            "tasks_total": 0,
            "task_completion_pct": 0,
            "phases": [],
            "has_wbs": False
        }
    
    # 2. Calculate totals from WBS tasks
    total_estimated = sum(task.get("estimated_hours", 0) for task in wbs_tasks)
    tasks_completed = sum(1 for t in wbs_tasks if t.get("status") == "done")
    tasks_total = len(wbs_tasks)
    
    # 3. Get actual hours from timesheets (only for WBS-linked timesheets)
    pipeline = [
        {
            "$match": {
                "project_id": project_id,
                "task_id": {"$exists": True, "$ne": None}
            }
        },
        {
            "$group": {
                "_id": None,
                "total_actual": {"$sum": "$actual_hours"}
            }
        }
    ]
    
    actuals_result = await timesheets_collection.aggregate(pipeline).to_list(1)
    total_actual = actuals_result[0]["total_actual"] if actuals_result else 0.0
    
    # 4. Calculate completion metrics
    completion_pct = (total_actual / total_estimated * 100) if total_estimated > 0 else 0
    variance = total_actual - total_estimated
    task_completion_pct = (tasks_completed / tasks_total * 100) if tasks_total > 0 else 0
    
    # 5. Build phase-level breakdown
    phase_summary = {}
    for task in wbs_tasks:
        phase_id = task.get("phase_id") or "unassigned"
        phase_name = task.get("phase_name") or "Unassigned"
        
        if phase_id not in phase_summary:
            phase_summary[phase_id] = {
                "phase_id": phase_id,
                "phase_name": phase_name,
                "estimated_hours": 0,
                "actual_hours": 0,
                "tasks_count": 0,
                "tasks_completed": 0
            }
        
        phase_summary[phase_id]["estimated_hours"] += task.get("estimated_hours", 0)
        phase_summary[phase_id]["tasks_count"] += 1
        if task.get("status") == "done":
            phase_summary[phase_id]["tasks_completed"] += 1
    
    # 6. Add actual hours to phases (via aggregation)
    phase_actuals_pipeline = [
        {
            "$match": {
                "project_id": project_id,
                "task_id": {"$exists": True, "$ne": None}
            }
        },
        {
            "$addFields": {
                "task_id_obj": {"$toObjectId": "$task_id"}
            }
        },
        {
            "$lookup": {
                "from": "wbs_tasks",
                "localField": "task_id_obj",
                "foreignField": "_id",
                "as": "task"
            }
        },
        {"$unwind": {"path": "$task", "preserveNullAndEmptyArrays": True}},
        {
            "$group": {
                "_id": "$task.phase_id",
                "actual_hours": {"$sum": "$actual_hours"}
            }
        }
    ]
    
    try:
        phase_actuals = await timesheets_collection.aggregate(phase_actuals_pipeline).to_list(100)
        for pa in phase_actuals:
            phase_id = pa["_id"] or "unassigned"
            if phase_id in phase_summary:
                phase_summary[phase_id]["actual_hours"] = round(pa["actual_hours"], 2)
    except Exception as e:
        # If aggregation fails (e.g., task_id not ObjectId), continue with 0 actuals
        print(f"[WBS Summary] Phase actuals aggregation failed (non-critical): {e}")
    
    # 7. Calculate phase completion percentages
    for phase in phase_summary.values():
        if phase["estimated_hours"] > 0:
            phase["completion_pct"] = round((phase["actual_hours"] / phase["estimated_hours"]) * 100, 1)
        else:
            phase["completion_pct"] = 0
        
        if phase["tasks_count"] > 0:
            phase["task_completion_pct"] = round((phase["tasks_completed"] / phase["tasks_count"]) * 100, 1)
        else:
            phase["task_completion_pct"] = 0
    
    return {
        "project_id": project_id,
        "total_estimated_hours": round(total_estimated, 2),
        "total_actual_hours": round(total_actual, 2),
        "completion_percentage": round(completion_pct, 1),
        "variance_hours": round(variance, 2),
        "tasks_completed": tasks_completed,
        "tasks_total": tasks_total,
        "task_completion_pct": round(task_completion_pct, 1),
        "phases": sorted(phase_summary.values(), key=lambda x: x["phase_name"]),
        "has_wbs": True
    }


# ============================================================
# WBS → Project Date Sync
# ============================================================

@router.post("/api/projects/{project_id}/sync-dates-from-wbs")
async def sync_project_dates_from_wbs(
    project_id: str,
    current_user: dict = Depends(require_admin)
):
    """
    Manually sync project and phase end dates based on WBS task end dates.
    Finds the latest WBS task end_date and updates:
    - Project end_date
    - Last phase end_date
    Returns a summary of changes made.
    """
    # Get project
    project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get all WBS tasks for this project
    wbs_tasks = await wbs_tasks_collection.find({
        "project_id": project_id,
        "end_date": {"$exists": True, "$ne": None}
    }).to_list(length=10000)
    
    if not wbs_tasks:
        raise HTTPException(
            status_code=400,
            detail="No WBS tasks with end dates found. Cannot sync dates."
        )
    
    # Find latest WBS end date
    latest_wbs_end = None
    latest_task_name = None
    
    for task in wbs_tasks:
        end_date_str = task.get("end_date")
        if not end_date_str:
            continue
        
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            if latest_wbs_end is None or end_date > latest_wbs_end:
                latest_wbs_end = end_date
                latest_task_name = task.get("name", "Unknown")
        except Exception:
            continue
    
    if not latest_wbs_end:
        raise HTTPException(
            status_code=400,
            detail="Could not parse any WBS end dates. Cannot sync."
        )
    
    # Convert to datetime for MongoDB
    latest_wbs_end_dt = datetime.combine(latest_wbs_end, datetime.min.time())
    
    # Current project end date
    current_project_end = project.get("end_date")
    if isinstance(current_project_end, datetime):
        current_project_end = current_project_end.date()
    
    changes = []
    
    # Update project end_date if different
    if current_project_end != latest_wbs_end:
        await projects_collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {"end_date": latest_wbs_end_dt}}
        )
        changes.append({
            "entity": "Project",
            "field": "end_date",
            "old_value": current_project_end.isoformat() if current_project_end else None,
            "new_value": latest_wbs_end.isoformat()
        })
    
    # Update last phase end_date
    phases = project.get("phases", [])
    if phases:
        last_phase = phases[-1]
        last_phase_end = last_phase.get("end_date")
        
        if isinstance(last_phase_end, datetime):
            last_phase_end = last_phase_end.date()
        elif isinstance(last_phase_end, str):
            try:
                last_phase_end = datetime.strptime(last_phase_end, "%Y-%m-%d").date()
            except Exception:
                last_phase_end = None
        
        if last_phase_end != latest_wbs_end:
            # Update the last phase
            phases[-1]["end_date"] = latest_wbs_end_dt
            
            await projects_collection.update_one(
                {"_id": ObjectId(project_id)},
                {"$set": {"phases": phases}}
            )
            
            changes.append({
                "entity": f"Phase: {last_phase.get('name', 'Unknown')}",
                "field": "end_date",
                "old_value": last_phase_end.isoformat() if last_phase_end else None,
                "new_value": latest_wbs_end.isoformat()
            })
    
    if not changes:
        return {
            "message": "Project and phase dates are already in sync with WBS",
            "latest_wbs_end_date": latest_wbs_end.isoformat(),
            "latest_task": latest_task_name,
            "changes": []
        }
    
    return {
        "message": f"Successfully synced dates from WBS. {len(changes)} update(s) made.",
        "latest_wbs_end_date": latest_wbs_end.isoformat(),
        "latest_task": latest_task_name,
        "changes": changes
    }
