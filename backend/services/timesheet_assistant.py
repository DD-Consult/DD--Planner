"""
Natural Language Timesheet Assistant
====================================
Parses free-form phrases like:
  "log 3h on Acme API yesterday"
  "add 6 hours to Website Redesign design phase last Monday"
  "8h Mobile App today"

Returns a proposed timesheet entry (project_id, phase_id, actual_hours,
week_start_date, notes) for the current resource. Uses the AI when possible
and falls back to deterministic parsing for the common shapes.

Does NOT create the entry — the frontend confirms with the user first.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone, date
from typing import Optional, List, Dict

from database import (
    projects_collection, allocations_collection,
)
from services.ai_providers import get_ai_config, call_openai_api, call_gemini_api, call_emergent_fallback
from utils import find_user_resource

logger = logging.getLogger(__name__)


def _week_start(d: date) -> date:
    """Monday of the week containing d."""
    return d - timedelta(days=d.weekday())


def _parse_relative_date(phrase: str) -> Optional[date]:
    """Deterministic parser for common date phrases."""
    p = (phrase or "").lower().strip()
    today = datetime.now(timezone.utc).date()
    if p in ("today", "now", ""):
        return today
    if p in ("yesterday", "yday"):
        return today - timedelta(days=1)
    if p in ("day before yesterday",):
        return today - timedelta(days=2)
    if p in ("tomorrow",):
        return today + timedelta(days=1)
    # "last monday", "this tuesday"
    m = re.match(r"(?:this|last)\s+(mon|tue|wed|thu|fri|sat|sun)(day)?", p)
    if m:
        target_weekday = ("mon", "tue", "wed", "thu", "fri", "sat", "sun").index(m.group(1))
        curr_wd = today.weekday()
        diff = curr_wd - target_weekday
        if "last" in p and diff <= 0:
            diff += 7
        if "this" in p and diff < 0:
            diff += 7
        return today - timedelta(days=diff)
    # "N days ago"
    m = re.match(r"(\d+)\s+days?\s+ago", p)
    if m:
        return today - timedelta(days=int(m.group(1)))
    # "N weeks ago"
    m = re.match(r"(\d+)\s+weeks?\s+ago", p)
    if m:
        return today - timedelta(weeks=int(m.group(1)))
    # ISO
    try:
        return date.fromisoformat(p)
    except Exception:
        return None


def _fuzzy_project_match(query: str, projects: List[dict]) -> Optional[dict]:
    """Case-insensitive substring / token match."""
    q = query.lower().strip()
    if not q:
        return None
    # Exact-ish name match
    for p in projects:
        if q == (p.get("name", "").lower().strip()):
            return p
    # Substring
    for p in projects:
        if q in p.get("name", "").lower():
            return p
    # Client match
    for p in projects:
        if q in (p.get("client_name", "") or "").lower():
            return p
    # Token overlap
    q_tokens = set(re.findall(r"\w+", q))
    best = None
    best_score = 0
    for p in projects:
        name_tokens = set(re.findall(r"\w+", p.get("name", "").lower()))
        client_tokens = set(re.findall(r"\w+", (p.get("client_name") or "").lower()))
        overlap = len(q_tokens & (name_tokens | client_tokens))
        if overlap > best_score:
            best_score = overlap
            best = p
    return best if best_score >= 1 else None


async def parse_timesheet_phrase(phrase: str, current_user: dict) -> dict:
    """Parse a natural-language timesheet phrase for the current user."""
    if not phrase or not phrase.strip():
        return {"error": "Please provide a phrase to parse."}

    # Resolve user's resource
    resource = await find_user_resource(current_user)
    if not resource:
        return {"error": "You don't have a resource profile — timesheets require one."}

    # Load candidate projects: allocated + active (users can log to non-allocated projects too)
    active_projects = await projects_collection.find(
        {"status": {"$in": ["Active", "Pipeline"]}}
    ).to_list(length=500)

    allocated = await allocations_collection.find({"resource_id": str(resource["_id"])}).to_list(length=200)
    allocated_pids = {str(a.get("project_id")) for a in allocated}

    project_summaries = [
        {
            "id": str(p["_id"]),
            "name": p.get("name"),
            "client": p.get("client_name"),
            "is_allocated": str(p["_id"]) in allocated_pids,
            "phases": [
                {"id": (ph.get("id") if isinstance(ph, dict) else ""), "name": (ph.get("name") if isinstance(ph, dict) else str(ph))}
                for ph in (p.get("phases") or [])
            ],
        }
        for p in active_projects
    ]

    # Try AI first — much better at handling wording variations
    system_prompt = """You extract structured timesheet data from natural-language phrases.

Return valid JSON only with this exact structure:
{
  "matched": true|false,
  "project_id": "<id from provided list, or null if unclear>",
  "phase_id": "<phase id under matched project, or null>",
  "actual_hours": <number 0-24, or null>,
  "date": "YYYY-MM-DD (interpreted from the phrase)",
  "notes": "<verbatim task description if any, or empty>",
  "confidence": 0.0-1.0,
  "clarification_needed": "<if unclear, one specific question to ask>"
}

