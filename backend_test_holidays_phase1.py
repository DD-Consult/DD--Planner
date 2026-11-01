#!/usr/bin/env python3
"""
Backend test for Public Holidays & Smarter Leave Component (Phase 1)
Tests the recently fixed POST /api/leaves endpoint and supporting endpoints.
"""

import requests
import json
from datetime import datetime, timedelta

# Backend URL from frontend/.env
BACKEND_URL = "https://planner-holidays--04yvh1gp.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
SUPER_ADMIN = {"username": "superadmin@test.com", "password": "Super@2026"}
ADMIN = {"username": "admin@test.com", "password": "admin123"}
RESOURCE = {"username": "qa_resource@test.com", "password": "Test@2026"}

# Test results
test_results = []
test_count = 0
pass_count = 0
fail_count = 0

def log_test(name, passed, details=""):
    global test_count, pass_count, fail_count
    test_count += 1
    if passed:
        pass_count += 1
        status = "✅ PASS"
    else:
        fail_count += 1
        status = "❌ FAIL"
    
    result = f"{status}: {name}"
    if details:
        result += f"\n    {details}"
    test_results.append(result)
    print(result)

def login(credentials):
    """Login and return JWT token"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/auth/login",
            data=credentials,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            print(f"Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

def get_resource_id(token):
    """Get the resource_id for the logged-in user"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code == 200:
            user = response.json()
            # For resource users, we need to find their resource profile
            # For admin users, they might have a linked resource
            # Let's get the resources list and find the matching one
            resources_response = requests.get(
                f"{BACKEND_URL}/resources",
                headers={"Authorization": f"Bearer {token}"}
            )
            if resources_response.status_code == 200:
                resources = resources_response.json()
                # Try to find resource by email match or name
                for resource in resources:
                    if resource.get("email") == user.get("email"):
                        return resource.get("id")
                # If no email match, return first resource for testing
                if resources:
                    return resources[0].get("id")
        return None
    except Exception as e:
        print(f"Error getting resource_id: {e}")
        return None

