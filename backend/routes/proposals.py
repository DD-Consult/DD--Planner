"""DD Planner Secure AI-Guided Proposal Module (Enhancement #5)

This module provides a full proposal lifecycle: AI-guided drafting, admin editing,
secure public sharing, client engagement tracking, and auto-provisioning of projects
and client access upon acceptance.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone
from bson import ObjectId
import secrets
import json
import re
import uuid as uuid_module
from dateutil.parser import parse as dateutil_parse

from database import (
    proposals_collection,
    proposal_events_collection,
    proposal_templates_collection,
    projects_collection,
    users_collection,
    report_links_collection,
    notifications_collection,
    allocations_collection,
    resources_collection,
    resend,
    SENDER_EMAIL,
    RESEND_API_KEY,
)
from auth.dependencies import require_admin, get_password_hash, create_access_token
from utils import serialize_doc
from services.proposals.renderer import (
    load_sample_brief,
    validate_brief,
    render_proposal_html,
)
from services.proposals.doc_ingest import extract_text
from services.ai_providers import get_ai_config, call_openai_api, call_gemini_api, call_emergent_fallback, extract_gemini_text

router = APIRouter()


# ============================================================
# UTILITY FUNCTIONS (reused from client_portal)
# ============================================================

def generate_secure_token(length: int = 64) -> str:
    """Generate a cryptographically secure random token"""
    return secrets.token_urlsafe(length)


def generate_verification_code() -> str:
    """Generate a 6-digit verification code"""
    import random
    return str(random.randint(100000, 999999))


def _public_base_url(request: Request) -> str:
    """Derive the public-facing base URL from forwarded headers"""
    proto = request.headers.get("x-forwarded-proto")
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    
    if host:
        host = host.split(",")[0].strip()
        proto = (proto.split(",")[0].strip() if proto else None) or "https"
        return f"{proto}://{host}"
    
    return str(request.base_url).rstrip('/')


async def send_proposal_link_email(email: str, link: str, client_name: str, title: str):
    """Send proposal link email via the active method + editable template/branding.

    Returns (sent: bool, message: str). Best-effort — never raises.
    """
    from services.email_config import send_email, get_email_settings_block
    from services.email_templates import render_email
    email_block = await get_email_settings_block()
    subject, html = render_email(email_block, "proposal_link", {
        "client_name": client_name,
        "proposal_title": title,
        "link": link,
    })
    return await send_email(email, subject, html, email_type="proposal_link", related_label=title)


# ============================================================
# AI HELPER (shared by ai-draft and project pre-fill)
# ============================================================

async def _call_ai_for_text(system_prompt: str, user_message: str) -> Optional[str]:
    """Call the configured AI provider and return the raw text response.

    Mirrors the provider-selection logic used across the app (ai.py). Falls back
    to the Emergent LLM on provider failure. Returns None if no AI is available.
    """
    ai_config = await get_ai_config()
    provider = ai_config.get("provider")
    api_key = ai_config.get("api_key")
    if not api_key:
        return None

    if provider == "openai":
        response = await call_openai_api(api_key, system_prompt, user_message, json_mode=True)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        fb = await call_emergent_fallback(system_prompt, user_message)
        return json.dumps(fb) if fb else None
    if provider == "gemini":
        response = await call_gemini_api(api_key, system_prompt, user_message, json_mode=True)
        if response.status_code == 200:
            return extract_gemini_text(response.json())
        fb = await call_emergent_fallback(system_prompt, user_message)
        return json.dumps(fb) if fb else None
    # emergent (default)
    fb = await call_emergent_fallback(system_prompt, user_message)
    return json.dumps(fb) if fb else None


def _parse_ai_brief(text: str, fallback_data: dict):
    """Strip code fences and parse the AI JSON response into (assistant_message, data).
    Returns (None, None) on parse failure."""
    if not text:
        return None, None
    cleaned = re.sub(r'^```(?:json)?\s*', '', text.strip())
    cleaned = re.sub(r'\s*```$', '', cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None, None
    return parsed.get("assistant_message", "Updated"), parsed.get("data", fallback_data)


def _deep_merge_onto(base: dict, overlay):
    """Deep-merge `overlay` onto a deepcopy of `base`.

    Guarantees every key present in `base` survives (so the renderer never hits a
    missing nested key), while non-empty values from `overlay` win. Empty/None
    values in the overlay are ignored (scaffold default kept).
    """
    import copy
    result = copy.deepcopy(base)
    if not isinstance(overlay, dict):
        return result
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge_onto(result[k], v)
        elif v in (None, "", [], {}):
            # keep scaffold default for empty/missing overlay values
            if k not in result:
                result[k] = v
        else:
            result[k] = v
    return result


def _coerce_valid_brief(ai_data: dict, scaffold: dict) -> dict:
    """Guarantee a schema-valid, fully-renderable brief.

    Smaller/cheaper models sometimes omit nested fields (e.g.
    understanding.challenges) or return structurally-invalid parts (e.g. options
    with a single made-up path), which break the renderer/validator. We:
      1. DEEP-MERGE the AI output onto the complete scaffold skeleton so EVERY
         key the renderer touches always exists (AI prose wins where present).
      2. Repair the STRUCTURAL fields the v4 validator enforces.
    """
    import copy
    if not isinstance(ai_data, dict):
        return copy.deepcopy(scaffold)

    # 1. Deep merge — fills any missing nested keys from the scaffold.
    data = _deep_merge_onto(scaffold, ai_data)

    # 2. Structural repairs (deep-merge can't guarantee these).
    # recommended_path must be a / b / c
    if data.get("recommended_path") not in ("a", "b", "c"):
        data["recommended_path"] = scaffold.get("recommended_path", "a")

    # options must be exactly paths a, b, c. Carry AI prose onto the scaffold's
    # 3-path skeleton when the AI returned the wrong shape.
    def _options_ok(opts):
        return (
            isinstance(opts, list)
            and {o.get("path") for o in opts if isinstance(o, dict)} == {"a", "b", "c"}
        )
    if not _options_ok(data.get("options")):
        base_opts = copy.deepcopy(scaffold.get("options", []))
        ai_opts = ai_data.get("options") if isinstance(ai_data.get("options"), list) else []
        for i, bo in enumerate(base_opts):
            if i < len(ai_opts) and isinstance(ai_opts[i], dict):
                for key in ("name", "tagline", "who_for", "includes"):
                    if ai_opts[i].get(key):
                        bo[key] = ai_opts[i][key]
        data["options"] = base_opts

    # pricing_model must have path_a/b/c
    pm = data.get("pricing_model")
    if not isinstance(pm, dict) or not all(f"path_{k}" in pm for k in ("a", "b", "c")):
        data["pricing_model"] = copy.deepcopy(scaffold.get("pricing_model", {}))

    # plan.stage_deliverables must have keys "1".."4"
    plan = data.get("plan", {})
    sd = plan.get("stage_deliverables") if isinstance(plan, dict) else None
    if not isinstance(sd, dict) or not all(str(k) in sd for k in ("1", "2", "3", "4")):
        data.setdefault("plan", {})["stage_deliverables"] = copy.deepcopy(
            scaffold.get("plan", {}).get("stage_deliverables", {})
        )

    # success.gates must have exactly 4 entries
    gates = data.get("success", {}).get("gates") if isinstance(data.get("success"), dict) else None
    if not isinstance(gates, list) or len(gates) != 4:
        data.setdefault("success", {})["gates"] = copy.deepcopy(
            scaffold.get("success", {}).get("gates", [])
        )

    return data


# ============================================================
# PYDANTIC MODELS
# ============================================================

class ProposalCreateRequest(BaseModel):
    client_name: Optional[str] = None
    proposal_title: Optional[str] = None


class ProposalUpdateRequest(BaseModel):
    data: dict


class AIDraftRequest(BaseModel):
    message: str
    current_data: Optional[dict] = None


class ProposalFromProjectRequest(BaseModel):
    project_id: str
    use_ai: bool = True  # if True, AI polishes the mapped facts into on-brand prose


class TemplateCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    # If provided, snapshot this proposal's data as the template; else snapshot `data`.
    from_proposal_id: Optional[str] = None
    data: Optional[dict] = None


class TemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    data: Optional[dict] = None


class ProposalFromTemplateRequest(BaseModel):
    template_id: str
    client_name: Optional[str] = None
    proposal_title: Optional[str] = None


class ProposalFromDriveRequest(BaseModel):
    doc_id: str          # Google Doc id or full URL
    use_ai: bool = True


# ============================================================
# ADMIN ENDPOINTS
# ============================================================

@router.post("/api/proposals")
async def create_proposal(
    req: Optional[ProposalCreateRequest] = None,
    admin: dict = Depends(require_admin)
):
    """Create a new proposal (admin only). Starts from the v4 sample brief scaffold."""
    # Load the v4 sample as the base
    data = load_sample_brief()
    
    # Override with provided fields
    if req:
        if req.client_name:
            data["client_name"] = req.client_name
        if req.proposal_title:
            data["proposal_title"] = req.proposal_title
    
    # Generate a unique proposal slug
    client_slug = (req.client_name if req and req.client_name else "proposal").lower().replace(" ", "-")
    short_id = str(uuid_module.uuid4())[:8]
    data["proposal_slug"] = f"{client_slug}-{short_id}"
    
    # Create proposal document
    proposal_doc = {
        "token": generate_secure_token(32),
        "status": "Draft",
        "data": data,
        "created_by": admin.get("email", ""),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "sent_at": None,
        "valid_until_date": None,
        "accepted_by": None,
        "accepted_path": None,
        "accepted_at": None,
        "decline_reason": None,
        "declined_at": None,
        "confirmed_at": None,
        "linked_project_id": None,
        "linked_client_user_id": None,
        "linked_report_token": None,
        "last_client_activity_at": None,
    }
    
    result = await proposals_collection.insert_one(proposal_doc)
    proposal_doc["_id"] = result.inserted_id
    
    return serialize_doc(proposal_doc)


def _weeks_between(start, end) -> int:
    """Whole weeks between two datetimes (min 1)."""
    try:
        if isinstance(start, str):
            start = dateutil_parse(start)
        if isinstance(end, str):
            end = dateutil_parse(end)
        days = max(1, (end - start).days)
        return max(1, round(days / 7))
    except Exception:
        return 8


@router.post("/api/proposals/from-project")
async def create_proposal_from_project(
    req: ProposalFromProjectRequest,
    admin: dict = Depends(require_admin),
):
    """Create a new proposal PRE-FILLED from an existing DD project (Phase 2a).

    Maps real project facts (client, title, timeline, phases, team, budget) onto
    the v4 brief scaffold, then (optionally) uses the AI to turn those facts into
    on-brand proposal prose. The PM refines the result in the builder.
    """
    # Fetch the project
    try:
        project = await projects_collection.find_one({"_id": ObjectId(req.project_id)})
    except Exception:
        project = await projects_collection.find_one({"id": req.project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Build a facts dict from the project
    pname = project.get("name", "")
    client = project.get("client_name", "")
    objective = project.get("project_objective") or ""
    start = project.get("start_date")
    end = project.get("end_date")
    weeks = _weeks_between(start, end)
    budgeted_hours = project.get("budgeted_hours")
    phases = project.get("phases", []) or []
    phase_names = [p.get("name", f"Phase {i+1}") for i, p in enumerate(phases)]

    # Team from allocations -> resource names/roles
    team_facts = []
    try:
        pid_str = str(project["_id"])
        allocs = await allocations_collection.find(
            {"project_id": {"$in": [pid_str, str(project.get("id") or "")]}}
        ).to_list(length=50)
        res_ids = list({a.get("resource_id") for a in allocs if a.get("resource_id")})
        obj_ids = []
        for rid in res_ids:
            try:
                obj_ids.append(ObjectId(rid))
            except Exception:
                pass
        res_map = {}
        if obj_ids:
            async for r in resources_collection.find({"_id": {"$in": obj_ids}}):
                res_map[str(r["_id"])] = {"name": r.get("name", ""), "role": r.get("role", "")}
        seen = set()
        for a in allocs:
            info = res_map.get(a.get("resource_id"))
            if info and info["name"] and info["name"] not in seen:
                seen.add(info["name"])
                initials = "".join(w[0] for w in info["name"].split()[:2]).upper() or "DD"
                team_facts.append({
                    "initials": initials,
                    "name": info["name"],
                    "role": a.get("role") or info["role"] or "Team member",
                    "focus": "",
                })
    except Exception as e:
        print(f"[PROPOSALS] team mapping skipped: {e}")

    # Start from the scaffold and overlay concrete facts
    data = load_sample_brief()
    data["client_name"] = client or data.get("client_name", "")
    data["proposal_title"] = pname or data.get("proposal_title", "")
    client_slug = (client or pname or "proposal").lower().replace(" ", "-")
    data["proposal_slug"] = f"{client_slug}-{str(uuid_module.uuid4())[:8]}"
    if team_facts:
        data["team"] = team_facts
    # Reflect timeline length in the recommended path's duration label
    try:
        rec = data.get("recommended_path", "a")
        data["pricing_model"][f"path_{rec}"]["duration_label"] = f"{weeks} weeks"
    except Exception:
        pass

    warnings = []
    assistant_note = "Pre-filled from project facts (client, title, timeline, team)."

    # Optionally let the AI turn the project facts into on-brand proposal prose
    if req.use_ai:
        sample_brief = load_sample_brief()
        facts = {
            "project_name": pname,
            "client_name": client,
            "objective": objective,
            "timeline_weeks": weeks,
            "phase_names": phase_names,
            "budgeted_hours": budgeted_hours,
            "team": team_facts,
            "status_summary": project.get("status_summary") or "",
        }
        system_prompt = f"""You are an AI proposal assistant for DD Consulting, a digital transformation consultancy.
