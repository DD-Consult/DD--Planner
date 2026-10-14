#!/usr/bin/env python3
"""
Backend Test: My Allocations Endpoint Fix
==========================================
Tests the fix for GET /api/my-allocations endpoint that was returning
non-overlapping allocations (causing "Total in Period = 0.0h" display).

The fix filters allocations to only those overlapping the selected period,
computed in Python.

Test Credentials: admin@test.com / admin123 (from /app/memory/test_credentials.md)
Backend URL: https://ddplanner-fixes.preview.emergentagent.com/api
"""

import requests
import sys
from datetime import datetime, date, timedelta
from typing import List, Dict, Any

# Backend URL from frontend/.env
BACKEND_URL = "https://ddplanner-fixes.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "admin123"

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def log_test(message: str, status: str = "INFO"):
    """Log test message with color coding"""
    color = {
        "PASS": GREEN,
        "FAIL": RED,
        "INFO": BLUE,
        "WARN": YELLOW
    }.get(status, RESET)
    print(f"{color}[{status}]{RESET} {message}")

def login() -> str:
    """Login and return JWT token"""
    log_test("Authenticating with admin@test.com...", "INFO")
    
    # Use form-encoded login as per OAuth2PasswordRequestForm
    response = requests.post(
        f"{BACKEND_URL}/auth/login",
        data={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
    )
    
    if response.status_code != 200:
        log_test(f"Login failed: {response.status_code} - {response.text}", "FAIL")
        sys.exit(1)
    
    data = response.json()
    token = data.get("access_token")
    user = data.get("user", {})
    
    log_test(f"✓ Login successful. User: {user.get('email')}, Role: {user.get('role')}", "PASS")
    return token

def parse_date(date_str: str) -> date:
    """Parse ISO date string to date object"""
    if 'T' in date_str:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
    return datetime.strptime(date_str, '%Y-%m-%d').date()

def check_overlap(alloc_start: date, alloc_end: date, period_start: date, period_end: date) -> bool:
    """Check if allocation overlaps with period"""
    return alloc_start <= period_end and alloc_end >= period_start

def test_my_allocations_endpoint(token: str, period: str) -> Dict[str, Any]:
    """Test GET /api/my-allocations endpoint for a specific period"""
    log_test(f"\n{'='*80}", "INFO")
    log_test(f"Testing GET /api/my-allocations?period={period}", "INFO")
    log_test(f"{'='*80}", "INFO")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BACKEND_URL}/my-allocations",
        params={"period": period},
        headers=headers
    )
    
    # Test 1: HTTP 200 response
    if response.status_code != 200:
        log_test(f"✗ Expected HTTP 200, got {response.status_code}", "FAIL")
        log_test(f"Response: {response.text}", "FAIL")
        return {"passed": False, "period": period}
    
    log_test(f"✓ HTTP 200 response received", "PASS")
    
    data = response.json()
    
    # Test 2: Response structure
    required_keys = ["period", "period_start", "period_end", "resource", "summary", "allocations"]
    missing_keys = [key for key in required_keys if key not in data]
    
    if missing_keys:
        log_test(f"✗ Missing required keys: {missing_keys}", "FAIL")
        return {"passed": False, "period": period}
    
    log_test(f"✓ Response has all required keys: {required_keys}", "PASS")
    
    # Extract data
    period_start = parse_date(data["period_start"])
    period_end = parse_date(data["period_end"])
    resource = data.get("resource")
    summary = data["summary"]
    allocations = data["allocations"]
    
    log_test(f"\nPeriod: {period}", "INFO")
    log_test(f"Period Start: {period_start}", "INFO")
    log_test(f"Period End: {period_end}", "INFO")
    log_test(f"Resource: {resource.get('name') if resource else 'None'} (ID: {resource.get('id') if resource else 'None'})", "INFO")
    log_test(f"Total Allocations: {len(allocations)}", "INFO")
    
    # Test 3: Summary structure
    summary_keys = ["total_allocations", "capacity_used_percentage", "is_over_capacity", 
                    "total_weekly_hours", "available_hours_per_week", "total_period_hours", "standard_capacity"]
    missing_summary_keys = [key for key in summary_keys if key not in summary]
    
    if missing_summary_keys:
        log_test(f"✗ Missing summary keys: {missing_summary_keys}", "FAIL")
        return {"passed": False, "period": period}
    
    log_test(f"✓ Summary has all required keys", "PASS")
    log_test(f"\nSummary:", "INFO")
    log_test(f"  - Total Allocations: {summary['total_allocations']}", "INFO")
    log_test(f"  - Capacity Used: {summary['capacity_used_percentage']}%", "INFO")
    log_test(f"  - Is Over Capacity: {summary['is_over_capacity']}", "INFO")
    log_test(f"  - Total Weekly Hours: {summary['total_weekly_hours']}h", "INFO")
    log_test(f"  - Available Hours/Week: {summary['available_hours_per_week']}h", "INFO")
    log_test(f"  - Total Period Hours: {summary['total_period_hours']}h", "INFO")
    log_test(f"  - Standard Capacity: {summary['standard_capacity']}%", "INFO")
    
    # If no resource linked, that's valid - return success
    if not resource:
        log_test(f"\n✓ No resource linked to admin account (valid scenario)", "PASS")
        return {
            "passed": True,
            "period": period,
            "period_start": period_start,
            "period_end": period_end,
            "allocations": [],
            "no_resource": True
        }
    
    # Test 4: Core assertion - no non-overlapping allocations
    log_test(f"\n{'='*80}", "INFO")
    log_test(f"CORE ASSERTION 1: No non-overlapping allocations", "INFO")
    log_test(f"{'='*80}", "INFO")
    
    non_overlapping = []
    overlapping_count = 0
    
    for i, alloc in enumerate(allocations, 1):
        alloc_start = parse_date(alloc["start_date"])
        alloc_end = parse_date(alloc["end_date"])
        
        overlaps = check_overlap(alloc_start, alloc_end, period_start, period_end)
        
        if not overlaps:
            non_overlapping.append({
                "index": i,
                "id": alloc["id"],
                "project_name": alloc["project_name"],
                "start_date": alloc_start,
                "end_date": alloc_end,
                "weekly_hours": alloc["weekly_hours"],
                "period_hours": alloc["period_hours"]
            })
            log_test(f"✗ Allocation #{i} does NOT overlap period:", "FAIL")
            log_test(f"    Project: {alloc['project_name']}", "FAIL")
            log_test(f"    Allocation: {alloc_start} to {alloc_end}", "FAIL")
            log_test(f"    Period: {period_start} to {period_end}", "FAIL")
            log_test(f"    Weekly Hours: {alloc['weekly_hours']}h", "FAIL")
            log_test(f"    Period Hours: {alloc['period_hours']}h", "FAIL")
        else:
            overlapping_count += 1
    
    if non_overlapping:
        log_test(f"\n✗ CRITICAL FAILURE: Found {len(non_overlapping)} non-overlapping allocations!", "FAIL")
        return {
            "passed": False,
            "period": period,
            "period_start": period_start,
            "period_end": period_end,
            "allocations": allocations,
            "non_overlapping": non_overlapping
        }
    
    log_test(f"✓ All {overlapping_count} allocations overlap the period", "PASS")
    
    # Test 5: Core assertion - period_hours correctness
    log_test(f"\n{'='*80}", "INFO")
    log_test(f"CORE ASSERTION 2: period_hours correctness", "INFO")
    log_test(f"{'='*80}", "INFO")
    
    invalid_period_hours = []
    
    for i, alloc in enumerate(allocations, 1):
        weekly_hours = alloc["weekly_hours"]
        period_hours = alloc["period_hours"]
        
        # If weekly_hours > 0 but period_hours == 0.0, that's a failure
        if weekly_hours > 0 and period_hours == 0.0:
            invalid_period_hours.append({
                "index": i,
                "id": alloc["id"],
                "project_name": alloc["project_name"],
                "start_date": alloc["start_date"],
                "end_date": alloc["end_date"],
                "weekly_hours": weekly_hours,
                "period_hours": period_hours
            })
            log_test(f"✗ Allocation #{i} has weekly_hours > 0 but period_hours == 0.0:", "FAIL")
            log_test(f"    Project: {alloc['project_name']}", "FAIL")
            log_test(f"    Weekly Hours: {weekly_hours}h", "FAIL")
            log_test(f"    Period Hours: {period_hours}h", "FAIL")
    
    if invalid_period_hours:
        log_test(f"\n✗ CRITICAL FAILURE: Found {len(invalid_period_hours)} allocations with invalid period_hours!", "FAIL")
        return {
            "passed": False,
            "period": period,
            "period_start": period_start,
            "period_end": period_end,
            "allocations": allocations,
            "invalid_period_hours": invalid_period_hours
        }
    
    log_test(f"✓ All allocations have correct period_hours (> 0 when weekly_hours > 0)", "PASS")
    
    # Display sample allocations
    log_test(f"\n{'='*80}", "INFO")
    log_test(f"Sample Allocations (first 5):", "INFO")
    log_test(f"{'='*80}", "INFO")
    
    for i, alloc in enumerate(allocations[:5], 1):
        log_test(f"\nAllocation #{i}:", "INFO")
        log_test(f"  Project: {alloc['project_name']} ({alloc.get('client_name', 'N/A')})", "INFO")
        log_test(f"  Start Date: {alloc['start_date']}", "INFO")
        log_test(f"  End Date: {alloc['end_date']}", "INFO")
        log_test(f"  Weekly Hours: {alloc['weekly_hours']}h", "INFO")
        log_test(f"  Period Hours: {alloc['period_hours']}h", "INFO")
        log_test(f"  Percentage: {alloc['percentage']}%", "INFO")
        log_test(f"  Role: {alloc.get('role', 'N/A')}", "INFO")
    
    return {
        "passed": True,
        "period": period,
        "period_start": period_start,
        "period_end": period_end,
        "allocations": allocations,
        "summary": summary
    }

