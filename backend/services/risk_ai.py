"""
AI-powered risk/issue polisher.

When a user creates or updates a risk with rough free-text input, this service
automatically rewrites it into a clear, concise, professional statement and
classifies it (Risk vs Issue, impact areas, severity, etc.).

Provider: Gemini (gemini-2.5-flash) via the existing settings_collection key,
with an Emergent LLM fallback for resilience.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from database import settings_collection, EMERGENT_LLM_KEY
from services.ai_instructions import get_instructions_for_prompt

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────
# Schema constants — keep in sync with frontend and Risk Pydantic models
# ────────────────────────────────────────────────────────────────────────────

CATEGORIES = ["Risk", "Issue"]
IMPACT_AREAS = ["Scope", "Budget", "Timeline", "Quality", "Resources", "Stakeholder"]
SEVERITY_LEVELS = ["Low", "Medium", "High", "Critical"]
PROBABILITY_LEVELS = ["Low", "Medium", "High"]


# ────────────────────────────────────────────────────────────────────────────
# Gemini key resolver
# ────────────────────────────────────────────────────────────────────────────

async def _get_gemini_key() -> Optional[str]:
    """Try several places to find a usable Gemini key (user preference: Gemini)."""
    # 1. settings_collection (admin-configured)
    s = await settings_collection.find_one({"type": "ai_config"})
    if s and (s.get("ai_provider") in ("gemini", "google")) and s.get("ai_api_key"):
        return s["ai_api_key"]
    # 2. dedicated gemini settings document
    s2 = await settings_collection.find_one({"type": "gemini_config"})
    if s2 and s2.get("api_key"):
        return s2["api_key"]
    # 3. environment fallbacks
    import os
    for k in ("GEMINI_API_KEY", "GOOGLE_AI_API_KEY", "GOOGLE_API_KEY"):
        if os.environ.get(k):
            return os.environ[k]
    return None


# ────────────────────────────────────────────────────────────────────────────
# System prompt (kept short — token budget matters for snappy UX)
# ────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a senior project-management editor. Take rough risk/issue notes from a project manager and rewrite them into a clear, concise, professional statement, then classify them.

Rules:
- Output ONLY valid JSON, no markdown fences.
- "description": one or two sentences, action-oriented, no jargon. Start with the THREAT or CONDITION (e.g. "Insufficient testing capacity may delay UAT sign-off…"). Avoid corporate filler.
- "category": Determine carefully:
    * "Issue" — the event has ALREADY happened or is CURRENTLY happening. Look for past-tense verbs ("quit", "left", "broke", "missed", "happened", "is delayed"), specific recent timeframes ("last week", "yesterday", "today"), or definite/realised events.
    * "Risk" — the event MIGHT happen but hasn't yet. Look for conditional language ("may", "could", "if", "potential", "might").
    When in doubt with past-tense verbs about a specific recent event, classify as "Issue".
- "impact_areas": array of one or more from {Scope, Budget, Timeline, Quality, Resources, Stakeholder}. Always include at least one.
- "impact": severity if it materialises — one of {Low, Medium, High, Critical}.
- "probability": likelihood of occurring — one of {Low, Medium, High}. For Issues (already happened) set to "High".
- "mitigation": one short sentence describing a concrete, actionable mitigation/response. If the user provided one and it's already good, polish it; otherwise propose a sensible default.

Examples:
  Input: "lead developer quit last week we have no replacement"
  → category: "Issue" (past-tense + specific timeframe)
  Input: "vendor might miss the deadline"
  → category: "Risk" (conditional)
  Input: "budget is tight"
  → category: "Issue" (currently happening)

Return shape:
{
  "description": string,
  "category": "Risk" | "Issue",
  "impact_areas": [string, ...],
  "impact": "Low" | "Medium" | "High" | "Critical",
  "probability": "Low" | "Medium" | "High",
  "mitigation": string
}
"""


def _build_user_message(raw: Dict[str, Any]) -> str:
    """Compose the user-side prompt from the raw risk dict."""
    lines = ["Raw risk/issue input from the user:"]
    if raw.get("description"):
        lines.append(f"- Description: {raw['description']}")
    if raw.get("mitigation"):
        lines.append(f"- Existing mitigation note: {raw['mitigation']}")
    if raw.get("impact"):
        lines.append(f"- User-tagged impact: {raw['impact']}")
    if raw.get("probability"):
        lines.append(f"- User-tagged probability: {raw['probability']}")
    if raw.get("category"):
        lines.append(f"- User-tagged category: {raw['category']}")
    if raw.get("impact_areas"):
        lines.append(f"- User-tagged impact areas: {', '.join(raw['impact_areas'])}")
    if raw.get("_project_context"):
        lines.append(f"\nProject context: {raw['_project_context']}")
    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────────────
# Gemini call
# ────────────────────────────────────────────────────────────────────────────

