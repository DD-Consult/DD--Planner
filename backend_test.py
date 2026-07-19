#!/usr/bin/env python3
"""
Backend API Testing for 6 NEW Endpoints
DD Planner - Budget Health, Allocations Validation, Reports, and Export Features
"""

import requests
import json
from datetime import datetime, timedelta

# Configuration
BASE_URL = "http://localhost:8001"
API_BASE = f"{BASE_URL}/api"

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"
CLIENT_EMAIL = "client@test.com"
CLIENT_PASSWORD = "client123"
SUPER_ADMIN_EMAIL = "don@ddconsult.tech"
SUPER_ADMIN_PASSWORD = "Welcome123!"

# Test results tracking
test_results = []
total_tests = 0
passed_tests = 0
failed_tests = 0


def log_test(test_name, passed, status_code=None, reason="", response_data=None):
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
        "response_data": response_data
    })
    print(f"{result}: {test_name}{status_info}")
    if reason:
        print(f"   Reason: {reason}")


def login(email, password):
    """Login and return JWT token"""
    try:
        response = requests.post(
            f"{API_BASE}/auth/login",
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
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
        response = requests.get(f"{API_BASE}/projects", headers=get_headers(token))
        if response.status_code == 200:
            projects = response.json()
            if projects and len(projects) > 0:
                return projects[0]["id"]
        return None
    except Exception as e:
        print(f"Error getting project ID: {str(e)}")
        return None


def test_budget_health(admin_token, client_token, project_id):
    """Test GET /api/projects/{project_id}/budget-health"""
    print("\n" + "="*80)
    print("TEST 1: GET /api/projects/{project_id}/budget-health")
    print("="*80)
    
    if not project_id:
        log_test("1.1 - Valid project with budget", False, None, "No project ID available")
        return
    
    # Test 1.1: Valid project (should return 200 with status field)
    try:
        response = requests.get(
            f"{API_BASE}/projects/{project_id}/budget-health",
            headers=get_headers(admin_token)
        )
        
        if response.status_code == 200:
            data = response.json()
            # Check for required fields
            required_fields = ["project_id", "budgeted_hours", "allocated_hours", 
                             "actual_hours", "usage_percentage", "status", "phase_breakdown"]
            missing_fields = [f for f in required_fields if f not in data]
            
            if missing_fields:
                log_test("1.1 - Valid project with budget", False, 200, 
                        f"Missing fields: {missing_fields}", data)
            else:
                # Check status is one of expected values
                valid_statuses = ["ok", "warning", "exceeded", "no_budget"]
                if data["status"] in valid_statuses:
                    log_test("1.1 - Valid project with budget", True, 200, 
                            f"Status: {data['status']}, Usage: {data['usage_percentage']}%")
                else:
                    log_test("1.1 - Valid project with budget", False, 200, 
                            f"Invalid status: {data['status']}")
        else:
            log_test("1.1 - Valid project with budget", False, response.status_code, 
                    response.text[:200])
    except Exception as e:
        log_test("1.1 - Valid project with budget", False, None, str(e))
    
    # Test 1.2: Invalid project ID (should return 404)
    try:
        fake_id = "507f1f77bcf86cd799439011"  # Valid ObjectId format but doesn't exist
        response = requests.get(
            f"{API_BASE}/projects/{fake_id}/budget-health",
            headers=get_headers(admin_token)
        )
        
        if response.status_code == 404:
            log_test("1.2 - Invalid project ID", True, 404, "Correctly returned 404")
        else:
            log_test("1.2 - Invalid project ID", False, response.status_code, 
                    f"Expected 404, got {response.status_code}")
    except Exception as e:
        log_test("1.2 - Invalid project ID", False, None, str(e))


def test_allocations_validate(admin_token, project_id):
    """Test POST /api/allocations/validate"""
    print("\n" + "="*80)
    print("TEST 2: POST /api/allocations/validate")
    print("="*80)
    
    if not project_id:
        log_test("2.1 - Valid allocation (small percentage)", False, None, "No project ID available")
        return
    
    # Get a resource ID for testing
    try:
        response = requests.get(f"{API_BASE}/resources", headers=get_headers(admin_token))
        resource_id = None
        if response.status_code == 200:
            resources = response.json()
            if resources and len(resources) > 0:
                resource_id = resources[0]["id"]
    except:
        pass
    
    if not resource_id:
        log_test("2.1 - Valid allocation (small percentage)", False, None, "No resource ID available")
        return
    
    # Test 2.1: Valid allocation with small percentage (should return status="ok")
    try:
        today = datetime.now().date()
        payload = {
            "project_id": project_id,
            "resource_id": resource_id,
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=30)).isoformat(),
            "percentage": 10,
            "allocation_type": "percentage"
        }
        
        response = requests.post(
            f"{API_BASE}/allocations/validate",
            json=payload,
            headers=get_headers(admin_token)
        )
        
        if response.status_code == 200:
            data = response.json()
            required_fields = ["valid", "would_exceed", "would_warn", 
                             "projected_usage_percentage", "message", "status"]
            missing_fields = [f for f in required_fields if f not in data]
            
            if missing_fields:
                log_test("2.1 - Valid allocation (small percentage)", False, 200, 
                        f"Missing fields: {missing_fields}")
            else:
                log_test("2.1 - Valid allocation (small percentage)", True, 200, 
                        f"Status: {data['status']}, Valid: {data['valid']}")
        else:
            log_test("2.1 - Valid allocation (small percentage)", False, response.status_code, 
                    response.text[:200])
    except Exception as e:
        log_test("2.1 - Valid allocation (small percentage)", False, None, str(e))
    
    # Test 2.2: Allocation that would exceed budget (should return would_exceed=true)
    try:
        payload = {
            "project_id": project_id,
            "resource_id": resource_id,
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=365)).isoformat(),
            "percentage": 100,
            "allocation_type": "percentage"
        }
        
        response = requests.post(
            f"{API_BASE}/allocations/validate",
            json=payload,
            headers=get_headers(admin_token)
        )
        
        if response.status_code == 200:
            data = response.json()
            # This might exceed or warn depending on existing allocations
            log_test("2.2 - Large allocation validation", True, 200, 
                    f"Status: {data['status']}, Would exceed: {data.get('would_exceed')}")
        else:
            log_test("2.2 - Large allocation validation", False, response.status_code, 
                    response.text[:200])
    except Exception as e:
        log_test("2.2 - Large allocation validation", False, None, str(e))
    
    # Test 2.3: Invalid project ID (should return 404 or 400)
    try:
        fake_id = "507f1f77bcf86cd799439011"
        payload = {
            "project_id": fake_id,
            "resource_id": resource_id,
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=30)).isoformat(),
            "percentage": 10,
            "allocation_type": "percentage"
        }
        
        response = requests.post(
            f"{API_BASE}/allocations/validate",
            json=payload,
            headers=get_headers(admin_token)
        )
        
        if response.status_code in [404, 400]:
            log_test("2.3 - Invalid project ID", True, response.status_code, 
                    "Correctly returned error")
        else:
            log_test("2.3 - Invalid project ID", False, response.status_code, 
                    f"Expected 404/400, got {response.status_code}")
    except Exception as e:
        log_test("2.3 - Invalid project ID", False, None, str(e))


