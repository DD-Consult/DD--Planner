#!/usr/bin/env python3
"""
Backend Export Endpoints Verification Test
Tests PDF and PPT export endpoints with ReportLab fallback verification
"""
import requests
import sys
import io
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8001"
PROJECT_ID = "6aabd45b6023b8429321ad6c"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_test(msg):
    print(f"{BLUE}[TEST]{RESET} {msg}")

def print_pass(msg):
    print(f"{GREEN}✅ PASS:{RESET} {msg}")

def print_fail(msg):
    print(f"{RED}❌ FAIL:{RESET} {msg}")

def print_info(msg):
    print(f"{YELLOW}ℹ INFO:{RESET} {msg}")

def login(email, password):
    """Authenticate and return JWT token"""
    print_test(f"Authenticating as {email}...")
    
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if response.status_code == 200:
        token = response.json().get("access_token")
        print_pass(f"Authentication successful. Token: {token[:20]}...")
        return token
    else:
        print_fail(f"Authentication failed: {response.status_code} - {response.text}")
        return None

def verify_pdf_bytes(pdf_bytes):
    """Verify PDF file structure"""
    if not pdf_bytes:
        return False, "Empty PDF bytes"
    
    # Check PDF magic bytes
    if not pdf_bytes.startswith(b'%PDF'):
        return False, "Invalid PDF magic bytes"
    
    # Check for EOF marker
    if b'%%EOF' not in pdf_bytes:
        return False, "Missing PDF EOF marker"
    
    # Get file size
    size_kb = len(pdf_bytes) / 1024
    
    # Count pages (rough estimate by counting /Page objects)
    page_count = pdf_bytes.count(b'/Type /Page')
    
    return True, f"Valid PDF: {size_kb:.1f} KB, ~{page_count} pages"

def verify_pptx_bytes(pptx_bytes):
    """Verify PPTX file structure"""
    if not pptx_bytes:
        return False, "Empty PPTX bytes"
    
    # Check ZIP magic bytes (PPTX is a ZIP file)
    if not pptx_bytes.startswith(b'PK'):
        return False, "Invalid PPTX magic bytes (not a ZIP file)"
    
    # Get file size
    size_kb = len(pptx_bytes) / 1024
    
    # Try to validate with python-pptx
    try:
        from pptx import Presentation
        prs = Presentation(io.BytesIO(pptx_bytes))
        slide_count = len(prs.slides)
        return True, f"Valid PPTX: {size_kb:.1f} KB, {slide_count} slides"
    except Exception as e:
        return True, f"Valid PPTX (ZIP structure): {size_kb:.1f} KB (python-pptx validation failed: {e})"

def test_pdf_export(token):
    """Test PDF export endpoint"""
    print_test(f"Testing GET /api/projects/{PROJECT_ID}/export/pdf...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/export/pdf",
        headers=headers,
        timeout=60
    )
    
    print_info(f"Response status: {response.status_code}")
    print_info(f"Content-Type: {response.headers.get('Content-Type')}")
    print_info(f"Content-Length: {response.headers.get('Content-Length')} bytes")
    print_info(f"Content-Disposition: {response.headers.get('Content-Disposition')}")
    
    if response.status_code != 200:
        print_fail(f"Expected status 200, got {response.status_code}")
        print_fail(f"Response: {response.text[:500]}")
        return False
    
    # Verify Content-Type
    content_type = response.headers.get('Content-Type', '')
    if 'application/pdf' not in content_type:
        print_fail(f"Expected Content-Type 'application/pdf', got '{content_type}'")
        return False
    
    print_pass("Content-Type is correct (application/pdf)")
    
    # Verify Content-Disposition header
    content_disposition = response.headers.get('Content-Disposition', '')
    if 'attachment' not in content_disposition:
        print_fail(f"Expected Content-Disposition with 'attachment', got '{content_disposition}'")
        return False
    
    print_pass("Content-Disposition header is correct")
    
    # Verify PDF bytes
    pdf_bytes = response.content
    is_valid, msg = verify_pdf_bytes(pdf_bytes)
    
    if not is_valid:
        print_fail(f"PDF validation failed: {msg}")
        return False
    
    print_pass(f"PDF validation passed: {msg}")
    
    # Save PDF for manual inspection
    filename = f"/tmp/test_export_pdf_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    with open(filename, 'wb') as f:
        f.write(pdf_bytes)
    print_info(f"PDF saved to {filename}")
    
    return True

def test_ppt_export(token):
    """Test PPT export endpoint"""
    print_test(f"Testing GET /api/projects/{PROJECT_ID}/export/ppt...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/export/ppt",
        headers=headers,
        timeout=60
    )
    
    print_info(f"Response status: {response.status_code}")
    print_info(f"Content-Type: {response.headers.get('Content-Type')}")
    print_info(f"Content-Length: {response.headers.get('Content-Length')} bytes")
    print_info(f"Content-Disposition: {response.headers.get('Content-Disposition')}")
    
    if response.status_code != 200:
        print_fail(f"Expected status 200, got {response.status_code}")
        print_fail(f"Response: {response.text[:500]}")
        return False
    
    # Verify Content-Type
    content_type = response.headers.get('Content-Type', '')
    expected_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    if expected_type not in content_type:
        print_fail(f"Expected Content-Type '{expected_type}', got '{content_type}'")
        return False
    
    print_pass("Content-Type is correct")
    
    # Verify Content-Disposition header
    content_disposition = response.headers.get('Content-Disposition', '')
    if 'attachment' not in content_disposition:
        print_fail(f"Expected Content-Disposition with 'attachment', got '{content_disposition}'")
        return False
    
    print_pass("Content-Disposition header is correct")
    
    # Verify PPTX bytes
    pptx_bytes = response.content
    is_valid, msg = verify_pptx_bytes(pptx_bytes)
    
    if not is_valid:
        print_fail(f"PPTX validation failed: {msg}")
        return False
    
    print_pass(f"PPTX validation passed: {msg}")
    
    # Save PPTX for manual inspection
    filename = f"/tmp/test_export_pptx_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
    with open(filename, 'wb') as f:
        f.write(pptx_bytes)
    print_info(f"PPTX saved to {filename}")
    
    return True

