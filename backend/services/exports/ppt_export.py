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


def _compose_pptx(images: list, title: str) -> bytes:
    """
    Compose a PowerPoint presentation from a list of screenshot images.
    Each image gets its own 16:9 slide with proper aspect-ratio preservation
    (fit-to-contain rather than stretch-to-fill).
    
    Args:
        images: List of PNG image bytes
        title: Presentation title
    
    Returns:
        PPTX bytes
    """
    from PIL import Image as PILImage

    logger.info(f"Composing PPTX with {len(images)} images, title: {title}")

    # Create presentation (16:9 widescreen)
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    header_height = Inches(0.55)

    # Content area (below header, small margins)
    content_left = Inches(0.2)
    content_top = header_height + Inches(0.1)
    content_max_width = prs.slide_width - Inches(0.4)   # 12.933"
    content_max_height = prs.slide_height - header_height - Inches(0.25)  # ~6.7"

    for idx, image_bytes in enumerate(images):
        logger.info(f"Adding slide {idx + 1} of {len(images)}")

        blank_slide_layout = prs.slide_layouts[6]  # Blank layout
        slide = prs.slides.add_slide(blank_slide_layout)

        # Header bar
        header = slide.shapes.add_shape(
            1,  # Rectangle
            Inches(0), Inches(0),
            prs.slide_width, header_height
        )
        header.fill.solid()
        header.fill.fore_color.rgb = DD_NAVY
        header.line.fill.background()

        # Title in header
        title_box = slide.shapes.add_textbox(
            Inches(0.4), Inches(0.12),
            Inches(10), Inches(0.32)
        )
        text_frame = title_box.text_frame
        text_frame.text = f"{title} — Slide {idx + 1}"
        text_frame.paragraphs[0].font.size = Pt(16)
        text_frame.paragraphs[0].font.bold = True
        text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)

        # DD Consulting brand on the right
        logo_box = slide.shapes.add_textbox(
            prs.slide_width - Inches(2.8), Inches(0.14),
            Inches(2.5), Inches(0.3)
        )
        logo_frame = logo_box.text_frame
        logo_frame.text = "DD Consulting"
        logo_frame.paragraphs[0].font.size = Pt(13)
        logo_frame.paragraphs[0].font.bold = True
        logo_frame.paragraphs[0].font.color.rgb = DD_GOLD
        logo_frame.paragraphs[0].alignment = PP_ALIGN.RIGHT

        # ── FIT image with preserved aspect ratio ──
        # Read image dimensions to compute correct scale
        try:
            img = PILImage.open(BytesIO(image_bytes))
            img_w_px, img_h_px = img.size
        except Exception as e:
            logger.warning(f"Could not read image dims: {e}; using slide dims")
            img_w_px, img_h_px = (1600, 900)

        # Scale to fit content area, keeping aspect ratio
        max_w = content_max_width
        max_h = content_max_height
        # Determine scale using EMU-ratio (Inches are EMU-based, so we compare ratios)
        img_ratio = img_w_px / img_h_px
        slot_ratio = max_w / max_h

        if img_ratio >= slot_ratio:
            # Width-bound
            new_w = max_w
            new_h = int(max_w / img_ratio)
        else:
            # Height-bound
            new_h = max_h
            new_w = int(max_h * img_ratio)

        # Center the image within the content area
        left = content_left + int((max_w - new_w) / 2)
        top = content_top + int((max_h - new_h) / 2)

        image_stream = BytesIO(image_bytes)
        slide.shapes.add_picture(
            image_stream,
            left, top,
            width=new_w,
            height=new_h,
        )

        logger.info(f"Slide {idx + 1} added ({new_w} × {new_h} EMU)")

    pptx_stream = BytesIO()
    prs.save(pptx_stream)
    pptx_bytes = pptx_stream.getvalue()
    logger.info(f"PPTX generated: {len(pptx_bytes)} bytes")
    return pptx_bytes


async def build_project_ppt(project_id: str, token: str, frontend_base_url: str) -> bytes:
    """
    Generate PowerPoint for a project report.
    Uses per-section screenshots (data-export-section) so each section becomes
    its own 16:9 slide — avoids the "one giant squished image" problem.
    
    Args:
        project_id: The project ID
        token: JWT token for authentication
        frontend_base_url: Base URL of the frontend (e.g., http://localhost:3000)
    
    Returns:
        PPTX bytes
    """
    logger.info(f"Building project PPT for project_id={project_id}")
    url = f"{frontend_base_url}/print/projects/{project_id}/report?print=1&_t={token}"
    
    # Screenshot each report section separately → one slide per section.
    # Order matches the report body layout (Summary → Timeline → Overview → Budget → Risks → WBS).
    section_selectors = [
        "#report-header",
        "[data-export-section='summary']",
        "[data-export-section='timeline']",
        "[data-export-section='overview']",
        "[data-export-section='budget']",
        "[data-print-section='risks']",
        "[data-export-section='wbs']",
    ]

    # Larger viewport so per-section screenshots are high-res
    pngs = await render_screenshots(
        url,
        viewport={'width': 1600, 'height': 900},
        selectors=section_selectors,
    )

    # Fallback to full-page if none of the section selectors matched
    if not pngs:
        logger.warning("No section screenshots captured; falling back to full page")
        pngs = await render_screenshots(url, viewport={'width': 1600, 'height': 900})

    if not pngs:
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
    
    pngs = await render_screenshots(
        url,
        viewport={'width': 1600, 'height': 900},
        selectors=["#report-header", "[data-export-section='wbs']"],
    )
    if not pngs:
        # Fallback
        pngs = await render_screenshots(url, viewport={'width': 1600, 'height': 900})
    
    if not pngs:
        logger.warning("No screenshots captured, WBS report may be empty")
        raise ValueError("Failed to generate WBS report screenshots")
    
    pptx_bytes = _compose_pptx(pngs, title="Work Breakdown Structure")
    
    logger.info(f"WBS PPT generated: {len(pptx_bytes)} bytes, {len(pngs)} slide(s)")
    return pptx_bytes
