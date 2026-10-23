"""
Integration routes — HubSpot bi-directional sync + Agent API key management.

MULTI-TENANT NOTE (Step 10 of MULTITENANT_PLAN.md):
    Every read/write on integration_settings_collection is automatically scoped
    to the CURRENT REQUEST'S TENANT via LazyCollection (see database.py).
    
    The `ORG_ID = "default"` filter below is now a stable primary-key within
    each tenant's isolated database — NOT a cross-tenant discriminator. Each
    tenant has exactly one `integration_settings` document with `org_id="default"`
    in their own DB. HubSpot tokens, portal IDs, MCP agent keys, etc. are all
    per-tenant with zero code changes needed here.

Endpoints:
  GET  /api/integrations/settings              - fetch current tenant config (super_admin)
  PUT  /api/integrations/settings              - save current tenant config (super_admin)
  POST /api/integrations/hubspot/test          - test HubSpot connection (super_admin)
  POST /api/integrations/hubspot/webhook       - receive HubSpot webhook events (public, sig-validated)
  POST /api/integrations/agent-api/regenerate  - generate/rotate agent API key (super_admin)
  GET  /api/integrations/sync-logs             - last 50 sync events (super_admin)
"""
import secrets
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth.dependencies import get_current_user
from database import (
    integration_settings_collection,
    integration_sync_logs_collection,
    projects_collection,
)
from services.hubspot import (
    test_hubspot_connection,
    get_deal,
    get_deal_company_name,
    get_deal_primary_contact,
    map_deal_to_project,
    append_sync_log,
    verify_hubspot_signature_v3,
)

logger = logging.getLogger(__name__)
router = APIRouter()

ORG_ID = "default"


# ─── helpers ──────────────────────────────────────────────────────────────────

def _require_super_admin(current_user: dict):
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")


async def _get_settings() -> dict:
    doc = await integration_settings_collection.find_one({"org_id": ORG_ID})
    if not doc:
        return {
            "org_id": ORG_ID,
            "hubspot": {
                "enabled": False,
                "private_app_token": "",
                "portal_id": "",
                "trigger_stage": "closedwon",
                "sync_status_updates": True,
                "default_project_status": "Pipeline",
            },
            "agent_api": {
                "enabled": False,
                "api_key": "",
            },
        }
    doc.pop("_id", None)
    return doc


# ─── Schemas ──────────────────────────────────────────────────────────────────

class HubSpotConfig(BaseModel):
    enabled: bool = False
    private_app_token: str = ""
    portal_id: str = ""
    trigger_stage: str = "closedwon"
    sync_status_updates: bool = True
    default_project_status: str = "Pipeline"


class AgentApiConfig(BaseModel):
    enabled: bool = False


class GoogleDriveConfig(BaseModel):
    enabled: bool = False
    # Service-account JSON (or OAuth client) — stored encrypted-at-rest by Mongo;
    # masked on read. Live Drive fetch is wired when credentials are present.
    service_account_json: str = ""
    # Optional: a default Drive folder ID proposals can be imported from.
    default_folder_id: str = ""


class EmailConfig(BaseModel):
    enabled: bool = False
    api_key: str = ""           # Resend API key — write-once, masked on read
    from_email: str = ""        # verified "from" sender address
    reply_to: str = ""          # optional reply-to


class IntegrationSettingsPayload(BaseModel):
    hubspot: Optional[HubSpotConfig] = None
    agent_api: Optional[AgentApiConfig] = None
    google_drive: Optional[GoogleDriveConfig] = None
    email: Optional[EmailConfig] = None


# ─── GET settings ─────────────────────────────────────────────────────────────