def test_allocations_regression(token: str) -> bool:
    """Test GET /api/allocations regression check"""
    log_test(f"\n{'='*80}", "INFO")
    log_test(f"REGRESSION CHECK: GET /api/allocations", "INFO")
    log_test(f"{'='*80}", "INFO")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BACKEND_URL}/allocations",
        headers=headers
    )
    
    if response.status_code != 200:
        log_test(f"✗ Expected HTTP 200, got {response.status_code}", "FAIL")
        return False
    
    log_test(f"✓ HTTP 200 response received", "PASS")
    
    data = response.json()
    
    if not isinstance(data, list):
        log_test(f"✗ Expected list response, got {type(data)}", "FAIL")
        return False
    
    log_test(f"✓ Response is a list with {len(data)} allocations", "PASS")
    
    # Check that allocations have weekly_hours field
    if data:
        sample = data[0]
        if "weekly_hours" not in sample:
            log_test(f"✗ Allocations missing 'weekly_hours' field", "FAIL")
            return False
        
        log_test(f"✓ Allocations include 'weekly_hours' field", "PASS")
        log_test(f"  Sample: {sample.get('project_name', 'Unknown')} - {sample['weekly_hours']}h/week", "INFO")
    
    return True

def test_no_mongo_objectid(token: str, period: str) -> bool:
    """Test that response contains no raw Mongo ObjectId"""
    log_test(f"\n{'='*80}", "INFO")
    log_test(f"TEST: No raw Mongo ObjectId in response", "INFO")
    log_test(f"{'='*80}", "INFO")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BACKEND_URL}/my-allocations",
        params={"period": period},
        headers=headers
    )
    
    if response.status_code != 200:
        log_test(f"✗ Request failed with {response.status_code}", "FAIL")
        return False
    
    # Check response text for ObjectId patterns
    response_text = response.text
    
    if "ObjectId(" in response_text or "_id" in response_text:
        # Check if _id values are strings (not ObjectId objects)
        data = response.json()
        allocations = data.get("allocations", [])
        
        for alloc in allocations:
            alloc_id = alloc.get("id")
            if not isinstance(alloc_id, str):
                log_test(f"✗ Found non-string ID: {alloc_id} (type: {type(alloc_id)})", "FAIL")
                return False
    
    log_test(f"✓ All IDs are plain strings (no raw ObjectId)", "PASS")
    return True

