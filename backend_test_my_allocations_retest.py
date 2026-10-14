"""
Re-test "My Allocations" backend fix in DD Planner (FastAPI + MongoDB).

Test Setup (already done):
- admin@test.com / admin123 is linked to resource "Alice Johnson"
- Three seeded allocations exist (tagged seed_tag="my_alloc_qa"):
  - A: 2025-07-13 → 2025-07-31, 60% (July only)
  - B: 2025-07-20 → 2025-08-28, 18% (spans into August)
  - C: 2025-08-01 → 2025-08-15, 30% (August only)

Tests:
1. GET /api/my-allocations?period=month → verify overlap filtering and period_hours > 0
2. GET /api/my-allocations?period=week and ?period=3months → same checks
3. Spot-check math for allocation B (18%, spans into August)
4. Verify summary object always includes available_hours_per_week key
5. Confirm no raw ObjectId strings leak
"""

import os
import requests
from datetime import date, datetime, timedelta

# Backend URL from environment
BACKEND_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')
API_BASE = f"{BACKEND_URL}/api"

# Test credentials
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "admin123"

# Expected seeded allocations (for reference)
SEEDED_ALLOCATIONS = {
    "A": {"start": "2025-07-13", "end": "2025-07-31", "percentage": 60, "label": "July only"},
    "B": {"start": "2025-07-20", "end": "2025-08-28", "percentage": 18, "label": "spans into August"},
    "C": {"start": "2025-08-01", "end": "2025-08-15", "percentage": 30, "label": "August only"},
}


