"""
Personal Monday Briefing (Phase 4)
==================================
Weekly personalised digest for a resource: allocations for the week ahead,
upcoming deadlines, capacity vs commitments, timesheet status, leaves, and
optional AI-generated tone.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone, date
from typing import Optional, List, Dict

from database import (
    projects_collection, allocations_collection, timesheets_collection,
    leaves_collection, wbs_tasks_collection,
)
from utils import find_user_resource

logger = logging.getLogger(__name__)


def _week_range(d: date):
    monday = d - timedelta(days=d.weekday())
    friday = monday + timedelta(days=4)
    return monday, friday


def _dt(x):
    if isinstance(x, datetime):
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    if isinstance(x, str):
        try:
            return datetime.fromisoformat(x.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


async def get_personal_briefing(current_user: dict) -> dict:
    resource = await find_user_resource(current_user)
    if not resource:
        return {"error": "No resource profile found for this user."}

    today = datetime.now(timezone.utc).date()
    monday, friday = _week_range(today)
    std_capacity = int(resource.get("standard_capacity", 100))
    weekly_hours_capacity = std_capacity / 100 * 40

    # 1. Allocations covering this week
    all_allocs = await allocations_collection.find(
        {"resource_id": str(resource["_id"])}
    ).to_list(length=200)

    this_week_pids = set()
    upcoming_pids = set()
    this_week_pct_total = 0
    this_week_alloc_details = []

    for a in all_allocs:
        s = _dt(a.get("start_date"))
        e = _dt(a.get("end_date"))
        if not (s and e):
            continue
        s_d = s.date()
        e_d = e.date()
        # Active this week (overlap Mon-Fri)
        if s_d <= friday and e_d >= monday:
            this_week_pids.add(str(a.get("project_id")))
            pct = a.get("percentage") or 0
            this_week_pct_total += pct
            this_week_alloc_details.append({
                "project_id": str(a.get("project_id")),
                "percentage": pct,
                "hours_this_week": round(pct / 100 * (std_capacity / 100) * 40, 1),
                "end_date": e_d.isoformat(),
                "ends_soon": (e_d - today).days <= 14,
            })
        # Starting in the next 30 days
        elif s_d > friday and (s_d - today).days <= 30:
            upcoming_pids.add(str(a.get("project_id")))

    # 2. Load project names
    all_pids = list(this_week_pids | upcoming_pids)
    projects_map = {}
    if all_pids:
        try:
            from bson import ObjectId
            projects = await projects_collection.find(
                {"_id": {"$in": [ObjectId(pid) for pid in all_pids if pid]}}
            ).to_list(length=200)
            projects_map = {str(p["_id"]): p for p in projects}
        except Exception:
            projects_map = {}

    this_week_projects = []
    for a in this_week_alloc_details:
        p = projects_map.get(a["project_id"])
        if not p:
            continue
        this_week_projects.append({
            **a,
            "project_name": p.get("name"),
            "client_name": p.get("client_name"),
        })

    upcoming_projects = [
        {
            "project_id": pid,
            "project_name": projects_map.get(pid, {}).get("name"),
            "client_name": projects_map.get(pid, {}).get("client_name"),
        }
        for pid in upcoming_pids
    ]

    # 3. Timesheet status for LAST week
    last_monday = monday - timedelta(days=7)
    last_week_ts = await timesheets_collection.find({
        "resource_id": str(resource["_id"]),
        "week_start_date": last_monday.isoformat(),
    }).to_list(length=50)
    last_week_hours = sum(float(t.get("actual_hours") or 0) for t in last_week_ts)
    last_week_status = "submitted" if any(t.get("submitted_at") for t in last_week_ts) else \
                       ("draft" if last_week_ts else "missing")

    # 4. Upcoming leaves in next 30 days
    leaves = await leaves_collection.find({
        "resource_id": str(resource["_id"]),
    }).to_list(length=100)
    upcoming_leaves = []
    for lv in leaves:
        s = _dt(lv.get("start_date"))
        if s and s.date() >= today and (s.date() - today).days <= 30:
            upcoming_leaves.append({
                "start_date": s.date().isoformat(),
                "end_date": (_dt(lv.get("end_date")) or s).date().isoformat(),
                "type": lv.get("type"),
                "notes": lv.get("notes"),
            })
    upcoming_leaves.sort(key=lambda x: x["start_date"])

    # 5. Deadlines: WBS tasks assigned to this resource ending in next 14 days
    resource_id = str(resource["_id"])
    upcoming_deadlines = []
    try:
        wbs = await wbs_tasks_collection.find({
            "assignee_ids": resource_id,
            "status": {"$nin": ["done", "completed"]},
        }).to_list(length=200)
        for t in wbs:
            end = _dt(t.get("end_date"))
            if end and monday <= end.date() <= (today + timedelta(days=14)):
                upcoming_deadlines.append({
                    "task_id": t.get("id"),
                    "name": t.get("name"),
                    "project_id": t.get("project_id"),
                    "project_name": (projects_map.get(t.get("project_id"), {}) or {}).get("name"),
                    "end_date": end.date().isoformat(),
                    "estimated_hours": t.get("estimated_hours"),
                    "days_until": (end.date() - today).days,
                })
    except Exception:
        pass
    upcoming_deadlines.sort(key=lambda x: x.get("end_date", ""))

    # 6. Load percentage
    over_capacity = this_week_pct_total > std_capacity
    over_hours = sum(a["hours_this_week"] for a in this_week_projects) - weekly_hours_capacity
    load_pct_of_capacity = round((this_week_pct_total / std_capacity * 100), 1) if std_capacity else 0

    # 7. Summary sentence
    if over_capacity:
        summary = (
            f"You're over capacity this week — allocated {this_week_pct_total}% "
            f"({sum(a['hours_this_week'] for a in this_week_projects):.0f}h) vs your "
            f"{std_capacity}% capacity ({weekly_hours_capacity:.0f}h). Consider rebalancing."
        )
    elif this_week_pct_total >= std_capacity * 0.9:
        summary = f"Busy week ahead — you're at {load_pct_of_capacity}% capacity across {len(this_week_projects)} project(s)."
    elif this_week_pct_total == 0:
        summary = "No active allocations this week — you have full capacity available."
    else:
        summary = f"Comfortable week — {load_pct_of_capacity}% of capacity used across {len(this_week_projects)} project(s)."

    if last_week_status == "missing":
        summary += " ⚠️ Last week's timesheet is missing — please submit."
    elif last_week_status == "draft":
        summary += f" ⏳ Last week's timesheet is still a draft ({last_week_hours:.0f}h)."

    return {
        "resource_id": str(resource["_id"]),
        "resource_name": resource.get("name"),
        "standard_capacity": std_capacity,
        "weekly_hours_capacity": weekly_hours_capacity,
        "week": {
            "start": monday.isoformat(),
            "end": friday.isoformat(),
        },
        "summary": summary,
        "capacity": {
            "allocated_pct": this_week_pct_total,
            "capacity_pct": std_capacity,
            "utilisation_pct_of_capacity": load_pct_of_capacity,
            "over_capacity": over_capacity,
            "extra_hours_needed": round(max(over_hours, 0), 1),
        },
        "this_week_projects": this_week_projects,
        "upcoming_projects": upcoming_projects,
        "upcoming_deadlines": upcoming_deadlines[:6],
        "upcoming_leaves": upcoming_leaves,
        "last_week": {
            "hours": round(last_week_hours, 1),
            "status": last_week_status,  # submitted | draft | missing
        },
    }