@router.get("/api/integrations/settings")
async def get_integration_settings(current_user: dict = Depends(get_current_user)):
    _require_super_admin(current_user)
    settings = await _get_settings()
    # Ensure both sections exist with defaults
    if "hubspot" not in settings:
        settings["hubspot"] = {
            "enabled": False,
            "private_app_token": "",
            "portal_id": "",
            "trigger_stage": "closedwon",
            "sync_status_updates": True,
            "default_project_status": "Pipeline",
        }
    if "agent_api" not in settings:
        settings["agent_api"] = {"enabled": False, "api_key": ""}
    if "google_drive" not in settings:
        settings["google_drive"] = {"enabled": False, "service_account_json": "", "default_folder_id": ""}
    if "email" not in settings:
        settings["email"] = {"enabled": False, "api_key": "", "from_email": "", "reply_to": ""}

    # Mask the token for display
    hs = settings.get("hubspot", {})
    token = hs.get("private_app_token", "") or ""
    if isinstance(token, str) and len(token) > 10:
        settings["hubspot"]["private_app_token_masked"] = token[:8] + "•" * (len(token) - 8)
    else:
        settings["hubspot"]["private_app_token_masked"] = ""
    # Don't expose the raw token — return boolean
    settings["hubspot"]["private_app_token"] = bool(token)

    agent = settings.get("agent_api", {})
    api_key = agent.get("api_key", "") or ""
    if isinstance(api_key, str) and len(api_key) > 8:
        settings["agent_api"]["api_key_masked"] = api_key[:8] + "•" * (len(api_key) - 8)
    else:
        settings["agent_api"]["api_key_masked"] = ""
    settings["agent_api"]["api_key"] = bool(api_key)

    # Google Drive: mask the service-account secret, expose only a boolean.
    gd = settings.get("google_drive", {})
    sa = gd.get("service_account_json", "") or ""
    settings["google_drive"]["has_credentials"] = bool(sa)
    settings["google_drive"]["service_account_json"] = ""  # never return the raw secret

    # Email (Resend): mask the API key, expose only a boolean + masked hint.
    em = settings.get("email", {})
    ekey = em.get("api_key", "") or ""
    settings["email"]["has_api_key"] = bool(ekey)
    if isinstance(ekey, str) and len(ekey) > 8:
        settings["email"]["api_key_masked"] = ekey[:5] + "•" * (len(ekey) - 5)
    else:
        settings["email"]["api_key_masked"] = ""
    settings["email"]["api_key"] = ""  # never return the raw key

    return settings


# ─── PUT settings ─────────────────────────────────────────────────────────────

@router.put("/api/integrations/settings")
async def update_integration_settings(
    payload: IntegrationSettingsPayload,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user)
    existing = await integration_settings_collection.find_one({"org_id": ORG_ID})
    update_doc = {"org_id": ORG_ID, "updated_at": datetime.now(timezone.utc)}

    if payload.hubspot:
        hs_data = payload.hubspot.model_dump()
        # If token is empty string, preserve the existing token
        if existing and not hs_data["private_app_token"]:
            hs_data["private_app_token"] = existing.get("hubspot", {}).get("private_app_token", "")
        update_doc["hubspot"] = hs_data

    if payload.agent_api:
        if existing:
            existing_agent = existing.get("agent_api", {})
            update_doc["agent_api"] = {
                **existing_agent,
                "enabled": payload.agent_api.enabled,
            }
        else:
            update_doc["agent_api"] = {"enabled": payload.agent_api.enabled, "api_key": ""}

    if payload.google_drive:
        gd_data = payload.google_drive.model_dump()
        # Preserve the existing secret when an empty string is submitted.
        if existing and not gd_data.get("service_account_json"):
            gd_data["service_account_json"] = existing.get("google_drive", {}).get("service_account_json", "")
        update_doc["google_drive"] = gd_data

    if payload.email:
        em_data = payload.email.model_dump()
        # Preserve the existing API key when an empty string is submitted.
        if existing and not em_data.get("api_key"):
            em_data["api_key"] = existing.get("email", {}).get("api_key", "")
        update_doc["email"] = em_data

    await integration_settings_collection.update_one(
        {"org_id": ORG_ID},
        {"$set": update_doc},
        upsert=True,
    )
    return {"ok": True, "message": "Settings saved"}