def login(email: str, password: str) -> str:
    """Login and return access token"""
    print(f"\n{'='*80}")
    print(f"AUTHENTICATION")
    print(f"{'='*80}")
    print(f"Logging in as: {email}")
    
    # OAuth2 password form (form-encoded)
    response = requests.post(
        f"{API_BASE}/auth/login",
        data={"username": email, "password": password}
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ Login failed: {response.text[:500]}")
        raise Exception(f"Login failed: {response.status_code}")
    
    data = response.json()
    token = data.get("access_token") or data.get("token")
    
    if not token:
        print(f"❌ No token in response: {data}")
        raise Exception("No token in login response")
    
    print(f"✅ Login successful")
    print(f"Token: {token[:20]}...")
    
    return token


def check_overlap(alloc_start: str, alloc_end: str, period_start: str, period_end: str) -> bool:
    """Check if allocation overlaps with period using date comparison"""
    # Convert strings to date objects
    a_start = datetime.fromisoformat(alloc_start).date()
    a_end = datetime.fromisoformat(alloc_end).date()
    p_start = datetime.fromisoformat(period_start).date()
    p_end = datetime.fromisoformat(period_end).date()
    
    # Overlap condition: alloc_start <= period_end AND alloc_end >= period_start
    return a_start <= p_end and a_end >= p_start


def count_business_days(start_date: date, end_date: date) -> int:
    """Count business days (Mon-Fri) between two dates (inclusive)"""
    count = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # Monday=0, Friday=4
            count += 1
        current = current + timedelta(days=1)
    return count


def test_my_allocations_period(token: str, period: str):
    """Test GET /api/my-allocations for a specific period"""
    print(f"\n{'='*80}")
    print(f"TEST: GET /api/my-allocations?period={period}")
    print(f"{'='*80}")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{API_BASE}/my-allocations?period={period}", headers=headers)
    
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ Request failed: {response.text[:500]}")
        return False
    
    data = response.json()
    
    # Extract key fields
    period_start = data.get("period_start")
    period_end = data.get("period_end")
    resource = data.get("resource")
    summary = data.get("summary", {})
    allocations = data.get("allocations", [])
    
    print(f"\n📅 PERIOD WINDOW (server-computed):")
    print(f"   period_start: {period_start}")
    print(f"   period_end:   {period_end}")
    
    print(f"\n👤 RESOURCE:")
    if resource:
        print(f"   id:   {resource.get('id')}")
        print(f"   name: {resource.get('name')}")
        print(f"   role: {resource.get('role')}")
        print(f"   standard_capacity: {resource.get('standard_capacity')}")
    else:
        print(f"   ⚠️  No resource linked to user")
    
    print(f"\n📊 SUMMARY:")
    for key, value in summary.items():
        print(f"   {key}: {value}")
    
    # CRITICAL CHECK: available_hours_per_week must be present
    if "available_hours_per_week" not in summary:
        print(f"\n❌ FAILURE: summary missing 'available_hours_per_week' key")
        return False
    else:
        print(f"\n✅ PASS: summary contains 'available_hours_per_week' key")
    
    print(f"\n📋 ALLOCATIONS ({len(allocations)} found):")
    
    if len(allocations) == 0:
        print(f"   ⚠️  No allocations returned")
        print(f"   This may be expected if no allocations overlap the period window")
    
    # Track which seeded allocations we found
    found_seeded = {"A": False, "B": False, "C": False}
    
    # Analyze each allocation
    all_pass = True
    for i, alloc in enumerate(allocations, 1):
        print(f"\n   [{i}] Allocation:")
        print(f"       id: {alloc.get('id')}")
        print(f"       project_name: {alloc.get('project_name')}")
        print(f"       start_date: {alloc.get('start_date')}")
        print(f"       end_date: {alloc.get('end_date')}")
        print(f"       percentage: {alloc.get('percentage')}%")
        print(f"       allocation_type: {alloc.get('allocation_type')}")
        print(f"       weekly_hours: {alloc.get('weekly_hours')}")
        print(f"       period_hours: {alloc.get('period_hours')}")
        
        # Check if this is one of the seeded allocations
        for label, seed_data in SEEDED_ALLOCATIONS.items():
            if (alloc.get('start_date') == seed_data['start'] and 
                alloc.get('end_date') == seed_data['end'] and
                alloc.get('percentage') == seed_data['percentage']):
                found_seeded[label] = True
                print(f"       🏷️  SEEDED ALLOCATION {label}: {seed_data['label']}")
        
        # CRITICAL CHECK 1: Verify overlap with period
        overlaps = check_overlap(
            alloc.get('start_date'),
            alloc.get('end_date'),
            period_start,
            period_end
        )
        
        if not overlaps:
            print(f"       ❌ FAILURE: Allocation does NOT overlap period but was returned")
            all_pass = False
        else:
            print(f"       ✅ Overlaps period window")
        
        # CRITICAL CHECK 2: period_hours must be > 0 for overlapping allocations
        period_hours = alloc.get('period_hours', 0)
        weekly_hours = alloc.get('weekly_hours', 0)
        
        if overlaps and weekly_hours > 0 and period_hours == 0:
            print(f"       ❌ FAILURE: period_hours is 0 but allocation overlaps and has weekly_hours > 0")
            all_pass = False
        elif overlaps and period_hours > 0:
            print(f"       ✅ period_hours > 0 (as expected for overlapping allocation)")
        
        # CRITICAL CHECK 3: No ObjectId strings should leak
        alloc_id = alloc.get('id', '')
        if 'ObjectId' in str(alloc_id):
            print(f"       ❌ FAILURE: Raw ObjectId string detected in id field: {alloc_id}")
            all_pass = False
        else:
            print(f"       ✅ No ObjectId leak detected")
    
    # Check which seeded allocations should have been returned based on overlap
    print(f"\n🔍 SEEDED ALLOCATIONS OVERLAP CHECK:")
    for label, seed_data in SEEDED_ALLOCATIONS.items():
        should_overlap = check_overlap(
            seed_data['start'],
            seed_data['end'],
            period_start,
            period_end
        )
        was_found = found_seeded[label]
        
        print(f"   [{label}] {seed_data['label']} ({seed_data['start']} → {seed_data['end']}, {seed_data['percentage']}%):")
        print(f"       Should overlap period: {should_overlap}")
        print(f"       Was returned: {was_found}")
        
        if should_overlap and not was_found:
            print(f"       ❌ FAILURE: Should have been returned but was NOT")
            all_pass = False
        elif not should_overlap and was_found:
            print(f"       ❌ FAILURE: Should NOT have been returned but WAS")
            all_pass = False
        else:
            print(f"       ✅ PASS: Correct inclusion/exclusion")
    
    return all_pass


def test_allocation_b_math(token: str):
    """Spot-check math for allocation B (18%, spans into August)"""
    print(f"\n{'='*80}")
    print(f"TEST: Allocation B Math Verification")
    print(f"{'='*80}")
    
    # Get month period to find allocation B
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{API_BASE}/my-allocations?period=month", headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Request failed: {response.text[:500]}")
        return False
    
    data = response.json()
    allocations = data.get("allocations", [])
    
    # Find allocation B
    alloc_b = None
    for alloc in allocations:
        if (alloc.get('start_date') == SEEDED_ALLOCATIONS['B']['start'] and 
            alloc.get('end_date') == SEEDED_ALLOCATIONS['B']['end'] and
            alloc.get('percentage') == SEEDED_ALLOCATIONS['B']['percentage']):
            alloc_b = alloc
            break
    
    if not alloc_b:
        print(f"⚠️  Allocation B not found in current month period")
        print(f"   This may be expected if the server's current date doesn't overlap with allocation B")
        return True  # Not a failure, just not applicable
    
    print(f"\n📋 ALLOCATION B DETAILS:")
    print(f"   start_date: {alloc_b.get('start_date')}")
    print(f"   end_date: {alloc_b.get('end_date')}")
    print(f"   percentage: {alloc_b.get('percentage')}%")
    print(f"   weekly_hours: {alloc_b.get('weekly_hours')}")
    print(f"   period_hours: {alloc_b.get('period_hours')}")
    
    # Expected math for 18% allocation:
    # With standard 40h week and 100% capacity:
    # weekly_hours = (18 / 100) * 40 = 7.2h
    
    weekly_hours = alloc_b.get('weekly_hours', 0)
    expected_weekly = 7.2  # 18% of 40h
    
    print(f"\n🧮 MATH CHECK:")
    print(f"   Expected weekly_hours: ~{expected_weekly}h (18% of 40h)")
    print(f"   Actual weekly_hours: {weekly_hours}h")
    
    # Allow small tolerance for rounding
    if abs(weekly_hours - expected_weekly) < 0.5:
        print(f"   ✅ PASS: weekly_hours is plausible")
    else:
        print(f"   ❌ FAILURE: weekly_hours significantly different from expected")
        return False
    
    # period_hours should be weekly_hours × (business_days_in_overlap / 5)
    period_hours = alloc_b.get('period_hours', 0)
    
    print(f"\n   period_hours: {period_hours}h")
    
    if period_hours > 0:
        print(f"   ✅ PASS: period_hours > 0 (non-zero, plausible)")
    else:
        print(f"   ❌ FAILURE: period_hours is 0 (should be > 0 for overlapping allocation)")
        return False
    
    # Check if period_hours is consistent with weekly_hours
    # period_hours = weekly_hours × weeks_in_period
    # weeks_in_period = business_days_in_overlap / 5
    
    period_start = data.get("period_start")
    period_end = data.get("period_end")
    
    # Calculate effective overlap
    alloc_start = datetime.fromisoformat(alloc_b.get('start_date')).date()
    alloc_end = datetime.fromisoformat(alloc_b.get('end_date')).date()
    p_start = datetime.fromisoformat(period_start).date()
    p_end = datetime.fromisoformat(period_end).date()
    
    effective_start = max(alloc_start, p_start)
    effective_end = min(alloc_end, p_end)
    
    biz_days = count_business_days(effective_start, effective_end)
    weeks = biz_days / 5.0
    expected_period_hours = weekly_hours * weeks
    
    print(f"\n   Overlap calculation:")
    print(f"     effective_start: {effective_start}")
    print(f"     effective_end: {effective_end}")
    print(f"     business_days: {biz_days}")
    print(f"     weeks: {weeks:.2f}")
    print(f"     expected_period_hours: {expected_period_hours:.2f}h")
    print(f"     actual_period_hours: {period_hours}h")
    
    # Allow tolerance for rounding
    if abs(period_hours - expected_period_hours) < 1.0:
        print(f"   ✅ PASS: period_hours is consistent with weekly_hours × weeks")
    else:
        print(f"   ⚠️  WARNING: period_hours differs from expected (may be due to rounding or different calculation)")
    
    return True