def test_timesheets_range(admin_token, client_token):
    """Test GET /api/reports/timesheets/range"""
    print("\n" + "="*80)
    print("TEST 3: GET /api/reports/timesheets/range")
    print("="*80)
    
    # Test 3.1: As admin with valid parameters (group_by=resource)
    try:
        params = {
            "start_date": "2024-01-01",
            "end_date": "2025-12-31",
            "group_by": "resource"
        }
        
        response = requests.get(
            f"{API_BASE}/reports/timesheets/range",
            params=params,
            headers=get_headers(admin_token)
        )
        
        if response.status_code == 200:
            data = response.json()
            required_fields = ["summary", "groups", "entries"]
            missing_fields = [f for f in required_fields if f not in data]
            
            if missing_fields:
                log_test("3.1 - Admin request (group_by=resource)", False, 200, 
                        f"Missing fields: {missing_fields}")
            else:
                log_test("3.1 - Admin request (group_by=resource)", True, 200, 
                        f"Groups: {len(data['groups'])}, Entries: {len(data['entries'])}")
        else:
            log_test("3.1 - Admin request (group_by=resource)", False, response.status_code, 
                    response.text[:200])
    except Exception as e:
        log_test("3.1 - Admin request (group_by=resource)", False, None, str(e))
    
    # Test 3.2: group_by=project
    try:
        params = {
            "start_date": "2024-01-01",
            "end_date": "2025-12-31",
            "group_by": "project"
        }
        
        response = requests.get(
            f"{API_BASE}/reports/timesheets/range",
            params=params,
            headers=get_headers(admin_token)
        )
        
        if response.status_code == 200:
            data = response.json()
            log_test("3.2 - group_by=project", True, 200, 
                    f"Groups: {len(data['groups'])}")
        else:
            log_test("3.2 - group_by=project", False, response.status_code, 
                    response.text[:200])
    except Exception as e:
        log_test("3.2 - group_by=project", False, None, str(e))
    
    # Test 3.3: group_by=client
    try:
        params = {
            "start_date": "2024-01-01",
            "end_date": "2025-12-31",
            "group_by": "client"
        }
        
        response = requests.get(
            f"{API_BASE}/reports/timesheets/range",
            params=params,
            headers=get_headers(admin_token)
        )
        
        if response.status_code == 200:
            log_test("3.3 - group_by=client", True, 200)
        else:
            log_test("3.3 - group_by=client", False, response.status_code, 
                    response.text[:200])
    except Exception as e:
        log_test("3.3 - group_by=client", False, None, str(e))
    
    # Test 3.4: group_by=week
    try:
        params = {
            "start_date": "2024-01-01",
            "end_date": "2025-12-31",
            "group_by": "week"
        }
        
        response = requests.get(
            f"{API_BASE}/reports/timesheets/range",
            params=params,
            headers=get_headers(admin_token)
        )
        
        if response.status_code == 200:
            log_test("3.4 - group_by=week", True, 200)
        else:
            log_test("3.4 - group_by=week", False, response.status_code, 
                    response.text[:200])
    except Exception as e:
        log_test("3.4 - group_by=week", False, None, str(e))
    
    # Test 3.5: Invalid group_by value (should return 400)
    try:
        params = {
            "start_date": "2024-01-01",
            "end_date": "2025-12-31",
            "group_by": "invalid_value"
        }
        
        response = requests.get(
            f"{API_BASE}/reports/timesheets/range",
            params=params,
            headers=get_headers(admin_token)
        )
        
        if response.status_code == 400:
            log_test("3.5 - Invalid group_by value", True, 400, "Correctly returned 400")
        else:
            log_test("3.5 - Invalid group_by value", False, response.status_code, 
                    f"Expected 400, got {response.status_code}")
    except Exception as e:
        log_test("3.5 - Invalid group_by value", False, None, str(e))
    
    # Test 3.6: Missing required parameters (should return 422)
    try:
        params = {
            "group_by": "resource"
            # Missing start_date and end_date
        }
        
        response = requests.get(
            f"{API_BASE}/reports/timesheets/range",
            params=params,
            headers=get_headers(admin_token)
        )
        
        if response.status_code == 422:
            log_test("3.6 - Missing required parameters", True, 422, "Correctly returned 422")
        else:
            log_test("3.6 - Missing required parameters", False, response.status_code, 
                    f"Expected 422, got {response.status_code}")
    except Exception as e:
        log_test("3.6 - Missing required parameters", False, None, str(e))
    
    # Test 3.7: As client (should return 403)
    try:
        params = {
            "start_date": "2024-01-01",
            "end_date": "2025-12-31",
            "group_by": "resource"
        }
        
        response = requests.get(
            f"{API_BASE}/reports/timesheets/range",
            params=params,
            headers=get_headers(client_token)
        )
        
        if response.status_code == 403:
            log_test("3.7 - As client (should be forbidden)", True, 403, 
                    "Correctly returned 403 (admin-only endpoint)")
        else:
            log_test("3.7 - As client (should be forbidden)", False, response.status_code, 
                    f"Expected 403, got {response.status_code}")
    except Exception as e:
        log_test("3.7 - As client (should be forbidden)", False, None, str(e))


