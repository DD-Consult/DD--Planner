#!/usr/bin/env python3
"""
Export Endpoints Testing - Playwright-based PDF/PPT Generation
Tests the 4 newly-rewritten export endpoints that use headless Chromium.

Endpoints tested:
1. GET /api/projects/{project_id}/export/pdf
2. GET /api/projects/{project_id}/export/ppt
3. GET /api/projects/{project_id}/export/wbs/pdf
4. GET /api/projects/{project_id}/export/wbs/ppt
"""

import requests
import os
import subprocess
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8001"
API_BASE = f"{BASE_URL}/api"
TIMEOUT = 60  # 60 seconds per call (Playwright rendering can take time)

# Test credentials from test_credentials.md
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Test results tracking
test_results = []
total_tests = 0
passed_tests = 0
failed_tests = 0


def log_test(test_name, passed, status_code=None, reason="", details=None):
    """Log test result"""
    global total_tests, passed_tests, failed_tests
    total_tests += 1
    if passed:
        passed_tests += 1
        result = "✅ PASS"
    else:
        failed_tests += 1
        result = "❌ FAIL"
    
    status_info = f" (Status: {status_code})" if status_code else ""
    test_results.append({
        "test": test_name,
        "result": result,
        "status_code": status_code,
        "reason": reason,
        "details": details
    })
    print(f"{result}: {test_name}{status_info}")
    if reason:
        print(f"   Reason: {reason}")
    if details:
        print(f"   Details: {details}")