async def _call_gemini(api_key: str, system_prompt: str, user_message: str) -> Optional[Dict[str, Any]]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{
                        "parts": [{"text": f"{system_prompt}\n\n{user_message}"}]
                    }],
                    "generationConfig": {
                        "temperature": 0.2,
                        "responseMimeType": "application/json",
                    },
                },
            )
    except Exception as e:
        logger.warning(f"[risk_ai] Gemini call exception: {e}")
        return None

    if resp.status_code != 200:
        logger.warning(f"[risk_ai] Gemini {resp.status_code}: {resp.text[:200]}")
        return None

    try:
        result = resp.json()
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        # Strip any code fences just in case
        cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return json.loads(cleaned.strip())
    except Exception as e:
        logger.warning(f"[risk_ai] Gemini parse error: {e} | raw={resp.text[:200]}")
        return None


async def _call_emergent_fallback(system_prompt: str, user_message: str) -> Optional[Dict[str, Any]]:
    """Fallback if Gemini isn't available."""
    if not EMERGENT_LLM_KEY:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import uuid as _uuid
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"risk-polish-{_uuid.uuid4()}",
            system_message=system_prompt,
        ).with_model("openai", "gpt-4o-mini")
        msg = UserMessage(text=user_message + "\n\nRespond with valid JSON only.")
        response = await chat.send_message(msg)
        if isinstance(response, str):
            cleaned = re.sub(r"^```(?:json)?\s*", "", response.strip())
            cleaned = re.sub(r"\s*```$", "", cleaned)
            return json.loads(cleaned.strip())
        return response
    except Exception as e:
        logger.warning(f"[risk_ai] Emergent fallback error: {e}")
        return None


# ────────────────────────────────────────────────────────────────────────────
# Validation & merging
# ────────────────────────────────────────────────────────────────────────────

def _coerce_enum(value: Any, allowed: List[str], default: str) -> str:
    if not isinstance(value, str):
        return default
    v = value.strip()
    for a in allowed:
        if a.lower() == v.lower():
            return a
    return default


def _coerce_impact_areas(value: Any) -> List[str]:
    if not isinstance(value, list):
        return ["Timeline"]
    out: List[str] = []
    for v in value:
        if not isinstance(v, str):
            continue
        for a in IMPACT_AREAS:
            if a.lower() == v.strip().lower() and a not in out:
                out.append(a)
                break
    return out or ["Timeline"]


def _validate_ai_output(ai: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    """Enforce schema; fall back to raw values if AI output is malformed."""
    desc = (ai.get("description") or raw.get("description") or "").strip()
    if not desc:
        desc = raw.get("description", "")
    category = _coerce_enum(ai.get("category"), CATEGORIES, raw.get("category") or "Risk")
    impact = _coerce_enum(ai.get("impact"), SEVERITY_LEVELS, raw.get("impact") or "Medium")
    probability = _coerce_enum(ai.get("probability"), PROBABILITY_LEVELS, raw.get("probability") or "Medium")
    impact_areas = _coerce_impact_areas(ai.get("impact_areas"))
    mitigation = (ai.get("mitigation") or raw.get("mitigation") or "").strip()
    return {
        "description": desc,
        "category": category,
        "impact": impact,
        "probability": probability,
        "impact_areas": impact_areas,
        "mitigation": mitigation,
        "ai_polished": True,
    }


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────

async def polish_risk(raw: Dict[str, Any], *, project_context: Optional[str] = None, project_id: Optional[str] = None) -> Dict[str, Any]:
    """Rewrite a raw risk/issue dict using Gemini (with fallback). Returns a dict
    with the same keys plus `impact_areas` and `ai_polished=True`. If the AI
    call fails for any reason, returns the raw input unchanged (no exception).
    """
    if not (raw.get("description") or "").strip():
        # No description = nothing to polish
        return {**raw, "ai_polished": False}

    payload = dict(raw)
    if project_context:
        payload["_project_context"] = project_context

    user_msg = _build_user_message(payload)

    # Inject custom AI instructions
    custom_instructions = await get_instructions_for_prompt(
        category="risk_polish",
        project_id=project_id
    )
    effective_prompt = _SYSTEM_PROMPT + custom_instructions

    api_key = await _get_gemini_key()
    ai_output: Optional[Dict[str, Any]] = None
    if api_key:
        ai_output = await _call_gemini(api_key, effective_prompt, user_msg)
    if not ai_output:
        ai_output = await _call_emergent_fallback(effective_prompt, user_msg)

    if not ai_output:
        logger.info("[risk_ai] No AI output; returning raw risk untouched")
        # Still infer impact_areas (default Timeline) so the new field exists
        return {
            **raw,
            "impact_areas": raw.get("impact_areas") or ["Timeline"],
            "ai_polished": False,
        }

    return _validate_ai_output(ai_output, raw)
