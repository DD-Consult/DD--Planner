# PDF Export 503 Error - Investigation Report

**Date**: September 21, 2025  
**Issue**: PDF export endpoints failing with 503 Service Unavailable error  
**Status**: ✅ RESOLVED

---

## Summary

The PDF export feature was failing with a 503 error because Playwright's Chromium browser binaries were not installed correctly in the running container. The issue was caused by a version mismatch between the Playwright library and the installed Chromium version.

---

## Root Cause Analysis

### 1. **Version Mismatch**
- **Installed Playwright version**: 1.49.1 (from `requirements.txt` line 129)
- **Expected Chromium version**: 1148 (chromium_headless_shell-1148)
- **Actual Chromium version in container**: 1208 (chromium_headless_shell-1208)

### 2. **How This Happened**
The Docker image was built with an older version of Playwright that installed Chromium version 1208. Later, the `requirements.txt` was updated to Playwright 1.49.1, which expects Chromium version 1148. When the container runs:

1. Python dependencies (including Playwright 1.49.1) are installed
2. However, the Chromium browser binaries are NOT re-downloaded (they're baked into the Docker image at build time)
3. Playwright 1.49.1 looks for `/pw-browsers/chromium_headless_shell-1148/chrome-linux/headless_shell`
4. But only `/pw-browsers/chromium_headless_shell-1208/chrome-linux/headless_shell` exists
5. Browser launch fails → PDF export returns 503

### 3. **Evidence from Logs**
```
[STARTUP-BG] Playwright pre-warm failed (retries on demand): 
BrowserType.launch: Executable doesn't exist at /pw-browsers/chromium_headless_shell-1148/chrome-linux/headless_shell
╔════════════════════════════════════════════════════════════╗
║ Looks like Playwright was just installed or updated.       ║
║ Please run the following command to download new browsers: ║
║                                                            ║
║     playwright install                                     ║
╚════════════════════════════════════════════════════════════╝
```

---

## Affected Components

### 1. **Backend Routes** (`/app/backend/routes/reports.py`)
Four PDF/PPT export endpoints were affected:
- `GET /api/projects/{project_id}/export/pdf` (line 904-933)
- `GET /api/projects/{project_id}/export/ppt` (line 936-965)
- `GET /api/projects/{project_id}/export/wbs/pdf` (line 968-992)
- `GET /api/projects/{project_id}/export/wbs/ppt` (line 995-1019)

### 2. **Export Services** (`/app/backend/services/exports/`)
- **pdf_export.py**: Uses Playwright to render HTML to PDF
  - `build_project_pdf()` - Generates project report PDF
  - `build_wbs_pdf()` - Generates WBS PDF
  
- **ppt_export.py**: Uses Playwright to capture screenshots for PowerPoint slides
  - `build_project_ppt()` - Generates project report PowerPoint
  - `build_wbs_ppt()` - Generates WBS PowerPoint
  
- **renderer.py**: Core Playwright integration
  - `render_pdf()` - HTML to PDF conversion
  - `render_screenshots()` - HTML to PNG screenshots
  - `_get_browser()` - Browser singleton management
  - `_ensure_chromium_installed()` - On-demand Chromium installation

### 3. **Test Script** (`/app/backend/test_pdf_export.py`)
A test script exists but had a bug (missing `request` parameter). Fixed during investigation.

---

## Solution Implemented

### Immediate Fix (Applied)
Installed the correct Chromium version matching Playwright 1.49.1:

```bash
cd /app/backend
python3 -m playwright install chromium
```

**Result**: Downloaded and installed chromium_headless_shell-1148 (103 MB) to `/pw-browsers/`

### Verification
```bash
python3 test_pdf_export.py
```

**Output**:
```
✅ Test PASSED: PDF export endpoint is working!
✅ PDF generated successfully!
   Size: 1,120,510 bytes (1094.2 KB)
   Content-Type: application/pdf
```

The browser now launches successfully:
```
INFO:services.exports.renderer:Browser launched successfully: 
<Browser type=<BrowserType name=chromium executable_path=/pw-browsers/chromium-1148/chrome-linux/chrome> version=131.0.6778.33>
```

---

## System Dependencies Status

All required system dependencies for Chromium are already installed in the container:

✅ libnss3, libatk1.0-0, libatk-bridge2.0-0  
✅ libcups2, libdrm2, libxkbcommon0  
✅ libxcomposite1, libxdamage1, libxfixes3  
✅ libxrandr2, libgbm1, libpango-1.0-0  
✅ libcairo2, libasound2, fonts-liberation

Verified with:
```bash
python3 -m playwright install-deps chromium
# Output: 0 upgraded, 0 newly installed, 0 to remove
```

---

## Long-Term Solution

### Dockerfile Configuration
The Dockerfile (`/app/Dockerfile` lines 42-45) already has the correct configuration:

```dockerfile
# Install Playwright Chromium for PDF/PPT exports
ENV PLAYWRIGHT_BROWSERS_PATH=/pw-browsers
RUN python -m playwright install chromium
```

**Action Required**: Rebuild the Docker image to ensure Chromium version 1148 is baked into the image.

When the Docker image is rebuilt:
1. Playwright 1.49.1 will be installed (from requirements.txt)
2. `playwright install chromium` will download the matching Chromium 1148
3. Future container instances will have the correct version from the start

---

## Architecture Notes

### PDF Export Implementation
The PDF export uses a sophisticated "pixel-perfect" approach:

1. **Frontend Rendering**: The React UI renders the report at a special `/print/projects/:id/report` route
2. **Playwright Browser**: Headless Chromium navigates to this URL with authentication token
3. **Wait for Ready**: Waits for `[data-export-ready='true']` selector before capturing
4. **PDF Generation**: Uses Chrome's native PDF engine with 16:9 widescreen dimensions (13.333" × 7.5")
5. **Response**: Returns PDF bytes as downloadable file

This approach ensures the PDF looks **exactly** like the on-screen report, including:
- All styling and formatting
- Charts and graphs
- Dynamic content
- Brand colors and logos

### Browser Singleton Pattern
The renderer uses a module-level browser singleton (`_browser`) with:
- **Lazy initialization**: Browser is created on first use
- **Resilience**: Auto-reconnects if browser process dies
- **On-demand installation**: If Chromium is missing, attempts to install it automatically
- **Shared across requests**: Reduces overhead of launching a new browser per request

### Pre-warming Strategy
The FastAPI server pre-warms the browser on startup (`server.py` line 368-375):

```python
async def _prewarm_playwright():
    try:
        from services.exports.renderer import _ensure_chromium_installed, _get_browser
        _ensure_chromium_installed()
        await _get_browser()
        print("[STARTUP-BG] Playwright Chromium pre-warmed")
    except Exception as e:
        print(f"[STARTUP-BG] Playwright pre-warm failed (retries on demand): {e}")
```

This ensures:
- First PDF export request doesn't have to wait for browser launch
- Any missing dependencies are caught at startup
- Graceful degradation if pre-warming fails (retry on first request)

---

## Testing

### Test Coverage
1. ✅ Project PDF export (`/api/projects/{id}/export/pdf`)
2. ✅ Browser launch and singleton management
3. ✅ System dependencies validation
4. ⚠️ WBS PDF export (not explicitly tested, but uses same renderer)
5. ⚠️ PowerPoint exports (not explicitly tested, but uses same renderer)

### Test Results
```bash
# Test 1: PDF Export
python3 /app/backend/test_pdf_export.py
# Result: ✅ PASSED - 1.1 MB PDF generated successfully

# Test 2: Browser Pre-warming
tail -f /var/log/supervisor/backend.*.log | grep Playwright
# Result: ✅ Browser launched successfully (version 131.0.6778.33)
```

---

## Recommendations

### Immediate Actions
1. ✅ **DONE**: Install Chromium 1148 in running container
2. ✅ **DONE**: Verify PDF export works
3. 📋 **TODO**: Rebuild Docker image with correct Chromium version
4. 📋 **TODO**: Test all export endpoints (PDF + PPT for both project and WBS)

### Future Improvements
1. **Version Pinning**: Consider pinning exact Playwright + Chromium versions in requirements.txt comments
2. **Health Check**: Add a `/api/health/exports` endpoint that verifies Playwright is ready
3. **Monitoring**: Add metrics for PDF generation time and success rate
4. **Error Handling**: Improve error messages when browser fails to launch
5. **Testing**: Add automated tests for all export endpoints in CI/CD pipeline

---

## Files Modified

### Fixed Files
- `/app/backend/test_pdf_export.py` - Added missing `request` parameter to test function

### Files Analyzed (No Changes)
- `/app/backend/routes/reports.py` - Export endpoints (working as designed)
- `/app/backend/services/exports/pdf_export.py` - PDF generation (working as designed)
- `/app/backend/services/exports/ppt_export.py` - PowerPoint generation (working as designed)
- `/app/backend/services/exports/renderer.py` - Playwright integration (working as designed)
- `/app/backend/server.py` - Pre-warming logic (working as designed)
- `/app/Dockerfile` - Build configuration (correct, needs rebuild)
- `/app/backend/requirements.txt` - Dependencies (correct)

---

## Conclusion

The 503 error was caused by a Playwright/Chromium version mismatch, not a code bug. The fix is simple (install correct Chromium version) and the architecture is well-designed with proper error handling and resilience.

**Current Status**: ✅ PDF export is fully functional in the running container  
**Next Step**: 📋 Rebuild Docker image to make the fix permanent

---

## Additional Notes

### Why 503 Service Unavailable?
The 503 error occurs when:
1. PDF export endpoint is called
2. `build_project_pdf()` calls `render_pdf()`
3. `render_pdf()` calls `_get_browser()`
4. `_get_browser()` tries to launch Chromium
5. Playwright can't find the browser executable → raises exception
6. FastAPI catches the exception and returns 500/503 error

The renderer has retry logic and on-demand installation, but if the first attempt fails, the endpoint times out or returns 503.

### Browser Installation Location
Browsers are installed to `/pw-browsers/` (not the default `~/.cache/ms-playwright`) because:
1. Defined in Dockerfile: `ENV PLAYWRIGHT_BROWSERS_PATH=/pw-browsers`
2. Also set at runtime in `renderer.py` if not already set
3. This location is persistent across container restarts (as long as the Docker image includes it)

### Current Browser Versions
- chromium-1148 (131.0.6778.33) - ✅ Correct, newly installed
- chromium_headless_shell-1148 - ✅ Correct, newly installed
- chromium_headless_shell-1208 - ⚠️ Old version, can be removed
- ffmpeg-1010 - ✅ Current
- ffmpeg-1011 - ⚠️ Old version, can be removed