def test_reportlab_fallback():
    """Test ReportLab fallback functionality"""
    print_test("Testing ReportLab fallback functionality...")
    
    try:
        import sys
        sys.path.insert(0, '/app/backend')
        from services.exports.reportlab_export import build_project_pdf_reportlab
        
        # Create a minimal project dict
        test_project = {
            "_id": "test_id",
            "name": "Test Project",
            "client_name": "Test Client",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "budgeted_hours": 1000,
            "status": "active",
            "health": "green",
            "phases": []
        }
        
        # Generate PDF using ReportLab
        pdf_bytes = build_project_pdf_reportlab(project=test_project)
        
        # Verify the generated PDF
        is_valid, msg = verify_pdf_bytes(pdf_bytes)
        
        if not is_valid:
            print_fail(f"ReportLab PDF validation failed: {msg}")
            return False
        
        print_pass(f"ReportLab fallback working: {msg}")
        
        # Check if it's a multi-page PDF
        page_count = pdf_bytes.count(b'/Type /Page')
        if page_count >= 2:
            print_pass(f"ReportLab generates multi-page PDF ({page_count} pages)")
        else:
            print_info(f"ReportLab generates single-page PDF ({page_count} page)")
        
        # Save for inspection
        filename = f"/tmp/test_reportlab_fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        with open(filename, 'wb') as f:
            f.write(pdf_bytes)
        print_info(f"ReportLab PDF saved to {filename}")
        
        return True
        
    except ImportError as e:
        print_fail(f"Failed to import ReportLab module: {e}")
        return False
    except Exception as e:
        print_fail(f"ReportLab fallback test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_auth_checks(token):
    """Test authentication requirements"""
    print_test("Testing authentication requirements...")
    
    # Test without token
    response = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/export/pdf")
    if response.status_code == 401:
        print_pass("PDF endpoint correctly returns 401 without auth token")
    else:
        print_fail(f"PDF endpoint should return 401 without auth, got {response.status_code}")
        return False
    
    # Test with invalid token
    headers = {"Authorization": "Bearer invalid_token_12345"}
    response = requests.get(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/export/pdf",
        headers=headers
    )
    if response.status_code == 401:
        print_pass("PDF endpoint correctly returns 401 with invalid token")
    else:
        print_fail(f"PDF endpoint should return 401 with invalid token, got {response.status_code}")
        return False
    
    # Test with non-existent project
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/api/projects/000000000000000000000000/export/pdf",
        headers=headers
    )
    if response.status_code == 404:
        print_pass("PDF endpoint correctly returns 404 for non-existent project")
    else:
        print_fail(f"PDF endpoint should return 404 for non-existent project, got {response.status_code}")
        return False
    
    return True

def main():
    print("\n" + "="*80)
    print("BACKEND EXPORT ENDPOINTS VERIFICATION TEST")
    print("="*80 + "\n")
    
    test_results = []
    
    # Test 1: Authentication
    print("\n" + "-"*80)
    print("TEST 1: AUTHENTICATION")
    print("-"*80)
    token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not token:
        print_fail("Authentication failed. Cannot proceed with tests.")
        sys.exit(1)
    test_results.append(("Authentication", True))
    
    # Test 2: PDF Export
    print("\n" + "-"*80)
    print("TEST 2: PDF EXPORT ENDPOINT")
    print("-"*80)
    pdf_result = test_pdf_export(token)
    test_results.append(("PDF Export", pdf_result))
    
    # Test 3: PPT Export
    print("\n" + "-"*80)
    print("TEST 3: PPT EXPORT ENDPOINT")
    print("-"*80)
    ppt_result = test_ppt_export(token)
    test_results.append(("PPT Export", ppt_result))
    
    # Test 4: ReportLab Fallback
    print("\n" + "-"*80)
    print("TEST 4: REPORTLAB FALLBACK")
    print("-"*80)
    reportlab_result = test_reportlab_fallback()
    test_results.append(("ReportLab Fallback", reportlab_result))
    
    # Test 5: Auth Checks
    print("\n" + "-"*80)
    print("TEST 5: AUTHENTICATION CHECKS")
    print("-"*80)
    auth_result = test_auth_checks(token)
    test_results.append(("Auth Checks", auth_result))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = f"{GREEN}✅ PASSED{RESET}" if result else f"{RED}❌ FAILED{RESET}"
        print(f"{test_name:30} {status}")
    
    print("-"*80)
    print(f"Total: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print("="*80 + "\n")
    
    if passed == total:
        print(f"{GREEN}🎉 ALL TESTS PASSED!{RESET}\n")
        sys.exit(0)
    else:
        print(f"{RED}⚠️  SOME TESTS FAILED{RESET}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
