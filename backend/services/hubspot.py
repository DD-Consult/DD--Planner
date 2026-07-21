"""
HubSpot service — wraps the HubSpot Private App API for DD Planner.
All credentials come from the integration_settings collection (DB-stored, not .env).
"""
import httpx
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

HUBSPOT_API_BASE = "https://api.hubapi.com"


# ─── Low-level API helpers ────────────────────────────────────────────────────

async def _hs_get(path: str, token: str, params: dict = None) -> dict:
    """GET from HubSpot API, return parsed JSON or raise on error."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{HUBSPOT_API_BASE}{path}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            params=params or {},
        )
        r.raise_for_status()
        return r.json()


async def _hs_post(path: str, token: str, body: dict) -> dict:
    """POST to HubSpot API, return parsed JSON or raise on error."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{HUBSPOT_API_BASE}{path}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
        )
        r.raise_for_status()
        return r.json()


# ─── Settings helpers ─────────────────────────────────────────────────────────

async def get_hubspot_config() -> Optional[dict]:
    """Return the HubSpot section of the integration settings, or None if not configured."""
    from database import integration_settings_collection
    doc = await integration_settings_collection.find_one({"org_id": "default"})
    if not doc:
        return None
    return doc.get("hubspot")


async def get_agent_api_config() -> Optional[dict]:
    """Return the agent API section of the integration settings, or None."""
    from database import integration_settings_collection
    doc = await integration_settings_collection.find_one({"org_id": "default"})
    if not doc:
        return None
    return doc.get("agent_api")


# ─── Connection test ──────────────────────────────────────────────────────────

