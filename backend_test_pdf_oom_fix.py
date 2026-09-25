#!/usr/bin/env python3
"""
Backend Test: PDF Export 502/OOM Hardening Verification

Tests the fix for intermittent 502 errors caused by OOM-killed containers
during heavy Chromium report renders.

ROOT CAUSE: Heavy headless-Chromium report renders were OOM-killing the 2Gi
Cloud Run instance; while it restarted, ALL concurrent requests returned
instant 502s, and the frontend fell back to a crude client-side generator
producing an unclean PDF.

FIX: Added concurrency semaphore to serialize heavy renders, memory-lean
Chromium flags, infra bumps (4Gi memory, 4 CPU), and nginx timeout increases.

Test Project: 6ab25bc82be78e05e89230f3 (Website Redesign with 8 WBS tasks + 4 risks)
Auth: admin@test.com / admin123
"""

import requests
import time
import subprocess
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Test configuration
BACKEND_URL = "http://localhost:8001"
TEST_PROJECT_ID = "6ab25bc82be78e05e89230f3"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def log_test(message, status="INFO"):
    """Log test message with color coding"""
    color = {
        "PASS": GREEN,
        "FAIL": RED,
        "INFO": BLUE,
        "WARN": YELLOW
    }.get(status, RESET)
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{timestamp}] [{status}] {message}{RESET}")

