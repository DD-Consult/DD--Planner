from bson import ObjectId
from datetime import date, datetime, timedelta, timezone
import re

from database import resources_collection, SYDNEY_TZ


def serialize_doc(doc):
    """Convert MongoDB document(s) to JSON-serializable format.

    IMPORTANT: If the doc contains BOTH `_id` (ObjectId) and a legacy/stale
    `id` string field, the ObjectId-derived value wins. This preserves the
    invariant from the pre-refactor implementation, where the returned `id`
    always matches the document's actual `_id` so that subsequent
    `find_one({"_id": ObjectId(returned_id)})` calls succeed.
    """
    if isinstance(doc, list):
        return [serialize_doc(d) for d in doc]
    if isinstance(doc, dict):
        result = {}
        has_mongo_id = '_id' in doc
        for key, value in doc.items():
            if key == '_id':
                result['id'] = str(value)
            elif key == 'id' and has_mongo_id:
                # Skip stale top-level 'id' field; _id takes precedence
                continue
            elif isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, date):
                result[key] = value.isoformat()
            elif isinstance(value, list):
                result[key] = [serialize_doc(v) if isinstance(v, dict) else v for v in value]
            elif isinstance(value, dict):
                result[key] = serialize_doc(value)
            else:
                result[key] = value
        return result
    return doc


def ensure_phase_ids(phases):
    """Ensure all phases have unique IDs."""
    import uuid
    for phase in phases:
        if not phase.get("id") or phase["id"] in ("", "None", None):
            phase["id"] = str(uuid.uuid4())
    return phases


async def find_user_resource(current_user: dict):
    """
    Find resource for current user.
    Priority: 1) resource_id FK on user, 2) email match, 3) normalized name match.
    """
    if current_user.get("resource_id"):
        resource = await resources_collection.find_one({"_id": ObjectId(current_user["resource_id"])})
        if resource:
            return resource

    resource = await resources_collection.find_one({"email": current_user["email"]})
    if resource:
        return resource

    def _norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower())

    email_prefix = current_user["email"].split("@")[0].lower()
    email_norm = _norm(email_prefix)
    email_parts = [p for p in re.split(r"[._\-]", email_prefix) if p]

    cursor = resources_collection.find()
    resources = await cursor.to_list(length=1000)

    for r in resources:
        if _norm(r.get("name", "")) == email_norm:
            return r

    if email_parts:
        first_part = email_parts[0]
        for r in resources:
            name_parts = r.get("name", "").lower().split()
            if name_parts and name_parts[0] == first_part:
                return r

    if len(email_parts) > 1:
        for r in resources:
            name_lower = r.get("name", "").lower()
            if all(part in name_lower for part in email_parts):
                return r

    for r in resources:
        name_norm = _norm(r.get("name", ""))
        if email_norm and name_norm and (email_norm in name_norm or name_norm in email_norm):
            return r

    return None


async def deactivate_resource_core(resource_id: str) -> dict:
    """Soft-delete a resource: keep all history, end future allocations today,
    disable linked login accounts. Returns a summary dict."""
    from database import resources_collection as rc, allocations_collection, users_collection
    res = await rc.find_one({"_id": ObjectId(resource_id)})
    if not res:
        return {"success": False, "message": "Resource not found"}
    now = datetime.now(timezone.utc)
    today = datetime(now.year, now.month, now.day)
    removed = await allocations_collection.delete_many({
        "resource_id": resource_id, "start_date": {"$gt": today},
    })
    trimmed = await allocations_collection.update_many(
        {"resource_id": resource_id, "start_date": {"$lte": today}, "end_date": {"$gt": today}},
        {"$set": {"end_date": today}},
    )
    await rc.update_one(
        {"_id": ObjectId(resource_id)},
        {"$set": {"active": False, "deactivated_at": now.isoformat()}},
    )
    users = await users_collection.update_many(
        {"resource_id": resource_id}, {"$set": {"disabled": True}}
    )
    return {
        "success": True,
        "name": res.get("name", "?"),
        "future_allocations_removed": removed.deleted_count,
        "allocations_ended_today": trimmed.modified_count,
        "users_disabled": users.modified_count,
        "message": (
            f"Resource '{res.get('name')}' deactivated. "
            f"{removed.deleted_count} future allocation(s) removed, "
            f"{trimmed.modified_count} active allocation(s) ended today, "
            f"{users.modified_count} linked login(s) disabled. History preserved."
        ),
    }


