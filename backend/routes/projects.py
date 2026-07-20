from fastapi import APIRouter, Depends, HTTPException, Response
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta, timezone
from bson import ObjectId
import uuid
import re
import json

from database import (
    projects_collection, resources_collection, allocations_collection,
    risks_collection, timesheets_collection, status_updates_collection,
    wbs_tasks_collection, EMERGENT_LLM_KEY,
)
from models.schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectStatus, ProjectWizardCreate,
    StatusUpdateCreate, StatusUpdateResponse, StatusUpdateEdit, RiskCreate, RiskUpdate, RiskResponse,
    BulkRiskCreate, BulkSummaryUpdate, CreateProjectFullRequest,
    RescheduleProjectRequest, MoveResourceRequest, UserRole,
    ALLOCATION_ROLES, SCHEDULE_STATUS_OPTIONS, HEALTH_STATUS_OPTIONS,
)
from auth.dependencies import get_current_user, require_admin
from utils import serialize_doc, ensure_phase_ids, find_user_resource, snap_to_weekday
from services.ai_providers import get_ai_config, call_openai_api, call_gemini_api

router = APIRouter()

@router.get("/api/projects", response_model=List[ProjectResponse])
async def get_projects(current_user: dict = Depends(get_current_user)):
    query = {}
    if current_user["role"] == UserRole.CLIENT:
        allowed_ids = [ObjectId(pid) for pid in current_user.get("allowed_project_ids", [])]
        query = {"_id": {"$in": allowed_ids}}
    elif current_user["role"] in [UserRole.RESOURCE, UserRole.CONTRACTOR]:
        # Resources and contractors only see projects they're allocated to
        resource = await find_user_resource(current_user)
        if resource:
            allocs = await allocations_collection.find(
                {"resource_id": str(resource["_id"])}
            ).to_list(length=1000)
            project_ids = list({ObjectId(a["project_id"]) for a in allocs})
            # Also include projects where they are the lead
            lead_projects = await projects_collection.find(
                {"project_lead_id": str(resource["_id"])}
            ).to_list(length=1000)
            for lp in lead_projects:
                if lp["_id"] not in project_ids:
                    project_ids.append(lp["_id"])
            query = {"_id": {"$in": project_ids}} if project_ids else {"_id": None}
        else:
            query = {"_id": None}  # No resource link → no projects
    
    cursor = projects_collection.find(query)
    projects = await cursor.to_list(length=1000)

    # Enrich with project lead name — filter out any invalid (non-ObjectId) lead IDs
    # This guards against AI-generated projects that may store placeholder strings
    def _is_valid_oid(v) -> bool:
        return bool(v and isinstance(v, str) and re.match(r'^[a-fA-F0-9]{24}$', v))

    # Silently repair any invalid project_lead_id values in the DB
    for p in projects:
        lid = p.get("project_lead_id")
        if lid and not _is_valid_oid(lid):
            p["project_lead_id"] = None
            await projects_collection.update_one(
                {"_id": p["_id"]},
                {"$set": {"project_lead_id": None}}
            )

    lead_ids = list({p["project_lead_id"] for p in projects if _is_valid_oid(p.get("project_lead_id"))})
    lead_map = {}
    if lead_ids:
        leads = await resources_collection.find(
            {"_id": {"$in": [ObjectId(lid) for lid in lead_ids]}}
        ).to_list(length=100)
        lead_map = {str(lead["_id"]): lead.get("name", "Unknown") for lead in leads}

    for p in projects:
        lid = p.get("project_lead_id")
        p["project_lead_name"] = lead_map.get(lid, None) if lid else None

    return serialize_doc(projects)


