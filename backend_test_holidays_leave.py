#!/usr/bin/env python3
"""
Comprehensive backend test for DD Planner "Public Holidays & Smarter Leave" feature.
Tests holiday region settings, public holiday loading, leave types CRUD, half-day leaves,
work-swap validation, capacity reports, and calendar endpoint with resource scoping.
"""

import httpx
import sys
from datetime import datetime

# Base URL from frontend/.env
BASE_URL = "https://proposal-approve.preview.emergentagent.com/api"

# Test credentials from test_credentials.md
SUPERADMIN_EMAIL = "superadmin@test.com"
SUPERADMIN_PASSWORD = "Super@2026"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"
RESOURCE_EMAIL = "qa_resource@test.com"
RESOURCE_PASSWORD = "Test@2026"

# Test results tracking
results = []
leave_ids = []  # Track created leave IDs for cleanup

def log_result(step, status, message, actual_value=None):
    """Log test result"""
    results.append({
        "step": step,
        "status": status,
        "message": message,
        "actual_value": actual_value
    })
    status_icon = "✅" if status == "PASS" else "❌"
    print(f"{status_icon} Step {step}: {message}")
    if actual_value is not None:
        print(f"   Actual: {actual_value}")

def login(email, password):
    """Login and return access token"""
    try:
        response = httpx.post(
            f"{BASE_URL}/auth/login",
            data={"username": email, "password": password},
            timeout=30.0
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            print(f"❌ Login failed for {email}: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Login exception for {email}: {e}")
        return None

def main():
    print("=" * 80)
    print("DD PLANNER - PUBLIC HOLIDAYS & SMARTER LEAVE - BACKEND TEST")
    print("=" * 80)
    print(f"Backend URL: {BASE_URL}")
    print(f"Test Time: {datetime.now().isoformat()}")
    print("=" * 80)
    
    # Login all users
    print("\n🔐 AUTHENTICATION")
    superadmin_token = login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    resource_token = login(RESOURCE_EMAIL, RESOURCE_PASSWORD)
    
    if not superadmin_token or not admin_token or not resource_token:
        print("❌ CRITICAL: Authentication failed. Cannot proceed.")
        sys.exit(1)
    
    print(f"✅ Superadmin authenticated: {SUPERADMIN_EMAIL}")
    print(f"✅ Admin authenticated: {ADMIN_EMAIL}")
    print(f"✅ Resource authenticated: {RESOURCE_EMAIL}")
    
    superadmin_headers = {"Authorization": f"Bearer {superadmin_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    resource_headers = {"Authorization": f"Bearer {resource_token}"}
    
    # Get resource ID for qa_resource (Bob Smith)
    try:
        me_response = httpx.get(f"{BASE_URL}/auth/me", headers=resource_headers, timeout=30.0)
        resource_id = me_response.json().get("resource_id") if me_response.status_code == 200 else None
        print(f"✅ Resource ID for Bob Smith: {resource_id}")
    except Exception as e:
        print(f"❌ Failed to get resource ID: {e}")
        resource_id = None
    
    print("\n" + "=" * 80)
    print("TEST EXECUTION")
    print("=" * 80)
    
    # STEP 1: GET /api/settings/holiday-region (admin token)
    print("\n📋 STEP 1: GET /api/settings/holiday-region (admin token)")
    try:
        response = httpx.get(f"{BASE_URL}/settings/holiday-region", headers=admin_headers, timeout=30.0)
        if response.status_code == 200:
            data = response.json()
            available = data.get("available", [])
            # API returns objects with 'value' and 'label' keys
            region_values = [r.get("value") if isinstance(r, dict) else r for r in available]
            has_au_nat = "AU-NAT" in region_values
            has_au_nsw = "AU-NSW" in region_values
            has_au_qld = "AU-QLD" in region_values
            
            if has_au_nat and has_au_nsw and has_au_qld:
                log_result(1, "PASS", "GET holiday-region returns 200 with AU-NAT/AU-NSW/AU-QLD", 
                          f"regions={region_values}")
            else:
                log_result(1, "FAIL", "Missing expected regions", 
                          f"regions={region_values}, has AU-NAT={has_au_nat}, AU-NSW={has_au_nsw}, AU-QLD={has_au_qld}")
        else:
            log_result(1, "FAIL", f"GET holiday-region returned {response.status_code}", response.text[:200])
    except Exception as e:
        log_result(1, "FAIL", f"Exception: {e}")
    
    # STEP 2: As superadmin PUT /api/settings/holiday-region {"region":"AU-NSW"}
    print("\n📋 STEP 2: PUT /api/settings/holiday-region (superadmin, region=AU-NSW)")
    try:
        response = httpx.put(
            f"{BASE_URL}/settings/holiday-region",
            headers=superadmin_headers,
            json={"region": "AU-NSW"},
            timeout=60.0  # Longer timeout for API call to Nager.Date
        )
        if response.status_code == 200:
            data = response.json()
            holidays_loaded = data.get("holidays_loaded", 0)
            
            if holidays_loaded > 0:
                log_result(2, "PASS", f"PUT holiday-region returns 200, holidays_loaded={holidays_loaded} (>0)", 
                          f"holidays_loaded={holidays_loaded}")
            else:
                log_result(2, "FAIL", f"holidays_loaded is {holidays_loaded}, expected >0", 
                          f"Response: {data}")
        else:
            log_result(2, "FAIL", f"PUT holiday-region returned {response.status_code}", response.text[:200])
    except Exception as e:
        log_result(2, "FAIL", f"Exception: {e}")
    
    # STEP 3: As admin GET /api/holidays
    print("\n📋 STEP 3: GET /api/holidays (admin, check auto public holidays)")
    try:
        response = httpx.get(f"{BASE_URL}/holidays", headers=admin_headers, timeout=30.0)
        if response.status_code == 200:
            holidays = response.json()
            auto_public = [h for h in holidays if h.get("source") == "auto" and h.get("is_public_holiday") == True]
            
            if len(auto_public) > 0:
                sample_name = auto_public[0].get("name", "N/A")
                log_result(3, "PASS", f"GET holidays returns {len(auto_public)} auto public holidays", 
                          f"count={len(auto_public)}, sample_name='{sample_name}'")
            else:
                log_result(3, "FAIL", f"No auto public holidays found", 
                          f"Total holidays: {len(holidays)}")
        else:
            log_result(3, "FAIL", f"GET holidays returned {response.status_code}", response.text[:200])
    except Exception as e:
        log_result(3, "FAIL", f"Exception: {e}")
    
    # STEP 4: As superadmin POST /api/holidays/refresh-public {"year":2026}
    print("\n📋 STEP 4: POST /api/holidays/refresh-public (superadmin, year=2026)")
    try:
        response = httpx.post(
            f"{BASE_URL}/holidays/refresh-public",
            headers=superadmin_headers,
            json={"year": 2026},
            timeout=60.0
        )
        if response.status_code == 200:
            data = response.json()
            holidays_loaded = data.get("holidays_loaded", 0)
            
            if holidays_loaded > 0:
                log_result(4, "PASS", f"POST refresh-public returns 200, holidays_loaded={holidays_loaded} (>0)", 
                          f"holidays_loaded={holidays_loaded}")
            else:
                log_result(4, "FAIL", f"holidays_loaded is {holidays_loaded}, expected >0", 
                          f"Response: {data}")
        else:
            log_result(4, "FAIL", f"POST refresh-public returned {response.status_code}", response.text[:200])
    except Exception as e:
        log_result(4, "FAIL", f"Exception: {e}")
    
    # STEP 5: As qa_resource PUT /api/settings/holiday-region (expect 403)
    print("\n📋 STEP 5: PUT /api/settings/holiday-region (qa_resource, expect 403)")
    try:
        response = httpx.put(
            f"{BASE_URL}/settings/holiday-region",
            headers=resource_headers,
            json={"region": "AU-QLD"},
            timeout=30.0
        )
        if response.status_code == 403:
            log_result(5, "PASS", "PUT holiday-region as resource correctly returns 403", 
                      f"status={response.status_code}")
        else:
            log_result(5, "FAIL", f"Expected 403, got {response.status_code}", response.text[:200])
    except Exception as e:
        log_result(5, "FAIL", f"Exception: {e}")
    
    # STEP 6: Leave types CRUD
    print("\n📋 STEP 6: Leave types CRUD")
    
    # 6a: GET /api/leave-types (admin)
    print("  6a: GET /api/leave-types (admin)")
    try:
        response = httpx.get(f"{BASE_URL}/leave-types", headers=admin_headers, timeout=30.0)
        if response.status_code == 200:
            leave_types = response.json()
            type_names = [lt.get("name") for lt in leave_types]
            required = ["Annual", "Sick", "Personal", "Unpaid", "Parental"]
            has_all = all(req in type_names for req in required)
            
            if has_all:
                log_result("6a", "PASS", f"GET leave-types includes all required types", 
                          f"types={type_names}")
            else:
                log_result("6a", "FAIL", f"Missing required leave types", 
                          f"types={type_names}, required={required}")
        else:
            log_result("6a", "FAIL", f"GET leave-types returned {response.status_code}", response.text[:200])
    except Exception as e:
        log_result("6a", "FAIL", f"Exception: {e}")
    
    # 6b: POST /api/leave-types (admin, create "Study Leave")
    print("  6b: POST /api/leave-types (admin, create 'Study Leave')")
    study_leave_id = None
    try:
        response = httpx.post(
            f"{BASE_URL}/leave-types",
            headers=admin_headers,
            json={"name": "Study Leave"},
            timeout=30.0
        )
        if response.status_code == 200:
            data = response.json()
            study_leave_id = data.get("id")
            log_result("6b", "PASS", f"POST leave-types creates 'Study Leave'", 
                      f"id={study_leave_id}")
        else:
            log_result("6b", "FAIL", f"POST leave-types returned {response.status_code}", response.text[:200])
    except Exception as e:
        log_result("6b", "FAIL", f"Exception: {e}")
    
    # 6c: POST /api/leave-types (admin, duplicate "study leave" - expect 400)
    print("  6c: POST /api/leave-types (admin, duplicate 'study leave', expect 400)")
    try:
        response = httpx.post(
            f"{BASE_URL}/leave-types",
            headers=admin_headers,
            json={"name": "study leave"},
            timeout=30.0
        )
        if response.status_code == 400:
            log_result("6c", "PASS", "POST duplicate leave-type correctly returns 400", 
                      f"status={response.status_code}")
        else:
            log_result("6c", "FAIL", f"Expected 400, got {response.status_code}", response.text[:200])
    except Exception as e:
        log_result("6c", "FAIL", f"Exception: {e}")
    
    # 6d: PUT /api/leave-types/{id} (admin, set is_active=false)
    print("  6d: PUT /api/leave-types/{id} (admin, set is_active=false)")
    if study_leave_id:
        try:
            response = httpx.put(
                f"{BASE_URL}/leave-types/{study_leave_id}",
                headers=admin_headers,
                json={"is_active": False},
                timeout=30.0
            )
            if response.status_code == 200:
                log_result("6d", "PASS", "PUT leave-types sets is_active=false", 
                          f"id={study_leave_id}")
            else:
                log_result("6d", "FAIL", f"PUT leave-types returned {response.status_code}", response.text[:200])
        except Exception as e:
            log_result("6d", "FAIL", f"Exception: {e}")
    else:
        log_result("6d", "SKIP", "No study_leave_id from step 6b")
    
    # 6e: DELETE /api/leave-types/{id} (admin)
    print("  6e: DELETE /api/leave-types/{id} (admin)")
    if study_leave_id:
        try:
            response = httpx.delete(
                f"{BASE_URL}/leave-types/{study_leave_id}",
                headers=admin_headers,
                timeout=30.0
            )
            if response.status_code == 200:
                log_result("6e", "PASS", "DELETE leave-types successful", 
                          f"id={study_leave_id}")
            else:
                log_result("6e", "FAIL", f"DELETE leave-types returned {response.status_code}", response.text[:200])
        except Exception as e:
            log_result("6e", "FAIL", f"Exception: {e}")
    else:
        log_result("6e", "SKIP", "No study_leave_id from step 6b")
    
    # 6f: POST /api/leave-types (qa_resource, expect 403)
    print("  6f: POST /api/leave-types (qa_resource, expect 403)")
    try:
        response = httpx.post(
            f"{BASE_URL}/leave-types",
            headers=resource_headers,
            json={"name": "x"},
            timeout=30.0
        )
        if response.status_code == 403:
            log_result("6f", "PASS", "POST leave-types as resource correctly returns 403", 
                      f"status={response.status_code}")
        else:
            log_result("6f", "FAIL", f"Expected 403, got {response.status_code}", response.text[:200])
    except Exception as e:
        log_result("6f", "FAIL", f"Exception: {e}")
    
    # STEP 7: HALF-DAY leave
    print("\n📋 STEP 7: HALF-DAY leave (qa_resource, 2026-02-10 AM)")
    leave_id_a = None
    try:
        response = httpx.post(
            f"{BASE_URL}/leaves",
            headers=resource_headers,
            json={
                "start_date": "2026-02-10",
                "end_date": "2026-02-10",
                "type": "Annual",
                "day_portion": "am"
            },
            timeout=30.0
        )
        if response.status_code == 200:
            data = response.json()
            leave_id_a = data.get("id")
            status = data.get("status")
            day_portion = data.get("day_portion")
            
            if status == "Pending" and day_portion == "am":
                log_result(7, "PASS", f"POST leaves creates half-day (AM) leave, status=Pending", 
                          f"id={leave_id_a}, status={status}, day_portion={day_portion}")
                leave_ids.append(leave_id_a)
            else:
                log_result(7, "FAIL", f"Unexpected status or day_portion", 
                          f"status={status}, day_portion={day_portion}")
        else:
            log_result(7, "FAIL", f"POST leaves returned {response.status_code}", response.text[:200])
    except Exception as e:
        log_result(7, "FAIL", f"Exception: {e}")
    
    # 7b: Approve half-day leave (superadmin)
    print("  7b: Approve half-day leave (superadmin)")
    if leave_id_a:
        try:
            response = httpx.put(
                f"{BASE_URL}/leaves/{leave_id_a}/approve",
                headers=superadmin_headers,
                timeout=30.0
            )
            if response.status_code == 200:
                log_result("7b", "PASS", "PUT leaves/approve successful", 
                          f"id={leave_id_a}")
            else:
                log_result("7b", "FAIL", f"PUT leaves/approve returned {response.status_code}", response.text[:200])
        except Exception as e:
            log_result("7b", "FAIL", f"Exception: {e}")
    else:
        log_result("7b", "SKIP", "No leave_id_a from step 7")
    
    # STEP 8: WORK-SWAP VALIDATION (no replacement_date, expect 400)
    print("\n📋 STEP 8: WORK-SWAP VALIDATION (no replacement_date, expect 400)")
    try:
        response = httpx.post(
            f"{BASE_URL}/leaves",
            headers=resource_headers,
            json={
                "start_date": "2026-01-26",
                "end_date": "2026-01-26",
                "worked_holiday": True,
                "holiday_date": "2026-01-26",
                "type": "Public holiday (worked)"
            },
            timeout=30.0
        )
        if response.status_code == 400:
            log_result(8, "PASS", "POST work-swap without replacement_date correctly returns 400", 
                      f"status={response.status_code}")
        else:
            log_result(8, "FAIL", f"Expected 400, got {response.status_code}", response.text[:200])
    except Exception as e:
        log_result(8, "FAIL", f"Exception: {e}")
    
    # STEP 9: WORK-SWAP VALID (with replacement_date)
    print("\n📋 STEP 9: WORK-SWAP VALID (with replacement_date)")
    leave_id_b = None
    try:
        response = httpx.post(
            f"{BASE_URL}/leaves",
            headers=resource_headers,
            json={
                "start_date": "2026-01-28",
                "end_date": "2026-01-28",
                "worked_holiday": True,
                "holiday_date": "2026-01-26",
                "replacement_date": "2026-01-28",
                "type": "Public holiday (worked)"
            },
            timeout=30.0
        )
        if response.status_code == 200:
            data = response.json()
            leave_id_b = data.get("id")
            log_result(9, "PASS", f"POST work-swap with replacement_date successful", 
                      f"id={leave_id_b}")
            leave_ids.append(leave_id_b)
        else:
            log_result(9, "FAIL", f"POST work-swap returned {response.status_code}", response.text[:200])
    except Exception as e:
        log_result(9, "FAIL", f"Exception: {e}")
    
    # 9b: Approve work-swap leave (superadmin)
    print("  9b: Approve work-swap leave (superadmin)")
    if leave_id_b:
        try:
            response = httpx.put(
                f"{BASE_URL}/leaves/{leave_id_b}/approve",
                headers=superadmin_headers,
                timeout=30.0
            )
            if response.status_code == 200:
                log_result("9b", "PASS", "PUT leaves/approve successful", 
                          f"id={leave_id_b}")
            else:
                log_result("9b", "FAIL", f"PUT leaves/approve returned {response.status_code}", response.text[:200])
        except Exception as e:
            log_result("9b", "FAIL", f"Exception: {e}")
    else:
        log_result("9b", "SKIP", "No leave_id_b from step 9")
    
    # STEP 10: CAPACITY report (work-swap dates)
    print("\n📋 STEP 10: CAPACITY report (2026-01-26 to 2026-01-28)")
    try:
        response = httpx.get(
            f"{BASE_URL}/reports/capacity",
            headers=superadmin_headers,
            params={"start_date": "2026-01-26", "end_date": "2026-01-28"},
            timeout=30.0
        )
        if response.status_code == 200:
            capacity_data = response.json()
            resources = capacity_data.get("resources", [])
            
            # Find Bob Smith in capacity data
            bob_data = None
            for resource in resources:
                if resource.get("name") == "Bob Smith" or (resource_id and resource.get("resource_id") == resource_id):
                    bob_data = resource
                    break
            
            if bob_data:
                days = bob_data.get("days", [])
                day_0126 = next((d for d in days if d.get("date") == "2026-01-26"), None)
                day_0127 = next((d for d in days if d.get("date") == "2026-01-27"), None)
                day_0128 = next((d for d in days if d.get("date") == "2026-01-28"), None)
                
                # EXPECT: 01-26 on_leave=false (worked holiday), 01-28 on_leave=true (replacement)
                on_leave_0126 = day_0126.get("on_leave") if day_0126 else None
                on_leave_0127 = day_0127.get("on_leave") if day_0127 else None
                on_leave_0128 = day_0128.get("on_leave") if day_0128 else None
                
                if on_leave_0126 == False and on_leave_0128 == True:
                    log_result(10, "PASS", "Capacity report shows correct work-swap: 01-26 on_leave=false, 01-28 on_leave=true", 
                              f"01-26={on_leave_0126}, 01-27={on_leave_0127}, 01-28={on_leave_0128}")
                else:
                    log_result(10, "FAIL", "Capacity report work-swap incorrect", 
                              f"01-26={on_leave_0126} (expect False), 01-28={on_leave_0128} (expect True)")
            else:
                log_result(10, "FAIL", "Bob Smith not found in capacity report", 
                          f"Available resources: {[r.get('name') for r in resources]}")
        else:
            log_result(10, "FAIL", f"GET capacity returned {response.status_code}", response.text[:200])
    except Exception as e:
        log_result(10, "FAIL", f"Exception: {e}")
    
    # STEP 11: HALF-DAY CAPACITY
    print("\n📋 STEP 11: HALF-DAY CAPACITY (2026-02-10)")
    try:
        response = httpx.get(
            f"{BASE_URL}/reports/capacity",
            headers=superadmin_headers,
            params={"start_date": "2026-02-10", "end_date": "2026-02-10"},
            timeout=30.0
        )
        if response.status_code == 200:
            capacity_data = response.json()
            
            # Find Bob Smith
            bob_data = None
            for resource in capacity_data:
                if resource.get("name") == "Bob Smith" or (resource_id and resource.get("resource_id") == resource_id):
                    bob_data = resource
                    break
            
            if bob_data:
                days = bob_data.get("days", [])
                day_0210 = next((d for d in days if d.get("date") == "2026-02-10"), None)
                
                if day_0210:
                    half_day = day_0210.get("half_day")
                    on_leave = day_0210.get("on_leave")
                    
                    if half_day == True and on_leave == True:
                        log_result(11, "PASS", "Half-day capacity shows half_day=true and on_leave=true", 
                                  f"half_day={half_day}, on_leave={on_leave}")
                    else:
                        log_result(11, "FAIL", "Half-day capacity incorrect", 
                                  f"half_day={half_day} (expect True), on_leave={on_leave} (expect True)")
                else:
                    log_result(11, "FAIL", "Date 2026-02-10 not found in Bob's days", 
                              f"Available dates: {[d.get('date') for d in days]}")
            else:
                log_result(11, "FAIL", "Bob Smith not found in capacity report", 
                          f"Available resources: {[r.get('name') for r in capacity_data]}")
        else:
            log_result(11, "FAIL", f"GET capacity returned {response.status_code}", response.text[:200])
    except Exception as e:
        log_result(11, "FAIL", f"Exception: {e}")
    
    # STEP 12: CALENDAR endpoint with resource scoping
    print("\n📋 STEP 12: CALENDAR endpoint (resource scoping)")
    
    # 12a: As superadmin (can_see_pending=true, sees all)
    print("  12a: GET /api/leaves/calendar (superadmin)")
    try:
        response = httpx.get(
            f"{BASE_URL}/leaves/calendar",
            headers=superadmin_headers,
            params={"start": "2026-01-01", "end": "2026-01-31"},
            timeout=30.0
        )
        if response.status_code == 200:
            data = response.json()
            holidays = data.get("holidays", [])
            can_see_pending = data.get("can_see_pending")
            
            if len(holidays) > 0 and can_see_pending == True:
                log_result("12a", "PASS", "Calendar (superadmin) returns holidays and can_see_pending=true", 
                          f"holidays_count={len(holidays)}, can_see_pending={can_see_pending}")
            else:
                log_result("12a", "FAIL", "Calendar (superadmin) missing holidays or can_see_pending", 
                          f"holidays_count={len(holidays)}, can_see_pending={can_see_pending}")
        else:
            log_result("12a", "FAIL", f"GET calendar returned {response.status_code}", response.text[:200])
    except Exception as e:
        log_result("12a", "FAIL", f"Exception: {e}")
    
    # 12b: As qa_resource (can_see_pending=false, only own entries, no 'notes')
    print("  12b: GET /api/leaves/calendar (qa_resource)")
    try:
        response = httpx.get(
            f"{BASE_URL}/leaves/calendar",
            headers=resource_headers,
            params={"start": "2026-01-01", "end": "2026-01-31"},
            timeout=30.0
        )
        if response.status_code == 200:
            data = response.json()
            can_see_pending = data.get("can_see_pending")
            entries = data.get("entries", [])
            
            # Check can_see_pending=false
            if can_see_pending != False:
                log_result("12b", "FAIL", f"can_see_pending should be false for resource", 
                          f"can_see_pending={can_see_pending}")
            else:
                # Check all entries are Bob's own (resource_id matches)
                all_own = all(e.get("resource_id") == resource_id for e in entries if "resource_id" in e)
                
                # Check no 'notes' key in entries
                has_notes = any("notes" in e for e in entries)
                
                if all_own and not has_notes:
                    log_result("12b", "PASS", "Calendar (resource) shows can_see_pending=false, only own entries, no 'notes' key", 
                              f"can_see_pending={can_see_pending}, entries_count={len(entries)}, all_own={all_own}, has_notes={has_notes}")
                else:
                    log_result("12b", "FAIL", "Calendar (resource) scoping incorrect", 
                              f"all_own={all_own}, has_notes={has_notes}, entries_count={len(entries)}")
        else:
            log_result("12b", "FAIL", f"GET calendar returned {response.status_code}", response.text[:200])
    except Exception as e:
        log_result("12b", "FAIL", f"Exception: {e}")
    
    # CLEANUP
    print("\n🧹 CLEANUP")
    for leave_id in leave_ids:
        try:
            response = httpx.delete(
                f"{BASE_URL}/leaves/{leave_id}",
                headers=superadmin_headers,
                timeout=30.0
            )
            if response.status_code == 200:
                print(f"✅ Deleted leave {leave_id}")
            else:
                print(f"⚠️  Failed to delete leave {leave_id}: {response.status_code}")
        except Exception as e:
            print(f"⚠️  Exception deleting leave {leave_id}: {e}")
    
    # Reset holiday region to AU-NAT
    print("  Resetting holiday region to AU-NAT")
    try:
        response = httpx.put(
            f"{BASE_URL}/settings/holiday-region",
            headers=superadmin_headers,
            json={"region": "AU-NAT"},
            timeout=60.0
        )
        if response.status_code == 200:
            print("✅ Reset holiday region to AU-NAT")
        else:
            print(f"⚠️  Failed to reset holiday region: {response.status_code}")
    except Exception as e:
        print(f"⚠️  Exception resetting holiday region: {e}")
    
    # SUMMARY
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    skip_count = sum(1 for r in results if r["status"] == "SKIP")
    total_count = len(results)
    
    print(f"\n✅ PASSED: {pass_count}/{total_count}")
    print(f"❌ FAILED: {fail_count}/{total_count}")
    print(f"⏭️  SKIPPED: {skip_count}/{total_count}")
    
    print("\n📊 DETAILED RESULTS TABLE:")
    print("-" * 80)
    print(f"{'STEP':<8} {'STATUS':<8} {'MESSAGE':<64}")
    print("-" * 80)
    for r in results:
        status_icon = "✅" if r["status"] == "PASS" else ("❌" if r["status"] == "FAIL" else "⏭️")
        print(f"{str(r['step']):<8} {status_icon:<8} {r['message'][:64]}")
    print("-" * 80)
    
    # CRITICAL CHECKS
    print("\n🔍 CRITICAL CHECKS:")
    critical_checks = {
        "Step 2: holidays_loaded > 0": any(r["step"] == 2 and r["status"] == "PASS" for r in results),
        "Step 8: Work-swap validation (400)": any(r["step"] == 8 and r["status"] == "PASS" for r in results),
        "Step 10: Work-swap capacity (01-26 false, 01-28 true)": any(r["step"] == 10 and r["status"] == "PASS" for r in results),
        "Step 11: Half-day capacity (half_day=true)": any(r["step"] == 11 and r["status"] == "PASS" for r in results),
        "Step 12: Calendar resource scoping + no notes": any(r["step"] == "12b" and r["status"] == "PASS" for r in results),
    }
    
    for check, passed in critical_checks.items():
        icon = "✅" if passed else "❌"
        print(f"{icon} {check}")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    
    # Exit with appropriate code
    if fail_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
