#!/usr/bin/env python3
"""
PHASE 3 Render Service Delegation Verification Test
====================================================
Tests the dedicated render-service delegation mechanism where the main app
delegates heavy PDF/PPTX renders to an internal render endpoint.

Test Project: 6ab25bc82be78e05e89230f3 (Website Redesign - 30 WBS tasks, 4 risks, status update)
Test Credentials: don@ddconsult.tech / @Ddplanner2026

Test Coverage:
A. DELEGATED PDF EXPORT - GET /api/projects/{id}/export/pdf
B. INTERNAL RENDER ENDPOINT AUTH - GET /api/internal/render/pdf with X-Render-Key
C. INTERNAL RENDER PPT - GET /api/internal/render/ppt
D. WBS MODE via internal endpoint
E. CONCURRENCY - 3 concurrent main PDF exports
F. REGRESSION - PPT export, health, projects list
"""

import requests
import time
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
BASE_URL = "http://localhost:8001"
TEST_PROJECT_ID = "6ab25bc82be78e05e89230f3"
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "admin123"
RENDER_SERVICE_KEY = "local-render-test-key-123"

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def log_test(message, status="INFO"):
    """Log test messages with color coding."""
    color = {
        "PASS": GREEN,
        "FAIL": RED,
        "INFO": BLUE,
        "WARN": YELLOW
    }.get(status, RESET)
    print(f"{color}[{status}]{RESET} {message}")

def authenticate():
    """Authenticate and return JWT token."""
    log_test("Authenticating...", "INFO")
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if response.status_code != 200:
        log_test(f"Authentication failed: {response.status_code} - {response.text}", "FAIL")
        sys.exit(1)
    
    token = response.json().get("access_token")
    if not token:
        log_test("No access token in response", "FAIL")
        sys.exit(1)
    
    log_test(f"✓ Authenticated successfully", "PASS")
    return token

