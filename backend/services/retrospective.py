"""
Project Retrospective Generator
===============================
AI-powered post-project (or mid-project) retrospective. Assembles a rich
project snapshot and asks the LLM to write a structured retrospective with:

  • What went well
  • What didn't go well
  • Root causes / lessons learned
  • Recommendations for future projects
  • Overall grade (A-F) with reasoning

Retrospectives are persisted so admins can revisit and compare.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from database import (
    projects_collection, timesheets_collection, allocations_collection,
    risks_collection, status_updates_collection, wbs_tasks_collection,
    resources_collection, db,
)
from services.ai_providers import (
    get_ai_config, call_openai_api, call_gemini_api, call_emergent_fallback,
)
from services.ai_instructions import get_instructions_for_prompt

logger = logging.getLogger(__name__)

# Collection for storing generated retrospectives
retrospectives_collection = db.project_retrospectives


async def _build_snapshot(project_id: str) -> Optional[dict]:
    try:
        p = await projects_collection.find_one({"_id": ObjectId(project_id)})
    except Exception:
        return None
    if not p:
        return None

    resources_map = {str(r["_id"]): r for r in await resources_collection.find().to_list(length=500)}
    ts = await timesheets_collection.find({"project_id": project_id}).to_list(length=20000)
    allocs = await allocations_collection.find({"project_id": project_id}).to_list(length=1000)
    risks = await risks_collection.find({"project_id": project_id}).to_list(length=500)
    sus = await status_updates_collection.find({"project_id": project_id}).sort("created_at", 1).to_list(length=200)
    wbs = await wbs_tasks_collection.find({"project_id": project_id}).to_list(length=2000)

    actual_hours = sum(float(t.get("actual_hours") or 0) for t in ts)
    planned_hours = float(p.get("budgeted_hours") or 0)
    budget_variance = actual_hours - planned_hours

    leaf = [t for t in wbs if float(t.get("estimated_hours") or 0) > 0 and not t.get("is_milestone")]
    total_est = sum(float(t.get("estimated_hours") or 0) for t in leaf) or 0
    done_est = sum(float(t.get("estimated_hours") or 0) for t in leaf
                   if (t.get("status") or "").lower() in ("done", "completed"))
    wbs_complete_pct = (done_est / total_est * 100) if total_est else None

    milestones = [t for t in wbs if t.get("is_milestone")]
    milestones_hit = sum(1 for m in milestones if (m.get("status") or "").lower() in ("done", "completed"))
    milestones_missed = sum(
        1 for m in milestones
        if (m.get("status") or "").lower() not in ("done", "completed")
        and m.get("end_date") and datetime.fromisoformat(str(m["end_date"]).replace("Z", "+00:00")) < datetime.now(timezone.utc)
    )

    risks_open = [r for r in risks if r.get("status") == "Active"]
    risks_mitigated = [r for r in risks if r.get("status") in ("Mitigated", "Closed")]

    top_contributors = {}
    for t in ts:
        rid = str(t.get("resource_id", ""))
        if not rid:
            continue
        top_contributors[rid] = top_contributors.get(rid, 0) + float(t.get("actual_hours") or 0)
    top_5 = sorted(top_contributors.items(), key=lambda kv: -kv[1])[:5]
    top_contributor_names = [
        {"name": (resources_map.get(rid, {}) or {}).get("name", "Unknown"), "hours": round(h, 1)}
        for rid, h in top_5
    ]

    health_arc = [
        {"date": (su.get("created_at").isoformat() if hasattr(su.get("created_at"), "isoformat") else str(su.get("created_at"))),
         "health": su.get("health"), "schedule": su.get("schedule_status"), "progress": su.get("actual_progress")}
        for su in sus[-8:]
    ]

    return {
        "project": {
            "id": str(p["_id"]),
            "name": p.get("name"),
            "client": p.get("client_name"),
            "status": p.get("status"),
            "start_date": str(p.get("start_date"))[:10] if p.get("start_date") else None,
            "end_date": str(p.get("end_date"))[:10] if p.get("end_date") else None,
        },
        "budget": {
            "planned_hours": planned_hours,
            "actual_hours": round(actual_hours, 1),
            "variance_hours": round(budget_variance, 1),
            "variance_pct": round((budget_variance / planned_hours * 100), 1) if planned_hours else None,
        },
        "wbs": {
            "leaf_tasks": len(leaf),
            "completion_pct": round(wbs_complete_pct, 1) if wbs_complete_pct is not None else None,
        },
        "milestones": {
            "total": len(milestones),
            "hit": milestones_hit,
            "missed_or_overdue": milestones_missed,
        },
        "risks": {
            "open": len(risks_open),
            "mitigated": len(risks_mitigated),
            "top_open": [
                {"description": r.get("description"), "impact": r.get("impact"),
                 "mitigation": r.get("mitigation")}
                for r in risks_open[:5]
            ],
        },
        "status_updates_count": len(sus),
        "health_arc": health_arc,
        "top_contributors": top_contributor_names,
        "allocations_count": len(allocs),
    }


async def generate_retrospective(project_id: str, requested_by: str) -> dict:
    """Generate and persist a retrospective for a project."""
    snap = await _build_snapshot(project_id)
    if not snap:
        return {"error": "Project not found"}

    system_prompt = """You are a senior program management expert writing an honest,
