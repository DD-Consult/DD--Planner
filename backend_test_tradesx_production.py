#!/usr/bin/env python3
"""
Test script for TradesX Phase 2 Production Build endpoints
Review Request: Verify project 6a81afb545f7c98ef63971fd endpoints return HTTP 200
"""

import requests
import json
import sys
from typing import Dict, Any

# Configuration
BASE_URL = "https://ddplan-502760053858.australia-southeast1.run.app"
EMAIL = "don@ddconsult.tech"
PASSWORD = "@Ddplanner2026"
PROJECT_ID = "6a81afb545f7c98ef63971fd"

# Test results tracking
test_results = []
total_tests = 0
passed_tests = 0
failed_tests = 0

def log_test(test_name: str, passed: bool, status_code: int = None, details: str = ""):
    """Log test result"""
    global total_tests, passed_tests, failed_tests
    total_tests += 1
    if passed:
        passed_tests += 1
        status = "✅ PASSED"
    else:
        failed_tests += 1
        status = "❌ FAILED"
    
    result = {
        "test": test_name,
        "status": status,
        "status_code": status_code,
        "details": details
    }
    test_results.append(result)
    print(f"{status} - {test_name}")
    if status_code:
        print(f"  Status Code: {status_code}")
    if details:
        print(f"  Details: {details}")
    print()

def authenticate() -> str:
    """Authenticate and return JWT token"""
    print("=" * 80)
    print("AUTHENTICATION")
    print("=" * 80)
    
    try:
        # OAuth2 form-encoded login
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={
                "username": EMAIL,
                "password": PASSWORD
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            if token:
                log_test("Authentication", True, 200, f"Successfully authenticated as {EMAIL}")
                return token
            else:
                log_test("Authentication", False, 200, "No access_token in response")
                return None
        else:
            log_test("Authentication", False, response.status_code, f"Response: {response.text[:200]}")
            return None
            
    except Exception as e:
        log_test("Authentication", False, details=f"Exception: {str(e)}")
        return None

def test_endpoint(name: str, method: str, url: str, headers: Dict[str, str], 
                  expected_status: int = 200, check_content_type: str = None) -> bool:
    """Test a single endpoint"""
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=60)
        else:
            log_test(name, False, details=f"Unsupported method: {method}")
            return False
        
        # Check status code
        if response.status_code != expected_status:
            log_test(name, False, response.status_code, 
                    f"Expected {expected_status}, got {response.status_code}. Response: {response.text[:200]}")
            return False
        
        # Check for 500/502 errors
        if response.status_code in [500, 502]:
            log_test(name, False, response.status_code, "Server error detected")
            return False
        
        # Check content type if specified
        if check_content_type:
            content_type = response.headers.get("Content-Type", "")
            if check_content_type not in content_type:
                log_test(name, False, response.status_code, 
                        f"Expected Content-Type containing '{check_content_type}', got '{content_type}'")
                return False
        
        # Additional checks based on content type
        details = f"Status: {response.status_code}"
        
        if "application/json" in response.headers.get("Content-Type", ""):
            try:
                data = response.json()
                if isinstance(data, dict):
                    details += f", Keys: {list(data.keys())[:5]}"
                elif isinstance(data, list):
                    details += f", Array length: {len(data)}"
            except:
                pass
        elif "application/pdf" in response.headers.get("Content-Type", ""):
            size_kb = len(response.content) / 1024
            details += f", PDF size: {size_kb:.1f}KB"
            # Verify PDF magic bytes
            if response.content[:4] == b'%PDF':
                details += ", Valid PDF"
            else:
                log_test(name, False, response.status_code, "Invalid PDF content (missing %PDF header)")
                return False
        else:
            size_kb = len(response.content) / 1024
            details += f", Content size: {size_kb:.1f}KB"
        
        log_test(name, True, response.status_code, details)
        return True
        
    except requests.exceptions.Timeout:
        log_test(name, False, details="Request timeout (60s)")
        return False
    except Exception as e:
        log_test(name, False, details=f"Exception: {str(e)}")
        return False

def main():
    """Main test execution"""
    print("\n" + "=" * 80)
    print("TRADESX PHASE 2 PRODUCTION BUILD - ENDPOINT TESTING")
    print("=" * 80)
    print(f"Base URL: {BASE_URL}")
    print(f"Project ID: {PROJECT_ID}")
    print(f"Test User: {EMAIL}")
    print("=" * 80)
    print()
    
    # Step 1: Authenticate
    token = authenticate()
    if not token:
        print("\n❌ CRITICAL: Authentication failed. Cannot proceed with endpoint tests.")
        sys.exit(1)
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print("\n" + "=" * 80)
    print("ENDPOINT TESTING")
    print("=" * 80)
    print()
    
    # Test 2: GET /api/projects/{project_id}
    test_endpoint(
        "Test 2: GET Project Details",
        "GET",
        f"{BASE_URL}/api/projects/{PROJECT_ID}",
        headers
    )
    
    # Test 3: GET /api/reports/planned-vs-actual/project/{project_id}
    test_endpoint(
        "Test 3: GET Planned vs Actual Report",
        "GET",
        f"{BASE_URL}/api/reports/planned-vs-actual/project/{PROJECT_ID}",
        headers
    )
    
    # Test 4: GET /api/projects/{project_id}/risks
    test_endpoint(
        "Test 4: GET Project Risks",
        "GET",
        f"{BASE_URL}/api/projects/{PROJECT_ID}/risks",
        headers
    )
    
    # Test 5: GET /api/projects/{project_id}/allocations
    test_endpoint(
        "Test 5: GET Project Allocations",
        "GET",
        f"{BASE_URL}/api/projects/{PROJECT_ID}/allocations",
        headers
    )
    
    # Test 6: GET /api/status-updates/project/{project_id}?limit=5
    test_endpoint(
        "Test 6: GET Status Updates (limit=5)",
        "GET",
        f"{BASE_URL}/api/status-updates/project/{PROJECT_ID}?limit=5",
        headers
    )
    
    # Test 7: GET /api/projects/{project_id}/export/pdf
    test_endpoint(
        "Test 7: GET Export PDF",
        "GET",
        f"{BASE_URL}/api/projects/{PROJECT_ID}/export/pdf",
        headers,
        check_content_type="application/pdf"
    )
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} ❌")
    print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
    print("=" * 80)
    
    # Detailed results
    print("\nDETAILED RESULTS:")
    print("-" * 80)
    for result in test_results:
        print(f"{result['status']} - {result['test']}")
        if result['status_code']:
            print(f"  Status Code: {result['status_code']}")
        if result['details']:
            print(f"  Details: {result['details']}")
    
    # Check for 500/502 errors
    print("\n" + "=" * 80)
    print("ERROR CHECK")
    print("=" * 80)
    has_server_errors = any(
        r.get('status_code') in [500, 502] 
        for r in test_results 
        if r.get('status_code')
    )
    
    if has_server_errors:
        print("❌ CRITICAL: 500 or 502 errors detected!")
    else:
        print("✅ No 500 or 502 errors detected")
    
    print("=" * 80)
    
    # Exit code
    if failed_tests == 0:
        print("\n✅ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print(f"\n❌ {failed_tests} TEST(S) FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