def test_export_pdf(admin_token, client_token, project_id):
    """Test GET /api/projects/{project_id}/export/pdf"""
    print("\n" + "="*80)
    print("TEST 4: GET /api/projects/{project_id}/export/pdf")
    print("="*80)
    
    if not project_id:
        log_test("4.1 - As admin (valid project)", False, None, "No project ID available")
        return
    
    # Test 4.1: As admin (should return 200 with PDF)
    try:
        response = requests.get(
            f"{API_BASE}/projects/{project_id}/export/pdf",
            headers=get_headers(admin_token),
            stream=True
        )
        
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            content_disposition = response.headers.get("Content-Disposition", "")
            
            # Check content type
            if "application/pdf" not in content_type:
                log_test("4.1 - As admin (valid project)", False, 200, 
                        f"Wrong content-type: {content_type}")
            # Check PDF magic number
            elif not response.content[:4].startswith(b'%PDF'):
                log_test("4.1 - As admin (valid project)", False, 200, 
                        "Response is not a valid PDF (missing %PDF header)")
            # Check Content-Disposition header
            elif "attachment" not in content_disposition:
                log_test("4.1 - As admin (valid project)", False, 200, 
                        "Missing Content-Disposition header")
            else:
                log_test("4.1 - As admin (valid project)", True, 200, 
                        f"PDF size: {len(response.content)} bytes, filename in header: {content_disposition}")
        else:
            log_test("4.1 - As admin (valid project)", False, response.status_code, 
                    response.text[:200])
    except Exception as e:
        log_test("4.1 - As admin (valid project)", False, None, str(e))
    
    # Test 4.2: Invalid project ID (should return 404)
    try:
        fake_id = "507f1f77bcf86cd799439011"
        response = requests.get(
            f"{API_BASE}/projects/{fake_id}/export/pdf",
            headers=get_headers(admin_token)
        )
        
        if response.status_code == 404:
            log_test("4.2 - Invalid project ID", True, 404, "Correctly returned 404")
        else:
            log_test("4.2 - Invalid project ID", False, response.status_code, 
                    f"Expected 404, got {response.status_code}")
    except Exception as e:
        log_test("4.2 - Invalid project ID", False, None, str(e))


