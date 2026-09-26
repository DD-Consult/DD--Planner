"""
Internal render endpoints — Phase 3 "dedicated render capacity".

These endpoints run the heavy Playwright render IN-PROCESS on whichever service
handles the request. In production the MAIN app (ddplan) does NOT call these on
itself — it calls the dedicated RENDER SERVICE (ddplan-render, same image) which
serves these on its own independently-scaled Cloud Run capacity.

Auth: guarded by a shared secret in the X-Render-Key header (compared with
secrets.compare_digest). Not for public/browser use.

The caller forwards the user's JWT in X-Forward-Authorization so the render
preserves the exact user/tenant data scoping.
"""
import os
import secrets
import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response

from services.exports import (
    build_project_pdf,
    build_wbs_pdf,
    build_project_ppt,
    build_wbs_ppt,
)

logger = logging.getLogger(__name__)
router = APIRouter()

RENDER_SERVICE_KEY = os.environ.get("RENDER_SERVICE_KEY", "")


def _check_render_key(request: Request):
    """Validate the internal render shared secret (timing-safe)."""
    provided = request.headers.get("x-render-key", "")
    if not RENDER_SERVICE_KEY:
        # If no key is configured, the internal endpoint is disabled entirely.
        raise HTTPException(status_code=403, detail="Internal render endpoint is not enabled")
    if not provided or not secrets.compare_digest(provided, RENDER_SERVICE_KEY):
        raise HTTPException(status_code=403, detail="Invalid render key")


def _forwarded_token(request: Request) -> str:
    """The caller forwards the user's JWT in X-Forward-Authorization."""
    fwd = request.headers.get("x-forward-authorization", "")
    if fwd.lower().startswith("bearer "):
        return fwd.split(" ", 1)[1].strip()
    # Fall back to a normal Authorization header if present.
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return ""


def _frontend_base_url() -> str:
    """Where this service's own React app is served (nginx :8080 in prod,
    dev-server :3000 locally). Mirrors routes/reports.py."""
    explicit = os.environ.get("FRONTEND_INTERNAL_URL")
    if explicit:
        return explicit.rstrip("/")
    if os.environ.get("K_SERVICE") or os.environ.get("GAE_APPLICATION") or os.path.exists("/app/frontend/build"):
        return "http://localhost:8080"
    return "http://localhost:3000"


@router.get("/api/internal/render/pdf")
async def internal_render_pdf(request: Request):
    """Render a project report (or WBS-only) to PDF. Internal use only."""
    _check_render_key(request)
    qp = request.query_params
    project_id = qp.get("project_id")
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    token = _forwarded_token(request)
    base = _frontend_base_url()
    view = qp.get("view")
    extra = {"period": qp.get("period") or "whole-project", "wbs_mode": qp.get("wbs_mode") or "full"}

    if view == "wbs":
        pdf_bytes = await build_wbs_pdf(project_id, token, base, extra_params=extra)
    else:
        pdf_bytes = await build_project_pdf(project_id, token, base, extra_params=extra)

    return Response(content=pdf_bytes, media_type="application/pdf")


@router.get("/api/internal/render/ppt")
async def internal_render_ppt(request: Request):
    """Render a project report (or WBS-only) to PPTX. Internal use only."""
    _check_render_key(request)
    qp = request.query_params
    project_id = qp.get("project_id")
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    token = _forwarded_token(request)
    base = _frontend_base_url()
    view = qp.get("view")
    extra = {"period": qp.get("period") or "whole-project", "wbs_mode": qp.get("wbs_mode") or "full"}

    if view == "wbs":
        pptx_bytes = await build_wbs_ppt(project_id, token, base, extra_params=extra)
    else:
        pptx_bytes = await build_project_ppt(project_id, token, base, extra_params=extra)

    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