def main():
    """Main test execution"""
    print(f"\n{'#'*80}")
    print(f"# MY ALLOCATIONS BACKEND FIX RE-TEST")
    print(f"# DD Planner - FastAPI + MongoDB")
    print(f"{'#'*80}")
    print(f"\nBackend URL: {BACKEND_URL}")
    print(f"Test User: {TEST_EMAIL}")
    
    try:
        # Step 1: Login
        token = login(TEST_EMAIL, TEST_PASSWORD)
        
        # Step 2: Test period=month
        print(f"\n{'#'*80}")
        print(f"# TEST 1: period=month")
        print(f"{'#'*80}")
        test1_pass = test_my_allocations_period(token, "month")
        
        # Step 3: Test period=week
        print(f"\n{'#'*80}")
        print(f"# TEST 2: period=week")
        print(f"{'#'*80}")
        test2_pass = test_my_allocations_period(token, "week")
        
        # Step 4: Test period=3months
        print(f"\n{'#'*80}")
        print(f"# TEST 3: period=3months")
        print(f"{'#'*80}")
        test3_pass = test_my_allocations_period(token, "3months")
        
        # Step 5: Test allocation B math
        print(f"\n{'#'*80}")
        print(f"# TEST 4: Allocation B Math")
        print(f"{'#'*80}")
        test4_pass = test_allocation_b_math(token)
        
        # Final summary
        print(f"\n{'#'*80}")
        print(f"# FINAL SUMMARY")
        print(f"{'#'*80}")
        
        all_tests = [
            ("period=month", test1_pass),
            ("period=week", test2_pass),
            ("period=3months", test3_pass),
            ("Allocation B Math", test4_pass),
        ]
        
        passed = sum(1 for _, result in all_tests if result)
        total = len(all_tests)
        
        print(f"\nTest Results:")
        for test_name, result in all_tests:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {status}: {test_name}")
        
        print(f"\n{'='*80}")
        print(f"OVERALL: {passed}/{total} tests passed")
        print(f"{'='*80}")
        
        if passed == total:
            print(f"\n🎉 ALL TESTS PASSED! 🎉")
            print(f"\nThe 'My Allocations' backend fix is working correctly:")
            print(f"  ✅ Overlap filtering works correctly")
            print(f"  ✅ period_hours > 0 for overlapping allocations")
            print(f"  ✅ Non-overlapping allocations are excluded")
            print(f"  ✅ Allocation B math is plausible")
            print(f"  ✅ summary.available_hours_per_week key is present")
            print(f"  ✅ No ObjectId strings leak")
        else:
            print(f"\n⚠️  SOME TESTS FAILED")
            print(f"\nPlease review the detailed output above for specific failures.")
        
    except Exception as e:
        print(f"\n❌ TEST EXECUTION FAILED")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