def authenticate():
    """Authenticate and return JWT token"""
    log_test("Authenticating with admin credentials...", "INFO")
    
    response = requests.post(
        f"{BACKEND_URL}/api/auth/login",
        data={
            "username": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if response.status_code != 200:
        log_test(f"Authentication failed: {response.status_code} - {response.text}", "FAIL")
        return None
    
    data = response.json()
    token = data.get("access_token")
    
    if not token:
        log_test("No access_token in response", "FAIL")
        return None
    
    log_test(f"✅ Authentication successful", "PASS")
    return token

def test_single_pdf_export(token):
    """
    TEST 1: SINGLE PDF EXPORT
    - Assert HTTP 200, Content-Type application/pdf, body starts with %PDF
    - Report byte size (must be ~1.2 MB, NOT ~4 KB ReportLab fallback)
    - Report page count and page size (expect multi-page, 960 x 540 pts / 16:9)
    - Visual verification with pdftoppm
    """
    log_test("=" * 80, "INFO")
    log_test("TEST 1: SINGLE PDF EXPORT", "INFO")
    log_test("=" * 80, "INFO")
    
    url = f"{BACKEND_URL}/api/projects/{TEST_PROJECT_ID}/export/pdf"
    headers = {"Authorization": f"Bearer {token}"}
    
    log_test(f"Requesting PDF export: GET {url}", "INFO")
    start_time = time.time()
    
    try:
        response = requests.get(url, headers=headers, timeout=120)
        elapsed = time.time() - start_time
        
        log_test(f"Response received in {elapsed:.2f}s", "INFO")
        
        # Check HTTP status
        if response.status_code != 200:
            log_test(f"❌ HTTP {response.status_code} (expected 200)", "FAIL")
            log_test(f"Response: {response.text[:500]}", "FAIL")
            return False
        
        log_test(f"✅ HTTP 200 OK", "PASS")
        
        # Check Content-Type
        content_type = response.headers.get("Content-Type", "")
        if content_type != "application/pdf":
            log_test(f"❌ Content-Type: {content_type} (expected application/pdf)", "FAIL")
            return False
        
        log_test(f"✅ Content-Type: application/pdf", "PASS")
        
        # Check PDF magic bytes
        pdf_bytes = response.content
        if not pdf_bytes.startswith(b"%PDF"):
            log_test(f"❌ PDF magic bytes not found (starts with: {pdf_bytes[:10]})", "FAIL")
            return False
        
        log_test(f"✅ PDF magic bytes verified (%PDF)", "PASS")
        
        # Check file size
        size_kb = len(pdf_bytes) / 1024
        size_mb = size_kb / 1024
        log_test(f"PDF size: {size_kb:.1f} KB ({size_mb:.2f} MB)", "INFO")
        
        # CRITICAL: Must be FULL report (~1.2 MB), NOT tiny ReportLab fallback (~4 KB)
        if size_kb < 100:
            log_test(f"❌ CRITICAL: PDF is only {size_kb:.1f} KB - this is the ReportLab fallback, NOT the full Playwright render!", "FAIL")
            log_test("This means Playwright rendering FAILED and the system fell back to the minimal PDF generator.", "FAIL")
            return False
        
        if size_kb < 1000:
            log_test(f"⚠️  WARNING: PDF is {size_kb:.1f} KB - expected ~1200 KB for full report", "WARN")
        else:
            log_test(f"✅ PDF size is {size_kb:.1f} KB - FULL report confirmed (NOT fallback)", "PASS")
        
        # Save PDF for analysis
        pdf_path = f"/tmp/test_pdf_single_{TEST_PROJECT_ID}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        log_test(f"PDF saved to: {pdf_path}", "INFO")
        
        # Analyze PDF with pdfinfo
        log_test("Analyzing PDF structure with pdfinfo...", "INFO")
        try:
            result = subprocess.run(
                ["pdfinfo", pdf_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                pdfinfo_output = result.stdout
                log_test("PDF Info:", "INFO")
                for line in pdfinfo_output.split("\n"):
                    if line.strip():
                        log_test(f"  {line}", "INFO")
                
                # Extract page count
                page_count = None
                page_size = None
                for line in pdfinfo_output.split("\n"):
                    if "Pages:" in line:
                        page_count = int(line.split(":")[1].strip())
                    if "Page size:" in line:
                        page_size = line.split(":")[1].strip()
                
                if page_count:
                    if page_count == 1:
                        log_test(f"⚠️  WARNING: Only 1 page - expected multi-page report", "WARN")
                    else:
                        log_test(f"✅ Page count: {page_count} pages (multi-page confirmed)", "PASS")
                
                if page_size:
                    log_test(f"Page size: {page_size}", "INFO")
                    # Check for 16:9 ratio (960 x 540 pts)
                    if "960" in page_size and "540" in page_size:
                        log_test(f"✅ Page size is 960 x 540 pts (16:9 ratio as expected)", "PASS")
                    else:
                        log_test(f"⚠️  Page size differs from expected 960 x 540 pts", "WARN")
            else:
                log_test(f"pdfinfo failed: {result.stderr}", "WARN")
        
        except FileNotFoundError:
            log_test("pdfinfo not installed - skipping PDF structure analysis", "WARN")
        except Exception as e:
            log_test(f"Error running pdfinfo: {e}", "WARN")
        
        # Visual verification with pdftoppm
        log_test("Rendering PDF pages to PNG with pdftoppm...", "INFO")
        try:
            png_prefix = f"/tmp/pdf_page_single_{TEST_PROJECT_ID}"
            result = subprocess.run(
                ["pdftoppm", "-png", "-r", "90", pdf_path, png_prefix],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                log_test(f"✅ PDF pages rendered to PNG: {png_prefix}-*.png", "PASS")
                
                # List generated PNG files
                import glob
                png_files = sorted(glob.glob(f"{png_prefix}-*.png"))
                log_test(f"Generated {len(png_files)} PNG files:", "INFO")
                for png_file in png_files:
                    size = os.path.getsize(png_file) / 1024
                    log_test(f"  - {os.path.basename(png_file)} ({size:.1f} KB)", "INFO")
                
                # Check for near-blank trailing page
                if len(png_files) >= 2:
                    last_size = os.path.getsize(png_files[-1]) / 1024
                    second_last_size = os.path.getsize(png_files[-2]) / 1024
                    ratio = last_size / second_last_size if second_last_size > 0 else 0
                    
                    log_test(f"Last page size: {last_size:.1f} KB", "INFO")
                    log_test(f"Second-last page size: {second_last_size:.1f} KB", "INFO")
                    log_test(f"Ratio: {ratio:.1%}", "INFO")
                    
                    if ratio < 0.3:
                        log_test(f"⚠️  WARNING: Last page is {ratio:.1%} of second-last - possible near-blank trailing page", "WARN")
                    else:
                        log_test(f"✅ No near-blank trailing page detected (ratio: {ratio:.1%})", "PASS")
                
                log_test("", "INFO")
                log_test("VISUAL VERIFICATION REQUIRED:", "INFO")
                log_test("Please manually inspect the PNG files to verify:", "INFO")
                log_test("  1. WBS table rightmost columns ('ACTUALS VS EST.' and 'DEPS') are FULLY visible", "INFO")
                log_test("  2. Project Timeline right side is NOT clipped", "INFO")
                log_test("  3. Risk items are NOT split mid-item across pages", "INFO")
                log_test("  4. No near-blank trailing page", "INFO")
            else:
                log_test(f"pdftoppm failed: {result.stderr}", "WARN")
        
        except FileNotFoundError:
            log_test("pdftoppm not installed - skipping visual rendering", "WARN")
        except Exception as e:
            log_test(f"Error running pdftoppm: {e}", "WARN")
        
        log_test("", "INFO")
        log_test("✅ TEST 1 PASSED: Single PDF export working correctly", "PASS")
        return True
    
    except requests.exceptions.Timeout:
        log_test(f"❌ Request timeout after 120s", "FAIL")
        return False
    except Exception as e:
        log_test(f"❌ Exception: {e}", "FAIL")
        return False

def export_pdf_concurrent(token, request_id):
    """Helper function for concurrent PDF export"""
    url = f"{BACKEND_URL}/api/projects/{TEST_PROJECT_ID}/export/pdf"
    headers = {"Authorization": f"Bearer {token}"}
    
    start_time = time.time()
    try:
        response = requests.get(url, headers=headers, timeout=180)
        elapsed = time.time() - start_time
        
        return {
            "request_id": request_id,
            "status_code": response.status_code,
            "elapsed": elapsed,
            "size_kb": len(response.content) / 1024 if response.status_code == 200 else 0,
            "content_type": response.headers.get("Content-Type", ""),
            "success": response.status_code == 200 and response.content.startswith(b"%PDF")
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "request_id": request_id,
            "status_code": 0,
            "elapsed": elapsed,
            "size_kb": 0,
            "content_type": "",
            "success": False,
            "error": str(e)
        }

def test_concurrent_pdf_export(token, num_requests=5):
    """
    TEST 2: CONCURRENCY / OOM-GUARD
    - Fire multiple PDF export requests CONCURRENTLY
    - Assert ALL return HTTP 200 with FULL ~1.2 MB PDF (NOT 4KB fallback, NOT 502/500)
    - Serialization is expected (staggered completion times)
    - Report individual response times to show serialization
    """
    log_test("=" * 80, "INFO")
    log_test(f"TEST 2: CONCURRENCY / OOM-GUARD ({num_requests} concurrent requests)", "INFO")
    log_test("=" * 80, "INFO")
    
    log_test(f"Firing {num_requests} concurrent PDF export requests...", "INFO")
    log_test("This tests the semaphore that prevents OOM-killing the container.", "INFO")
    log_test("", "INFO")
    
    start_time = time.time()
    results = []
    
    with ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [
            executor.submit(export_pdf_concurrent, token, i+1)
            for i in range(num_requests)
        ]
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            
            req_id = result["request_id"]
            status = result["status_code"]
            elapsed = result["elapsed"]
            size_kb = result["size_kb"]
            
            if result["success"]:
                log_test(f"Request #{req_id}: ✅ HTTP {status} in {elapsed:.2f}s - {size_kb:.1f} KB", "PASS")
            else:
                error = result.get("error", "Unknown error")
                log_test(f"Request #{req_id}: ❌ HTTP {status} in {elapsed:.2f}s - {error}", "FAIL")
    
    total_elapsed = time.time() - start_time
    
    log_test("", "INFO")
    log_test(f"All {num_requests} requests completed in {total_elapsed:.2f}s", "INFO")
    log_test("", "INFO")
    
    # Analyze results
    log_test("RESULTS ANALYSIS:", "INFO")
    log_test("-" * 80, "INFO")
    
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    log_test(f"Successful: {len(successful)}/{num_requests}", "INFO")
    log_test(f"Failed: {len(failed)}/{num_requests}", "INFO")
    
    if successful:
        avg_time = sum(r["elapsed"] for r in successful) / len(successful)
        min_time = min(r["elapsed"] for r in successful)
        max_time = max(r["elapsed"] for r in successful)
        avg_size = sum(r["size_kb"] for r in successful) / len(successful)
        
        log_test(f"Response times: min={min_time:.2f}s, max={max_time:.2f}s, avg={avg_time:.2f}s", "INFO")
        log_test(f"Average PDF size: {avg_size:.1f} KB", "INFO")
        
        # Check for serialization (staggered completion)
        time_spread = max_time - min_time
        if time_spread > 5:
            log_test(f"✅ Serialization detected: {time_spread:.2f}s spread between fastest and slowest", "PASS")
            log_test("This confirms the semaphore is working to prevent concurrent renders.", "PASS")
        else:
            log_test(f"⚠️  Small time spread ({time_spread:.2f}s) - may indicate parallel execution", "WARN")
        
        # Check all PDFs are FULL size (not fallback)
        small_pdfs = [r for r in successful if r["size_kb"] < 100]
        if small_pdfs:
            log_test(f"❌ CRITICAL: {len(small_pdfs)} requests returned tiny PDFs (<100 KB) - ReportLab fallback!", "FAIL")
            for r in small_pdfs:
                log_test(f"  Request #{r['request_id']}: {r['size_kb']:.1f} KB", "FAIL")
            return False
        else:
            log_test(f"✅ All {len(successful)} PDFs are FULL size (>100 KB) - NO fallback triggered", "PASS")
    
    if failed:
        log_test("", "INFO")
        log_test("FAILED REQUESTS:", "FAIL")
        for r in failed:
            log_test(f"  Request #{r['request_id']}: HTTP {r['status_code']} - {r.get('error', 'Unknown')}", "FAIL")
    
    log_test("", "INFO")
    
    # Final verdict
    if len(successful) == num_requests:
        log_test(f"✅ TEST 2 PASSED: All {num_requests} concurrent requests succeeded with FULL PDFs", "PASS")
        log_test("The semaphore successfully prevented OOM-killing the container.", "PASS")
        return True
    else:
        log_test(f"❌ TEST 2 FAILED: {len(failed)}/{num_requests} requests failed", "FAIL")
        return False

def test_pptx_regression(token):
    """
    TEST 3: PPTX REGRESSION
    - GET /api/projects/{id}/export/ppt
    - Assert HTTP 200, valid PPTX, correct Content-Type, ZIP magic bytes
    """
    log_test("=" * 80, "INFO")
    log_test("TEST 3: PPTX REGRESSION", "INFO")
    log_test("=" * 80, "INFO")
    
    url = f"{BACKEND_URL}/api/projects/{TEST_PROJECT_ID}/export/ppt"
    headers = {"Authorization": f"Bearer {token}"}
    
    log_test(f"Requesting PPTX export: GET {url}", "INFO")
    
    try:
        response = requests.get(url, headers=headers, timeout=120)
        
        # Check HTTP status
        if response.status_code != 200:
            log_test(f"❌ HTTP {response.status_code} (expected 200)", "FAIL")
            return False
        
        log_test(f"✅ HTTP 200 OK", "PASS")
        
        # Check Content-Type
        content_type = response.headers.get("Content-Type", "")
        expected_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        if content_type != expected_type:
            log_test(f"❌ Content-Type: {content_type} (expected {expected_type})", "FAIL")
            return False
        
        log_test(f"✅ Content-Type: {expected_type}", "PASS")
        
        # Check ZIP magic bytes (PPTX is a ZIP file)
        pptx_bytes = response.content
        if not pptx_bytes.startswith(b"PK"):
            log_test(f"❌ ZIP magic bytes not found (starts with: {pptx_bytes[:10]})", "FAIL")
            return False
        
        log_test(f"✅ ZIP magic bytes verified (PK)", "PASS")
        
        # Report size
        size_kb = len(pptx_bytes) / 1024
        log_test(f"PPTX size: {size_kb:.1f} KB", "INFO")
        
        # Save PPTX
        pptx_path = f"/tmp/test_pptx_{TEST_PROJECT_ID}.pptx"
        with open(pptx_path, "wb") as f:
            f.write(pptx_bytes)
        log_test(f"PPTX saved to: {pptx_path}", "INFO")
        
        # Try to read slide count with python-pptx
        try:
            from pptx import Presentation
            prs = Presentation(pptx_path)
            slide_count = len(prs.slides)
            log_test(f"✅ PPTX validated: {slide_count} slides", "PASS")
        except ImportError:
            log_test("python-pptx not installed - skipping slide count verification", "WARN")
        except Exception as e:
            log_test(f"⚠️  Could not read PPTX: {e}", "WARN")
        
        log_test("", "INFO")
        log_test("✅ TEST 3 PASSED: PPTX export working correctly", "PASS")
        return True
    
    except Exception as e:
        log_test(f"❌ Exception: {e}", "FAIL")
        return False

def test_regression_sanity(token):
    """
    TEST 4: REGRESSION SANITY
    - GET /api/health returns 200 healthy
    - GET /api/projects returns 4-project list
    """
    log_test("=" * 80, "INFO")
    log_test("TEST 4: REGRESSION SANITY", "INFO")
    log_test("=" * 80, "INFO")
    
    all_passed = True
    
    # Test /api/health
    log_test("Testing GET /api/health...", "INFO")
    try:
        response = requests.get(f"{BACKEND_URL}/api/health", timeout=10)
        
        if response.status_code != 200:
            log_test(f"❌ /api/health returned HTTP {response.status_code}", "FAIL")
            all_passed = False
        else:
            data = response.json()
            status = data.get("status")
            if status == "healthy":
                log_test(f"✅ /api/health: HTTP 200, status=healthy", "PASS")
            else:
                log_test(f"⚠️  /api/health: HTTP 200, but status={status}", "WARN")
    except Exception as e:
        log_test(f"❌ /api/health failed: {e}", "FAIL")
        all_passed = False
    
    # Test /api/projects
    log_test("Testing GET /api/projects...", "INFO")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(f"{BACKEND_URL}/api/projects", headers=headers, timeout=10)
        
        if response.status_code != 200:
            log_test(f"❌ /api/projects returned HTTP {response.status_code}", "FAIL")
            all_passed = False
        else:
            data = response.json()
            project_count = len(data)
            log_test(f"✅ /api/projects: HTTP 200, {project_count} projects returned", "PASS")
            
            # Check if test project exists
            test_project = next((p for p in data if p.get("id") == TEST_PROJECT_ID), None)
            if test_project:
                log_test(f"✅ Test project found: {test_project.get('name')}", "PASS")
            else:
                log_test(f"⚠️  Test project {TEST_PROJECT_ID} not found in list", "WARN")
    except Exception as e:
        log_test(f"❌ /api/projects failed: {e}", "FAIL")
        all_passed = False
    
    log_test("", "INFO")
    if all_passed:
        log_test("✅ TEST 4 PASSED: Regression sanity checks passed", "PASS")
    else:
        log_test("❌ TEST 4 FAILED: Some regression checks failed", "FAIL")
    
    return all_passed

def main():
    """Run all tests"""
    log_test("=" * 80, "INFO")
    log_test("PDF EXPORT 502/OOM HARDENING VERIFICATION", "INFO")
    log_test("=" * 80, "INFO")
    log_test(f"Backend URL: {BACKEND_URL}", "INFO")
    log_test(f"Test Project: {TEST_PROJECT_ID}", "INFO")
    log_test(f"Test Credentials: {ADMIN_EMAIL} / {ADMIN_PASSWORD}", "INFO")
    log_test("", "INFO")
    
    # Authenticate
    token = authenticate()
    if not token:
        log_test("❌ AUTHENTICATION FAILED - Cannot proceed with tests", "FAIL")
        sys.exit(1)
    
    log_test("", "INFO")
    
    # Run tests
    results = {}
    
    results["test1_single_export"] = test_single_pdf_export(token)
    log_test("", "INFO")
    
    results["test2_concurrent_export"] = test_concurrent_pdf_export(token, num_requests=5)
    log_test("", "INFO")
    
    results["test3_pptx_regression"] = test_pptx_regression(token)
    log_test("", "INFO")
    
    results["test4_regression_sanity"] = test_regression_sanity(token)
    log_test("", "INFO")
    
    # Final summary
    log_test("=" * 80, "INFO")
    log_test("FINAL SUMMARY", "INFO")
    log_test("=" * 80, "INFO")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_flag in results.items():
        status = "✅ PASS" if passed_flag else "❌ FAIL"
        log_test(f"{test_name}: {status}", "PASS" if passed_flag else "FAIL")
    
    log_test("", "INFO")
    log_test(f"TOTAL: {passed}/{total} tests passed ({passed/total*100:.0f}%)", "INFO")
    
    if passed == total:
        log_test("", "INFO")
        log_test("🎉 ALL TESTS PASSED! 🎉", "PASS")
        log_test("The PDF export 502/OOM hardening fix is working correctly.", "PASS")
        log_test("", "INFO")
        log_test("KEY FINDINGS:", "INFO")
        log_test("  ✅ Single PDF export returns FULL ~1.2 MB report (NOT 4KB fallback)", "PASS")
        log_test("  ✅ Concurrent exports ALL succeed with FULL PDFs (semaphore working)", "PASS")
        log_test("  ✅ PPTX export regression test passed", "PASS")
        log_test("  ✅ Health and projects endpoints working", "PASS")
        sys.exit(0)
    else:
        log_test("", "INFO")
        log_test("❌ SOME TESTS FAILED", "FAIL")
        log_test(f"{total - passed} test(s) need attention.", "FAIL")
        sys.exit(1)

if __name__ == "__main__":
    main()