You will turn FACTS about an existing project into a complete, on-brand client proposal brief.

## PROPOSAL BRIEF SCHEMA (return EXACTLY this structure, every key present)
{json.dumps(sample_brief, indent=2)}

## BRAND & WORDING GUARDRAILS (CRITICAL)
1. AWS Funding: always "positioned to apply for" / "if approved"; never "funded"/"guaranteed".
2. Credentials order: PMP, Prosci/ADKAR, ISO 42001, AWS, HubSpot.
3. Public refs use ddconsult.com.au; ddconsult.tech only for the contact email.
4. Pricing entered ONLY as hours/rate/percentages/tier_fee — never finished totals or bare multipliers.
5. options must contain EXACTLY paths a, b, c. success.gates EXACTLY 4. stage_deliverables keys "1".."4".

## TASK
Use the FACTS to populate client_name, proposal_title, understanding, vision, options, plan (timeline/stages that reflect the project's phases and {facts['timeline_weeks']}-week timeline), team (use the provided team members), and realistic pricing. Where facts are missing, write sensible, conservative placeholder prose the PM can refine. Keep every field valid.

Return ONLY valid JSON: {{"assistant_message": "<1-2 sentence summary>", "data": {{<full brief>}}}}"""
        user_message = f"FACTS about the project:\n{json.dumps(facts, indent=2, default=str)}\n\nProduce the full proposal brief."
        try:
            text = await _call_ai_for_text(system_prompt, user_message)
            msg, new_data = _parse_ai_brief(text, data)
            if new_data:
                # Repair any structural issues so the brief is always schema-valid.
                new_data = _coerce_valid_brief(new_data, sample_brief)
                # keep our deterministic slug
                new_data["proposal_slug"] = data["proposal_slug"]
                # keep the mapped team if the AI dropped it
                if team_facts and not new_data.get("team"):
                    new_data["team"] = team_facts
                data = new_data
                assistant_note = msg or assistant_note
                try:
                    warnings = validate_brief(data)
                except SystemExit as e:
                    # Should be rare after coercion; fall back to mapped-facts scaffold.
                    print(f"[PROPOSALS] from-project brief still invalid after coercion: {e}")
                    warnings.append("AI output could not be fully validated; used mapped facts.")
            else:
                assistant_note += " (AI polish unavailable — used mapped facts; refine in the builder.)"
        except Exception as e:
            print(f"[PROPOSALS] from-project AI polish failed: {e}")
            assistant_note += " (AI polish failed — used mapped facts.)"

    proposal_doc = {
        "token": generate_secure_token(32),
        "status": "Draft",
        "data": data,
        "created_by": admin.get("email", ""),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "sent_at": None,
        "valid_until_date": None,
        "accepted_by": None,
        "accepted_path": None,
        "accepted_at": None,
        "decline_reason": None,
        "declined_at": None,
        "confirmed_at": None,
        "linked_project_id": str(project["_id"]),
        "linked_client_user_id": None,
        "linked_report_token": None,
        "last_client_activity_at": None,
        "source": {"type": "project", "project_id": str(project["_id"])},
    }
    result = await proposals_collection.insert_one(proposal_doc)
    proposal_doc["_id"] = result.inserted_id

    out = serialize_doc(proposal_doc)
    out["assistant_message"] = assistant_note
    out["warnings"] = warnings
    return out


@router.get("/api/proposals")
async def list_proposals(admin: dict = Depends(require_admin)):
    """List all proposals (admin only) with summary fields"""
    cursor = proposals_collection.find().sort("created_at", -1)
    proposals = await cursor.to_list(length=500)
    
    # Return summary view (no full data, no html)
    summaries = []
    for p in proposals:
        data = p.get("data", {})
        summaries.append({
            "id": str(p["_id"]),
            "client_name": data.get("client_name", ""),
            "proposal_title": data.get("proposal_title", ""),
            "status": p.get("status", "Draft"),
            "created_at": p.get("created_at"),
            "updated_at": p.get("updated_at"),
            "sent_at": p.get("sent_at"),
            "valid_until": data.get("valid_until", ""),
            "accepted_by": p.get("accepted_by"),
            "accepted_path": p.get("accepted_path"),
            "last_client_activity_at": p.get("last_client_activity_at"),
        })
    
    return summaries


# ============================================================
# REUSABLE TEMPLATES (Phase 2b)
# ============================================================

@router.post("/api/proposal-templates")
async def create_template(req: TemplateCreateRequest, admin: dict = Depends(require_admin)):
    """Save a reusable proposal template (admin only).

    Snapshot comes from an existing proposal (from_proposal_id) or an explicit
    `data` brief. The stored data is coerced to a valid brief so it always
    produces a renderable proposal when instantiated.
    """
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Template name is required")

    data = None
    if req.from_proposal_id:
        src = await proposals_collection.find_one({"_id": ObjectId(req.from_proposal_id)})
        if not src:
            raise HTTPException(status_code=404, detail="Source proposal not found")
        data = src.get("data")
    elif req.data:
        data = req.data

    if not data:
        # Start from the v4 sample as a sensible default template.
        data = load_sample_brief()

    # Ensure the template data is always valid/renderable.
    data = _coerce_valid_brief(data, load_sample_brief())

    doc = {
        "name": req.name.strip(),
        "description": req.description or "",
        "data": data,
        "created_by": admin.get("email", ""),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    result = await proposal_templates_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


@router.get("/api/proposal-templates")
async def list_templates(admin: dict = Depends(require_admin)):
    """List reusable templates (admin only) — summary fields only."""
    cursor = proposal_templates_collection.find().sort("created_at", -1)
    templates = await cursor.to_list(length=500)
    return [
        {
            "id": str(t["_id"]),
            "name": t.get("name", ""),
            "description": t.get("description", ""),
            "created_by": t.get("created_by", ""),
            "created_at": t.get("created_at"),
            "updated_at": t.get("updated_at"),
        }
        for t in templates
    ]


@router.get("/api/proposal-templates/{template_id}")
async def get_template(template_id: str, admin: dict = Depends(require_admin)):
    """Get a full template (admin only)."""
    t = await proposal_templates_collection.find_one({"_id": ObjectId(template_id)})
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return serialize_doc(t)


@router.put("/api/proposal-templates/{template_id}")
async def update_template(template_id: str, req: TemplateUpdateRequest, admin: dict = Depends(require_admin)):
    """Update a template's name/description/data (admin only)."""
    update = {}
    if req.name is not None:
        update["name"] = req.name.strip()
    if req.description is not None:
        update["description"] = req.description
    if req.data is not None:
        update["data"] = _coerce_valid_brief(req.data, load_sample_brief())
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")
    update["updated_at"] = datetime.now(timezone.utc)
    result = await proposal_templates_collection.find_one_and_update(
        {"_id": ObjectId(template_id)},
        {"$set": update},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Template not found")
    return serialize_doc(result)


@router.delete("/api/proposal-templates/{template_id}")
async def delete_template(template_id: str, admin: dict = Depends(require_admin)):
    """Delete a template (admin only)."""
    result = await proposal_templates_collection.delete_one({"_id": ObjectId(template_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "Template deleted"}


@router.post("/api/proposals/from-template")
async def create_proposal_from_template(req: ProposalFromTemplateRequest, admin: dict = Depends(require_admin)):
    """Create a new proposal pre-filled from a saved template (Phase 2b)."""
    template = await proposal_templates_collection.find_one({"_id": ObjectId(req.template_id)})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    import copy
    data = _coerce_valid_brief(copy.deepcopy(template.get("data") or {}), load_sample_brief())

    # Overlay optional client/title and a fresh unique slug
    if req.client_name:
        data["client_name"] = req.client_name
    if req.proposal_title:
        data["proposal_title"] = req.proposal_title
    client_slug = (req.client_name or data.get("client_name") or "proposal").lower().replace(" ", "-")
    data["proposal_slug"] = f"{client_slug}-{str(uuid_module.uuid4())[:8]}"

    proposal_doc = {
        "token": generate_secure_token(32),
        "status": "Draft",
        "data": data,
        "created_by": admin.get("email", ""),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "sent_at": None,
        "valid_until_date": None,
        "accepted_by": None,
        "accepted_path": None,
        "accepted_at": None,
        "decline_reason": None,
        "declined_at": None,
        "confirmed_at": None,
        "linked_project_id": None,
        "linked_client_user_id": None,
        "linked_report_token": None,
        "last_client_activity_at": None,
        "source": {"type": "template", "template_id": req.template_id},
    }
    result = await proposals_collection.insert_one(proposal_doc)
    proposal_doc["_id"] = result.inserted_id
    return serialize_doc(proposal_doc)


# ============================================================
# DOCUMENT INGESTION (Phase 2c — upload .docx/.pdf/.txt)
# ============================================================

async def _build_proposal_from_text(source_text: str, use_ai: bool, source_meta: dict, created_by: str):
    """Shared: turn extracted source text into a saved Draft proposal (used by
    document upload AND Google Drive import). Returns serialized proposal + note + warnings."""
    scaffold = load_sample_brief()
    data = scaffold
    assistant_note = "Imported from source document."
    warnings = []

    if use_ai:
        system_prompt = f"""You are an AI proposal assistant for DD Consulting, a digital transformation consultancy.
You will turn the CONTENT of a source document into a complete, on-brand client proposal brief.

## PROPOSAL BRIEF SCHEMA (return EXACTLY this structure, every key present)
{json.dumps(scaffold, indent=2)}

## BRAND & WORDING GUARDRAILS (CRITICAL)
1. AWS Funding: always "positioned to apply for" / "if approved"; never "funded"/"guaranteed".
2. Credentials order: PMP, Prosci/ADKAR, ISO 42001, AWS, HubSpot.
3. Public refs use ddconsult.com.au; ddconsult.tech only for the contact email.
4. Pricing entered ONLY as hours/rate/percentages/tier_fee — never finished totals or bare multipliers.
5. options must contain EXACTLY paths a, b, c. success.gates EXACTLY 4. stage_deliverables keys "1".."4".

## TASK
Read the document content and populate the brief: client_name, proposal_title, understanding (their situation, challenges), vision, options (3 paths), plan (stages/timeline), success, pricing and team where the document implies them. Where the document is silent, write sensible conservative placeholder prose the PM can refine. Keep every field valid.

Return ONLY valid JSON: {{"assistant_message": "<1-2 sentence summary of what you mapped>", "data": {{<full brief>}}}}"""
        user_message = f"SOURCE DOCUMENT CONTENT:\n\n{source_text}\n\nProduce the full proposal brief."
        try:
            text = await _call_ai_for_text(system_prompt, user_message)
            msg, new_data = _parse_ai_brief(text, scaffold)
            if new_data:
                data = _coerce_valid_brief(new_data, scaffold)
                assistant_note = msg or assistant_note
                try:
                    warnings = validate_brief(data)
                except SystemExit as e:
                    warnings.append(f"Validation note: {str(e)}")
            else:
                data = _coerce_valid_brief({"understanding": {"paragraphs": [source_text[:4000]]}}, scaffold)
                assistant_note = "AI mapping unavailable — imported the raw text into the Understanding section; please refine in the builder."
        except Exception as e:
            print(f"[PROPOSALS] import AI mapping failed: {e}")
            data = _coerce_valid_brief({"understanding": {"paragraphs": [source_text[:4000]]}}, scaffold)
            assistant_note = "AI mapping failed — imported the raw text into the Understanding section; please refine in the builder."
    else:
        data = _coerce_valid_brief({"understanding": {"paragraphs": [source_text[:4000]]}}, scaffold)

    client_slug = (data.get("client_name") or "proposal").lower().replace(" ", "-")
    data["proposal_slug"] = f"{client_slug}-{str(uuid_module.uuid4())[:8]}"

    proposal_doc = {
        "token": generate_secure_token(32),
        "status": "Draft",
        "data": data,
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "sent_at": None,
        "valid_until_date": None,
        "accepted_by": None,
        "accepted_path": None,
        "accepted_at": None,
        "decline_reason": None,
        "declined_at": None,
        "confirmed_at": None,
        "linked_project_id": None,
        "linked_client_user_id": None,
        "linked_report_token": None,
        "last_client_activity_at": None,
        "source": source_meta,
    }
    result = await proposals_collection.insert_one(proposal_doc)
    proposal_doc["_id"] = result.inserted_id
    out = serialize_doc(proposal_doc)
    out["assistant_message"] = assistant_note
    out["warnings"] = warnings
    return out


@router.post("/api/proposals/from-document")
async def create_proposal_from_document(
    file: UploadFile = File(...),
    use_ai: bool = Form(True),
    admin: dict = Depends(require_admin),
):
    """Create a new proposal by ingesting an uploaded source document (Phase 2c)."""
    content = await file.read()
    MAX_BYTES = 15 * 1024 * 1024  # 15 MB
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 15 MB).")
    try:
        source_text = extract_text(file.filename or "", content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read the document: {e}")

    return await _build_proposal_from_text(
        source_text, use_ai,
        {"type": "document", "filename": file.filename},
        admin.get("email", ""),
    )


# ============================================================
# GOOGLE DRIVE IMPORT (live fetch via service account)
# ============================================================

@router.get("/api/proposals/drive/docs")
async def list_drive_documents(folder_id: Optional[str] = None, admin: dict = Depends(require_admin)):
    """List Google Docs the configured service account can see (admin)."""
    from services.proposals.drive_import import list_drive_docs
    files, err = await list_drive_docs(folder_id=folder_id)
    if err:
        return {"ok": False, "message": err, "files": []}
    return {"ok": True, "files": files}


@router.post("/api/proposals/from-drive")
async def create_proposal_from_drive(req: ProposalFromDriveRequest, admin: dict = Depends(require_admin)):
    """Create a proposal by importing a Google Doc directly from Drive."""
    from services.proposals.drive_import import fetch_doc_text, extract_doc_id
    text, err = await fetch_doc_text(req.doc_id)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return await _build_proposal_from_text(
        text, req.use_ai,
        {"type": "drive", "doc_id": extract_doc_id(req.doc_id)},
        admin.get("email", ""),
    )




@router.get("/api/proposals/{id}")
async def get_proposal(id: str, admin: dict = Depends(require_admin)):
    """Get full proposal (admin only)"""
    proposal = await proposals_collection.find_one({"_id": ObjectId(id)})
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    return serialize_doc(proposal)


@router.put("/api/proposals/{id}")
async def update_proposal(
    id: str,
    req: ProposalUpdateRequest,
    admin: dict = Depends(require_admin)
):
    """Update proposal data (admin only). Allows editing in Draft/Sent/Viewed; blocks if Confirmed."""
    proposal = await proposals_collection.find_one({"_id": ObjectId(id)})
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if proposal.get("status") == "Confirmed":
        raise HTTPException(status_code=400, detail="Cannot edit a confirmed proposal")
    
    # Parse valid_until_date from the new data if present
    valid_until_date = None
    if req.data.get("valid_until"):
        try:
            valid_until_date = dateutil_parse(req.data["valid_until"], fuzzy=True)
        except Exception:
            pass
    
    update_doc = {
        "data": req.data,
        "updated_at": datetime.now(timezone.utc),
    }
    if valid_until_date:
        update_doc["valid_until_date"] = valid_until_date
    
    await proposals_collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": update_doc}
    )
    
    updated = await proposals_collection.find_one({"_id": ObjectId(id)})
    return serialize_doc(updated)


@router.post("/api/proposals/{id}/ai-draft")
async def ai_draft_proposal(
    id: str,
    req: AIDraftRequest,
    admin: dict = Depends(require_admin)
):
    """THE AI BUILDER. Uses AI to update the proposal brief from PM notes/plain-English instructions."""
    proposal = await proposals_collection.find_one({"_id": ObjectId(id)})
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    # Get current data or use sample as fallback
    current_data = req.current_data or proposal.get("data") or load_sample_brief()
    
    # Build the AI system prompt with brand guardrails
    sample_brief = load_sample_brief()
    
    system_prompt = f"""You are an AI proposal assistant for DD Consulting, a digital transformation consultancy.

Your job is to help PMs draft client proposals by updating a structured proposal brief based on their notes.

## PROPOSAL BRIEF SCHEMA (JSON)

Here is the EXACT structure you must return. Every field is required. Use the sample below as a reference:

{json.dumps(sample_brief, indent=2)}

## BRAND & WORDING GUARDRAILS (CRITICAL)

1. AWS Funding: ALWAYS position as "positioned to apply for" or "if approved". NEVER say "funded" or "guaranteed".
2. Credentials: Order = PMP, Prosci/ADKAR, ISO 42001, AWS, HubSpot.
3. Public refs: Use ddconsult.com.au. Only ddconsult.tech for contact email.
4. Pricing: Enter ONLY hours/rate/percentages/tier_fee — NEVER finished totals or bare multipliers in copy.
5. Options: Must contain EXACTLY paths a, b, c.
6. Success gates: Exactly 4 items in success.gates.
7. Stage deliverables: Keys "1", "2", "3", "4" (strings, not integers).

## YOUR TASK

The PM has provided notes/instructions. You must:
1. MERGE the PM's notes into the current brief, updating ONLY the fields the notes inform.
2. Keep all other fields valid and unchanged.
3. Return the COMPLETE brief as valid JSON (every required key present).
4. Also return a short "assistant_message" string summarizing what you filled/changed and asking the next clarifying question.

## RESPONSE FORMAT (MUST BE VALID JSON)

{{
  "assistant_message": "I've updated the client name to Acme Corp and added three challenges. What are the project phases?",
  "data": {{
    ... (the complete proposal brief, with all fields from the schema)
  }}
}}

CRITICAL: Return ONLY the JSON. No markdown fences, no extra text. The entire response must be parseable as JSON."""
    
    user_message = f"""Current proposal brief:
{json.dumps(current_data, indent=2)}

PM notes/instructions:
{req.message}

Please update the brief according to the notes and return the complete updated brief plus your assistant message."""
    
    # Call AI provider
    try:
        ai_config = await get_ai_config()
        provider = ai_config.get("provider")
        api_key = ai_config.get("api_key")
        
        if not api_key:
            raise HTTPException(status_code=500, detail="No AI provider configured. Ask a super admin to set up AI settings.")
        
        # Graceful degradation: if the AI is momentarily unavailable, do NOT 500.
        # Return the unchanged current data with a friendly retry message.
        def _ai_unavailable():
            return {
                "assistant_message": "The AI assistant is briefly unavailable — your content is unchanged. Please try again in a moment.",
                "data": current_data,
                "warnings": ["AI temporarily unavailable"],
            }

        ai_response_text = None

        if provider == "openai":
            response = await call_openai_api(api_key, system_prompt, user_message, json_mode=True)
            if response.status_code == 200:
                result = response.json()
                ai_response_text = result["choices"][0]["message"]["content"]
            else:
                fallback = await call_emergent_fallback(system_prompt, user_message)
                if fallback:
                    ai_response_text = json.dumps(fallback)
                else:
                    return _ai_unavailable()
        
        elif provider == "gemini":
            response = await call_gemini_api(api_key, system_prompt, user_message, json_mode=True)
            if response.status_code == 200:
                ai_response_text = extract_gemini_text(response.json())
            else:
                fallback = await call_emergent_fallback(system_prompt, user_message)
                if fallback:
                    ai_response_text = json.dumps(fallback)
                else:
                    return _ai_unavailable()
        
        else:  # emergent
            fallback = await call_emergent_fallback(system_prompt, user_message)
            if fallback:
                ai_response_text = json.dumps(fallback)
            else:
                return _ai_unavailable()
        
        if not ai_response_text:
            return _ai_unavailable()
        
        # Parse the AI response (strip code fences if present)
        cleaned = re.sub(r'^```(?:json)?\s*', '', ai_response_text.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned)
        
        try:
            ai_parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback: return current data with error message
            return {
                "assistant_message": "I couldn't parse the response properly. Please try rephrasing your request.",
                "data": current_data,
                "warnings": ["AI response parsing failed"]
            }
        
        assistant_message = ai_parsed.get("assistant_message", "Updated successfully")
        new_data = ai_parsed.get("data", current_data)
        
        # Repair any structural issues so the brief is always schema-valid.
        new_data = _coerce_valid_brief(new_data, sample_brief)
        
        # Validate the new brief
        warnings = []
        try:
            warnings = validate_brief(new_data)
        except SystemExit as e:
            # Hard validation error from the v4 validator (rare after coercion)
            warnings.append(f"Validation error: {str(e)}")
            assistant_message += f" (Warning: {str(e)})"
        
        # Persist the new data
        await proposals_collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"data": new_data, "updated_at": datetime.now(timezone.utc)}}
        )
        
        return {
            "assistant_message": assistant_message,
            "data": new_data,
            "warnings": warnings
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI draft failed: {str(e)}")


@router.post("/api/proposals/{id}/preview")
async def preview_proposal(id: str, admin: dict = Depends(require_admin)):
    """Generate HTML preview (admin only)"""
    proposal = await proposals_collection.find_one({"_id": ObjectId(id)})
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    data = proposal.get("data", {})
    
    try:
        html, warnings = render_proposal_html(data, tracking_url="", noindex=True)
        return HTMLResponse(content=html)
    except SystemExit as e:
        raise HTTPException(status_code=400, detail=f"Proposal validation failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rendering failed: {str(e)}")


@router.post("/api/proposals/{id}/send")
async def send_proposal(id: str, request: Request, admin: dict = Depends(require_admin)):
    """Send proposal to client (mark as Sent, generate public link, optionally email)"""
    proposal = await proposals_collection.find_one({"_id": ObjectId(id)})
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    # Build secure public link
    base_url = _public_base_url(request)
    token = proposal.get("token")
    proposal_link = f"{base_url}/proposal/{token}"
    
    # Mark as Sent
    await proposals_collection.update_one(
        {"_id": ObjectId(id)},
        {
            "$set": {
                "status": "Sent",
                "sent_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )
    
    # Send email if contact_email present (email is best-effort; link always returned)
    data = proposal.get("data", {})
    contact_email = data.get("contact_email")
    email_sent = False
    email_message = "No client contact email on the proposal — share the link manually."

    if contact_email:
        client_name = data.get("client_name", "Client")
        title = data.get("proposal_title", "Proposal")
        email_sent, email_message = await send_proposal_link_email(contact_email, proposal_link, client_name, title)

    return {
        "proposal_link": proposal_link,
        "email_sent": email_sent,
        "email_message": email_message,
        "recipient": contact_email or None,
    }


@router.post("/api/proposals/{id}/confirm")
async def confirm_proposal(id: str, request: Request, admin: dict = Depends(require_admin)):
    """AUTO-PROVISION: create project, client user, and report link (admin only, after client accepts)"""
    proposal = await proposals_collection.find_one({"_id": ObjectId(id)})
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if proposal.get("status") != "Accepted":
        raise HTTPException(status_code=400, detail="Proposal must be accepted before confirmation")
    
    data = proposal.get("data", {})
    contact_email = data.get("contact_email")
    
    if not contact_email:
        raise HTTPException(status_code=400, detail="Client contact email required to provision access")
    
    client_name = data.get("client_name", "Client")
    proposal_title = data.get("proposal_title", "Project")
    accepted_path = proposal.get("accepted_path", "a")
    
    # Find the accepted option
    options = data.get("options", [])
    accepted_option = next((o for o in options if o.get("path") == accepted_path), None)
    
    if not accepted_option:
        raise HTTPException(status_code=500, detail="Accepted option not found in proposal data")
    
    # (a) Create Project
    today = datetime.now(timezone.utc)
    
    # Parse duration from accepted path
    duration_label = None
    if accepted_path == "a":
        duration_label = data.get("pricing_model", {}).get("path_a", {}).get("duration_label", "8 weeks")
    elif accepted_path == "b":
        duration_label = data.get("pricing_model", {}).get("path_b", {}).get("duration_label", "8 weeks")
    elif accepted_path == "c":
        duration_label = data.get("pricing_model", {}).get("path_c", {}).get("duration_label", "12 weeks")
    
    # Extract integer weeks (simple parse)
    import re
    weeks_match = re.search(r'(\d+)\s*week', duration_label or "8 weeks", re.IGNORECASE)
    weeks = int(weeks_match.group(1)) if weeks_match else 8
    
    end_date = today + timedelta(weeks=weeks)
    
    # Build phases from the accepted option's stages using the canonical
    # Transformation Operating System (TOS) stage names (brand-fixed in the v4
    # generator). stage_deliverables[str(n)] is a LIST of deliverable strings —
    # we don't derive the phase NAME from it.
    stages_in_option = accepted_option.get("stages", [])

    TOS_STAGE_NAMES = {
        1: "Align & Audit",
        2: "Architect & Select",
        3: "Engineer & Operationalize",
        4: "Adopt & Sustain",
    }

    phases = []
    if stages_in_option:
        phase_duration = timedelta(weeks=weeks / len(stages_in_option))
        phase_start = today

        for stage_num in stages_in_option:
            try:
                stage_int = int(stage_num)
            except (ValueError, TypeError):
                stage_int = None
            phase_name = TOS_STAGE_NAMES.get(stage_int, f"Stage {stage_num}")

            phase_end = phase_start + phase_duration
            phases.append({
                "id": str(uuid_module.uuid4()),
                "name": phase_name,
                "start_date": phase_start,
                "end_date": phase_end,
            })
            phase_start = phase_end
    
    # Budgeted hours (path b/c have hours)
    budgeted_hours = None
    if accepted_path in ("b", "c"):
        pricing = data.get("pricing_model", {}).get(f"path_{accepted_path}", {})
        budgeted_hours = pricing.get("hours")
    
    project_doc = {
        "name": proposal_title or f"{client_name} — {accepted_option.get('name', 'Project')}",
        "client_name": client_name,
        "status": "Active",
        "start_date": today,
        "end_date": end_date,
        "phases": phases,
        "budgeted_hours": budgeted_hours,
        "main_contact_name": client_name,
        "main_contact_email": contact_email,
        "created_at": today,
    }
    
    project_result = await projects_collection.insert_one(project_doc)
    project_id = str(project_result.inserted_id)
    
    # (b) Create or reuse client user
    existing_client = await users_collection.find_one({"email": contact_email})
    
    if existing_client:
        # Append new project id to allowed_project_ids
        current_pids = existing_client.get("allowed_project_ids", [])
        if project_id not in current_pids:
            current_pids.append(project_id)
            await users_collection.update_one(
                {"_id": existing_client["_id"]},
                {"$set": {"allowed_project_ids": current_pids}}
            )
        client_user_id = str(existing_client["_id"])
    else:
        # Create new client user
        client_user_doc = {
            "email": contact_email,
            "password_hash": get_password_hash(str(uuid_module.uuid4())),  # random password
            "role": "client",
            "company_name": client_name,
            "allowed_project_ids": [project_id],
            "must_change_password": False,
        }
        client_result = await users_collection.insert_one(client_user_doc)
        client_user_id = str(client_result.inserted_id)
    
    # (c) Create magic report link
    report_token = generate_secure_token(64)
    verification_code = generate_verification_code()
    
    report_link_doc = {
        "token": report_token,
        "project_id": project_id,
        "report_type": "project_status",
        "report_period": "whole_project",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "recipient_email": contact_email,
        "verification_code": verification_code,
        "is_active": True,
        "view_count": 0,
    }
    
    await report_links_collection.insert_one(report_link_doc)
    
    base_url = _public_base_url(request)
    report_link = f"{base_url}/portal/{report_token}"
    
    # Send emails (best-effort — report link always returned regardless)
    magic_link_sent = False
    email_message = "Email not configured — share the report link manually."
    try:
        from routes.client_portal import send_magic_link_email, send_verification_email
        magic_link_sent, email_message = await send_magic_link_email(contact_email, report_link, project_doc["name"])
        # Also send the verification code (best-effort, status tracked by magic-link send)
        await send_verification_email(contact_email, verification_code, project_doc["name"])
    except Exception as e:
        print(f"[PROPOSALS] Email send failed: {e}")
        email_message = f"Email not sent: {e}"

    # (d) Update proposal
    await proposals_collection.update_one(
        {"_id": ObjectId(id)},
        {
            "$set": {
                "status": "Confirmed",
                "confirmed_at": datetime.now(timezone.utc),
                "linked_project_id": project_id,
                "linked_client_user_id": client_user_id,
                "linked_report_token": report_token,
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )
    
    return {
        "project_id": project_id,
        "client_user_id": client_user_id,
        "report_link": report_link,
        "magic_link_sent": magic_link_sent,
        "email_message": email_message,
    }


@router.delete("/api/proposals/{id}")
async def delete_proposal(id: str, admin: dict = Depends(require_admin)):
    """Delete a Draft proposal (admin only)"""
    proposal = await proposals_collection.find_one({"_id": ObjectId(id)})
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if proposal.get("status") != "Draft":
        raise HTTPException(status_code=400, detail="Can only delete Draft proposals")
    
    await proposals_collection.delete_one({"_id": ObjectId(id)})
    
    return {"message": "Proposal deleted"}


@router.get("/api/proposals/{id}/events")
async def get_proposal_events(id: str, admin: dict = Depends(require_admin)):
    """Get engagement events for a proposal (admin only)"""
    proposal = await proposals_collection.find_one({"_id": ObjectId(id)})
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    # Fetch events
    cursor = proposal_events_collection.find({"proposal_id": str(proposal["_id"])}).sort("created_at", -1)
    events = await cursor.to_list(length=1000)
    
    # Build rollup summary
    opened = any(e.get("type") == "opened" for e in events)
    sections_viewed = list(set(e.get("payload", {}).get("section") for e in events if e.get("type") == "section_view" and e.get("payload", {}).get("section")))
    interested_path = proposal.get("interested_path")
    accept_clicked = any(e.get("type") == "accept_clicked" for e in events)
    accepted = proposal.get("status") == "Accepted"
    
    return {
        "events": serialize_doc(events),
        "summary": {
            "opened": opened,
            "sections_viewed": sections_viewed,
            "interested_path": interested_path,
            "accept_clicked": accept_clicked,
            "accepted": accepted,
        }
    }


# ============================================================
# REMINDERS (Phase 3) — "viewed but not accepted after N days"
# ============================================================

async def run_proposal_reminders(days: int = 3, request_base_url: Optional[str] = None) -> dict:
    """Find Sent/Viewed proposals with client activity older than `days` that
    haven't been Accepted/Confirmed/Declined/Expired and haven't already been
    reminded, and email the client contact a gentle nudge. Best-effort.

    Returns a summary dict. Safe to run repeatedly (sends at most one reminder
    per proposal via reminder_sent_at).
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    sent_count = 0
    checked = 0

    # Candidates: status Sent or Viewed, no reminder yet.
    cursor = proposals_collection.find({
        "status": {"$in": ["Sent", "Viewed"]},
        "reminder_sent_at": {"$in": [None, ""]},
    })
    candidates = await cursor.to_list(length=500)
    for p in candidates:
        checked += 1
        # Use last client activity, else sent_at, as the "since" marker.
        marker = p.get("last_client_activity_at") or p.get("sent_at")
        if not marker:
            continue
        try:
            marker_dt = marker if isinstance(marker, datetime) else dateutil_parse(str(marker))
            if marker_dt.tzinfo is None:
                marker_dt = marker_dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if marker_dt > cutoff:
            continue  # too recent

        data = p.get("data", {}) or {}
        contact_email = data.get("contact_email")
        if not contact_email:
            continue

        # Build the proposal link (reuse public base if available).
        base = (request_base_url or "").rstrip("/")
        link = f"{base}/proposal/{p.get('token')}" if base else None

        from services.email_config import send_email, get_email_settings_block
        from services.email_templates import render_email, DEFAULT_TEMPLATES
        email_block = await get_email_settings_block()
        # Reuse the proposal_link template but with a reminder-flavoured subject fallback.
        client_name = data.get("client_name", "there")
        title = data.get("proposal_title", "your proposal")
        ctx = {"client_name": client_name, "proposal_title": title, "link": link or ""}
        subject, html = render_email(email_block, "proposal_link", ctx)
        subject = f"Reminder: {subject}"

        sent, _msg = await send_email(
            contact_email, subject, html,
            email_type="proposal_reminder", related_id=str(p["_id"]), related_label=title,
        )
        # Mark as reminded regardless of send outcome, so we don't spam on failures.
        await proposals_collection.update_one(
            {"_id": p["_id"]},
            {"$set": {"reminder_sent_at": now.isoformat()}},
        )
        if sent:
            sent_count += 1

    return {"checked": checked, "reminders_sent": sent_count, "days": days}


@router.post("/api/proposals/reminders/run")
async def trigger_proposal_reminders(request: Request, days: int = 3, admin: dict = Depends(require_admin)):
    """Manually trigger the 'viewed but not accepted' reminder sweep (admin)."""
    base = _public_base_url(request)
    result = await run_proposal_reminders(days=days, request_base_url=base)
    return result



# ============================================================
# PUBLIC ENDPOINTS (NO AUTH)
# ============================================================

@router.get("/api/proposals/public/{token}")
async def get_public_proposal(token: str, request: Request):
    """Public proposal view (no auth). Returns rendered HTML."""
    proposal = await proposals_collection.find_one({"token": token})
    
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    # Check expiry
    valid_until_date = proposal.get("valid_until_date")
    if valid_until_date:
        if isinstance(valid_until_date, str):
            valid_until_date = dateutil_parse(valid_until_date)
        
        if datetime.now(timezone.utc) > valid_until_date.replace(tzinfo=timezone.utc):
            await proposals_collection.update_one(
                {"_id": proposal["_id"]},
                {"$set": {"status": "Expired"}}
            )
            return JSONResponse(status_code=410, content={"detail": "This proposal has expired."})
    
    # Don't leak drafts
    if proposal.get("status") == "Draft":
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    # On first view, mark as Viewed
    if proposal.get("status") == "Sent":
        await proposals_collection.update_one(
            {"_id": proposal["_id"]},
            {
                "$set": {
                    "status": "Viewed",
                    "last_client_activity_at": datetime.now(timezone.utc),
                }
            }
        )
    
    # Render HTML
    data = proposal.get("data", {})
    base_url = _public_base_url(request)
    tracking_url = f"{base_url}/api/proposals/public/{token}/track"
    
    try:
        html, warnings = render_proposal_html(data, tracking_url=tracking_url, noindex=True)
        return HTMLResponse(content=html)
    except SystemExit as e:
        raise HTTPException(status_code=500, detail=f"Rendering failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rendering failed: {str(e)}")


@router.post("/api/proposals/public/{token}/track")
async def track_proposal_event(token: str, event: dict):
    """Public tracking endpoint (no auth). Accepts engagement events from the rendered page."""
    proposal = await proposals_collection.find_one({"token": token})
    
    if not proposal:
        # Don't 404 on tracking — fail silently
        return {"ok": True}
    
    try:
        # Insert event
        event_doc = {
            "proposal_id": str(proposal["_id"]),
            "token": token,
            "type": event.get("type", "unknown"),
            "payload": event,
            "created_at": datetime.now(timezone.utc),
        }
        
        await proposal_events_collection.insert_one(event_doc)
        
        # Update last_client_activity_at
        update_fields = {"last_client_activity_at": datetime.now(timezone.utc)}
        
        # Special cases
        event_type = event.get("type")
        
        if event_type == "option_interest":
            update_fields["interested_path"] = event.get("path")
        
        elif event_type == "accepted":
            update_fields["status"] = "Accepted"
            update_fields["accepted_by"] = event.get("accepted_by", "")
            update_fields["accepted_path"] = event.get("accepted_path", "")
            update_fields["accepted_at"] = datetime.now(timezone.utc)
            
            # Create admin notification (best-effort)
            try:
                admins = await users_collection.find({"role": {"$in": ["admin", "super_admin"]}}).to_list(100)
                for admin_user in admins:
                    notification = {
                        "user_id": str(admin_user["_id"]),
                        "type": "proposal_accepted",
                        "title": "Proposal Accepted",
                        "message": f"Proposal for {proposal.get('data', {}).get('client_name', 'Client')} has been accepted (Path {event.get('accepted_path', '?').upper()}).",
                        "related_id": str(proposal["_id"]),
                        "priority": "high",
                        "read": False,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                    await notifications_collection.insert_one(notification)
            except Exception as e:
                print(f"[PROPOSALS] Notification failed: {e}")
        
        await proposals_collection.update_one(
            {"_id": proposal["_id"]},
            {"$set": update_fields}
        )
        
        return {"ok": True}
    
    except Exception as e:
        # Never 500 on tracking — fail silently
        print(f"[PROPOSALS] Tracking error: {e}")
        return {"ok": True}
