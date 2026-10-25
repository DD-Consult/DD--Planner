"""Editable email templates + workspace branding for proposal / report emails.

Templates (subject + HTML body) and branding (logo, accent colour) are stored
per workspace on the integration_settings `email.templates` / `email.branding`
blocks. Senders render the active template with simple {{merge_field}}
substitution and wrap the body in a branded shell. If a workspace hasn't
customised a template, the built-in default is used — so behaviour is unchanged
until someone edits it.

Merge fields available (missing ones render as empty string):
  proposal_link:  {{client_name}} {{proposal_title}} {{link}} {{sender_name}} {{company_name}}
  report_link:    {{client_name}} {{project_name}} {{link}} {{sender_name}} {{company_name}}
  report_code:    {{client_name}} {{project_name}} {{code}} {{company_name}}
"""
import re
from typing import Dict

DEFAULT_ACCENT = "#1570EF"
DEFAULT_COMPANY = "DD Consulting"

# Template keys and their built-in defaults. Body is the INNER html (wrapped by
# the branded shell at render time). Keep merge fields in {{snake_case}}.
DEFAULT_TEMPLATES: Dict[str, Dict[str, str]] = {
    "proposal_link": {
        "label": "Proposal link email",
        "subject": "Proposal: {{proposal_title}}",
        "body": (
            "<p>Hi {{client_name}},</p>"
            "<p>Your proposal <strong>{{proposal_title}}</strong> is ready to view.</p>"
            "<p style=\"text-align:center;margin:30px 0;\">"
            "<a href=\"{{link}}\" class=\"btn\">View Proposal</a></p>"
            "<p style=\"background:#F4F6F8;padding:12px;border-radius:6px;font-size:13px;\">"
            "🔒 This is a secure, unique link for your review.</p>"
            "<p style=\"color:#667085;font-size:13px;\">You can also copy this link:</p>"
            "<p style=\"background:#f3f4f6;padding:10px;border-radius:4px;word-break:break-all;"
            "font-size:12px;font-family:monospace;\">{{link}}</p>"
        ),
    },
    "report_link": {
        "label": "Client report link email",
        "subject": "Project Report - {{project_name}}",
        "body": (
            "<p>Hi {{client_name}},</p>"
            "<p>Your project status report for <strong>{{project_name}}</strong> is ready to view.</p>"
            "<p style=\"text-align:center;margin:30px 0;\">"
            "<a href=\"{{link}}\" class=\"btn\">View Report Online</a></p>"
            "<p style=\"background:#F4F6F8;padding:12px;border-radius:6px;font-size:13px;\">"
            "🔒 This link is valid for 30 days and requires email verification to access.</p>"
            "<p style=\"color:#667085;font-size:13px;\">You can also copy this link:</p>"
            "<p style=\"background:#f3f4f6;padding:10px;border-radius:4px;word-break:break-all;"
            "font-size:12px;font-family:monospace;\">{{link}}</p>"
        ),
    },
    "report_code": {
        "label": "Report verification code email",
        "subject": "Verification Code - {{project_name}} Report",
        "body": (
            "<p>Hi {{client_name}},</p>"
            "<p>You've been sent a secure link to view the project report for "
            "<strong>{{project_name}}</strong>. Use this verification code to access it:</p>"
            "<div style=\"background:#f3f4f6;padding:20px;text-align:center;border-radius:8px;margin:20px 0;\">"
            "<h1 style=\"font-size:32px;letter-spacing:4px;margin:0;\">{{code}}</h1></div>"
            "<p style=\"color:#667085;font-size:13px;\">This code is valid for 1 hour and can be used up to 3 times.</p>"
        ),
    },
}

_MERGE_RE = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def _merge(text: str, ctx: Dict[str, str]) -> str:
    """Replace {{field}} with ctx[field] (missing -> empty)."""
    def repl(m):
        return str(ctx.get(m.group(1), "") or "")
    return _MERGE_RE.sub(repl, text or "")


def get_default_templates() -> dict:
    """Return a deep copy of the default templates (for the Settings UI / reset)."""
    import copy
    return copy.deepcopy(DEFAULT_TEMPLATES)


def _branded_shell(inner_html: str, branding: dict) -> str:
    accent = (branding or {}).get("accent_color") or DEFAULT_ACCENT
    logo = (branding or {}).get("logo_url") or ""
    company = (branding or {}).get("company_name") or DEFAULT_COMPANY
    logo_html = (
        f'<img src="{logo}" alt="{company}" style="max-height:40px;margin-bottom:8px;" />'
        if logo else f'<div style="font-weight:700;font-size:18px;color:{accent};">{company}</div>'
    )
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#0B1220;">
      <div style="padding:20px 0;border-bottom:2px solid {accent};margin-bottom:24px;">{logo_html}</div>
      <style>.btn{{background:{accent};color:#fff;padding:12px 24px;text-decoration:none;border-radius:6px;display:inline-block;font-weight:600;}}</style>
      {inner_html}
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:30px 0;" />
      <p style="color:#999;font-size:12px;">{company}</p>
    </div>
    """


def render_email(settings_email: dict, template_key: str, ctx: Dict[str, str]):
    """Render (subject, html) for a template key using the workspace's custom
    template+branding, falling back to defaults. `settings_email` is the `email`
    block of integration_settings (may be None)."""
    settings_email = settings_email or {}
    templates = settings_email.get("templates") or {}
    branding = settings_email.get("branding") or {}
    default = DEFAULT_TEMPLATES.get(template_key, {"subject": "", "body": ""})
    tmpl = templates.get(template_key) or {}

    subject = tmpl.get("subject") or default["subject"]
    body = tmpl.get("body") or default["body"]

    # Inject company_name default into ctx if not provided.
    ctx = dict(ctx or {})
    ctx.setdefault("company_name", branding.get("company_name") or DEFAULT_COMPANY)

    subject_r = _merge(subject, ctx)
    body_r = _merge(body, ctx)
    html = _branded_shell(body_r, branding)
    return subject_r, html
