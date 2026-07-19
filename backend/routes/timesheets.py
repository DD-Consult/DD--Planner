from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date, timedelta, timezone
from bson import ObjectId

from database import (
    timesheets_collection, allocations_collection, resources_collection,
    projects_collection, wbs_tasks_collection, SYDNEY_TZ,
)
from models.schemas import TimesheetCreate, TimesheetUpdate, TimesheetResponse
from auth.dependencies import get_current_user, require_admin
from utils import serialize_doc, find_user_resource, calculate_weekly_hours, is_timesheet_update_allowed

router = APIRouter()

@router.post("/api/timesheets", response_model=TimesheetResponse)
async def create_timesheet(timesheet: TimesheetCreate, current_user: dict = Depends(get_current_user)):
    """
    Create a new timesheet entry.
    Super admins can create timesheets for any resource.
    Regular users can only create their own timesheets.
    """
    is_super_admin = current_user.get("role") == "super_admin"
    
    # Regular users can only create timesheets for themselves
    if not is_super_admin:
        resource = await find_user_resource(current_user)
        if not resource:
            raise HTTPException(status_code=404, detail="Resource profile not found")
        
        # Verify the timesheet is for their own resource
        if timesheet.resource_id != str(resource["_id"]):
            raise HTTPException(
                status_code=403,
                detail="You can only create timesheets for yourself"
            )
    
    timesheet_doc = timesheet.dict()
    
    # VALIDATION: Ensure phase_id is not None
    if not timesheet_doc.get("phase_id"):
        raise HTTPException(
            status_code=400, 
            detail="phase_id is required. Please select a valid project phase."
        )
    
    # NEW: VALIDATION - Check phase allocation
    # Verify that the resource is allocated to this phase with sufficient capacity
    resource_id = timesheet_doc.get("resource_id")
    project_id = timesheet_doc.get("project_id")
    phase_id = timesheet_doc.get("phase_id")
    actual_hours = timesheet_doc.get("actual_hours", 0)
    
    # Get resource allocation for this project
    allocation = await allocations_collection.find_one({
        "resource_id": resource_id,
        "project_id": project_id
    })
    
    if allocation:
        from utils import get_allocation_for_phase, get_allocation_hours_for_phase
        
        # Get phase-specific allocation percentage
        phase_percentage = get_allocation_for_phase(allocation, phase_id)
        phase_weekly_hours = get_allocation_hours_for_phase(allocation, phase_id)
        
        # If phase allocation is 0%, warn but allow (they might be reallocated mid-week)
        if phase_percentage == 0 and actual_hours > 0:
            # Log warning but don't block (super admins can override)
            import logging
            logging.getLogger(__name__).warning(
                f"Timesheet created for resource {resource_id} with 0% allocation in phase {phase_id}"
            )
        
        # If hours significantly exceed allocation, warn (but allow for flexibility)
        if actual_hours > phase_weekly_hours * 1.5:  # 50% tolerance
            import logging
            logging.getLogger(__name__).warning(
                f"Timesheet hours ({actual_hours}) significantly exceed phase allocation ({phase_weekly_hours}h/week) "
                f"for resource {resource_id} in phase {phase_id}"
            )
    
    # Convert dates to datetime for MongoDB
    if isinstance(timesheet_doc.get("week_start_date"), date):
        timesheet_doc["week_start_date"] = datetime.combine(timesheet_doc["week_start_date"], datetime.min.time())
    if isinstance(timesheet_doc.get("week_end_date"), date):
        timesheet_doc["week_end_date"] = datetime.combine(timesheet_doc["week_end_date"], datetime.min.time())
    
    # Add metadata
    timesheet_doc["auto_filled"] = False
    timesheet_doc["modified_by_user"] = True
    timesheet_doc["created_at"] = datetime.now(timezone.utc)
    timesheet_doc["submitted_at"] = None
    
    # Calculate variance
    variance_hours = timesheet_doc["actual_hours"] - timesheet_doc["planned_hours"]
    variance_percentage = (variance_hours / timesheet_doc["planned_hours"] * 100) if timesheet_doc["planned_hours"] > 0 else 0
    
    timesheet_doc["variance_hours"] = round(variance_hours, 2)
    timesheet_doc["variance_percentage"] = round(variance_percentage, 2)
    
    result = await timesheets_collection.insert_one(timesheet_doc)
    timesheet_doc["_id"] = result.inserted_id
    return serialize_doc(timesheet_doc)


