"""
Playwright-based HTML rendering for PDF and screenshots.
"""
import os
import sys
import logging
import subprocess
from typing import Optional, List
from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger(__name__)

# Make sure Playwright knows where chromium lives. In this container, browsers
# are installed under /pw-browsers but Playwright defaults to ~/.cache/ms-playwright.
# Set the env var so Playwright finds them, regardless of how the process was started.
_PW_PATH = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
if not _PW_PATH:
    if os.path.isdir("/pw-browsers"):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/pw-browsers"
        logger.info("Set PLAYWRIGHT_BROWSERS_PATH=/pw-browsers")
    else:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/root/.cache/ms-playwright"
        logger.info("Set PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright (default)")


def _ensure_chromium_installed() -> None:
    """Best-effort check that Playwright's chromium is installed. If the
    expected executable is missing (e.g. container rebuild wiped /pw-browsers),
    try to install it on demand. Safe to call repeatedly — does nothing if
    chromium is already present."""
    pw_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    if pw_path and os.path.isdir(pw_path):
        # Look for any chromium_headless_shell-* directory
        try:
            for name in os.listdir(pw_path):
                if name.startswith("chromium_headless_shell-") and os.path.exists(
                    os.path.join(pw_path, name, "chrome-linux", "headless_shell")
                ):
                    return  # already installed
        except OSError:
            pass

    logger.warning("Chromium headless shell not found — installing on demand...")
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True,
            timeout=300,
            env={**os.environ},
        )
        logger.info("Chromium installed successfully")
    except Exception as e:
        logger.error(f"Failed to install chromium: {e}")
        # Don't raise — let the actual launch fail with a clear message


# Module-level browser instance (lazy initialization)
_browser: Optional[Browser] = None
_playwright = None


async def _get_browser() -> Browser:
    """Get or create a shared browser instance.

    Resilient to:
      • Container restarts (chromium re-installed on demand)
      • Browser process death (singleton is rebuilt on disconnect)
      • Launch failure (one retry after explicit install)
    """
    global _browser, _playwright

    # Fast path: existing connected browser
    if _browser is not None:
        try:
            if _browser.is_connected():
                return _browser
        except Exception:
            pass
        # Stale handle — drop it
        _browser = None

    # Cold path: install (if needed) and launch
    _ensure_chromium_installed()

    async def _do_launch():
        global _playwright, _browser
        if _playwright is None:
            _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
        )

    logger.info("Initializing Playwright browser (Chromium headless)")
    try:
        await _do_launch()
    except Exception as e:
        # Last-ditch: force re-install and retry once
        logger.warning(f"Browser launch failed ({e}); re-installing chromium and retrying...")
        _ensure_chromium_installed()
        await _do_launch()

    logger.info(f"Browser launched successfully: {_browser}")
    return _browser


async def render_pdf(
    url: str,
    *,
    landscape: bool = True,
    format: str = "A4",
    margin: dict = None,
    wait_selector: str = "[data-export-ready='true']",
    timeout_ms: int = 30000
) -> bytes:
    """
    Render a URL to PDF using headless Chromium.
    
    Args:
        url: The URL to render
        landscape: Use landscape orientation
        format: Paper format (A4, Letter, etc.)
        margin: Dict with top/bottom/left/right in mm (e.g., {'top': '8mm'})
        wait_selector: CSS selector to wait for before rendering
        timeout_ms: Maximum wait time in milliseconds
    
    Returns:
        PDF bytes
    """
    if margin is None:
        margin = {'top': '8mm', 'bottom': '8mm', 'left': '8mm', 'right': '8mm'}
    
    logger.info(f"Rendering PDF from URL: {url}")
    browser = await _get_browser()
    page = await browser.new_page()
    
    try:
        # Navigate to URL
        logger.info(f"Navigating to {url}")
        await page.goto(url, wait_until='networkidle', timeout=timeout_ms)
        
        # Wait for the ready indicator
        logger.info(f"Waiting for selector: {wait_selector}")
        await page.wait_for_selector(wait_selector, timeout=timeout_ms)
        
        # Small additional delay to ensure all rendering is complete
        await page.wait_for_timeout(500)
        
        # Generate PDF
        logger.info("Generating PDF")
        pdf_bytes = await page.pdf(
            format=format,
            landscape=landscape,
            print_background=True,
            margin=margin,
            prefer_css_page_size=False
        )
        
        logger.info(f"PDF generated successfully: {len(pdf_bytes)} bytes")
        return pdf_bytes
        
    except Exception as e:
        logger.error(f"Error rendering PDF: {e}")
        raise
    finally:
        await page.close()


async def render_screenshots(
    url: str,
    *,
    viewport: dict = None,
    selectors: List[str] = None,
    wait_selector: str = "[data-export-ready='true']",
    timeout_ms: int = 30000
) -> List[bytes]:
    """
    Render screenshots from a URL.
    
    Args:
        url: The URL to render
        viewport: Viewport size dict, e.g., {'width': 1600, 'height': 900}
        selectors: List of CSS selectors to screenshot individually.
                  If None, takes a single full-page screenshot.
        wait_selector: CSS selector to wait for before rendering
        timeout_ms: Maximum wait time in milliseconds
    
    Returns:
        List of PNG screenshot bytes
    """
    if viewport is None:
        viewport = {'width': 1600, 'height': 900}
    
    logger.info(f"Rendering screenshots from URL: {url}")
    browser = await _get_browser()
    page = await browser.new_page(
        viewport=viewport,
        device_scale_factor=2  # High DPI
    )
    
    try:
        # Navigate to URL
        logger.info(f"Navigating to {url}")
        await page.goto(url, wait_until='networkidle', timeout=timeout_ms)
        
        # Wait for the ready indicator
        logger.info(f"Waiting for selector: {wait_selector}")
        await page.wait_for_selector(wait_selector, timeout=timeout_ms)
        
        # Small additional delay to ensure all rendering is complete
        await page.wait_for_timeout(500)
        
        screenshots = []
        
        if selectors:
            # Take individual screenshots for each selector
            for selector in selectors:
                logger.info(f"Taking screenshot of: {selector}")
                element = await page.query_selector(selector)
                if element:
                    screenshot_bytes = await element.screenshot(type='png')
                    screenshots.append(screenshot_bytes)
                    logger.info(f"Screenshot captured: {len(screenshot_bytes)} bytes")
                else:
                    logger.warning(f"Selector not found: {selector}")
        else:
            # Take a single full-page screenshot
            logger.info("Taking full-page screenshot")
            screenshot_bytes = await page.screenshot(type='png', full_page=True)
            screenshots.append(screenshot_bytes)
            logger.info(f"Screenshot captured: {len(screenshot_bytes)} bytes")
        
        logger.info(f"Total screenshots captured: {len(screenshots)}")
        return screenshots
        
    except Exception as e:
        logger.error(f"Error rendering screenshots: {e}")
        raise
    finally:
        await page.close()


async def close_browser():
    """Close the shared browser instance."""
    global _browser
    if _browser:
        logger.info("Closing browser")
        await _browser.close()
        _browser = None