# ─── Test HubSpot connection ───────────────────────────────────────────────────

class TestConnectionPayload(BaseModel):
    token: Optional[str] = None   # if provided, test THIS token (not the saved one)


@router.post("/api/integrations/hubspot/test")
async def test_hubspot(
    payload: TestConnectionPayload,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user)

    if payload.token:
        token = payload.token
    else:
        settings = await _get_settings()
        token = settings.get("hubspot", {}).get("private_app_token", "")

    if not token:
        raise HTTPException(status_code=400, detail="No HubSpot token provided")

    result = await test_hubspot_connection(token)
    await append_sync_log(
        direction="outbound",
        event_type="test_connection",
        status="success" if result["ok"] else "error",
        detail=result["message"],
    )
    return result


# ─── Test Email (Resend) ───────────────────────────────────────────────────────

class TestEmailPayload(BaseModel):
    to: Optional[str] = None  # if provided, send the test to this address


@router.post("/api/integrations/email/test")
async def test_email(payload: TestEmailPayload, current_user: dict = Depends(get_current_user)):
    """Send a test email using the currently-saved Email (Resend) config.

    Surfaces Resend's typical responses (e.g. 'verify your domain' / 'can only
    send to your own address until verified') so the admin knows the real state.
    """
    _require_super_admin(current_user)
    from services.email_config import resolve_email_config, send_email

    cfg = await resolve_email_config()
    if not cfg:
        return {"ok": False, "message": "Email is not configured or is disabled. Save a Resend API key and 'from' address, then try again."}

    to_addr = (payload.to or current_user.get("email") or "").strip()
    if not to_addr:
        return {"ok": False, "message": "No recipient address available for the test."}

    html = (
        "<div style=\"font-family:Arial,sans-serif;max-width:600px;margin:0 auto;\">"
        "<h2 style=\"color:#1570EF;\">DD Planner — test email</h2>"
        "<p>This is a test email confirming your Resend configuration works.</p>"
        f"<p style=\"color:#666;font-size:13px;\">Sent from: {cfg['from_email']}</p>"
        "<hr style=\"border:none;border-top:1px solid #e5e7eb;margin:24px 0;\"/>"
        "<p style=\"color:#999;font-size:12px;\">DD Consulting — Project Management Platform</p>"
        "</div>"
    )
    sent, message = await send_email(to_addr, "DD Planner — test email", html)
    return {"ok": sent, "message": (f"Test email sent to {to_addr}." if sent else message)}



# ─── Generate / rotate agent API key ──────────────────────────────────────────

@router.post("/api/integrations/agent-api/regenerate")
async def regenerate_agent_key(current_user: dict = Depends(get_current_user)):
    _require_super_admin(current_user)
    new_key = "dda_" + secrets.token_hex(24)  # dda = dd-agent
    await integration_settings_collection.update_one(
        {"org_id": ORG_ID},
        {"$set": {
            "agent_api.api_key": new_key,
            "agent_api.enabled": True,
            "agent_api.created_at": datetime.now(timezone.utc),
            "agent_api.last_used_at": None,
        }},
        upsert=True,
    )
    return {"ok": True, "api_key": new_key, "message": "New key generated — save it now, it won't be shown again in full"}


# ─── Sync logs ────────────────────────────────────────────────────────────────

@router.get("/api/integrations/sync-logs")
async def get_sync_logs(
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user)
    cursor = integration_sync_logs_collection.find(
        {},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit)
    logs = await cursor.to_list(length=limit)
    for log in logs:
        if "created_at" in log and hasattr(log["created_at"], "isoformat"):
            log["created_at"] = log["created_at"].isoformat()
    return logs


# ─── HubSpot Webhook receiver ─────────────────────────────────────────────────