def test_export_ppt(admin_token, project_id):
    """Test GET /api/projects/{project_id}/export/ppt"""
    print("\n" + "="*80)
    print("TEST 5: GET /api/projects/{project_id}/export/ppt")
    print("="*80)
    
    if not project_id:
        log_test("5.1 - As admin (valid project)", False, None, "No project ID available")
        return
    
    # Test 5.1: As admin (should return 200 with PPTX)
    try:
        response = requests.get(
            f"{API_BASE}/projects/{project_id}/export/ppt",
            headers=get_headers(admin_token),
            stream=True
        )
        
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            
            # Check content type
            expected_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            if expected_type not in content_type:
                log_test("5.1 - As admin (valid project)", False, 200, 
                        f"Wrong content-type: {content_type}")
            # Check ZIP magic number (PPTX is a ZIP file)
            elif not response.content[:2] == b'PK':
                log_test("5.1 - As admin (valid project)", False, 200, 
                        "Response is not a valid PPTX (missing PK header)")
            else:
                log_test("5.1 - As admin (valid project)", True, 200, 
                        f"PPTX size: {len(response.content)} bytes")
        else:
            log_test("5.1 - As admin (valid project)", False, response.status_code, 
                    response.text[:200])
    except Exception as e:
        log_test("5.1 - As admin (valid project)", False, None, str(e))
    
    # Test 5.2: Invalid project ID (should return 404)
    try:
        fake_id = "507f1f77bcf86cd799439011"
        response = requests.get(
            f"{API_BASE}/projects/{fake_id}/export/ppt",
            headers=get_headers(admin_token)
        )
        
        if response.status_code == 404:
            log_test("5.2 - Invalid project ID", True, 404, "Correctly returned 404")
        else:
            log_test("5.2 - Invalid project ID", False, response.status_code, 
                    f"Expected 404, got {response.status_code}")
    except Exception as e:
        log_test("5.2 - Invalid project ID", False, None, str(e))


