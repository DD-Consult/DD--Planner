"""
Render delegation client — Phase 3 "dedicated render capacity".

WHY
----
Heavy PDF/PPTX exports spin up headless Chromium, which competes for CPU/memory
with normal API/UI traffic when it runs inside the main app instance. Phase 3
moves that work to a SEPARATE Cloud Run service ("render service") running the
SAME image but scaled independently, so exports never starve the app.

HOW
----
- The main app's export endpoints call `render_via_service(...)`.
- If RENDER_SERVICE_URL is configured, this makes an authenticated HTTP call to
  the render service's internal endpoint and returns the produced bytes.
- If RENDER_SERVICE_URL is NOT configured (e.g. local/preview, or before the
  dedicated service is provisioned), this returns None and the caller falls back
  to rendering in-process — so behaviour is 100% backward compatible.
- On ANY delegation error (network, non-200), returns None so the caller falls
  back in-process → the "exports never error" guarantee is preserved.

SECURITY
---------
The internal render endpoint is guarded by a shared secret (RENDER_SERVICE_KEY)
sent in the X-Render-Key header and compared with secrets.compare_digest on the
render service. The user's JWT is forwarded so the render preserves the exact
user/tenant data scoping.
"""
import os
import logging
import httpx

logger = logging.getLogger(__name__)

RENDER_SERVICE_URL = os.environ.get("RENDER_SERVICE_URL", "").rstrip("/")
RENDER_SERVICE_KEY = os.environ.get("RENDER_SERVICE_KEY", "")
# Generous timeout — a heavy render can take a while; must exceed the in-render
# selector waits. Matches Cloud Run's 300s request cap.
_RENDER_HTTP_TIMEOUT = float(os.environ.get("RENDER_SERVICE_TIMEOUT", "290"))


def render_delegation_enabled() -> bool:
    """True when a dedicated render service is configured."""
    return bool(RENDER_SERVICE_URL and RENDER_SERVICE_KEY)


async def render_via_service(
    kind: str,
    project_id: str,
    token: str,
    *,
    period: str = None,
    wbs_mode: str = None,
    view: str = None,
):
    """Delegate a render to the dedicated render service.

    Args:
        kind: 'pdf' | 'ppt' (project report) — WBS-only uses view='wbs'.
        project_id: project id
        token: the caller's JWT (forwarded to preserve data scoping)
        period / wbs_mode / view: render options threaded to the print page

    Returns:
        bytes on success, or None if delegation is disabled or failed (caller
        should then render in-process).
    """
    if not render_delegation_enabled():
        return None

    endpoint = f"{RENDER_SERVICE_URL}/api/internal/render/{kind}"
    params = {"project_id": project_id}
    if period:
        params["period"] = period
    if wbs_mode:
        params["wbs_mode"] = wbs_mode
    if view:
        params["view"] = view

    headers = {
        "X-Render-Key": RENDER_SERVICE_KEY,
        # Forward the caller's identity so the render preserves user/tenant scope.
        "X-Forward-Authorization": f"Bearer {token}",
    }

    try:
        async with httpx.AsyncClient(timeout=_RENDER_HTTP_TIMEOUT) as client:
            resp = await client.get(endpoint, params=params, headers=headers)
        if resp.status_code == 200 and resp.content:
            logger.info(
                f"[RENDER DELEGATE] {kind} for {project_id} rendered by render service "
                f"({len(resp.content)} bytes)"
            )
            return resp.content
        logger.warning(
            f"[RENDER DELEGATE] render service returned {resp.status_code} for {kind}/{project_id}; "
            f"falling back to in-process render"
        )
        return None
    except Exception as e:
        logger.warning(
            f"[RENDER DELEGATE] call to render service failed ({e}); falling back to in-process render"
        )
        return None