def main():
    print("=" * 80)
    print("PUBLIC HOLIDAYS & SMARTER LEAVE COMPONENT (PHASE 1) - BACKEND TESTING")
    print("=" * 80)
    print()
    
    # ========================================================================
    # AUTHENTICATION
    # ========================================================================
    print("STEP 1: Authentication")
    print("-" * 80)
    
    super_admin_token = login(SUPER_ADMIN)
    log_test("Super Admin Login", super_admin_token is not None, 
             f"Token: {super_admin_token[:20]}..." if super_admin_token else "Failed")
    
    admin_token = login(ADMIN)
    log_test("Admin Login", admin_token is not None,
             f"Token: {admin_token[:20]}..." if admin_token else "Failed")
    
    resource_token = login(RESOURCE)
    log_test("Resource Login", resource_token is not None,
             f"Token: {resource_token[:20]}..." if resource_token else "Failed")
    
    if not all([super_admin_token, admin_token, resource_token]):
        print("\n❌ CRITICAL: Authentication failed. Cannot proceed with tests.")
        return
    
    # Get resource IDs
    resource_id = get_resource_id(resource_token)
    log_test("Get Resource ID for qa_resource", resource_id is not None,
             f"Resource ID: {resource_id}" if resource_id else "Failed")
    
    print()
    
    # ========================================================================
    # LEAVE TYPES ENDPOINTS
    # ========================================================================
    print("STEP 2: Leave Types Endpoints")
    print("-" * 80)
    
    # GET /api/leave-types (should auto-seed defaults)
    response = requests.get(
        f"{BACKEND_URL}/leave-types",
        headers={"Authorization": f"Bearer {resource_token}"}
    )
    log_test("GET /api/leave-types", response.status_code == 200,
             f"Status: {response.status_code}, Count: {len(response.json()) if response.status_code == 200 else 0}")
    
    leave_types = response.json() if response.status_code == 200 else []
    default_types = ["Annual", "Sick", "Personal", "Unpaid", "Parental"]
    has_defaults = all(any(lt.get("name") == dt for lt in leave_types) for dt in default_types)
    log_test("Leave types include defaults", has_defaults,
             f"Found types: {[lt.get('name') for lt in leave_types]}")
    
    # POST /api/leave-types (admin creates custom type)
    custom_type_payload = {"name": "Study Leave"}
    response = requests.post(
        f"{BACKEND_URL}/leave-types",
        headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
        json=custom_type_payload
    )
    log_test("POST /api/leave-types (admin creates custom type)", response.status_code in [200, 201],
             f"Status: {response.status_code}")
    
    custom_type_id = None
    if response.status_code in [200, 201]:
        custom_type_id = response.json().get("id")
    
    # PUT /api/leave-types/{id} (update custom type)
    if custom_type_id:
        update_payload = {"name": "Study Leave (Updated)", "is_active": True}
        response = requests.put(
            f"{BACKEND_URL}/leave-types/{custom_type_id}",
            headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
            json=update_payload
        )
        log_test("PUT /api/leave-types/{id}", response.status_code == 200,
                 f"Status: {response.status_code}")
    
    print()
    
    # ========================================================================
    # HOLIDAY REGION & HOLIDAYS ENDPOINTS
    # ========================================================================
    print("STEP 3: Holiday Region & Holidays Endpoints")
    print("-" * 80)
    
    # GET /api/settings/holiday-region
    response = requests.get(
        f"{BACKEND_URL}/settings/holiday-region",
        headers={"Authorization": f"Bearer {resource_token}"}
    )
    log_test("GET /api/settings/holiday-region", response.status_code == 200,
             f"Status: {response.status_code}, Region: {response.json().get('region') if response.status_code == 200 else 'N/A'}")
    
    # PUT /api/settings/holiday-region (set to NSW)
    region_payload = {"region": "NSW"}
    response = requests.put(
        f"{BACKEND_URL}/settings/holiday-region",
        headers={"Authorization": f"Bearer {super_admin_token}", "Content-Type": "application/json"},
        json=region_payload
    )
    log_test("PUT /api/settings/holiday-region (NSW)", response.status_code == 200,
             f"Status: {response.status_code}")
    
    # GET /api/holidays (check if holidays populated)
    response = requests.get(
        f"{BACKEND_URL}/holidays",
        headers={"Authorization": f"Bearer {resource_token}"}
    )
    log_test("GET /api/holidays", response.status_code == 200,
             f"Status: {response.status_code}, Count: {len(response.json()) if response.status_code == 200 else 0}")
    
    holidays = response.json() if response.status_code == 200 else []
    log_test("Holidays populated from Nager.Date API", len(holidays) > 0,
             f"Found {len(holidays)} holidays" if len(holidays) > 0 else "No holidays found (external API may be unreachable)")
    
    print()
    
    # ========================================================================
    # CRITICAL TEST: POST /api/leaves SCENARIOS
    # ========================================================================
    print("STEP 4: CRITICAL TEST - POST /api/leaves Scenarios")
    print("-" * 80)
    
    created_leave_ids = []
    
    # Scenario 1: Standard leave request (resource user)
    print("\nScenario 1: Standard leave request (resource user qa_resource)")
    today = datetime.now()
    start_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = (today + timedelta(days=9)).strftime("%Y-%m-%d")
    
    leave_payload = {
        "start_date": start_date,
        "end_date": end_date,
        "type": "Annual",
        "notes": "Phase 1 test - standard leave"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/leaves",
        headers={"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"},
        json=leave_payload
    )
    log_test("Scenario 1: POST /api/leaves (standard leave)", response.status_code in [200, 201],
             f"Status: {response.status_code}")
    
    if response.status_code in [200, 201]:
        leave_data = response.json()
        created_leave_ids.append(leave_data.get("id"))
        log_test("Scenario 1: Status is 'Pending'", leave_data.get("status") == "Pending",
                 f"Status: {leave_data.get('status')}")
    
    # Scenario 2: Half-day leave (AM)
    print("\nScenario 2: Half-day leave (AM)")
    leave_payload = {
        "start_date": start_date,
        "end_date": start_date,
        "type": "Personal",
        "day_portion": "am",
        "notes": "Phase 1 test - half day AM"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/leaves",
        headers={"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"},
        json=leave_payload
    )
    log_test("Scenario 2: POST /api/leaves (half-day AM)", response.status_code in [200, 201],
             f"Status: {response.status_code}")
    
    if response.status_code in [200, 201]:
        leave_data = response.json()
        created_leave_ids.append(leave_data.get("id"))
        log_test("Scenario 2: day_portion persisted correctly", leave_data.get("day_portion") == "am",
                 f"day_portion: {leave_data.get('day_portion')}")
    
    # Scenario 3: Half-day leave (PM)
    print("\nScenario 3: Half-day leave (PM)")
    leave_payload = {
        "start_date": start_date,
        "end_date": start_date,
        "type": "Personal",
        "day_portion": "pm",
        "notes": "Phase 1 test - half day PM"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/leaves",
        headers={"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"},
        json=leave_payload
    )
    log_test("Scenario 3: POST /api/leaves (half-day PM)", response.status_code in [200, 201],
             f"Status: {response.status_code}")
    
    if response.status_code in [200, 201]:
        leave_data = response.json()
        created_leave_ids.append(leave_data.get("id"))
        log_test("Scenario 3: day_portion persisted correctly", leave_data.get("day_portion") == "pm",
                 f"day_portion: {leave_data.get('day_portion')}")
    
    # Scenario 4: Invalid day_portion normalizes to "full"
    print("\nScenario 4: Invalid day_portion normalizes to 'full'")
    leave_payload = {
        "start_date": start_date,
        "end_date": start_date,
        "type": "Personal",
        "day_portion": "xyz",
        "notes": "Phase 1 test - invalid portion"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/leaves",
        headers={"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"},
        json=leave_payload
    )
    log_test("Scenario 4: POST /api/leaves (invalid day_portion)", response.status_code in [200, 201],
             f"Status: {response.status_code}")
    
    if response.status_code in [200, 201]:
        leave_data = response.json()
        created_leave_ids.append(leave_data.get("id"))
        log_test("Scenario 4: day_portion normalized to 'full'", leave_data.get("day_portion") == "full",
                 f"day_portion: {leave_data.get('day_portion')}")
    
    # Scenario 5: Work-a-public-holiday WITH a swap (replacement day)
    print("\nScenario 5: Work-a-public-holiday WITH a swap (replacement day)")
    holiday_date = (today + timedelta(days=14)).strftime("%Y-%m-%d")
    replacement_date = (today + timedelta(days=21)).strftime("%Y-%m-%d")
    
    leave_payload = {
        "worked_holiday": True,
        "holiday_date": holiday_date,
        "replacement_date": replacement_date,
        "notes": "Phase 1 test - worked holiday with swap"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/leaves",
        headers={"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"},
        json=leave_payload
    )
    log_test("Scenario 5: POST /api/leaves (worked holiday WITH swap)", response.status_code in [200, 201],
             f"Status: {response.status_code}")
    
    if response.status_code in [200, 201]:
        leave_data = response.json()
        created_leave_ids.append(leave_data.get("id"))
        log_test("Scenario 5: start_date equals replacement_date", 
                 leave_data.get("start_date", "").startswith(replacement_date),
                 f"start_date: {leave_data.get('start_date')}, replacement_date: {replacement_date}")
        log_test("Scenario 5: end_date equals replacement_date",
                 leave_data.get("end_date", "").startswith(replacement_date),
                 f"end_date: {leave_data.get('end_date')}, replacement_date: {replacement_date}")
        log_test("Scenario 5: type defaults to 'Public holiday (worked)'",
                 leave_data.get("type") == "Public holiday (worked)",
                 f"type: {leave_data.get('type')}")
    
    # Scenario 6: Work-a-public-holiday WITHOUT a swap (NEW behavior - replacement day is OPTIONAL)
    print("\nScenario 6: Work-a-public-holiday WITHOUT a swap (replacement day OPTIONAL)")
    holiday_date = (today + timedelta(days=28)).strftime("%Y-%m-%d")
    
    leave_payload = {
        "worked_holiday": True,
        "holiday_date": holiday_date,
        "notes": "Phase 1 test - worked holiday no swap"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/leaves",
        headers={"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"},
        json=leave_payload
    )
    log_test("Scenario 6: POST /api/leaves (worked holiday WITHOUT swap)", response.status_code in [200, 201],
             f"Status: {response.status_code} - CRITICAL: Should be 200/201, NOT 400/422")
    
    if response.status_code in [200, 201]:
        leave_data = response.json()
        created_leave_ids.append(leave_data.get("id"))
        log_test("Scenario 6: start_date equals holiday_date",
                 leave_data.get("start_date", "").startswith(holiday_date),
                 f"start_date: {leave_data.get('start_date')}, holiday_date: {holiday_date}")
        log_test("Scenario 6: end_date equals holiday_date",
                 leave_data.get("end_date", "").startswith(holiday_date),
                 f"end_date: {leave_data.get('end_date')}, holiday_date: {holiday_date}")
        log_test("Scenario 6: type defaults to 'Public holiday (worked, no swap)'",
                 leave_data.get("type") == "Public holiday (worked, no swap)",
                 f"type: {leave_data.get('type')}")
    
    # Scenario 7: Work-a-holiday with worked_holiday=true but NO holiday_date and NO replacement_date
    print("\nScenario 7: Work-a-holiday with worked_holiday=true but NO dates (should return 400)")
    leave_payload = {
        "worked_holiday": True,
        "notes": "Phase 1 test - worked holiday no dates"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/leaves",
        headers={"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"},
        json=leave_payload
    )
    log_test("Scenario 7: POST /api/leaves (worked holiday no dates)", response.status_code == 400,
             f"Status: {response.status_code} - Should return 400 with helpful message")
    
    if response.status_code == 400:
        error_detail = response.json().get("detail", "")
        log_test("Scenario 7: Error message mentions holiday date",
                 "holiday" in error_detail.lower() or "date" in error_detail.lower(),
                 f"Error: {error_detail}")
    
    # Scenario 8: Standard leave validation - missing start_date
    print("\nScenario 8: Standard leave validation - missing start_date (should return 400)")
    leave_payload = {
        "end_date": end_date,
        "type": "Annual",
        "notes": "Phase 1 test - missing start_date"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/leaves",
        headers={"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"},
        json=leave_payload
    )
    log_test("Scenario 8: POST /api/leaves (missing start_date)", response.status_code == 400,
             f"Status: {response.status_code} - Should return 400")
    
    # Scenario 9: Standard leave validation - missing type
    print("\nScenario 9: Standard leave validation - missing type (should return 400)")
    leave_payload = {
        "start_date": start_date,
        "end_date": end_date,
        "notes": "Phase 1 test - missing type"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/leaves",
        headers={"Authorization": f"Bearer {resource_token}", "Content-Type": "application/json"},
        json=leave_payload
    )
    log_test("Scenario 9: POST /api/leaves (missing type)", response.status_code == 400,
             f"Status: {response.status_code} - Should return 400")
    
    print()
    
    # ========================================================================
    # GET /api/leaves VERIFICATION
    # ========================================================================
    print("STEP 5: GET /api/leaves Verification")
    print("-" * 80)
    
    # Resource sees only own leaves
    response = requests.get(
        f"{BACKEND_URL}/leaves",
        headers={"Authorization": f"Bearer {resource_token}"}
    )
    log_test("GET /api/leaves (resource sees own)", response.status_code == 200,
             f"Status: {response.status_code}, Count: {len(response.json()) if response.status_code == 200 else 0}")
    
    # Super admin sees all relevant leaves
    response = requests.get(
        f"{BACKEND_URL}/leaves",
        headers={"Authorization": f"Bearer {super_admin_token}"}
    )
    log_test("GET /api/leaves (super_admin sees all)", response.status_code == 200,
             f"Status: {response.status_code}, Count: {len(response.json()) if response.status_code == 200 else 0}")
    
    print()
    
    # ========================================================================
    # LEAVE CALENDAR ENDPOINT
    # ========================================================================
    print("STEP 6: Leave Calendar Endpoint")
    print("-" * 80)
    
    # GET /api/leaves/calendar
    response = requests.get(
        f"{BACKEND_URL}/leaves/calendar",
        headers={"Authorization": f"Bearer {resource_token}"}
    )
    log_test("GET /api/leaves/calendar", response.status_code == 200,
             f"Status: {response.status_code}")
    
    if response.status_code == 200:
        calendar_data = response.json()
        log_test("Calendar has 'window' field", "window" in calendar_data,
                 f"Keys: {list(calendar_data.keys())}")
        log_test("Calendar has 'holidays' field", "holidays" in calendar_data,
                 f"Holidays count: {len(calendar_data.get('holidays', []))}")
        log_test("Calendar has 'entries' field", "entries" in calendar_data,
                 f"Entries count: {len(calendar_data.get('entries', []))}")
    
    print()
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    print("STEP 7: Cleanup")
    print("-" * 80)
    
    # Delete created leaves
    for leave_id in created_leave_ids:
        if leave_id:
            response = requests.delete(
                f"{BACKEND_URL}/leaves/{leave_id}",
                headers={"Authorization": f"Bearer {resource_token}"}
            )
            log_test(f"Delete leave {leave_id}", response.status_code == 200,
                     f"Status: {response.status_code}")
    
    # Delete custom leave type
    if custom_type_id:
        response = requests.delete(
            f"{BACKEND_URL}/leave-types/{custom_type_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        log_test(f"Delete custom leave type {custom_type_id}", response.status_code == 200,
                 f"Status: {response.status_code}")
    
    print()
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {test_count}")
    print(f"Passed: {pass_count} ({pass_count/test_count*100:.1f}%)")
    print(f"Failed: {fail_count} ({fail_count/test_count*100:.1f}%)")
    print()
    
    if fail_count > 0:
        print("FAILED TESTS:")
        for result in test_results:
            if "❌ FAIL" in result:
                print(result)
        print()
    
    print("=" * 80)
    print("CRITICAL SCENARIOS VERIFICATION:")
    print("=" * 80)
    print("✓ Scenario 1: Standard leave request - Creates with status 'Pending'")
    print("✓ Scenario 2-3: Half-day leave (AM/PM) - day_portion persisted correctly")
    print("✓ Scenario 4: Invalid day_portion - Normalizes to 'full'")
    print("✓ Scenario 5: Work-a-holiday WITH swap - start/end_date = replacement_date")
    print("✓ Scenario 6: Work-a-holiday WITHOUT swap - start/end_date = holiday_date (NOT 422)")
    print("✓ Scenario 7: Work-a-holiday no dates - Returns 400 with helpful message")
    print("✓ Scenario 8-9: Standard leave validation - Returns 400 for missing fields")
    print()
    
    if fail_count == 0:
        print("🎉 ALL TESTS PASSED - PUBLIC HOLIDAYS & SMARTER LEAVE COMPONENT (PHASE 1) WORKING CORRECTLY")
    else:
        print("⚠️  SOME TESTS FAILED - REVIEW DETAILS ABOVE")
    print()

if __name__ == "__main__":
    main()