def create_test_allocation(token: str) -> Dict[str, Any]:
    """Create a test allocation overlapping current month"""
    log_test(f"\n{'='*80}", "INFO")
    log_test(f"Creating test allocation for current month...", "INFO")
    log_test(f"{'='*80}", "INFO")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get resources and projects
    resources_resp = requests.get(f"{BACKEND_URL}/resources", headers=headers)
    projects_resp = requests.get(f"{BACKEND_URL}/projects", headers=headers)
    
    if resources_resp.status_code != 200 or projects_resp.status_code != 200:
        log_test(f"✗ Failed to fetch resources or projects", "FAIL")
        return None
    
    resources = resources_resp.json()
    projects = projects_resp.json()
    
    if not resources or not projects:
        log_test(f"✗ No resources or projects available", "FAIL")
        return None
    
    # Use first resource and project
    resource = resources[0]
    project = projects[0]
    
    # Create allocation for current month
    today = date.today()
    start_date = today.replace(day=1)
    if today.month == 12:
        end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    
    allocation_data = {
        "resource_id": resource["id"],
        "project_id": project["id"],
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "percentage": 50,
        "allocation_type": "percentage"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/allocations",
        json=allocation_data,
        headers=headers
    )
    
    if response.status_code != 200:
        log_test(f"✗ Failed to create allocation: {response.status_code} - {response.text}", "FAIL")
        return None
    
    allocation = response.json()
    log_test(f"✓ Created test allocation: {allocation['id']}", "PASS")
    log_test(f"  Resource: {resource['name']}", "INFO")
    log_test(f"  Project: {project['name']}", "INFO")
    log_test(f"  Period: {start_date} to {end_date}", "INFO")
    log_test(f"  Percentage: 50%", "INFO")
    
    return allocation

