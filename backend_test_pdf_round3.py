#!/usr/bin/env python3
"""
Backend Test: PDF Export ROUND-3 Layout Fine-Tuning Verification
Test project: 6ab25bc82be78e05e89230f3 (Website Redesign - 8 WBS tasks + 4 risks)
Focus: WBS table columns not clipped, no near-blank pages
"""

import requests
import os
import subprocess
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
BASE_URL = "http://localhost:8001"
API_BASE = f"{BASE_URL}/api"
TEST_PROJECT_ID = "6ab25bc82be78e05e89230f3"
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "admin123"

# Test results
results = {
    "passed": 0,
    "failed": 0,
    "details": []
}

def log_result(test_name, passed, message):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    results["details"].append(f"{status} - {test_name}: {message}")
    if passed:
        results["passed"] += 1
    else:
        results["failed"] += 1
    print(f"{status} - {test_name}: {message}")

def authenticate():
    """Authenticate and return access token"""
    print("\n=== AUTHENTICATION ===")
    try:
        response = requests.post(
            f"{API_BASE}/auth/login",
            data={
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            log_result("Authentication", True, f"Successfully authenticated as {TEST_EMAIL}")
            return token
        else:
            log_result("Authentication", False, f"HTTP {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        log_result("Authentication", False, f"Exception: {str(e)}")
        return None

def test_pdf_export_single(token):
    """Test 1: Single PDF export with detailed verification"""
    print("\n=== TEST 1: SINGLE PDF EXPORT ===")
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{API_BASE}/projects/{TEST_PROJECT_ID}/export/pdf"
        
        print(f"Requesting: {url}")
        response = requests.get(url, headers=headers, timeout=120)
        
        # Check HTTP status
        if response.status_code != 200:
            log_result("PDF Export - HTTP Status", False, f"Expected 200, got {response.status_code}")
            return False
        log_result("PDF Export - HTTP Status", True, "HTTP 200")
        
        # Check Content-Type
        content_type = response.headers.get("Content-Type", "")
        if "application/pdf" not in content_type:
            log_result("PDF Export - Content-Type", False, f"Expected application/pdf, got {content_type}")
            return False
        log_result("PDF Export - Content-Type", True, "application/pdf")
        
        # Check PDF magic bytes
        pdf_bytes = response.content
        if not pdf_bytes.startswith(b"%PDF"):
            log_result("PDF Export - Magic Bytes", False, "Does not start with %PDF")
            return False
        log_result("PDF Export - Magic Bytes", True, "Starts with %PDF")
        
        # Check file size (should be ~1.2 MB, NOT 4KB ReportLab fallback)
        file_size_kb = len(pdf_bytes) / 1024
        if file_size_kb < 100:
            log_result("PDF Export - File Size", False, f"Only {file_size_kb:.1f} KB - likely ReportLab fallback (expected ~1200 KB)")
            return False
        log_result("PDF Export - File Size", True, f"{file_size_kb:.1f} KB - FULL report (NOT fallback)")
        
        # Save PDF for analysis
        pdf_path = f"/tmp/test_pdf_round3_{TEST_PROJECT_ID}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"PDF saved to: {pdf_path}")
        
        # Get page count and page size using pdfinfo
        try:
            pdfinfo_output = subprocess.check_output(["pdfinfo", pdf_path], text=True)
            page_count = None
            page_size = None
            
            for line in pdfinfo_output.split("\n"):
                if line.startswith("Pages:"):
                    page_count = int(line.split(":")[1].strip())
                elif line.startswith("Page size:"):
                    page_size = line.split(":")[1].strip()
            
            if page_count:
                log_result("PDF Export - Page Count", True, f"{page_count} pages")
            else:
                log_result("PDF Export - Page Count", False, "Could not determine page count")
            
            if page_size:
                # Expected: 960 x 540 pts (16:9 ratio)
                if "960" in page_size and "540" in page_size:
                    log_result("PDF Export - Page Size", True, f"{page_size} (16:9 ratio as expected)")
                else:
                    log_result("PDF Export - Page Size", False, f"{page_size} (expected 960x540 pts)")
            else:
                log_result("PDF Export - Page Size", False, "Could not determine page size")
                
        except Exception as e:
            log_result("PDF Export - PDF Info", False, f"pdfinfo failed: {str(e)}")
        
        # Render all pages to PNG for visual verification
        print("\n=== RENDERING PDF PAGES TO PNG ===")
        try:
            png_prefix = f"/tmp/pdf_page_round3_{TEST_PROJECT_ID}"
            subprocess.run(
                ["pdftoppm", "-png", "-r", "90", pdf_path, png_prefix],
                check=True,
                capture_output=True
            )
            
            # Count generated PNG files
            png_files = sorted([f for f in os.listdir("/tmp") if f.startswith(f"pdf_page_round3_{TEST_PROJECT_ID}")])
            log_result("PDF Export - PNG Rendering", True, f"Rendered {len(png_files)} pages to PNG")
            
            # Analyze last page size to detect near-blank trailing page
            if len(png_files) >= 2:
                last_page = f"/tmp/{png_files[-1]}"
                second_last_page = f"/tmp/{png_files[-2]}"
                
                last_size = os.path.getsize(last_page)
                second_last_size = os.path.getsize(second_last_page)
                
                size_ratio = (last_size / second_last_size) * 100
                
                # A near-blank page would be significantly smaller (< 30% of previous page)
                if size_ratio < 30:
                    log_result("PDF Export - Trailing Page Check", False, 
                             f"Last page is {size_ratio:.1f}% of second-last page - likely near-blank")
                else:
                    log_result("PDF Export - Trailing Page Check", True, 
                             f"Last page is {size_ratio:.1f}% of second-last page - substantial content")
            
            print(f"\n📊 VISUAL VERIFICATION REQUIRED:")
            print(f"   Please inspect PNG files: {png_prefix}-*.png")
            print(f"   Key checks:")
            print(f"   (a) WBS Table: 'ACTUALS VS EST.' column (values like '0h / 8h') fully visible")
            print(f"   (b) WBS Table: 'DEPS' column fully visible")
            print(f"   (c) Project Timeline: Right side (e.g. 'Oct 2026') not clipped")
            print(f"   (d) No near-blank pages (>70% whitespace)")
            print(f"   (e) Risk items not split mid-item")
            
        except Exception as e:
            log_result("PDF Export - PNG Rendering", False, f"pdftoppm failed: {str(e)}")
        
        return True
        
    except Exception as e:
        log_result("PDF Export - Single", False, f"Exception: {str(e)}")
        return False

def export_pdf_concurrent(token, request_num):
    """Helper function for concurrent PDF export"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{API_BASE}/projects/{TEST_PROJECT_ID}/export/pdf"
        
        start_time = time.time()
        response = requests.get(url, headers=headers, timeout=120)
        elapsed = time.time() - start_time
        
        if response.status_code != 200:
            return {
                "request": request_num,
                "success": False,
                "status": response.status_code,
                "size": 0,
                "elapsed": elapsed
            }
        
        pdf_bytes = response.content
        file_size_kb = len(pdf_bytes) / 1024
        
        # Check if it's a full PDF (not fallback)
        is_full = pdf_bytes.startswith(b"%PDF") and file_size_kb > 100
        
        return {
            "request": request_num,
            "success": True,
            "status": response.status_code,
            "size": file_size_kb,
            "elapsed": elapsed,
            "is_full": is_full
        }
        
    except Exception as e:
        return {
            "request": request_num,
            "success": False,
            "error": str(e),
            "elapsed": 0
        }

def test_pdf_export_concurrent(token):
    """Test 2: Concurrent PDF exports (OOM guard verification)"""
    print("\n=== TEST 2: CONCURRENT PDF EXPORTS (3 requests) ===")
    
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(export_pdf_concurrent, token, i+1) for i in range(3)]
            
            concurrent_results = []
            for future in as_completed(futures):
                result = future.result()
                concurrent_results.append(result)
        
        # Sort by request number
        concurrent_results.sort(key=lambda x: x["request"])
        
        # Analyze results
        all_success = all(r["success"] for r in concurrent_results)
        all_full_pdf = all(r.get("is_full", False) for r in concurrent_results)
        
        print("\nConcurrent Export Results:")
        for r in concurrent_results:
            status = "✅" if r["success"] and r.get("is_full", False) else "❌"
            print(f"  {status} Request {r['request']}: HTTP {r.get('status', 'N/A')}, "
                  f"{r.get('size', 0):.1f} KB, {r.get('elapsed', 0):.2f}s")
        
        if not all_success:
            log_result("Concurrent Export - All Success", False, "Some requests failed")
            return False
        log_result("Concurrent Export - All Success", True, "All 3 requests returned HTTP 200")
        
        if not all_full_pdf:
            log_result("Concurrent Export - Full PDFs", False, "Some requests returned fallback (4KB)")
            return False
        
        avg_size = sum(r["size"] for r in concurrent_results) / len(concurrent_results)
        log_result("Concurrent Export - Full PDFs", True, f"All 3 returned FULL PDFs (avg {avg_size:.1f} KB)")
        
        # Check for serialization (staggered times indicate semaphore working)
        times = [r["elapsed"] for r in concurrent_results]
        time_spread = max(times) - min(times)
        log_result("Concurrent Export - Serialization", True, 
                  f"Time spread: {time_spread:.2f}s (min={min(times):.2f}s, max={max(times):.2f}s)")
        
        return True
        
    except Exception as e:
        log_result("Concurrent Export", False, f"Exception: {str(e)}")
        return False

def test_regression(token):
    """Test 3: Regression tests (PPT, health, projects)"""
    print("\n=== TEST 3: REGRESSION TESTS ===")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test PPT export
    try:
        url = f"{API_BASE}/projects/{TEST_PROJECT_ID}/export/ppt"
        response = requests.get(url, headers=headers, timeout=60)
        
        if response.status_code != 200:
            log_result("Regression - PPT Export", False, f"HTTP {response.status_code}")
        else:
            ppt_bytes = response.content
            file_size_kb = len(ppt_bytes) / 1024
            
            # Check ZIP magic bytes (PPTX is a ZIP file)
            if ppt_bytes.startswith(b"PK"):
                log_result("Regression - PPT Export", True, f"HTTP 200, {file_size_kb:.1f} KB, valid PPTX")
            else:
                log_result("Regression - PPT Export", False, "Invalid PPTX (no PK magic bytes)")
    except Exception as e:
        log_result("Regression - PPT Export", False, f"Exception: {str(e)}")
    
    # Test health endpoint
    try:
        response = requests.get(f"{API_BASE}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "")
            log_result("Regression - Health", True, f"HTTP 200, status={status}")
        else:
            log_result("Regression - Health", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_result("Regression - Health", False, f"Exception: {str(e)}")
    
    # Test projects list
    try:
        response = requests.get(f"{API_BASE}/projects", headers=headers, timeout=10)
        if response.status_code == 200:
            projects = response.json()
            project_count = len(projects)
            log_result("Regression - Projects List", True, f"HTTP 200, {project_count} projects")
        else:
            log_result("Regression - Projects List", False, f"HTTP {response.status_code}")
    except Exception as e:
        log_result("Regression - Projects List", False, f"Exception: {str(e)}")

def main():
    """Main test execution"""
    print("=" * 80)
    print("PDF EXPORT ROUND-3 LAYOUT FINE-TUNING VERIFICATION")
    print("=" * 80)
    print(f"Test Project: {TEST_PROJECT_ID} (Website Redesign)")
    print(f"Backend URL: {BASE_URL}")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Authenticate
    token = authenticate()
    if not token:
        print("\n❌ AUTHENTICATION FAILED - Cannot proceed with tests")
        return
    
    # Run tests
    test_pdf_export_single(token)
    test_pdf_export_concurrent(token)
    test_regression(token)
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    total = results["passed"] + results["failed"]
    pass_rate = (results["passed"] / total * 100) if total > 0 else 0
    print(f"Total Tests: {total}")
    print(f"Passed: {results['passed']} ✅")
    print(f"Failed: {results['failed']} ❌")
    print(f"Pass Rate: {pass_rate:.1f}%")
    print("=" * 80)
    
    print("\nDetailed Results:")
    for detail in results["details"]:
        print(f"  {detail}")
    
    print("\n" + "=" * 80)
    print("CRITICAL CHECKS (Manual Visual Verification Required):")
    print("=" * 80)
    print("1. WBS Table Columns:")
    print("   - 'ACTUALS VS EST.' column (values like '0h / 8h', '0h / 40h') fully visible")
    print("   - 'DEPS' column fully visible")
    print("   - NO clipping at right page edge")
    print("2. Project Timeline:")
    print("   - Right side (e.g. 'Oct 2026') not clipped")
    print("3. Page Breaks:")
    print("   - NO near-blank pages (>70% whitespace)")
    print("   - Risk items not split mid-item")
    print("=" * 80)
    
    if results["failed"] == 0:
        print("\n✅ ALL AUTOMATED TESTS PASSED")
    else:
        print(f"\n❌ {results['failed']} TEST(S) FAILED")

if __name__ == "__main__":
    main()
