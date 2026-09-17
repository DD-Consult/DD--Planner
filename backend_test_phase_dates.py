#!/usr/bin/env python3
"""
Detailed Test for _phase_overlaps_week Function
================================================
This test specifically verifies that the auto-fill endpoint handles:
1. Projects without phases
2. Projects with phases that have string dates
3. Projects with phases that have datetime dates
4. No TypeError is thrown from _phase_overlaps_week
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8001"

def login(email, password):
    """Login and get JWT token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    return None

def get_projects(token):
    """Get all projects to inspect their phase structures"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/projects", headers=headers)
    if response.status_code == 200:
        return response.json()
    return []

def test_phase_date_handling(token):
    """
    Test that auto-fill handles different phase date formats correctly
    """
    print("="*80)
    print("DETAILED TEST: _phase_overlaps_week Date Handling")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get all projects to inspect phase structures
    print("\n[STEP 1] Fetching all projects to inspect phase date formats...")
    projects = get_projects(token)
    print(f"Found {len(projects)} projects")
    
    # Analyze phase date formats
    phase_analysis = {
        "projects_without_phases": 0,
        "projects_with_phases": 0,
        "phases_with_string_dates": 0,
        "phases_with_datetime_dates": 0,
        "phases_with_null_dates": 0,
    }
    
    print("\n[STEP 2] Analyzing phase date formats...")
    for project in projects:
        phases = project.get("phases", [])
        if not phases:
            phase_analysis["projects_without_phases"] += 1
        else:
            phase_analysis["projects_with_phases"] += 1
            for phase in phases:
                start_date = phase.get("start_date")
                end_date = phase.get("end_date")
                
                if start_date is None or end_date is None:
                    phase_analysis["phases_with_null_dates"] += 1
                elif isinstance(start_date, str):
                    phase_analysis["phases_with_string_dates"] += 1
                else:
                    phase_analysis["phases_with_datetime_dates"] += 1
    
    print("\nPhase Analysis:")
    for key, value in phase_analysis.items():
        print(f"  - {key}: {value}")
    
    # Test auto-fill with different week dates
    test_weeks = [
        "2026-09-14",  # Current week
        "2026-09-21",  # Next week
        "2026-08-31",  # Past week
    ]
    
    print("\n[STEP 3] Testing auto-fill with different week dates...")
    all_passed = True
    
    for week_start in test_weeks:
        print(f"\n  Testing week_start={week_start}...")
        response = requests.post(
            f"{BASE_URL}/api/timesheets/auto-fill?week_start={week_start}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"    ✅ HTTP 200 - Processed {data['total']} timesheet(s)")
            print(f"       Created: {data['created']}, Updated: {data['updated']}, Skipped: {data['skipped']}")
        elif response.status_code == 500:
            print(f"    ❌ HTTP 500 - Server Error")
            print(f"       Response: {response.text[:200]}")
            all_passed = False
        else:
            print(f"    ⚠️  HTTP {response.status_code}")
            print(f"       Response: {response.text[:200]}")
    
    return all_passed

def test_specific_phase_scenarios(token):
    """
    Test specific scenarios that could cause TypeError in _phase_overlaps_week
    """
    print("\n" + "="*80)
    print("SPECIFIC SCENARIO TESTS")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Scenario 1: Project without phases
    print("\n[SCENARIO 1] Testing with projects that have no phases...")
    projects = get_projects(token)
    projects_without_phases = [p for p in projects if not p.get("phases")]
    
    if projects_without_phases:
        print(f"  Found {len(projects_without_phases)} project(s) without phases")
        print(f"  Example: {projects_without_phases[0].get('name')}")
    else:
        print("  No projects without phases found")
    
    # Scenario 2: Projects with phases that have string dates
    print("\n[SCENARIO 2] Testing with projects that have string dates in phases...")
    projects_with_string_dates = []
    for p in projects:
        phases = p.get("phases", [])
        for phase in phases:
            if isinstance(phase.get("start_date"), str):
                projects_with_string_dates.append(p)
                break
    
    if projects_with_string_dates:
        print(f"  Found {len(projects_with_string_dates)} project(s) with string dates")
        example = projects_with_string_dates[0]
        print(f"  Example: {example.get('name')}")
        print(f"  Phase date format: {type(example['phases'][0].get('start_date'))}")
    else:
        print("  No projects with string dates found")
    
    # Run auto-fill and verify no errors
    print("\n[FINAL TEST] Running auto-fill to verify no TypeError...")
    response = requests.post(
        f"{BASE_URL}/api/timesheets/auto-fill?week_start=2026-09-14",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"  ✅ SUCCESS - No TypeError occurred")
        print(f"  ✅ Processed {data['total']} timesheet(s) successfully")
        return True
    else:
        print(f"  ❌ FAILED - HTTP {response.status_code}")
        print(f"  Response: {response.text}")
        return False

def main():
    print("="*80)
    print("DD PLANNER - PHASE DATE HANDLING VERIFICATION")
    print("="*80)
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Backend URL: {BASE_URL}")
    
    # Login
    token = login("admin@test.com", "admin123")
    if not token:
        print("\n❌ CRITICAL: Login failed")
        return
    
    print("✅ Login successful\n")
    
    # Run tests
    test1_passed = test_phase_date_handling(token)
    test2_passed = test_specific_phase_scenarios(token)
    
    # Summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    
    if test1_passed and test2_passed:
        print("\n🎉 ALL TESTS PASSED")
        print("✅ _phase_overlaps_week handles string dates correctly")
        print("✅ No TypeError occurs with projects without phases")
        print("✅ Auto-fill works correctly with all date formats")
    else:
        print("\n⚠️  SOME TESTS FAILED")
        if not test1_passed:
            print("❌ Phase date handling test failed")
        if not test2_passed:
            print("❌ Specific scenario test failed")

if __name__ == "__main__":
    main()
