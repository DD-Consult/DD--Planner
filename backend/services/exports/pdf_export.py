"""
PDF export service using Playwright HTML-to-PDF rendering.
"""
import logging
from .renderer import render_pdf

logger = logging.getLogger(__name__)


async def build_project_pdf(project_id: str, token: str, frontend_base_url: str) -> bytes:
    """
    Generate PDF for a project report.
    
    Args:
        project_id: The project ID
        token: JWT token for authentication
        frontend_base_url: Base URL of the frontend (e.g., http://localhost:3000)
    
    Returns:
        PDF bytes
    """
    logger.info(f"Building project PDF for project_id={project_id}")
    url = f"{frontend_base_url}/print/projects/{project_id}/report?print=1&_t={token}"
    
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


async def build_wbs_pdf(project_id: str, token: str, frontend_base_url: str) -> bytes:
    """
    Generate PDF for a WBS (Work Breakdown Structure).
    
    Args:
        project_id: The project ID
        token: JWT token for authentication
        frontend_base_url: Base URL of the frontend (e.g., http://localhost:3000)
    
    Returns:
        PDF bytes
    """
    logger.info(f"Building WBS PDF for project_id={project_id}")
    url = f"{frontend_base_url}/print/projects/{project_id}/report?print=1&view=wbs&_t={token}"
    
    pdf_bytes = await render_pdf(
        url,
        width="13.333in",
        height="7.5in",
        landscape=False,
        margin={'top': '6mm', 'bottom': '6mm', 'left': '6mm', 'right': '6mm'}
    )
    
    logger.info(f"WBS PDF generated: {len(pdf_bytes)} bytes")
    return pdf_bytes
