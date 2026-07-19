"""
Baseline & Change-Log services.

This module provides:
  1.  Snapshot helpers — build a point-in-time picture of a project + its
      WBS tasks (used when creating a baseline).
  2.  Variance calculation — compares a stored baseline to the *current* state
      of the project and returns deltas for project dates, phases, and tasks.
  3.  Change logging — a single `log_change` coroutine that any mutation
      handler can call to append an entry to the `change_log` collection.

Design notes:
  • Baselines store a *deep copy* of the relevant fields, NOT a reference. This
    means deleting/renaming a phase or task does not corrupt historical
    baselines.
  • Only ONE baseline per project is marked is_current = True. Setting a new
    current baseline auto-flips the previous one.
  • Change-log entries are append-only; we never edit/delete them.
"""
from __future__ import annotations

import uuid as uuid_module
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId

from database import (
    projects_collection,
    wbs_tasks_collection,
    baselines_collection,
    change_log_collection,
)


# ────────────────────────────────────────────────────────────────────────────
# Common helpers
# ────────────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_str(v: Any) -> Optional[str]:
    """Normalise dates / ObjectIds to strings for JSON-safe storage."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, ObjectId):
        return str(v)
    return str(v) if not isinstance(v, (str, int, float, bool, list, dict)) else v


async def _find_project(project_id: str) -> Optional[dict]:
    """Look up a project by either its UUID `id` field OR its MongoDB ObjectId."""
    if ObjectId.is_valid(project_id):
        p = await projects_collection.find_one({"_id": ObjectId(project_id)})
        if p:
            return p
    return await projects_collection.find_one({"id": project_id})


def _norm_date(d: Any) -> Optional[str]:
    """Coerce a date-like value into a YYYY-MM-DD string (or None)."""
    if not d:
        return None
    if isinstance(d, datetime):
        return d.date().isoformat()
    s = str(d)
    return s[:10] if len(s) >= 10 else s


def _diff_days(a: Optional[str], b: Optional[str]) -> Optional[int]:
    """Days between two YYYY-MM-DD strings (a − b). Returns None if either missing."""
    if not a or not b:
        return None
    try:
        da = datetime.fromisoformat(a[:10]).date()
        db = datetime.fromisoformat(b[:10]).date()
        return (da - db).days
    except Exception:
        return None


# ────────────────────────────────────────────────────────────────────────────
# Snapshot construction
# ────────────────────────────────────────────────────────────────────────────

async def build_project_snapshot(project_id: str) -> Dict[str, Any]:
    """Capture the current state of a project + its WBS tasks into a plain dict
    suitable for storage as a baseline.

    Only the fields that matter for *variance* are captured (dates, budgets,
    estimates, dependencies, structure). Free-text fields like descriptions
    are NOT captured to keep snapshots compact.
    """
    project = await _find_project(project_id)
    if not project:
        raise ValueError(f"Project not found: {project_id}")

    # Project-level snapshot
    project_snap: Dict[str, Any] = {
        "start_date": _norm_date(project.get("start_date")),
        "end_date": _norm_date(project.get("end_date")),
        "budgeted_hours": project.get("budgeted_hours"),
        "phases": [],
    }
    for ph in (project.get("phases") or []):
        project_snap["phases"].append({
            "id": ph.get("id"),
            "name": ph.get("name"),
            "start_date": _norm_date(ph.get("start_date")),
            "end_date": _norm_date(ph.get("end_date")),
            "budgeted_hours": ph.get("budgeted_hours"),
            "status": ph.get("status"),
        })

    # WBS snapshot — store one entry per task with the few fields that matter
    pid_str = str(project.get("_id")) if project.get("_id") else project.get("id")
    # WBS tasks reference project_id either by Mongo _id-as-string OR by UUID `id`
    wbs_cursor = wbs_tasks_collection.find({"$or": [
        {"project_id": pid_str},
        {"project_id": project.get("id")} if project.get("id") else {"project_id": "__none__"},
    ]})
    wbs_snap: List[Dict[str, Any]] = []
    async for t in wbs_cursor:
        wbs_snap.append({
            "id": str(t.get("id") or t.get("_id")),
            "name": t.get("name"),
            "phase_id": t.get("phase_id"),
            "phase_name": t.get("phase_name"),
            "parent_id": t.get("parent_id"),
            "status": t.get("status"),
            "priority": t.get("priority"),
            "estimated_hours": t.get("estimated_hours"),
            "start_date": _norm_date(t.get("start_date")),
            "end_date": _norm_date(t.get("end_date")),
            "dependencies": list(t.get("dependencies") or []),
            "assigned_to": t.get("assigned_to"),
        })

    return {
        "project": project_snap,
        "wbs": wbs_snap,
        "task_count": len(wbs_snap),
        "phase_count": len(project_snap["phases"]),
    }


# ────────────────────────────────────────────────────────────────────────────
# Baseline CRUD
# ────────────────────────────────────────────────────────────────────────────

async def create_baseline(
    project_id: str,
    *,
    name: str,
    description: Optional[str] = None,
    created_by: str,
    set_current: bool = True,
) -> Dict[str, Any]:
    """Snapshot the current state of the project and persist as a new baseline.

    If set_current=True, the new baseline becomes the comparison baseline (the
    previous one is demoted to is_current=False).
    """
    snapshot = await build_project_snapshot(project_id)

    if set_current:
        # Demote any existing current baseline
        await baselines_collection.update_many(
            {"project_id": project_id, "is_current": True},
            {"$set": {"is_current": False}},
        )

    doc = {
        "id": str(uuid_module.uuid4()),
        "project_id": project_id,
        "name": name,
        "description": description,
        "is_current": bool(set_current),
        "created_at": _now_iso(),
        "created_by": created_by,
        "project_snapshot": snapshot["project"],
        "wbs_snapshot": snapshot["wbs"],
        "task_count": snapshot["task_count"],
        "phase_count": snapshot["phase_count"],
    }
    await baselines_collection.insert_one(doc)
    # Strip _id from response (we keep the UUID `id`)
    doc.pop("_id", None)
    return doc


async def list_baselines(project_id: str) -> List[Dict[str, Any]]:
    """List baselines for a project, newest first. Strips heavy snapshot blobs
    so the listing stays lightweight; callers fetch the full snapshot via
    get_baseline()."""
    cursor = baselines_collection.find({"project_id": project_id}).sort("created_at", -1)
    out: List[Dict[str, Any]] = []
    async for b in cursor:
        b.pop("_id", None)
        # Trim heavy fields from listing
        b_light = {**b}
        b_light.pop("wbs_snapshot", None)
        b_light.pop("project_snapshot", None)
        out.append(b_light)
    return out


async def get_baseline(baseline_id: str) -> Optional[Dict[str, Any]]:
    b = await baselines_collection.find_one({"id": baseline_id})
    if not b:
        return None
    b.pop("_id", None)
    return b


async def get_current_baseline(project_id: str) -> Optional[Dict[str, Any]]:
    b = await baselines_collection.find_one({"project_id": project_id, "is_current": True})
    if not b:
        return None
    b.pop("_id", None)
    return b


async def set_current_baseline(project_id: str, baseline_id: str) -> bool:
    """Mark a specific baseline as the current/comparison baseline for the
    project, demoting any other current baseline."""
    target = await baselines_collection.find_one({"id": baseline_id, "project_id": project_id})
    if not target:
        return False
    await baselines_collection.update_many(
        {"project_id": project_id, "is_current": True},
        {"$set": {"is_current": False}},
    )
    await baselines_collection.update_one(
        {"id": baseline_id},
        {"$set": {"is_current": True}},
    )
    return True


async def rename_baseline(
    baseline_id: str,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> bool:
    fields: Dict[str, Any] = {}
    if name is not None:
        fields["name"] = name
    if description is not None:
        fields["description"] = description
    if not fields:
        return False
    r = await baselines_collection.update_one({"id": baseline_id}, {"$set": fields})
    return r.matched_count > 0


async def delete_baseline(baseline_id: str) -> bool:
    """Delete a baseline. Refuses to delete a current baseline — caller must
    set another as current first."""
    b = await baselines_collection.find_one({"id": baseline_id})
    if not b:
        return False
    if b.get("is_current"):
        raise ValueError("Cannot delete the current baseline. Set another as current first.")
    r = await baselines_collection.delete_one({"id": baseline_id})
    return r.deleted_count > 0


# ────────────────────────────────────────────────────────────────────────────
# Variance calculation
# ────────────────────────────────────────────────────────────────────────────

async def compute_variance(project_id: str, baseline_id: Optional[str] = None) -> Dict[str, Any]:
    """Compare the current project state against a baseline. Returns:
      {
        baseline: { id, name, created_at, ... },
        project: { start_var, end_var, budget_var, ... },
        phases:  [ { id, name, start_var, end_var, status, present_in_baseline, present_now } ],
        tasks:   [ { id, name, start_var, end_var, hours_var, status, dep_changed, present_in_baseline, present_now } ],
        summary: { total_tasks_added, total_tasks_removed, schedule_slip_days, scope_delta_hours }
      }

    Variance convention: positive number = LATER / MORE than baseline. Negative
    = EARLIER / LESS than baseline.
    """
    if baseline_id:
        baseline = await get_baseline(baseline_id)
    else:
        baseline = await get_current_baseline(project_id)

    if not baseline:
        return {
            "baseline": None,
            "project": None,
            "phases": [],
            "tasks": [],
            "summary": {},
            "note": "No baseline configured for this project.",
        }

    current = await build_project_snapshot(project_id)
    base_p = baseline.get("project_snapshot", {}) or {}
    cur_p = current["project"]

    # ── Project-level variance ──
    proj_var = {
        "baseline_start": base_p.get("start_date"),
        "current_start": cur_p.get("start_date"),
        "start_var_days": _diff_days(cur_p.get("start_date"), base_p.get("start_date")),
        "baseline_end": base_p.get("end_date"),
        "current_end": cur_p.get("end_date"),
        "end_var_days": _diff_days(cur_p.get("end_date"), base_p.get("end_date")),
        "baseline_budget": base_p.get("budgeted_hours"),
        "current_budget": cur_p.get("budgeted_hours"),
        "budget_var_hours": (
            (cur_p.get("budgeted_hours") or 0) - (base_p.get("budgeted_hours") or 0)
            if cur_p.get("budgeted_hours") is not None or base_p.get("budgeted_hours") is not None
            else None
        ),
    }

    # ── Phase-level variance ──
    base_phases_by_id = {p["id"]: p for p in (base_p.get("phases") or []) if p.get("id")}
    cur_phases_by_id = {p["id"]: p for p in cur_p.get("phases", []) if p.get("id")}
    phase_ids = set(base_phases_by_id.keys()) | set(cur_phases_by_id.keys())
    phases_out: List[Dict[str, Any]] = []
    for pid in phase_ids:
        b = base_phases_by_id.get(pid)
        c = cur_phases_by_id.get(pid)
        phases_out.append({
            "id": pid,
            "name": (c or b).get("name") if (c or b) else None,
            "present_in_baseline": b is not None,
            "present_now": c is not None,
            "baseline_start": (b or {}).get("start_date"),
            "current_start": (c or {}).get("start_date"),
            "start_var_days": _diff_days((c or {}).get("start_date"), (b or {}).get("start_date")),
            "baseline_end": (b or {}).get("end_date"),
            "current_end": (c or {}).get("end_date"),
            "end_var_days": _diff_days((c or {}).get("end_date"), (b or {}).get("end_date")),
            "baseline_budget": (b or {}).get("budgeted_hours"),
            "current_budget": (c or {}).get("budgeted_hours"),
        })

    # ── Task-level variance ──
    base_tasks_by_id = {t["id"]: t for t in (baseline.get("wbs_snapshot") or []) if t.get("id")}
    cur_tasks_by_id = {t["id"]: t for t in current["wbs"] if t.get("id")}
    task_ids = set(base_tasks_by_id.keys()) | set(cur_tasks_by_id.keys())
    tasks_out: List[Dict[str, Any]] = []
    tasks_added = 0
    tasks_removed = 0
    for tid in task_ids:
        b = base_tasks_by_id.get(tid)
        c = cur_tasks_by_id.get(tid)
        if b is None:
            tasks_added += 1
        if c is None:
            tasks_removed += 1
        deps_changed = (
            b is not None and c is not None
            and sorted(b.get("dependencies") or []) != sorted(c.get("dependencies") or [])
        )
        tasks_out.append({
            "id": tid,
            "name": (c or b).get("name") if (c or b) else None,
            "phase_id": (c or b).get("phase_id") if (c or b) else None,
            "phase_name": (c or b).get("phase_name") if (c or b) else None,
            "present_in_baseline": b is not None,
            "present_now": c is not None,
            "baseline_start": (b or {}).get("start_date"),
            "current_start": (c or {}).get("start_date"),
            "start_var_days": _diff_days((c or {}).get("start_date"), (b or {}).get("start_date")),
            "baseline_end": (b or {}).get("end_date"),
            "current_end": (c or {}).get("end_date"),
            "end_var_days": _diff_days((c or {}).get("end_date"), (b or {}).get("end_date")),
            "baseline_hours": (b or {}).get("estimated_hours"),
            "current_hours": (c or {}).get("estimated_hours"),
            "hours_var": (
                ((c or {}).get("estimated_hours") or 0) - ((b or {}).get("estimated_hours") or 0)
                if b is not None or c is not None
                else None
            ),
            "deps_changed": deps_changed,
        })

    summary = {
        "baseline_phase_count": len(base_phases_by_id),
        "current_phase_count": len(cur_phases_by_id),
        "phases_added": len(set(cur_phases_by_id.keys()) - set(base_phases_by_id.keys())),
        "phases_removed": len(set(base_phases_by_id.keys()) - set(cur_phases_by_id.keys())),
        "baseline_task_count": baseline.get("task_count", len(base_tasks_by_id)),
        "current_task_count": len(cur_tasks_by_id),
        "tasks_added": tasks_added,
        "tasks_removed": tasks_removed,
        "schedule_slip_days": proj_var["end_var_days"],
        "scope_delta_hours": (
            sum(((t.get("hours_var") or 0)) for t in tasks_out)
        ),
    }

    # Slim baseline meta for response
    baseline_meta = {
        "id": baseline["id"],
        "name": baseline.get("name"),
        "description": baseline.get("description"),
        "created_at": baseline.get("created_at"),
        "created_by": baseline.get("created_by"),
        "is_current": baseline.get("is_current"),
    }
    return {
        "baseline": baseline_meta,
        "project": proj_var,
        "phases": phases_out,
        "tasks": tasks_out,
        "summary": summary,
    }


# ────────────────────────────────────────────────────────────────────────────
# Change-log
# ────────────────────────────────────────────────────────────────────────────

_BASELINED_PROJECT_FIELDS = {"start_date", "end_date", "budgeted_hours", "phases", "project_objective", "status"}
_BASELINED_WBS_FIELDS = {"name", "phase_id", "phase_name", "parent_id", "estimated_hours",
                         "start_date", "end_date", "dependencies", "status", "priority", "assigned_to"}


async def log_change(
    *,
    project_id: str,
    user_email: Optional[str],
    entity_type: str,         # "project" | "phase" | "wbs_task"
    entity_id: Optional[str],
    action: str,              # "create" | "update" | "delete"
    field: Optional[str] = None,
    old_value: Any = None,
    new_value: Any = None,
    reason: Optional[str] = None,
    baselined: bool = True,
) -> None:
    """Append an entry to the change_log collection. Safe to call from any
    mutation handler. Silently swallows DB errors so logging never blocks the
    primary operation."""
    try:
        await change_log_collection.insert_one({
            "id": str(uuid_module.uuid4()),
            "project_id": project_id,
            "timestamp": _now_iso(),
            "user_email": user_email,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "field": field,
            "old_value": _safe_serialise(old_value),
            "new_value": _safe_serialise(new_value),
            "reason": reason,
            "baselined": baselined,
        })
    except Exception as e:  # pragma: no cover
        import logging
        logging.getLogger(__name__).warning(f"Change log write failed: {e}")


def _safe_serialise(v: Any) -> Any:
    """Make a value JSON/BSON-safe."""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (datetime,)):
        return v.isoformat()
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, list):
        return [_safe_serialise(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _safe_serialise(val) for k, val in v.items()}
    return str(v)


async def diff_and_log_project_update(
    *,
    project_id: str,
    user_email: Optional[str],
    before: Dict[str, Any],
    after: Dict[str, Any],
    reason: Optional[str] = None,
) -> None:
    """Compare two project documents and write a change-log entry for each
    baselined field that changed. Phases are diffed structurally: add /
    remove / per-phase field change."""
    if not before or not after:
        return

    # Scalar baselined fields
    for f in (_BASELINED_PROJECT_FIELDS - {"phases"}):
        old, new = before.get(f), after.get(f)
        if _normalise_for_compare(old) != _normalise_for_compare(new):
            await log_change(
                project_id=project_id, user_email=user_email,
                entity_type="project", entity_id=project_id,
                action="update", field=f,
                old_value=old, new_value=new, reason=reason,
            )

    # Phases — diff by id
    old_phases = {p.get("id"): p for p in (before.get("phases") or []) if p.get("id")}
    new_phases = {p.get("id"): p for p in (after.get("phases") or []) if p.get("id")}

    for pid in set(new_phases.keys()) - set(old_phases.keys()):
        await log_change(
            project_id=project_id, user_email=user_email,
            entity_type="phase", entity_id=pid,
            action="create", new_value=new_phases[pid], reason=reason,
        )
    for pid in set(old_phases.keys()) - set(new_phases.keys()):
        await log_change(
            project_id=project_id, user_email=user_email,
            entity_type="phase", entity_id=pid,
            action="delete", old_value=old_phases[pid], reason=reason,
        )
    for pid in set(old_phases.keys()) & set(new_phases.keys()):
        op, np = old_phases[pid], new_phases[pid]
        for f in ("name", "start_date", "end_date", "status", "budgeted_hours"):
            if _normalise_for_compare(op.get(f)) != _normalise_for_compare(np.get(f)):
                await log_change(
                    project_id=project_id, user_email=user_email,
                    entity_type="phase", entity_id=pid,
                    action="update", field=f,
                    old_value=op.get(f), new_value=np.get(f), reason=reason,
                )


async def diff_and_log_wbs_update(
    *,
    project_id: str,
    user_email: Optional[str],
    task_id: str,
    before: Dict[str, Any],
    after: Dict[str, Any],
    reason: Optional[str] = None,
) -> None:
    if not before or not after:
        return
    for f in _BASELINED_WBS_FIELDS:
        old, new = before.get(f), after.get(f)
        if _normalise_for_compare(old) != _normalise_for_compare(new):
            await log_change(
                project_id=project_id, user_email=user_email,
                entity_type="wbs_task", entity_id=task_id,
                action="update", field=f,
                old_value=old, new_value=new, reason=reason,
            )


def _normalise_for_compare(v: Any) -> Any:
    """Normalise values for change-detection (so date(2026, 5, 18) equals
    '2026-05-18T00:00:00')."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, list):
        return [_normalise_for_compare(x) for x in v]
    s = str(v)
    # Coerce ISO date strings
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return s


