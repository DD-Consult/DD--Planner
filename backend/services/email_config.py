"""Per-workspace email configuration resolver + sender (Resend API or SMTP).

Email credentials are configured per workspace in Settings → Integrations → Email
(stored on the integration_settings document under the "email" key), resolved at
SEND TIME. A per-workspace `method` selector ("resend" | "smtp") chooses which
transport is used. Falls back to the server-wide env Resend vars for backward
compatibility when a workspace hasn't configured its own.

Design goals (owner-approved plan):
  - Email is strictly best-effort: a failed/unconfigured send never blocks the
    core action; callers still return the shareable link.
  - Secrets never leave the backend; API key / SMTP password are write-once,
    masked on read.
  - SMTP uses the Python stdlib (smtplib) — no new third-party dependency.
"""
import logging
import smtplib
import socket
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional, Tuple

import resend

from database import (
    integration_settings_collection,
    RESEND_API_KEY as ENV_RESEND_API_KEY,
    SENDER_EMAIL as ENV_SENDER_EMAIL,
)

logger = logging.getLogger(__name__)

ORG_ID = "default"


async def get_email_settings_block() -> dict:
    """Return the raw `email` settings block (templates/branding live here), or {}."""
    try:
        doc = await integration_settings_collection.find_one({"org_id": ORG_ID})
    except Exception:
        doc = None
    return (doc or {}).get("email") or {}


async def resolve_email_config() -> Optional[dict]:
    """Return the active email config for the current workspace, or None if email
    is not usable (disabled / incomplete for the chosen method).

    Returns one of:
      {"method": "resend", "api_key", "from_email", "reply_to"}
      {"method": "smtp", "host", "port", "username", "password", "use_tls",
       "from_email", "reply_to"}
    or None.

    Resolution:
      1. Per-workspace Settings → Integrations → Email block, using its `method`.
      2. Server-wide env Resend (legacy fallback) when no workspace config.
    """
    try:
        doc = await integration_settings_collection.find_one({"org_id": ORG_ID})
    except Exception as e:
        logger.warning(f"[email] settings lookup failed, falling back to env: {e}")
        doc = None

    email_cfg = (doc or {}).get("email") or {}
    if email_cfg.get("enabled"):
        method = (email_cfg.get("method") or "resend").lower()

        if method == "smtp":
            smtp = email_cfg.get("smtp") or {}
            host = smtp.get("host")
            username = smtp.get("username")
            password = smtp.get("password")
            from_email = smtp.get("from_email") or username
            if host and username and password and from_email:
                return {
                    "method": "smtp",
                    "host": host,
                    "port": int(smtp.get("port") or 587),
                    "username": username,
                    "password": password,
                    "use_tls": smtp.get("use_tls", True),  # STARTTLS on 587 by default
                    "from_email": from_email,
                    "reply_to": smtp.get("reply_to") or None,
                }
            logger.warning("[email] SMTP selected but incomplete (host/user/pass/from)")
            return None

        # method == "resend"
        resend_cfg = email_cfg.get("resend") or {}
        # Backward-compat: the earlier single-method shape stored api_key/from_email
        # at the top level of email_cfg.
        api_key = resend_cfg.get("api_key") or email_cfg.get("api_key")
        from_email = resend_cfg.get("from_email") or email_cfg.get("from_email") or ENV_SENDER_EMAIL
        reply_to = resend_cfg.get("reply_to") or email_cfg.get("reply_to")
        if api_key and from_email:
            return {
                "method": "resend",
                "api_key": api_key,
                "from_email": from_email,
                "reply_to": reply_to or None,
            }
        logger.warning("[email] Resend selected but incomplete (api_key/from)")
        return None

    # Legacy fallback: server-wide env Resend config.
    if ENV_RESEND_API_KEY and ENV_SENDER_EMAIL:
        return {
            "method": "resend",
            "api_key": ENV_RESEND_API_KEY,
            "from_email": ENV_SENDER_EMAIL,
            "reply_to": None,
        }

    return None


async def is_email_configured() -> bool:
    return (await resolve_email_config()) is not None


def _send_via_resend(cfg: dict, to_email: str, subject: str, html: str) -> Tuple[bool, str]:
    try:
        resend.api_key = cfg["api_key"]
        params = {
            "from": cfg["from_email"],
            "to": [to_email],
            "subject": subject,
            "html": html,
        }
        if cfg.get("reply_to"):
            params["reply_to"] = cfg["reply_to"]
        result = resend.Emails.send(params)
        if isinstance(result, dict) and result.get("id"):
            logger.info(f"[email] (resend) sent to {to_email}: {result.get('id')}")
            return True, "Email sent."
        msg = ""
        if isinstance(result, dict):
            msg = result.get("message") or result.get("name") or str(result)
        logger.warning(f"[email] (resend) not confirmed to {to_email}: {result}")
        return False, f"Email not sent: {msg or 'provider did not confirm delivery'}"
    except Exception as e:
        logger.error(f"[email] (resend) send failed to {to_email}: {e}")
        return False, f"Email not sent: {e}"