constructive project retrospective. You are direct but not cynical — every criticism
comes paired with an actionable lesson.

Return valid JSON only with this exact structure:
{
  "grade": "A|B|C|D|F",
  "grade_reasoning": "one-sentence justification",
  "summary": "2-3 sentence executive summary",
  "what_went_well": ["bullet 1", "bullet 2", ...],
  "what_didnt_go_well": ["bullet 1", "bullet 2", ...],
  "root_causes": ["bullet 1", "bullet 2", ...],
  "lessons_learned": ["actionable lesson 1", "actionable lesson 2", ...],
  "recommendations": ["specific recommendation for next similar project", ...],
  "kpi_highlights": {
    "delivered_on_time": true|false|null,
    "delivered_on_budget": true|false|null,
    "quality_indicator": "strong|adequate|weak|unknown"
  }
}

Guidance:
- Be specific: cite hours, %s, milestone counts, health arc
- Every "what didn't go well" should have a matching "lesson learned"
- Recommendations should be practical (e.g. "Add 15% contingency for API-heavy phases")
- If data is thin, say so in the summary rather than fabricating"""

    custom = await get_instructions_for_prompt(category="retrospective")
    system_prompt += custom

    user_message = "Analyze this project and write the retrospective:\n\n" + json.dumps(snap, indent=2, default=str)

    ai_config = await get_ai_config()
    ai_json = None
    provider_used = ai_config.get("provider") or "unknown"

    try:
        if ai_config["provider"] == "openai" and ai_config["api_key"]:
            resp = await call_openai_api(ai_config["api_key"], system_prompt, user_message)
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                ai_json = json.loads(content)
        elif ai_config["provider"] == "gemini" and ai_config["api_key"]:
            resp = await call_gemini_api(ai_config["api_key"], system_prompt, user_message)
            if resp.status_code == 200:
                content = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                ai_json = json.loads(content)
        if ai_json is None:
            ai_json = await call_emergent_fallback(system_prompt, user_message)
            provider_used = "emergent_fallback"
    except Exception as e:
        logger.exception(f"[Retrospective] AI call failed: {e}")
        return {"error": f"AI service failed: {e}"}

    if not ai_json:
        return {"error": "AI returned no content."}

    now = datetime.now(timezone.utc)
    doc = {
        "project_id": project_id,
        "project_name": snap["project"]["name"],
        "generated_by": requested_by,
        "generated_at": now,
        "provider": provider_used,
        "snapshot": snap,
        "retrospective": ai_json,
    }
    inserted = await retrospectives_collection.insert_one(doc)
    doc["_id"] = str(inserted.inserted_id)
    doc["generated_at"] = now.isoformat()
    return doc


async def list_retrospectives(project_id: str) -> list:
    cursor = retrospectives_collection.find(
        {"project_id": project_id},
        {"snapshot": 0},  # trim payload for list view
    ).sort("generated_at", -1)
    rows = await cursor.to_list(length=50)
    for r in rows:
        r["_id"] = str(r["_id"])
        if hasattr(r.get("generated_at"), "isoformat"):
            r["generated_at"] = r["generated_at"].isoformat()
    return rows


async def get_retrospective(retro_id: str) -> Optional[dict]:
    try:
        r = await retrospectives_collection.find_one({"_id": ObjectId(retro_id)})
    except Exception:
        return None
    if not r:
        return None
    r["_id"] = str(r["_id"])
    if hasattr(r.get("generated_at"), "isoformat"):
        r["generated_at"] = r["generated_at"].isoformat()
    return r


async def delete_retrospective(retro_id: str) -> bool:
    try:
        result = await retrospectives_collection.delete_one({"_id": ObjectId(retro_id)})
        return result.deleted_count > 0
    except Exception:
        return False
