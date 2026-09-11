#!/usr/bin/env python3
"""
Bug Fix Verification — Comprehensive int→float schema fix for prod data compatibility
Testing 15 scenarios as specified in the review request.
"""
import requests
import json
import sys
from datetime import datetime, timedelta

# Backend URL from review request
BASE_URL = "https://a0ac7ee9-2785-4339-ad6f-6886af7a3f1a.preview.emergentagent.com/api"

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Global token storage
TOKEN = None
HEADERS = {}

# Test results tracking
test_results = []
test_count = 0

def log_test(test_num, description, passed, details=""):
    """Log test result"""
    global test_count
    test_count += 1
    status = "✅ PASS" if passed else "❌ FAIL"
    result = f"Test {test_num}: {status} - {description}"
    if details:
        result += f"\n  Details: {details}"
    print(result)
    test_results.append({
        "test_num": test_num,
        "description": description,
        "passed": passed,
        "details": details
    })
    return passed

def login():
    """Test 1: Login and get JWT token"""
    global TOKEN, HEADERS
    print("\n" + "="*80)
    print("A. DIRECT FIX VERIFICATION — Decimals Accepted")
    print("="*80)
    
    url = f"{BASE_URL}/auth/login"
    data = {
        "username": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    }
    
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            result = response.json()
            TOKEN = result.get("access_token")
            HEADERS = {"Authorization": f"Bearer {TOKEN}"}
            log_test(1, "POST /api/auth/login", True, f"HTTP {response.status_code}, got JWT token")
            return True
        else:
            log_test(1, "POST /api/auth/login", False, f"HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test(1, "POST /api/auth/login", False, f"Exception: {str(e)}")
        return False

def test_get_allocations():
    """Test 2: GET /api/allocations - must not crash with 500"""
    url = f"{BASE_URL}/allocations"
    
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            allocations = response.json()
            count = len(allocations) if isinstance(allocations, list) else "unknown"
            log_test(2, "GET /api/allocations", True, f"HTTP {response.status_code}, returned {count} allocations (any count is fine)")
            return allocations
        else:
            log_test(2, "GET /api/allocations", False, f"HTTP {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log_test(2, "GET /api/allocations", False, f"Exception: {str(e)}")
        return None

def test_get_resources():
    """Test 3: GET /api/resources - should return exactly 5"""
    url = f"{BASE_URL}/resources"
    
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            resources = response.json()
            count = len(resources) if isinstance(resources, list) else 0
            passed = count == 5
            log_test(3, "GET /api/resources", passed, f"HTTP {response.status_code}, returned {count} resources (expected 5)")
            return resources
        else:
            log_test(3, "GET /api/resources", False, f"HTTP {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log_test(3, "GET /api/resources", False, f"Exception: {str(e)}")
        return None

def test_get_projects():
    """Test 4: GET /api/projects - should return exactly 4"""
    url = f"{BASE_URL}/projects"
    
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            projects = response.json()
            count = len(projects) if isinstance(projects, list) else 0
            passed = count == 4
            log_test(4, "GET /api/projects", passed, f"HTTP {response.status_code}, returned {count} projects (expected 4)")
            return projects
        else:
            log_test(4, "GET /api/projects", False, f"HTTP {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log_test(4, "GET /api/projects", False, f"Exception: {str(e)}")
        return None

def test_create_allocation_with_decimal(projects, resources):
    """Test 5: Create allocation with percentage: 12.5 (decimal)"""
    if not projects or not resources:
        log_test(5, "POST /api/allocations with decimal percentage", False, "Missing projects or resources data")
        return None
    
    # Get first project and resource
    project = projects[0]
    resource = resources[0]
    
    project_id = project.get("id")
    resource_id = resource.get("id")
    start_date_raw = project.get("start_date")
    end_date_raw = project.get("end_date")
    
    # Extract just the date part (YYYY-MM-DD) from datetime strings
    # Dates may come as "2026-08-15T10:07:14.226000" or "2026-08-15"
    try:
        start_date = start_date_raw.split("T")[0] if "T" in start_date_raw else start_date_raw
        end_date = end_date_raw.split("T")[0] if "T" in end_date_raw else end_date_raw
    except:
        start_date = start_date_raw
        end_date = end_date_raw
    
    # Calculate a date within project range (use start_date + 7 days or end_date, whichever is earlier)
    try:
        from datetime import datetime, timedelta
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        allocation_end = min(start_dt + timedelta(days=7), end_dt)
        allocation_end_str = allocation_end.strftime("%Y-%m-%d")
    except:
        allocation_end_str = end_date
    
    url = f"{BASE_URL}/allocations"
    payload = {
        "resource_id": resource_id,
        "project_id": project_id,
        "start_date": start_date,
        "end_date": allocation_end_str,
        "percentage": 12.5,  # DECIMAL VALUE - THE FIX
        "allocation_type": "percentage"
    }
    
    try:
        response = requests.post(url, headers=HEADERS, json=payload)
        if response.status_code == 200:
            allocation = response.json()
            allocation_id = allocation.get("id")
            percentage = allocation.get("percentage")
            log_test(5, "POST /api/allocations with percentage: 12.5", True, 
                    f"HTTP {response.status_code}, created allocation with id={allocation_id}, percentage={percentage}")
            return allocation
        else:
            log_test(5, "POST /api/allocations with percentage: 12.5", False, 
                    f"HTTP {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log_test(5, "POST /api/allocations with percentage: 12.5", False, f"Exception: {str(e)}")
        return None

def test_verify_decimal_allocation(allocation_id):
    """Test 6: Verify GET /api/allocations returns the decimal allocation"""
    url = f"{BASE_URL}/allocations"
    
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            allocations = response.json()
            found = False
            for alloc in allocations:
                if alloc.get("id") == allocation_id:
                    found = True
                    percentage = alloc.get("percentage")
                    if percentage == 12.5:
                        log_test(6, "GET /api/allocations contains decimal allocation", True, 
                                f"Found allocation with id={allocation_id}, percentage={percentage}")
                        return True
                    else:
                        log_test(6, "GET /api/allocations contains decimal allocation", False, 
                                f"Found allocation but percentage={percentage} (expected 12.5)")
                        return False
            
            if not found:
                log_test(6, "GET /api/allocations contains decimal allocation", False, 
                        f"Allocation with id={allocation_id} not found in list")
                return False
        else:
            log_test(6, "GET /api/allocations contains decimal allocation", False, 
                    f"HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test(6, "GET /api/allocations contains decimal allocation", False, f"Exception: {str(e)}")
        return False

def test_delete_allocation(allocation_id):
    """Test 7: DELETE /api/allocations/{id}"""
    url = f"{BASE_URL}/allocations/{allocation_id}"
    
    try:
        response = requests.delete(url, headers=HEADERS)
        if response.status_code == 200:
            log_test(7, f"DELETE /api/allocations/{allocation_id}", True, f"HTTP {response.status_code}")
            return True
        else:
            log_test(7, f"DELETE /api/allocations/{allocation_id}", False, 
                    f"HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test(7, f"DELETE /api/allocations/{allocation_id}", False, f"Exception: {str(e)}")
        return False

def test_create_resource_with_decimal_capacity():
    """Test 8: POST /api/resources with standard_capacity: 87.5"""
    print("\n" + "="*80)
    print("B. CREATE RESOURCE WITH DECIMAL CAPACITY")
    print("="*80)
    
    url = f"{BASE_URL}/resources"
    payload = {
        "name": "Test Part Time",
        "role": "Developer",
        "standard_capacity": 87.5  # DECIMAL VALUE - THE FIX
    }
    
    try:
        response = requests.post(url, headers=HEADERS, json=payload)
        if response.status_code == 200:
            resource = response.json()
            resource_id = resource.get("id")
            capacity = resource.get("standard_capacity")
            log_test(8, "POST /api/resources with standard_capacity: 87.5", True, 
                    f"HTTP {response.status_code}, created resource with id={resource_id}, standard_capacity={capacity}")
            return resource
        else:
            log_test(8, "POST /api/resources with standard_capacity: 87.5", False, 
                    f"HTTP {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log_test(8, "POST /api/resources with standard_capacity: 87.5", False, f"Exception: {str(e)}")
        return None

def test_verify_decimal_capacity(resource_id):
    """Test 9: Verify GET /api/resources returns the decimal capacity"""
    url = f"{BASE_URL}/resources"
    
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            resources = response.json()
            found = False
            for res in resources:
                if res.get("id") == resource_id:
                    found = True
                    capacity = res.get("standard_capacity")
                    if capacity == 87.5:
                        log_test(9, "GET /api/resources verifies decimal capacity", True, 
                                f"Found resource with id={resource_id}, standard_capacity={capacity}")
                        return True
                    else:
                        log_test(9, "GET /api/resources verifies decimal capacity", False, 
                                f"Found resource but standard_capacity={capacity} (expected 87.5)")
                        return False
            
            if not found:
                log_test(9, "GET /api/resources verifies decimal capacity", False, 
                        f"Resource with id={resource_id} not found in list")
                return False
        else:
            log_test(9, "GET /api/resources verifies decimal capacity", False, 
                    f"HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test(9, "GET /api/resources verifies decimal capacity", False, f"Exception: {str(e)}")
        return False

def test_delete_resource(resource_id):
    """Test 10: DELETE /api/resources/{id}"""
    url = f"{BASE_URL}/resources/{resource_id}"
    
    try:
        response = requests.delete(url, headers=HEADERS)
        if response.status_code == 200:
            log_test(10, f"DELETE /api/resources/{resource_id}", True, f"HTTP {response.status_code}")
            return True
        else:
            log_test(10, f"DELETE /api/resources/{resource_id}", False, 
                    f"HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test(10, f"DELETE /api/resources/{resource_id}", False, f"Exception: {str(e)}")
        return False

def test_regression_endpoints():
    """Tests 11-14: Regression - no other endpoints broken"""
    print("\n" + "="*80)
    print("C. REGRESSION — No Other Endpoints Broken")
    print("="*80)
    
    endpoints = [
        (11, "GET /api/portfolio", f"{BASE_URL}/portfolio"),
        (12, "GET /api/dashboard/action-items", f"{BASE_URL}/dashboard/action-items"),
        (13, "GET /api/tenant/modules", f"{BASE_URL}/tenant/modules"),
        (14, "GET /api/health", f"{BASE_URL}/health"),
    ]
    
    all_passed = True
    for test_num, description, url in endpoints:
        try:
            response = requests.get(url, headers=HEADERS)
            if response.status_code == 200:
                # Special check for tenant/modules - should return 17 modules
                if "tenant/modules" in url:
                    data = response.json()
                    modules = data.get("modules", {})
                    module_count = len(modules)
                    passed = module_count == 17
                    log_test(test_num, description, passed, 
                            f"HTTP {response.status_code}, returned {module_count} modules (expected 17)")
                    all_passed = all_passed and passed
                else:
                    log_test(test_num, description, True, f"HTTP {response.status_code}")
            else:
                log_test(test_num, description, False, f"HTTP {response.status_code}: {response.text}")
                all_passed = False
        except Exception as e:
            log_test(test_num, description, False, f"Exception: {str(e)}")
            all_passed = False
    
    return all_passed

def test_backend_logs():
    """Test 15: Check backend logs for ResponseValidationError"""
    print("\n" + "="*80)
    print("D. BACKEND LOG CHECK")
    print("="*80)
    
    import subprocess
    
    try:
        # Check backend error logs for ResponseValidationError, TypeError, or 500 traceback
        result = subprocess.run(
            ["grep", "-E", "ResponseValidationError|TypeError.*percentage|500.*traceback", 
             "/var/log/supervisor/backend.err.log"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            # Found errors
            errors = result.stdout.strip()
            log_test(15, "Backend logs check (no ResponseValidationError)", False, 
                    f"Found errors in logs:\n{errors[:500]}")
            return False
        else:
            # No errors found (grep returns 1 when no match)
            log_test(15, "Backend logs check (no ResponseValidationError)", True, 
                    "No ResponseValidationError, TypeError, or 500 traceback found during test run")
            return True
    except Exception as e:
        log_test(15, "Backend logs check (no ResponseValidationError)", False, f"Exception: {str(e)}")
        return False

def print_summary():
    """Print final summary"""
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    
    passed_count = sum(1 for r in test_results if r["passed"])
    total_count = len(test_results)
    
    print(f"\nTotal Tests: {total_count}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {total_count - passed_count}")
    print(f"Success Rate: {(passed_count/total_count*100):.1f}%")
    
    # Print failed tests
    failed_tests = [r for r in test_results if not r["passed"]]
    if failed_tests:
        print("\n❌ FAILED TESTS:")
        for test in failed_tests:
            print(f"  Test {test['test_num']}: {test['description']}")
            if test['details']:
                print(f"    {test['details']}")
    
    # Final verdict
    print("\n" + "="*80)
    if passed_count == total_count:
        print("SCHEMA FIX VERDICT: ✅ PASS")
        print("All 15 tests passed. The int→float schema fix is working correctly.")
        print("Decimal values (12.5, 87.5) are accepted without ResponseValidationError.")
    else:
        print("SCHEMA FIX VERDICT: ❌ FAIL")
        print(f"{total_count - passed_count} test(s) failed. See details above.")
    print("="*80)
    
    return passed_count == total_count

def main():
    """Run all tests"""
    print("="*80)
    print("BUG FIX VERIFICATION — Comprehensive int→float schema fix")
    print("Testing 15 scenarios for prod data compatibility")
    print("="*80)
    
    # Test 1: Login
    if not login():
        print("\n❌ Login failed. Cannot proceed with tests.")
        sys.exit(1)
    
    # Test 2: GET allocations
    allocations = test_get_allocations()
    
    # Test 3: GET resources
    resources = test_get_resources()
    
    # Test 4: GET projects
    projects = test_get_projects()
    
    # Test 5: Create allocation with decimal percentage
    new_allocation = test_create_allocation_with_decimal(projects, resources)
    
    # Test 6: Verify decimal allocation in list
    if new_allocation:
        allocation_id = new_allocation.get("id")
        test_verify_decimal_allocation(allocation_id)
        
        # Test 7: Delete allocation
        test_delete_allocation(allocation_id)
    else:
        log_test(6, "GET /api/allocations contains decimal allocation", False, "Skipped - allocation creation failed")
        log_test(7, "DELETE /api/allocations/{id}", False, "Skipped - allocation creation failed")
    
    # Test 8: Create resource with decimal capacity
    new_resource = test_create_resource_with_decimal_capacity()
    
    # Test 9: Verify decimal capacity
    if new_resource:
        resource_id = new_resource.get("id")
        test_verify_decimal_capacity(resource_id)
        
        # Test 10: Delete resource
        test_delete_resource(resource_id)
    else:
        log_test(9, "GET /api/resources verifies decimal capacity", False, "Skipped - resource creation failed")
        log_test(10, "DELETE /api/resources/{id}", False, "Skipped - resource creation failed")
    
    # Tests 11-14: Regression
    test_regression_endpoints()
    
    # Test 15: Backend logs
    test_backend_logs()
    
    # Print summary
    all_passed = print_summary()
    
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()
