#!/usr/bin/env python3
"""
Backend API Testing for Export Endpoints (PDF & PPT)
Testing memory-optimized, resilient renderer
Test URL: https://enhance-feedback-2.preview.emergentagent.com
"""

import requests
import json
import os
from io import BytesIO

# Configuration
BASE_URL = "https://enhance-feedback-2.preview.emergentagent.com/api"
TEST_USER = "admin@test.com"
TEST_PASSWORD = "admin123"
PROJECT_ID = "6aabd45b6023b8429321ad6c"

# Global token storage
token = None

def login():
    """Login and get JWT token"""
    global token
    print("\n" + "="*80)
    print("TEST: Login")
    print("="*80)
    
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={
            "username": TEST_USER,
            "password": TEST_PASSWORD
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        print(f"✅ Login successful. Token: {token[:20]}...")
        return True
    else:
        print(f"❌ Login failed: {response.text}")
        return False

def get_headers():
    """Get authorization headers"""
    return {"Authorization": f"Bearer {token}"}

# ============================================================================
# TEST 1: Export Project PDF
# ============================================================================
def test_export_pdf():
    """Test GET /api/projects/{project_id}/export/pdf"""
    print("\n" + "="*80)
    print("TEST 1: Export Project PDF")
    print("="*80)
    
    url = f"{BASE_URL}/projects/{PROJECT_ID}/export/pdf"
    print(f"GET {url}")
    
    response = requests.get(url, headers=get_headers(), timeout=120)
    
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print(f"Content-Length: {len(response.content)} bytes")
    print(f"Content-Disposition: {response.headers.get('Content-Disposition')}")
    
    # Check HTTP 200
    if response.status_code != 200:
        print(f"❌ FAILED: Expected HTTP 200, got {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return False
    
    # Check Content-Type
    content_type = response.headers.get('Content-Type', '')
    if 'application/pdf' not in content_type:
        print(f"❌ FAILED: Expected Content-Type 'application/pdf', got '{content_type}'")
        return False
    
    # Check non-empty bytes
    if len(response.content) == 0:
        print(f"❌ FAILED: PDF content is empty")
        return False
    
    # Check PDF magic bytes
    if not response.content.startswith(b'%PDF'):
        print(f"❌ FAILED: Content does not start with PDF magic bytes")
        print(f"First 20 bytes: {response.content[:20]}")
        return False
    
    # Save to file for verification
    pdf_path = "/tmp/test_export.pdf"
    with open(pdf_path, "wb") as f:
        f.write(response.content)
    print(f"✅ PDF saved to {pdf_path}")
    
    # Verify with pdfinfo
    try:
        import subprocess
        result = subprocess.run(['pdfinfo', pdf_path], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ PDF validation successful:")
            for line in result.stdout.split('\n')[:5]:
                if line.strip():
                    print(f"   {line}")
        else:
            print(f"⚠️ pdfinfo validation failed: {result.stderr}")
    except Exception as e:
        print(f"⚠️ Could not run pdfinfo: {e}")
    
    print(f"✅ TEST 1 PASSED: PDF export working correctly")
    return True

# ============================================================================
# TEST 2: Export Project PPT
# ============================================================================
def test_export_ppt():
    """Test GET /api/projects/{project_id}/export/ppt"""
    print("\n" + "="*80)
    print("TEST 2: Export Project PPT")
    print("="*80)
    
    url = f"{BASE_URL}/projects/{PROJECT_ID}/export/ppt"
    print(f"GET {url}")
    
    response = requests.get(url, headers=get_headers(), timeout=120)
    
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print(f"Content-Length: {len(response.content)} bytes")
    print(f"Content-Disposition: {response.headers.get('Content-Disposition')}")
    
    # Check HTTP 200
    if response.status_code != 200:
        print(f"❌ FAILED: Expected HTTP 200, got {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return False
    
    # Check Content-Type
    content_type = response.headers.get('Content-Type', '')
    expected_mime = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    if expected_mime not in content_type:
        print(f"❌ FAILED: Expected Content-Type '{expected_mime}', got '{content_type}'")
        return False
    
    # Check non-empty bytes
    if len(response.content) == 0:
        print(f"❌ FAILED: PPTX content is empty")
        return False
    
    # Check PPTX magic bytes (ZIP format: PK)
    if not response.content.startswith(b'PK'):
        print(f"❌ FAILED: Content does not start with ZIP/PPTX magic bytes")
        print(f"First 20 bytes: {response.content[:20]}")
        return False
    
    # Save to file for verification
    pptx_path = "/tmp/test_export.pptx"
    with open(pptx_path, "wb") as f:
        f.write(response.content)
    print(f"✅ PPTX saved to {pptx_path}")
    
    # Verify with python-pptx
    try:
        from pptx import Presentation
        prs = Presentation(pptx_path)
        slide_count = len(prs.slides)
        print(f"✅ PPTX validation successful:")
        print(f"   Slide count: {slide_count}")
        
        # Check each slide has shapes
        for i, slide in enumerate(prs.slides):
            shape_count = len(slide.shapes)
            print(f"   Slide {i+1}: {shape_count} shapes")
            if shape_count == 0:
                print(f"   ⚠️ Warning: Slide {i+1} has no shapes")
        
    except Exception as e:
        print(f"⚠️ PPTX validation failed: {e}")
        return False
    
    print(f"✅ TEST 2 PASSED: PPT export working correctly")
    return True

# ============================================================================
# TEST 3: Check Backend Logs for Errors
# ============================================================================
def test_backend_logs():
    """Check backend logs for 503 or 500 errors"""
    print("\n" + "="*80)
    print("TEST 3: Check Backend Logs")
    print("="*80)
    
    log_files = [
        "/var/log/supervisor/backend.err.log",
        "/var/log/supervisor/backend.out.log"
    ]
    
    error_patterns = ["503", "500", "ERROR", "CRITICAL", "Traceback"]
    found_errors = []
    
    for log_file in log_files:
        if not os.path.exists(log_file):
            print(f"⚠️ Log file not found: {log_file}")
            continue
        
        print(f"\nChecking {log_file}...")
        try:
            with open(log_file, 'r') as f:
                # Read last 200 lines
                lines = f.readlines()[-200:]
                
            for i, line in enumerate(lines):
                for pattern in error_patterns:
                    if pattern in line and 'export' in line.lower():
                        found_errors.append(f"{log_file}:{len(lines)-200+i}: {line.strip()}")
        
        except Exception as e:
            print(f"⚠️ Could not read log file: {e}")
    
    if found_errors:
        print(f"\n❌ FOUND {len(found_errors)} EXPORT-RELATED ERRORS IN LOGS:")
        for error in found_errors[:10]:  # Show first 10
            print(f"   {error}")
        return False
    else:
        print(f"✅ No export-related errors found in backend logs")
        return True

# ============================================================================
# TEST 4: Test with Non-existent Project (404 check)
# ============================================================================
def test_export_404():
    """Test export endpoints return 404 for non-existent project"""
    print("\n" + "="*80)
    print("TEST 4: Export 404 Handling")
    print("="*80)
    
    fake_project_id = "000000000000000000000000"
    
    # Test PDF
    url = f"{BASE_URL}/projects/{fake_project_id}/export/pdf"
    print(f"GET {url}")
    response = requests.get(url, headers=get_headers(), timeout=30)
    print(f"PDF Status: {response.status_code}")
    
    if response.status_code != 404:
        print(f"❌ FAILED: Expected 404 for non-existent project PDF, got {response.status_code}")
        return False
    
    # Test PPT
    url = f"{BASE_URL}/projects/{fake_project_id}/export/ppt"
    print(f"GET {url}")
    response = requests.get(url, headers=get_headers(), timeout=30)
    print(f"PPT Status: {response.status_code}")
    
    if response.status_code != 404:
        print(f"❌ FAILED: Expected 404 for non-existent project PPT, got {response.status_code}")
        return False
    
    print(f"✅ TEST 4 PASSED: 404 handling working correctly")
    return True

# ============================================================================
# TEST 5: Test without Auth (401 check)
# ============================================================================
def test_export_401():
    """Test export endpoints return 401 without auth"""
    print("\n" + "="*80)
    print("TEST 5: Export 401 Handling")
    print("="*80)
    
    # Test PDF without auth
    url = f"{BASE_URL}/projects/{PROJECT_ID}/export/pdf"
    print(f"GET {url} (no auth)")
    response = requests.get(url, timeout=30)
    print(f"PDF Status: {response.status_code}")
    
    if response.status_code != 401:
        print(f"❌ FAILED: Expected 401 for PDF without auth, got {response.status_code}")
        return False
    
    # Test PPT without auth
    url = f"{BASE_URL}/projects/{PROJECT_ID}/export/ppt"
    print(f"GET {url} (no auth)")
    response = requests.get(url, timeout=30)
    print(f"PPT Status: {response.status_code}")
    
    if response.status_code != 401:
        print(f"❌ FAILED: Expected 401 for PPT without auth, got {response.status_code}")
        return False
    
    print(f"✅ TEST 5 PASSED: 401 handling working correctly")
    return True

# ============================================================================
# Main Test Runner
# ============================================================================
def main():
    print("\n" + "="*80)
    print("EXPORT ENDPOINTS VERIFICATION TEST SUITE")
    print("Testing memory-optimized, resilient renderer")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Project ID: {PROJECT_ID}")
    print(f"Test User: {TEST_USER}")
    
    results = []
    
    # Login first
    if not login():
        print("\n❌ LOGIN FAILED - Cannot proceed with tests")
        return
    
    # Run tests
    results.append(("Export PDF", test_export_pdf()))
    results.append(("Export PPT", test_export_ppt()))
    results.append(("Backend Logs Check", test_backend_logs()))
    results.append(("404 Handling", test_export_404()))
    results.append(("401 Handling", test_export_401()))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed*100//total}% success rate)")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Export endpoints working correctly!")
    else:
        print(f"\n⚠️ {total - passed} TEST(S) FAILED - See details above")

if __name__ == "__main__":
    main()
