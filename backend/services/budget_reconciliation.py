"""
Budget Reconciliation Service
==============================
Enforces the PMBOK hierarchy:

    Project Budget (cap)
        └─ Sum(Phase Budgets) ≤ Project Budget
              └─ Sum(WBS Estimates) ≤ Phase Budget
              └─ Phase dates = MIN/MAX(WBS task dates)
        └─ Sum(Allocation Effort) ≤ Phase/Project Budget (soft)

Surfaces drift between four parallel numbers:
    1. **Budget**     = project.budgeted_hours (target, top-down)
    2. **Estimated**  = SUM(wbs_task.estimated_hours) (bottom-up)
    3. **Allocated**  = SUM(allocation.% × duration × 8h) (resource commitment)
    4. **Actual**     = SUM(timesheet.actual_hours) (logged effort)

All validations return WARNINGS (non-blocking). Callers may force-save with
`force=True` if the caller is admin/super_admin.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId

from database import (
    projects_collection,
    allocations_collection,
    timesheets_collection,
    wbs_tasks_collection,
)
from utils import count_business_days


# ────────────────────────────────────────────────────────────────────────────
# Date helpers
# ────────────────────────────────────────────────────────────────────────────

def _parse_date(d: Any) -> Optional[date]:
    if not d:
        return None
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        return d.date()
    try:
        return datetime.fromisoformat(str(d)[:10]).date()
    except Exception:
        return None


def _safe_float(v: Any) -> float:
    try:
        return float(v) if v is not None and v != "" else 0.0
    except Exception:
        return 0.0


def _diff_days(start: Any, end: Any) -> int:
    """Count business days (Mon-Fri) between start and end dates, inclusive."""
    s, e = _parse_date(start), _parse_date(end)
    if not s or not e:
        return 0
    return max(0, count_business_days(s, e))


# ────────────────────────────────────────────────────────────────────────────
# Budget hierarchy validation
# ────────────────────────────────────────────────────────────────────────────

class HierarchyWarning(Dict[str, Any]):
    """Just a typed alias for clarity — these are plain dicts."""


def validate_phase_budgets(project: dict, phases: List[dict]) -> List[Dict[str, Any]]:
    """Return warnings if SUM(phase budgets) > project budget.
    Returns [] if no project budget set (nothing to validate against)."""
    warnings: List[Dict[str, Any]] = []
    project_budget = _safe_float(project.get("budgeted_hours"))
    if project_budget <= 0:
        return warnings  # no cap configured

    phase_budgets = [_safe_float(p.get("budgeted_hours")) for p in (phases or [])]
    total = sum(phase_budgets)
    if total > project_budget:
        warnings.append({
            "code": "phase_budgets_exceed_project",
            "severity": "warning",
            "level": "project",
            "message": (
                f"Sum of phase budgets ({total:g}h) exceeds project budget "
                f"({project_budget:g}h) by {total - project_budget:g}h."
            ),
            "project_budget": project_budget,
            "sum_of_phase_budgets": total,
            "excess_hours": total - project_budget,
        })
    return warnings


async def validate_wbs_estimates_for_phase(
    project_id: str, phase: dict, *, all_tasks: Optional[List[dict]] = None
) -> List[Dict[str, Any]]:
    """Return warnings if SUM(task estimates in this phase) > phase budget."""
    warnings: List[Dict[str, Any]] = []
    phase_budget = _safe_float(phase.get("budgeted_hours"))
    if phase_budget <= 0:
        return warnings
    phase_id = phase.get("id")
    if not phase_id:
        return warnings

    if all_tasks is None:
        cursor = wbs_tasks_collection.find({"project_id": project_id, "phase_id": phase_id})
        all_tasks = await cursor.to_list(length=10000)

    # Only count LEAF tasks (no children) to avoid double-counting parent rollups
    # A task is a leaf if no other task has it as a parent_id
    parent_ids = {str(t.get("parent_id")) for t in all_tasks if t.get("parent_id")}
    leaf_total = sum(
        _safe_float(t.get("estimated_hours"))
        for t in all_tasks
        if t.get("phase_id") == phase_id and str(t.get("id") or t.get("_id")) not in parent_ids
    )

    if leaf_total > phase_budget:
        warnings.append({
            "code": "wbs_estimates_exceed_phase_budget",
            "severity": "warning",
            "level": "phase",
            "phase_id": phase_id,
            "phase_name": phase.get("name"),
            "message": (
                f"WBS task estimates in phase '{phase.get('name')}' total {leaf_total:g}h, "
                f"exceeding the phase budget of {phase_budget:g}h."
            ),
            "phase_budget": phase_budget,
            "sum_of_estimates": leaf_total,
            "excess_hours": leaf_total - phase_budget,
        })
    return warnings


async def validate_all_wbs_estimates(project_id: str, project: dict) -> List[Dict[str, Any]]:
    """Run WBS-vs-phase-budget validation for every phase in the project."""
    cursor = wbs_tasks_collection.find({"project_id": project_id})
    all_tasks = await cursor.to_list(length=10000)
    warnings: List[Dict[str, Any]] = []
    for phase in (project.get("phases") or []):
        warnings.extend(
            await validate_wbs_estimates_for_phase(project_id, phase, all_tasks=all_tasks)
        )
    return warnings


def _allocated_hours_for_range(allocations: List[dict], start: Optional[date] = None, end: Optional[date] = None) -> float:
    """Compute total allocated hours across allocations, optionally clipped to [start, end].
    Uses business days (Mon-Fri) × 8 hours/day for all calculations."""
    total = 0.0
    for a in allocations:
        a_start = _parse_date(a.get("start_date"))
        a_end = _parse_date(a.get("end_date"))
        pct = _safe_float(a.get("percentage"))
        if not a_start or not a_end or pct <= 0:
            continue
        clip_start = max(a_start, start) if start else a_start
        clip_end = min(a_end, end) if end else a_end
        if clip_start > clip_end:
            continue
        business_days = count_business_days(clip_start, clip_end)
        total += (pct / 100.0) * business_days * 8.0
    return total


async def validate_allocations(
    project_id: str, project: dict, *, allocations: Optional[List[dict]] = None
) -> List[Dict[str, Any]]:
    """Warn if total allocation effort exceeds project or phase budget."""
    warnings: List[Dict[str, Any]] = []
    if allocations is None:
        cursor = allocations_collection.find({"project_id": project_id})
        allocations = await cursor.to_list(length=10000)

    project_budget = _safe_float(project.get("budgeted_hours"))
    total_allocated = _allocated_hours_for_range(allocations)

    if project_budget > 0 and total_allocated > project_budget:
        warnings.append({
            "code": "allocations_exceed_project_budget",
            "severity": "warning",
            "level": "project",
            "message": (
                f"Total allocated effort ({total_allocated:g}h) exceeds project budget "
                f"({project_budget:g}h) by {total_allocated - project_budget:g}h."
            ),
            "project_budget": project_budget,
            "allocated_hours": total_allocated,
        })

    # Per-phase allocation check (allocations are clipped to phase date range)
    for phase in (project.get("phases") or []):
        phase_budget = _safe_float(phase.get("budgeted_hours"))
        if phase_budget <= 0:
            continue
        phase_start = _parse_date(phase.get("start_date"))
        phase_end = _parse_date(phase.get("end_date"))
        if not phase_start or not phase_end:
            continue
        phase_alloc = _allocated_hours_for_range(allocations, phase_start, phase_end)
        if phase_alloc > phase_budget:
            warnings.append({
                "code": "allocations_exceed_phase_budget",
                "severity": "warning",
                "level": "phase",
                "phase_id": phase.get("id"),
                "phase_name": phase.get("name"),
                "message": (
                    f"Allocation effort during phase '{phase.get('name')}' is {phase_alloc:g}h, "
                    f"exceeding the phase budget of {phase_budget:g}h."
                ),
                "phase_budget": phase_budget,
                "allocated_hours": phase_alloc,
            })
    return warnings


# ────────────────────────────────────────────────────────────────────────────
# Phase date derivation from WBS
# ────────────────────────────────────────────────────────────────────────────

async def derive_phase_dates_from_wbs(
    project_id: str, phase_id: str, *, all_tasks: Optional[List[dict]] = None
) -> Dict[str, Any]:
    """Compute the MIN(start_date) and MAX(end_date) across all WBS tasks in
    this phase. Returns {derived_start, derived_end, task_count} or empty dict
    if no tasks have dates."""
    if all_tasks is None:
        cursor = wbs_tasks_collection.find({"project_id": project_id, "phase_id": phase_id})
        all_tasks = await cursor.to_list(length=10000)

    starts = [_parse_date(t.get("start_date")) for t in all_tasks if t.get("phase_id") == phase_id]
    ends = [_parse_date(t.get("end_date")) for t in all_tasks if t.get("phase_id") == phase_id]
    starts = [s for s in starts if s]
    ends = [e for e in ends if e]
    if not starts or not ends:
        return {"derived_start": None, "derived_end": None, "task_count": 0}
    return {
        "derived_start": min(starts).isoformat(),
        "derived_end": max(ends).isoformat(),
        "task_count": len(starts),
    }


# ────────────────────────────────────────────────────────────────────────────
# Reconciliation summary (the 4-number widget data)
# ────────────────────────────────────────────────────────────────────────────

async def reconciliation_summary(project_id: str) -> Dict[str, Any]:
    """Compute the four parallel numbers for the project + per-phase breakdown."""
    if ObjectId.is_valid(project_id):
        project = await projects_collection.find_one({"_id": ObjectId(project_id)})
    else:
        project = await projects_collection.find_one({"id": project_id})
    if not project:
        return {"error": "Project not found"}

    # Use the canonical project_id for downstream lookups (string of _id)
    canonical_pid = str(project.get("_id")) if project.get("_id") else project_id

    # 1. BUDGET (top-down)
    project_budget = _safe_float(project.get("budgeted_hours"))
    phases = project.get("phases") or []
    phase_budgets_sum = sum(_safe_float(p.get("budgeted_hours")) for p in phases)

    # 2. ESTIMATED (bottom-up from WBS)
    wbs_cursor = wbs_tasks_collection.find({"project_id": canonical_pid})
    all_tasks = await wbs_cursor.to_list(length=10000)
    parent_ids = {str(t.get("parent_id")) for t in all_tasks if t.get("parent_id")}
    leaf_estimated_total = sum(
        _safe_float(t.get("estimated_hours"))
        for t in all_tasks
        if str(t.get("id") or t.get("_id")) not in parent_ids
    )

    # 3. ALLOCATED (resource commitment)
    alloc_cursor = allocations_collection.find({"project_id": canonical_pid})
    allocations = await alloc_cursor.to_list(length=10000)
    allocated_total = _allocated_hours_for_range(allocations)

    # 4. ACTUAL (logged)
    ts_cursor = timesheets_collection.find({"project_id": canonical_pid})
    timesheets = await ts_cursor.to_list(length=10000)
    actual_total = sum(_safe_float(t.get("actual_hours")) for t in timesheets)

    # Variance percentages (against budget if set, otherwise against estimated)
    reference = project_budget if project_budget > 0 else leaf_estimated_total

    def pct_of(val: float) -> Optional[float]:
        if reference <= 0:
            return None
        return round((val / reference) * 100, 1)

    # Per-phase breakdown
    phases_summary: List[Dict[str, Any]] = []
    for phase in phases:
        phase_id = phase.get("id")
        phase_budget = _safe_float(phase.get("budgeted_hours"))

        # Estimated (leaf tasks in this phase)
        phase_estimated = sum(
            _safe_float(t.get("estimated_hours"))
            for t in all_tasks
            if t.get("phase_id") == phase_id and str(t.get("id") or t.get("_id")) not in parent_ids
        )

        # Allocated (clipped to phase dates)
        phase_start = _parse_date(phase.get("start_date"))
        phase_end = _parse_date(phase.get("end_date"))
        phase_allocated = (
            _allocated_hours_for_range(allocations, phase_start, phase_end)
            if phase_start and phase_end else None
        )

        # Actual (timesheets tagged with this phase)
        phase_actual = sum(
            _safe_float(t.get("actual_hours"))
            for t in timesheets
            if t.get("phase_id") == phase_id
        )

        # Derived dates from WBS
        derived = await derive_phase_dates_from_wbs(canonical_pid, phase_id, all_tasks=all_tasks)

        # Date drift indicator
        derived_start = derived.get("derived_start")
        derived_end = derived.get("derived_end")
        date_drift = None
        if derived_start and derived_end and phase.get("start_date") and phase.get("end_date"):
            ps = _parse_date(phase.get("start_date"))
            pe = _parse_date(phase.get("end_date"))
            ds = _parse_date(derived_start)
            de = _parse_date(derived_end)
            if ps and pe and ds and de:
                start_drift = (ds - ps).days
                end_drift = (de - pe).days
                if start_drift or end_drift:
                    date_drift = {"start_drift_days": start_drift, "end_drift_days": end_drift}

        phases_summary.append({
            "id": phase_id,
            "name": phase.get("name"),
            "status": phase.get("status"),
            "budget": phase_budget,
            "estimated": round(phase_estimated, 2),
            "allocated": round(phase_allocated, 2) if phase_allocated is not None else None,
            "actual": round(phase_actual, 2),
            "manual_start": _parse_date(phase.get("start_date")).isoformat() if _parse_date(phase.get("start_date")) else None,
            "manual_end": _parse_date(phase.get("end_date")).isoformat() if _parse_date(phase.get("end_date")) else None,
            "derived_start": derived_start,
            "derived_end": derived_end,
            "date_drift": date_drift,
            "task_count": derived.get("task_count", 0),
        })

    # Gather all warnings
    warnings: List[Dict[str, Any]] = []
    warnings.extend(validate_phase_budgets(project, phases))
    warnings.extend(await validate_all_wbs_estimates(canonical_pid, project))
    warnings.extend(await validate_allocations(canonical_pid, project, allocations=allocations))

    return {
        "project_id": canonical_pid,
        "totals": {
            "budget": project_budget,
            "phase_budgets_sum": round(phase_budgets_sum, 2),
            "estimated": round(leaf_estimated_total, 2),
            "allocated": round(allocated_total, 2),
            "actual": round(actual_total, 2),
            # Drift vs budget (or vs estimated when no budget)
            "reference_label": "budget" if project_budget > 0 else "estimated",
            "estimated_pct": pct_of(leaf_estimated_total),
            "allocated_pct": pct_of(allocated_total),
            "actual_pct": pct_of(actual_total),
            # Quick drift labels
            "estimated_vs_budget": round(leaf_estimated_total - project_budget, 2) if project_budget > 0 else None,
            "allocated_vs_budget": round(allocated_total - project_budget, 2) if project_budget > 0 else None,
            "actual_vs_budget": round(actual_total - project_budget, 2) if project_budget > 0 else None,
        },
        "phases": phases_summary,
        "warnings": warnings,
        "warning_count": len(warnings),
    }


# ────────────────────────────────────────────────────────────────────────────
# Validation entry point used by mutation routes
# ────────────────────────────────────────────────────────────────────────────

async def gather_save_warnings(
    project_id: str,
    *,
    project: Optional[dict] = None,
    proposed_phases: Optional[List[dict]] = None,
) -> List[Dict[str, Any]]:
    """Convenience: run all hierarchy validations and return the combined list.
    `proposed_phases` lets callers preview validation BEFORE persisting."""
    if project is None:
        if ObjectId.is_valid(project_id):
            project = await projects_collection.find_one({"_id": ObjectId(project_id)})
        else:
            project = await projects_collection.find_one({"id": project_id})
    if not project:
        return []
    phases = proposed_phases if proposed_phases is not None else (project.get("phases") or [])

    canonical_pid = str(project.get("_id")) if project.get("_id") else project_id
    warnings: List[Dict[str, Any]] = []
    warnings.extend(validate_phase_budgets(project, phases))
    project_with_proposed = {**project, "phases": phases}
    warnings.extend(await validate_all_wbs_estimates(canonical_pid, project_with_proposed))
    warnings.extend(await validate_allocations(canonical_pid, project_with_proposed))
    return warnings