async def reactivate_resource_core(resource_id: str) -> dict:
    """Reactivate a resource and re-enable linked login accounts."""
    from database import resources_collection as rc, users_collection
    res = await rc.find_one({"_id": ObjectId(resource_id)})
    if not res:
        return {"success": False, "message": "Resource not found"}
    await rc.update_one(
        {"_id": ObjectId(resource_id)},
        {"$set": {"active": True}, "$unset": {"deactivated_at": ""}},
    )
    users = await users_collection.update_many(
        {"resource_id": resource_id}, {"$set": {"disabled": False}}
    )
    return {
        "success": True,
        "name": res.get("name", "?"),
        "users_enabled": users.modified_count,
        "message": f"Resource '{res.get('name')}' reactivated. {users.modified_count} linked login(s) re-enabled.",
    }


async def user_leads_project(current_user: dict, project_id: str) -> bool:
    """True if the user is admin/super_admin OR their linked resource is the project's lead."""
    role = (current_user.get("role") or "").lower()
    if role in ("admin", "super_admin"):
        return True
    resource = await find_user_resource(current_user)
    if not resource:
        return False
    from database import projects_collection
    try:
        project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    except Exception:
        return False
    return bool(project and str(project.get("project_lead_id") or "") == str(resource["_id"]))


def calculate_weekly_hours(percentage: int, allocation_start: date, allocation_end: date, week_start: date, week_end: date) -> float:
    """Calculate planned hours for a specific week based on allocation percentage.
    Uses 5-day business week (Mon-Fri) for all calculations."""
    HOURS_PER_WEEK = 40.0
    BUSINESS_DAYS_PER_WEEK = 5
    overlap_start = max(allocation_start, week_start)
    overlap_end = min(allocation_end, week_end)
    if overlap_start > overlap_end:
        return 0.0
    # Count only business days in the overlap
    overlap_biz_days = count_business_days(overlap_start, overlap_end)
    weekly_hours = (percentage / 100.0) * HOURS_PER_WEEK
    if overlap_biz_days < BUSINESS_DAYS_PER_WEEK:
        prorated_hours = weekly_hours * (overlap_biz_days / BUSINESS_DAYS_PER_WEEK)
        return round(prorated_hours, 2)
    return round(weekly_hours, 2)



def is_timesheet_update_allowed():
    """Check if current time in Sydney is within the update window: Thursday 00:00 to Monday 12:00"""
    sydney_now = datetime.now(SYDNEY_TZ)
    weekday = sydney_now.weekday()
    if weekday in [3, 4, 5, 6]:
        return True
    if weekday == 0 and sydney_now.hour < 12:
        return True
    return False


def get_next_allowed_timesheet_day():
    """Get the next Thursday in Sydney timezone"""
    sydney_now = datetime.now(SYDNEY_TZ)
    current_weekday = sydney_now.weekday()
    days_until_thursday = (3 - current_weekday) % 7
    if days_until_thursday == 0 and not is_timesheet_update_allowed():
        days_until_thursday = 7
    next_thursday = sydney_now + timedelta(days=days_until_thursday)
    return next_thursday.replace(hour=0, minute=0, second=0, microsecond=0)


def get_allocation_for_phase(allocation: dict, phase_id: str) -> int:
    """
    Get allocation percentage for a specific phase.
    
    If phase_allocations is defined and contains the phase_id, use that percentage.
    Otherwise, fall back to the project-level percentage.
    
    Args:
        allocation: Allocation document from MongoDB
        phase_id: Phase ID to get allocation for
        
    Returns:
        Allocation percentage for the phase (0-100)
    """
    phase_allocations = allocation.get("phase_allocations", [])
    
    if phase_allocations:
        # Look for phase-specific allocation
        for phase_alloc in phase_allocations:
            if phase_alloc.get("phase_id") == phase_id:
                return phase_alloc.get("percentage", allocation.get("percentage", 0))
    
    # Fall back to project-level percentage
    return allocation.get("percentage", 0)


def get_allocation_hours_for_phase(allocation: dict, phase_id: str, default_weekly_hours: float = 40.0) -> float:
    """
    Calculate weekly hours for a specific phase based on allocation percentage.
    
    Args:
        allocation: Allocation document from MongoDB
        phase_id: Phase ID to get hours for
        default_weekly_hours: Standard full-time hours per week (default: 40)
        
    Returns:
        Weekly hours for the phase allocation
    """
    percentage = get_allocation_for_phase(allocation, phase_id)
    return (percentage / 100.0) * default_weekly_hours



