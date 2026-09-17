#!/usr/bin/env python3
"""
Backend Test for User-Reported Issues
======================================
Issue 1: "failed auto timesheet pre fill in dashboard"
Issue 2: "can not see project details"

Test credentials: admin@test.com / admin123
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8001"

def login(email, password):
    """Login and get JWT token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    print(f"[LOGIN] Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        print(f"[LOGIN] ✅ Success - Token obtained")
        return token
    else:
        print(f"[LOGIN] ❌ Failed - {response.text}")
        return None

def test_issue_1_auto_fill_timesheet(token):
    """
    Issue 1: Test POST /api/timesheets/auto-fill?week_start=2026-09-14
    
    Expected:
    - HTTP 200
    - JSON response with {message, created, updated, skipped, total}
    - No TypeError from _phase_overlaps_week with string dates
    """
    print("\n" + "="*80)
    print("ISSUE 1: Auto-fill Timesheet Pre-fill")
    print("="*80)
    
    week_start = "2026-09-14"  # Monday
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"\n[TEST 1.1] POST /api/timesheets/auto-fill?week_start={week_start}")
    response = requests.post(
        f"{BASE_URL}/api/timesheets/auto-fill?week_start={week_start}",
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response Body: {json.dumps(data, indent=2)}")
        
        # Verify response structure
        required_fields = ["message", "created", "updated", "skipped", "total"]
        missing_fields = [f for f in required_fields if f not in data]
        
        if missing_fields:
            print(f"❌ FAILED: Missing fields in response: {missing_fields}")
            return False
        
        print(f"\n✅ Response Structure Valid:")
        print(f"   - message: {data['message']}")
        print(f"   - created: {data['created']}")
        print(f"   - updated: {data['updated']}")
        print(f"   - skipped: {data['skipped']}")
        print(f"   - total: {data['total']}")
        
        # Check if any timesheets were processed
        if data['total'] > 0:
            print(f"\n✅ Auto-fill processed {data['total']} timesheet(s)")
        else:
            print(f"\n⚠️  No timesheets were auto-filled (this may be expected if no allocations exist)")
        
        return True
    else:
        print(f"❌ FAILED: HTTP {response.status_code}")
        print(f"Response: {response.text}")
        return False

def test_issue_2_project_details(token):
    """
    Issue 2: Test GET /api/projects and GET /api/projects/{id}
    
    Expected:
    - GET /api/projects returns list with full project details
    - Each project should have: name, client_name, status, start_date, end_date, 
      budgeted_hours, project_lead_id, phases
    - GET /api/projects/{id} returns single project with all fields
    """
    print("\n" + "="*80)
    print("ISSUE 2: Project Details Visibility")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test 2.1: GET /api/projects
    print(f"\n[TEST 2.1] GET /api/projects")
    response = requests.get(f"{BASE_URL}/api/projects", headers=headers)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ FAILED: HTTP {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    projects = response.json()
    print(f"✅ Retrieved {len(projects)} project(s)")
    
    if len(projects) == 0:
        print("⚠️  No projects found in database")
        return True
    
    # Verify first project has all required fields
    project = projects[0]
    required_fields = [
        "id", "name", "client_name", "status", "start_date", "end_date",
        "budgeted_hours", "project_lead_id", "phases"
    ]
    
    print(f"\n[TEST 2.2] Verify project fields for: {project.get('name', 'Unknown')}")
    missing_fields = []
    present_fields = []
    
    for field in required_fields:
        if field in project:
            present_fields.append(field)
            value = project[field]
            # Truncate long values for display
            if isinstance(value, list):
                display_value = f"[{len(value)} items]"
            elif isinstance(value, str) and len(value) > 50:
                display_value = value[:50] + "..."
            else:
                display_value = value
            print(f"   ✅ {field}: {display_value}")
        else:
            missing_fields.append(field)
            print(f"   ❌ {field}: MISSING")
    
    if missing_fields:
        print(f"\n❌ FAILED: Missing fields: {missing_fields}")
        return False
    
    # Test 2.3: GET /api/projects/{id} for specific project
    project_id = project.get("id")
    print(f"\n[TEST 2.3] GET /api/projects/{project_id}")
    response = requests.get(f"{BASE_URL}/api/projects/{project_id}", headers=headers)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ FAILED: HTTP {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    project_detail = response.json()
    print(f"✅ Retrieved project details for: {project_detail.get('name', 'Unknown')}")
    
    # Verify all fields are present
    print(f"\n[TEST 2.4] Verify detailed project fields")
    for field in required_fields:
        if field in project_detail:
            value = project_detail[field]
            if isinstance(value, list):
                display_value = f"[{len(value)} items]"
            elif isinstance(value, str) and len(value) > 50:
                display_value = value[:50] + "..."
            else:
                display_value = value
            print(f"   ✅ {field}: {display_value}")
        else:
            print(f"   ❌ {field}: MISSING")
            missing_fields.append(field)
    
    if missing_fields:
        print(f"\n❌ FAILED: Missing fields in project detail: {missing_fields}")
        return False
    
    print(f"\n✅ All required project fields are present")
    return True

def main():
    print("="*80)
    print("DD PLANNER - USER ISSUE VERIFICATION TEST")
    print("="*80)
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Backend URL: {BASE_URL}")
    print(f"Test Credentials: admin@test.com / admin123")
    
    # Login
    token = login("admin@test.com", "admin123")
    if not token:
        print("\n❌ CRITICAL: Login failed. Cannot proceed with tests.")
        return
    
    # Run tests
    results = {}
    
    # Issue 1: Auto-fill timesheet
    results["issue_1"] = test_issue_1_auto_fill_timesheet(token)
    
    # Issue 2: Project details
    results["issue_2"] = test_issue_2_project_details(token)
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    print(f"\nIssue 1 (Auto-fill Timesheet): {'✅ PASSED' if results['issue_1'] else '❌ FAILED'}")
    print(f"Issue 2 (Project Details): {'✅ PASSED' if results['issue_2'] else '❌ FAILED'}")
    
    print(f"\n{'='*80}")
    print(f"OVERALL: {passed_tests}/{total_tests} tests passed")
    print(f"{'='*80}")
    
    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED - Both user issues are resolved!")
    else:
        print(f"\n⚠️  {total_tests - passed_tests} test(s) failed - Issues need attention")

if __name__ == "__main__":
    main()
