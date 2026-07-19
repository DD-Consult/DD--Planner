from bson import ObjectId
from datetime import date, datetime, timedelta
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


def get_allocation_hours_for_phase(allocation: dict, phase_id: str, default_weekly_hours: float = 38.0) -> float:
    """
    Calculate weekly hours for a specific phase based on allocation percentage.
    
    Args:
        allocation: Allocation document from MongoDB
        phase_id: Phase ID to get hours for
        default_weekly_hours: Standard full-time hours per week (default: 38)
        
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
