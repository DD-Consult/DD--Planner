"""
AI Agent Action Registry
========================
Declarative registry for every action the AI chat agent can execute.

Each entry declares:
  • handler           — async callable (action: dict, current_user: dict) -> dict
  • required_fields   — must be present in the action JSON
  • permission        — "admin" or "super_admin"
  • is_destructive    — destructive ops require confirmation token (unless super_admin)
  • category          — used for audit log + AI prompt grouping
  • description       — plain-English summary surfaced in the AI prompt
  • example           — example JSON shape the AI should emit
  • audit_entity_type — entity_type written to change_log on success

The single `dispatch_action(action, current_user)` function is the only entry point
the chat endpoint calls. All cross-cutting concerns (permission, confirmation,
audit logging) live here so each handler stays focused on its DB operation.
"""
from __future__ import annotations

import uuid as uuid_module
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from database import pending_actions_collection


# ─────────────────────────────────────────────────────────────────────────
# Token-based confirmation flow (for destructive actions)
# ─────────────────────────────────────────────────────────────────────────

CONFIRMATION_TTL_MINUTES = 10


async def _create_confirmation_token(user_email: str, action: dict, summary: str) -> str:
    """Store a pending destructive action and return a short token the user
    must echo back to confirm."""
    token = uuid_module.uuid4().hex[:8]
    now = datetime.now(timezone.utc)
    await pending_actions_collection.insert_one({
        "token": token,
        "user_email": user_email,
        "action": action,
        "summary": summary,
        "created_at": now,
        "expires_at": now + timedelta(minutes=CONFIRMATION_TTL_MINUTES),
    })
    return token


async def _consume_confirmation_token(user_email: str, token: str) -> Optional[dict]:
    """Look up and delete a pending action by token. Returns the stored action
    dict if valid + not expired, else None."""
    pending = await pending_actions_collection.find_one({
        "token": token,
        "user_email": user_email,
    })
    if not pending:
        return None
    # Reject expired
    exp = pending.get("expires_at")
    if exp and exp.replace(tzinfo=timezone.utc) if exp.tzinfo is None else exp:
        if datetime.now(timezone.utc) > (exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)):
            await pending_actions_collection.delete_one({"_id": pending["_id"]})
            return None
    await pending_actions_collection.delete_one({"_id": pending["_id"]})
    return pending


# ─────────────────────────────────────────────────────────────────────────
# Audit logging — every successful action writes to change_log
# ─────────────────────────────────────────────────────────────────────────

async def _audit_log(action: dict, spec: dict, result: dict, current_user: dict) -> None:
    """Write a change_log entry for a successful AI action. Best-effort."""
    try:
        from services.baselines import log_change
        # Determine project_id for grouping
        project_id = (
            action.get("project_id")
            or action.get("from_project_id")
            or result.get("project_id")
            or "system"
        )
        # Determine entity_id
        entity_type = spec.get("audit_entity_type", "system")
        entity_id_key_candidates = [
            f"{entity_type}_id",
            "id",
            "user_email",
            "task_id",
            "risk_id",
            "allocation_id",
            "baseline_id",
            "phase_id",
            "leave_id",
            "holiday_id",
            "timesheet_id",
            "notification_id",
        ]
        entity_id = None
        for k in entity_id_key_candidates:
            if action.get(k):
                entity_id = action[k]
                break
        if not entity_id:
            entity_id = result.get("id") or result.get("inserted_id") or "?"

        # Strip noise from the payload before logging
        payload = {k: v for k, v in action.items() if k not in ("action", "confirm_token", "description", "summary")}

        await log_change(
            project_id=str(project_id),
            user_email=current_user.get("email"),
            entity_type=entity_type,
            entity_id=str(entity_id),
            action="ai:" + action.get("action", "?"),
            new_value=payload,
            reason=f"AI agent: {action.get('description', action.get('action'))}",
        )
    except Exception:
        # Never fail an action because audit logging failed
        pass


# ─────────────────────────────────────────────────────────────────────────
# Registry build helper — populated by importing handlers at the bottom
# ─────────────────────────────────────────────────────────────────────────

ACTIONS: Dict[str, dict] = {}


def register(
    name: str,
    *,
    handler: Callable[[dict, dict], Awaitable[dict]],
    required_fields: Optional[List[str]] = None,
    permission: str = "admin",
    is_destructive: bool = False,
    category: str = "system",
    description: str = "",
    example: Optional[dict] = None,
    audit_entity_type: str = "system",
):
    ACTIONS[name] = {
        "handler": handler,
        "required_fields": required_fields or [],
        "permission": permission,
        "is_destructive": is_destructive,
        "category": category,
        "description": description,
        "example": example or {"action": name},
        "audit_entity_type": audit_entity_type,
    }


