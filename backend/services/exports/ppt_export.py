"""
PowerPoint export service using Playwright screenshots + python-pptx composition.
"""
import logging
from io import BytesIO
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from .renderer import render_screenshots

logger = logging.getLogger(__name__)

# DD Consulting Brand Colors
DD_NAVY = RGBColor(0x1B, 0x2A, 0x47)
DD_GOLD = RGBColor(0xC9, 0xA8, 0x4C)
DD_LIGHT = RGBColor(0xE8, 0xED, 0xF2)


def _compose_pptx(images: list[bytes], title: str) -> bytes:
    """
    Compose a PowerPoint presentation from a list of screenshot images.
    
    Args:
        images: List of PNG image bytes
        title: Presentation title
    
    Returns:
        PPTX bytes
    """
    logger.info(f"Composing PPTX with {len(images)} images, title: {title}")
    
    # Create presentation (16:9 widescreen)
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    
    for idx, image_bytes in enumerate(images):
        logger.info(f"Adding slide {idx + 1} of {len(images)}")
        
        # Add blank slide
        blank_slide_layout = prs.slide_layouts[6]  # Blank layout
        slide = prs.slides.add_slide(blank_slide_layout)
        
        # Add DD-branded header bar (navy background)
        header_height = Inches(0.6)
        header = slide.shapes.add_shape(
            1,  # Rectangle
            Inches(0), Inches(0),
            prs.slide_width, header_height
        )
        header.fill.solid()
        header.fill.fore_color.rgb = DD_NAVY
        header.line.fill.background()
        
        # Add title text to header
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.15),
            Inches(10), Inches(0.3)
        )
        text_frame = title_box.text_frame
        text_frame.text = f"{title} - Slide {idx + 1}"
        text_frame.paragraphs[0].font.size = Pt(18)
        text_frame.paragraphs[0].font.bold = True
        text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)
        
        # Add DD logo placeholder text (right side of header)
        logo_box = slide.shapes.add_textbox(
            prs.slide_width - Inches(3), Inches(0.15),
            Inches(2.5), Inches(0.3)
        )
        logo_frame = logo_box.text_frame
        logo_frame.text = "DD Consulting"
        logo_frame.paragraphs[0].font.size = Pt(14)
        logo_frame.paragraphs[0].font.bold = True
        logo_frame.paragraphs[0].font.color.rgb = DD_GOLD
        logo_frame.paragraphs[0].alignment = PP_ALIGN.RIGHT
        
        # Add the screenshot image (maximized below header)
        image_stream = BytesIO(image_bytes)
        
        # Calculate image position and size to maximize below header
        img_left = Inches(0.2)
        img_top = header_height + Inches(0.1)
        img_width = prs.slide_width - Inches(0.4)
        img_height = prs.slide_height - header_height - Inches(0.2)
        
        slide.shapes.add_picture(
            image_stream,
            img_left, img_top,
            width=img_width,
            height=img_height
        )
        
        logger.info(f"Slide {idx + 1} added successfully")
    
    # Save to BytesIO
    pptx_stream = BytesIO()
    prs.save(pptx_stream)
    pptx_bytes = pptx_stream.getvalue()
    
    logger.info(f"PPTX generated: {len(pptx_bytes)} bytes")
    return pptx_bytes


async def build_project_ppt(project_id: str, token: str, frontend_base_url: str) -> bytes:
    """
    Generate PowerPoint for a project report.
    Matches PDF export by rendering the full report page.
    
    Args:
        project_id: The project ID
        token: JWT token for authentication
        frontend_base_url: Base URL of the frontend (e.g., http://localhost:3000)
    
    Returns:
        PPTX bytes
    """
    logger.info(f"Building project PPT for project_id={project_id}")
    url = f"{frontend_base_url}/print/projects/{project_id}/report?print=1&_t={token}"
    
    # Take full page screenshot to match PDF export
    # No selectors = full page capture, same as PDF
    pngs = await render_screenshots(
        url,
        viewport={'width': 1920, 'height': 1080}
    )
    
    if not pngs:
        logger.warning("No screenshots captured, report may be empty")
        raise ValueError("Failed to generate project report screenshots")
    
    pptx_bytes = _compose_pptx(pngs, title="Project Report")
    
    logger.info(f"Project PPT generated: {len(pptx_bytes)} bytes, {len(pngs)} slide(s)")
    return pptx_bytes


async def build_wbs_ppt(project_id: str, token: str, frontend_base_url: str) -> bytes:
    """
    Generate PowerPoint for a WBS (Work Breakdown Structure).
    Matches PDF export by rendering the full WBS page.
    
    Args:
        project_id: The project ID
        token: JWT token for authentication
        frontend_base_url: Base URL of the frontend (e.g., http://localhost:3000)
    
    Returns:
        PPTX bytes
    """
    logger.info(f"Building WBS PPT for project_id={project_id}")
    url = f"{frontend_base_url}/print/projects/{project_id}/report?print=1&view=wbs&_t={token}"
    
    # Take full page screenshot to match PDF export
    # No selectors = full page capture, same as PDF
    pngs = await render_screenshots(
        url,
        viewport={'width': 1920, 'height': 1080}
    )
    
    if not pngs:
        logger.warning("No screenshots captured, WBS report may be empty")
        raise ValueError("Failed to generate WBS report screenshots")
    
    pptx_bytes = _compose_pptx(pngs, title="Work Breakdown Structure")
    
    logger.info(f"WBS PPT generated: {len(pptx_bytes)} bytes, {len(pngs)} slide(s)")
    return pptx_bytes
