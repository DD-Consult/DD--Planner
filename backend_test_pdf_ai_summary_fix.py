#!/usr/bin/env python3
"""
Backend Test: PDF Export AI Status Summary Fix Verification
============================================================
Verifies the fix for the "Generating client status summary..." timing issue.

The fix raised render wait budgets:
- Frontend force-ready cap: 12s → 30s
- Backend renderer wait_for_selector: 15s → 35s
- Gemini call fail-fast: 18s per attempt

Test Project: 6ab25bc82be78e05e89230f3 (Website Redesign)
Auth: admin@test.com / admin123
Backend: http://localhost:8001
"""

import requests
import time
import subprocess
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8001"
TEST_PROJECT_ID = "6ab25bc82be78e05e89230f3"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Test results
test_results = []
pdf_files = []

def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    result = f"{status}: {test_name}"
    if details:
        result += f"\n    {details}"
    print(result)
    test_results.append({
        "test": test_name,
        "passed": passed,
        "details": details
    })
    return passed

def authenticate():
    """Authenticate and get access token"""
    print("\n" + "="*80)
    print("AUTHENTICATION")
    print("="*80)
    
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
        log_test("Authentication", True, f"Logged in as {ADMIN_EMAIL}")
        return token
    else:
        log_test("Authentication", False, f"HTTP {response.status_code}: {response.text[:200]}")
        return None

def export_pdf_single(token, test_name="PDF Export"):
    """Export PDF and return response details"""
    print(f"\n{'='*80}")
    print(f"{test_name.upper()}")
    print("="*80)
    
    start_time = time.time()
    
    response = requests.get(
        f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/export/pdf",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60  # Allow up to 60s for the export
    )
    
    elapsed = time.time() - start_time
    
    return {
        "status_code": response.status_code,
        "content_type": response.headers.get("Content-Type", ""),
        "content_length": len(response.content),
        "content": response.content,
        "elapsed": elapsed,
        "headers": dict(response.headers)
    }

def verify_pdf_structure(pdf_content, test_name="PDF Structure"):
    """Verify PDF structure and extract text"""
    print(f"\n{'='*80}")
    print(f"{test_name.upper()}")
    print("="*80)
    
    # Save PDF to temp file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = f"/tmp/test_pdf_ai_summary_{timestamp}.pdf"
    
    with open(pdf_path, "wb") as f:
        f.write(pdf_content)
    
    pdf_files.append(pdf_path)
    print(f"PDF saved to: {pdf_path}")
    
    # Check PDF magic bytes
    magic_bytes = pdf_content[:8]
    has_pdf_magic = magic_bytes.startswith(b"%PDF")
    log_test("PDF Magic Bytes", has_pdf_magic, f"Magic bytes: {magic_bytes}")
    
    # Get page count using pdfinfo
    try:
        pdfinfo_output = subprocess.check_output(
            ["pdfinfo", pdf_path],
            stderr=subprocess.STDOUT,
            text=True
        )
        
        page_count = None
        for line in pdfinfo_output.split("\n"):
            if line.startswith("Pages:"):
                page_count = int(line.split(":")[1].strip())
                break
        
        log_test("PDF Page Count", page_count is not None and page_count > 0, 
                f"Pages: {page_count}")
        
    except subprocess.CalledProcessError as e:
        log_test("PDF Page Count", False, f"pdfinfo failed: {e.output}")
        page_count = None
    
    # Extract text using pdftotext
    try:
        text_output = subprocess.check_output(
            ["pdftotext", pdf_path, "-"],
            stderr=subprocess.STDOUT,
            text=True
        )
        
        print(f"\nExtracted text length: {len(text_output)} characters")
        
        return {
            "path": pdf_path,
            "page_count": page_count,
            "text": text_output,
            "valid": has_pdf_magic and page_count is not None
        }
        
    except subprocess.CalledProcessError as e:
        log_test("PDF Text Extraction", False, f"pdftotext failed: {e.output}")
        return {
            "path": pdf_path,
            "page_count": page_count,
            "text": "",
            "valid": False
        }