async def list_change_log(
    project_id: str,
    *,
    limit: int = 200,
    entity_type: Optional[str] = None,
    since: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List recent change-log entries for a project (newest first)."""
    q: Dict[str, Any] = {"project_id": project_id}
    if entity_type:
        q["entity_type"] = entity_type
    if since:
        q["timestamp"] = {"$gte": since}
    cursor = change_log_collection.find(q).sort("timestamp", -1).limit(int(limit))
    out: List[Dict[str, Any]] = []
    async for c in cursor:
        c.pop("_id", None)
        out.append(c)
    return out


# ────────────────────────────────────────────────────────────────────────────
# Startup backfill
# ────────────────────────────────────────────────────────────────────────────

async def backfill_baselines(*, system_user_email: str = "system") -> int:
    """For every project that doesn't have ANY baseline yet, create one
    automatically named 'Baseline v1' marked as current. Idempotent."""
    n_created = 0
    cursor = projects_collection.find({})
    async for p in cursor:
        pid = p.get("id") or str(p.get("_id"))
        existing = await baselines_collection.count_documents({"project_id": pid})
        if existing > 0:
            continue
        try:
            await create_baseline(
                pid,
                name="Baseline v1",
                description="Auto-generated initial baseline (backfilled)",
                created_by=system_user_email,
                set_current=True,
            )
            n_created += 1
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Backfill baseline failed for {pid}: {e}")
    return n_created
