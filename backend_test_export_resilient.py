#!/usr/bin/env python3
"""
Backend Test: Two-Tier Resilient Export Architecture Verification
Tests the export endpoints with Playwright + ReportLab fallback
"""
import requests
import sys
import time

# Test configuration
BASE_URL = "https://enhance-feedback-2.preview.emergentagent.com/api"
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "admin123"
PROJECT_ID = "6aabd45b6023b8429321ad6c"

def login():
    """Login and get JWT token"""
    print(f"🔐 Logging in as {TEST_EMAIL}...")
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if response.status_code != 200:
        print(f"❌ Login failed: {response.status_code}")
        print(f"Response: {response.text}")
        sys.exit(1)
    
    token = response.json().get("access_token")
    print(f"✅ Login successful")
    return token

def test_pdf_export(token):
    """Test 1: PDF Export with Playwright"""
    print(f"\n📄 TEST 1: PDF Export (Playwright)")
    print(f"Testing GET /api/projects/{PROJECT_ID}/export/pdf")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/projects/{PROJECT_ID}/export/pdf",
        headers=headers,
        timeout=60
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return False
    
    # Check Content-Type
    content_type = response.headers.get("Content-Type", "")
    print(f"Content-Type: {content_type}")
    if "application/pdf" not in content_type:
        print(f"❌ FAILED: Expected Content-Type 'application/pdf', got '{content_type}'")
        return False
    
    # Check PDF size
    pdf_size = len(response.content)
    print(f"PDF Size: {pdf_size} bytes ({pdf_size / 1024:.1f} KB)")
    if pdf_size < 1000:
        print(f"❌ FAILED: PDF too small ({pdf_size} bytes), expected >1000 bytes")
        return False
    
    # Check PDF magic bytes
    if not response.content.startswith(b'%PDF'):
        print(f"❌ FAILED: Invalid PDF magic bytes")
        return False
    
    # Check Content-Disposition header
    content_disposition = response.headers.get("Content-Disposition", "")
    print(f"Content-Disposition: {content_disposition}")
    if "attachment" not in content_disposition:
        print(f"⚠️  WARNING: Content-Disposition header missing 'attachment'")
    
    print(f"✅ PASSED: PDF export working correctly")
    return True

def test_reportlab_fallback():
    """Test 2: Verify ReportLab fallback exists and can generate PDFs"""
    print(f"\n🔧 TEST 2: ReportLab Fallback Verification")
    
    try:
        # Import the fallback function
        sys.path.insert(0, '/app/backend')
        from services.exports.reportlab_export import build_project_pdf_reportlab
        print(f"✅ ReportLab fallback module imported successfully")
        
        # Test with minimal project data
        test_project = {
            "name": "Test Project",
            "client_name": "Test Client",
            "status": "Active",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "budgeted_hours": 500,
            "health": "Green"
        }
        
        print(f"Generating test PDF with ReportLab...")
        pdf_bytes = build_project_pdf_reportlab(project=test_project)
        
        if not pdf_bytes:
            print(f"❌ FAILED: ReportLab returned empty bytes")
            return False
        
        pdf_size = len(pdf_bytes)
        print(f"PDF Size: {pdf_size} bytes ({pdf_size / 1024:.1f} KB)")
        
        if pdf_size < 1000:
            print(f"❌ FAILED: PDF too small ({pdf_size} bytes)")
            return False
        
        # Check PDF magic bytes
        if not pdf_bytes.startswith(b'%PDF'):
            print(f"❌ FAILED: Invalid PDF magic bytes")
            return False
        
        print(f"✅ PASSED: ReportLab fallback generates valid PDF bytes")
        return True
        
    except ImportError as e:
        print(f"❌ FAILED: Cannot import ReportLab fallback: {e}")
        return False
    except Exception as e:
        print(f"❌ FAILED: ReportLab fallback error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ppt_export(token):
    """Test 3: PPT Export"""
    print(f"\n📊 TEST 3: PPT Export")
    print(f"Testing GET /api/projects/{PROJECT_ID}/export/ppt")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/projects/{PROJECT_ID}/export/ppt",
        headers=headers,
        timeout=60
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return False
    
    # Check Content-Type
    content_type = response.headers.get("Content-Type", "")
    print(f"Content-Type: {content_type}")
    expected_mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    if expected_mime not in content_type:
        print(f"❌ FAILED: Expected Content-Type '{expected_mime}', got '{content_type}'")
        return False
    
    # Check PPTX size
    pptx_size = len(response.content)
    print(f"PPTX Size: {pptx_size} bytes ({pptx_size / 1024:.1f} KB)")
    if pptx_size < 1000:
        print(f"❌ FAILED: PPTX too small ({pptx_size} bytes)")
        return False
    
    # Check ZIP magic bytes (PPTX is a ZIP file)
    if not response.content.startswith(b'PK'):
        print(f"❌ FAILED: Invalid PPTX magic bytes (should start with 'PK')")
        return False
    
    print(f"✅ PASSED: PPT export working correctly")
    return True

def test_cloudbuild_config():
    """Test 4: Verify cloudbuild.yaml configuration"""
    print(f"\n⚙️  TEST 4: cloudbuild.yaml Configuration")
    
    try:
        with open('/app/cloudbuild.yaml', 'r') as f:
            content = f.read()
        
        checks = {
            "Service name 'ddplan'": '"ddplan"' in content or "'ddplan'" in content or "- ddplan" in content,
            "Memory: 2Gi": '"2Gi"' in content or "'2Gi'" in content or "- 2Gi" in content or "- \"2Gi\"" in content,
            "CPU: 2": '"2"' in content and '--cpu' in content,
            "Min instances: 1": '"1"' in content and '--min-instances' in content,
            "Execution environment: gen2": 'gen2' in content and '--execution-environment' in content
        }
        
        all_passed = True
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"{status} {check_name}: {result}")
            if not result:
                all_passed = False
        
        if all_passed:
            print(f"✅ PASSED: All cloudbuild.yaml configurations verified")
        else:
            print(f"❌ FAILED: Some cloudbuild.yaml configurations missing")
        
        return all_passed
        
    except FileNotFoundError:
        print(f"❌ FAILED: cloudbuild.yaml not found")
        return False
    except Exception as e:
        print(f"❌ FAILED: Error reading cloudbuild.yaml: {e}")
        return False

def main():
    print("=" * 80)
    print("Two-Tier Resilient Export Architecture Verification")
    print("=" * 80)
    
    # Login
    token = login()
    
    # Run tests
    results = []
    
    # Test 1: PDF Export
    results.append(("PDF Export (Playwright)", test_pdf_export(token)))
    
    # Test 2: ReportLab Fallback
    results.append(("ReportLab Fallback", test_reportlab_fallback()))
    
    # Test 3: PPT Export
    results.append(("PPT Export", test_ppt_export(token)))
    
    # Test 4: cloudbuild.yaml
    results.append(("cloudbuild.yaml Config", test_cloudbuild_config()))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Two-Tier Resilient Export Architecture Verified")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed} TEST(S) FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