def render_pdf_to_images(pdf_path, test_name="PDF Rendering"):
    """Render PDF pages to PNG images"""
    print(f"\n{'='*80}")
    print(f"{test_name.upper()}")
    print("="*80)
    
    output_prefix = pdf_path.replace(".pdf", "_page")
    
    try:
        subprocess.check_output(
            ["pdftoppm", "-png", "-r", "90", pdf_path, output_prefix],
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Count generated PNG files
        png_files = [f for f in os.listdir("/tmp") if f.startswith(os.path.basename(output_prefix)) and f.endswith(".png")]
        
        log_test("PDF Page Rendering", len(png_files) > 0, 
                f"Rendered {len(png_files)} pages to PNG")
        
        return png_files
        
    except subprocess.CalledProcessError as e:
        log_test("PDF Page Rendering", False, f"pdftoppm failed: {e.output}")
        return []

def check_critical_content(pdf_text, test_name="Critical Content Checks"):
    """Check for critical content issues"""
    print(f"\n{'='*80}")
    print(f"{test_name.upper()}")
    print("="*80)
    
    # CRITICAL CHECK (a): "Generating client status summary" must NOT appear
    has_generating_text = "Generating client status summary" in pdf_text
    log_test(
        "NO 'Generating client status summary'",
        not has_generating_text,
        "FOUND 'Generating client status summary' - FIX FAILED!" if has_generating_text 
        else "Text not found (correct)"
    )
    
    # CRITICAL CHECK (b): Status Summary must show REAL content
    has_executive_summary = "EXECUTIVE SUMMARY" in pdf_text
    has_project_objective = "PROJECT OBJECTIVE" in pdf_text
    
    log_test(
        "Status Summary - EXECUTIVE SUMMARY present",
        has_executive_summary,
        "Found 'EXECUTIVE SUMMARY'" if has_executive_summary 
        else "NOT FOUND - may indicate AI summary failed"
    )
    
    log_test(
        "Status Summary - PROJECT OBJECTIVE present",
        has_project_objective,
        "Found 'PROJECT OBJECTIVE'" if has_project_objective 
        else "NOT FOUND - may indicate AI summary failed"
    )
    
    # CRITICAL CHECK (c): Must NOT show error messages
    has_parse_error = "Could not parse structured summary" in pdf_text
    has_unable_error = "I'm unable to process your request" in pdf_text
    
    log_test(
        "NO 'Could not parse structured summary'",
        not has_parse_error,
        "FOUND error message" if has_parse_error else "Error message not found (correct)"
    )
    
    log_test(
        "NO 'I'm unable to process your request'",
        not has_unable_error,
        "FOUND error message" if has_unable_error else "Error message not found (correct)"
    )
    
    # Extract Status Summary section for detailed inspection
    if "Status Summary" in pdf_text:
        # Find the Status Summary section
        summary_start = pdf_text.find("Status Summary")
        summary_end = pdf_text.find("\n\n\n", summary_start)  # Sections typically separated by multiple newlines
        
        if summary_end == -1:
            summary_end = summary_start + 1000  # Take next 1000 chars if no clear end
        
        summary_section = pdf_text[summary_start:summary_end]
        
        print("\n" + "-"*80)
        print("STATUS SUMMARY SECTION PREVIEW (first 500 chars):")
        print("-"*80)
        print(summary_section[:500])
        print("-"*80)
    
    return {
        "no_generating_text": not has_generating_text,
        "has_executive_summary": has_executive_summary,
        "has_project_objective": has_project_objective,
        "no_parse_error": not has_parse_error,
        "no_unable_error": not has_unable_error
    }

def test_consistency(token):
    """Test consistency - run PDF export 2 more times"""
    print(f"\n{'='*80}")
    print("CONSISTENCY TEST - 2 MORE EXPORTS")
    print("="*80)
    
    for i in range(2):
        print(f"\n--- Export {i+1}/2 ---")
        result = export_pdf_single(token, f"Consistency Export {i+1}")
        
        is_success = (
            result["status_code"] == 200 and
            result["content_type"] == "application/pdf" and
            result["content_length"] > 100000  # > 100KB (full report)
        )
        
        log_test(
            f"Consistency Export {i+1}",
            is_success,
            f"HTTP {result['status_code']}, {result['content_length']/1024:.1f} KB, {result['elapsed']:.2f}s"
        )
        
        if is_success:
            # Quick check for "Generating" text
            # Save to temp file for pdftotext
            temp_pdf = f"/tmp/consistency_check_{i+1}.pdf"
            with open(temp_pdf, "wb") as f:
                f.write(result["content"])
            
            try:
                pdf_text_check = subprocess.check_output(
                    ["pdftotext", temp_pdf, "-"],
                    text=True
                )
                
                has_generating = "Generating client status summary" in pdf_text_check
                log_test(
                    f"Consistency Export {i+1} - NO 'Generating' text",
                    not has_generating,
                    "FOUND 'Generating' text - INCONSISTENT!" if has_generating else "Clean (correct)"
                )
            except subprocess.CalledProcessError:
                log_test(
                    f"Consistency Export {i+1} - NO 'Generating' text",
                    False,
                    "Could not extract text for verification"
                )

def test_concurrency(token):
    """Test concurrency - fire 3 concurrent PDF exports"""
    print(f"\n{'='*80}")
    print("CONCURRENCY TEST - 3 CONCURRENT EXPORTS")
    print("="*80)
    
    def export_worker(worker_id):
        """Worker function for concurrent export"""
        start = time.time()
        result = export_pdf_single(token, f"Concurrent Export {worker_id}")
        result["worker_id"] = worker_id
        result["start_time"] = start
        return result
    
    # Fire 3 concurrent requests
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(export_worker, i+1) for i in range(3)]
        results = [future.result() for future in as_completed(futures)]
    
    # Sort by worker_id for consistent reporting
    results.sort(key=lambda x: x["worker_id"])
    
    print("\n" + "-"*80)
    print("CONCURRENCY RESULTS:")
    print("-"*80)
    
    all_success = True
    times = []
    
    for result in results:
        is_success = (
            result["status_code"] == 200 and
            result["content_type"] == "application/pdf" and
            result["content_length"] > 100000  # > 100KB (full report)
        )
        
        all_success = all_success and is_success
        times.append(result["elapsed"])
        
        log_test(
            f"Concurrent Export {result['worker_id']}",
            is_success,
            f"HTTP {result['status_code']}, {result['content_length']/1024:.1f} KB, {result['elapsed']:.2f}s"
        )
    
    # Check for 502/503 errors
    has_errors = any(r["status_code"] in [502, 503, 500] for r in results)
    log_test(
        "Concurrency - NO 502/503/500 errors",
        not has_errors,
        "All requests returned 200" if not has_errors else "Some requests failed with server errors"
    )
    
    # Report timing stats
    if times:
        print(f"\nTiming stats: min={min(times):.2f}s, max={max(times):.2f}s, avg={sum(times)/len(times):.2f}s")

