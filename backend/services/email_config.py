"""Per-workspace email (Resend) configuration resolver + sender.

Email credentials are configured per workspace in Settings → Integrations → Email
(stored on the integration_settings document under the "email" key), resolved at
SEND TIME. Falls back to the server-wide env vars (RESEND_API_KEY / SENDER_EMAIL)
for backward compatibility when a workspace hasn't configured its own.

Design goals (owner-approved plan):
  - Email is strictly best-effort: a failed/unconfigured send never blocks the
    core action; callers still return the shareable link.
  - Secrets never leave the backend; the API key is write-once, masked on read.
"""
import logging
from typing import Optional, Tuple

import resend

from database import (
    integration_settings_collection,
    RESEND_API_KEY as ENV_RESEND_API_KEY,
    SENDER_EMAIL as ENV_SENDER_EMAIL,
)

logger = logging.getLogger(__name__)

ORG_ID = "default"


async def resolve_email_config() -> Optional[dict]:
    """Return the active email config for the current workspace, or None if email
    is not usable (disabled / no key).

    Resolution order:
      1. Per-workspace Settings → Integrations → Email block (if enabled + api_key)
      2. Server-wide env (RESEND_API_KEY + SENDER_EMAIL) — legacy fallback
    Returns {api_key, from_email, reply_to} or None.
    """
    try:
        doc = await integration_settings_collection.find_one({"org_id": ORG_ID})
    except Exception as e:
        logger.warning(f"[email] settings lookup failed, falling back to env: {e}")
        doc = None

    email_cfg = (doc or {}).get("email") or {}
    if email_cfg.get("enabled") and email_cfg.get("api_key"):
        from_email = email_cfg.get("from_email") or ENV_SENDER_EMAIL
        if not from_email:
            logger.warning("[email] enabled but no 'from' address set; cannot send")
            return None
        return {
            "api_key": email_cfg["api_key"],
            "from_email": from_email,
            "reply_to": email_cfg.get("reply_to") or None,
        }

    # Legacy fallback: server-wide env config.
    if ENV_RESEND_API_KEY and ENV_SENDER_EMAIL:
        return {
            "api_key": ENV_RESEND_API_KEY,
            "from_email": ENV_SENDER_EMAIL,
            "reply_to": None,
        }

    return None


async def is_email_configured() -> bool:
    return (await resolve_email_config()) is not None


async def send_email(to_email: str, subject: str, html: str) -> Tuple[bool, str]:
    """Send an email using the resolved per-workspace Resend config.

    Returns (sent, message). Never raises — email is best-effort.
      sent=True  → Resend accepted the message.
      sent=False → not configured, or the provider rejected it (message explains why,
                   e.g. Resend's "verify your domain" / "can only send to yourself").
    """
    cfg = await resolve_email_config()
    if not cfg:
        logger.info("[email] not configured; skipping send (link available to copy)")
        return False, "Email is not configured — share the link manually."

    try:
        import asyncio
        resend.api_key = cfg["api_key"]
        params = {
            "from": cfg["from_email"],
            "to": [to_email],
            "subject": subject,
            "html": html,
        }
        if cfg.get("reply_to"):
            params["reply_to"] = cfg["reply_to"]
        result = await asyncio.to_thread(resend.Emails.send, params)
        # Resend returns a dict with an 'id' on success.
        if isinstance(result, dict) and result.get("id"):
            logger.info(f"[email] sent to {to_email}: {result.get('id')}")
            return True, "Email sent."
        # Some error shapes come back as dicts with a message/name.
        msg = ""
        if isinstance(result, dict):
            msg = result.get("message") or result.get("name") or str(result)
        logger.warning(f"[email] provider did not confirm send to {to_email}: {result}")
        return False, f"Email not sent: {msg or 'provider did not confirm delivery'}"
    except Exception as e:
        logger.error(f"[email] send failed to {to_email}: {e}")
        return False, f"Email not sent: {e}"