def count_business_days(start_date, end_date):
    """Count business days (Monday-Friday) between two dates, inclusive.
    
    Handles both date and datetime objects.
    """
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()
    if start_date > end_date:
        return 0
    business_days = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # Monday=0 through Friday=4
            business_days += 1
        current += timedelta(days=1)
    return business_days


def snap_to_weekday(d):
    """Snap a date to the nearest weekday. Saturday→Monday, Sunday→Monday."""
    if isinstance(d, datetime):
        d = d.date()
    if d.weekday() == 5:  # Saturday
        return d + timedelta(days=2)
    if d.weekday() == 6:  # Sunday
        return d + timedelta(days=1)
    return d


# ============================================================
# CANONICAL HOUR CALCULATIONS — single source of truth
# Standard work week: 40 hours (8h/day × Mon-Fri)
# ============================================================

HOURS_PER_WEEK = 40.0
HOURS_PER_DAY = 8.0


def coerce_date(d):
    """Coerce datetime/str/date into a date, or None."""
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    try:
        return datetime.fromisoformat(str(d)[:10]).date()
    except Exception:
        return None


def allocation_weekly_hours(allocation: dict) -> float:
    """Canonical weekly hours for an allocation (100% = 40h/week).
    'hours' allocation type = TOTAL hours spread evenly over the allocation range."""
    if allocation.get("allocation_type") == "hours" and allocation.get("hours") is not None:
        s = coerce_date(allocation.get("start_date"))
        e = coerce_date(allocation.get("end_date"))
        total_biz = count_business_days(s, e) if s and e else 0
        if total_biz <= 0:
            return 0.0
        return float(allocation["hours"]) / (total_biz / 5.0)
    return ((allocation.get("percentage") or 0) / 100.0) * HOURS_PER_WEEK


def compute_allocation_hours(allocation: dict, clip_start=None, clip_end=None) -> float:
    """Canonical TOTAL hours for an allocation, optionally clipped to a window.
    Formula: weekly_hours × (business_days_in_window / 5)."""
    s = coerce_date(allocation.get("start_date"))
    e = coerce_date(allocation.get("end_date"))
    if not s or not e:
        return 0.0
    cs = max(s, coerce_date(clip_start)) if clip_start else s
    ce = min(e, coerce_date(clip_end)) if clip_end else e
    if cs > ce:
        return 0.0
    biz = count_business_days(cs, ce)
    return allocation_weekly_hours(allocation) * (biz / 5.0)


def compute_phase_allocated_hours(allocation: dict, phase: dict) -> float:
    """Canonical phase attribution for allocated hours:
    1. Per-phase percentage (phase_allocations) wins when set.
    2. Else phase_names filter excludes non-matching phases.
    3. Hours are clipped to the phase date range (no double counting)."""
    phase_id = phase.get("id")
    p_start = coerce_date(phase.get("start_date"))
    p_end = coerce_date(phase.get("end_date"))

    for pa in (allocation.get("phase_allocations") or []):
        if pa.get("phase_id") == phase_id and pa.get("percentage") is not None:
            s = coerce_date(allocation.get("start_date"))
            e = coerce_date(allocation.get("end_date"))
            if not s or not e:
                return 0.0
            cs = max(s, p_start) if p_start else s
            ce = min(e, p_end) if p_end else e
            if cs > ce:
                return 0.0
            biz = count_business_days(cs, ce)
            return (pa["percentage"] / 100.0) * HOURS_PER_WEEK * (biz / 5.0)

    names = allocation.get("phase_names") or []
    if names and phase.get("name") not in names:
        return 0.0
    if p_start and p_end:
        return compute_allocation_hours(allocation, p_start, p_end)
    return compute_allocation_hours(allocation)


def wbs_parent_id_set(tasks: list) -> set:
    """Set of parent identifiers referenced by any task."""
    return {str(t.get("parent_id")) for t in tasks if t.get("parent_id")}


def is_leaf_task(task: dict, parent_ids: set) -> bool:
    """A task is a leaf if neither its Mongo _id nor its internal uuid id is referenced as a parent."""
    return not ({str(task.get("_id")), str(task.get("id"))} & parent_ids)


def leaf_estimated_hours(tasks: list) -> float:
    """Sum estimated_hours over LEAF WBS tasks only (avoids double counting parents)."""
    parent_ids = wbs_parent_id_set(tasks)
    return sum(
        float(t.get("estimated_hours") or 0)
        for t in tasks
        if is_leaf_task(t, parent_ids)
    )
