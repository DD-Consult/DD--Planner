#!/usr/bin/env python3
"""
Comprehensive verification of Time Off approval accounting-gating.

CRITICAL RULE TO VERIFY:
- Only leave with status == "Approved" blocks capacity
- A "Pending" leave must NOT mark days as on-leave
- After approval, the same leave MUST mark days as on-leave

Test accounts:
- Admin: don@ddconsult.tech / @Ddplanner2026
- Resource: qa_resource@test.com / Test@2026 (linked to "Bob Smith")
"""

import requests
import json
from datetime import datetime

# Configuration
BACKEND_URL = "https://ddplanner-fixes.preview.emergentagent.com"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"
RESOURCE_EMAIL = "qa_resource@test.com"
RESOURCE_PASSWORD = "Test@2026"

# Test date range
LEAVE_START = "2026-12-07"  # Monday
LEAVE_END = "2026-12-11"    # Friday

def login(email, password):
    """Login and return JWT token"""
    response = requests.post(
        f"{BACKEND_URL}/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code != 200:
        print(f"❌ Login failed for {email}: {response.status_code}")
        print(f"Response: {response.text}")
        return None
    
    data = response.json()
    print(f"✅ Login successful for {email}")
    return data.get("access_token")

def get_bob_smith_resource_id(admin_token):
    """Get Bob Smith's resource_id from /api/resources"""
    response = requests.get(
        f"{BACKEND_URL}/api/resources",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    if response.status_code != 200:
        print(f"❌ Failed to get resources: {response.status_code}")
        return None
    
    resources = response.json()
    for resource in resources:
        if resource.get("name") == "Bob Smith":
            resource_id = resource.get("id")
            print(f"✅ Found Bob Smith with resource_id: {resource_id}")
            return resource_id
    
    print("❌ Bob Smith not found in resources")
    return None

def create_leave(resource_token):
    """Create a leave request as qa_resource (Bob Smith)"""
    payload = {
        "start_date": LEAVE_START,
        "end_date": LEAVE_END,
        "type": "Annual Leave",
        "notes": "Accounting gating test"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/api/leaves",
        json=payload,
        headers={"Authorization": f"Bearer {resource_token}"}
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to create leave: {response.status_code}")
        print(f"Response: {response.text}")
        return None
    
    data = response.json()
    leave_id = data.get("id")
    status = data.get("status")
    print(f"✅ Leave created: ID={leave_id}, Status={status}")
    return leave_id

def get_capacity(admin_token, start_date, end_date):
    """Get capacity report for date range"""
    response = requests.get(
        f"{BACKEND_URL}/api/reports/capacity",
        params={"start_date": start_date, "end_date": end_date},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to get capacity: {response.status_code}")
        print(f"Response: {response.text}")
        return None
    
    return response.json()

def find_bob_smith_days(capacity_data):
    """Find Bob Smith's days from capacity response"""
    resources = capacity_data.get("resources", [])
    
    for resource in resources:
        if resource.get("name") == "Bob Smith":
            days = resource.get("days", [])
            print(f"✅ Found Bob Smith in capacity with {len(days)} days")
            return days
    
    print("❌ Bob Smith not found in capacity response")
    return None

def print_days_table(days, title):
    """Print a formatted table of days"""
    print(f"\n{title}")
    print("=" * 80)
    print(f"{'Date':<12} {'On Leave':<10} {'Color':<10} {'Leave Type':<20}")
    print("-" * 80)
    
    for day in days:
        date = day.get("date", "N/A")
        on_leave = day.get("on_leave", False)
        color = day.get("color", "N/A")
        leave_type = day.get("leave_type") or "—"
        print(f"{date:<12} {str(on_leave):<10} {color:<10} {leave_type:<20}")
    
    print("=" * 80)

def approve_leave(admin_token, leave_id):
    """Approve a leave request as admin"""
    response = requests.put(
        f"{BACKEND_URL}/api/leaves/{leave_id}/approve",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to approve leave: {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    print(f"✅ Leave approved: ID={leave_id}")
    return True

def test_auto_fill(resource_token, week_start):
    """Test auto-fill timesheet endpoint"""
    response = requests.post(
        f"{BACKEND_URL}/api/timesheets/auto-fill",
        params={"week_start": week_start},
        headers={"Authorization": f"Bearer {resource_token}"}
    )
    
    if response.status_code != 200:
        print(f"❌ Auto-fill failed: {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    print(f"✅ Auto-fill successful: {response.status_code}")
    return True

def delete_leave(resource_token, leave_id):
    """Delete a leave request"""
    response = requests.delete(
        f"{BACKEND_URL}/api/leaves/{leave_id}",
        headers={"Authorization": f"Bearer {resource_token}"}
    )
    
    if response.status_code != 200:
        print(f"⚠️  Failed to delete leave {leave_id}: {response.status_code}")
        return False
    
    print(f"✅ Leave deleted: ID={leave_id}")
    return True

def main():
    print("=" * 80)
    print("TIME OFF APPROVAL ACCOUNTING-GATING VERIFICATION")
    print("=" * 80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test Date Range: {LEAVE_START} to {LEAVE_END}")
    print("=" * 80)
    
    # Step 1: Login as admin and resource
    print("\n[STEP 1] Authentication")
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    resource_token = login(RESOURCE_EMAIL, RESOURCE_PASSWORD)
    
    if not admin_token or not resource_token:
        print("❌ FAILED: Authentication failed")
        return
    
    # Step 2: Get Bob Smith's resource_id
    print("\n[STEP 2] Get Bob Smith's resource_id")
    bob_resource_id = get_bob_smith_resource_id(admin_token)
    if not bob_resource_id:
        print("❌ FAILED: Could not find Bob Smith")
        return
    
    # Step 3: Create leave as qa_resource (Bob Smith)
    print("\n[STEP 3] Create leave request (Pending)")
    leave_id = create_leave(resource_token)
    if not leave_id:
        print("❌ FAILED: Could not create leave")
        return
    
    # Step 4: Get capacity BEFORE approval (Pending state)
    print("\n[STEP 4] Get capacity BEFORE approval (Pending state)")
    capacity_before = get_capacity(admin_token, LEAVE_START, LEAVE_END)
    if not capacity_before:
        print("❌ FAILED: Could not get capacity before approval")
        return
    
    bob_days_before = find_bob_smith_days(capacity_before)
    if not bob_days_before:
        print("❌ FAILED: Could not find Bob Smith in capacity")
        return
    
    print_days_table(bob_days_before, "BEFORE APPROVAL (Pending Leave)")
    
    # Step 5: Verify BEFORE state - Pending leave should NOT block capacity
    print("\n[STEP 5] Verify BEFORE state - Pending leave should NOT block capacity")
    before_blocked = False
    for day in bob_days_before:
        date = day.get("date")
        on_leave = day.get("on_leave", False)
        color = day.get("color", "")
        
        if LEAVE_START <= date <= LEAVE_END:
            if on_leave or color == "leave":
                print(f"❌ ASSERTION FAILED: Date {date} is marked as on_leave={on_leave}, color={color} while leave is PENDING")
                before_blocked = True
    
    if not before_blocked:
        print("✅ ASSERTION PASSED: Pending leave does NOT block capacity")
    else:
        print("❌ CRITICAL FAILURE: Pending leave is blocking capacity (should NOT)")
    
    # Step 6: Approve leave as admin
    print("\n[STEP 6] Approve leave as admin")
    if not approve_leave(admin_token, leave_id):
        print("❌ FAILED: Could not approve leave")
        return
    
    # Step 7: Get capacity AFTER approval (Approved state)
    print("\n[STEP 7] Get capacity AFTER approval (Approved state)")
    capacity_after = get_capacity(admin_token, LEAVE_START, LEAVE_END)
    if not capacity_after:
        print("❌ FAILED: Could not get capacity after approval")
        return
    
    bob_days_after = find_bob_smith_days(capacity_after)
    if not bob_days_after:
        print("❌ FAILED: Could not find Bob Smith in capacity")
        return
    
    print_days_table(bob_days_after, "AFTER APPROVAL (Approved Leave)")
    
    # Step 8: Verify AFTER state - Approved leave MUST block capacity
    print("\n[STEP 8] Verify AFTER state - Approved leave MUST block capacity")
    after_blocked_count = 0
    expected_blocked_days = []
    
    for day in bob_days_after:
        date = day.get("date")
        on_leave = day.get("on_leave", False)
        color = day.get("color", "")
        
        if LEAVE_START <= date <= LEAVE_END:
            expected_blocked_days.append(date)
            if on_leave and color == "leave":
                print(f"✅ Date {date}: on_leave={on_leave}, color={color} (CORRECT)")
                after_blocked_count += 1
            else:
                print(f"❌ ASSERTION FAILED: Date {date} is NOT marked as on_leave (on_leave={on_leave}, color={color}) after approval")
    
    if after_blocked_count == len(expected_blocked_days):
        print(f"✅ ASSERTION PASSED: All {after_blocked_count} business days are blocked after approval")
    else:
        print(f"❌ CRITICAL FAILURE: Only {after_blocked_count}/{len(expected_blocked_days)} days are blocked after approval")
    
    # Step 9: Compare BEFORE vs AFTER
    print("\n[STEP 9] Compare BEFORE vs AFTER")
    print("=" * 80)
    print(f"{'Date':<12} {'BEFORE (Pending)':<25} {'AFTER (Approved)':<25}")
    print("-" * 80)
    
    for i, date in enumerate(expected_blocked_days):
        before_day = bob_days_before[i] if i < len(bob_days_before) else {}
        after_day = bob_days_after[i] if i < len(bob_days_after) else {}
        
        before_status = f"on_leave={before_day.get('on_leave', False)}, color={before_day.get('color', 'N/A')}"
        after_status = f"on_leave={after_day.get('on_leave', False)}, color={after_day.get('color', 'N/A')}"
        
        print(f"{date:<12} {before_status:<25} {after_status:<25}")
    
    print("=" * 80)
    
    # Step 10: Test auto-fill timesheet
    print("\n[STEP 10] Test auto-fill timesheet")
    auto_fill_success = test_auto_fill(resource_token, LEAVE_START)
    
    if auto_fill_success:
        print("✅ Auto-fill returned 200 (no crash)")
    else:
        print("❌ Auto-fill failed or crashed")
    
    # Step 11: Cleanup
    print("\n[STEP 11] Cleanup")
    delete_leave(resource_token, leave_id)
    
    # Final Summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    
    all_passed = True
    
    if not before_blocked:
        print("✅ PASS: Pending leave did NOT block capacity")
    else:
        print("❌ FAIL: Pending leave blocked capacity (should NOT)")
        all_passed = False
    
    if after_blocked_count == len(expected_blocked_days):
        print(f"✅ PASS: Approved leave DID block capacity ({after_blocked_count}/{len(expected_blocked_days)} days)")
    else:
        print(f"❌ FAIL: Approved leave did NOT block all days ({after_blocked_count}/{len(expected_blocked_days)} days)")
        all_passed = False
    
    if auto_fill_success:
        print("✅ PASS: Auto-fill returned 200 (no crash)")
    else:
        print("❌ FAIL: Auto-fill failed")
        all_passed = False
    
    print("=" * 80)
    
    if all_passed:
        print("✅✅✅ ALL TESTS PASSED - ACCOUNTING-GATING WORKING CORRECTLY ✅✅✅")
    else:
        print("❌❌❌ SOME TESTS FAILED - ACCOUNTING-GATING HAS ISSUES ❌❌❌")
    
    print("=" * 80)

if __name__ == "__main__":
    main()