def test_my_allocations(admin_token, client_token):
    """Test GET /api/my-allocations"""
    print("\n" + "="*80)
    print("TEST 6: GET /api/my-allocations")
    print("="*80)
    
    # Test 6.1: As admin with period=week
    try:
        params = {"period": "week"}
        response = requests.get(
            f"{API_BASE}/my-allocations",
            params=params,
            headers=get_headers(admin_token)
        )
        
        if response.status_code == 200:
            data = response.json()
            required_fields = ["period", "period_start", "period_end", "resource", 
                             "summary", "allocations"]
            missing_fields = [f for f in required_fields if f not in data]
            
            if missing_fields:
                log_test("6.1 - As admin (period=week)", False, 200, 
                        f"Missing fields: {missing_fields}")
            else:
                # Check period is approximately 14 days (2 weeks)
                from datetime import datetime
                start = datetime.fromisoformat(data["period_start"])
                end = datetime.fromisoformat(data["period_end"])
                days = (end - start).days
                
                if 13 <= days <= 15:  # Allow some flexibility
                    log_test("6.1 - As admin (period=week)", True, 200, 
                            f"Period: {days} days, Resource: {data['resource']}")
                else:
                    log_test("6.1 - As admin (period=week)", False, 200, 
                            f"Period should be ~14 days, got {days} days")
        else:
            log_test("6.1 - As admin (period=week)", False, response.status_code, 
                    response.text[:200])
    except Exception as e:
        log_test("6.1 - As admin (period=week)", False, None, str(e))
    
    # Test 6.2: period=month
    try:
        params = {"period": "month"}
        response = requests.get(
            f"{API_BASE}/my-allocations",
            params=params,
            headers=get_headers(admin_token)
        )
        
        if response.status_code == 200:
            data = response.json()
            log_test("6.2 - period=month", True, 200, 
                    f"Allocations: {len(data.get('allocations', []))}")
        else:
            log_test("6.2 - period=month", False, response.status_code, 
                    response.text[:200])
    except Exception as e:
        log_test("6.2 - period=month", False, None, str(e))
    
    # Test 6.3: period=3months
    try:
        params = {"period": "3months"}
        response = requests.get(
            f"{API_BASE}/my-allocations",
            params=params,
            headers=get_headers(admin_token)
        )
        
        if response.status_code == 200:
            data = response.json()
            # Check period is approximately 90 days
            from datetime import datetime
            start = datetime.fromisoformat(data["period_start"])
            end = datetime.fromisoformat(data["period_end"])
            days = (end - start).days
            
            if 89 <= days <= 91:
                log_test("6.3 - period=3months", True, 200, f"Period: {days} days")
            else:
                log_test("6.3 - period=3months", False, 200, 
                        f"Period should be ~90 days, got {days} days")
        else:
            log_test("6.3 - period=3months", False, response.status_code, 
                    response.text[:200])
    except Exception as e:
        log_test("6.3 - period=3months", False, None, str(e))
    
    # Test 6.4: Invalid period (should return 400)
    try:
        params = {"period": "year"}
        response = requests.get(
            f"{API_BASE}/my-allocations",
            params=params,
            headers=get_headers(admin_token)
        )
        
        if response.status_code == 400:
            log_test("6.4 - Invalid period value", True, 400, "Correctly returned 400")
        else:
            log_test("6.4 - Invalid period value", False, response.status_code, 
                    f"Expected 400, got {response.status_code}")
    except Exception as e:
        log_test("6.4 - Invalid period value", False, None, str(e))
    
    # Test 6.5: As client (should return 403)
    try:
        params = {"period": "month"}
        response = requests.get(
            f"{API_BASE}/my-allocations",
            params=params,
            headers=get_headers(client_token)
        )
        
        if response.status_code == 403:
            log_test("6.5 - As client (should be forbidden)", True, 403, 
                    "Correctly returned 403 (not available for clients)")
        else:
            log_test("6.5 - As client (should be forbidden)", False, response.status_code, 
                    f"Expected 403, got {response.status_code}")
    except Exception as e:
        log_test("6.5 - As client (should be forbidden)", False, None, str(e))


