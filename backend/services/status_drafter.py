"""
AI Status Update Drafter
========================
Given a project, gathers recent activity (last 1-2 weeks) and asks the LLM
to draft a weekly status update the user can edit and submit.

Signals used:
  • Recent timesheets (planned vs actual)
  • WBS tasks completed since last update
  • Milestones hit/missed
  • New / closed risks
  • Previous status update health (for continuity)
  • Blockers surfaced in comments (top few WBS comments)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId

from database import (
    projects_collection, timesheets_collection, wbs_tasks_collection,
    risks_collection, status_updates_collection, resources_collection,
    wbs_comments_collection,
)
from services.ai_providers import get_ai_config, call_openai_api, call_gemini_api, call_emergent_fallback
from services.ai_instructions import get_instructions_for_prompt

logger = logging.getLogger(__name__)


def _dt(x):
    if x is None:
        return None
    if isinstance(x, str):
        try:
            return datetime.fromisoformat(x.replace("Z", "+00:00"))
        except Exception:
            return None
    if isinstance(x, datetime):
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    return None


async def _snapshot(project_id: str) -> Optional[dict]:
    try:
        p = await projects_collection.find_one({"_id": ObjectId(project_id)})
    except Exception:
        return None
    if not p:
        return None

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=14)
    since_iso = since.date().isoformat()

    # Recent timesheets
    recent_ts = await timesheets_collection.find({
        "project_id": project_id,
        "week_start_date": {"$gte": since_iso},
    }).to_list(length=2000)
    planned_h = sum(float(t.get("planned_hours") or 0) for t in recent_ts)
    actual_h = sum(float(t.get("actual_hours") or 0) for t in recent_ts)

    # Contributor breakdown
    resources_map = {str(r["_id"]): r for r in await resources_collection.find().to_list(length=500)}
    by_res = {}
    for t in recent_ts:
        rid = str(t.get("resource_id", ""))
        by_res[rid] = by_res.get(rid, 0) + float(t.get("actual_hours") or 0)
    contributors = [
        {"name": (resources_map.get(rid, {}) or {}).get("name", "Unknown"), "hours": round(h, 1)}
        for rid, h in sorted(by_res.items(), key=lambda kv: -kv[1])[:8]
    ]

    # WBS completed / at-risk
    all_wbs = await wbs_tasks_collection.find({"project_id": project_id}).to_list(length=2000)
    completed_recent = [
        t for t in all_wbs
        if (t.get("status") or "").lower() in ("done", "completed")
        and _dt(t.get("updated_at")) and _dt(t["updated_at"]) >= since
    ]
    overdue_open = [
        t for t in all_wbs
        if (t.get("status") or "").lower() not in ("done", "completed")
        and _dt(t.get("end_date")) and _dt(t["end_date"]) < now
    ]
    milestones_hit = [t for t in completed_recent if t.get("is_milestone")]
    milestones_missed = [t for t in overdue_open if t.get("is_milestone")]

    # Risks
    all_risks = await risks_collection.find({"project_id": project_id}).to_list(length=500)
    new_risks = [r for r in all_risks if _dt(r.get("created_at")) and _dt(r["created_at"]) >= since]
    closed_risks = [
        r for r in all_risks
        if r.get("status") in ("Mitigated", "Closed")
        and _dt(r.get("updated_at")) and _dt(r["updated_at"]) >= since
    ]
    active_risks = [r for r in all_risks if r.get("status") == "Active"]

    # Previous status update
    prev = await status_updates_collection.find_one(
        {"project_id": project_id}, sort=[("created_at", -1)]
    )
    prev_summary = None
    if prev:
        prev_summary = {
            "health": prev.get("health"),
            "schedule_status": prev.get("schedule_status"),
            "actual_progress": prev.get("actual_progress"),
            "created_at": (prev.get("created_at").isoformat() if hasattr(prev.get("created_at"), "isoformat") else str(prev.get("created_at"))),
        }

    # WBS comments (potential blockers from team chatter)
    recent_wbs_ids = [t.get("id") for t in all_wbs if t.get("id")]
    top_comments = []
    if recent_wbs_ids:
        cmts = await wbs_comments_collection.find({
            "task_id": {"$in": recent_wbs_ids},
            "created_at": {"$gte": since.isoformat()},
        }).sort("created_at", -1).to_list(length=20)
        top_comments = [
            {"author": c.get("user_email", "?"), "text": (c.get("text") or "")[:200]}
            for c in cmts[:8]
        ]

    # Compute overall progress (leaf estimated done / total)
    leaf = [t for t in all_wbs if float(t.get("estimated_hours") or 0) > 0 and not t.get("is_milestone")]
    total_est = sum(float(t.get("estimated_hours") or 0) for t in leaf)
    done_est = sum(float(t.get("estimated_hours") or 0) for t in leaf
                   if (t.get("status") or "").lower() in ("done", "completed"))
    progress_pct = round((done_est / total_est * 100), 1) if total_est else None

    return {
        "project": {
            "name": p.get("name"),
            "client": p.get("client_name"),
            "status": p.get("status"),
            "start_date": str(p.get("start_date"))[:10] if p.get("start_date") else None,
            "end_date": str(p.get("end_date"))[:10] if p.get("end_date") else None,
        },
        "period": {"from": since.date().isoformat(), "to": now.date().isoformat()},
        "hours": {"planned": round(planned_h, 1), "actual": round(actual_h, 1)},
        "contributors": contributors,
        "wbs": {
            "completed_recent": [
                {"name": t.get("name"), "hours": t.get("estimated_hours")} for t in completed_recent[:12]
            ],
            "overdue_open_count": len(overdue_open),
            "overall_progress_pct": progress_pct,
        },
        "milestones": {
            "hit": [m.get("name") for m in milestones_hit],
            "missed": [{"name": m.get("name"), "end_date": str(m.get("end_date"))[:10]} for m in milestones_missed],
        },
        "risks": {
            "new": [{"desc": r.get("description"), "impact": r.get("impact")} for r in new_risks[:5]],
            "closed": [{"desc": r.get("description")} for r in closed_risks[:5]],
            "top_active": [
                {"desc": r.get("description"), "impact": r.get("impact"),
                 "mitigation": r.get("mitigation")}
                for r in active_risks[:5]
            ],
        },
        "previous_status_update": prev_summary,
        "recent_team_comments": top_comments,
    }


async def draft_status_update(project_id: str) -> dict:
    snap = await _snapshot(project_id)
    if not snap:
        return {"error": "Project not found"}

    system_prompt = """You are drafting a weekly project status update for a technical PM.
