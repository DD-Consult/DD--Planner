"""AI action execution, pre-state capture, undo spec building, and undo application."""
from datetime import datetime, timezone
import re
import uuid
from bson import ObjectId

from database import (
    projects_collection, allocations_collection, risks_collection,
    status_updates_collection, wbs_tasks_collection,
)
from utils import serialize_doc

# All AI-proposed actions are auto-executed server-side.
AUTO_EXECUTE_ACTIONS = {
    "create_project",
    "create_allocation",
    "update_allocation",
    "remove_allocation",
    "update_project_status",
    "update_project_dates",
    "add_risk",
    "update_risk",
    "set_project_lead",
    "bulk_set_project_lead",
    "create_status_update",
    # FIX #4: WBS Actions
    "generate_wbs",
    "create_wbs_task",
    "update_wbs_task",
    "delete_wbs_task",
    "assign_wbs_task",
}


async def execute_ai_action(action: dict, current_user: dict) -> dict:
    """Internal dispatch for AI-proposed actions. Returns {success, message, ...}."""
    action_type = action.get("action")

    try:
        if action_type == "create_project":
            # Validate project_lead_id — only accept 24-char hex ObjectId strings
            raw_lead_id = action.get("project_lead_id")
            valid_lead_id = None
            if raw_lead_id and isinstance(raw_lead_id, str) and re.match(r'^[a-fA-F0-9]{24}$', raw_lead_id):
                valid_lead_id = raw_lead_id

            project_doc = {
                "name": action["name"],
                "client_name": action.get("client_name", ""),
                "status": action.get("status", "Pipeline"),
                "start_date": datetime.strptime(action["start_date"], "%Y-%m-%d"),
                "end_date": datetime.strptime(action["end_date"], "%Y-%m-%d"),
                "is_draft": False,
                "budgeted_hours": action.get("budgeted_hours"),
                "project_lead_id": valid_lead_id,
                "google_drive_url": action.get("google_drive_url"),
                "phases": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            result = await projects_collection.insert_one(project_doc)
            return {"success": True, "message": f"Project '{action['name']}' created successfully", "id": str(result.inserted_id)}

        elif action_type == "create_allocation":
            alloc_data = {
                "resource_id": action["resource_id"],
                "project_id": action["project_id"],
                "percentage": action.get("percentage", 100),
                "start_date": datetime.strptime(action["start_date"], "%Y-%m-%d"),
                "end_date": datetime.strptime(action["end_date"], "%Y-%m-%d"),
                "allocation_type": "percentage",
                "confirmation_status": "Pending",
                "role": action.get("role", ""),
                "phase_names": [],
            }
            result = await allocations_collection.insert_one(alloc_data)
            return {"success": True, "message": "Allocation created successfully", "id": str(result.inserted_id)}

        elif action_type == "update_allocation":
            update_data = {}
            if "percentage" in action:
                update_data["percentage"] = action["percentage"]
            if "start_date" in action:
                update_data["start_date"] = datetime.strptime(action["start_date"], "%Y-%m-%d")
            if "end_date" in action:
                update_data["end_date"] = datetime.strptime(action["end_date"], "%Y-%m-%d")
            await allocations_collection.update_one(
                {"_id": ObjectId(action["allocation_id"])},
                {"$set": update_data}
            )
            return {"success": True, "message": "Allocation updated successfully"}

        elif action_type == "remove_allocation":
            result = await allocations_collection.delete_one({"_id": ObjectId(action["allocation_id"])})
            if result.deleted_count > 0:
                return {"success": True, "message": "Allocation removed successfully"}
            return {"success": False, "message": "Allocation not found"}

        elif action_type == "update_project_status":
            await projects_collection.update_one(
                {"_id": ObjectId(action["project_id"])},
                {"$set": {"status": action["status"]}}
            )
            return {"success": True, "message": f"Project status updated to {action['status']}"}

        elif action_type == "update_project_dates":
            update_data = {}
            if "start_date" in action:
                update_data["start_date"] = datetime.strptime(action["start_date"], "%Y-%m-%d")
            if "end_date" in action:
                update_data["end_date"] = datetime.strptime(action["end_date"], "%Y-%m-%d")
            await projects_collection.update_one(
                {"_id": ObjectId(action["project_id"])},
                {"$set": update_data}
            )
            return {"success": True, "message": "Project dates updated successfully"}

        elif action_type == "add_risk":
            # Use the shared polishing helper so AI runs on AI-Action-created risks too
            from routes.projects import _build_polished_risk_doc
            project = await projects_collection.find_one({"_id": ObjectId(action["project_id"])})
            risk_data = await _build_polished_risk_doc(
                {
                    "description": action["description"],
                    "impact": action.get("impact", "Medium"),
                    "probability": action.get("probability", "Medium"),
                    "mitigation": action.get("mitigation"),
                    "status": action.get("status", "Active"),
                    "category": action.get("category", "Risk"),
                },
                project_id=action["project_id"],
                project=project,
            )
            result = await risks_collection.insert_one(risk_data)
            return {"success": True, "message": "Risk added successfully", "id": str(result.inserted_id)}

        elif action_type == "update_risk":
            update_data = {}
            for f in ("description", "impact", "probability", "mitigation", "status", "category"):
                if f in action and action[f] is not None:
                    update_data[f] = action[f]
            if not update_data:
                return {"success": False, "message": "No fields to update"}
            update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            await risks_collection.update_one(
                {"_id": ObjectId(action["risk_id"])},
                {"$set": update_data},
            )
            return {"success": True, "message": "Risk updated successfully"}

        elif action_type == "create_status_update":
            project = await projects_collection.find_one({"_id": ObjectId(action["project_id"])})
            if not project:
                return {"success": False, "message": "Project not found"}

            now_dt = datetime.now(timezone.utc)
            effective_progress = action.get("actual_progress", project.get("actual_progress", 0))

            status_doc = {
                "project_id": action["project_id"],
                "updated_by": current_user.get("email"),
                "updated_by_name": current_user.get("email", "AI Assistant"),
                "update_date": now_dt.strftime("%Y-%m-%d"),
                "week_start_date": now_dt,
                "health": action.get("health", "Green"),
                "schedule_status": action.get("schedule_status", "On Track"),
                "actual_progress": effective_progress,
                "accomplishments": action.get("accomplishments"),
                "progress_summary": action.get("accomplishments"),
                "blockers": [b.strip() for b in re.split(r"[,\n]+", action.get("blockers", "")) if b.strip()] if action.get("blockers") else [],
                "next_steps": action.get("next_steps"),
                "next_week_plan": action.get("next_steps"),
                "notes": action.get("notes"),
                "ai_generated_summary": None,
                "created_at": now_dt,
                "ai_generated": True,
            }
            su_result = await status_updates_collection.insert_one(status_doc)
            status_update_id = str(su_result.inserted_id)

            # Auto-promote blockers to issues (deduped) — polished by AI
            created_issue_ids = []
            if action.get("blockers"):
                from routes.projects import _build_polished_risk_doc
                blocker_items = [b.strip() for b in re.split(r"[,\n]+", action["blockers"]) if b.strip()]
                existing = await risks_collection.find({"project_id": action["project_id"]}).to_list(length=500)
                existing_desc = {r.get("description", "").strip().lower() for r in existing}
                for b_text in blocker_items:
                    if b_text.lower() in existing_desc:
                        continue
                    r_doc = await _build_polished_risk_doc(
                        {
                            "description": b_text,
                            "impact": "Medium",
                            "probability": "High",
                            "mitigation": action.get("next_steps"),
                            "status": "Active",
                            "category": "Issue",
                        },
                        project_id=action["project_id"],
                        project=project,
                        extra_fields={"source_status_update_id": status_update_id},
                    )
                    r_result = await risks_collection.insert_one(r_doc)
                    created_issue_ids.append(str(r_result.inserted_id))

            await projects_collection.update_one(
                {"_id": ObjectId(action["project_id"])},
                {"$set": {
                    "health": status_doc["health"],
                    "schedule_status": status_doc["schedule_status"],
                    "actual_progress": effective_progress,
                    "last_status_update": now_dt,
                }}
            )

            msg = f"Status update submitted for '{project.get('name')}'."
            if created_issue_ids:
                msg += f" Auto-created {len(created_issue_ids)} issue(s) from blockers."
            return {"success": True, "message": msg, "id": status_update_id, "issues_created": len(created_issue_ids)}

        elif action_type == "set_project_lead":
            await projects_collection.update_one(
                {"_id": ObjectId(action["project_id"])},
                {"$set": {"project_lead_id": action["resource_id"]}}
            )
            return {"success": True, "message": "Project lead updated"}

        elif action_type == "bulk_set_project_lead":
            resource_id = action.get("resource_id")
            force_all = action.get("force_all", False)
            if force_all:
                result = await projects_collection.update_many(
                    {},
                    {"$set": {"project_lead_id": resource_id}}
                )
            else:
                result = await projects_collection.update_many(
                    {"$or": [{"project_lead_id": None}, {"project_lead_id": {"$exists": False}}, {"project_lead_id": ""}]},
                    {"$set": {"project_lead_id": resource_id}}
                )
            return {"success": True, "message": f"Updated {result.modified_count} projects with new lead"}

        # ============================================================
        # FIX #4: WBS ACTIONS
        # ============================================================
        
        elif action_type == "generate_wbs":
            """AI-generate WBS tasks for a project."""
            from services.ai_providers import call_emergent_fallback
            
            # Get project details
            project = await projects_collection.find_one({"_id": ObjectId(action["project_id"])})
            if not project:
                return {"success": False, "message": "Project not found"}
            
            # Build AI prompt
            phases_str = ", ".join([p.get("name", "") for p in project.get("phases", []) if isinstance(p, dict)])
            
            system_prompt = f"""Generate a Work Breakdown Structure for this project.
Return ONLY valid JSON with a "tasks" array. Each task: name, description, estimated_hours, priority (low/medium/high/critical), phase_name.
Complexity: {action.get('complexity', 'standard')} (simple=5-8 tasks, standard=8-15, detailed=15-25)"""
            
            user_message = f"""Project: {project.get('name')}
Client: {project.get('client_name')}
Objective: {project.get('project_objective', 'Not specified')}
Phases: {phases_str or 'None'}
Context: {action.get('additional_context', '')}"""
            
            # Call AI with Emergent fallback
            ai_result = await call_emergent_fallback(system_prompt, user_message)
            
            if not ai_result or "tasks" not in ai_result:
                return {"success": False, "message": "AI failed to generate WBS"}
            
            # Save tasks to WBS collection
            tasks = ai_result.get("tasks", [])
            saved_count = 0
            
            for idx, task in enumerate(tasks[:25]):  # Limit to 25 tasks for safety
                task_doc = {
                    "id": str(uuid.uuid4()),
                    "project_id": action["project_id"],
                    "name": task.get("name", "Unnamed Task"),
                    "description": task.get("description", ""),
                    "phase_id": None,
                    "phase_name": task.get("phase_name"),
                    "parent_id": None,
                    "assigned_to": None,
                    "status": "todo",
                    "priority": task.get("priority", "medium"),
                    "estimated_hours": float(task.get("estimated_hours", 8)),
                    "actual_hours": 0.0,
                    "start_date": None,
                    "end_date": None,
                    "order": idx,
                    "dependencies": [],
                    "labels": [],
                    "created_by": current_user.get("email", "ai"),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                await wbs_tasks_collection.insert_one(task_doc)
                saved_count += 1
            
            return {
                "success": True,
                "message": f"Generated {saved_count} WBS tasks for {project.get('name')}",
                "tasks_created": saved_count
            }
        
        elif action_type == "create_wbs_task":
            """Create a single WBS task."""
            task_doc = {
                "id": str(uuid.uuid4()),
                "project_id": action["project_id"],
                "name": action["name"],
                "description": action.get("description", ""),
                "phase_id": action.get("phase_id"),
                "phase_name": action.get("phase_name"),
                "parent_id": action.get("parent_id"),
                "assigned_to": action.get("assigned_to"),
                "status": action.get("status", "todo"),
                "priority": action.get("priority", "medium"),
                "estimated_hours": float(action.get("estimated_hours", 0)),
                "actual_hours": 0.0,
                "start_date": action.get("start_date"),
                "end_date": action.get("end_date"),
                "order": action.get("order", 0),
                "dependencies": action.get("dependencies", []),
                "labels": action.get("labels", []),
                "created_by": current_user.get("email", "ai"),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            result = await wbs_tasks_collection.insert_one(task_doc)
            return {
                "success": True,
                "message": f"Created WBS task: {action['name']}",
                "task_id": str(result.inserted_id)
            }
        
        elif action_type == "update_wbs_task":
            """Update a WBS task."""
            update_data = {}
            allowed_fields = [
                "name", "description", "status", "priority", "estimated_hours",
                "assigned_to", "start_date", "end_date", "labels"
            ]
            for field in allowed_fields:
                if field in action:
                    update_data[field] = action[field]
            
            if not update_data:
                return {"success": False, "message": "No update fields provided"}
            
            update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            result = await wbs_tasks_collection.update_one(
                {"_id": ObjectId(action["task_id"])},
                {"$set": update_data}
            )
            
            if result.matched_count > 0:
                return {"success": True, "message": "WBS task updated"}
            return {"success": False, "message": "Task not found"}
        
        elif action_type == "delete_wbs_task":
            """Delete a WBS task."""
            result = await wbs_tasks_collection.delete_one({"_id": ObjectId(action["task_id"])})
            if result.deleted_count > 0:
                return {"success": True, "message": "WBS task deleted"}
            return {"success": False, "message": "Task not found"}
        
        elif action_type == "assign_wbs_task":
            """Assign a WBS task to a team member."""
            result = await wbs_tasks_collection.update_one(
                {"_id": ObjectId(action["task_id"])},
                {"$set": {
                    "assigned_to": action["resource_id"],
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            if result.matched_count > 0:
                return {"success": True, "message": "Task assigned to team member"}
            return {"success": False, "message": "Task not found"}

        else:
            return {"success": False, "message": f"Unknown action: {action_type}"}

    except Exception as e:
        return {"success": False, "message": f"Action failed: {str(e)[:200]}"}


async def capture_pre_state(action: dict) -> dict:
    """Snapshot the state that will change, so we can reverse it later."""
    t = action.get("action")
    try:
        if t == "update_allocation":
            doc = await allocations_collection.find_one({"_id": ObjectId(action["allocation_id"])})
            return {"before": serialize_doc(doc) if doc else None}
        if t == "remove_allocation":
            doc = await allocations_collection.find_one({"_id": ObjectId(action["allocation_id"])})
            return {"before": serialize_doc(doc) if doc else None}
        if t == "update_project_status":
            p = await projects_collection.find_one({"_id": ObjectId(action["project_id"])}, {"status": 1})
            return {"before_status": (p or {}).get("status")}
        if t == "update_project_dates":
            p = await projects_collection.find_one({"_id": ObjectId(action["project_id"])}, {"start_date": 1, "end_date": 1})
            if p:
                sd = p.get("start_date")
                ed = p.get("end_date")
                return {
                    "before_start": sd.strftime("%Y-%m-%d") if isinstance(sd, datetime) else sd,
                    "before_end": ed.strftime("%Y-%m-%d") if isinstance(ed, datetime) else ed,
                }
            return {}
        if t == "update_risk":
            doc = await risks_collection.find_one({"_id": ObjectId(action["risk_id"])})
            return {"before": serialize_doc(doc) if doc else None}
        if t == "set_project_lead":
            p = await projects_collection.find_one({"_id": ObjectId(action["project_id"])}, {"project_lead_id": 1})
            return {"before_lead": (p or {}).get("project_lead_id")}
        if t == "bulk_set_project_lead":
            cursor = projects_collection.find({}, {"_id": 1, "project_lead_id": 1})
            snapshot = {}
            async for p in cursor:
                snapshot[str(p["_id"])] = p.get("project_lead_id")
            return {"snapshot": snapshot}
    except Exception as e:
        print(f"[capture_pre_state] error: {e}")
    return {}


def build_undo_spec(action_type: str, action: dict, pre_state: dict, result: dict) -> dict | None:
    """Map each action to a reversal spec. Returns None if not reversible or execution failed."""
    if not result or not result.get("success"):
        return None
    new_id = result.get("id")
    if action_type == "create_project":
        return {"op": "delete_project", "id": new_id, "label": "Undo project creation"}
    if action_type == "create_allocation":
        return {"op": "delete_allocation", "id": new_id, "label": "Undo allocation"}
    if action_type == "remove_allocation":
        before = pre_state.get("before")
        if not before:
            return None
        return {"op": "recreate_allocation", "doc": before, "label": "Restore allocation"}
    if action_type == "update_allocation":
        before = pre_state.get("before")
        if not before:
            return None
        return {"op": "restore_allocation", "id": action["allocation_id"], "doc": before, "label": "Revert allocation changes"}
    if action_type == "update_project_status":
        return {"op": "set_project_status", "id": action["project_id"], "status": pre_state.get("before_status"), "label": "Revert project status"}
    if action_type == "update_project_dates":
        return {
            "op": "set_project_dates",
            "id": action["project_id"],
            "start_date": pre_state.get("before_start"),
            "end_date": pre_state.get("before_end"),
            "label": "Revert project dates",
        }
    if action_type == "add_risk":
        return {"op": "delete_risk", "id": new_id, "label": "Undo risk/issue"}
    if action_type == "update_risk":
        before = pre_state.get("before")
        if not before:
            return None
        return {"op": "restore_risk", "id": action["risk_id"], "doc": before, "label": "Revert risk changes"}
    if action_type == "set_project_lead":
        return {"op": "set_project_lead", "id": action["project_id"], "resource_id": pre_state.get("before_lead"), "label": "Revert project lead"}
    if action_type == "bulk_set_project_lead":
        return {"op": "bulk_restore_lead", "snapshot": pre_state.get("snapshot", {}), "label": "Revert bulk lead change"}
    if action_type == "create_status_update":
        return {"op": "delete_status_update", "id": new_id, "label": "Undo status update"}
    return None


async def apply_undo(spec: dict) -> dict:
    """Reverse a previously-executed action using its undo spec."""
    op = spec.get("op")
    try:
        if op == "delete_project":
            await projects_collection.delete_one({"_id": ObjectId(spec["id"])})
            return {"success": True, "message": "Project creation undone"}
        if op == "delete_allocation":
            await allocations_collection.delete_one({"_id": ObjectId(spec["id"])})
            return {"success": True, "message": "Allocation undone"}
        if op == "recreate_allocation":
            doc = dict(spec["doc"] or {})
            original_id = doc.pop("id", None)
            doc.pop("_id", None)
            for k in ("start_date", "end_date"):
                v = doc.get(k)
                if isinstance(v, str):
                    try:
                        doc[k] = datetime.fromisoformat(v.replace("Z", "+00:00"))
                    except Exception:
                        pass
            if original_id:
                try:
                    doc["_id"] = ObjectId(original_id)
                except Exception:
                    pass
            await allocations_collection.insert_one(doc)
            return {"success": True, "message": "Allocation restored"}
        if op == "restore_allocation":
            doc = dict(spec["doc"] or {})
            doc.pop("id", None)
            doc.pop("_id", None)
            for k in ("start_date", "end_date"):
                v = doc.get(k)
                if isinstance(v, str):
                    try:
                        doc[k] = datetime.fromisoformat(v.replace("Z", "+00:00"))
                    except Exception:
                        pass
            await allocations_collection.update_one({"_id": ObjectId(spec["id"])}, {"$set": doc})
            return {"success": True, "message": "Allocation reverted"}
        if op == "set_project_status":
            await projects_collection.update_one({"_id": ObjectId(spec["id"])}, {"$set": {"status": spec.get("status")}})
            return {"success": True, "message": "Project status reverted"}
        if op == "set_project_dates":
            update = {}
            if spec.get("start_date"):
                update["start_date"] = datetime.strptime(spec["start_date"], "%Y-%m-%d")
            if spec.get("end_date"):
                update["end_date"] = datetime.strptime(spec["end_date"], "%Y-%m-%d")
            if update:
                await projects_collection.update_one({"_id": ObjectId(spec["id"])}, {"$set": update})
            return {"success": True, "message": "Project dates reverted"}
        if op == "delete_risk":
            await risks_collection.delete_one({"_id": ObjectId(spec["id"])})
            return {"success": True, "message": "Risk/issue undone"}
        if op == "restore_risk":
            doc = dict(spec["doc"] or {})
            doc.pop("id", None)
            doc.pop("_id", None)
            await risks_collection.update_one({"_id": ObjectId(spec["id"])}, {"$set": doc})
            return {"success": True, "message": "Risk reverted"}
        if op == "set_project_lead":
            await projects_collection.update_one({"_id": ObjectId(spec["id"])}, {"$set": {"project_lead_id": spec.get("resource_id")}})
            return {"success": True, "message": "Project lead reverted"}
        if op == "bulk_restore_lead":
            snapshot = spec.get("snapshot", {})
            count = 0
            for pid, lead in snapshot.items():
                await projects_collection.update_one({"_id": ObjectId(pid)}, {"$set": {"project_lead_id": lead}})
                count += 1
            return {"success": True, "message": f"Bulk lead change reverted for {count} projects"}
        if op == "delete_status_update":
            await risks_collection.delete_many({"source_status_update_id": spec["id"]})
            await status_updates_collection.delete_one({"_id": ObjectId(spec["id"])})
            return {"success": True, "message": "Status update undone"}
    except Exception as e:
        return {"success": False, "message": f"Undo failed: {str(e)[:200]}"}
    return {"success": False, "message": f"Unknown undo op: {op}"}
