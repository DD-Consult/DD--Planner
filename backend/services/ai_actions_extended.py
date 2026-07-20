"""
Extended AI Action Handlers
============================
All NEW handlers added for full admin parity, registered with the action
registry. Each handler is a thin wrapper that mirrors the corresponding
admin REST endpoint — DB writes + return {success, message, ...}.

The existing 16 actions remain in `services/ai_actions.py` and are dispatched
by `dispatch_action`'s legacy-fallback path.
"""
from __future__ import annotations

import re
import uuid as uuid_module
from datetime import datetime, date, timedelta, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId

from database import (
    projects_collection, resources_collection, allocations_collection,
    timesheets_collection, risks_collection, leaves_collection,
    holidays_collection, wbs_tasks_collection, baselines_collection,
    users_collection, notifications_collection,
)
from auth.dependencies import get_password_hash
from services.ai_action_registry import register


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

def _ok(message: str, **extra) -> dict:
    return {"success": True, "message": message, **extra}


def _err(message: str, **extra) -> dict:
    return {"success": False, "message": message, **extra}


def _parse_date(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        if isinstance(s, datetime):
            return s
        return datetime.strptime(str(s)[:10], "%Y-%m-%d")
    except Exception:
        return None


async def _find_project(project_id: str) -> Optional[dict]:
    if ObjectId.is_valid(project_id):
        p = await projects_collection.find_one({"_id": ObjectId(project_id)})
        if p:
            return p
    return await projects_collection.find_one({"id": project_id})


# ═════════════════════════════════════════════════════════════════════════
# TIER 1 — Critical project / phase / risk / resource handlers
# ═════════════════════════════════════════════════════════════════════════

async def _h_update_project(action: dict, user: dict) -> dict:
    """Patch any subset of fields on a project."""
    pid = action.get("project_id")
    if not pid or not ObjectId.is_valid(pid):
        return _err("Invalid project_id")
    update_data: Dict[str, Any] = {}
    for f in ("name", "client_name", "status", "budgeted_hours", "project_objective",
              "google_drive_url", "project_lead_id"):
        if f in action and action[f] is not None:
            update_data[f] = action[f]
    for f in ("start_date", "end_date"):
        if f in action and action[f]:
            d = _parse_date(action[f])
            if d:
                update_data[f] = d
    if not update_data:
        return _err("No fields provided to update")
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    r = await projects_collection.update_one({"_id": ObjectId(pid)}, {"$set": update_data})
    if r.matched_count == 0:
        return _err("Project not found")
    return _ok(f"Project updated ({len(update_data)} field(s))")


async def _h_delete_project(action: dict, user: dict) -> dict:
    pid = action.get("project_id")
    if not pid or not ObjectId.is_valid(pid):
        return _err("Invalid project_id")
    proj = await projects_collection.find_one({"_id": ObjectId(pid)})
    if not proj:
        return _err("Project not found")
    name = proj.get("name", "?")
    # Cascade — delete allocations, timesheets, risks, baselines, status updates, WBS
    await allocations_collection.delete_many({"project_id": pid})
    await timesheets_collection.delete_many({"project_id": pid})
    await risks_collection.delete_many({"project_id": pid})
    await baselines_collection.delete_many({"project_id": pid})
    await wbs_tasks_collection.delete_many({"project_id": pid})
    await projects_collection.delete_one({"_id": ObjectId(pid)})
    return _ok(f"Project '{name}' and all its related data deleted")


async def _h_manage_phases(action: dict, user: dict) -> dict:
    """Merge or replace the phases array.

    Default mode is 'merge' (upsert): phases in the action payload are added or
    updated by name/id match; existing phases NOT in the payload are kept intact.
    Pass `"mode": "replace"` to fully replace the array (old behaviour).
    """
    pid = action.get("project_id")
    if not pid or not ObjectId.is_valid(pid):
        return _err("Invalid project_id")
    incoming = action.get("phases") or []
    if not isinstance(incoming, list):
        return _err("`phases` must be a list")

    proj = await projects_collection.find_one({"_id": ObjectId(pid)})
    if not proj:
        return _err("Project not found")

    existing_phases: List[dict] = list(proj.get("phases") or [])
    mode = (action.get("mode") or "merge").lower()

    def _normalise(ph: dict) -> dict:
        """Return a clean phase dict from raw input."""
        result = {
            "id": ph.get("id") or str(uuid_module.uuid4()),
            "name": ph["name"],
            "start_date": ph.get("start_date"),
            "end_date": ph.get("end_date"),
            "status": ph.get("status", "Not Started"),
        }
        if ph.get("budgeted_hours") is not None:
            result["budgeted_hours"] = ph["budgeted_hours"]
        return result

    if mode == "replace":
        # Legacy: throw away existing, use only what was supplied
        cleaned = [_normalise(ph) for ph in incoming if isinstance(ph, dict) and ph.get("name")]
    else:
        # MERGE (default): upsert incoming phases into existing list
        # Build lookup maps from existing phases
        by_id: dict[str, int] = {}
        by_name: dict[str, int] = {}
        for i, ph in enumerate(existing_phases):
            if ph.get("id"):
                by_id[ph["id"]] = i
            by_name[ph.get("name", "").strip().lower()] = i

        cleaned = list(existing_phases)  # start from existing
        for ph in incoming:
            if not isinstance(ph, dict) or not ph.get("name"):
                continue
            # Determine if this phase already exists (by id or name)
            idx = by_id.get(ph.get("id", ""))
            if idx is None:
                idx = by_name.get(ph["name"].strip().lower())

            if idx is not None:
                # UPDATE existing phase — only overwrite fields that were supplied
                existing_ph = dict(cleaned[idx])
                if ph.get("id"):
                    existing_ph["id"] = ph["id"]
                existing_ph["name"] = ph["name"]
                for f in ("start_date", "end_date", "status", "budgeted_hours"):
                    if ph.get(f) is not None:
                        existing_ph[f] = ph[f]
                cleaned[idx] = existing_ph
            else:
                # ADD new phase — assign id if missing
                new_ph = _normalise(ph)
                cleaned.append(new_ph)
                by_id[new_ph["id"]] = len(cleaned) - 1
                by_name[new_ph["name"].strip().lower()] = len(cleaned) - 1

    await projects_collection.update_one(
        {"_id": ObjectId(pid)},
        {"$set": {"phases": cleaned, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    action_taken = "replaced" if mode == "replace" else "merged"
    return _ok(f"Phases {action_taken} — project now has {len(cleaned)} phase(s)")


async def _h_delete_risk(action: dict, user: dict) -> dict:
    rid = action.get("risk_id")
    if not rid or not ObjectId.is_valid(rid):
        return _err("Invalid risk_id")
    risk = await risks_collection.find_one({"_id": ObjectId(rid)})
    if not risk:
        return _err("Risk not found")
    await risks_collection.delete_one({"_id": ObjectId(rid)})
    return _ok(f"Risk removed", project_id=str(risk.get("project_id")))


async def _h_create_resource(action: dict, user: dict) -> dict:
    doc = {
        "name": action["name"],
        "role": action.get("role", ""),
        "standard_capacity": int(action.get("standard_capacity") or 100),
        "avatar_url": action.get("avatar_url"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    r = await resources_collection.insert_one(doc)
    return _ok(f"Resource '{action['name']}' created", id=str(r.inserted_id))


async def _h_update_resource(action: dict, user: dict) -> dict:
    rid = action.get("resource_id")
    if not rid or not ObjectId.is_valid(rid):
        return _err("Invalid resource_id")
    upd = {k: v for k, v in action.items() if k in ("name", "role", "standard_capacity", "avatar_url") and v is not None}
    if not upd:
        return _err("No fields to update")
    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    r = await resources_collection.update_one({"_id": ObjectId(rid)}, {"$set": upd})
    if r.matched_count == 0:
        return _err("Resource not found")
    return _ok(f"Resource updated ({len(upd)} field(s))")


async def _h_delete_resource(action: dict, user: dict) -> dict:
    rid = action.get("resource_id")
    if not rid or not ObjectId.is_valid(rid):
        return _err("Invalid resource_id")
    res = await resources_collection.find_one({"_id": ObjectId(rid)})
    if not res:
        return _err("Resource not found")
    name = res.get("name", "?")
    # Hard delete only when there is NO history — otherwise suggest deactivation
    al = await allocations_collection.count_documents({"resource_id": rid})
    ts = await timesheets_collection.count_documents({"resource_id": rid})
    lead_count = await projects_collection.count_documents({"project_lead_id": rid})
    if al or ts or lead_count:
        return _err(
            f"'{name}' has history ({al} allocation(s), {ts} timesheet(s), lead of {lead_count} project(s)). "
            f"Use deactivate_resource instead — it preserves history, ends future allocations and disables their login."
        )
    await resources_collection.delete_one({"_id": ObjectId(rid)})
    await users_collection.update_many({"resource_id": rid}, {"$unset": {"resource_id": ""}})
    return _ok(f"Resource '{name}' deleted (no history existed)")


async def _h_deactivate_resource(action: dict, user: dict) -> dict:
    rid = action.get("resource_id")
    if not rid or not ObjectId.is_valid(rid):
        return _err("Invalid resource_id")
    from utils import deactivate_resource_core
    result = await deactivate_resource_core(rid)
    return _ok(result["message"]) if result.get("success") else _err(result.get("message", "Failed"))


async def _h_reactivate_resource(action: dict, user: dict) -> dict:
    rid = action.get("resource_id")
    if not rid or not ObjectId.is_valid(rid):
        return _err("Invalid resource_id")
    from utils import reactivate_resource_core
    result = await reactivate_resource_core(rid)
    return _ok(result["message"]) if result.get("success") else _err(result.get("message", "Failed"))


async def _h_sync_phase_to_wbs(action: dict, user: dict) -> dict:
    pid = action.get("project_id")
    phase_id = action.get("phase_id")
    if not pid or not phase_id:
        return _err("project_id and phase_id required")
    from services.budget_reconciliation import derive_phase_dates_from_wbs
    canonical_pid = pid if not ObjectId.is_valid(pid) else pid
    derived = await derive_phase_dates_from_wbs(canonical_pid, phase_id)
    if not derived.get("derived_start") or not derived.get("derived_end"):
        return _err("No WBS tasks with dates exist for this phase")
    proj = await _find_project(pid)
    if not proj:
        return _err("Project not found")
    phases = proj.get("phases") or []
    updated = False
    for ph in phases:
        if ph.get("id") == phase_id:
            ph["start_date"] = derived["derived_start"]
            ph["end_date"] = derived["derived_end"]
            updated = True
            break
    if not updated:
        return _err("Phase not found")
    await projects_collection.update_one(
        {"_id": proj["_id"]},
        {"$set": {"phases": phases, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return _ok(f"Phase dates synced to WBS: {derived['derived_start']} → {derived['derived_end']}")


async def _h_polish_all_risks(action: dict, user: dict) -> dict:
    pid = action.get("project_id")
    if not pid:
        return _err("project_id required")
    proj = await _find_project(pid)
    if not proj:
        return _err("Project not found")
    canonical = str(proj["_id"])
    cursor = risks_collection.find({
        "project_id": canonical,
        "$or": [{"ai_polished": {"$ne": True}}, {"ai_polished": {"$exists": False}}],
    })
    risks_to_polish = await cursor.to_list(length=500)
    if not risks_to_polish:
        return _ok("All risks already polished", polished=0)
    from services.risk_ai import polish_risk
    polished = 0
    ctx = f"Project: {proj.get('name')}"
    for risk in risks_to_polish:
        try:
            res = await polish_risk({k: risk.get(k) for k in
                                     ("description", "impact", "probability", "mitigation", "category", "impact_areas")},
                                    project_context=ctx)
            if res and res.get("ai_polished"):
                await risks_collection.update_one({"_id": risk["_id"]}, {"$set": {**{
                    k: res[k] for k in ("description", "category", "impact", "probability", "impact_areas", "mitigation")
                }, "ai_polished": True, "updated_at": datetime.now(timezone.utc).isoformat()}})
                polished += 1
        except Exception:
            pass
    return _ok(f"Polished {polished} risk(s)", polished=polished)


async def _h_reschedule_project(action: dict, user: dict) -> dict:
    """Shift project start (and optionally end) by N days, dragging phases along."""
    pid = action.get("project_id")
    if not pid or not ObjectId.is_valid(pid):
        return _err("Invalid project_id")
    shift_days = int(action.get("shift_days") or 0)
    if shift_days == 0:
        return _err("shift_days must be non-zero")
    proj = await projects_collection.find_one({"_id": ObjectId(pid)})
    if not proj:
        return _err("Project not found")
    delta = timedelta(days=shift_days)
    new_start = (proj.get("start_date") + delta) if isinstance(proj.get("start_date"), datetime) else None
    new_end = (proj.get("end_date") + delta) if isinstance(proj.get("end_date"), datetime) else None
    upd: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if new_start:
        upd["start_date"] = new_start
    if new_end:
        upd["end_date"] = new_end
    # Shift phases too
    new_phases = []
    for ph in (proj.get("phases") or []):
        try:
            ps = _parse_date(ph.get("start_date"))
            pe = _parse_date(ph.get("end_date"))
            if ps:
                ph["start_date"] = (ps + delta).date().isoformat()
            if pe:
                ph["end_date"] = (pe + delta).date().isoformat()
        except Exception:
            pass
        new_phases.append(ph)
    upd["phases"] = new_phases
    await projects_collection.update_one({"_id": ObjectId(pid)}, {"$set": upd})
    return _ok(f"Project rescheduled by {shift_days} days")


# ═════════════════════════════════════════════════════════════════════════
# TIER 2 — Operational: timesheet, leave, holiday, baseline, move resource
# ═════════════════════════════════════════════════════════════════════════

async def _h_create_timesheet(action: dict, user: dict) -> dict:
    doc = {
        "resource_id": action["resource_id"],
        "project_id": action["project_id"],
        "phase_id": action.get("phase_id"),
        "task_id": action.get("task_id"),
        "task_name": action.get("task_name"),
        "week_start_date": action["week_start_date"],
        "planned_hours": float(action.get("planned_hours") or 0),
        "actual_hours": float(action.get("actual_hours") or 0),
        "notes": action.get("notes", ""),
        "status": action.get("status", "Draft"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    r = await timesheets_collection.insert_one(doc)
    return _ok("Timesheet entry created", id=str(r.inserted_id))


async def _h_update_timesheet(action: dict, user: dict) -> dict:
    tid = action.get("timesheet_id")
    if not tid or not ObjectId.is_valid(tid):
        return _err("Invalid timesheet_id")
    upd = {k: v for k, v in action.items()
           if k in ("planned_hours", "actual_hours", "notes", "status", "phase_id", "task_id", "task_name") and v is not None}
    if not upd:
        return _err("No fields to update")
    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    r = await timesheets_collection.update_one({"_id": ObjectId(tid)}, {"$set": upd})
    if r.matched_count == 0:
        return _err("Timesheet not found")
    return _ok(f"Timesheet updated ({len(upd)-1} field(s))")


async def _h_delete_timesheet(action: dict, user: dict) -> dict:
    tid = action.get("timesheet_id")
    if not tid or not ObjectId.is_valid(tid):
        return _err("Invalid timesheet_id")
    r = await timesheets_collection.delete_one({"_id": ObjectId(tid)})
    if r.deleted_count == 0:
        return _err("Timesheet not found")
    return _ok("Timesheet deleted")


async def _h_submit_timesheet_week(action: dict, user: dict) -> dict:
    rid = action.get("resource_id")
    week = action.get("week_start_date")
    if not rid or not week:
        return _err("resource_id and week_start_date required")
    r = await timesheets_collection.update_many(
        {"resource_id": rid, "week_start_date": week, "status": {"$ne": "Submitted"}},
        {"$set": {"status": "Submitted", "submitted_at": datetime.now(timezone.utc).isoformat()}},
    )
    return _ok(f"Submitted {r.modified_count} timesheet row(s) for week {week}")


async def _h_autofill_timesheets_week(action: dict, user: dict) -> dict:
    """Generate timesheet rows for a resource's allocations for one week."""
    rid = action.get("resource_id")
    week = action.get("week_start_date")
    if not rid or not week:
        return _err("resource_id and week_start_date required")
    try:
        week_start = datetime.strptime(week, "%Y-%m-%d")
    except Exception:
        return _err("week_start_date must be YYYY-MM-DD")
    week_end = week_start + timedelta(days=4)  # Friday
    allocs = await allocations_collection.find({"resource_id": rid}).to_list(length=100)
    created = 0
    for a in allocs:
        a_start = a.get("start_date")
        a_end = a.get("end_date")
        if not isinstance(a_start, datetime) or not isinstance(a_end, datetime):
            continue
        if a_start > week_end or a_end < week_start:
            continue
        # Check duplicate
        existing = await timesheets_collection.find_one({
            "resource_id": rid,
            "project_id": a.get("project_id"),
            "week_start_date": week,
        })
        if existing:
            continue
        planned = (float(a.get("percentage", 0)) / 100.0) * 40.0  # 40h work week
        await timesheets_collection.insert_one({
            "resource_id": rid,
            "project_id": a.get("project_id"),
            "week_start_date": week,
            "planned_hours": round(planned, 2),
            "actual_hours": round(planned, 2),
            "status": "Draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        created += 1
    return _ok(f"Autofilled {created} timesheet row(s) for week {week}")


async def _h_create_leave(action: dict, user: dict) -> dict:
    doc = {
        "resource_id": action["resource_id"],
        "start_date": _parse_date(action["start_date"]),
        "end_date": _parse_date(action["end_date"]),
        "type": action.get("type") or action.get("reason") or "Annual Leave",
        "notes": action.get("notes") or action.get("reason") or "",
        "status": action.get("status", "Approved"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    r = await leaves_collection.insert_one(doc)
    return _ok("Leave entry created", id=str(r.inserted_id))


async def _h_delete_leave(action: dict, user: dict) -> dict:
    lid = action.get("leave_id")
    if not lid or not ObjectId.is_valid(lid):
        return _err("Invalid leave_id")
    r = await leaves_collection.delete_one({"_id": ObjectId(lid)})
    return _ok("Leave deleted") if r.deleted_count else _err("Leave not found")


async def _h_create_holiday(action: dict, user: dict) -> dict:
    doc = {
        "date": _parse_date(action["date"]),
        "name": action["name"],
        "region": action.get("region", "AU"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    r = await holidays_collection.insert_one(doc)
    return _ok(f"Holiday '{action['name']}' created", id=str(r.inserted_id))


async def _h_delete_holiday(action: dict, user: dict) -> dict:
    hid = action.get("holiday_id")
    if not hid or not ObjectId.is_valid(hid):
        return _err("Invalid holiday_id")
    r = await holidays_collection.delete_one({"_id": ObjectId(hid)})
    return _ok("Holiday deleted") if r.deleted_count else _err("Holiday not found")


async def _h_create_baseline(action: dict, user: dict) -> dict:
    from services.baselines import create_baseline
    pid = action.get("project_id")
    proj = await _find_project(pid)
    if not proj:
        return _err("Project not found")
    canonical = str(proj["_id"])
    try:
        b = await create_baseline(
            canonical,
            name=action["name"],
            description=action.get("description"),
            created_by=user.get("email", "ai"),
            set_current=bool(action.get("set_current", True)),
        )
        return _ok(f"Baseline '{action['name']}' created", id=b.get("id"))
    except Exception as e:
        return _err(f"Baseline creation failed: {e}")


async def _h_set_current_baseline(action: dict, user: dict) -> dict:
    from services.baselines import set_current_baseline
    pid = action.get("project_id")
    bid = action.get("baseline_id")
    proj = await _find_project(pid)
    if not proj:
        return _err("Project not found")
    ok = await set_current_baseline(str(proj["_id"]), bid)
    return _ok("Baseline set as current") if ok else _err("Baseline not found")


async def _h_delete_baseline(action: dict, user: dict) -> dict:
    from services.baselines import delete_baseline
    bid = action.get("baseline_id")
    try:
        ok = await delete_baseline(bid)
        return _ok("Baseline deleted") if ok else _err("Baseline not found")
    except ValueError as e:
        return _err(str(e))


async def _h_move_resource_between_projects(action: dict, user: dict) -> dict:
    """Remove an allocation from one project, create on another."""
    rid = action["resource_id"]
    from_pid = action["from_project_id"]
    to_pid = action["to_project_id"]
    pct = int(action.get("percentage") or 100)
    start = _parse_date(action["start_date"])
    end = _parse_date(action["end_date"])
    # Find the source allocation
    src = await allocations_collection.find_one({"resource_id": rid, "project_id": from_pid})
    if src:
        await allocations_collection.delete_one({"_id": src["_id"]})
    # Create new
    await allocations_collection.insert_one({
        "resource_id": rid,
        "project_id": to_pid,
        "percentage": pct,
        "start_date": start,
        "end_date": end,
        "allocation_type": "percentage",
        "confirmation_status": "Pending",
    })
    return _ok(f"Moved resource from {from_pid[:8]}… to {to_pid[:8]}… at {pct}%")


# ═════════════════════════════════════════════════════════════════════════
# TIER 3 — Super-admin: user management + system
# ═════════════════════════════════════════════════════════════════════════

async def _h_create_user(action: dict, user: dict) -> dict:
    email = (action.get("email") or "").strip().lower()
    pw = action.get("password")
    role = action.get("role", "resource")
    if not email or not pw:
        return _err("email and password required")
    if await users_collection.find_one({"email": email}):
        return _err("User with that email already exists")
    await users_collection.insert_one({
        "email": email,
        "password_hash": get_password_hash(pw),
        "role": role,
        "allowed_project_ids": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return _ok(f"User '{email}' created with role '{role}'")


async def _h_update_user_role(action: dict, user: dict) -> dict:
    email = (action.get("user_email") or "").strip().lower()
    role = action.get("new_role")
    if not email or not role:
        return _err("user_email and new_role required")
    r = await users_collection.update_one({"email": email}, {"$set": {"role": role}})
    if r.matched_count == 0:
        return _err("User not found")
    return _ok(f"User '{email}' role updated to '{role}'")


async def _h_disable_user(action: dict, user: dict) -> dict:
    email = (action.get("user_email") or "").strip().lower()
    if not email:
        return _err("user_email required")
    r = await users_collection.update_one({"email": email}, {"$set": {"disabled": True}})
    if r.matched_count == 0:
        return _err("User not found")
    return _ok(f"User '{email}' disabled")


async def _h_reset_user_password(action: dict, user: dict) -> dict:
    email = (action.get("user_email") or "").strip().lower()
    new_pw = action.get("new_password")
    if not email or not new_pw:
        return _err("user_email and new_password required")
    r = await users_collection.update_one(
        {"email": email},
        {"$set": {"password_hash": get_password_hash(new_pw)}},
    )
    if r.matched_count == 0:
        return _err("User not found")
    return _ok(f"Password reset for '{email}'")


async def _h_send_notification(action: dict, user: dict) -> dict:
    email = (action.get("user_email") or "").strip().lower()
    msg = action.get("message")
    if not email or not msg:
        return _err("user_email and message required")
    doc = {
        "user_email": email,
        "message": msg,
        "link": action.get("link"),
        "type": action.get("type", "info"),
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    r = await notifications_collection.insert_one(doc)
    return _ok(f"Notification sent to '{email}'", id=str(r.inserted_id))


async def _h_run_data_cleanup_scan(action: dict, user: dict) -> dict:
    """Lightweight summary — count orphans without modifying anything."""
    proj_ids = {str(p["_id"]) for p in await projects_collection.find({}, {"_id": 1}).to_list(length=10000)}
    res_ids = {str(r["_id"]) for r in await resources_collection.find({}, {"_id": 1}).to_list(length=10000)}
    orphan_allocs = await allocations_collection.count_documents({
        "$or": [{"project_id": {"$nin": list(proj_ids)}}, {"resource_id": {"$nin": list(res_ids)}}]
    })
    orphan_ts = await timesheets_collection.count_documents({
        "$or": [{"project_id": {"$nin": list(proj_ids)}}, {"resource_id": {"$nin": list(res_ids)}}]
    })
    orphan_risks = await risks_collection.count_documents({"project_id": {"$nin": list(proj_ids)}})
    return _ok(
        f"Cleanup scan complete — orphan allocations: {orphan_allocs}, orphan timesheets: {orphan_ts}, orphan risks: {orphan_risks}",
        orphan_allocations=orphan_allocs,
        orphan_timesheets=orphan_ts,
        orphan_risks=orphan_risks,
    )


async def _h_save_memory(action: dict, user: dict) -> dict:
    """Save a key decision, preference, or note to agent memory for future context injection."""
    from database import ai_memory_collection
    title = (action.get("title") or "").strip()
    content = (action.get("content") or "").strip()
    if not title or not content:
        return _err("title and content are required")
    scope = action.get("scope", "project")
    if scope == "project" and not action.get("project_id"):
        scope = "global"
    doc = {
        "scope": scope,
        "project_id": action.get("project_id") if scope == "project" else None,
        "title": title,
        "content": content,
        "category": action.get("category", "note"),
        "created_by": user.get("email"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "active": True,
    }
    r = await ai_memory_collection.insert_one(doc)
    return _ok(f"Memory saved: '{title}'", id=str(r.inserted_id))


async def _h_run_health_check(action: dict, user: dict) -> dict:
    """Trigger a full portfolio health analysis and return a summary."""
    try:
        from services.health_monitor import run_health_monitor
        report = await run_health_monitor(triggered_by=user.get("email", "ai"), save_report=True)
        findings = report.get("findings", [])
        summary = report.get("summary", {})
        overall = report.get("overall_health", "Unknown")
        msg = (
            f"Health check complete — {overall}. "
            f"{summary.get('critical', 0)} critical, {summary.get('high', 0)} high, "
            f"{summary.get('medium', 0)} medium findings across {report.get('projects_analyzed', 0)} projects."
        )
        return _ok(msg, findings=findings[:10], summary=summary, overall_health=overall)
    except Exception as e:
        return _err(f"Health check failed: {e}")


# ─────────────────────────────────────────────────────────────────────────
# Destructive legacy action wrappers (needed to gate with confirmation token)
# ─────────────────────────────────────────────────────────────────────────

async def _h_remove_allocation(action: dict, user: dict) -> dict:
    """Delete a resource allocation (destructive — requires confirmation)."""
    aid = action.get("allocation_id")
    if not aid or not ObjectId.is_valid(aid):
        return _err("Invalid allocation_id")
    alloc = await allocations_collection.find_one({"_id": ObjectId(aid)})
    if not alloc:
        return _err("Allocation not found")
    # Build a human-readable summary for the confirmation message
    from database import resources_collection as _res_col, projects_collection as _proj_col
    res = await _res_col.find_one({"_id": ObjectId(alloc["resource_id"])}) if ObjectId.is_valid(alloc.get("resource_id", "")) else None
    proj = await _proj_col.find_one({"_id": ObjectId(alloc["project_id"])}) if ObjectId.is_valid(alloc.get("project_id", "")) else None
    res_name = (res or {}).get("name", "?")
    proj_name = (proj or {}).get("name", "?")
    await allocations_collection.delete_one({"_id": ObjectId(aid)})
    return _ok(f"Allocation removed — {res_name} is no longer assigned to '{proj_name}'")


async def _h_delete_wbs_task(action: dict, user: dict) -> dict:
    """Delete a WBS task and all its direct children (destructive — requires confirmation)."""
    tid = action.get("task_id")
    if not tid or not ObjectId.is_valid(tid):
        return _err("Invalid task_id")
    task = await wbs_tasks_collection.find_one({"_id": ObjectId(tid)})
    if not task:
        return _err("Task not found")
    task_name = task.get("name", "?")
    task_internal_id = task.get("id") or str(task["_id"])
    # Delete task itself plus any children that reference it as parent
    await wbs_tasks_collection.delete_many({
        "$or": [
            {"_id": ObjectId(tid)},
            {"parent_id": str(tid)},          # children referencing mongo _id as string
            {"parent_id": task_internal_id},   # children referencing internal uuid id
        ]
    })
    return _ok(f"WBS task '{task_name}' deleted (including any child tasks)")


# ═════════════════════════════════════════════════════════════════════════
# REGISTRATION — register all handlers with the registry
# ═════════════════════════════════════════════════════════════════════════

# Tier 1
register("update_project",
         handler=_h_update_project,
         required_fields=["project_id"],
         category="project",
         description="Patch any subset of project fields (name, client_name, budgeted_hours, status, dates, lead, etc.)",
         example={"project_id": "<id>", "name": "New Name", "budgeted_hours": 600},
         audit_entity_type="project")

register("delete_project",
         handler=_h_delete_project,
         required_fields=["project_id"],
         is_destructive=True,
         category="project",
         description="Delete a project and ALL related data (allocations, timesheets, risks, WBS, baselines)",
         example={"project_id": "<id>"},
         audit_entity_type="project")

register("manage_phases",
         handler=_h_manage_phases,
         required_fields=["project_id", "phases"],
         category="project",
         description="Add, update, or remove phases on a project. Default mode='merge': only supplied phases are changed; other existing phases are kept. Pass mode='replace' to fully replace the array.",
         example={"project_id": "<id>", "phases": [{"name": "Discovery", "start_date": "2026-05-01", "end_date": "2026-05-15", "status": "Active", "budgeted_hours": 80}], "mode": "merge"},
         audit_entity_type="phase")

register("delete_risk",
         handler=_h_delete_risk,
         required_fields=["risk_id"],
         is_destructive=True,
         category="risk",
         description="Delete a risk/issue",
         example={"risk_id": "<id>"},
         audit_entity_type="risk")

register("create_resource",
         handler=_h_create_resource,
         required_fields=["name"],
         category="resource",
         description="Create a new team member",
         example={"name": "Jane Doe", "role": "Developer", "standard_capacity": 100},
         audit_entity_type="resource")

register("update_resource",
         handler=_h_update_resource,
         required_fields=["resource_id"],
         category="resource",
         description="Update a team member's name, role, capacity, or avatar",
         example={"resource_id": "<id>", "role": "Senior Developer"},
         audit_entity_type="resource")

register("delete_resource",
         handler=_h_delete_resource,
         required_fields=["resource_id"],
         is_destructive=True,
         category="resource",
         description="Hard-delete a team member — only allowed if they have NO allocations/timesheets; otherwise use deactivate_resource",
         example={"resource_id": "<id>"},
         audit_entity_type="resource")

register("deactivate_resource",
         handler=_h_deactivate_resource,
         required_fields=["resource_id"],
         is_destructive=True,
         category="resource",
         description="Deactivate a team member (e.g. they left the company): preserves history, ends future allocations today, disables their login",
         example={"resource_id": "<id>"},
         audit_entity_type="resource")

register("reactivate_resource",
         handler=_h_reactivate_resource,
         required_fields=["resource_id"],
         category="resource",
         description="Reactivate a previously deactivated team member and re-enable their login",
         example={"resource_id": "<id>"},
         audit_entity_type="resource")

register("sync_phase_to_wbs",
         handler=_h_sync_phase_to_wbs,
         required_fields=["project_id", "phase_id"],
         category="project",
         description="Update phase dates to MIN/MAX of its WBS task dates",
         example={"project_id": "<id>", "phase_id": "<phase_uuid>"},
         audit_entity_type="phase")

register("polish_all_risks",
         handler=_h_polish_all_risks,
         required_fields=["project_id"],
         category="risk",
         description="Run AI polish on every un-polished risk in this project",
         example={"project_id": "<id>"},
         audit_entity_type="risk")

register("reschedule_project",
         handler=_h_reschedule_project,
         required_fields=["project_id", "shift_days"],
         category="project",
         description="Shift project start, end, and all phase dates by N days (positive = later, negative = earlier)",
         example={"project_id": "<id>", "shift_days": 14},
         audit_entity_type="project")

register("remove_allocation",
         handler=_h_remove_allocation,
         required_fields=["allocation_id"],
         is_destructive=True,
         category="allocation",
         description="Remove a resource allocation from a project — requires confirmation token",
         example={"allocation_id": "<id>"},
         audit_entity_type="allocation")

register("delete_wbs_task",
         handler=_h_delete_wbs_task,
         required_fields=["task_id"],
         is_destructive=True,
         category="wbs",
         description="Delete a WBS task and all its child tasks — requires confirmation token",
         example={"task_id": "<id>"},
         audit_entity_type="wbs")

# Tier 2
register("create_timesheet",
         handler=_h_create_timesheet,
         required_fields=["resource_id", "project_id", "week_start_date"],
         category="timesheet",
         description="Create a single weekly timesheet entry",
         example={"resource_id": "<id>", "project_id": "<id>", "week_start_date": "2026-05-18", "planned_hours": 20, "actual_hours": 20},
         audit_entity_type="timesheet")

register("update_timesheet",
         handler=_h_update_timesheet,
         required_fields=["timesheet_id"],
         category="timesheet",
         description="Update planned/actual hours, notes, or status on a timesheet row",
         example={"timesheet_id": "<id>", "actual_hours": 25},
         audit_entity_type="timesheet")

register("delete_timesheet",
         handler=_h_delete_timesheet,
         required_fields=["timesheet_id"],
         is_destructive=True,
         category="timesheet",
         description="Delete a timesheet entry",
         example={"timesheet_id": "<id>"},
         audit_entity_type="timesheet")

register("submit_timesheet_week",
         handler=_h_submit_timesheet_week,
         required_fields=["resource_id", "week_start_date"],
         category="timesheet",
         description="Mark all of a resource's draft rows for one week as Submitted",
         example={"resource_id": "<id>", "week_start_date": "2026-05-18"},
         audit_entity_type="timesheet")

register("autofill_timesheets_week",
         handler=_h_autofill_timesheets_week,
         required_fields=["resource_id", "week_start_date"],
         category="timesheet",
         description="Auto-generate draft timesheet rows from a resource's allocations for one week",
         example={"resource_id": "<id>", "week_start_date": "2026-05-18"},
         audit_entity_type="timesheet")

register("create_leave",
         handler=_h_create_leave,
         required_fields=["resource_id", "start_date", "end_date"],
         category="leave",
         description="Record a leave / vacation entry",
         example={"resource_id": "<id>", "start_date": "2026-06-01", "end_date": "2026-06-05", "type": "Annual Leave", "notes": "optional"},
         audit_entity_type="leave")

register("delete_leave",
         handler=_h_delete_leave,
         required_fields=["leave_id"],
         is_destructive=True,
         category="leave",
         description="Delete a leave entry",
         example={"leave_id": "<id>"},
         audit_entity_type="leave")

register("create_holiday",
         handler=_h_create_holiday,
         required_fields=["date", "name"],
         category="holiday",
         description="Create a public holiday entry",
         example={"date": "2026-12-25", "name": "Christmas Day", "region": "AU"},
         audit_entity_type="holiday")

register("delete_holiday",
         handler=_h_delete_holiday,
         required_fields=["holiday_id"],
         is_destructive=True,
         category="holiday",
         description="Delete a public holiday",
         example={"holiday_id": "<id>"},
         audit_entity_type="holiday")

register("create_baseline",
         handler=_h_create_baseline,
         required_fields=["project_id", "name"],
         category="baseline",
         description="Snapshot the project's current state as a new baseline",
         example={"project_id": "<id>", "name": "Re-baseline Q4 2026", "set_current": True},
         audit_entity_type="baseline")

register("set_current_baseline",
         handler=_h_set_current_baseline,
         required_fields=["project_id", "baseline_id"],
         category="baseline",
         description="Mark a baseline as the current/comparison baseline",
         example={"project_id": "<id>", "baseline_id": "<id>"},
         audit_entity_type="baseline")

register("delete_baseline",
         handler=_h_delete_baseline,
         required_fields=["baseline_id"],
         is_destructive=True,
         category="baseline",
         description="Delete a baseline (cannot delete the current one)",
         example={"baseline_id": "<id>"},
         audit_entity_type="baseline")

register("move_resource_between_projects",
         handler=_h_move_resource_between_projects,
         required_fields=["resource_id", "from_project_id", "to_project_id", "start_date", "end_date"],
         category="resource",
         description="Move a resource from one project to another with a new allocation",
         example={"resource_id": "<id>", "from_project_id": "<id>", "to_project_id": "<id>", "percentage": 50, "start_date": "2026-06-01", "end_date": "2026-07-31"},
         audit_entity_type="resource")

# Tier 3 — super-admin only
register("create_user",
         handler=_h_create_user,
         required_fields=["email", "password"],
         permission="super_admin",
         category="user",
         description="Create a new login user (admin/super_admin/resource/contractor/client)",
         example={"email": "new@example.com", "password": "Secret123!", "role": "admin"},
         audit_entity_type="user")

register("update_user_role",
         handler=_h_update_user_role,
         required_fields=["user_email", "new_role"],
         permission="super_admin",
         category="user",
         description="Change a user's role",
         example={"user_email": "user@example.com", "new_role": "admin"},
         audit_entity_type="user")

register("disable_user",
         handler=_h_disable_user,
         required_fields=["user_email"],
         is_destructive=True,
         permission="super_admin",
         category="user",
         description="Disable a user (cannot log in)",
         example={"user_email": "user@example.com"},
         audit_entity_type="user")

register("reset_user_password",
         handler=_h_reset_user_password,
         required_fields=["user_email", "new_password"],
         permission="super_admin",
         category="user",
         description="Reset a user's password",
         example={"user_email": "user@example.com", "new_password": "NewSecret123!"},
         audit_entity_type="user")

register("send_notification",
         handler=_h_send_notification,
         required_fields=["user_email", "message"],
         category="system",
         description="Send an in-app notification to a user",
         example={"user_email": "user@example.com", "message": "Please review the Q4 plan", "link": "/projects/abc", "type": "info"},
         audit_entity_type="notification")

register("run_data_cleanup_scan",
         handler=_h_run_data_cleanup_scan,
         permission="super_admin",
         category="system",
         description="Scan the database for orphaned allocations/timesheets/risks. Reports counts only — no mutation.",
         example={},
         audit_entity_type="system")

register("save_memory",
         handler=_h_save_memory,
         required_fields=["title", "content"],
         category="system",
         description="Save a key decision, preference, or context note to agent memory so it's available in future sessions. scope='project' links it to a project; scope='global' makes it app-wide.",
         example={"title": "Phase budget split", "content": "Team agreed to 60/40 Discovery/Build split for all future projects.", "scope": "global", "category": "decision"},
         audit_entity_type="system")

register("run_health_check",
         handler=_h_run_health_check,
         category="system",
         description="Trigger a proactive portfolio health analysis: budget overruns, over-allocations, stale status updates, overdue milestones, unmitigated risks. Returns a structured findings report.",
         example={},
         audit_entity_type="system")