def _send_via_smtp(cfg: dict, to_email: str, subject: str, html: str) -> Tuple[bool, str]:
    host = cfg["host"]
    port = int(cfg["port"])
    username = cfg["username"]
    password = cfg["password"]
    use_tls = cfg.get("use_tls", True)
    from_email = cfg["from_email"]

    # Envelope MAIL FROM. Gmail / Google Workspace require the envelope sender to
    # be the AUTHENTICATED account (or a verified "Send mail as" alias) — using a
    # different envelope sender causes the server to accept the message but then
    # rewrite or DROP it (the classic "reported sent but never arrives"). So for
    # Gmail/Workspace hosts we send the envelope as the authenticated username and
    # keep the user's chosen address in the visible From header.
    host_l = (host or "").lower()
    is_gmail = "gmail.com" in host_l or "googlemail.com" in host_l
    envelope_from = username if is_gmail else from_email

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        # On Gmail the visible From is forced to the authenticated user unless the
        # chosen address is a verified alias — so set the header to the account we
        # actually authenticate as when they differ on Gmail, to avoid confusion.
        header_from = username if (is_gmail and from_email.lower() != username.lower()) else from_email
        msg["From"] = formataddr(("", header_from))
        msg["To"] = to_email
        if cfg.get("reply_to"):
            msg["Reply-To"] = cfg["reply_to"]
        elif is_gmail and from_email.lower() != username.lower():
            # Preserve the intended address as reply-to so replies still reach it.
            msg["Reply-To"] = from_email
        msg.attach(MIMEText(html, "html"))

        if port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=15, context=context) as server:
                server.login(username, password)
                refused = server.sendmail(envelope_from, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.ehlo()
                if use_tls:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                server.login(username, password)
                refused = server.sendmail(envelope_from, [to_email], msg.as_string())

        # sendmail returns a dict of recipients the server refused. Empty = all accepted.
        if refused:
            logger.warning(f"[email] (smtp) recipients refused: {refused}")
            return False, f"Email not sent: recipient refused ({refused})."

        logger.info(f"[email] (smtp) accepted to {to_email} via {host}:{port} (envelope from {envelope_from})")
        if is_gmail and from_email.lower() != username.lower():
            return True, (
                f"Email accepted by Gmail — note: it will be sent from {username} (the "
                f"authenticated account), not {from_email}, unless {from_email} is added as a "
                f"verified 'Send mail as' alias in that Gmail/Workspace account. Replies go to {from_email}."
            )
        return True, "Email sent."
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"[email] (smtp) auth failed: {e}")
        return False, ("Email not sent: SMTP login failed. For Gmail/Workspace use a 16-character "
                       "App Password (not your normal password) with 2-Step Verification enabled.")
    except smtplib.SMTPSenderRefused as e:
        logger.error(f"[email] (smtp) sender refused: {e}")
        return False, (f"Email not sent: the server rejected the sender address '{envelope_from}'. "
                       f"On Gmail/Workspace the sender must be the authenticated account or a verified alias.")
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPDataError) as e:
        logger.error(f"[email] (smtp) send rejected: {e}")
        return False, f"Email not sent: {e}"
    except (socket.timeout, TimeoutError, smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError, ConnectionError) as e:
        # Could not open/complete the SMTP connection. The #1 cause in production
        # is the hosting platform BLOCKING OUTBOUND SMTP (ports 25/465/587) —
        # Google Cloud Run, App Engine and many serverless hosts do this. In that
        # case SMTP can never work from the server; use the Resend (API) method,
        # which sends over HTTPS (port 443) and is not blocked.
        logger.error(f"[email] (smtp) connection failed to {host}:{port}: {e}")
        return False, (
            f"Email not sent: couldn't connect to {host}:{port} ({e}). Many hosting platforms "
            f"(e.g. Google Cloud Run) BLOCK outbound SMTP ports — if this is production, SMTP may be "
            f"blocked there. Switch the Email method to 'Resend (API)' (sends over HTTPS and is not blocked), "
            f"or allow SMTP egress on your host (e.g. a Serverless VPC connector + Cloud NAT)."
        )
    except Exception as e:
        logger.error(f"[email] (smtp) send failed to {to_email}: {e}")
        return False, f"Email not sent: {e}"


async def send_email(
    to_email: str,
    subject: str,
    html: str,
    *,
    email_type: str = "other",
    related_id: Optional[str] = None,
    related_label: Optional[str] = None,
) -> Tuple[bool, str]:
    """Send an email using the resolved per-workspace config and its active method,
    and record the attempt in the email delivery log.

    Returns (sent, message). Never raises — email is best-effort.
    email_type: "proposal_link" | "report_link" | "report_code" | "proposal_reminder" | "test" | "other"
    """
    cfg = await resolve_email_config()
    if not cfg:
        logger.info("[email] not configured; skipping send (link available to copy)")
        await _log_email(to_email, subject, email_type, related_id, related_label,
                         method=None, sent=False, message="Email not configured")
        return False, "Email is not configured — share the link manually."

    import asyncio
    method = cfg.get("method", "resend")
    if method == "smtp":
        sent, message = await asyncio.to_thread(_send_via_smtp, cfg, to_email, subject, html)
    else:
        sent, message = await asyncio.to_thread(_send_via_resend, cfg, to_email, subject, html)

    await _log_email(to_email, subject, email_type, related_id, related_label,
                     method=method, sent=sent, message=message)
    return sent, message


async def _log_email(to_email, subject, email_type, related_id, related_label, *, method, sent, message):
    """Best-effort write to the email delivery log. Never raises."""
    try:
        from datetime import datetime, timezone
        from database import email_log_collection
        await email_log_collection.insert_one({
            "to": to_email,
            "subject": subject,
            "type": email_type,
            "related_id": related_id,
            "related_label": related_label,
            "method": method,
            "status": "sent" if sent else "failed",
            "message": message,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"[email] delivery-log write failed (non-fatal): {e}")

