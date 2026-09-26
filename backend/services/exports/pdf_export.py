"""
PDF export service using Playwright HTML-to-PDF rendering.
"""
import logging
from urllib.parse import urlencode
from .renderer import render_pdf

logger = logging.getLogger(__name__)


def _print_url(frontend_base_url: str, project_id: str, token: str, extra: dict = None) -> str:
    """Build the /print report URL, threading through optional query params
    (e.g. period, wbs_mode) so the exported render matches the user's choices."""
    params = {"print": "1"}
    if extra:
        for k, v in extra.items():
            if v is not None and v != "":
                params[k] = v
    params["_t"] = token
    return f"{frontend_base_url}/print/projects/{project_id}/report?{urlencode(params)}"


async def build_project_pdf(project_id: str, token: str, frontend_base_url: str, extra_params: dict = None) -> bytes:
    """
    Generate PDF for a project report.

    Args:
        project_id: The project ID
        token: JWT token for authentication
        frontend_base_url: Base URL of the frontend (e.g., http://localhost:3000)
        extra_params: Optional query params to thread into the print URL, e.g.
                      {"period": "whole-project", "wbs_mode": "summary"}

    Returns:
        PDF bytes
    """
    logger.info(f"Building project PDF for project_id={project_id} params={extra_params}")
    url = _print_url(frontend_base_url, project_id, token, extra_params)
    
    pdf_bytes = await render_pdf(
        url,
        # 16:9 widescreen — matches PPTX / Google Slides so exports can be
        # dropped into a deck without re-formatting.
        width="13.333in",
        height="7.5in",
        landscape=False,  # dimensions already landscape (width > height)
        margin={'top': '6mm', 'bottom': '6mm', 'left': '6mm', 'right': '6mm'}
    )
    
    logger.info(f"Project PDF generated: {len(pdf_bytes)} bytes")
    return pdf_bytes


async def build_wbs_pdf(project_id: str, token: str, frontend_base_url: str, extra_params: dict = None) -> bytes:
    """
    Generate PDF for a WBS (Work Breakdown Structure).

    Args:
        project_id: The project ID
        token: JWT token for authentication
        frontend_base_url: Base URL of the frontend (e.g., http://localhost:3000)
        extra_params: Optional extra query params (e.g. wbs_mode).

    Returns:
        PDF bytes
    """
    logger.info(f"Building WBS PDF for project_id={project_id}")
    extra = {"view": "wbs"}
    if extra_params:
        extra.update(extra_params)
    url = _print_url(frontend_base_url, project_id, token, extra)
    
    pdf_bytes = await render_pdf(
        url,
        width="13.333in",
        height="7.5in",
        landscape=False,
        margin={'top': '6mm', 'bottom': '6mm', 'left': '6mm', 'right': '6mm'}
    )
    
    logger.info(f"WBS PDF generated: {len(pdf_bytes)} bytes")
    return pdf_bytes