@router.get("/api/timesheets/my-week", response_model=List[TimesheetResponse])
async def get_my_week_timesheets(
    week_start: str, 
    view: str = "personal", 
    current_user: dict = Depends(get_current_user)
):
    """
    Get timesheets for a specific week with project and client names enriched.
    view="all": Super admins can see ALL timesheets.
    view="personal": Users see only their own timesheets.
    """
    # Parse week_start date
    try:
        week_start_date = datetime.strptime(week_start, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Calculate week end (4 days later = Friday, business days only)
    week_end_date = week_start_date + timedelta(days=4)
    
    # Check if user is super admin
    is_super_admin = current_user.get("role") == "super_admin"
    
    if view == "all" and is_super_admin:
        # Super admin requesting ALL timesheets
        cursor = timesheets_collection.find({
            "week_start_date": {
                "$gte": week_start_date,
                "$lte": week_end_date
            }
        })
    else:
        # Regular users OR Super admin requesting PERSONAL view
        resource = await find_user_resource(current_user)
        if not resource:
            # If super admin has no linked resource, return empty list instead of error
            if is_super_admin:
                return []
            raise HTTPException(status_code=404, detail="Resource profile not found")
        
        resource_id = str(resource["_id"])
        
        cursor = timesheets_collection.find({
            "resource_id": resource_id,
            "week_start_date": {
                "$gte": week_start_date,
                "$lte": week_end_date
            }
        })
    
    timesheets = await cursor.to_list(length=1000)
    
    # Enrich timesheets with project and client information
    enriched_timesheets = []
    for timesheet in timesheets:
        timesheet_data = serialize_doc(timesheet)
        
        # Fetch project details
        project = await projects_collection.find_one({"_id": ObjectId(timesheet["project_id"])})
        if project:
            timesheet_data["project_name"] = project.get("name", "Unknown Project")
            timesheet_data["client_name"] = project.get("client_name", "Unknown Client")
            
            # Find phase name from project phases
            phase_name = "Unknown Phase"
            phases = project.get("phases", [])
            for phase in phases:
                if phase.get("id") == timesheet.get("phase_id"):
                    phase_name = phase.get("name", "Unknown Phase")
                    break
            timesheet_data["phase_name"] = phase_name
        else:
            timesheet_data["project_name"] = "Unknown Project"
            timesheet_data["client_name"] = "Unknown Client"
            timesheet_data["phase_name"] = "Unknown Phase"
        
        # Fetch resource name
        resource = await resources_collection.find_one({"_id": ObjectId(timesheet["resource_id"])})
        if resource:
            timesheet_data["resource_name"] = resource.get("name", "Unknown Resource")
        else:
            timesheet_data["resource_name"] = "Unknown Resource"
        
        enriched_timesheets.append(timesheet_data)
    
    return enriched_timesheets


@router.put("/api/timesheets/{timesheet_id}", response_model=TimesheetResponse)
async def update_timesheet(timesheet_id: str, update: TimesheetUpdate, current_user: dict = Depends(get_current_user)):
    """
    Update a timesheet entry.
    Super admins can update any timesheet at any time.
    Regular users can update their own Draft timesheets.
    """
    # Find the timesheet
    timesheet = await timesheets_collection.find_one({"_id": ObjectId(timesheet_id)})
    if not timesheet:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    
    is_super_admin = current_user.get("role") == "super_admin"
    
    if not is_super_admin:
        # Regular users can only edit their own timesheets
        resource = await find_user_resource(current_user)
        if not resource or timesheet.get("resource_id") != str(resource["_id"]):
            raise HTTPException(status_code=403, detail="You can only edit your own timesheets")
        
        # Regular users can only edit Draft timesheets
        if timesheet.get("status") != "Draft":
            raise HTTPException(status_code=403, detail="You can only edit timesheets that haven't been submitted yet")
    
    # Update fields
    update_data = update.dict(exclude_unset=True)
    
    # Recalculate variance if actual_hours changed
    if "actual_hours" in update_data:
        planned_hours = timesheet.get("planned_hours", 0)
        actual_hours = update_data["actual_hours"]
        variance_hours = actual_hours - planned_hours
        variance_percentage = (variance_hours / planned_hours * 100) if planned_hours > 0 else 0
        
        update_data["variance_hours"] = round(variance_hours, 2)
        update_data["variance_percentage"] = round(variance_percentage, 2)
        update_data["modified_by_user"] = True
    
    await timesheets_collection.update_one(
        {"_id": ObjectId(timesheet_id)},
        {"$set": update_data}
    )
    
    updated_timesheet = await timesheets_collection.find_one({"_id": ObjectId(timesheet_id)})
    return serialize_doc(updated_timesheet)


@router.delete("/api/timesheets/{timesheet_id}")
async def delete_timesheet(timesheet_id: str, current_user: dict = Depends(get_current_user)):
    """
    Delete a timesheet entry.
    Super admins can delete any timesheet.
    Regular users can delete their own Draft timesheets.
    """
    timesheet = await timesheets_collection.find_one({"_id": ObjectId(timesheet_id)})
    if not timesheet:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    
    is_super_admin = current_user.get("role") == "super_admin"
    
    if not is_super_admin:
        resource = await find_user_resource(current_user)
        if not resource or timesheet.get("resource_id") != str(resource["_id"]):
            raise HTTPException(status_code=403, detail="You can only delete your own timesheets")
        
        if timesheet.get("status") != "Draft":
            raise HTTPException(status_code=403, detail="You can only delete timesheets that haven't been submitted yet")
    
    await timesheets_collection.delete_one({"_id": ObjectId(timesheet_id)})
    return {"message": "Timesheet deleted successfully"}


@router.post("/api/timesheets/auto-fill")
async def auto_fill_timesheets(week_start: str, current_user: dict = Depends(get_current_user)):
    """
    Auto-fill timesheet entries for current user based on active allocations.
    Pre-fills with planned hours, user can then edit.
    """
    # Parse week_start date
    try:
        week_start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    week_end_date = week_start_date + timedelta(days=4)  # Friday
    
    # Find current user's resource
    resource = await find_user_resource(current_user)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource profile not found")
    
    resource_id = str(resource["_id"])
    
    # Get active allocations for this resource that overlap with the week
    cursor = allocations_collection.find({
        "resource_id": resource_id,
        "start_date": {"$lte": datetime.combine(week_end_date, datetime.max.time())},
        "end_date": {"$gte": datetime.combine(week_start_date, datetime.min.time())}
    })
    
    allocations = await cursor.to_list(length=1000)
    
    created_count = 0
    updated_count = 0
    skipped_count = 0
    
    for allocation in allocations:
        project_id = allocation["project_id"]
        
        # Get project to fetch phases
        project = await projects_collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            continue
        
        phases = project.get("phases", [])
        if not phases:
            continue  # Skip projects without phases
        
        # Determine which phases this allocation applies to
        phase_ids_to_process = []
        phase_names = allocation.get("phase_names", [])
        phase_ids = allocation.get("phase_ids", [])
        
        if phase_ids:
            # Use phase_ids if available (specific phases selected)
            phase_ids_to_process = phase_ids
        elif phase_names:
            # Resolve phase names to IDs
            for phase in phases:
                if phase.get("name") in phase_names:
                    phase_ids_to_process.append(phase.get("id"))
        else:
            # No phase filter - allocation applies to whole project
            # Create ONE timesheet for the first/current active phase, not all phases
            current_phase = None
            
            # Find the current active phase based on dates
            for phase in phases:
                phase_start = phase.get('start_date')
                phase_end = phase.get('end_date')
                
                if phase_start and phase_end:
                    if isinstance(phase_start, str):
                        phase_start = datetime.fromisoformat(phase_start.replace('Z', '+00:00')).date()
                    elif isinstance(phase_start, datetime):
                        phase_start = phase_start.date()
                    
                    if isinstance(phase_end, str):
                        phase_end = datetime.fromisoformat(phase_end.replace('Z', '+00:00')).date()
                    elif isinstance(phase_end, datetime):
                        phase_end = phase_end.date()
                    
                    # Check if week overlaps with this phase
                    if phase_start <= week_end_date and phase_end >= week_start_date:
                        current_phase = phase
                        break
            
            # Use current phase, or fallback to first phase
            if current_phase and current_phase.get("id"):
                phase_ids_to_process = [current_phase["id"]]
            elif phases and phases[0].get("id"):
                phase_ids_to_process = [phases[0]["id"]]
            else:
                continue  # Skip if no valid phases
        
        # Filter out any None values
        phase_ids_to_process = [pid for pid in phase_ids_to_process if pid]
        
        if not phase_ids_to_process:
            # Fallback: use first phase
            if phases and phases[0].get("id"):
                phase_ids_to_process = [phases[0]["id"]]
            else:
                continue  # Skip if no valid phases
        
        # Create/update timesheet for each phase
        for phase_id in phase_ids_to_process:
            # ========== NEW: WBS Task Assignment Logic ==========
            # Query WBS tasks for this project/phase to enable smart task linking
            task_id = None
            task_name = None
            
            try:
                wbs_tasks = await wbs_tasks_collection.find({
                    "project_id": project_id,
                    "phase_id": phase_id,
                    "status": {"$in": ["todo", "in_progress"]},  # Only active tasks
                    "assigned_to": resource_id  # Prefer tasks assigned to this resource
                }).to_list(length=100)
                
                # Smart assignment logic:
                # 1. If exactly 1 task assigned to this resource → auto-assign
                # 2. If multiple tasks → don't assign (user chooses later)
                # 3. If no assigned tasks but 1 task in phase → auto-assign
                # 4. Otherwise → no assignment (general hours)
                
                if len(wbs_tasks) == 1:
                    # Perfect match: exactly one task
                    task_id = str(wbs_tasks[0]["_id"])
                    task_name = wbs_tasks[0].get("name", "")
                elif len(wbs_tasks) == 0:
                    # No assigned tasks, check if there's only 1 task in phase (any assignee)
                    all_phase_tasks = await wbs_tasks_collection.find({
                        "project_id": project_id,
                        "phase_id": phase_id,
                        "status": {"$in": ["todo", "in_progress"]}
                    }).to_list(length=100)
                    
                    if len(all_phase_tasks) == 1:
                        # Only one task in entire phase → auto-assign
                        task_id = str(all_phase_tasks[0]["_id"])
                        task_name = all_phase_tasks[0].get("name", "")
                # If multiple tasks, leave task_id=None (user selects manually)
                
            except Exception as e:
                # If WBS query fails, continue without task assignment
                # This ensures backward compatibility - auto-fill still works
                print(f"[Auto-fill] WBS task query failed (non-critical): {e}")
                task_id = None
                task_name = None
            # ========== END: WBS Task Assignment Logic ==========
            
            # Check if timesheet already exists
            existing = await timesheets_collection.find_one({
                "resource_id": resource_id,
                "project_id": project_id,
                "phase_id": phase_id,
                "week_start_date": datetime.combine(week_start_date, datetime.min.time())
            })
            
            # Calculate planned hours for this week
            allocation_start = allocation["start_date"].date() if isinstance(allocation["start_date"], datetime) else allocation["start_date"]
            allocation_end = allocation["end_date"].date() if isinstance(allocation["end_date"], datetime) else allocation["end_date"]
            percentage = allocation.get("percentage", 0)
            
            planned_hours = calculate_weekly_hours(percentage, allocation_start, allocation_end, week_start_date, week_end_date)
            
            if planned_hours <= 0:
                continue  # Skip if no hours for this week
            
            # Distribute hours across phases if multiple phases
            if len(phase_ids_to_process) > 1:
                planned_hours = planned_hours / len(phase_ids_to_process)
            
            if existing:
                # Update only if not modified by user
                if not existing.get("modified_by_user", False):
                    update_fields = {
                        "planned_hours": round(planned_hours, 2),
                        "actual_hours": round(planned_hours, 2),  # Default to planned
                        "variance_hours": 0.0,
                        "variance_percentage": 0.0
                    }
                    
                    # Update task info if we found a WBS task (don't overwrite if user manually set)
                    if task_id and not existing.get("task_id"):
                        update_fields["task_id"] = task_id
                        update_fields["task_name"] = task_name
                    
                    await timesheets_collection.update_one(
                        {"_id": existing["_id"]},
                        {"$set": update_fields}
                    )
                    updated_count += 1
                else:
                    skipped_count += 1
            else:
                # Create new draft timesheet
                timesheet_doc = {
                    "resource_id": resource_id,
                    "project_id": project_id,
                    "phase_id": phase_id,
                    "week_start_date": datetime.combine(week_start_date, datetime.min.time()),
                    "week_end_date": datetime.combine(week_end_date, datetime.min.time()),
                    "planned_hours": round(planned_hours, 2),
                    "actual_hours": round(planned_hours, 2),  # Default to planned
                    "variance_hours": 0.0,
                    "variance_percentage": 0.0,
                    "notes": None,
                    "status": "Draft",
                    "auto_filled": True,
                    "modified_by_user": False,
                    "submitted_at": None,
                    "created_at": datetime.now(timezone.utc),
                    "task_id": task_id,      # NEW: WBS task link (None if no single task found)
                    "task_name": task_name   # NEW: WBS task name for display
                }
                
                await timesheets_collection.insert_one(timesheet_doc)
                created_count += 1
    
    return {
        "message": "Timesheets auto-filled successfully",
        "created": created_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "total": created_count + updated_count + skipped_count
    }


@router.post("/api/timesheets/submit-week")
async def submit_week_timesheets(week_start: str, current_user: dict = Depends(get_current_user)):
    """
    Submit all draft timesheets for the week. 
    Restricted to Thursday/Friday (Sydney time).
    """
    # Check if timesheet updates are allowed
    if not is_timesheet_update_allowed():
        raise HTTPException(
            status_code=403, 
            detail="Timesheet submissions are only allowed from Thursday to Monday 12:00 PM (Sydney time)"
        )
    
    # Parse week_start date
    try:
        week_start_date = datetime.strptime(week_start, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Find current user's resource
    resource = await find_user_resource(current_user)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource profile not found")
    
    resource_id = str(resource["_id"])
    
    # Update all draft timesheets for this week to "Submitted"
    result = await timesheets_collection.update_many(
        {
            "resource_id": resource_id,
            "week_start_date": week_start_date,
            "status": "Draft"
        },
        {
            "$set": {
                "status": "Submitted",
                "submitted_at": datetime.now(timezone.utc)
            }
        }
    )
    
    return {
        "message": "Timesheets submitted successfully",
        "submitted_count": result.modified_count
    }


# =============================================================================
# REPORTING ENDPOINTS (Planned vs Actual Analysis)
# =============================================================================