async def test_hubspot_connection(token: str) -> dict:
    """Test whether the token is valid. Returns {ok, owner_email}."""
    try:
        data = await _hs_get("/crm/v3/owners/?limit=1", token)
        results = data.get("results", [])
        owner_email = results[0].get("email", "unknown") if results else "unknown"
        return {"ok": True, "message": f"Connected — portal owner: {owner_email}"}
    except httpx.HTTPStatusError as e:
        return {"ok": False, "message": f"HubSpot API error: {e.response.status_code} — {e.response.text[:200]}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# ─── Deal fetching ────────────────────────────────────────────────────────────

DEAL_PROPERTIES = [
    "dealname", "amount", "closedate", "createdate", "dealstage",
    "description", "hubspot_owner_id",
]

async def get_deal(deal_id: str, token: str) -> dict:
    """Fetch a deal with standard properties."""
    return await _hs_get(
        f"/crm/v3/objects/deals/{deal_id}",
        token,
        params={"properties": ",".join(DEAL_PROPERTIES), "associations": "companies,contacts"},
    )


async def get_deal_company_name(deal_data: dict, token: str) -> str:
    """Resolve the associated company name from a deal's association data."""
    try:
        assoc = deal_data.get("associations", {}).get("companies", {}).get("results", [])
        if not assoc:
            return ""
        company_id = assoc[0]["id"]
        company = await _hs_get(
            f"/crm/v3/objects/companies/{company_id}",
            token,
            params={"properties": "name"},
        )
        return company.get("properties", {}).get("name", "")
    except Exception:
        return ""


async def get_deal_primary_contact(deal_data: dict, token: str) -> dict:
    """Resolve the primary contact from a deal's association data."""
    try:
        assoc = deal_data.get("associations", {}).get("contacts", {}).get("results", [])
        if not assoc:
            return {}
        contact_id = assoc[0]["id"]
        contact = await _hs_get(
            f"/crm/v3/objects/contacts/{contact_id}",
            token,
            params={"properties": "firstname,lastname,email,jobtitle,phone"},
        )
        props = contact.get("properties", {})
        first = props.get("firstname", "")
        last = props.get("lastname", "")
        return {
            "name": f"{first} {last}".strip() or props.get("email", ""),
            "email": props.get("email", ""),
            "phone": props.get("phone", ""),
            "role": props.get("jobtitle", ""),
        }
    except Exception:
        return {}


# ─── Deal → Project mapping ───────────────────────────────────────────────────

def map_deal_to_project(deal_data: dict, company_name: str, contact: dict, config: dict) -> dict:
    """Convert a HubSpot deal dict into a DD Planner project payload."""
    props = deal_data.get("properties", {})
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Dates — HubSpot stores as epoch ms strings
    def parse_hs_date(val: str) -> str:
        if not val:
            return today_str
        try:
            # Could be ISO string or epoch ms
            if "T" in val:
                return val[:10]
            ts = int(val) / 1000
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            return today_str

    start_date = parse_hs_date(props.get("createdate", ""))
    end_date = parse_hs_date(props.get("closedate", ""))
    if end_date <= start_date:
        end_date = today_str

    # Budget — HubSpot amount is monetary; store as budget_value and estimate hours
    amount_str = props.get("amount", "") or "0"
    try:
        budget_value = float(amount_str)
    except ValueError:
        budget_value = 0.0

    project = {
        "name": props.get("dealname", "Unnamed Project"),
        "client_name": company_name or props.get("dealname", ""),
        "status": config.get("default_project_status", "Pipeline"),
        "start_date": start_date,
        "end_date": end_date,
        "description": props.get("description", ""),
        "hubspot_deal_id": str(deal_data.get("id", "")),
        "hubspot_portal_id": str(config.get("portal_id", "")),
        "budgeted_hours": 0,  # To be filled manually
        "budget_value": budget_value,
    }

    if contact:
        project["main_contact_name"] = contact.get("name", "")
        project["main_contact_email"] = contact.get("email", "")
        project["main_contact_phone"] = contact.get("phone", "")
        project["main_contact_role"] = contact.get("role", "")

    return project


# ─── Outbound — push status update note to HubSpot ───────────────────────────

async def push_status_update_to_hubspot(project: dict, status_update: dict, token: str) -> dict:
    """
    Create a HubSpot note engagement on the deal linked to this project.
    Returns {ok, engagement_id} or {ok=False, message}.
    """
    deal_id = project.get("hubspot_deal_id")
    if not deal_id:
        return {"ok": False, "message": "No hubspot_deal_id on project"}

    health = status_update.get("health", "Unknown")
    progress = status_update.get("actual_progress", 0)
    accomplishments = status_update.get("accomplishments", "") or status_update.get("progress_summary", "")
    blockers_raw = status_update.get("blockers", [])
    if isinstance(blockers_raw, list):
        blockers_text = "; ".join(blockers_raw) if blockers_raw else "None"
    else:
        blockers_text = str(blockers_raw) or "None"
    next_steps = status_update.get("next_steps", "") or status_update.get("next_week_plan", "")
    ai_summary = status_update.get("ai_generated_summary", "")
    project_name = project.get("name", "Project")
    updated_at = status_update.get("created_at", "")
    if hasattr(updated_at, "isoformat"):
        updated_at = updated_at.isoformat()

    body = f"""DD Planner Status Update — {project_name}

Date: {str(updated_at)[:10]}
Health: {health}
Progress: {progress}%

{f'Summary: {ai_summary}' if ai_summary else ''}

Accomplishments:
{accomplishments or 'N/A'}

Blockers:
{blockers_text}

Next Steps:
{next_steps or 'N/A'}

---
Synced automatically from DD Planner
"""

    try:
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        payload = {
            "engagement": {
                "active": True,
                "type": "NOTE",
                "timestamp": now_ms,
            },
            "associations": {
                "dealIds": [int(deal_id)],
            },
            "metadata": {
                "body": body,
            },
        }
        result = await _hs_post("/engagements/v1/engagements", token, payload)
        engagement_id = result.get("engagement", {}).get("id")
        logger.info(f"[HubSpot] Created note {engagement_id} on deal {deal_id}")
        return {"ok": True, "engagement_id": engagement_id}
    except httpx.HTTPStatusError as e:
        msg = f"HubSpot note error: {e.response.status_code} — {e.response.text[:300]}"
        logger.warning(f"[HubSpot] {msg}")
        return {"ok": False, "message": msg}
    except Exception as e:
        logger.warning(f"[HubSpot] push_status_update_to_hubspot: {e}")
        return {"ok": False, "message": str(e)}


# ─── Webhook signature validation ─────────────────────────────────────────────

def verify_hubspot_signature_v3(
    client_secret: str,
    request_uri: str,
    request_body: str,
    timestamp: str,
    signature: str,
) -> bool:
    """
    Validate HubSpot webhook signature v3.
    https://developers.hubspot.com/docs/api/webhooks/validating-requests
    """
    try:
        source = f"POST{request_uri}{request_body}{timestamp}"
        expected = hmac.new(
            client_secret.encode("utf-8"),
            source.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


# ─── Sync log helper ──────────────────────────────────────────────────────────

async def append_sync_log(direction: str, event_type: str, status: str, detail: str, reference_id: str = ""):
    """Write an audit entry to integration_sync_logs."""
    from database import integration_sync_logs_collection
    try:
        await integration_sync_logs_collection.insert_one({
            "direction": direction,       # "inbound" | "outbound"
            "event_type": event_type,     # "deal_to_project" | "status_update_push" | "test" etc.
            "status": status,             # "success" | "error" | "skipped"
            "detail": detail,
            "reference_id": reference_id,
            "created_at": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.warning(f"[SyncLog] Failed to write sync log: {e}")
