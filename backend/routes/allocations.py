from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date, timedelta, timezone
from bson import ObjectId

from database import (
    allocations_collection, resources_collection, projects_collection,
    leaves_collection, holidays_collection, risks_collection, 
    timesheets_collection, SYDNEY_TZ,
)
from models.schemas import (
    AllocationCreate, AllocationUpdate, AllocationResponse,
    RiskResponse, UserRole, AllocationValidateRequest,
)
from auth.dependencies import get_current_user, require_admin
from utils import serialize_doc, is_timesheet_update_allowed, get_next_allowed_timesheet_day

router = APIRouter()


class TimesheetConfirmation(BaseModel):
    actual_percentage: int
    confirmation_status: str = "Confirmed"

@router.get("/api/allocations", response_model=List[AllocationResponse])
async def get_allocations(current_user: dict = Depends(get_current_user)):
    cursor = allocations_collection.find().limit(500)
    allocations = await cursor.to_list(length=500)

    # Build lookup maps for resource and project names
    resource_ids = list(set(a.get("resource_id") for a in allocations if a.get("resource_id")))
    project_ids = list(set(a.get("project_id") for a in allocations if a.get("project_id")))

    resource_map = {}
    if resource_ids:
        obj_ids = []
        for rid in resource_ids:
            try:
                obj_ids.append(ObjectId(rid))
            except Exception:
                pass
        if obj_ids:
            res_cursor = resources_collection.find({"_id": {"$in": obj_ids}}, {"name": 1, "role": 1})
            async for r in res_cursor:
                resource_map[str(r["_id"])] = {"name": r.get("name", ""), "role": r.get("role", "")}

    project_map = {}
    if project_ids:
        obj_ids = []
        for pid in project_ids:
            try:
                obj_ids.append(ObjectId(pid))
            except Exception:
                pass
        if obj_ids:
            proj_cursor = projects_collection.find({"_id": {"$in": obj_ids}}, {"name": 1, "client_name": 1})
            async for p in proj_cursor:
                project_map[str(p["_id"])] = {"name": p.get("name", ""), "client_name": p.get("client_name", "")}

    result = []
    for alloc in allocations:
        doc = serialize_doc(alloc)
        rid = doc.get("resource_id", "")
        pid = doc.get("project_id", "")
        r_info = resource_map.get(rid, {})
        p_info = project_map.get(pid, {})
        doc["resource_name"] = r_info.get("name", "Unknown")
        doc["resource_role"] = r_info.get("role", "")
        doc["project_name"] = p_info.get("name", "Unknown")
        doc["client_name"] = p_info.get("client_name", "")
        result.append(doc)
    return result


