#!/usr/bin/env python3
"""
Backend Test: PDF Export with AI Status Summary Wait + Page-Flow Improvements
Review Request: Verify Status Summary cards stay whole, no sparse pages, 
and PDF waits for AI summary generation (NOT "Generating client status summary...")
"""

import requests
import time
import subprocess
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8001"
TEST_PROJECT_ID = "6ab25bc82be78e05e89230f3"  # Website Redesign - 30 WBS tasks, 4 risks, status update
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Test results
test_results = []
token = None

def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    result = f"{status}: {test_name}"
    if details:
        result += f" - {details}"
    test_results.append(result)
    print(result)
    return passed

def authenticate():
    """Authenticate and get JWT token"""
    global token
    print("\n=== AUTHENTICATION ===")
    
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={
            "username": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        log_test("Authentication", True, f"Token obtained for {ADMIN_EMAIL}")
        return True
    else:
        log_test("Authentication", False, f"HTTP {response.status_code}: {response.text}")
        return False

def test_pdf_export():
    """Test 1: PDF Export with AI Status Summary Wait"""
    print("\n=== TEST 1: PDF EXPORT WITH AI STATUS SUMMARY ===")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Measure render time
    start_time = time.time()
    response = requests.get(
        f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/export/pdf",
        headers=headers,
        timeout=30  # Allow up to 30s for AI summary generation
    )
    render_time = time.time() - start_time
    
    # Check HTTP 200
    if not log_test("PDF Export HTTP 200", response.status_code == 200, 
                    f"Status: {response.status_code}"):
        return False
    
    # Check Content-Type
    content_type = response.headers.get("Content-Type", "")
    log_test("PDF Content-Type", content_type == "application/pdf", 
             f"Content-Type: {content_type}")
    
    # Check PDF magic bytes
    pdf_content = response.content
    starts_with_pdf = pdf_content[:4] == b'%PDF'
    log_test("PDF Magic Bytes", starts_with_pdf, 
             f"Starts with: {pdf_content[:10]}")
    
    # Check file size (FULL report ~1.2MB, NOT ~4KB fallback)
    file_size_kb = len(pdf_content) / 1024
    file_size_mb = file_size_kb / 1024
    is_full_report = file_size_kb > 100  # Must be > 100KB (fallback is ~4KB)
    log_test("PDF Full Report Size", is_full_report, 
             f"Size: {file_size_kb:.1f} KB ({file_size_mb:.2f} MB)")
    
    # Report render time
    log_test("PDF Render Time", True, 
             f"Render time: {render_time:.2f}s (expected ~4-6s for AI summary wait)")
    
    # Save PDF for analysis
    pdf_path = f"/tmp/test_pdf_status_summary_{TEST_PROJECT_ID}.pdf"
    with open(pdf_path, "wb") as f:
        f.write(pdf_content)
    print(f"PDF saved to: {pdf_path}")
    
    # Get page count and page size using pdfinfo
    try:
        pdfinfo_output = subprocess.check_output(
            ["pdfinfo", pdf_path],
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Extract page count
        page_count_match = re.search(r'Pages:\s+(\d+)', pdfinfo_output)
        page_count = int(page_count_match.group(1)) if page_count_match else 0
        
        # Extract page size
        page_size_match = re.search(r'Page size:\s+([\d.]+)\s+x\s+([\d.]+)\s+pts', pdfinfo_output)
        if page_size_match:
            width = float(page_size_match.group(1))
            height = float(page_size_match.group(2))
            aspect_ratio = width / height if height > 0 else 0
            page_size = f"{width} x {height} pts (aspect ratio: {aspect_ratio:.2f})"
        else:
            page_size = "Unknown"
        
        log_test("PDF Page Count", page_count > 0, f"Pages: {page_count}")
        log_test("PDF Page Size", "960" in page_size and "540" in page_size, 
                 f"Page size: {page_size} (expected 960x540 for 16:9)")
        
    except subprocess.CalledProcessError as e:
        log_test("PDF Info Extraction", False, f"pdfinfo error: {e.output}")
        page_count = 0
    
    # Render all pages to PNG for visual inspection
    print("\n=== RENDERING PDF PAGES TO PNG ===")
    png_prefix = f"/tmp/pdf_page_status_summary_{TEST_PROJECT_ID}"
    try:
        subprocess.run(
            ["pdftoppm", "-png", "-r", "90", pdf_path, png_prefix],
            check=True,
            capture_output=True
        )
        
        # Count generated PNG files
        png_files = sorted(Path("/tmp").glob(f"pdf_page_status_summary_{TEST_PROJECT_ID}-*.png"))
        log_test("PDF Pages Rendered to PNG", len(png_files) == page_count, 
                 f"Rendered {len(png_files)} pages")
        
        print(f"PNG files: {[str(f) for f in png_files]}")
        
    except subprocess.CalledProcessError as e:
        log_test("PDF Page Rendering", False, f"pdftoppm error: {e.stderr.decode()}")
    
    # Visual verification instructions
    print("\n=== VISUAL VERIFICATION REQUIRED ===")
    print("Please manually inspect the PNG files for:")
    print("(a) KEY CHECK - Status Summary section shows REAL generated content:")
    print("    - Look for 'EXECUTIVE SUMMARY' block with actual sentences (mentions project/client)")
    print("    - Look for 'PROJECT OBJECTIVE' block")
    print("    - CONFIRM text 'Generating client status summary' does NOT appear")
    print("(b) NO near-blank/sparse page - every page should have substantial content")
    print("    - A page with >75% whitespace (only heading/footer) is a FAIL")
    print("    - Final page legitimately ends with content + closing footer")
    print("(c) WBS table columns:")
    print("    - Columns: Task/Phase/Start/End/Duration/Status/% Complete/Actuals vs Est.")
    print("    - Rightmost 'Actuals vs Est.' column fully visible (not clipped)")
    print("    - NO 'Deps' column should be present")
    
    # Automated check: Extract text from PDF to verify Status Summary content
    print("\n=== AUTOMATED TEXT EXTRACTION CHECK ===")
    try:
        pdf_text = subprocess.check_output(
            ["pdftotext", pdf_path, "-"],
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Check for "Generating client status summary" (should NOT be present)
        has_generating_text = "Generating client status summary" in pdf_text
        log_test("Status Summary NOT Generating", not has_generating_text, 
                 "Text 'Generating client status summary' NOT found" if not has_generating_text 
                 else "❌ CRITICAL: Found 'Generating client status summary' in PDF")
        
        # Check for real content indicators
        has_executive_summary = "EXECUTIVE SUMMARY" in pdf_text or "Executive Summary" in pdf_text
        has_project_objective = "PROJECT OBJECTIVE" in pdf_text or "Project Objective" in pdf_text
        
        log_test("Status Summary Has Executive Summary", has_executive_summary, 
                 "Found EXECUTIVE SUMMARY section" if has_executive_summary 
                 else "Executive Summary section not found")
        
        log_test("Status Summary Has Project Objective", has_project_objective, 
                 "Found PROJECT OBJECTIVE section" if has_project_objective 
                 else "Project Objective section not found")
        
        # Check for WBS table columns
        has_actuals_vs_est = "Actuals vs Est" in pdf_text or "ACTUALS VS EST" in pdf_text
        log_test("WBS Table Has 'Actuals vs Est' Column", has_actuals_vs_est, 
                 "Found 'Actuals vs Est' column in WBS table")
        
        # Save extracted text for manual review
        text_path = f"/tmp/test_pdf_text_{TEST_PROJECT_ID}.txt"
        with open(text_path, "w") as f:
            f.write(pdf_text)
        print(f"Extracted text saved to: {text_path}")
        
    except subprocess.CalledProcessError as e:
        log_test("PDF Text Extraction", False, f"pdftotext error: {e.output}")
    
    return True

def test_concurrency():
    """Test 2: Concurrent PDF Export Requests"""
    print("\n=== TEST 2: CONCURRENT PDF EXPORT ===")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    def export_pdf(request_num):
        """Single export request"""
        start_time = time.time()
        response = requests.get(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/export/pdf",
            headers=headers,
            timeout=30
        )
        elapsed = time.time() - start_time
        return {
            "request_num": request_num,
            "status_code": response.status_code,
            "size_kb": len(response.content) / 1024,
            "elapsed": elapsed,
            "content": response.content
        }
    
    # Fire 3 concurrent requests
    print("Firing 3 concurrent PDF export requests...")
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(export_pdf, i+1) for i in range(3)]
        results = [future.result() for future in as_completed(futures)]
    
    # Sort by request number
    results.sort(key=lambda x: x["request_num"])
    
    # Verify all returned HTTP 200
    all_200 = all(r["status_code"] == 200 for r in results)
    log_test("Concurrent Exports All HTTP 200", all_200, 
             f"Status codes: {[r['status_code'] for r in results]}")
    
    # Verify all are FULL PDFs (not fallback)
    all_full = all(r["size_kb"] > 100 for r in results)
    sizes = [f"{r['size_kb']:.1f} KB" for r in results]
    log_test("Concurrent Exports All Full PDFs", all_full, 
             f"Sizes: {sizes}")
    
    # Report timing
    times = [r["elapsed"] for r in results]
    log_test("Concurrent Export Timing", True, 
             f"Times: min={min(times):.2f}s, max={max(times):.2f}s, avg={sum(times)/len(times):.2f}s")
    
    # Check for 502/503/500 errors
    no_errors = all(r["status_code"] not in [500, 502, 503] for r in results)
    log_test("Concurrent Exports No Server Errors", no_errors, 
             "No 500/502/503 errors detected")
    
    return all_200 and all_full and no_errors

def test_regression():
    """Test 3: Regression Tests"""
    print("\n=== TEST 3: REGRESSION TESTS ===")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test PPT export
    response = requests.get(
        f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/export/ppt",
        headers=headers,
        timeout=30
    )
    
    ppt_ok = response.status_code == 200
    if ppt_ok:
        ppt_size_kb = len(response.content) / 1024
        is_valid_pptx = response.content[:2] == b'PK'  # ZIP magic bytes
        log_test("PPT Export", ppt_ok and is_valid_pptx, 
                 f"HTTP {response.status_code}, Size: {ppt_size_kb:.1f} KB, Valid PPTX: {is_valid_pptx}")
    else:
        log_test("PPT Export", False, f"HTTP {response.status_code}")
    
    # Test health endpoint
    response = requests.get(f"{BASE_URL}/api/health")
    health_ok = response.status_code == 200
    if health_ok:
        health_data = response.json()
        log_test("Health Endpoint", health_ok, 
                 f"Status: {health_data.get('status', 'unknown')}")
    else:
        log_test("Health Endpoint", False, f"HTTP {response.status_code}")
    
    # Test projects list
    response = requests.get(
        f"{BASE_URL}/api/projects",
        headers=headers
    )
    projects_ok = response.status_code == 200
    if projects_ok:
        projects = response.json()
        project_count = len(projects)
        log_test("Projects List", projects_ok, 
                 f"HTTP {response.status_code}, Count: {project_count} projects")
    else:
        log_test("Projects List", False, f"HTTP {response.status_code}")
    
    return ppt_ok and health_ok and projects_ok

def main():
    """Run all tests"""
    print("=" * 80)
    print("BACKEND TEST: PDF Export with AI Status Summary Wait + Page-Flow Improvements")
    print("=" * 80)
    
    # Authenticate
    if not authenticate():
        print("\n❌ Authentication failed. Aborting tests.")
        return
    
    # Run tests
    test_pdf_export()
    test_concurrency()
    test_regression()
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for r in test_results if "✅ PASS" in r)
    failed = sum(1 for r in test_results if "❌ FAIL" in r)
    total = len(test_results)
    
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed/total*100):.1f}%")
    
    print("\n" + "=" * 80)
    print("CRITICAL CHECKS (Manual Verification Required)")
    print("=" * 80)
    print("1. Status Summary shows REAL content (EXECUTIVE SUMMARY, PROJECT OBJECTIVE)")
    print("2. NO 'Generating client status summary' text in PDF")
    print("3. NO near-blank/sparse pages (>75% whitespace)")
    print("4. WBS table rightmost 'Actuals vs Est.' column fully visible (not clipped)")
    print("5. NO 'Deps' column in WBS table")
    print("\nPlease inspect PNG files in /tmp/pdf_page_status_summary_*.png")
    
    if failed == 0:
        print("\n✅ ALL AUTOMATED TESTS PASSED")
    else:
        print(f"\n❌ {failed} TEST(S) FAILED")

if __name__ == "__main__":
    main()