def login(email, password):
    """Login and return JWT token"""
    try:
        response = requests.post(
            f"{API_BASE}/auth/login",
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            print(f"✅ Login successful for {email}")
            return token
        else:
            print(f"❌ Login failed for {email}: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Login exception for {email}: {str(e)}")
        return None


def get_headers(token):
    """Get authorization headers"""
    return {"Authorization": f"Bearer {token}"}


def get_first_project_id(token):
    """Get the first project ID for testing"""
    try:
        response = requests.get(
            f"{API_BASE}/projects",
            headers=get_headers(token),
            timeout=10
        )
        if response.status_code == 200:
            projects = response.json()
            if projects and len(projects) > 0:
                project_id = projects[0].get("id") or str(projects[0].get("_id"))
                project_name = projects[0].get("name", "Unknown")
                print(f"✅ Using project: {project_name} (ID: {project_id})")
                return project_id, project_name
        print("❌ No projects found")
        return None, None
    except Exception as e:
        print(f"❌ Error getting project ID: {str(e)}")
        return None, None


def validate_pdf_file(filepath):
    """Validate PDF file using pdfinfo"""
    try:
        result = subprocess.run(
            ["pdfinfo", filepath],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Extract page count
            for line in result.stdout.split('\n'):
                if line.startswith('Pages:'):
                    pages = line.split(':')[1].strip()
                    return True, f"Valid PDF with {pages} page(s)"
            return True, "Valid PDF"
        else:
            return False, f"pdfinfo failed: {result.stderr}"
    except FileNotFoundError:
        return False, "pdfinfo not installed"
    except Exception as e:
        return False, f"Validation error: {str(e)}"


def validate_pptx_file(filepath):
    """Validate PPTX file using python-pptx"""
    try:
        from pptx import Presentation
        prs = Presentation(filepath)
        slide_count = len(prs.slides)
        return True, f"Valid PPTX with {slide_count} slide(s)"
    except ImportError:
        return False, "python-pptx not installed"
    except Exception as e:
        return False, f"Validation error: {str(e)}"


def test_export_endpoint(endpoint_path, expected_mime, file_extension, validator_func, 
                         token, test_prefix, min_size_kb=50):
    """
    Generic test function for export endpoints
    
    Args:
        endpoint_path: API endpoint path (e.g., "/api/projects/{project_id}/export/pdf")
        expected_mime: Expected Content-Type
        file_extension: File extension for saving (e.g., "pdf", "pptx")
        validator_func: Function to validate the file (validate_pdf_file or validate_pptx_file)
        token: JWT token
        test_prefix: Test number prefix (e.g., "1.1")
        min_size_kb: Minimum expected file size in KB
    """
    
    # Test 1: Valid request with auth
    try:
        print(f"\n📥 Testing {endpoint_path}...")
        response = requests.get(
            f"{BASE_URL}{endpoint_path}",
            headers=get_headers(token),
            timeout=TIMEOUT,
            stream=True
        )
        
        if response.status_code == 200:
            # Check Content-Type
            content_type = response.headers.get("Content-Type", "")
            if expected_mime not in content_type:
                log_test(
                    f"{test_prefix} - Valid request (Content-Type)",
                    False,
                    200,
                    f"Wrong Content-Type: expected '{expected_mime}', got '{content_type}'"
                )
                return
            
            # Check Content-Disposition
            content_disposition = response.headers.get("Content-Disposition", "")
            if "attachment" not in content_disposition or "filename=" not in content_disposition:
                log_test(
                    f"{test_prefix} - Valid request (Content-Disposition)",
                    False,
                    200,
                    f"Invalid Content-Disposition: '{content_disposition}'"
                )
                return
            
            # Check file size
            file_size = len(response.content)
            file_size_kb = file_size / 1024
            if file_size_kb < min_size_kb:
                log_test(
                    f"{test_prefix} - Valid request (file size)",
                    False,
                    200,
                    f"File too small: {file_size_kb:.1f}KB (expected >{min_size_kb}KB)"
                )
                return
            
            # Save file to /tmp/
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"export_test_{timestamp}.{file_extension}"
            filepath = f"/tmp/{filename}"
            
            with open(filepath, "wb") as f:
                f.write(response.content)
            
            # Validate file
            is_valid, validation_msg = validator_func(filepath)
            
            if is_valid:
                log_test(
                    f"{test_prefix} - Valid request",
                    True,
                    200,
                    f"File size: {file_size_kb:.1f}KB, {validation_msg}",
                    f"Saved to {filepath}"
                )
            else:
                log_test(
                    f"{test_prefix} - Valid request (file validation)",
                    False,
                    200,
                    f"File validation failed: {validation_msg}"
                )
        else:
            log_test(
                f"{test_prefix} - Valid request",
                False,
                response.status_code,
                response.text[:500]
            )
    except requests.exceptions.Timeout:
        log_test(
            f"{test_prefix} - Valid request",
            False,
            None,
            f"Request timeout after {TIMEOUT}s"
        )
    except Exception as e:
        log_test(
            f"{test_prefix} - Valid request",
            False,
            None,
            str(e)
        )


def test_404_scenario(endpoint_path, token, test_prefix):
    """Test 404 for non-existent project"""
    try:
        fake_id = "nonexistent-id-12345"
        fake_endpoint = endpoint_path.replace("{project_id}", fake_id)
        
        response = requests.get(
            f"{BASE_URL}{fake_endpoint}",
            headers=get_headers(token),
            timeout=10
        )
        
        if response.status_code == 404:
            log_test(
                f"{test_prefix} - Non-existent project (404)",
                True,
                404,
                "Correctly returned 404"
            )
        else:
            log_test(
                f"{test_prefix} - Non-existent project (404)",
                False,
                response.status_code,
                f"Expected 404, got {response.status_code}"
            )
    except Exception as e:
        log_test(
            f"{test_prefix} - Non-existent project (404)",
            False,
            None,
            str(e)
        )


def test_401_scenario(endpoint_path, test_prefix):
    """Test 401 for missing auth token"""
    try:
        response = requests.get(
            f"{BASE_URL}{endpoint_path}",
            timeout=10
        )
        
        if response.status_code == 401:
            log_test(
                f"{test_prefix} - No auth token (401)",
                True,
                401,
                "Correctly returned 401"
            )
        else:
            log_test(
                f"{test_prefix} - No auth token (401)",
                False,
                response.status_code,
                f"Expected 401, got {response.status_code}"
            )
    except Exception as e:
        log_test(
            f"{test_prefix} - No auth token (401)",
            False,
            None,
            str(e)
        )


def test_all_export_endpoints(token, project_id):
    """Test all 4 export endpoints"""
    
    # Endpoint 1: Project PDF
    print("\n" + "="*80)
    print("TEST 1: GET /api/projects/{project_id}/export/pdf")
    print("="*80)
    endpoint = f"/api/projects/{project_id}/export/pdf"
    test_export_endpoint(
        endpoint,
        "application/pdf",
        "pdf",
        validate_pdf_file,
        token,
        "1.1",
        min_size_kb=50
    )
    test_404_scenario("/api/projects/{project_id}/export/pdf", token, "1.2")
    test_401_scenario(endpoint, "1.3")
    
    # Endpoint 2: Project PPT
    print("\n" + "="*80)
    print("TEST 2: GET /api/projects/{project_id}/export/ppt")
    print("="*80)
    endpoint = f"/api/projects/{project_id}/export/ppt"
    test_export_endpoint(
        endpoint,
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "pptx",
        validate_pptx_file,
        token,
        "2.1",
        min_size_kb=50
    )
    test_404_scenario("/api/projects/{project_id}/export/ppt", token, "2.2")
    test_401_scenario(endpoint, "2.3")
    
    # Endpoint 3: WBS PDF
    print("\n" + "="*80)
    print("TEST 3: GET /api/projects/{project_id}/export/wbs/pdf")
    print("="*80)
    endpoint = f"/api/projects/{project_id}/export/wbs/pdf"
    test_export_endpoint(
        endpoint,
        "application/pdf",
        "pdf",
        validate_pdf_file,
        token,
        "3.1",
        min_size_kb=50
    )
    test_404_scenario("/api/projects/{project_id}/export/wbs/pdf", token, "3.2")
    test_401_scenario(endpoint, "3.3")
    
    # Endpoint 4: WBS PPT
    print("\n" + "="*80)
    print("TEST 4: GET /api/projects/{project_id}/export/wbs/ppt")
    print("="*80)
    endpoint = f"/api/projects/{project_id}/export/wbs/ppt"
    test_export_endpoint(
        endpoint,
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "pptx",
        validate_pptx_file,
        token,
        "4.1",
        min_size_kb=50
    )
    test_404_scenario("/api/projects/{project_id}/export/wbs/ppt", token, "4.2")
    test_401_scenario(endpoint, "4.3")


def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY - EXPORT ENDPOINTS")
    print("="*80)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} ❌")
    if total_tests > 0:
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
    
    if failed_tests > 0:
        print("\n" + "="*80)
        print("FAILED TESTS DETAILS")
        print("="*80)
        for result in test_results:
            if "❌" in result["result"]:
                print(f"\n{result['test']}")
                print(f"  Status Code: {result['status_code']}")
                print(f"  Reason: {result['reason']}")
                if result.get('details'):
                    print(f"  Details: {result['details']}")


def check_backend_logs():
    """Check backend logs for any errors during export"""
    print("\n" + "="*80)
    print("BACKEND LOGS (Last 50 lines)")
    print("="*80)
    try:
        result = subprocess.run(
            ["tail", "-n", "50", "/var/log/supervisor/backend.err.log"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.stdout:
            print(result.stdout)
        else:
            print("No error logs found")
    except Exception as e:
        print(f"Could not read logs: {str(e)}")


def main():
    """Main test execution"""
    print("="*80)
    print("EXPORT ENDPOINTS TESTING - Playwright-based PDF/PPT Generation")
    print("Testing 4 endpoints with comprehensive validation")
    print("="*80)
    
    # Login
    print("\n🔐 Logging in as admin...")
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    
    if not admin_token:
        print("❌ CRITICAL: Admin login failed. Cannot proceed with tests.")
        return 1
    
    # Get project ID
    print("\n📋 Getting test project...")
    project_id, project_name = get_first_project_id(admin_token)
    
    if not project_id:
        print("❌ CRITICAL: No projects found. Cannot proceed with tests.")
        return 1
    
    # Run all tests
    test_all_export_endpoints(admin_token, project_id)
    
    # Print summary
    print_summary()
    
    # Check backend logs if there were failures
    if failed_tests > 0:
        check_backend_logs()
    
    # Return exit code based on results
    return 0 if failed_tests == 0 else 1


if __name__ == "__main__":
    exit(main())