Rules:
- Interpret dates relative to today (which is provided below)
- Match project by name OR client — prefer allocated projects on ties
- If a phase name is mentioned (e.g., "design phase"), match to that phase id under the matched project
- If no phase mentioned, leave phase_id null (frontend will default to first phase)
- Hours: accept "3h", "3 hours", "3.5", "half day" (=4h), "full day" (=8h)
- If the phrase is ambiguous or missing critical info (hours or project), set matched=false and put a clarification question in clarification_needed"""

    today = datetime.now(timezone.utc).date().isoformat()
    user_ctx = {
        "today": today,
        "user_phrase": phrase,
        "candidate_projects": project_summaries,
    }
    user_message = "Parse this timesheet phrase:\n\n" + json.dumps(user_ctx, indent=2, default=str)

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
        logger.exception(f"[TimesheetAssistant] AI failed: {e}")

    # Fallback: deterministic parser
    if not ai_json or not ai_json.get("matched"):
        return _fallback_parse(phrase, project_summaries, resource, ai_json)

    # Compute week_start_date and shape the response
    return _shape_response(ai_json, project_summaries, resource, phrase)


def _fallback_parse(phrase: str, projects: List[dict], resource: dict, ai_json: Optional[dict]) -> dict:
    """Regex-based fallback when AI is unavailable or unsure."""
    # Extract hours
    hours = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:h(?:rs?|ours?)?|hr)\b", phrase.lower())
    if m:
        hours = float(m.group(1))
    else:
        if "half day" in phrase.lower():
            hours = 4
        elif "full day" in phrase.lower():
            hours = 8
        else:
            m2 = re.search(r"^\s*(\d+(?:\.\d+)?)\s+", phrase)
            if m2:
                v = float(m2.group(1))
                if 0 < v <= 24:
                    hours = v

    # Extract date phrase
    date_phrases = [
        r"\byesterday\b", r"\btoday\b", r"\btomorrow\b",
        r"\blast\s+\w+\b", r"\bthis\s+\w+\b", r"\d+\s+days?\s+ago",
        r"\d{4}-\d{2}-\d{2}",
    ]
    parsed_date = datetime.now(timezone.utc).date()
    for dp in date_phrases:
        m = re.search(dp, phrase.lower())
        if m:
            parsed = _parse_relative_date(m.group(0))
            if parsed:
                parsed_date = parsed
                break

    # Match project — strip hours and date phrases and take remaining
    stripped = phrase.lower()
    for dp in date_phrases + [r"\d+(?:\.\d+)?\s*h(?:rs?|ours?)?", r"\d+(?:\.\d+)?\s+hr",
                              "half day", "full day", "log", "add", "record", "hours?", "hrs?"]:
        stripped = re.sub(dp, " ", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip(" ,:.-")

    match = _fuzzy_project_match(stripped, projects) if stripped else None
    if not match and hours is None:
        return {
            "matched": False,
            "clarification_needed": "Which project and how many hours? Try e.g. 'log 3h on Acme yesterday'.",
        }
    if not match:
        return {
            "matched": False,
            "clarification_needed": f"I couldn't identify a project from '{stripped or phrase}'. Please include the project name.",
        }
    if hours is None:
        return {
            "matched": False,
            "clarification_needed": "How many hours? E.g. '3h', '4 hours', 'half day'.",
        }

    return _shape_response({
        "matched": True,
        "project_id": match["id"],
        "phase_id": (match["phases"][0]["id"] if match.get("phases") else None),
        "actual_hours": hours,
        "date": parsed_date.isoformat(),
        "notes": "",
        "confidence": 0.7,
    }, projects, resource, phrase)


def _shape_response(ai_json: dict, projects: List[dict], resource: dict, phrase: str) -> dict:
    """Enrich AI output with project/phase details and week_start_date."""
    matched_pid = ai_json.get("project_id")
    matched_phase_id = ai_json.get("phase_id")
    project = next((p for p in projects if p["id"] == matched_pid), None)
    phase = None
    if project:
        phase = next((ph for ph in project.get("phases", []) if ph["id"] == matched_phase_id), None)
        if not phase and project.get("phases"):
            phase = project["phases"][0]

    parsed_date = None
    try:
        parsed_date = date.fromisoformat(ai_json.get("date", ""))
    except Exception:
        parsed_date = datetime.now(timezone.utc).date()

    week_start = _week_start(parsed_date)

    return {
        "matched": True,
        "resource_id": str(resource["_id"]),
        "resource_name": resource.get("name"),
        "project_id": matched_pid,
        "project_name": (project or {}).get("name"),
        "client_name": (project or {}).get("client"),
        "is_allocated": (project or {}).get("is_allocated", False),
        "phase_id": (phase or {}).get("id"),
        "phase_name": (phase or {}).get("name"),
        "actual_hours": ai_json.get("actual_hours"),
        "date": parsed_date.isoformat(),
        "week_start_date": week_start.isoformat(),
        "notes": ai_json.get("notes") or "",
        "confidence": ai_json.get("confidence", 0.7),
        "original_phrase": phrase,
    }