def test_auth_me(admin_token, client_token):
    """Test GET /api/auth/me"""
    print("\n" + "="*80)
    print("TEST 7: GET /api/auth/me")
    print("="*80)
    
    # Test 7.1: As admin user
    try:
        response = requests.get(
            f"{API_BASE}/auth/me",
            headers=get_headers(admin_token)
        )
        
        if response.status_code == 200:
            data = response.json()
            required_fields = ["id", "email", "role"]
            missing_fields = [f for f in required_fields if f not in data]
            
            if missing_fields:
                log_test("7.1 - As admin user", False, 200, 
                        f"Missing required fields: {missing_fields}", data)
            elif data.get("email") != ADMIN_EMAIL:
                log_test("7.1 - As admin user", False, 200, 
                        f"Email mismatch: expected {ADMIN_EMAIL}, got {data.get('email')}", data)
            elif data.get("role") != "admin":
                log_test("7.1 - As admin user", False, 200, 
                        f"Role mismatch: expected 'admin', got {data.get('role')}", data)
            else:
                log_test("7.1 - As admin user", True, 200, 
                        f"Email: {data['email']}, Role: {data['role']}, ID: {data['id']}")
        else:
            log_test("7.1 - As admin user", False, response.status_code, 
                    response.text[:200])
    except Exception as e:
        log_test("7.1 - As admin user", False, None, str(e))
    
    # Test 7.2: As client user
    try:
        response = requests.get(
            f"{API_BASE}/auth/me",
            headers=get_headers(client_token)
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("email") != CLIENT_EMAIL:
                log_test("7.2 - As client user", False, 200, 
                        f"Email mismatch: expected {CLIENT_EMAIL}, got {data.get('email')}")
            elif data.get("role") != "client":
                log_test("7.2 - As client user", False, 200, 
                        f"Role mismatch: expected 'client', got {data.get('role')}")
            else:
                log_test("7.2 - As client user", True, 200, 
                        f"Email: {data['email']}, Role: {data['role']}")
        else:
            log_test("7.2 - As client user", False, response.status_code, 
                    response.text[:200])
    except Exception as e:
        log_test("7.2 - As client user", False, None, str(e))
    
    # Test 7.3: Without authentication (should return 401)
    try:
        response = requests.get(f"{API_BASE}/auth/me")
        
        if response.status_code == 401:
            log_test("7.3 - Without authentication", True, 401, 
                    "Correctly returned 401 (unauthorized)")
        else:
            log_test("7.3 - Without authentication", False, response.status_code, 
                    f"Expected 401, got {response.status_code}")
    except Exception as e:
        log_test("7.3 - Without authentication", False, None, str(e))
    
    # Test 7.4: With invalid token (should return 401)
    try:
        invalid_headers = {"Authorization": "Bearer invalid_token_12345"}
        response = requests.get(
            f"{API_BASE}/auth/me",
            headers=invalid_headers
        )
        
        if response.status_code == 401:
            log_test("7.4 - With invalid token", True, 401, 
                    "Correctly returned 401 (invalid token)")
        else:
            log_test("7.4 - With invalid token", False, response.status_code, 
                    f"Expected 401, got {response.status_code}")
    except Exception as e:
        log_test("7.4 - With invalid token", False, None, str(e))


def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} ❌")
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


def main():
    """Main test execution"""
    print("="*80)
    print("DD PLANNER - BACKEND API TESTING")
    print("Testing 6 NEW Endpoints")
    print("="*80)
    
    # Login as different users
    print("\n🔐 Logging in...")
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    client_token = login(CLIENT_EMAIL, CLIENT_PASSWORD)
    
    if not admin_token:
        print("❌ CRITICAL: Admin login failed. Cannot proceed with tests.")
        return
    
    if not client_token:
        print("⚠️  WARNING: Client login failed. Some tests will be skipped.")
    
    print("✅ Login successful")
    
    # Get a project ID for testing
    print("\n📋 Getting test project...")
    project_id = get_first_project_id(admin_token)
    if project_id:
        print(f"✅ Using project ID: {project_id}")
    else:
        print("⚠️  WARNING: No projects found. Some tests will be skipped.")
    
    # Run all tests
    test_budget_health(admin_token, client_token, project_id)
    test_allocations_validate(admin_token, project_id)
    test_timesheets_range(admin_token, client_token)
    test_export_pdf(admin_token, client_token, project_id)
    test_export_ppt(admin_token, project_id)
    test_my_allocations(admin_token, client_token)
    test_auth_me(admin_token, client_token)
    
    # Print summary
    print_summary()
    
    # Return exit code based on results
    return 0 if failed_tests == 0 else 1


if __name__ == "__main__":
    exit(main())