@router.get("/api/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, current_user: dict = Depends(get_current_user)):
    # Check role and permissions
    if current_user["role"] == UserRole.CLIENT:
        allowed_ids = [ObjectId(pid) for pid in current_user.get("allowed_project_ids", [])]
        if ObjectId(project_id) not in allowed_ids:
            raise HTTPException(status_code=403, detail="Access denied to this project")
    elif current_user["role"] in [UserRole.RESOURCE, UserRole.CONTRACTOR]:
        resource = await find_user_resource(current_user)
        if resource:
            alloc = await allocations_collection.find_one(
                {"resource_id": str(resource["_id"]), "project_id": project_id}
            )
            project_check = await projects_collection.find_one(
                {"_id": ObjectId(project_id), "project_lead_id": str(resource["_id"])}
            )
            if not alloc and not project_check:
                raise HTTPException(status_code=403, detail="Access denied to this project")
        else:
            raise HTTPException(status_code=403, detail="Access denied to this project")
    
    project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # NEW: Aggregate actual hours from timesheets
    try:
        pipeline = [
            {"$match": {"project_id": project_id}},
            {"$group": {
                "_id": "$phase_id",
                "total_hours": {"$sum": "$actual_hours"}
            }}
        ]
        
        timesheet_data = await timesheets_collection.aggregate(pipeline).to_list(length=1000)
        
        # Map phase_id -> hours
        # Note: timesheets with phase_id=None are included in total but not mapped to a specific phase
        phase_hours_map = {doc["_id"]: doc["total_hours"] for doc in timesheet_data}
        total_project_hours = sum(phase_hours_map.values())
        
        # Inject into project object (for response)
        project["actual_hours"] = total_project_hours
        
        # Inject into phases
        if "phases" in project and project["phases"]:
            for phase in project["phases"]:
                p_id = phase.get("id")
                # If phase has ID, match it.
                phase["actual_hours"] = phase_hours_map.get(p_id, 0.0)
                # Ensure budgeted_hours exists even if None
                if "budgeted_hours" not in phase:
                    phase["budgeted_hours"] = None
    except Exception as e:
        print(f"Error calculating project actuals: {e}")
        project["actual_hours"] = 0.0

    # Enrich with project lead name
    if project.get("project_lead_id"):
        lead = await resources_collection.find_one({"_id": ObjectId(project["project_lead_id"])})
        project["project_lead_name"] = lead.get("name", "Unknown") if lead else None

    # NEW (FIX #2): Add WBS summary to project response
    try:
        # Get WBS tasks count
        wbs_tasks = await wbs_tasks_collection.find({"project_id": project_id}).to_list(length=10000)
        
        if wbs_tasks:
            # Leaf tasks only — parents carry rolled-up estimates (avoid double counting)
            from utils import leaf_estimated_hours
            total_estimated = leaf_estimated_hours(wbs_tasks)
            tasks_completed = sum(1 for t in wbs_tasks if t.get("status") == "done")
            tasks_total = len(wbs_tasks)
            
            # Get actual hours from timesheets (only WBS-linked)
            wbs_actuals_pipeline = [
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
            
            actuals_result = await timesheets_collection.aggregate(wbs_actuals_pipeline).to_list(1)
            total_actual = actuals_result[0]["total_actual"] if actuals_result else 0.0
            
            completion_pct = (total_actual / total_estimated * 100) if total_estimated > 0 else 0
            task_completion_pct = (tasks_completed / tasks_total * 100) if tasks_total > 0 else 0
            
            project["wbs_summary"] = {
                "total_estimated_hours": round(total_estimated, 2),
                "total_actual_hours": round(total_actual, 2),
                "completion_percentage": round(completion_pct, 1),
                "variance_hours": round(total_actual - total_estimated, 2),
                "tasks_completed": tasks_completed,
                "tasks_total": tasks_total,
                "task_completion_pct": round(task_completion_pct, 1),
                "has_wbs": True
            }
            # Extract milestones from WBS tasks for PhaseVisualizer
            project["milestones"] = [
                {
                    "name": t.get("name", "Milestone"),
                    "date": t.get("milestone_date") or t.get("start_date"),
                    "status": "Completed" if t.get("milestone_completed") else "Pending"
                }
                for t in wbs_tasks if t.get("is_milestone")
            ]
        else:
            project["wbs_summary"] = {"has_wbs": False}
            project["milestones"] = []
    except Exception as e:
        # If WBS summary fails, continue without it (non-critical)
        print(f"[Project API] WBS summary failed (non-critical): {e}")
        project["wbs_summary"] = None
        project["milestones"] = []

    return serialize_doc(project)


@router.get("/api/projects/{project_id}/budget-health")
async def get_project_budget_health(project_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get budget health status for a project, including:
    - Total budgeted, allocated, actual hours
    - Usage percentages and status
    - Phase-level breakdown
    """
    # Check permissions
    if current_user["role"] == UserRole.CLIENT:
        allowed_ids = [str(pid) for pid in current_user.get("allowed_project_ids", [])]
        if project_id not in allowed_ids:
            raise HTTPException(status_code=403, detail="Access denied to this project")
    elif current_user["role"] in [UserRole.RESOURCE, UserRole.CONTRACTOR]:
        resource = await find_user_resource(current_user)
        if resource:
            alloc = await allocations_collection.find_one(
                {"resource_id": str(resource["_id"]), "project_id": project_id}
            )
            project_check = await projects_collection.find_one(
                {"_id": ObjectId(project_id), "project_lead_id": str(resource["_id"])}
            )
            if not alloc and not project_check:
                raise HTTPException(status_code=403, detail="Access denied to this project")
        else:
            raise HTTPException(status_code=403, detail="Access denied to this project")
    
    # Fetch project
    project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_name = project.get("name", "")
    budgeted_hours = project.get("budgeted_hours")
    phases = project.get("phases", [])
    
    # Canonical allocation-hours computation (40h/week, business days, hours = total over range)
    from utils import compute_allocation_hours, compute_phase_allocated_hours
    
    # Get all allocations for this project
    allocations_cursor = allocations_collection.find({"project_id": project_id})
    allocations = await allocations_cursor.to_list(length=10000)
    
    # Calculate total allocated hours
    allocated_hours = sum(compute_allocation_hours(alloc) for alloc in allocations)
    
    # Get actual and planned hours from timesheets
    timesheets_cursor = timesheets_collection.find({"project_id": project_id})
    timesheets = await timesheets_cursor.to_list(length=10000)
    
    actual_hours = sum(ts.get("actual_hours", 0) for ts in timesheets)
    planned_hours = sum(ts.get("planned_hours", 0) for ts in timesheets)
    
    # Calculate project-level metrics
    remaining_hours = (budgeted_hours - allocated_hours) if budgeted_hours else None
    usage_percentage = ((allocated_hours / budgeted_hours) * 100) if budgeted_hours and budgeted_hours > 0 else 0
    actual_usage_percentage = ((actual_hours / budgeted_hours) * 100) if budgeted_hours and budgeted_hours > 0 else 0
    
    # Determine status
    if budgeted_hours is None:
        status = "no_budget"
    elif usage_percentage > 100:
        status = "exceeded"
    elif usage_percentage >= 90:
        status = "warning"
    else:
        status = "ok"
    
    # Calculate phase breakdown
    phase_breakdown = []
    for phase in phases:
        phase_id = phase.get("id")
        phase_name = phase.get("name", "")
        phase_budgeted = phase.get("budgeted_hours")
        
        # Canonical phase attribution: per-phase % wins, else phase_names filter,
        # clipped to phase date range (no double counting across phases)
        phase_allocated = sum(compute_phase_allocated_hours(alloc, phase) for alloc in allocations)
        
        # Get actual hours from timesheets for this phase
        phase_timesheets = [ts for ts in timesheets if ts.get("phase_id") == phase_id]
        phase_actual = sum(ts.get("actual_hours", 0) for ts in phase_timesheets)
        
        # Calculate phase metrics
        phase_usage = ((phase_allocated / phase_budgeted) * 100) if phase_budgeted and phase_budgeted > 0 else 0
        
        # Determine phase status
        if phase_budgeted is None:
            phase_status = "no_budget"
        elif phase_usage > 100:
            phase_status = "exceeded"
        elif phase_usage >= 90:
            phase_status = "warning"
        else:
            phase_status = "ok"
        
        phase_breakdown.append({
            "phase_id": phase_id,
            "phase_name": phase_name,
            "budgeted_hours": phase_budgeted,
            "allocated_hours": round(phase_allocated, 2),
            "actual_hours": round(phase_actual, 2),
            "usage_percentage": round(phase_usage, 2),
            "status": phase_status
        })
    
    # Return response
    return {
        "project_id": project_id,
        "project_name": project_name,
        "budgeted_hours": budgeted_hours,
        "allocated_hours": round(allocated_hours, 2),
        "actual_hours": round(actual_hours, 2),
        "planned_hours": round(planned_hours, 2),
        "remaining_hours": round(remaining_hours, 2) if remaining_hours is not None else None,
        "usage_percentage": round(usage_percentage, 2),
        "actual_usage_percentage": round(actual_usage_percentage, 2),
        "status": status,
        "phase_breakdown": phase_breakdown
    }


@router.post("/api/projects", response_model=ProjectResponse)
async def create_project(project: ProjectCreate, admin: dict = Depends(require_admin)):
    project_doc = project.dict()
    # Convert date objects to datetime for MongoDB compatibility
    if isinstance(project_doc.get("start_date"), date) and not isinstance(project_doc.get("start_date"), datetime):
        project_doc["start_date"] = datetime.combine(project_doc["start_date"], datetime.min.time())
    if isinstance(project_doc.get("end_date"), date) and not isinstance(project_doc.get("end_date"), datetime):
        project_doc["end_date"] = datetime.combine(project_doc["end_date"], datetime.min.time())
    result = await projects_collection.insert_one(project_doc)
    project_doc["_id"] = result.inserted_id
    return serialize_doc(project_doc)


@router.put("/api/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project: ProjectUpdate,
    response: Response,
    current_user: dict = Depends(get_current_user),
):
    # Admins or the project's lead may edit
    from utils import user_leads_project
    if not await user_leads_project(current_user, project_id):
        raise HTTPException(status_code=403, detail="Admin or project lead access required")

    update_data = {k: v for k, v in project.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")
    
    # Convert date objects to datetime for MongoDB compatibility
    if isinstance(update_data.get("start_date"), date) and not isinstance(update_data.get("start_date"), datetime):
        update_data["start_date"] = datetime.combine(update_data["start_date"], datetime.min.time())
    if isinstance(update_data.get("end_date"), date) and not isinstance(update_data.get("end_date"), datetime):
        update_data["end_date"] = datetime.combine(update_data["end_date"], datetime.min.time())
    
    # Auto-assign UUIDs to any phases missing an id
    if "phases" in update_data and update_data["phases"]:
        ensure_phase_ids(update_data["phases"])

    # Capture BEFORE state for change-log diff
    before_doc = await projects_collection.find_one({"_id": ObjectId(project_id)})

    result = await projects_collection.find_one_and_update(
        {"_id": ObjectId(project_id)},
        {"$set": update_data},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")

    # BUDGET HIERARCHY VALIDATION — soft, non-blocking. Warnings are surfaced in
    # the X-Budget-Warnings response header (JSON-encoded) so the frontend can
    # show a toast without breaking the save flow.
    try:
        from services.budget_reconciliation import gather_save_warnings
        warnings = await gather_save_warnings(str(result["_id"]), project=result)
        if warnings:
            import json as _json
            response.headers["X-Budget-Warnings"] = _json.dumps(warnings)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Budget validation skipped: {e}")

    # CHANGE-LOG: diff before vs after on baselined fields
    try:
        from services.baselines import diff_and_log_project_update
        await diff_and_log_project_update(
            project_id=str(result["_id"]),
            user_email=current_user.get("email"),
            before=before_doc or {},
            after=result,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Change-log diff failed: {e}")

    # Enrich with lead name
    if result.get("project_lead_id"):
        lead = await resources_collection.find_one({"_id": ObjectId(result["project_lead_id"])})
        result["project_lead_name"] = lead.get("name", "Unknown") if lead else None
    return serialize_doc(result)


@router.delete("/api/projects/{project_id}")
async def delete_project(project_id: str, admin: dict = Depends(require_admin)):
    result = await projects_collection.delete_one({"_id": ObjectId(project_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": "Project deleted"}


@router.post("/api/projects/wizard")
async def create_project_wizard(wizard_data: ProjectWizardCreate, admin: dict = Depends(require_admin)):
    """
    Multi-step project creation wizard
    Creates project, allocations, and risks in one transaction-like flow
    """
    try:
        # Step 1: Create the project
        project_doc = {
            "name": wizard_data.name,
            "client_name": wizard_data.client_name,
            "main_contact_name": wizard_data.main_contact_name,
            "main_contact_email": wizard_data.main_contact_email,
            "main_contact_phone": wizard_data.main_contact_phone,
            "main_contact_role": wizard_data.main_contact_role,
            "status": wizard_data.status,
            "start_date": datetime.combine(wizard_data.start_date, datetime.min.time()),
            "end_date": datetime.combine(wizard_data.end_date, datetime.min.time()),
            "budgeted_hours": wizard_data.budgeted_hours,
        }
        
        # Add phases (with default if not provided)
        if wizard_data.phases and len(wizard_data.phases) > 0:
            phases_with_datetime = []
            for phase in wizard_data.phases:
                phase_doc = {
                    "name": phase["name"],
                    "start_date": datetime.strptime(phase["start_date"], "%Y-%m-%d") if isinstance(phase["start_date"], str) else datetime.combine(phase["start_date"], datetime.min.time()),
                    "end_date": datetime.strptime(phase["end_date"], "%Y-%m-%d") if isinstance(phase["end_date"], str) else datetime.combine(phase["end_date"], datetime.min.time()),
                    "status": phase.get("status", "Pending"),
                    "budgeted_hours": phase.get("budgeted_hours"),
                }
                phases_with_datetime.append(phase_doc)
            ensure_phase_ids(phases_with_datetime)
            project_doc["phases"] = phases_with_datetime
        else:
            # Default single phase
            project_doc["phases"] = [{
                "id": str(uuid.uuid4()),
                "name": "Execution Phase",
                "start_date": project_doc["start_date"],
                "end_date": project_doc["end_date"],
                "status": "Active"
            }]
        
        project_result = await projects_collection.insert_one(project_doc)
        new_project_id = str(project_result.inserted_id)
        
        # Step 2: Create allocations (REUSING EXISTING ALLOCATION LOGIC)
        created_allocations = []
        for alloc_data in wizard_data.allocations:
            allocation_doc = {
                "resource_id": alloc_data["resource_id"],
                "project_id": new_project_id,
                "start_date": datetime.strptime(alloc_data["start_date"], "%Y-%m-%d") if isinstance(alloc_data["start_date"], str) else datetime.combine(alloc_data["start_date"], datetime.min.time()),
                "end_date": datetime.strptime(alloc_data["end_date"], "%Y-%m-%d") if isinstance(alloc_data["end_date"], str) else datetime.combine(alloc_data["end_date"], datetime.min.time()),
                "percentage": alloc_data["percentage"],
            }
            alloc_result = await allocations_collection.insert_one(allocation_doc)
            created_allocations.append(str(alloc_result.inserted_id))
        
        # Step 3: Create risks (auto-polished by AI)
        created_risks = []
        # Get project for context
        wizard_project = await projects_collection.find_one({"_id": ObjectId(new_project_id)})
        for risk_data in wizard_data.risks:
            risk_doc = await _build_polished_risk_doc(
                {
                    "description": risk_data["description"],
                    "impact": risk_data["impact"],
                    "probability": risk_data["probability"],
                },
                project_id=new_project_id,
                project=wizard_project,
            )
            risk_result = await risks_collection.insert_one(risk_doc)
            created_risks.append(str(risk_result.inserted_id))
        
        # Return summary
        return {
            "message": "Project created successfully via wizard",
            "project_id": new_project_id,
            "allocations_created": len(created_allocations),
            "risks_created": len(created_risks),
        }
    
    except Exception as e:
        # If anything fails, we should ideally rollback, but MongoDB doesn't have transactions in this setup
        # In production, you'd use MongoDB transactions
        raise HTTPException(status_code=500, detail=f"Wizard failed: {str(e)}")


# Allocation Roles endpoint
@router.get("/api/allocation-roles")
async def get_allocation_roles(current_user: dict = Depends(get_current_user)):
    """Return predefined allocation roles for project assignments"""
    return {"roles": ALLOCATION_ROLES}


@router.get("/api/projects/{project_id}/phases")
async def get_project_phases(project_id: str, current_user: dict = Depends(get_current_user)):
    """Get phases for a specific project with their dates"""
    project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    phases = project.get("phases", [])
    
    # Format phases for frontend
    formatted_phases = []
    for idx, phase in enumerate(phases):
        phase_data = {
            "id": str(idx),  # Use index as ID if no ID exists
            "name": phase.get("name", f"Phase {idx + 1}"),
            "start_date": None,
            "end_date": None,
            "status": phase.get("status", "Pending")
        }
        
        # Handle date formatting
        start = phase.get("start_date")
        end = phase.get("end_date")
        
        if start:
            if isinstance(start, datetime):
                phase_data["start_date"] = start.strftime("%Y-%m-%d")
            elif isinstance(start, str):
                phase_data["start_date"] = start
        
        if end:
            if isinstance(end, datetime):
                phase_data["end_date"] = end.strftime("%Y-%m-%d")
            elif isinstance(end, str):
                phase_data["end_date"] = end
        
        formatted_phases.append(phase_data)
    
    # Helper to serialize dates
    def format_date(date_val):
        if date_val is None:
            return None
        if isinstance(date_val, datetime):
            return date_val.strftime("%Y-%m-%d")
        if isinstance(date_val, str):
            return date_val
        return str(date_val)
    
    return {
        "project_id": project_id,
        "project_name": project.get("name"),
        "project_start": format_date(project.get("start_date")),
        "project_end": format_date(project.get("end_date")),
        "phases": formatted_phases
    }


# ========== AI-POWERED BULK OPERATIONS ==========



@router.post("/api/projects/{project_id}/reschedule")
async def reschedule_project(
    project_id: str,
    request: RescheduleProjectRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Reschedule a project by shifting all dates forward or backward.
    Updates project dates, phases, and all associated allocations.
    Admins or the project's lead.
    """
    from utils import user_leads_project
    if not await user_leads_project(current_user, project_id):
        raise HTTPException(status_code=403, detail="Admin or project lead access required")
    from datetime import timezone
    
    # Fetch the project
    project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Calculate shift in days
    days_shift = request.weeks_to_shift * 7
    if request.shift_direction == "backward":
        days_shift = -days_shift
    
    shift_delta = timedelta(days=days_shift)
    
    # Update project start and end dates
    project_updates = {}
    if project.get("start_date"):
        new_start = project["start_date"] + shift_delta
        project_updates["start_date"] = new_start
    if project.get("end_date"):
        new_end = project["end_date"] + shift_delta
        project_updates["end_date"] = new_end
    
    # Update phases
    if project.get("phases"):
        updated_phases = []
        for phase in project["phases"]:
            new_phase = phase.copy()
            if phase.get("start_date"):
                phase_start = phase["start_date"]
                if isinstance(phase_start, str):
                    phase_start = datetime.strptime(phase_start, "%Y-%m-%d")
                new_phase["start_date"] = phase_start + shift_delta
            if phase.get("end_date"):
                phase_end = phase["end_date"]
                if isinstance(phase_end, str):
                    phase_end = datetime.strptime(phase_end, "%Y-%m-%d")
                new_phase["end_date"] = phase_end + shift_delta
            updated_phases.append(new_phase)
        project_updates["phases"] = updated_phases
    
    # Apply project updates
    if project_updates:
        await projects_collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": project_updates}
        )
    
    # Update all allocations for this project
    allocations_cursor = allocations_collection.find({"project_id": project_id})
    allocations = await allocations_cursor.to_list(length=1000)
    
    allocations_updated = 0
    for alloc in allocations:
        alloc_updates = {}
        for f in ("start_date", "end_date"):
            if alloc.get(f):
                new_d = alloc[f] + shift_delta
                if hasattr(new_d, 'weekday'):
                    snapped = snap_to_weekday(new_d)
                    # snap_to_weekday returns a date — BSON needs datetime
                    new_d = snapped if isinstance(snapped, datetime) else datetime.combine(snapped, datetime.min.time())
                alloc_updates[f] = new_d
        
        if alloc_updates:
            await allocations_collection.update_one(
                {"_id": alloc["_id"]},
                {"$set": alloc_updates}
            )
            allocations_updated += 1
    
    # Update all WBS tasks for this project
    wbs_tasks = await wbs_tasks_collection.find({"project_id": project_id}).to_list(length=10000)
    tasks_updated = 0
    for task in wbs_tasks:
        task_updates = {}
        for date_field in ["start_date", "end_date", "milestone_date"]:
            if task.get(date_field):
                d = task[date_field]
                if isinstance(d, str):
                    try:
                        d = datetime.strptime(d[:10], "%Y-%m-%d")
                    except ValueError:
                        continue
                new_d = d + shift_delta
                task_updates[date_field] = snap_to_weekday(new_d).isoformat() if hasattr(snap_to_weekday(new_d), 'isoformat') else str(snap_to_weekday(new_d))
        
        if task_updates:
            await wbs_tasks_collection.update_one(
                {"_id": task["_id"]},
                {"$set": task_updates}
            )
            tasks_updated += 1
    
    direction_text = "forward" if request.shift_direction == "forward" else "backward"
    return {
        "message": f"Project rescheduled {request.weeks_to_shift} weeks {direction_text}",
        "project_id": project_id,
        "allocations_updated": allocations_updated,
        "wbs_tasks_updated": tasks_updated
    }



@router.post("/api/allocations/move-resource")
async def move_resource_between_projects(
    request: MoveResourceRequest,
    admin: dict = Depends(require_admin)
):
    """
    Move a resource from one project to another.
    Removes allocation from source project and creates new one in target project.
    """
    # Find existing allocation in source project
    source_allocation = await allocations_collection.find_one({
        "resource_id": request.source_project_id,
        "project_id": request.source_project_id
    })
    
    # Actually search correctly
    source_allocation = await allocations_collection.find_one({
        "resource_id": request.resource_id,
        "project_id": request.source_project_id
    })
    
    if not source_allocation:
        raise HTTPException(
            status_code=404, 
            detail="Resource not found in source project"
        )
    
    # Determine percentage for new allocation
    new_percentage = request.new_percentage or source_allocation.get("percentage", 50)
    
    # Create new allocation in target project
    new_allocation = {
        "resource_id": request.resource_id,
        "project_id": request.target_project_id,
        "start_date": source_allocation.get("start_date"),
        "end_date": source_allocation.get("end_date"),
        "percentage": new_percentage,
        "role": source_allocation.get("role"),
        "allocation_type": source_allocation.get("allocation_type", "percentage"),
        "confirmation_status": "Pending"
    }
    
    # Insert new allocation
    result = await allocations_collection.insert_one(new_allocation)
    
    # Delete old allocation
    await allocations_collection.delete_one({"_id": source_allocation["_id"]})
    
    return {
        "message": "Resource moved successfully",
        "new_allocation_id": str(result.inserted_id),
        "removed_allocation_id": str(source_allocation["_id"])
    }




@router.post("/api/risks/bulk")
async def create_bulk_risks(
    request: BulkRiskCreate,
    admin: dict = Depends(require_admin)
):
    """Create multiple risks for a project at once. Each risk is auto-polished
    by AI (description rewrite + impact_areas inference) unless skip_ai_polish
    is set on the individual risk."""
    # Verify project exists
    project = await projects_collection.find_one({"_id": ObjectId(request.project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    created_risks = []
    for risk_data in request.risks:
        # risk_data is a RiskCreate Pydantic model — convert to dict
        raw = risk_data.dict() if hasattr(risk_data, "dict") else dict(risk_data)
        risk_doc = await _build_polished_risk_doc(
            raw,
            project_id=request.project_id,
            project=project,
            skip_ai=bool(raw.get("skip_ai_polish")),
        )
        result = await risks_collection.insert_one(risk_doc)
        created_risks.append(str(result.inserted_id))

    return {
        "message": f"Created {len(created_risks)} risks",
        "risk_ids": created_risks
    }


async def _find_duplicate_risk(project_id: str, description: str, threshold: float = 0.7) -> Optional[dict]:
    """Check if a similar risk already exists for this project.
    
    Uses simple keyword matching to detect duplicates.
    Returns the existing risk dict if a match is found, None otherwise.
    
    Args:
        project_id: Project ID to search within
        description: New risk description to check
        threshold: Similarity threshold (0.7 = 70% keyword overlap)
    """
    if not description or len(description.strip()) < 10:
        return None
    
    try:
        # Get all active/mitigated risks for this project (not closed)
        existing_risks = await risks_collection.find({
            "project_id": project_id,
            "status": {"$in": ["Active", "Mitigated", "Accepted"]}
        }).to_list(length=1000)
        
        # Simple keyword-based similarity check
        desc_lower = description.lower()
        desc_words = set(w for w in desc_lower.split() if len(w) > 3)  # ignore short words
        
        for risk in existing_risks:
            existing_desc = (risk.get("description") or "").lower()
            existing_words = set(w for w in existing_desc.split() if len(w) > 3)
            
            if not desc_words or not existing_words:
                continue
            
            # Calculate Jaccard similarity (intersection over union)
            intersection = desc_words & existing_words
            union = desc_words | existing_words
            similarity = len(intersection) / len(union) if union else 0
            
            if similarity >= threshold:
                return risk
        
        return None
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Duplicate risk check failed: {e}")
        return None


async def _build_polished_risk_doc(
    raw: dict,
    *,
    project_id: str,
    project: Optional[dict] = None,
    extra_fields: Optional[dict] = None,
    skip_ai: bool = False,
) -> dict:
    """Shared helper used by every risk-insertion path to ensure
    AI polish + impact_areas + ai_polished flag are applied consistently.

    Falls back to raw values if the AI call fails (never raises)."""
    polished = raw
    if not skip_ai and (raw.get("description") or "").strip():
        try:
            from services.risk_ai import polish_risk
            ctx = f"Project: {project.get('name')}" if project else None
            polished = await polish_risk({
                "description": raw.get("description"),
                "impact": raw.get("impact"),
                "probability": raw.get("probability"),
                "mitigation": raw.get("mitigation"),
                "category": raw.get("category"),
                "impact_areas": raw.get("impact_areas"),
            }, project_context=ctx, project_id=project_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[risks] AI polish failed: {e}")
            polished = {**raw, "impact_areas": raw.get("impact_areas") or ["Timeline"], "ai_polished": False}

    risk_doc = {
        "project_id": project_id,
        "description": polished.get("description") or raw.get("description") or "",
        "impact": polished.get("impact") or raw.get("impact") or "Medium",
        "probability": polished.get("probability") or raw.get("probability") or "Medium",
        "mitigation": polished.get("mitigation") or raw.get("mitigation"),
        "status": raw.get("status") or "Active",
        "category": polished.get("category") or raw.get("category") or "Risk",
        "impact_areas": polished.get("impact_areas") or raw.get("impact_areas") or ["Timeline"],
        "ai_polished": bool(polished.get("ai_polished")),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra_fields:
        risk_doc.update(extra_fields)
    return risk_doc


@router.post("/api/projects/{project_id}/risks", response_model=RiskResponse)
async def create_single_risk(
    project_id: str,
    risk: RiskCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a single risk/issue for a project. Any user assigned to the project (or admin) can add.

    AUTO-POLISH: unless `skip_ai_polish=true`, the description is rewritten by
    Gemini into a clear/concise form, the category (Risk vs Issue) is inferred,
    and the `impact_areas` field is auto-populated.
    """
    project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    user_role = current_user.get("role", "")
    is_admin = user_role in ["admin", "super_admin"]
    if not is_admin:
        user_resource = await find_user_resource(current_user)
        if not user_resource:
            raise HTTPException(status_code=403, detail="Access denied")
        allocation = await allocations_collection.find_one({
            "resource_id": str(user_resource["_id"]),
            "project_id": project_id,
        })
        if not allocation:
            # Project leads can add risks even without an allocation
            is_lead = str(project.get("project_lead_id") or "") == str(user_resource["_id"])
            if not is_lead:
                raise HTTPException(status_code=403, detail="You must be allocated to this project or be its lead to add risks")

    # Build the raw dict that the polisher will work on
    raw = {
        "description": risk.description,
        "impact": risk.impact,
        "probability": risk.probability,
        "mitigation": risk.mitigation,
        "status": risk.status,
        "category": risk.category,
        "impact_areas": risk.impact_areas,
    }

    risk_doc = await _build_polished_risk_doc(
        raw,
        project_id=project_id,
        project=project,
        skip_ai=bool(risk.skip_ai_polish),
    )
    result = await risks_collection.insert_one(risk_doc)
    risk_doc["_id"] = result.inserted_id
    return serialize_doc(risk_doc)


@router.put("/api/risks/{risk_id}", response_model=RiskResponse)
async def update_risk(
    risk_id: str,
    update: RiskUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update a risk — including status transitions (Active → Mitigated / Accepted / Closed).

    AUTO-POLISH: if the description text changed and skip_ai_polish is not set,
    re-run the Gemini polish so impact_areas, category and severity stay
    consistent with the new wording.
    """
    risk = await risks_collection.find_one({"_id": ObjectId(risk_id)})
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    user_role = current_user.get("role", "")
    is_admin = user_role in ["admin", "super_admin"]
    if not is_admin:
        user_resource = await find_user_resource(current_user)
        if not user_resource:
            raise HTTPException(status_code=403, detail="Access denied")
        allocation = await allocations_collection.find_one({
            "resource_id": str(user_resource["_id"]),
            "project_id": risk.get("project_id"),
        })
        if not allocation:
            # Project leads can manage risks even without an allocation
            lead_project = None
            try:
                lead_project = await projects_collection.find_one({
                    "_id": ObjectId(risk.get("project_id")),
                    "project_lead_id": str(user_resource["_id"]),
                })
            except Exception:
                lead_project = None
            if not lead_project:
                raise HTTPException(status_code=403, detail="Access denied")

    update_data = {k: v for k, v in update.dict(exclude={"skip_ai_polish"}).items() if v is not None}

    # AUTO-POLISH on update — only re-polish if description was changed by the user
    description_changed = (
        update.description is not None
        and update.description.strip() != (risk.get("description") or "").strip()
    )
    if description_changed and not update.skip_ai_polish:
        try:
            from services.risk_ai import polish_risk
            # Merge existing risk with the new update for context
            merged = {**risk, **update_data}
            project = None
            try:
                project = await projects_collection.find_one({"_id": ObjectId(risk.get("project_id"))})
            except Exception:
                project = None
            ctx = f"Project: {project.get('name')}" if project else None
            polished = await polish_risk({
                "description": merged.get("description"),
                "impact": merged.get("impact"),
                "probability": merged.get("probability"),
                "mitigation": merged.get("mitigation"),
                "category": merged.get("category"),
                "impact_areas": merged.get("impact_areas"),
            }, project_context=ctx)
            # Apply polished fields back into update_data
            for f in ("description", "category", "impact", "probability", "impact_areas", "mitigation"):
                if polished.get(f):
                    update_data[f] = polished[f]
            update_data["ai_polished"] = bool(polished.get("ai_polished"))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[risks] AI polish on update skipped: {e}")

    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        await risks_collection.update_one({"_id": ObjectId(risk_id)}, {"$set": update_data})

    updated = await risks_collection.find_one({"_id": ObjectId(risk_id)})
    return serialize_doc(updated)


@router.post("/api/projects/{project_id}/risks/polish-all")
async def polish_all_project_risks(
    project_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Backfill: run AI polish on every risk in this project that hasn't been
    polished yet (where ai_polished != True). Useful for risks created before
    AI polish was wired in, or via paths that bypassed it (e.g. older bulk
    imports).

    Returns the count of risks updated. Admins or project lead only.
    """
    # Permission check
    project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    user_role = current_user.get("role", "")
    is_admin = user_role in ["admin", "super_admin"]
    if not is_admin:
        lead_id = str(project.get("project_lead_id") or "")
        user_resource = await find_user_resource(current_user)
        user_id = str(user_resource["_id"]) if user_resource else ""
        if not (lead_id and user_id and lead_id == user_id):
            raise HTTPException(status_code=403, detail="Admin or project lead access required")

    # Find all un-polished risks for this project
    cursor = risks_collection.find({
        "project_id": project_id,
        "$or": [
            {"ai_polished": {"$ne": True}},
            {"ai_polished": {"$exists": False}},
        ],
    })
    risks_to_polish = await cursor.to_list(length=500)
    if not risks_to_polish:
        return {"polished": 0, "skipped": 0, "message": "All risks already polished."}

    from services.risk_ai import polish_risk
    polished_count = 0
    skipped_count = 0
    ctx = f"Project: {project.get('name')}"
    for risk in risks_to_polish:
        try:
            polished = await polish_risk({
                "description": risk.get("description"),
                "impact": risk.get("impact"),
                "probability": risk.get("probability"),
                "mitigation": risk.get("mitigation"),
                "category": risk.get("category"),
                "impact_areas": risk.get("impact_areas"),
            }, project_context=ctx)
            if polished and polished.get("ai_polished"):
                await risks_collection.update_one(
                    {"_id": risk["_id"]},
                    {"$set": {
                        "description": polished["description"],
                        "category": polished["category"],
                        "impact": polished["impact"],
                        "probability": polished["probability"],
                        "impact_areas": polished["impact_areas"],
                        "mitigation": polished["mitigation"],
                        "ai_polished": True,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )
                polished_count += 1
            else:
                skipped_count += 1
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[polish-all] Failed to polish risk {risk.get('_id')}: {e}")
            skipped_count += 1

    return {
        "polished": polished_count,
        "skipped": skipped_count,
        "total_examined": len(risks_to_polish),
        "message": f"Polished {polished_count} risk(s). Skipped {skipped_count}.",
    }


@router.delete("/api/risks/{risk_id}")
async def delete_risk(
    risk_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a risk. Admins or users allocated to the project."""
    risk = await risks_collection.find_one({"_id": ObjectId(risk_id)})
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    user_role = current_user.get("role", "")
    is_admin = user_role in ["admin", "super_admin"]
    if not is_admin:
        user_resource = await find_user_resource(current_user)
        if not user_resource:
            raise HTTPException(status_code=403, detail="Access denied")
        allocation = await allocations_collection.find_one({
            "resource_id": str(user_resource["_id"]),
            "project_id": risk.get("project_id"),
        })
        if not allocation:
            # Project leads can manage risks even without an allocation
            lead_project = None
            try:
                lead_project = await projects_collection.find_one({
                    "_id": ObjectId(risk.get("project_id")),
                    "project_lead_id": str(user_resource["_id"]),
                })
            except Exception:
                lead_project = None
            if not lead_project:
                raise HTTPException(status_code=403, detail="Access denied")

    await risks_collection.delete_one({"_id": ObjectId(risk_id)})
    return {"success": True, "message": "Risk deleted"}




@router.post("/api/projects/bulk-generate-summaries")
async def bulk_generate_summaries(
    request: BulkSummaryUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Generate AI summaries for multiple projects"""
    results = []
    
    for project_id in request.project_ids:
        try:
            # Call the existing generate_summary function logic
            project = await projects_collection.find_one({"_id": ObjectId(project_id)})
            if not project:
                results.append({"project_id": project_id, "status": "error", "message": "Project not found"})
                continue
            
            # Generate summary (simplified - in production would call full AI)
            from datetime import timezone
            alloc_cursor = allocations_collection.find({"project_id": project_id})
            allocations = await alloc_cursor.to_list(length=100)
            
            risk_cursor = risks_collection.find({"project_id": project_id})
            risks = await risk_cursor.to_list(length=100)
            
            # Create a basic summary
            summary = f"**{project.get('name', 'Project')}** for {project.get('client_name', 'client')} is {project.get('status', 'in progress')}. "
            summary += f"The project has {len(allocations)} resource(s) assigned and {len(risks)} risk(s) identified."
            
            update_time = datetime.now(timezone.utc).isoformat()
            await projects_collection.update_one(
                {"_id": ObjectId(project_id)},
                {"$set": {
                    "status_summary": summary,
                    "status_summary_updated_at": update_time
                }}
            )
            
            results.append({"project_id": project_id, "status": "success", "summary": summary})
        except Exception as e:
            results.append({"project_id": project_id, "status": "error", "message": str(e)})
    
    return {
        "message": f"Processed {len(request.project_ids)} projects",
        "results": results
    }




@router.post("/api/projects/create-full")
async def create_project_full(
    request: CreateProjectFullRequest,
    admin: dict = Depends(require_admin)
):
    """
    Create a complete project with phases and resource allocations in one operation.
    Useful for AI-driven project creation.
    """
    from datetime import timezone
    
    today = datetime.now(timezone.utc)
    
    # Calculate project dates based on phases
    total_weeks = sum(phase.get("duration_weeks", 3) for phase in request.phases) if request.phases else 12
    project_end = today + timedelta(weeks=total_weeks)
    
    # Build phases with calculated dates
    phases_with_dates = []
    current_start = today
    for phase in request.phases:
        duration_weeks = phase.get("duration_weeks", 3)
        phase_end = current_start + timedelta(weeks=duration_weeks)
        phases_with_dates.append({
            "id": str(uuid.uuid4()),  # Always generate unique UUID for phases
            "name": phase.get("name", "Phase"),
            "start_date": current_start,
            "end_date": phase_end,
            "status": "Pending" if current_start > today else "Active"
        })
        current_start = phase_end
    
    # If no phases provided, create default
    if not phases_with_dates:
        phases_with_dates = [{
            "id": str(uuid.uuid4()),  # Always generate unique UUID for phases
            "name": "Execution Phase",
            "start_date": today,
            "end_date": project_end,
            "status": "Active"
        }]
    
    # Create project
    project_doc = {
        "name": request.name,
        "client_name": request.client_name,
        "status": request.status,
        "start_date": today,
        "end_date": phases_with_dates[-1]["end_date"] if phases_with_dates else project_end,
        "phases": phases_with_dates,
        "created_at": today
    }
    
    project_result = await projects_collection.insert_one(project_doc)
    project_id = str(project_result.inserted_id)
    
    # Create allocations
    created_allocations = []
    for alloc in request.allocations:
        allocation_doc = {
            "resource_id": alloc.get("resource_id"),
            "project_id": project_id,
            "start_date": today,
            "end_date": project_doc["end_date"],
            "percentage": alloc.get("percentage", 50),
            "role": alloc.get("role"),
            "allocation_type": "percentage",
            "confirmation_status": "Pending"
        }
        result = await allocations_collection.insert_one(allocation_doc)
        created_allocations.append(str(result.inserted_id))
    
    return {
        "message": "Project created successfully",
        "project_id": project_id,
        "phases_created": len(phases_with_dates),
        "allocations_created": len(created_allocations)
    }


# ========== END AI-POWERED BULK OPERATIONS ==========


# ========== PROJECT STATUS UPDATES (Weekly Check-ins) ==========

def _count_business_days(start_date: date, end_date: date) -> int:
    """
    Count business days (Monday-Friday) between two dates.
    Excludes weekends (Saturday, Sunday).
    
    Args:
        start_date: Start date
        end_date: End date
        
    Returns:
        Number of business days (inclusive of both start and end if they're weekdays)
    """
    if start_date > end_date:
        return 0
    
    business_days = 0
    current = start_date
    
    while current <= end_date:
        # Monday = 0, Sunday = 6 (Python weekday())
        if current.weekday() < 5:  # Monday-Friday
            business_days += 1
        current += timedelta(days=1)
    
    return business_days


def _calculate_time_based_progress(project: dict) -> int:
    """
    Calculate project progress based on business days elapsed.
    Formula: (business_days_elapsed / total_business_days) * 100
    Clamped between 0-100%.
    Only counts Monday-Friday (excludes weekends).
    """
    try:
        start = project.get("start_date")
        end = project.get("end_date")
        
        if not start or not end:
            return 0
        
        # Convert to date if datetime
        if isinstance(start, datetime):
            start = start.date()
        if isinstance(end, datetime):
            end = end.date()
        
        today = datetime.now(timezone.utc).date()
        
        # Calculate total business days and elapsed business days
        total_business_days = _count_business_days(start, end)
        elapsed_business_days = _count_business_days(start, min(today, end))
        
        if total_business_days <= 0:
            return 100 if today >= end else 0
        
        # Calculate percentage and clamp between 0-100
        progress = int((elapsed_business_days / total_business_days) * 100)
        return max(0, min(100, progress))
    except Exception as e:
        print(f"Error calculating time-based progress: {e}")
        return 0


@router.post("/api/status-updates", response_model=StatusUpdateResponse)
async def create_status_update(
    update: StatusUpdateCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new project status update (weekly check-in).
    Any user assigned to the project can submit updates.
    """
    from datetime import timezone
    
    # Verify project exists
    project = await projects_collection.find_one({"_id": ObjectId(update.project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if user has access (is assigned to project or is admin)
    user_role = current_user.get("role", "")
    is_admin = user_role in ["admin", "super_admin"]
    
    if not is_admin:
        # Check if user's resource is allocated to this project
        user_resource = await find_user_resource(current_user)
        if user_resource:
            allocation = await allocations_collection.find_one({
                "resource_id": str(user_resource["_id"]),
                "project_id": update.project_id
            })
            if not allocation:
                # Project leads can submit even without an allocation
                is_lead = str(project.get("project_lead_id") or "") == str(user_resource["_id"])
                if not is_lead:
                    raise HTTPException(
                        status_code=403, 
                        detail="You must be assigned to this project or be its lead to submit status updates"
                    )
        else:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Get user's name
    user_resource = await find_user_resource(current_user)
    updated_by_name = user_resource["name"] if user_resource else current_user.get("email", "Unknown")
    
    now = datetime.now(timezone.utc)
    
    # Generate AI summary from the status update
    ai_summary = None
    try:
        # Prepare summary prompt
        summary_parts = []
        if update.accomplishments:
            summary_parts.append(f"Achievements: {update.accomplishments}")
        if update.blockers:
            summary_parts.append(f"Blockers: {update.blockers}")
        if update.next_steps:
            summary_parts.append(f"Next Steps: {update.next_steps}")
        
        if summary_parts:
            system_prompt = """You are a professional project manager creating an executive summary. 
            Based on the status update details provided, create a concise, professional 2-3 sentence executive summary 
            that highlights the key points without repeating the exact wording. Focus on the overall project status and outlook.
            Write in third person, past tense for achievements, present tense for current status."""
            
            user_message = f"""Project: {project.get('name')}
Health: {update.health}
Schedule: {update.schedule_status}
Progress: {update.actual_progress}%

{chr(10).join(summary_parts)}

Generate a professional executive summary (2-3 sentences only)."""

            # Use app-wide AI config
            ai_config = await get_ai_config()
            if ai_config["api_key"]:
                if ai_config["provider"] == "openai":
                    response = await call_openai_api(ai_config["api_key"], system_prompt, user_message)
                    if response.status_code == 200:
                        data = response.json()
                        ai_summary = data['choices'][0]['message']['content'].strip()
                elif ai_config["provider"] == "gemini":
                    response = await call_gemini_api(ai_config["api_key"], system_prompt, user_message)
                    if response.status_code == 200:
                        data = response.json()
                        ai_summary = data['candidates'][0]['content']['parts'][0]['text'].strip()
                elif ai_config["provider"] == "emergent":
                    response = await call_openai_api(ai_config["api_key"], system_prompt, user_message)
                    if response.status_code == 200:
                        data = response.json()
                        ai_summary = data['choices'][0]['message']['content'].strip()

            # Fallback to Emergent LLM if no summary generated
            if not ai_summary and EMERGENT_LLM_KEY:
                response = await call_openai_api(EMERGENT_LLM_KEY, system_prompt, user_message)
                if response.status_code == 200:
                    data = response.json()
                    ai_summary = data['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"AI summary generation failed: {str(e)}")
        # Continue without AI summary
    
    # Create status update document
    # actual_progress: use explicit value if provided, else calculate from time elapsed
    if update.actual_progress is not None:
        effective_progress = update.actual_progress
    else:
        # Calculate time-based progress
        effective_progress = _calculate_time_based_progress(project)

    status_doc = {
        "project_id": update.project_id,
        "updated_by": current_user.get("email"),
        "updated_by_name": updated_by_name,
        "update_date": now.strftime("%Y-%m-%d"),
        "week_start_date": now,  # For filtering in reports
        "health": update.health,
        "schedule_status": update.schedule_status,
        "actual_progress": effective_progress,
        "accomplishments": update.accomplishments,
        "progress_summary": update.accomplishments,  # Alias for backward compatibility
        "blockers": [b.strip() for b in re.split(r"[,\n]+", update.blockers) if b.strip()] if update.blockers else [],
        "next_steps": update.next_steps,
        "next_week_plan": update.next_steps,  # Alias for backward compatibility
        "notes": update.notes,
        "ai_generated_summary": ai_summary,
        "created_at": now
    }

    result = await status_updates_collection.insert_one(status_doc)
    status_update_id = str(result.inserted_id)

    # Auto-promote each blocker into a risk/issue (deduped against existing risk descriptions)
    auto_created_risks = []
    try:
        if update.blockers:
            # Split blockers by comma or newline
            blocker_items = [b.strip() for b in re.split(r"[,\n]+", update.blockers) if b.strip()]
            # Get project for AI context
            blocker_project = None
            try:
                blocker_project = await projects_collection.find_one({"_id": ObjectId(update.project_id)})
            except Exception:
                pass
            for b_text in blocker_items:
                # Check for duplicate using fuzzy matching
                duplicate_risk = await _find_duplicate_risk(update.project_id, b_text)
                
                if duplicate_risk:
                    # Update existing blocker/issue instead of creating duplicate
                    try:
                        await risks_collection.update_one(
                            {"_id": duplicate_risk["_id"]},
                            {"$set": {
                                "source_status_update_id": status_update_id,
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                                "status": "Active",  # Ensure it's still active
                                "probability": "High",  # Blockers are high probability
                            }}
                        )
                        auto_created_risks.append(str(duplicate_risk["_id"]))
                        print(f"[risks] Updated existing blocker risk: {duplicate_risk.get('_id')}")
                    except Exception as update_err:
                        print(f"Failed to update duplicate blocker: {update_err}")
                else:
                    # No duplicate, create new blocker risk
                    r_doc = await _build_polished_risk_doc(
                        {
                            "description": b_text,
                            "impact": "Medium",
                            "probability": "High",  # blockers are typically already happening
                            "mitigation": update.next_steps or None,
                            "status": "Active",
                            "category": "Issue",  # blockers = current issues
                        },
                        project_id=update.project_id,
                        project=blocker_project,
                        extra_fields={"source_status_update_id": status_update_id},
                    )
                    r_result = await risks_collection.insert_one(r_doc)
                    auto_created_risks.append(str(r_result.inserted_id))
    except Exception as e:
        print(f"Auto-promote blockers to risks failed: {str(e)}")

    # Create any explicit new_risks passed inline with the status update
    try:
        if update.new_risks:
            # Project context for AI polish
            inline_project = None
            try:
                inline_project = await projects_collection.find_one({"_id": ObjectId(update.project_id)})
            except Exception:
                pass
            for r_data in update.new_risks:
                if not r_data.get("description"):
                    continue
                
                # Check for duplicate risk before creating
                duplicate_risk = await _find_duplicate_risk(
                    update.project_id,
                    r_data.get("description")
                )
                
                if duplicate_risk:
                    # Update existing risk instead of creating duplicate
                    try:
                        update_fields = {}
                        # Update impact/probability if new values are "higher"
                        impact_order = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}
                        prob_order = {"Low": 0, "Medium": 1, "High": 2}
                        
                        new_impact = r_data.get("impact", "Medium")
                        existing_impact = duplicate_risk.get("impact", "Medium")
                        if impact_order.get(new_impact, 1) > impact_order.get(existing_impact, 1):
                            update_fields["impact"] = new_impact
                        
                        new_prob = r_data.get("probability", "Medium")
                        existing_prob = duplicate_risk.get("probability", "Medium")
                        if prob_order.get(new_prob, 1) > prob_order.get(existing_prob, 1):
                            update_fields["probability"] = new_prob
                        
                        # Update mitigation if provided
                        if r_data.get("mitigation"):
                            update_fields["mitigation"] = r_data.get("mitigation")
                        
                        # Add source status update link
                        update_fields["source_status_update_id"] = status_update_id
                        update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
                        
                        if update_fields:
                            await risks_collection.update_one(
                                {"_id": duplicate_risk["_id"]},
                                {"$set": update_fields}
                            )
                        
                        auto_created_risks.append(str(duplicate_risk["_id"]))
                        print(f"[risks] Updated existing duplicate risk: {duplicate_risk.get('_id')}")
                    except Exception as update_err:
                        print(f"Failed to update duplicate risk: {update_err}")
                else:
                    # No duplicate found, create new risk
                    r_doc = await _build_polished_risk_doc(
                        r_data,
                        project_id=update.project_id,
                        project=inline_project,
                        extra_fields={"source_status_update_id": status_update_id},
                    )
                    r_result = await risks_collection.insert_one(r_doc)
                    auto_created_risks.append(str(r_result.inserted_id))
    except Exception as e:
        print(f"Inline risks creation failed: {str(e)}")

    # Also update the project with latest status
    await projects_collection.update_one(
        {"_id": ObjectId(update.project_id)},
        {"$set": {
            "health": update.health,
            "schedule_status": update.schedule_status,
            "actual_progress": effective_progress,
            "last_status_update": now
        }}
    )
    
    status_doc["_id"] = result.inserted_id
    return serialize_doc(status_doc)


@router.get("/api/status-updates/project/{project_id}")
async def get_project_status_updates(
    project_id: str,
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """Get status update history for a project"""
    cursor = status_updates_collection.find(
        {"project_id": project_id}
    ).sort("created_at", -1).limit(limit)
    
    updates = await cursor.to_list(length=limit)
    return [serialize_doc(u) for u in updates]


@router.get("/api/status-updates/latest/{project_id}")
async def get_latest_status_update(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get the most recent status update for a project"""
    update = await status_updates_collection.find_one(
        {"project_id": project_id},
        sort=[("created_at", -1)]
    )
    
    if not update:
        return None
    
    return serialize_doc(update)


@router.get("/api/status-updates/my-projects")
async def get_my_projects_for_status(current_user: dict = Depends(get_current_user)):
    """
    Get projects that the current user can submit status updates for.
    Returns projects the user is assigned to (or all projects for admins).
    """
    user_role = current_user.get("role", "")
    is_admin = user_role in ["admin", "super_admin"]
    
    if is_admin:
        # Admins can update all active projects (not Pipeline or Completed)
        cursor = projects_collection.find({"status": "Active"})
        projects = await cursor.to_list(length=100)
    else:
        # Get user's resource using robust fallback lookup
        user_resource = await find_user_resource(current_user)
        if not user_resource:
            return []
        
        # Get all allocations for this resource
        alloc_cursor = allocations_collection.find({"resource_id": str(user_resource["_id"])})
        allocations = await alloc_cursor.to_list(length=100)
        
        # Get unique project IDs
        project_ids = list(set(a["project_id"] for a in allocations))
        
        if not project_ids:
            return []
        
        # Get those projects (only Active ones)
        cursor = projects_collection.find({
            "_id": {"$in": [ObjectId(pid) for pid in project_ids]},
            "status": "Active"
        })
        projects = await cursor.to_list(length=100)
    
    # For each project, get the latest status update
    result = []
    # Optimize: Fetch all latest status updates in a single aggregation query
    project_ids = [str(p["_id"]) for p in projects]
    
    if project_ids:
        # Aggregation pipeline to get latest status update for each project
        pipeline = [
            {"$match": {"project_id": {"$in": project_ids}}},
            {"$sort": {"created_at": -1}},
            {"$group": {
                "_id": "$project_id",
                "latest": {"$first": "$$ROOT"}
            }}
        ]
        
        status_updates_cursor = status_updates_collection.aggregate(pipeline)
        status_updates_list = await status_updates_cursor.to_list(length=len(project_ids))
        
        # Create a lookup map for O(1) access
        status_map = {s["_id"]: serialize_doc(s["latest"]) for s in status_updates_list}
    else:
        status_map = {}
    
    # Build result with status data
    for project in projects:
        project_data = serialize_doc(project)
        project_data["latest_status"] = status_map.get(project_data["id"])
        result.append(project_data)
    
    return result


@router.get("/api/status-options")
async def get_status_options(current_user: dict = Depends(get_current_user)):
    """Get available options for status updates"""
    return {
        "health_options": HEALTH_STATUS_OPTIONS,
        "schedule_options": SCHEDULE_STATUS_OPTIONS
    }


@router.put("/api/status-updates/{update_id}", response_model=StatusUpdateResponse)
async def edit_status_update(
    update_id: str,
    update_data: StatusUpdateEdit,
    current_user: dict = Depends(get_current_user)
):
    """
    Edit an existing status update (admins or the project's lead).
    Tracks who edited and when.
    """
    from datetime import timezone
    
    # Find the status update
    try:
        status_update = await status_updates_collection.find_one({"_id": ObjectId(update_id)})
    except Exception:
        raise HTTPException(status_code=404, detail="Status update not found")
    
    if not status_update:
        raise HTTPException(status_code=404, detail="Status update not found")
    
    # Permission: admin or lead of the update's project
    from utils import user_leads_project
    if not await user_leads_project(current_user, status_update.get("project_id", "")):
        raise HTTPException(status_code=403, detail="Admin or project lead access required")
    
    # Build update dict
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    
    if not update_dict:
        raise HTTPException(status_code=400, detail="No update data provided")
    
    # Add edit tracking
    update_dict["edited_by"] = current_user.get("email")
    update_dict["edited_at"] = datetime.now(timezone.utc).isoformat()
    
    # Convert blockers to list if it's a string
    if "blockers" in update_dict and isinstance(update_dict["blockers"], str):
        update_dict["blockers"] = [b.strip() for b in re.split(r"[,\n]+", update_dict["blockers"]) if b.strip()]
    
    # Update the status update
    result = await status_updates_collection.find_one_and_update(
        {"_id": ObjectId(update_id)},
        {"$set": update_dict},
        return_document=True
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Status update not found")
    
    # Also update the project with latest status if certain fields changed
    if any(k in update_dict for k in ["health", "schedule_status", "actual_progress"]):
        project_updates = {}
        if "health" in update_dict:
            project_updates["health"] = update_dict["health"]
        if "schedule_status" in update_dict:
            project_updates["schedule_status"] = update_dict["schedule_status"]
        if "actual_progress" in update_dict:
            project_updates["actual_progress"] = update_dict["actual_progress"]
        
        if project_updates:
            await projects_collection.update_one(
                {"_id": ObjectId(status_update["project_id"])},
                {"$set": project_updates}
            )
    
    return serialize_doc(result)


# ========== END PROJECT STATUS UPDATES ==========


# AI Project Summary endpoints
@router.post("/api/projects/{project_id}/generate-summary")
async def generate_project_summary(project_id: str, current_user: dict = Depends(get_current_user)):
    """Generate AI-powered project status summary"""
    
    # Fetch project data
    project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Fetch allocations
    alloc_cursor = allocations_collection.find({"project_id": project_id})
    allocations = await alloc_cursor.to_list(length=100)
    
    # Fetch risks
    risk_cursor = risks_collection.find({"project_id": project_id})
    risks = await risk_cursor.to_list(length=100)
    
    # Fetch resources for context
    resources_cursor = resources_collection.find()
    resources = await resources_cursor.to_list(length=100)
    resource_map = {str(r["_id"]): r["name"] for r in resources}
    
    # Calculate progress
    from datetime import timezone
    today = datetime.now(timezone.utc).date()
    start = project.get("start_date")
    end = project.get("end_date")
    
    if isinstance(start, datetime):
        start = start.date()
    if isinstance(end, datetime):
        end = end.date()
    
    total_days = (end - start).days if start and end else 1
    elapsed_days = (today - start).days if start else 0
    progress = min(100, max(0, int((elapsed_days / total_days) * 100))) if total_days > 0 else 0
    
    # Build context for AI
    team_info = []
    for alloc in allocations:
        resource_name = resource_map.get(alloc.get("resource_id"), "Unknown")
        role = alloc.get("role", "Team Member")
        percentage = alloc.get("percentage", 0)
        team_info.append(f"- {resource_name} ({role}): {percentage}% allocation")
    
    risk_info = []
    for risk in risks:
        risk_info.append(f"- [{risk.get('impact', 'Medium')} Impact] {risk.get('description', 'No description')}")
    
    system_prompt = """You are a project management assistant. Generate a concise, professional project status summary.
The summary should be 2-3 paragraphs covering:
1. Overall project health and progress
2. Team capacity and resource utilization
3. Key risks or concerns (if any)

Keep the tone professional but conversational. Be specific about numbers and dates when available.
Return ONLY the summary text, no JSON formatting."""

    user_message = f"""Generate a status summary for this project:

Project: {project.get('name', 'Unnamed')}
Client: {project.get('client_name', 'Unknown')}
Status: {project.get('status', 'Unknown')}
Progress: {progress}% complete
Timeline: {start} to {end}
Draft Mode: {'Yes' if project.get('is_draft') else 'No'}

Team ({len(allocations)} allocations):
{chr(10).join(team_info) if team_info else 'No team members assigned yet.'}

Risks ({len(risks)} identified):
{chr(10).join(risk_info) if risk_info else 'No risks identified yet.'}

Current Date: {today}"""

    # Try to generate summary using AI (with Emergent fallback)
    try:
        # Use emergent integration directly for text response
        import uuid as uuid_module
        import re
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"summary-{uuid_module.uuid4()}",
            system_message=system_prompt
        ).with_model("openai", "gpt-4o-mini")
        
        user_msg = UserMessage(text=user_message)
        response = await chat.send_message(user_msg)
        
        # Clean response - remove markdown formatting if present
        if isinstance(response, str):
            # Remove markdown code blocks if present
            cleaned = re.sub(r'^```(?:\w+)?\s*', '', response.strip())
            cleaned = re.sub(r'\s*```$', '', cleaned)
            generated_summary = cleaned.strip()
        else:
            generated_summary = str(response) if response else None
            
    except Exception as e:
        print(f"AI summary generation error: {type(e).__name__}: {str(e)}")
        generated_summary = None
    
    if not generated_summary:
        # Fallback to template-based summary
        generated_summary = f"""**Project Overview**
{project.get('name', 'This project')} for {project.get('client_name', 'the client')} is currently {project.get('status', 'in progress')} with approximately {progress}% of the timeline elapsed.

**Team & Resources**
The project has {len(allocations)} resource allocation(s) assigned. {'The team is actively working on deliverables.' if allocations else 'Resource allocation is pending.'}

**Risks & Concerns**
{f"There are {len(risks)} identified risk(s) to monitor." if risks else "No significant risks have been identified at this time."} Regular monitoring is recommended to ensure project success."""

    # Update project with summary
    update_time = datetime.now(timezone.utc).isoformat()
    await projects_collection.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {
            "status_summary": generated_summary,
            "status_summary_updated_at": update_time
        }}
    )
    
    return {
        "summary": generated_summary,
        "updated_at": update_time
    }


@router.patch("/api/projects/{project_id}/summary")
async def update_project_summary(
    project_id: str, 
    summary: str,
    current_user: dict = Depends(get_current_user)
):
    """Manually update project status summary"""
    from datetime import timezone
    
    update_time = datetime.now(timezone.utc).isoformat()
    result = await projects_collection.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {
            "status_summary": summary,
            "status_summary_updated_at": update_time
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {
        "summary": summary,
        "updated_at": update_time
    }