@router.post("/api/integrations/hubspot/webhook")
async def receive_hubspot_webhook(request: Request):
    """
    Receives real-time HubSpot deal events.
    When a deal's stage changes to the configured trigger_stage → create/update project.
    """
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")

    settings = await _get_settings()
    hs_config = settings.get("hubspot", {})

    if not hs_config.get("enabled"):
        logger.info("[HubSpot Webhook] Integration disabled — ignoring")
        return {"ok": True, "skipped": True}

    token = hs_config.get("private_app_token", "")
    if not token:
        logger.warning("[HubSpot Webhook] No token configured")
        return {"ok": False, "detail": "No token configured"}

    # Parse body
    try:
        events = body_str if isinstance(body_str, list) else __import__("json").loads(body_str)
        if not isinstance(events, list):
            events = [events]
    except Exception as e:
        logger.warning(f"[HubSpot Webhook] Failed to parse body: {e}")
        return {"ok": False, "detail": "Bad request body"}

    trigger_stage = hs_config.get("trigger_stage", "closedwon").lower().replace(" ", "")
    processed = 0

    for event in events:
        event_type = event.get("eventType") or event.get("subscriptionType", "")
        property_name = event.get("propertyName", "")
        property_value = (event.get("propertyValue") or "").lower().replace(" ", "")
        deal_id = str(event.get("objectId", ""))

        logger.info(f"[HubSpot Webhook] event={event_type} prop={property_name} val={property_value} deal={deal_id}")

        # Only act on dealstage changes to the trigger stage
        stage_match = (
            property_name == "dealstage" and property_value == trigger_stage
        )
        if not stage_match:
            continue

        # Fetch full deal
        try:
            deal_data = await get_deal(deal_id, token)
        except Exception as e:
            msg = f"Failed to fetch deal {deal_id}: {e}"
            logger.warning(f"[HubSpot] {msg}")
            await append_sync_log("inbound", "deal_to_project", "error", msg, deal_id)
            continue

        # Check if project with this deal_id already exists
        existing = await projects_collection.find_one({"hubspot_deal_id": deal_id})
        if existing:
            await append_sync_log(
                "inbound", "deal_to_project", "skipped",
                f"Project already exists for deal {deal_id} → project {existing.get('name')}",
                deal_id,
            )
            processed += 1
            continue

        # Resolve company + contact
        company_name = await get_deal_company_name(deal_data, token)
        contact = await get_deal_primary_contact(deal_data, token)

        # Map deal to project
        project_data = map_deal_to_project(deal_data, company_name, contact, hs_config)

        # Create project in DD Planner
        import uuid
        from datetime import timedelta

        try:
            start_dt = datetime.strptime(project_data["start_date"], "%Y-%m-%d")
            end_dt = datetime.strptime(project_data["end_date"], "%Y-%m-%d")
        except Exception:
            start_dt = datetime.now(timezone.utc).replace(tzinfo=None)
            end_dt = start_dt + __import__("datetime").timedelta(days=30)

        default_phase = {
            "id": str(uuid.uuid4()),
            "name": "Execution Phase",
            "start_date": project_data["start_date"],
            "end_date": project_data["end_date"],
            "status": "Active",
        }
        mongo_doc = {
            **project_data,
            "start_date": start_dt,
            "end_date": end_dt,
            "phases": [default_phase],
            "wbs_tasks": [],
            "risks": [],
            "status_updates": [],
            "created_at": datetime.now(timezone.utc),
            "source": "hubspot",
        }
        mongo_doc.pop("start_date", None)
        mongo_doc.pop("end_date", None)
        mongo_doc["start_date"] = start_dt
        mongo_doc["end_date"] = end_dt

        result = await projects_collection.insert_one(mongo_doc)
        new_project_id = str(result.inserted_id)

        msg = f"Created project '{project_data['name']}' (id={new_project_id}) from HubSpot deal {deal_id}"
        logger.info(f"[HubSpot] {msg}")
        await append_sync_log("inbound", "deal_to_project", "success", msg, deal_id)
        processed += 1

    return {"ok": True, "processed": processed}