def test_regression(token):
    """Test regression - PPT export, health, projects list"""
    print(f"\n{'='*80}")
    print("REGRESSION TESTS")
    print("="*80)
    
    # Test 1: PPT Export
    print("\n--- PPT Export ---")
    response = requests.get(
        f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/export/ppt",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    
    is_ppt_success = (
        response.status_code == 200 and
        "application/vnd.openxmlformats-officedocument.presentationml.presentation" in response.headers.get("Content-Type", "") and
        response.content[:2] == b"PK"  # ZIP magic bytes
    )
    
    log_test(
        "PPT Export",
        is_ppt_success,
        f"HTTP {response.status_code}, {len(response.content)/1024:.1f} KB"
    )
    
    # Test 2: Health endpoint
    print("\n--- Health Endpoint ---")
    response = requests.get(f"{BASE_URL}/api/health")
    
    is_health_success = response.status_code == 200
    
    log_test(
        "Health Endpoint",
        is_health_success,
        f"HTTP {response.status_code}"
    )
    
    # Test 3: Projects list
    print("\n--- Projects List ---")
    response = requests.get(
        f"{BASE_URL}/api/projects",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    is_projects_success = response.status_code == 200
    project_count = len(response.json()) if is_projects_success else 0
    
    log_test(
        "Projects List",
        is_projects_success and project_count >= 4,
        f"HTTP {response.status_code}, {project_count} projects"
    )

def main():
    """Main test execution"""
    print("\n" + "="*80)
    print("PDF EXPORT AI STATUS SUMMARY FIX VERIFICATION")
    print("="*80)
    print(f"Test Project: {TEST_PROJECT_ID} (Website Redesign)")
    print(f"Backend URL: {BASE_URL}")
    print(f"Test Credentials: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print("="*80)
    
    # Authenticate
    token = authenticate()
    if not token:
        print("\n❌ AUTHENTICATION FAILED - Cannot proceed with tests")
        return
    
    # TEST 1: PDF EXPORT - Main test
    print("\n" + "="*80)
    print("TEST 1: PDF EXPORT - MAIN TEST")
    print("="*80)
    
    result = export_pdf_single(token, "Main PDF Export")
    
    # Verify HTTP 200
    is_http_200 = result["status_code"] == 200
    log_test("HTTP 200", is_http_200, f"Status: {result['status_code']}")
    
    # Verify Content-Type
    is_pdf_content_type = result["content_type"] == "application/pdf"
    log_test("Content-Type", is_pdf_content_type, f"Content-Type: {result['content_type']}")
    
    # Verify full report (not 4KB fallback)
    is_full_report = result["content_length"] > 100000  # > 100KB
    log_test(
        "Full Report (NOT 4KB fallback)",
        is_full_report,
        f"Size: {result['content_length']/1024:.1f} KB ({result['content_length']} bytes)"
    )
    
    # Report request time
    print(f"\nTotal request time: {result['elapsed']:.2f}s")
    if result['elapsed'] > 15:
        print("⚠️  Note: Export took longer than 15s (expected 8-15s range)")
    
    if not (is_http_200 and is_pdf_content_type and is_full_report):
        print("\n❌ BASIC PDF EXPORT CHECKS FAILED - Cannot proceed with detailed verification")
        return
    
    # Extract PDF structure and text
    pdf_info = verify_pdf_structure(result["content"])
    
    if not pdf_info["valid"]:
        print("\n❌ PDF STRUCTURE INVALID - Cannot proceed with content checks")
        return
    
    # Render PDF to images
    png_files = render_pdf_to_images(pdf_info["path"])
    
    # CRITICAL CONTENT CHECKS
    content_checks = check_critical_content(pdf_info["text"])
    
    # TEST 2: CONSISTENCY
    test_consistency(token)
    
    # TEST 3: CONCURRENCY
    test_concurrency(token)
    
    # TEST 4: REGRESSION
    test_regression(token)
    
    # FINAL SUMMARY
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for r in test_results if r["passed"])
    failed_tests = total_tests - passed_tests
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} ❌")
    print(f"Success Rate: {passed_tests/total_tests*100:.1f}%")
    
    # CRITICAL VERDICT
    print("\n" + "="*80)
    print("CRITICAL VERDICT - AI STATUS SUMMARY FIX")
    print("="*80)
    
    critical_checks = [
        content_checks["no_generating_text"],
        content_checks["has_executive_summary"],
        content_checks["has_project_objective"],
        content_checks["no_parse_error"],
        content_checks["no_unable_error"]
    ]
    
    all_critical_passed = all(critical_checks)
    
    if all_critical_passed:
        print("\n✅✅✅ PASS - AI STATUS SUMMARY FIX WORKING CORRECTLY ✅✅✅")
        print("\n(a) NO 'Generating client status summary' text found ✅")
        print("(b) Status Summary shows REAL content (EXECUTIVE SUMMARY + PROJECT OBJECTIVE) ✅")
        print("(c) NO error messages ('Could not parse' / 'unable to process') ✅")
    else:
        print("\n❌❌❌ FAIL - AI STATUS SUMMARY FIX NOT WORKING ❌❌❌")
        print("\nFailed checks:")
        if not content_checks["no_generating_text"]:
            print("  ❌ (a) FOUND 'Generating client status summary' text")
        if not content_checks["has_executive_summary"]:
            print("  ❌ (b) Missing 'EXECUTIVE SUMMARY' in Status Summary")
        if not content_checks["has_project_objective"]:
            print("  ❌ (b) Missing 'PROJECT OBJECTIVE' in Status Summary")
        if not content_checks["no_parse_error"]:
            print("  ❌ (c) FOUND 'Could not parse structured summary' error")
        if not content_checks["no_unable_error"]:
            print("  ❌ (c) FOUND 'I'm unable to process your request' error")
    
    print("\n" + "="*80)
    print("ARTIFACTS")
    print("="*80)
    for pdf_file in pdf_files:
        print(f"PDF: {pdf_file}")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
