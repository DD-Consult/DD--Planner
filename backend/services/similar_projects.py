"""
Similar Projects Finder
=======================
Given a project, find historic projects that are similar based on:
  • Name/description word overlap
  • Same/similar client
  • Similar budget (±40%)
  • Similar duration (±40%)
  • Shared team roles

Returns top-N similar projects with an explanation of why they were picked.
Also provides a suggested WBS template that could be reused.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict

from bson import ObjectId

from database import (
    projects_collection, wbs_tasks_collection, allocations_collection,
    resources_collection,
)

logger = logging.getLogger(__name__)

_STOP = {"the", "a", "an", "and", "or", "for", "of", "on", "in", "to", "with",
         "project", "app", "system"}


def _tok(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if w not in _STOP and len(w) > 2}


def _duration_days(p: dict) -> Optional[int]:
    s = p.get("start_date")
    e = p.get("end_date")
    if isinstance(s, datetime) and isinstance(e, datetime):
        return (e - s).days
    return None


async def find_similar_projects(project_id: str, limit: int = 5) -> dict:
    try:
        target = await projects_collection.find_one({"_id": ObjectId(project_id)})
    except Exception:
        return {"error": "Invalid project id"}
    if not target:
        return {"error": "Project not found"}

    all_projects = await projects_collection.find({
        "_id": {"$ne": target["_id"]},
        "status": {"$in": ["Active", "Completed", "On Hold"]},
    }).to_list(length=500)

    target_tokens = _tok(target.get("name", "") + " " + (target.get("description") or ""))
    target_client = (target.get("client_name") or "").lower().strip()
    target_budget = float(target.get("budgeted_hours") or 0)
    target_dur = _duration_days(target) or 0

    # Team roles on target project
    allocs = await allocations_collection.find({}).to_list(length=5000)
    resources_map = {str(r["_id"]): r for r in await resources_collection.find().to_list(length=500)}
    target_roles = set()
    for a in allocs:
        if str(a.get("project_id")) == str(target["_id"]):
            r = resources_map.get(str(a.get("resource_id")))
            if r and r.get("role"):
                target_roles.add(r["role"].lower())

    scored = []
    for p in all_projects:
        reasons: List[str] = []
        score = 0.0

        # Name/description overlap
        cand_tokens = _tok(p.get("name", "") + " " + (p.get("description") or ""))
        overlap = target_tokens & cand_tokens
        if overlap:
            score += len(overlap) * 3
            reasons.append(f"Shared keywords: {', '.join(list(overlap)[:4])}")

        # Same client
        cand_client = (p.get("client_name") or "").lower().strip()
        if target_client and cand_client and target_client == cand_client:
            score += 8
            reasons.append(f"Same client ({p.get('client_name')})")

        # Similar budget
        cand_budget = float(p.get("budgeted_hours") or 0)
        if target_budget and cand_budget:
            ratio = min(target_budget, cand_budget) / max(target_budget, cand_budget)
            if ratio >= 0.6:
                score += 4 * ratio
                reasons.append(f"Similar budget ({cand_budget:.0f}h vs {target_budget:.0f}h)")

        # Similar duration
        cand_dur = _duration_days(p) or 0
        if target_dur and cand_dur:
            ratio = min(target_dur, cand_dur) / max(target_dur, cand_dur)
            if ratio >= 0.6:
                score += 3 * ratio
                reasons.append(f"Similar duration ({cand_dur}d vs {target_dur}d)")

        # Shared roles
        cand_roles = set()
        for a in allocs:
            if str(a.get("project_id")) == str(p["_id"]):
                r = resources_map.get(str(a.get("resource_id")))
                if r and r.get("role"):
                    cand_roles.add(r["role"].lower())
        role_overlap = target_roles & cand_roles
        if role_overlap:
            score += len(role_overlap) * 1.5
            reasons.append(f"Shared team roles: {', '.join(sorted(role_overlap)[:3])}")

        if score >= 3:  # min bar
            scored.append({
                "project_id": str(p["_id"]),
                "project_name": p.get("name"),
                "client": p.get("client_name"),
                "status": p.get("status"),
                "budgeted_hours": p.get("budgeted_hours"),
                "duration_days": cand_dur,
                "phases": [
                    (ph.get("name") if isinstance(ph, dict) else str(ph))
                    for ph in (p.get("phases") or [])
                ],
                "score": round(score, 2),
                "reasons": reasons,
            })

    scored.sort(key=lambda s: -s["score"])
    top = scored[:limit]

    # WBS template from the top candidate
    template = None
    if top:
        top_pid = top[0]["project_id"]
        tasks = await wbs_tasks_collection.find({"project_id": top_pid}).to_list(length=500)
        # Group by phase name
        by_phase: Dict[str, List[dict]] = {}
        # Map phase id → name via source project's phases
        try:
            source_p = await projects_collection.find_one({"_id": ObjectId(top_pid)})
            phase_name_by_id = {
                (ph.get("id") if isinstance(ph, dict) else ""):
                (ph.get("name") if isinstance(ph, dict) else str(ph))
                for ph in (source_p.get("phases") or []) if isinstance(ph, dict)
            }
        except Exception:
            phase_name_by_id = {}
        for t in tasks:
            if t.get("is_milestone"):
                continue
            phase_name = phase_name_by_id.get(t.get("phase_id"), "General")
            by_phase.setdefault(phase_name, []).append({
                "name": t.get("name"),
                "estimated_hours": t.get("estimated_hours"),
                "description": t.get("description"),
            })
        template = {
            "source_project_id": top_pid,
            "source_project_name": top[0]["project_name"],
            "phases": [
                {"phase": ph, "tasks": tasks_in_phase[:20]}
                for ph, tasks_in_phase in by_phase.items()
            ],
        }

    return {
        "target_project_id": str(target["_id"]),
        "target_project_name": target.get("name"),
        "similar_projects": top,
        "wbs_template_suggestion": template,
    }