Write the update the way a competent lead would — factual, specific, and short.

Return valid JSON only with this exact structure:
{
  "health": "Green|Amber|Red",
  "schedule_status": "On Track|Delayed|Ahead of Schedule|At Risk",
  "actual_progress": <integer 0-100>,
  "accomplishments": "2-4 short sentences (or bullet lines) listing what was completed this period. Cite specifics like task names, hours, or milestones.",
  "blockers": "Blockers/risks. If none, say 'No new blockers.' Each blocker MUST be surfaced clearly since they auto-become issues in the risk register.",
  "next_steps": "2-3 short lines on the plan for the next period. Concrete tasks or decisions, not platitudes.",
  "confidence_notes": "One sentence: how confident is this draft? Note any data gaps you saw (e.g., 'No timesheet activity this week — may be inaccurate')."
}

Rules for health:
- Green: no blockers, schedule healthy, budget healthy
- Amber: minor blockers, mild schedule/budget concerns
- Red: overdue milestones, active blockers not moving, over budget, or health downgrade trend
- schedule_status MUST match health: if Delayed/At Risk, health cannot be Green"""

    system_prompt += await get_instructions_for_prompt(category="status_update")

    user_message = "Draft based on this snapshot:\n\n" + json.dumps(snap, indent=2, default=str)

    ai_config = await get_ai_config()
    ai_json = None
    try:
        if ai_config["provider"] == "openai" and ai_config["api_key"]:
            resp = await call_openai_api(ai_config["api_key"], system_prompt, user_message)
            if resp.status_code == 200:
                ai_json = json.loads(resp.json()["choices"][0]["message"]["content"])
        elif ai_config["provider"] == "gemini" and ai_config["api_key"]:
            resp = await call_gemini_api(ai_config["api_key"], system_prompt, user_message)
            if resp.status_code == 200:
                ai_json = json.loads(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
        if ai_json is None:
            ai_json = await call_emergent_fallback(system_prompt, user_message)
    except Exception as e:
        logger.exception(f"[Status Drafter] AI failed: {e}")
        return {"error": f"AI service failed: {e}"}

    if not ai_json:
        return {"error": "AI returned no content"}

    # Ensure required fields
    for k in ("health", "schedule_status", "accomplishments", "blockers", "next_steps"):
        ai_json.setdefault(k, "")
    ai_json.setdefault("actual_progress", snap["wbs"].get("overall_progress_pct") or 0)

    return {
        "draft": ai_json,
        "snapshot": {
            "period": snap["period"],
            "hours": snap["hours"],
            "milestones": snap["milestones"],
            "progress_pct": snap["wbs"].get("overall_progress_pct"),
        },
    }