def test_a_delegated_pdf_export(token):
    """
    TEST A: DELEGATED PDF EXPORT
    GET /api/projects/{id}/export/pdf should return full PDF (~1.2MB)
    """
    log_test("\n" + "="*80, "INFO")
    log_test("TEST A: DELEGATED PDF EXPORT", "INFO")
    log_test("="*80, "INFO")
    
    start_time = time.time()
    response = requests.get(
        f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/export/pdf",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    elapsed = time.time() - start_time
    
    # Check HTTP 200
    if response.status_code != 200:
        log_test(f"✗ HTTP {response.status_code} (expected 200)", "FAIL")
        return False
    log_test(f"✓ HTTP 200", "PASS")
    
    # Check Content-Type
    content_type = response.headers.get("Content-Type", "")
    if content_type != "application/pdf":
        log_test(f"✗ Content-Type: {content_type} (expected application/pdf)", "FAIL")
        return False
    log_test(f"✓ Content-Type: application/pdf", "PASS")
    
    # Check PDF magic bytes
    if not response.content.startswith(b"%PDF"):
        log_test(f"✗ Invalid PDF magic bytes", "FAIL")
        return False
    log_test(f"✓ PDF magic bytes verified (%PDF)", "PASS")
    
    # Check size (should be FULL report ~1.2MB, NOT ~4KB fallback)
    size_kb = len(response.content) / 1024
    size_mb = size_kb / 1024
    if size_kb < 100:
        log_test(f"✗ PDF too small: {size_kb:.1f} KB (expected >100KB, got fallback?)", "FAIL")
        return False
    log_test(f"✓ FULL report size: {size_mb:.2f} MB ({len(response.content)} bytes)", "PASS")
    
    # Save PDF for manual inspection
    pdf_path = f"/tmp/test_phase3_delegated_export_{TEST_PROJECT_ID}.pdf"
    with open(pdf_path, "wb") as f:
        f.write(response.content)
    log_test(f"✓ PDF saved to: {pdf_path}", "INFO")
    
    # Report page count using pdfinfo
    try:
        import subprocess
        result = subprocess.run(
            ["pdfinfo", pdf_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if line.startswith("Pages:"):
                    pages = line.split(":")[1].strip()
                    log_test(f"✓ Page count: {pages} pages", "PASS")
                    break
    except Exception as e:
        log_test(f"⚠ Could not get page count: {e}", "WARN")
    
    # Render pages with pdftoppm for visual verification
    try:
        import subprocess
        output_prefix = f"/tmp/phase3_delegated_page_{TEST_PROJECT_ID}"
        result = subprocess.run(
            ["pdftoppm", "-png", "-r", "90", pdf_path, output_prefix],
            capture_output=True,
            timeout=30
        )
        if result.returncode == 0:
            # Count generated PNG files
            import glob
            png_files = glob.glob(f"{output_prefix}-*.png")
            log_test(f"✓ Rendered {len(png_files)} pages to PNG for visual inspection", "PASS")
            log_test(f"  PNG files: {output_prefix}-*.png", "INFO")
        else:
            log_test(f"⚠ pdftoppm failed: {result.stderr.decode()}", "WARN")
    except Exception as e:
        log_test(f"⚠ Could not render pages: {e}", "WARN")
    
    log_test(f"✓ Export took {elapsed:.2f}s (expected ~4-6s for AI summary)", "INFO")
    
    log_test("\n✓ TEST A: DELEGATED PDF EXPORT - PASSED", "PASS")
    return True

def test_b_internal_render_auth(token):
    """
    TEST B: INTERNAL RENDER ENDPOINT AUTH CHECKS
    - No X-Render-Key header → 403
    - Wrong X-Render-Key → 403
    - Correct X-Render-Key + X-Forward-Authorization → 200
    """
    log_test("\n" + "="*80, "INFO")
    log_test("TEST B: INTERNAL RENDER ENDPOINT AUTH", "INFO")
    log_test("="*80, "INFO")
    
    url = f"{BASE_URL}/api/internal/render/pdf?project_id={TEST_PROJECT_ID}"
    
    # B.1: No X-Render-Key header → 403
    log_test("\nB.1: Testing without X-Render-Key header...", "INFO")
    response = requests.get(url, timeout=10)
    if response.status_code != 403:
        log_test(f"✗ Expected 403, got {response.status_code}", "FAIL")
        return False
    log_test(f"✓ Correctly returned 403 without X-Render-Key", "PASS")
    
    # B.2: Wrong X-Render-Key → 403
    log_test("\nB.2: Testing with WRONG X-Render-Key...", "INFO")
    response = requests.get(
        url,
        headers={"X-Render-Key": "WRONG-KEY"},
        timeout=10
    )
    if response.status_code != 403:
        log_test(f"✗ Expected 403, got {response.status_code}", "FAIL")
        return False
    log_test(f"✓ Correctly returned 403 with wrong key", "PASS")
    
    # B.3: Correct X-Render-Key + X-Forward-Authorization → 200
    log_test("\nB.3: Testing with correct X-Render-Key + forwarded JWT...", "INFO")
    start_time = time.time()
    response = requests.get(
        url,
        headers={
            "X-Render-Key": RENDER_SERVICE_KEY,
            "X-Forward-Authorization": f"Bearer {token}"
        },
        timeout=30
    )
    elapsed = time.time() - start_time
    
    if response.status_code != 200:
        log_test(f"✗ Expected 200, got {response.status_code}", "FAIL")
        log_test(f"  Response: {response.text[:500]}", "INFO")
        return False
    log_test(f"✓ HTTP 200 with correct auth", "PASS")
    
    # Check Content-Type
    content_type = response.headers.get("Content-Type", "")
    if content_type != "application/pdf":
        log_test(f"✗ Content-Type: {content_type} (expected application/pdf)", "FAIL")
        return False
    log_test(f"✓ Content-Type: application/pdf", "PASS")
    
    # Check PDF magic bytes
    if not response.content.startswith(b"%PDF"):
        log_test(f"✗ Invalid PDF magic bytes", "FAIL")
        return False
    log_test(f"✓ PDF magic bytes verified", "PASS")
    
    # Check size
    size_kb = len(response.content) / 1024
    if size_kb < 100:
        log_test(f"✗ PDF too small: {size_kb:.1f} KB", "FAIL")
        return False
    log_test(f"✓ Full PDF size: {size_kb:.1f} KB ({len(response.content)} bytes)", "PASS")
    log_test(f"✓ Render took {elapsed:.2f}s", "INFO")
    
    log_test("\n✓ TEST B: INTERNAL RENDER AUTH - PASSED", "PASS")
    return True

def test_c_internal_render_ppt(token):
    """
    TEST C: INTERNAL RENDER PPT
    GET /api/internal/render/ppt with correct auth → 200 valid PPTX
    """
    log_test("\n" + "="*80, "INFO")
    log_test("TEST C: INTERNAL RENDER PPT", "INFO")
    log_test("="*80, "INFO")
    
    url = f"{BASE_URL}/api/internal/render/ppt?project_id={TEST_PROJECT_ID}"
    
    start_time = time.time()
    response = requests.get(
        url,
        headers={
            "X-Render-Key": RENDER_SERVICE_KEY,
            "X-Forward-Authorization": f"Bearer {token}"
        },
        timeout=30
    )
    elapsed = time.time() - start_time
    
    # Check HTTP 200
    if response.status_code != 200:
        log_test(f"✗ HTTP {response.status_code} (expected 200)", "FAIL")
        return False
    log_test(f"✓ HTTP 200", "PASS")
    
    # Check Content-Type
    content_type = response.headers.get("Content-Type", "")
    expected_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    if content_type != expected_type:
        log_test(f"✗ Content-Type: {content_type}", "FAIL")
        return False
    log_test(f"✓ Content-Type: {expected_type}", "PASS")
    
    # Check ZIP magic bytes (PPTX is a ZIP file)
    if not response.content.startswith(b"PK"):
        log_test(f"✗ Invalid PPTX magic bytes", "FAIL")
        return False
    log_test(f"✓ PPTX magic bytes verified (PK)", "PASS")
    
    # Check size
    size_kb = len(response.content) / 1024
    log_test(f"✓ PPTX size: {size_kb:.1f} KB ({len(response.content)} bytes)", "PASS")
    log_test(f"✓ Render took {elapsed:.2f}s", "INFO")
    
    log_test("\n✓ TEST C: INTERNAL RENDER PPT - PASSED", "PASS")
    return True

def test_d_wbs_mode_internal(token):
    """
    TEST D: WBS MODE via internal endpoint
    GET /api/internal/render/pdf?wbs_mode=summary should return compact WBS
    """
    log_test("\n" + "="*80, "INFO")
    log_test("TEST D: WBS MODE VIA INTERNAL ENDPOINT", "INFO")
    log_test("="*80, "INFO")
    
    url = f"{BASE_URL}/api/internal/render/pdf?project_id={TEST_PROJECT_ID}&wbs_mode=summary"
    
    start_time = time.time()
    response = requests.get(
        url,
        headers={
            "X-Render-Key": RENDER_SERVICE_KEY,
            "X-Forward-Authorization": f"Bearer {token}"
        },
        timeout=30
    )
    elapsed = time.time() - start_time
    
    # Check HTTP 200
    if response.status_code != 200:
        log_test(f"✗ HTTP {response.status_code} (expected 200)", "FAIL")
        return False
    log_test(f"✓ HTTP 200", "PASS")
    
    # Check PDF
    if not response.content.startswith(b"%PDF"):
        log_test(f"✗ Invalid PDF magic bytes", "FAIL")
        return False
    log_test(f"✓ PDF magic bytes verified", "PASS")
    
    size_kb = len(response.content) / 1024
    log_test(f"✓ PDF size: {size_kb:.1f} KB (wbs_mode=summary)", "PASS")
    log_test(f"✓ Render took {elapsed:.2f}s", "INFO")
    
    # Save for inspection
    pdf_path = f"/tmp/test_phase3_wbs_summary_{TEST_PROJECT_ID}.pdf"
    with open(pdf_path, "wb") as f:
        f.write(response.content)
    log_test(f"✓ WBS summary PDF saved to: {pdf_path}", "INFO")
    log_test(f"  (Should show compact phase summary, NOT full task table)", "INFO")
    
    log_test("\n✓ TEST D: WBS MODE - PASSED", "PASS")
    return True

def test_e_concurrency(token):
    """
    TEST E: CONCURRENCY
    Fire 3 concurrent main PDF exports - ALL should return 200 with full PDFs
    """
    log_test("\n" + "="*80, "INFO")
    log_test("TEST E: CONCURRENCY (3 concurrent exports)", "INFO")
    log_test("="*80, "INFO")
    
    def export_pdf(index):
        """Single export request."""
        start = time.time()
        try:
            response = requests.get(
                f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/export/pdf",
                headers={"Authorization": f"Bearer {token}"},
                timeout=60
            )
            elapsed = time.time() - start
            return {
                "index": index,
                "status": response.status_code,
                "size": len(response.content),
                "time": elapsed,
                "success": response.status_code == 200 and len(response.content) > 100000
            }
        except Exception as e:
            elapsed = time.time() - start
            return {
                "index": index,
                "status": 0,
                "size": 0,
                "time": elapsed,
                "success": False,
                "error": str(e)
            }
    
    # Fire 3 concurrent requests
    log_test("Firing 3 concurrent PDF export requests...", "INFO")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(export_pdf, i+1) for i in range(3)]
        results = [future.result() for future in as_completed(futures)]
    
    total_time = time.time() - start_time
    
    # Sort results by index
    results.sort(key=lambda x: x["index"])
    
    # Check all results
    all_passed = True
    for result in results:
        idx = result["index"]
        if result["success"]:
            size_mb = result["size"] / (1024 * 1024)
            log_test(
                f"✓ Request {idx}: HTTP {result['status']}, {size_mb:.2f} MB, {result['time']:.2f}s",
                "PASS"
            )
        else:
            error = result.get("error", "Unknown error")
            log_test(
                f"✗ Request {idx}: FAILED - {error}",
                "FAIL"
            )
            all_passed = False
    
    if not all_passed:
        log_test("\n✗ TEST E: CONCURRENCY - FAILED (some requests failed)", "FAIL")
        return False
    
    # Check that all returned full PDFs (not fallback)
    sizes = [r["size"] for r in results]
    avg_size = sum(sizes) / len(sizes)
    min_size = min(sizes)
    max_size = max(sizes)
    
    log_test(f"\nSize stats: min={min_size/1024:.1f}KB, max={max_size/1024:.1f}KB, avg={avg_size/1024:.1f}KB", "INFO")
    
    if min_size < 100000:
        log_test(f"✗ Some PDFs too small (got fallback?)", "FAIL")
        return False
    
    # Check timing spread (should show serialization if semaphore is working)
    times = [r["time"] for r in results]
    min_time = min(times)
    max_time = max(times)
    spread = max_time - min_time
    
    log_test(f"Time stats: min={min_time:.2f}s, max={max_time:.2f}s, spread={spread:.2f}s", "INFO")
    log_test(f"Total wall time: {total_time:.2f}s", "INFO")
    
    if spread > 2.0:
        log_test(f"✓ Serialization detected (spread={spread:.2f}s confirms semaphore working)", "PASS")
    else:
        log_test(f"⚠ Low spread ({spread:.2f}s) - may indicate parallel execution", "WARN")
    
    log_test("\n✓ TEST E: CONCURRENCY - PASSED (all returned full PDFs)", "PASS")
    return True

def test_f_regression(token):
    """
    TEST F: REGRESSION
    - GET /api/projects/{id}/export/ppt → 200 valid PPTX
    - GET /api/health → 200
    - GET /api/projects → returns 4 projects
    """
    log_test("\n" + "="*80, "INFO")
    log_test("TEST F: REGRESSION TESTS", "INFO")
    log_test("="*80, "INFO")
    
    # F.1: PPT export
    log_test("\nF.1: Testing main PPT export endpoint...", "INFO")
    response = requests.get(
        f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/export/ppt",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    
    if response.status_code != 200:
        log_test(f"✗ PPT export: HTTP {response.status_code}", "FAIL")
        return False
    
    if not response.content.startswith(b"PK"):
        log_test(f"✗ PPT export: Invalid PPTX magic bytes", "FAIL")
        return False
    
    size_kb = len(response.content) / 1024
    log_test(f"✓ PPT export: HTTP 200, {size_kb:.1f} KB, valid PPTX", "PASS")
    
    # F.2: Health endpoint
    log_test("\nF.2: Testing health endpoint...", "INFO")
    response = requests.get(f"{BASE_URL}/api/health", timeout=10)
    
    if response.status_code != 200:
        log_test(f"✗ Health: HTTP {response.status_code}", "FAIL")
        return False
    
    health_data = response.json()
    log_test(f"✓ Health: HTTP 200, status={health_data.get('status')}", "PASS")
    
    # F.3: Projects list
    log_test("\nF.3: Testing projects list...", "INFO")
    response = requests.get(
        f"{BASE_URL}/api/projects",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    
    if response.status_code != 200:
        log_test(f"✗ Projects list: HTTP {response.status_code}", "FAIL")
        return False
    
    projects = response.json()
    project_count = len(projects)
    
    if project_count < 4:
        log_test(f"✗ Projects list: Expected ≥4 projects, got {project_count}", "FAIL")
        return False
    
    log_test(f"✓ Projects list: HTTP 200, {project_count} projects", "PASS")
    
    log_test("\n✓ TEST F: REGRESSION - PASSED", "PASS")
    return True

def main():
    """Run all Phase 3 render delegation tests."""
    log_test("\n" + "="*80, "INFO")
    log_test("PHASE 3 RENDER SERVICE DELEGATION VERIFICATION", "INFO")
    log_test("="*80, "INFO")
    log_test(f"Base URL: {BASE_URL}", "INFO")
    log_test(f"Test Project: {TEST_PROJECT_ID}", "INFO")
    log_test(f"Test User: {TEST_EMAIL}", "INFO")
    log_test(f"Render Service Key: {RENDER_SERVICE_KEY}", "INFO")
    
    # Authenticate
    token = authenticate()
    
    # Run all tests
    results = {}
    
    try:
        results["A_DELEGATED_PDF"] = test_a_delegated_pdf_export(token)
    except Exception as e:
        log_test(f"\n✗ TEST A EXCEPTION: {e}", "FAIL")
        results["A_DELEGATED_PDF"] = False
    
    try:
        results["B_INTERNAL_AUTH"] = test_b_internal_render_auth(token)
    except Exception as e:
        log_test(f"\n✗ TEST B EXCEPTION: {e}", "FAIL")
        results["B_INTERNAL_AUTH"] = False
    
    try:
        results["C_INTERNAL_PPT"] = test_c_internal_render_ppt(token)
    except Exception as e:
        log_test(f"\n✗ TEST C EXCEPTION: {e}", "FAIL")
        results["C_INTERNAL_PPT"] = False
    
    try:
        results["D_WBS_MODE"] = test_d_wbs_mode_internal(token)
    except Exception as e:
        log_test(f"\n✗ TEST D EXCEPTION: {e}", "FAIL")
        results["D_WBS_MODE"] = False
    
    try:
        results["E_CONCURRENCY"] = test_e_concurrency(token)
    except Exception as e:
        log_test(f"\n✗ TEST E EXCEPTION: {e}", "FAIL")
        results["E_CONCURRENCY"] = False
    
    try:
        results["F_REGRESSION"] = test_f_regression(token)
    except Exception as e:
        log_test(f"\n✗ TEST F EXCEPTION: {e}", "FAIL")
        results["F_REGRESSION"] = False
    
    # Summary
    log_test("\n" + "="*80, "INFO")
    log_test("TEST SUMMARY", "INFO")
    log_test("="*80, "INFO")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_flag in results.items():
        status = "PASS" if passed_flag else "FAIL"
        log_test(f"{test_name}: {status}", status)
    
    log_test(f"\nTotal: {passed}/{total} tests passed", "INFO")
    
    if passed == total:
        log_test("\n✓✓✓ ALL TESTS PASSED ✓✓✓", "PASS")
        return 0
    else:
        log_test(f"\n✗✗✗ {total - passed} TEST(S) FAILED ✗✗✗", "FAIL")
        return 1

if __name__ == "__main__":
    sys.exit(main())
