#!/usr/bin/env python3
"""
Final Verification Test for Export Endpoints and ReportLab Fallback
Tests all requirements from the review request:
1. Authenticate with admin@test.com / admin123
2. Test GET /api/projects/6aabd45b6023b8429321ad6c/export/pdf (returns HTTP 200, valid multi-page PDF)
3. Test GET /api/projects/6aabd45b6023b8429321ad6c/export/ppt (returns HTTP 200, valid PPTX)
4. Verify ReportLab fallback generates valid PDF bytes without crashing
5. Verify cloudbuild.yaml has correct configuration
"""

import requests
import sys
import os
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8001"
PROJECT_ID = "6aabd45b6023b8429321ad6c"
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "admin123"

# Test results tracking
tests_passed = 0
tests_failed = 0
test_results = []

def log_test(test_name, passed, message=""):
    """Log test result"""
    global tests_passed, tests_failed
    status = "✅ PASSED" if passed else "❌ FAILED"
    result = f"{status}: {test_name}"
    if message:
        result += f" - {message}"
    print(result)
    test_results.append(result)
    
    if passed:
        tests_passed += 1
    else:
        tests_failed += 1

def authenticate():
    """Authenticate and get JWT token"""
    print("\n" + "="*80)
    print("TEST 1: Authentication")
    print("="*80)
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            if token:
                log_test("Authentication", True, f"Successfully authenticated with {TEST_EMAIL}")
                return token
            else:
                log_test("Authentication", False, "No access_token in response")
                return None
        else:
            log_test("Authentication", False, f"HTTP {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        log_test("Authentication", False, f"Exception: {str(e)}")
        return None

def test_pdf_export(token):
    """Test PDF export endpoint"""
    print("\n" + "="*80)
    print("TEST 2: PDF Export Endpoint")
    print("="*80)
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{BASE_URL}/api/projects/{PROJECT_ID}/export/pdf"
        
        print(f"Requesting: {url}")
        response = requests.get(url, headers=headers, timeout=60)
        
        # Check HTTP status
        if response.status_code != 200:
            log_test("PDF Export - HTTP Status", False, f"Expected 200, got {response.status_code}")
            return False
        
        log_test("PDF Export - HTTP Status", True, "Returns HTTP 200")
        
        # Check Content-Type
        content_type = response.headers.get("Content-Type", "")
        if "application/pdf" in content_type:
            log_test("PDF Export - Content-Type", True, f"Correct Content-Type: {content_type}")
        else:
            log_test("PDF Export - Content-Type", False, f"Expected application/pdf, got {content_type}")
        
        # Check Content-Disposition
        content_disposition = response.headers.get("Content-Disposition", "")
        if content_disposition:
            log_test("PDF Export - Content-Disposition", True, f"Header present: {content_disposition}")
        else:
            log_test("PDF Export - Content-Disposition", False, "Header missing")
        
        # Check PDF content
        pdf_bytes = response.content
        pdf_size_kb = len(pdf_bytes) / 1024
        
        if len(pdf_bytes) > 0:
            log_test("PDF Export - File Size", True, f"{pdf_size_kb:.1f} KB")
        else:
            log_test("PDF Export - File Size", False, "Empty file")
            return False
        
        # Verify PDF magic bytes
        if pdf_bytes.startswith(b'%PDF'):
            log_test("PDF Export - Valid PDF", True, "PDF magic bytes verified (%PDF)")
        else:
            log_test("PDF Export - Valid PDF", False, f"Invalid magic bytes: {pdf_bytes[:10]}")
            return False
        
        # Count pages in PDF (simple heuristic)
        page_count = pdf_bytes.count(b'/Type /Page')
        if page_count > 1:
            log_test("PDF Export - Multi-page", True, f"Multi-page PDF detected ({page_count} page objects)")
        else:
            # Try alternative method
            count_field = pdf_bytes.find(b'/Count ')
            if count_field > 0:
                # Extract count value
                count_str = pdf_bytes[count_field+7:count_field+10].decode('utf-8', errors='ignore').strip()
                try:
                    count_val = int(count_str.split()[0])
                    if count_val > 1:
                        log_test("PDF Export - Multi-page", True, f"Multi-page PDF ({count_val} pages via /Count)")
                    else:
                        log_test("PDF Export - Multi-page", False, f"Only {count_val} page detected")
                except:
                    log_test("PDF Export - Multi-page", False, f"Could not determine page count")
            else:
                log_test("PDF Export - Multi-page", False, f"Only {page_count} page object(s) found")
        
        # Save PDF for verification
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = f"/tmp/test_export_pdf_{timestamp}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"PDF saved to: {pdf_path}")
        
        return True
        
    except Exception as e:
        log_test("PDF Export", False, f"Exception: {str(e)}")
        return False

def test_ppt_export(token):
    """Test PPT export endpoint"""
    print("\n" + "="*80)
    print("TEST 3: PPT Export Endpoint")
    print("="*80)
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{BASE_URL}/api/projects/{PROJECT_ID}/export/ppt"
        
        print(f"Requesting: {url}")
        response = requests.get(url, headers=headers, timeout=60)
        
        # Check HTTP status
        if response.status_code != 200:
            log_test("PPT Export - HTTP Status", False, f"Expected 200, got {response.status_code}")
            return False
        
        log_test("PPT Export - HTTP Status", True, "Returns HTTP 200")
        
        # Check Content-Type
        content_type = response.headers.get("Content-Type", "")
        expected_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        if expected_type in content_type:
            log_test("PPT Export - Content-Type", True, "Correct MIME type")
        else:
            log_test("PPT Export - Content-Type", False, f"Expected {expected_type}, got {content_type}")
        
        # Check Content-Disposition
        content_disposition = response.headers.get("Content-Disposition", "")
        if content_disposition:
            log_test("PPT Export - Content-Disposition", True, f"Header present: {content_disposition}")
        else:
            log_test("PPT Export - Content-Disposition", False, "Header missing")
        
        # Check PPTX content
        pptx_bytes = response.content
        pptx_size_kb = len(pptx_bytes) / 1024
        
        if len(pptx_bytes) > 0:
            log_test("PPT Export - File Size", True, f"{pptx_size_kb:.1f} KB")
        else:
            log_test("PPT Export - File Size", False, "Empty file")
            return False
        
        # Verify PPTX magic bytes (ZIP format)
        if pptx_bytes.startswith(b'PK'):
            log_test("PPT Export - Valid PPTX", True, "ZIP magic bytes verified (PK)")
        else:
            log_test("PPT Export - Valid PPTX", False, f"Invalid magic bytes: {pptx_bytes[:10]}")
            return False
        
        # Try to validate with python-pptx
        try:
            from pptx import Presentation
            from io import BytesIO
            
            prs = Presentation(BytesIO(pptx_bytes))
            slide_count = len(prs.slides)
            
            if slide_count > 0:
                log_test("PPT Export - Slide Count", True, f"{slide_count} slides verified with python-pptx")
            else:
                log_test("PPT Export - Slide Count", False, "No slides found")
        except ImportError:
            log_test("PPT Export - Validation", True, "python-pptx not available, skipping detailed validation")
        except Exception as e:
            log_test("PPT Export - Validation", False, f"python-pptx validation failed: {str(e)}")
        
        # Save PPTX for verification
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pptx_path = f"/tmp/test_export_pptx_{timestamp}.pptx"
        with open(pptx_path, "wb") as f:
            f.write(pptx_bytes)
        print(f"PPTX saved to: {pptx_path}")
        
        return True
        
    except Exception as e:
        log_test("PPT Export", False, f"Exception: {str(e)}")
        return False

def test_reportlab_fallback():
    """Test ReportLab fallback function"""
    print("\n" + "="*80)
    print("TEST 4: ReportLab Fallback")
    print("="*80)
    
    try:
        # Import the fallback function
        sys.path.insert(0, '/app/backend')
        from services.exports.reportlab_export import build_project_pdf_reportlab
        
        log_test("ReportLab Import", True, "Successfully imported build_project_pdf_reportlab")
        
        # Test with minimal project data
        minimal_project = {
            "name": "Test Project",
            "client_name": "Test Client",
            "status": "Active",
            "health": "Green",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "budgeted_hours": 500
        }
        
        # Call the function
        pdf_bytes = build_project_pdf_reportlab(
            project=minimal_project,
            risks=[],
            allocations=[],
            status_updates=[]
        )
        
        # Verify it returns bytes
        if isinstance(pdf_bytes, bytes):
            log_test("ReportLab Returns Bytes", True, f"Returns {len(pdf_bytes)} bytes")
        else:
            log_test("ReportLab Returns Bytes", False, f"Returns {type(pdf_bytes)} instead of bytes")
            return False
        
        # Verify it's a valid PDF
        if pdf_bytes.startswith(b'%PDF'):
            log_test("ReportLab Valid PDF", True, "PDF magic bytes verified")
        else:
            log_test("ReportLab Valid PDF", False, "Invalid PDF format")
            return False
        
        # Verify it doesn't crash with missing data
        empty_project = {}
        pdf_bytes_empty = build_project_pdf_reportlab(project=empty_project)
        
        if isinstance(pdf_bytes_empty, bytes) and pdf_bytes_empty.startswith(b'%PDF'):
            log_test("ReportLab Crash-Proof", True, "Handles empty project data without crashing")
        else:
            log_test("ReportLab Crash-Proof", False, "Crashes or returns invalid data with empty project")
            return False
        
        # Save fallback PDF
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback_path = f"/tmp/test_reportlab_fallback_{timestamp}.pdf"
        with open(fallback_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"ReportLab fallback PDF saved to: {fallback_path}")
        
        return True
        
    except Exception as e:
        log_test("ReportLab Fallback", False, f"Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_cloudbuild_config():
    """Test cloudbuild.yaml configuration"""
    print("\n" + "="*80)
    print("TEST 5: cloudbuild.yaml Configuration")
    print("="*80)
    
    try:
        import yaml
        
        with open('/app/cloudbuild.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        log_test("cloudbuild.yaml - File Exists", True, "File loaded successfully")
        
        # Find the deploy step
        deploy_step = None
        for step in config.get('steps', []):
            if step.get('entrypoint') == 'gcloud' and 'deploy' in step.get('args', []):
                deploy_step = step
                break
        
        if not deploy_step:
            log_test("cloudbuild.yaml - Deploy Step", False, "Deploy step not found")
            return False
        
        log_test("cloudbuild.yaml - Deploy Step", True, "Deploy step found")
        
        args = deploy_step.get('args', [])
        
        # Check service name
        if 'ddplan' in args:
            log_test("cloudbuild.yaml - Service Name", True, "Service name is 'ddplan'")
        else:
            log_test("cloudbuild.yaml - Service Name", False, f"Service name not 'ddplan', args: {args}")
        
        # Check memory
        if '--memory' in args:
            memory_idx = args.index('--memory')
            memory_value = args[memory_idx + 1] if memory_idx + 1 < len(args) else None
            if memory_value == '2Gi':
                log_test("cloudbuild.yaml - Memory", True, "Memory is 2Gi")
            else:
                log_test("cloudbuild.yaml - Memory", False, f"Memory is {memory_value}, expected 2Gi")
        else:
            log_test("cloudbuild.yaml - Memory", False, "--memory flag not found")
        
        # Check CPU
        if '--cpu' in args:
            cpu_idx = args.index('--cpu')
            cpu_value = args[cpu_idx + 1] if cpu_idx + 1 < len(args) else None
            if cpu_value == '2':
                log_test("cloudbuild.yaml - CPU", True, "CPU is 2")
            else:
                log_test("cloudbuild.yaml - CPU", False, f"CPU is {cpu_value}, expected 2")
        else:
            log_test("cloudbuild.yaml - CPU", False, "--cpu flag not found")
        
        # Check min-instances
        if '--min-instances' in args:
            min_idx = args.index('--min-instances')
            min_value = args[min_idx + 1] if min_idx + 1 < len(args) else None
            if min_value == '1':
                log_test("cloudbuild.yaml - Min Instances", True, "Min instances is 1")
            else:
                log_test("cloudbuild.yaml - Min Instances", False, f"Min instances is {min_value}, expected 1")
        else:
            log_test("cloudbuild.yaml - Min Instances", False, "--min-instances flag not found")
        
        # Check execution-environment
        if '--execution-environment' in args:
            env_idx = args.index('--execution-environment')
            env_value = args[env_idx + 1] if env_idx + 1 < len(args) else None
            if env_value == 'gen2':
                log_test("cloudbuild.yaml - Execution Environment", True, "Execution environment is gen2")
            else:
                log_test("cloudbuild.yaml - Execution Environment", False, f"Execution environment is {env_value}, expected gen2")
        else:
            log_test("cloudbuild.yaml - Execution Environment", False, "--execution-environment flag not found")
        
        return True
        
    except Exception as e:
        log_test("cloudbuild.yaml Configuration", False, f"Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("FINAL VERIFICATION TEST SUITE")
    print("Export Endpoints and ReportLab Fallback")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Project ID: {PROJECT_ID}")
    print(f"Test Credentials: {TEST_EMAIL} / {TEST_PASSWORD}")
    print("="*80)
    
    # Test 1: Authentication
    token = authenticate()
    if not token:
        print("\n❌ CRITICAL: Authentication failed. Cannot proceed with API tests.")
        print("\nTest Summary:")
        print(f"Total Tests: {tests_passed + tests_failed}")
        print(f"Passed: {tests_passed}")
        print(f"Failed: {tests_failed}")
        sys.exit(1)
    
    # Test 2: PDF Export
    test_pdf_export(token)
    
    # Test 3: PPT Export
    test_ppt_export(token)
    
    # Test 4: ReportLab Fallback
    test_reportlab_fallback()
    
    # Test 5: cloudbuild.yaml
    test_cloudbuild_config()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {tests_passed + tests_failed}")
    print(f"✅ Passed: {tests_passed}")
    print(f"❌ Failed: {tests_failed}")
    print(f"Success Rate: {(tests_passed / (tests_passed + tests_failed) * 100):.1f}%")
    print("="*80)
    
    if tests_failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {tests_failed} TEST(S) FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