def cleanup_test_allocation(token: str, allocation_id: str):
    """Delete test allocation"""
    log_test(f"\nCleaning up test allocation: {allocation_id}", "INFO")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.delete(
        f"{BACKEND_URL}/allocations/{allocation_id}",
        headers=headers
    )
    
    if response.status_code == 200:
        log_test(f"✓ Test allocation deleted", "PASS")
    else:
        log_test(f"⚠ Failed to delete test allocation: {response.status_code}", "WARN")

def main():
    """Main test execution"""
    print(f"\n{'='*80}")
    print(f"Backend Test: My Allocations Endpoint Fix")
    print(f"{'='*80}\n")
    
    # Login
    token = login()
    
    # Test all three period values
    periods = ["week", "month", "3months"]
    results = []
    
    for period in periods:
        result = test_my_allocations_endpoint(token, period)
        results.append(result)
    
    # Regression check
    regression_passed = test_allocations_regression(token)
    
    # Test no ObjectId in response
    objectid_passed = test_no_mongo_objectid(token, "month")
    
    # Summary
    print(f"\n{'='*80}")
    print(f"TEST SUMMARY")
    print(f"{'='*80}\n")
    
    all_passed = all(r["passed"] for r in results) and regression_passed and objectid_passed
    
    for result in results:
        period = result["period"]
        passed = result["passed"]
        status = "PASS" if passed else "FAIL"
        color = GREEN if passed else RED
        
        print(f"{color}[{status}]{RESET} GET /api/my-allocations?period={period}")
        
        if passed and not result.get("no_resource"):
            print(f"       Period: {result['period_start']} to {result['period_end']}")
            print(f"       Allocations: {len(result['allocations'])}")
            if result['allocations']:
                summary = result.get('summary', {})
                print(f"       Total Period Hours: {summary.get('total_period_hours', 0)}h")
        elif result.get("no_resource"):
            print(f"       No resource linked (valid scenario)")
    
    print(f"\n{GREEN if regression_passed else RED}[{'PASS' if regression_passed else 'FAIL'}]{RESET} GET /api/allocations (regression check)")
    print(f"{GREEN if objectid_passed else RED}[{'PASS' if objectid_passed else 'FAIL'}]{RESET} No raw Mongo ObjectId in response")
    
    print(f"\n{'='*80}")
    if all_passed:
        print(f"{GREEN}✓ ALL TESTS PASSED{RESET}")
        print(f"{'='*80}\n")
        sys.exit(0)
    else:
        print(f"{RED}✗ SOME TESTS FAILED{RESET}")
        print(f"{'='*80}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
