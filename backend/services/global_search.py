"""
Global Semantic Search
======================
Cross-collection keyword search with AI-friendly ranking. Searches over:
  • Projects (name, client, description)
  • Resources (name, role)
  • WBS tasks (name, description)
  • Risks (description, mitigation)
  • Status updates (accomplishments, blockers, next_steps)
  • WBS comments

Results are scored + returned with type, title, subtitle, and href for
frontend navigation.
"""
from __future__ import annotations

import logging
import re
from typing import List, Dict, Optional
from bson import ObjectId

from database import (
    projects_collection, resources_collection, wbs_tasks_collection,
    risks_collection, status_updates_collection, wbs_comments_collection,
    allocations_collection,
)

logger = logging.getLogger(__name__)

_STOP = {"the", "a", "an", "and", "or", "for", "of", "on", "in", "to", "with"}


def _tok(text: str) -> set:
    if not text:
        return set()
    return {w for w in re.findall(r"[a-z0-9]+", text.lower())
            if w not in _STOP and len(w) > 1}


def _score(query_tokens: set, *texts) -> int:
    """Sum token hits across fields (name-like fields could be weighted upstream)."""
    score = 0
    for t in texts:
        if not t:
            continue
        tokens = _tok(t)
        score += len(query_tokens & tokens)
    return score


async def _project_scope_for_user(current_user: dict) -> Optional[set]:
    """Return the set of project_ids the user is allowed to see, or None (=all)."""
    role = (current_user.get("role") or "").lower()
    if role in ("admin", "super_admin"):
        return None
    if role == "client":
        return set(current_user.get("allowed_project_ids") or [])
    # Resource/contractor — union of allocated + led projects
    from utils import find_user_resource
    res = await find_user_resource(current_user)
    if not res:
        return set()
    allocs = await allocations_collection.find({"resource_id": str(res["_id"])}).to_list(length=500)
    pids = {str(a.get("project_id")) for a in allocs if a.get("project_id")}
    # Led projects
    led = await projects_collection.find({"project_lead_id": str(res["_id"])}).to_list(length=100)
    pids.update(str(p["_id"]) for p in led)
    return pids


async def global_search(query: str, current_user: dict, limit_per_type: int = 5) -> dict:
    """Search across DD Planner and return grouped results."""
    q = (query or "").strip()
    if not q:
        return {"query": "", "results": {}, "total": 0}

    tokens = _tok(q)
    if not tokens:
        return {"query": q, "results": {}, "total": 0}

    scope = await _project_scope_for_user(current_user)
    role = (current_user.get("role") or "").lower()
    is_admin = role in ("admin", "super_admin")

    # ── Projects ────────────────────────────────────────────────────────
    proj_filter = {}
    if scope is not None:
        try:
            proj_filter = {"_id": {"$in": [ObjectId(pid) for pid in scope]}}
        except Exception:
            proj_filter = {"_id": {"$in": []}}
    projects = await projects_collection.find(proj_filter).to_list(length=500)
    proj_scored = []
    for p in projects:
        s = _score(tokens, p.get("name"), p.get("client_name"), p.get("description"))
        if s > 0:
            proj_scored.append({
                "type": "project",
                "id": str(p["_id"]),
                "title": p.get("name"),
                "subtitle": p.get("client_name"),
                "href": f"/projects/{str(p['_id'])}",
                "score": s,
            })

    # ── Resources (admin-only for now) ──────────────────────────────────
    res_scored = []
    if is_admin:
        resources = await resources_collection.find({"active": {"$ne": False}}).to_list(length=500)
        for r in resources:
            s = _score(tokens, r.get("name"), r.get("role"))
            if s > 0:
                res_scored.append({
                    "type": "resource",
                    "id": str(r["_id"]),
                    "title": r.get("name"),
                    "subtitle": r.get("role"),
                    "href": "/resources",
                    "score": s,
                })

    # ── WBS tasks (scoped) ──────────────────────────────────────────────
    wbs_filter = {}
    if scope is not None:
        wbs_filter = {"project_id": {"$in": list(scope)}}
    wbs = await wbs_tasks_collection.find(wbs_filter).to_list(length=2000)
    project_names = {str(p["_id"]): p.get("name") for p in projects}
    if scope is None:  # admin — need all projects for names
        all_projs = await projects_collection.find({}, {"name": 1}).to_list(length=1000)
        project_names.update({str(p["_id"]): p.get("name") for p in all_projs})
    wbs_scored = []
    for t in wbs:
        s = _score(tokens, t.get("name"), t.get("description"))
        if s > 0:
            pid = str(t.get("project_id", ""))
            wbs_scored.append({
                "type": "task",
                "id": t.get("id") or "",
                "title": t.get("name"),
                "subtitle": f"WBS · {project_names.get(pid, '?')}",
                "href": f"/projects/{pid}?tab=wbs",
                "score": s,
            })

    # ── Risks (scoped) ──────────────────────────────────────────────────
    risk_filter = {}
    if scope is not None:
        risk_filter = {"project_id": {"$in": list(scope)}}
    risks = await risks_collection.find(risk_filter).to_list(length=1000)
    risk_scored = []
    for r in risks:
        s = _score(tokens, r.get("description"), r.get("mitigation"))
        if s > 0:
            pid = str(r.get("project_id", ""))
            risk_scored.append({
                "type": "risk",
                "id": str(r["_id"]),
                "title": (r.get("description") or "")[:80],
                "subtitle": f"{r.get('impact', '?')} · {project_names.get(pid, '?')}",
                "href": f"/projects/{pid}?tab=risks",
                "score": s,
            })

    # ── Status updates (scoped) ────────────────────────────────────────
    su_filter = {}
    if scope is not None:
        su_filter = {"project_id": {"$in": list(scope)}}
    sus = await status_updates_collection.find(su_filter).sort("created_at", -1).limit(500).to_list(length=500)
    su_scored = []
    for su in sus:
        s = _score(tokens, su.get("accomplishments"), su.get("blockers"), su.get("next_steps"))
        if s > 0:
            pid = str(su.get("project_id", ""))
            date_str = ""
            if hasattr(su.get("created_at"), "isoformat"):
                date_str = su["created_at"].isoformat()[:10]
            su_scored.append({
                "type": "status_update",
                "id": str(su["_id"]),
                "title": (su.get("accomplishments") or su.get("blockers") or "Status update")[:80],
                "subtitle": f"{project_names.get(pid, '?')} · {date_str}",
                "href": f"/projects/{pid}?tab=status",
                "score": s,
            })

    # ── Sort by score, cap ─────────────────────────────────────────────
    def _top(items):
        return sorted(items, key=lambda x: -x["score"])[:limit_per_type]

    results = {
        "projects": _top(proj_scored),
        "resources": _top(res_scored),
        "tasks": _top(wbs_scored),
        "risks": _top(risk_scored),
        "status_updates": _top(su_scored),
    }
    total = sum(len(v) for v in results.values())
    return {"query": q, "results": results, "total": total}