@router.post("/api/allocations", response_model=AllocationResponse)
async def create_allocation(allocation: AllocationCreate, admin: dict = Depends(require_admin)):
    allocation_doc = allocation.dict()
    
    # Fetch project to validate dates
    project = await projects_collection.find_one({"_id": ObjectId(allocation.project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get project dates
    project_start = project.get("start_date")
    project_end = project.get("end_date")
    
    # Convert to date objects for comparison
    if isinstance(project_start, datetime):
        project_start = project_start.date()
    elif isinstance(project_start, str):
        project_start = datetime.fromisoformat(project_start.replace("Z", "+00:00")).date() if "T" in project_start else datetime.strptime(project_start, "%Y-%m-%d").date()
    
    if isinstance(project_end, datetime):
        project_end = project_end.date()
    elif isinstance(project_end, str):
        project_end = datetime.fromisoformat(project_end.replace("Z", "+00:00")).date() if "T" in project_end else datetime.strptime(project_end, "%Y-%m-%d").date()
    
    # Validate allocation dates are within project range
    alloc_start = allocation.start_date
    alloc_end = allocation.end_date
    
    if project_start and alloc_start < project_start:
        raise HTTPException(
            status_code=400, 
            detail=f"Allocation start date ({alloc_start}) cannot be before project start date ({project_start})"
        )
    
    if project_end and alloc_end > project_end:
        raise HTTPException(
            status_code=400, 
            detail=f"Allocation end date ({alloc_end}) cannot be after project end date ({project_end})"
        )
    
    # Convert date objects to datetime for MongoDB compatibility
    if isinstance(allocation_doc.get("start_date"), date) and not isinstance(allocation_doc.get("start_date"), datetime):
        allocation_doc["start_date"] = datetime.combine(allocation_doc["start_date"], datetime.min.time())
    if isinstance(allocation_doc.get("end_date"), date) and not isinstance(allocation_doc.get("end_date"), datetime):
        allocation_doc["end_date"] = datetime.combine(allocation_doc["end_date"], datetime.min.time())
    
    # Calculate percentage from hours if allocation_type is "hours"
    if allocation_doc.get("allocation_type") == "hours" and allocation_doc.get("hours"):
        start = allocation_doc.get("start_date")
        end = allocation_doc.get("end_date")
        if isinstance(start, datetime):
            start = start.date()
        if isinstance(end, datetime):
            end = end.date()
        days = (end - start).days + 1
        # Use business days for hours calculation
        from utils import count_business_days
        biz_days = count_business_days(start, end)
        # 8 hours per business day standard
        total_available_hours = biz_days * 8
        if total_available_hours > 0:
            allocation_doc["percentage"] = min(100, round((allocation_doc["hours"] / total_available_hours) * 100))
    
    # Ensure percentage has a default value
    if allocation_doc.get("percentage") is None:
        allocation_doc["percentage"] = 0
    
    result = await allocations_collection.insert_one(allocation_doc)
    allocation_doc["_id"] = result.inserted_id
    return serialize_doc(allocation_doc)


@router.put("/api/allocations/{allocation_id}", response_model=AllocationResponse)
async def update_allocation(allocation_id: str, allocation: AllocationUpdate, admin: dict = Depends(require_admin)):
    update_data = {k: v for k, v in allocation.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")
    
    # Convert date objects to datetime for MongoDB compatibility
    if isinstance(update_data.get("start_date"), date) and not isinstance(update_data.get("start_date"), datetime):
        update_data["start_date"] = datetime.combine(update_data["start_date"], datetime.min.time())
    if isinstance(update_data.get("end_date"), date) and not isinstance(update_data.get("end_date"), datetime):
        update_data["end_date"] = datetime.combine(update_data["end_date"], datetime.min.time())
    
    result = await allocations_collection.find_one_and_update(
        {"_id": ObjectId(allocation_id)},
        {"$set": update_data},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Allocation not found")
    return serialize_doc(result)


# Timesheet confirmation endpoint - allows any user to confirm their own allocations

# Helper function to check if timesheet updates are allowed (Thursday/Friday Sydney time)
def is_timesheet_update_allowed():
    """Check if current time in Sydney is within the update window: Thursday 00:00 to Monday 12:00"""
    sydney_now = datetime.now(SYDNEY_TZ)
    weekday = sydney_now.weekday()
    # Thursday(3), Friday(4), Saturday(5), Sunday(6) = always allowed
    if weekday in [3, 4, 5, 6]:
        return True
    # Monday(0) = allowed before 12:00 PM
    if weekday == 0 and sydney_now.hour < 12:
        return True
    return False


def get_next_allowed_timesheet_day():
    """Get the next Thursday in Sydney timezone"""
    sydney_now = datetime.now(SYDNEY_TZ)
    current_weekday = sydney_now.weekday()
    
    # Calculate days until next Thursday
    days_until_thursday = (3 - current_weekday) % 7
    if days_until_thursday == 0 and not is_timesheet_update_allowed():
        days_until_thursday = 7
    
    next_thursday = sydney_now + timedelta(days=days_until_thursday)
    return next_thursday.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/api/timesheet/can-update")
async def check_timesheet_update_allowed(current_user: dict = Depends(get_current_user)):
    """Check if timesheet updates are currently allowed (Thursday/Friday Sydney time)"""
    allowed = is_timesheet_update_allowed()
    sydney_now = datetime.now(SYDNEY_TZ)
    
    if allowed:
        return {
            "allowed": True,
            "reason": "Timesheet updates are allowed right now",
            "current_day": sydney_now.strftime("%A"),
            "sydney_time": sydney_now.strftime("%Y-%m-%d %H:%M:%S %Z")
        }
    else:
        next_allowed = get_next_allowed_timesheet_day()
        return {
            "allowed": False,
            "reason": "Timesheet updates are only allowed from Thursday to Monday 12:00 PM (Sydney time)",
            "current_day": sydney_now.strftime("%A"),
            "sydney_time": sydney_now.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "next_allowed": next_allowed.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "next_allowed_day": next_allowed.strftime("%A")
        }


@router.put("/api/allocations/{allocation_id}/confirm", response_model=AllocationResponse)
async def confirm_allocation(
    allocation_id: str, 
    confirmation: TimesheetConfirmation,
    current_user: dict = Depends(get_current_user)
):
    """
    Allow users to confirm their own timesheet allocations.
    Users can only confirm allocations assigned to their linked resource.
    Admins can confirm any allocation.
    RESTRICTION: Only allowed on Thursday and Friday (Sydney timezone).
    """
    # Check if timesheet updates are allowed (Thursday/Friday Sydney time)
    if not is_timesheet_update_allowed():
        sydney_now = datetime.now(SYDNEY_TZ)
        next_allowed = get_next_allowed_timesheet_day()
        raise HTTPException(
            status_code=403, 
            detail=f"Timesheet updates are only allowed from Thursday to Monday 12:00 PM (Sydney time). Current day: {sydney_now.strftime('%A %H:%M')}. Next allowed: {next_allowed.strftime('%A, %B %d')}"
        )
    
    # Get the allocation
    allocation = await allocations_collection.find_one({"_id": ObjectId(allocation_id)})
    if not allocation:
        raise HTTPException(status_code=404, detail="Allocation not found")
    
    # Check if user is admin - admins can confirm any allocation
    is_admin = current_user.get("role") in ["admin", "super_admin"]
    
    if not is_admin:
        # Non-admin users can only confirm their own allocations
        user_resource_id = current_user.get("resource_id")
        if not user_resource_id or allocation.get("resource_id") != user_resource_id:
            raise HTTPException(
                status_code=403, 
                detail="You can only confirm your own allocations"
            )
    
    # Update only the confirmation fields
    update_data = {
        "actual_percentage": confirmation.actual_percentage,
        "confirmation_status": confirmation.confirmation_status
    }
    
    result = await allocations_collection.find_one_and_update(
        {"_id": ObjectId(allocation_id)},
        {"$set": update_data},
        return_document=True
    )
    
    return serialize_doc(result)


@router.delete("/api/allocations/{allocation_id}")
async def delete_allocation(allocation_id: str, admin: dict = Depends(require_admin)):
    result = await allocations_collection.delete_one({"_id": ObjectId(allocation_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Allocation not found")
    return {"message": "Allocation deleted"}


# Capacity report endpoint - CRITICAL (Updated for Leave Management)
@router.get("/api/reports/capacity")
async def get_capacity_report(
    start_date: str,
    end_date: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    if start > end:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    
    # Get all resources
    cursor = resources_collection.find()
    resources = await cursor.to_list(length=1000)
    
    # Get all allocations
    allocations_cursor = allocations_collection.find()
    all_allocations = await allocations_cursor.to_list(length=10000)
    
    # Get all leaves (NEW)
    leaves_cursor = leaves_collection.find()
    all_leaves = await leaves_cursor.to_list(length=10000)
    
    # Get all holidays (NEW)
    # Convert date objects to datetime for MongoDB query
    start_datetime = datetime.combine(start, datetime.min.time())
    end_datetime = datetime.combine(end, datetime.max.time())
    
    holidays_cursor = holidays_collection.find({
        "date": {"$gte": start_datetime, "$lte": end_datetime}
    })
    all_holidays = await holidays_cursor.to_list(length=1000)
    
    # Convert holiday dates to date objects for comparison
    holiday_dates = set()
    for holiday in all_holidays:
        holiday_date = holiday["date"]
        if isinstance(holiday_date, datetime):
            holiday_dates.add(holiday_date.date())
        else:
            holiday_dates.add(holiday_date)
    
    # Build response
    result = {
        "range": {"start": start_date, "end": end_date},
        "resources": []
    }
    
    # For each resource, calculate daily capacity
    for resource in resources:
        resource_id = str(resource["_id"])
        resource_data = {
            "resource_id": resource_id,
            "name": resource["name"],
            "role": resource["role"],
            "days": []
        }
        
        # Iterate through each day in the range
        current_date = start
        while current_date <= end:
            total_percentage = 0
            
            # NEW: Check if resource is on leave or it's a holiday
            is_on_leave = False
            leave_type = None
            
            # Check holidays (applies to ALL resources)
            if current_date in holiday_dates:
                is_on_leave = True
                leave_type = "Holiday"
            
            # Check individual leaves
            for leave in all_leaves:
                if str(leave["resource_id"]) == resource_id:
                    leave_start = leave["start_date"]
                    leave_end = leave["end_date"]
                    
                    # Convert datetime to date for comparison if needed
                    if isinstance(leave_start, datetime):
                        leave_start = leave_start.date()
                    if isinstance(leave_end, datetime):
                        leave_end = leave_end.date()
                    
                    if leave_start <= current_date <= leave_end:
                        is_on_leave = True
                        leave_type = leave["type"]
                        break
            
            # Find all allocations for this resource on this date
            for allocation in all_allocations:
                if str(allocation["resource_id"]) == resource_id:
                    alloc_start = allocation["start_date"]
                    alloc_end = allocation["end_date"]
                    
                    # Convert datetime to date for comparison if needed
                    if isinstance(alloc_start, datetime):
                        alloc_start = alloc_start.date()
                    if isinstance(alloc_end, datetime):
                        alloc_end = alloc_end.date()
                    
                    # Check if current_date falls within allocation range
                    if alloc_start <= current_date <= alloc_end:
                        total_percentage += allocation["percentage"]
            
            # NEW LOGIC: Determine color based on leave status
            if is_on_leave:
                # If on leave, available capacity is 0%
                # Any allocation = overload (red)
                if total_percentage > 0:
                    color = "red"  # Work assigned on leave day = overload
                else:
                    color = "leave"  # NEW: Special color for leave days
            else:
                # Normal capacity calculation
                if total_percentage <= 80:
                    color = "green"
                elif total_percentage <= 100:
                    color = "yellow"
                else:
                    color = "red"
            
            resource_data["days"].append({
                "date": current_date.isoformat(),
                "load": total_percentage,
                "color": color,
                "on_leave": is_on_leave,
                "leave_type": leave_type if is_on_leave else None
            })
            
            current_date += timedelta(days=1)
        
        result["resources"].append(resource_data)
    
    return result


@router.get("/api/client/projects")
async def get_client_projects(current_user: dict = Depends(get_current_user)):
    """
    Client-specific endpoint to fetch only their allowed projects
    Excludes sensitive internal fields
    """
    if current_user["role"] != UserRole.CLIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for client users only"
        )
    
    # Get allowed project IDs for this client
    allowed_ids = [ObjectId(pid) for pid in current_user.get("allowed_project_ids", [])]
    
    if not allowed_ids:
        return []
    
    # Fetch only allowed projects
    cursor = projects_collection.find({"_id": {"$in": allowed_ids}})
    projects = await cursor.to_list(length=1000)
    
    # Remove sensitive fields and serialize
    sanitized_projects = []
    for project in projects:
        proj_dict = serialize_doc(project)
        # Exclude internal fields if they exist
        proj_dict.pop("internal_notes", None)
        proj_dict.pop("resource_cost", None)
        proj_dict.pop("internal_capacity_flags", None)
        sanitized_projects.append(proj_dict)
    
    return sanitized_projects


@router.get("/api/allocations/by-cell")
async def get_allocations_by_cell(
    resource_id: str,
    date: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all allocations for a specific resource on a specific date
    Used for interactive grid editing
    """
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Find all allocations for this resource that overlap with the target date
    cursor = allocations_collection.find({"resource_id": resource_id})
    all_allocations = await cursor.to_list(length=1000)
    
    matching_allocations = []
    for allocation in all_allocations:
        alloc_start = allocation["start_date"]
        alloc_end = allocation["end_date"]
        
        # Convert datetime to date for comparison if needed
        if isinstance(alloc_start, datetime):
            alloc_start = alloc_start.date()
        if isinstance(alloc_end, datetime):
            alloc_end = alloc_end.date()
        
        # Check if target_date falls within allocation range
        if alloc_start <= target_date <= alloc_end:
            matching_allocations.append(serialize_doc(allocation))
    
    return matching_allocations


@router.get("/api/projects/{project_id}/risks")
async def get_project_risks(project_id: str, current_user: dict = Depends(get_current_user)):
    """Get all risks for a specific project"""
    # Check permissions
    if current_user["role"] == UserRole.CLIENT:
        allowed_ids = [str(pid) for pid in current_user.get("allowed_project_ids", [])]
        if project_id not in allowed_ids:
            raise HTTPException(status_code=403, detail="Access denied to this project")
    
    cursor = risks_collection.find({"project_id": project_id})
    risks = await cursor.to_list(length=1000)
    return serialize_doc(risks)


@router.get("/api/projects/{project_id}/allocations")
async def get_project_allocations(project_id: str, current_user: dict = Depends(get_current_user)):
    """Get all allocations for a specific project"""
    # Check permissions
    if current_user["role"] == UserRole.CLIENT:
        allowed_ids = [str(pid) for pid in current_user.get("allowed_project_ids", [])]
        if project_id not in allowed_ids:
            raise HTTPException(status_code=403, detail="Access denied to this project")
    
    cursor = allocations_collection.find({"project_id": project_id})
    allocations = await cursor.to_list(length=1000)
    return serialize_doc(allocations)



@router.post("/api/allocations/validate")
async def validate_allocation(request_data: AllocationValidateRequest, current_user: dict = Depends(get_current_user)):
    """
    Validate a proposed allocation against project budget.
    Returns validation status, warnings, and projected budget usage.
    Never hard-rejects — always returns valid: true with appropriate warnings.
    """
    
    project_id = request_data.project_id
    resource_id = request_data.resource_id
    start_date = request_data.start_date
    end_date = request_data.end_date
    percentage = request_data.percentage
    hours = request_data.hours
    allocation_type = request_data.allocation_type
    exclude_allocation_id = request_data.exclude_allocation_id
    
    # Fetch project
    try:
        project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    except Exception:
        # If project_id is not a valid ObjectId, return error
        raise HTTPException(status_code=400, detail="Invalid project_id")
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    budgeted_hours = project.get("budgeted_hours")
    
    # If no budget, return "no_budget" status
    if budgeted_hours is None:
        return {
            "valid": True,
            "would_exceed": False,
            "would_warn": False,
            "current_usage_percentage": 0.0,
            "projected_usage_percentage": 0.0,
            "current_allocated_hours": 0.0,
            "new_allocation_hours": 0.0,
            "projected_allocated_hours": 0.0,
            "budgeted_hours": None,
            "remaining_after": None,
            "status": "no_budget",
            "message": "No budget set for this project. Allocation can proceed without budget checks."
        }
    
    # Helper function to compute hours from allocation (canonical: 40h/week, hours = total over range)
    def compute_allocation_hours(alloc_start: date, alloc_end: date, alloc_percentage: int = None, alloc_hours: int = None, alloc_type: str = "percentage") -> float:
        """Compute total hours for an allocation over its date range using business days."""
        from utils import compute_allocation_hours as _canonical
        return _canonical({
            "start_date": alloc_start,
            "end_date": alloc_end,
            "percentage": alloc_percentage,
            "hours": alloc_hours,
            "allocation_type": alloc_type,
        })
    
    # Get all existing allocations for this project (excluding the one being edited if any)
    allocations_cursor = allocations_collection.find({"project_id": project_id})
    allocations = await allocations_cursor.to_list(length=10000)
    
    # Filter out the allocation being edited
    if exclude_allocation_id:
        allocations = [a for a in allocations if str(a.get("_id")) != exclude_allocation_id]
    
    # Calculate current allocated hours
    current_allocated_hours = 0.0
    for alloc in allocations:
        alloc_start = alloc.get("start_date")
        alloc_end = alloc.get("end_date")
        
        # Convert datetime to date if needed
        if isinstance(alloc_start, datetime):
            alloc_start = alloc_start.date()
        if isinstance(alloc_end, datetime):
            alloc_end = alloc_end.date()
        
        alloc_type = alloc.get("allocation_type", "percentage")
        alloc_hours = alloc.get("hours")
        alloc_percentage = alloc.get("percentage", 0)
        
        current_allocated_hours += compute_allocation_hours(
            alloc_start, alloc_end, alloc_percentage, alloc_hours, alloc_type
        )
    
    # Calculate new allocation hours
    new_allocation_hours = compute_allocation_hours(
        start_date, end_date, percentage, hours, allocation_type
    )
    
    # Calculate projected hours
    projected_allocated_hours = current_allocated_hours + new_allocation_hours
    
    # Calculate percentages
    current_usage_percentage = (current_allocated_hours / budgeted_hours) * 100 if budgeted_hours > 0 else 0
    projected_usage_percentage = (projected_allocated_hours / budgeted_hours) * 100 if budgeted_hours > 0 else 0
    
    # Calculate remaining
    remaining_after = budgeted_hours - projected_allocated_hours
    
    # Determine status and warnings
    would_exceed = projected_usage_percentage > 100
    would_warn = projected_usage_percentage >= 90 and projected_usage_percentage <= 100
    
    if would_exceed:
        status = "exceeded"
        message = f"Warning: This allocation will push the project to {projected_usage_percentage:.1f}% of budget (over 100%). Proceed with caution."
    elif would_warn:
        status = "warning"
        message = f"This allocation will use {projected_usage_percentage:.1f}% of project budget. Proceed?"
    else:
        status = "ok"
        message = f"Allocation looks good. Project will be at {projected_usage_percentage:.1f}% of budget."
    
    return {
        "valid": True,  # Always true — we never hard-reject
        "would_exceed": would_exceed,
        "would_warn": would_warn,
        "current_usage_percentage": round(current_usage_percentage, 2),
        "projected_usage_percentage": round(projected_usage_percentage, 2),
        "current_allocated_hours": round(current_allocated_hours, 2),
        "new_allocation_hours": round(new_allocation_hours, 2),
        "projected_allocated_hours": round(projected_allocated_hours, 2),
        "budgeted_hours": budgeted_hours,
        "remaining_after": round(remaining_after, 2),
        "status": status,
        "message": message
    }


# =============================================================================
# TIMESHEET ENDPOINTS (Planned vs Actual Time Tracking)
# =============================================================================

# Helper function: Find resource for current user


# =============================================================================
# MY ALLOCATIONS ENDPOINT (Feature #8 - Resource self-service view)
# =============================================================================

@router.get("/api/my-allocations")
async def get_my_allocations(
    period: str = "month",
    current_user: dict = Depends(get_current_user)
):
    """
    Get allocations for the current logged-in user (resource self-service view).
    Allowed roles: resource, contractor, admin, super_admin (all except client).
    
    Query params:
    - period: "week" | "month" | "3months" (default: "month")
    
    Returns:
    - Summary: total allocations, capacity used %, total hours, etc.
    - List of allocations with per-allocation metrics (weekly hours, period hours)
    """
    from utils import find_user_resource
    
    # Validate period parameter
    allowed_periods = ["week", "month", "3months"]
    if period not in allowed_periods:
        raise HTTPException(
            status_code=400,
            detail=f"period must be one of {' | '.join(allowed_periods)}"
        )
    
    # Check role - clients not allowed
    if current_user.get("role") == UserRole.CLIENT:
        raise HTTPException(
            status_code=403,
            detail="This endpoint is not available for client users"
        )
    
    # Find user's linked resource
    resource = await find_user_resource(current_user)
    
    # Compute period dates based on period parameter
    today = datetime.now(timezone.utc).date()
    
    if period == "week":
        # "this and next week" = 14 days
        period_start = today
        period_end = today + timedelta(days=13)
    elif period == "month":
        # First day to last day of current month
        period_start = today.replace(day=1)
        # Last day of month: go to first day of next month, then subtract 1 day
        if today.month == 12:
            next_month_first = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month_first = today.replace(month=today.month + 1, day=1)
        period_end = next_month_first - timedelta(days=1)
    else:  # "3months"
        period_start = today
        period_end = today + timedelta(days=90)
    
    # If no resource linked, return empty data
    if not resource:
        return {
            "period": period,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "resource": None,
            "summary": {
                "total_allocations": 0,
                "capacity_used_percentage": 0,
                "is_over_capacity": False,
                "total_weekly_hours": 0.0,
                "total_period_hours": 0.0,
                "standard_capacity": 100
            },
            "allocations": []
        }
    
    resource_id = str(resource["_id"])
    resource_name = resource.get("name", "Unknown")
    resource_role = resource.get("role", "")
    standard_capacity = resource.get("standard_capacity", 100)
    
    # Convert period dates to datetime for MongoDB query
    period_start_dt = datetime.combine(period_start, datetime.min.time())
    period_end_dt = datetime.combine(period_end, datetime.max.time())
    
    # Query allocations that overlap the period for this resource
    # Overlap condition: allocation.start_date <= period_end AND allocation.end_date >= period_start
    allocations_cursor = allocations_collection.find({
        "resource_id": resource_id,
        "start_date": {"$lte": period_end_dt},
        "end_date": {"$gte": period_start_dt}
    })
    allocations = await allocations_cursor.to_list(length=10000)
    
    # Bulk-fetch projects
    project_ids = list(set(a.get("project_id") for a in allocations if a.get("project_id")))
    project_map = {}
    
    if project_ids:
        obj_ids = []
        for pid in project_ids:
            try:
                obj_ids.append(ObjectId(pid))
            except Exception:
                pass
        
        if obj_ids:
            proj_cursor = projects_collection.find(
                {"_id": {"$in": obj_ids}},
                {"name": 1, "client_name": 1, "status": 1}
            )
            async for p in proj_cursor:
                project_map[str(p["_id"])] = {
                    "name": p.get("name", "Unknown"),
                    "client_name": p.get("client_name", ""),
                    "status": p.get("status", "Active")
                }
    
    # Calculate per-allocation metrics
    allocation_results = []
    total_period_hours = 0.0
    
    for alloc in allocations:
        alloc_start = alloc.get("start_date")
        alloc_end = alloc.get("end_date")
        
        # Convert datetime to date for comparison if needed
        if isinstance(alloc_start, datetime):
            alloc_start = alloc_start.date()
        if isinstance(alloc_end, datetime):
            alloc_end = alloc_end.date()
        
        # Effective overlap with period
        effective_start = max(alloc_start, period_start)
        effective_end = min(alloc_end, period_end)
        
        # Days in period
        days_in_period = (effective_end - effective_start).days + 1
        if days_in_period < 0:
            days_in_period = 0
        
        # Business days in period (Mon-Fri only)
        from utils import count_business_days
        biz_days_in_period = count_business_days(effective_start, effective_end)
        weeks_in_period = biz_days_in_period / 5.0
        
        # Determine weekly hours based on allocation type (canonical: 40h/week)
        from utils import allocation_weekly_hours
        allocation_type = alloc.get("allocation_type", "percentage")
        percentage = alloc.get("percentage", 0)
        hours = alloc.get("hours")
        weekly_hours = allocation_weekly_hours(alloc)
        
        # Total hours in this period
        period_hours = weekly_hours * weeks_in_period
        total_period_hours += period_hours
        
        # Get project info
        project_id = alloc.get("project_id", "")
        p_info = project_map.get(project_id, {})
        
        allocation_results.append({
            "id": str(alloc["_id"]),
            "project_id": project_id,
            "project_name": p_info.get("name", "Unknown"),
            "client_name": p_info.get("client_name", ""),
            "project_status": p_info.get("status", "Active"),
            "role": alloc.get("role"),
            "percentage": percentage,
            "allocation_type": allocation_type,
            "hours": hours,
            "start_date": alloc_start.isoformat(),
            "end_date": alloc_end.isoformat(),
            "weekly_hours": round(weekly_hours, 2),
            "period_hours": round(period_hours, 2),
            "phase_names": alloc.get("phase_names"),
            "confirmation_status": alloc.get("confirmation_status", "Pending")
        })
    
    # Compute summary metrics
    # Capacity used: sum of percentages of allocations active TODAY (or period_start)
    reference_date = today  # Use today as reference for capacity calculation
    capacity_used_percentage = 0
    
    for alloc in allocations:
        alloc_start = alloc.get("start_date")
        alloc_end = alloc.get("end_date")
        
        if isinstance(alloc_start, datetime):
            alloc_start = alloc_start.date()
        if isinstance(alloc_end, datetime):
            alloc_end = alloc_end.date()
        
        # Check if allocation is active on reference date
        if alloc_start <= reference_date <= alloc_end:
            capacity_used_percentage += alloc.get("percentage", 0)
    
    is_over_capacity = capacity_used_percentage > standard_capacity
    
    # Total weekly hours: sum of weekly hours for allocations active today
    total_weekly_hours = 0.0
    for alloc in allocations:
        alloc_start = alloc.get("start_date")
        alloc_end = alloc.get("end_date")
        
        if isinstance(alloc_start, datetime):
            alloc_start = alloc_start.date()
        if isinstance(alloc_end, datetime):
            alloc_end = alloc_end.date()
        
        if alloc_start <= reference_date <= alloc_end:
            from utils import allocation_weekly_hours
            total_weekly_hours += allocation_weekly_hours(alloc)
    
    return {
        "period": period,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "resource": {
            "id": resource_id,
            "name": resource_name,
            "role": resource_role,
            "standard_capacity": standard_capacity
        },
        "summary": {
            "total_allocations": len(allocations),
            "capacity_used_percentage": capacity_used_percentage,
            "is_over_capacity": is_over_capacity,
            "total_weekly_hours": round(total_weekly_hours, 2),
            "total_period_hours": round(total_period_hours, 2),
            "standard_capacity": standard_capacity
        },
        "allocations": allocation_results
    }


# ========== PHASE-BASED ALLOCATIONS ==========

class PhaseAllocationUpdate(BaseModel):
    """Update phase allocations for a specific allocation"""
    phase_allocations: List[dict]  # List of {phase_id, percentage, hours}


@router.put("/api/allocations/{allocation_id}/phase-allocations")
async def update_phase_allocations(
    allocation_id: str,
    update: PhaseAllocationUpdate,
    admin: dict = Depends(require_admin)
):
    """
    Update phase-specific allocations for a resource allocation.
    
    This allows setting different allocation percentages per phase.
    For example: 100% in Phase 1, 50% in Phase 2, 0% in Phase 3.
    
    If phase_allocations is empty, the resource uses the project-level percentage for all phases.
    """
    # Validate allocation exists
    allocation = await allocations_collection.find_one({"_id": ObjectId(allocation_id)})
    if not allocation:
        raise HTTPException(status_code=404, detail="Allocation not found")
    
    # Validate phase allocations format
    for phase_alloc in update.phase_allocations:
        if "phase_id" not in phase_alloc:
            raise HTTPException(status_code=400, detail="Each phase allocation must have a phase_id")
        
        percentage = phase_alloc.get("percentage")
        if percentage is not None and (percentage < 0 or percentage > 100):
            raise HTTPException(status_code=400, detail="Percentage must be between 0 and 100")
    
    # Update the allocation with phase-specific allocations
    result = await allocations_collection.update_one(
        {"_id": ObjectId(allocation_id)},
        {"$set": {"phase_allocations": update.phase_allocations}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Allocation not found or no changes made")
    
    # Fetch and return updated allocation
    updated_allocation = await allocations_collection.find_one({"_id": ObjectId(allocation_id)})
    
    # Enrich with resource and project names
    resource = await resources_collection.find_one({"_id": ObjectId(updated_allocation["resource_id"])})
    project = await projects_collection.find_one({"_id": ObjectId(updated_allocation["project_id"])})
    
    updated_allocation["resource_name"] = resource.get("name") if resource else None
    updated_allocation["project_name"] = project.get("name") if project else None
    updated_allocation["client_name"] = project.get("client_name") if project else None
    
    return serialize_doc(updated_allocation)


@router.get("/api/projects/{project_id}/phase-allocations")
async def get_project_phase_allocations(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all resource allocations for a project with their phase-specific allocations.
    
    Returns a matrix view suitable for the Phase Allocation Editor:
    - List of resources
    - List of phases
    - Allocation percentages per resource per phase
    """
    # Fetch project to get phases
    project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    phases = project.get("phases", [])
    
    # Fetch all allocations for this project
    cursor = allocations_collection.find({"project_id": project_id})
    allocations = await cursor.to_list(length=1000)
    
    # Enrich with resource names
    result_allocations = []
    for alloc in allocations:
        resource = await resources_collection.find_one({"_id": ObjectId(alloc["resource_id"])})
        
        if resource:
            alloc["resource_name"] = resource.get("name", "Unknown")
            alloc["resource_role"] = resource.get("role", "")
            alloc["resource_standard_capacity"] = resource.get("standard_capacity", 100)  # NEW: Include standard capacity
            
            # For each phase, get the allocation percentage
            phase_details = []
            for phase in phases:
                phase_id = phase.get("id")
                from utils import get_allocation_for_phase, get_allocation_hours_for_phase
                
                percentage = get_allocation_for_phase(alloc, phase_id)
                hours = get_allocation_hours_for_phase(alloc, phase_id)
                
                phase_details.append({
                    "phase_id": phase_id,
                    "phase_name": phase.get("name"),
                    "percentage": percentage,
                    "hours": round(hours, 1)
                })
            
            alloc["phase_details"] = phase_details
            result_allocations.append(serialize_doc(alloc))
    
    return {
        "project_id": project_id,
        "project_name": project.get("name"),
        "phases": phases,
        "allocations": result_allocations
    }
