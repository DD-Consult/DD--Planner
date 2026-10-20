"""DD Planner Secure AI-Guided Proposal Module (Enhancement #5)

This module provides a full proposal lifecycle: AI-guided drafting, admin editing,
secure public sharing, client engagement tracking, and auto-provisioning of projects
and client access upon acceptance.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
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
    projects_collection,
    users_collection,
    report_links_collection,
    notifications_collection,
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
    """Send proposal link notification email"""
    if not RESEND_API_KEY or not resend.api_key:
        print(f"[EMAIL] Resend not configured. Proposal link: {link}")
        return False
    
    try:
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #1B2A47;">Your Proposal from DD Consulting</h2>
            <p>Hi {client_name},</p>
            <p>Your proposal <strong>{title}</strong> is ready to view.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{link}" style="background: #1570EF; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: 600;">
                    View Proposal
                </a>
            </div>
            <p style="background: #EFF6FF; padding: 15px; border-left: 4px solid #1570EF; border-radius: 4px; font-size: 14px;">
                <strong>🔒 Security:</strong> This is a secure, unique link for your review.
            </p>
            <p style="color: #666; font-size: 14px;">You can also copy this link:</p>
            <p style="background: #f3f4f6; padding: 10px; border-radius: 4px; word-break: break-all; font-size: 12px; font-family: monospace;">
                {link}
            </p>
            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;" />
            <p style="color: #999; font-size: 12px;">DD Consulting</p>
        </div>
        """
        
        params = {
            "from": SENDER_EMAIL,
            "to": [email],
            "subject": f"Proposal: {title}",
            "html": html_content,
        }
        
        response = resend.Emails.send(params)
        print(f"[EMAIL] Proposal link sent to {email}: {response}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send proposal link: {e}")
        return False


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
        
        ai_response_text = None
        
        if provider == "openai":
            response = await call_openai_api(api_key, system_prompt, user_message, json_mode=True)
            if response.status_code == 200:
                result = response.json()
                ai_response_text = result["choices"][0]["message"]["content"]
            else:
                # Fallback to emergent
                fallback = await call_emergent_fallback(system_prompt, user_message)
                if fallback:
                    ai_response_text = json.dumps(fallback)
                else:
                    raise HTTPException(status_code=500, detail="AI service failed")
        
        elif provider == "gemini":
            response = await call_gemini_api(api_key, system_prompt, user_message, json_mode=True)
            if response.status_code == 200:
                ai_response_text = extract_gemini_text(response.json())
            else:
                fallback = await call_emergent_fallback(system_prompt, user_message)
                if fallback:
                    ai_response_text = json.dumps(fallback)
                else:
                    raise HTTPException(status_code=500, detail="AI service failed")
        
        else:  # emergent
            fallback = await call_emergent_fallback(system_prompt, user_message)
            if fallback:
                ai_response_text = json.dumps(fallback)
            else:
                raise HTTPException(status_code=500, detail="AI service unavailable")
        
        if not ai_response_text:
            raise HTTPException(status_code=500, detail="No AI response received")
        
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
        
        # Validate the new brief
        warnings = []
        try:
            warnings = validate_brief(new_data)
        except SystemExit as e:
            # Hard validation error from the v4 validator
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
    
    # Send email if contact_email present and Resend configured
    data = proposal.get("data", {})
    contact_email = data.get("contact_email")
    email_sent = False
    
    if contact_email and RESEND_API_KEY:
        client_name = data.get("client_name", "Client")
        title = data.get("proposal_title", "Proposal")
        email_sent = await send_proposal_link_email(contact_email, proposal_link, client_name, title)
    
    return {
        "proposal_link": proposal_link,
        "email_sent": email_sent
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
    
    # Send emails (best-effort)
    magic_link_sent = False
    if RESEND_API_KEY:
        try:
            from routes.client_portal import send_magic_link_email, send_verification_email
            await send_magic_link_email(contact_email, report_link, project_doc["name"])
            await send_verification_email(contact_email, verification_code, project_doc["name"])
            magic_link_sent = True
        except Exception as e:
            print(f"[PROPOSALS] Email send failed: {e}")
    
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
