"""
AI Kickoff Wizard
=================
Given a project name + goal + target end date (+ optional client/budget),
propose:
  • Recommended phases with durations
  • Initial WBS structure (per-phase tasks with estimates)
  • Team roles required
  • Rough budget breakdown

Uses historical DD Planner projects to inform suggestions where possible.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from database import (
    projects_collection, wbs_tasks_collection, allocations_collection,
    resources_collection,
)
from services.ai_providers import get_ai_config, call_openai_api, call_gemini_api, call_emergent_fallback
from services.ai_instructions import get_instructions_for_prompt

logger = logging.getLogger(__name__)


async def _historical_summary() -> dict:
    """Compact summary of past projects to inform kickoff suggestions."""
    projects = await projects_collection.find(
        {"status": {"$in": ["Active", "Completed"]}},
    ).sort("start_date", -1).to_list(length=30)

    proj_ids = [str(p["_id"]) for p in projects]
    wbs = await wbs_tasks_collection.find({"project_id": {"$in": proj_ids}}).to_list(length=5000)
    allocs = await allocations_collection.find({"project_id": {"$in": proj_ids}}).to_list(length=5000)
    resources_map = {str(r["_id"]): r for r in await resources_collection.find().to_list(length=500)}

    by_project = {}
    for t in wbs:
        pid = str(t.get("project_id", ""))
        by_project.setdefault(pid, []).append(t)

    alloc_by_project = {}
    for a in allocs:
        pid = str(a.get("project_id", ""))
        alloc_by_project.setdefault(pid, []).append(a)

    summaries = []
    for p in projects[:20]:
        pid = str(p["_id"])
        phases = p.get("phases") or []
        phase_names = [
            (ph.get("name") if isinstance(ph, dict) else str(ph)) for ph in phases
        ]
        # Team roles used
        roles = set()
        for a in alloc_by_project.get(pid, []):
            r = resources_map.get(str(a.get("resource_id")))
            if r and r.get("role"):
                roles.add(r["role"])
        summaries.append({
            "name": p.get("name"),
            "client": p.get("client_name"),
            "budget_hours": p.get("budgeted_hours"),
            "duration_days": (
                ((p.get("end_date") - p.get("start_date")).days)
                if hasattr(p.get("end_date"), "days") or (p.get("end_date") and p.get("start_date"))
                else None
            ) if isinstance(p.get("end_date"), datetime) and isinstance(p.get("start_date"), datetime) else None,
            "phases": phase_names,
            "wbs_task_count": len(by_project.get(pid, [])),
            "team_roles": sorted(roles),
        })
    return {"projects": summaries}


async def suggest_kickoff(payload: dict) -> dict:
    """Payload keys: name, goal, client (opt), target_end_date (opt YYYY-MM-DD),
    budget_hours (opt), start_date (opt), complexity (simple|standard|detailed)."""
    name = payload.get("name") or "New Project"
    goal = payload.get("goal") or ""
    client = payload.get("client") or ""
    target_end = payload.get("target_end_date") or ""
    start_date = payload.get("start_date") or datetime.now(timezone.utc).date().isoformat()
    budget = payload.get("budget_hours")
    complexity = payload.get("complexity") or "standard"

    historical = await _historical_summary()

    system_prompt = """You are a program manager helping a team kick off a new project. Return
practical, opinionated suggestions grounded in the historical projects provided.

Return valid JSON only with this exact structure:
{
  "phases": [
    {"name": "Discovery", "duration_weeks": 2, "description": "brief"},
    ...
  ],
  "wbs": [
    {"phase": "Discovery", "tasks": [
      {"name": "Task", "estimated_hours": 16, "description": "brief"},
      ...
    ]},
    ...
  ],
  "team_roles": [
    {"role": "Project Manager", "allocation_pct": 25, "why": "brief"},
    ...
  ],
  "budget_breakdown": {
    "total_estimated_hours": <number>,
    "by_phase": [{"phase": "Discovery", "hours": 40}, ...]
  },
  "risks_to_watch": ["risk 1", "risk 2", ...],
  "kickoff_checklist": ["item 1", "item 2", ...],
  "notes": "1-2 sentences summarising the shape of the project and any similar past projects you drew on."
}

Rules:
- Phase count depends on complexity: simple=2-3, standard=3-4, detailed=4-6
- Total WBS estimated hours should roughly match user's budget if provided (±20%)
- If similar past project exists, mention its name in "notes" and mirror its phase structure
- Team roles must be practical (Project Manager, Developer, Designer, QA, etc.)
- All durations use business weeks
- kickoff_checklist should have 4-6 concrete items (e.g., "Confirm scope with client", "Schedule kickoff call")"""

    system_prompt += await get_instructions_for_prompt(category="kickoff")

    user_context = {
        "project_request": {
            "name": name,
            "goal": goal,
            "client": client,
            "target_end_date": target_end,
            "start_date": start_date,
            "budget_hours": budget,
            "complexity": complexity,
        },
        "recent_projects_for_reference": historical["projects"],
    }
    user_message = "Suggest a kickoff plan for this project:\n\n" + json.dumps(user_context, indent=2, default=str)

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
        logger.exception(f"[Kickoff] AI failed: {e}")
        return {"error": f"AI service failed: {e}"}

    if not ai_json:
        return {"error": "AI returned no content"}

    # Compute suggested end_date if not supplied
    if not target_end and ai_json.get("phases"):
        total_weeks = sum(int(p.get("duration_weeks") or 0) for p in ai_json["phases"])
        try:
            start = datetime.fromisoformat(start_date)
        except Exception:
            start = datetime.now(timezone.utc)
        target_end = (start + timedelta(weeks=total_weeks)).date().isoformat()
    ai_json["projected_end_date"] = target_end
    ai_json["start_date"] = start_date
    return ai_json