# ─────────────────────────────────────────────────────────────────────────
# THE DISPATCHER — the only entrypoint chat uses
# ─────────────────────────────────────────────────────────────────────────

async def dispatch_action(action: dict, current_user: dict) -> dict:
    """Validate, permission-check, confirm (if destructive), execute, and
    audit-log an AI-proposed action."""
    name = action.get("action")

    # ── Permission check FIRST — applies to registry AND legacy actions ──
    role = (current_user.get("role") or "").lower()
    is_super = role == "super_admin"
    is_admin = role in ("admin", "super_admin")
    if not is_admin:
        return {"success": False, "message": "🔒 Admin access required for AI actions."}

    spec = ACTIONS.get(name)
    if not spec:
        # Legacy fallback: try the old executor in ai_actions.py for actions not
        # yet migrated to the registry (keeps the existing 16 actions working
        # while we migrate them over).
        try:
            from services.ai_actions import execute_ai_action as _legacy
            return await _legacy(action, current_user)
        except Exception as e:
            return {"success": False, "message": f"Unknown action '{name}': {e}"}

    # ── Required-field check ──
    missing = [f for f in spec["required_fields"] if action.get(f) is None]
    if missing:
        return {
            "success": False,
            "message": f"Missing required field(s) for {name}: {', '.join(missing)}",
        }

    # ── Super-admin permission check ──
    if spec["permission"] == "super_admin" and not is_super:
        return {
            "success": False,
            "message": f"🔒 The action `{name}` requires super-admin privileges. Please ask a super-admin.",
        }

    # ── Destructive confirmation flow ──
    if spec["is_destructive"] and not is_super:
        token = action.get("confirm_token")
        if not token:
            # No token yet — issue one and prompt the user
            summary = spec["description"] or name
            new_token = await _create_confirmation_token(
                current_user.get("email", ""),
                action,
                summary,
            )
            return {
                "success": False,
                "needs_confirmation": True,
                "confirm_token": new_token,
                "action_name": name,
                "message": (
                    f"⚠️ **{name}** is a destructive action. To proceed, reply with:\n"
                    f"`confirm {new_token}`\n"
                    f"(token expires in {CONFIRMATION_TTL_MINUTES} minutes)"
                ),
            }
        else:
            # Validate token
            pending = await _consume_confirmation_token(current_user.get("email", ""), token)
            if not pending:
                return {"success": False, "message": f"❌ Confirmation token `{token}` is invalid or expired. Please retry the action."}

    # ── Execute ──
    try:
        result = await spec["handler"](action, current_user)
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception(f"[AI registry] {name} failed")
        return {"success": False, "message": f"Action `{name}` failed: {e}"}

    if not isinstance(result, dict):
        result = {"success": True, "data": result}

    # ── Audit log ──
    if result.get("success"):
        await _audit_log(action, spec, result, current_user)

    return result


# ─────────────────────────────────────────────────────────────────────────
# Prompt builder — generates the AI prompt action documentation
# ─────────────────────────────────────────────────────────────────────────

def build_actions_prompt() -> str:
    """Generate the chunk of the AI system prompt that documents every
    registered action, grouped by category. Compact for token efficiency."""
    by_cat: Dict[str, List[str]] = {}
    for name, spec in ACTIONS.items():
        cat = spec["category"]
        flags = []
        if spec["is_destructive"]:
            flags.append("destructive")
        if spec["permission"] == "super_admin":
            flags.append("super-admin only")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        # Format the example as compact JSON for the AI
        import json as _json
        example_json = _json.dumps({**spec["example"], "action": name})
        line = f"- **{name}**{flag_str} — {spec['description']}\n  Example: `{example_json}`"
        by_cat.setdefault(cat, []).append(line)

    out_lines = []
    for cat in sorted(by_cat.keys()):
        out_lines.append(f"\n### {cat.upper()} ACTIONS")
        out_lines.extend(by_cat[cat])
    return "\n".join(out_lines)


def list_action_names() -> List[str]:
    """For debugging / smoke tests."""
    return sorted(ACTIONS.keys())


# ─────────────────────────────────────────────────────────────────────────
# Handler registration happens in ai_actions_extended.py to avoid
# circular imports. That module is imported below at the bottom.
# ─────────────────────────────────────────────────────────────────────────

def _bootstrap_handlers():
    """Late import to avoid circular dependency."""
    from services import ai_actions_extended  # noqa: F401  — side-effect: registers handlers


_bootstrap_handlers()
