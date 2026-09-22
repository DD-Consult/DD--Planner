#!/usr/bin/env python3
"""
Comprehensive Magic Link Feature Test
Tests the complete magic link flow for DD Planner Client Portal
"""
import requests
import pymongo
from datetime import datetime
import sys

# Configuration
BACKEND_URL = "http://localhost:8001"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"
TEST_PROJECT_ID = "6ab25bc82be78e05e89230f3"  # Website Redesign
TEST_RECIPIENT_EMAIL = "client-test@example.com"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "resource_planner"

# Test results tracking
test_results = []

def log_test(step, passed, message, details=None):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status} - Step {step}: {message}")
    if details:
        print(f"  Details: {details}")
    test_results.append({
        "step": step,
        "passed": passed,
        "message": message,
        "details": details
    })

def get_verification_code_from_db(token):
    """Fetch verification code from MongoDB"""
    try:
        client = pymongo.MongoClient(MONGO_URL)
        db = client[DB_NAME]
        link = db.report_links.find_one({"token": token})
        if link:
            return link.get("verification_code")
        return None
    except Exception as e:
        print(f"Error fetching verification code from DB: {e}")
        return None

def test_admin_login():
    """Step 0: Admin login"""
    print("\n" + "="*80)
    print("STEP 0: ADMIN LOGIN")
    print("="*80)
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/auth/login",
            data={
                "username": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            if token:
                log_test(0, True, "Admin login successful", f"Token received: {token[:20]}...")
                return token
            else:
                log_test(0, False, "Admin login failed", "No access_token in response")
                return None
        else:
            log_test(0, False, f"Admin login failed with status {response.status_code}", response.text)
            return None
    except Exception as e:
        log_test(0, False, "Admin login exception", str(e))
        return None

def test_create_magic_link(admin_token):
    """Step 1: CREATE magic link"""
    print("\n" + "="*80)
    print("STEP 1: CREATE MAGIC LINK")
    print("="*80)
    
    # Test 1a: Create with admin auth
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/reports/magic-link",
            json={
                "project_id": TEST_PROJECT_ID,
                "recipient_email": TEST_RECIPIENT_EMAIL,
                "report_type": "project",
                "report_period": "whole-project"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            magic_link = data.get("magic_link")
            token = data.get("token")
            
            if magic_link and token:
                log_test("1a", True, "Magic link created successfully", 
                        f"Token: {token[:20]}..., Link: {magic_link}")
                
                # Verify response structure
                required_fields = ["magic_link", "token", "project_id", "recipient_email", 
                                 "report_type", "report_period", "created_at", "expires_at"]
                missing_fields = [f for f in required_fields if f not in data]
                if missing_fields:
                    log_test("1a-structure", False, "Response missing fields", 
                            f"Missing: {missing_fields}")
                else:
                    log_test("1a-structure", True, "Response has all required fields", None)
                
                return token
            else:
                log_test("1a", False, "Magic link creation failed", 
                        "Response missing magic_link or token")
                return None
        else:
            log_test("1a", False, f"Magic link creation failed with status {response.status_code}", 
                    response.text)
            return None
    except Exception as e:
        log_test("1a", False, "Magic link creation exception", str(e))
        return None
    
    # Test 1b: Create without auth (should fail)
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/reports/magic-link",
            json={
                "project_id": TEST_PROJECT_ID,
                "recipient_email": TEST_RECIPIENT_EMAIL,
                "report_type": "project",
                "report_period": "whole-project"
            }
        )
        
        if response.status_code in [401, 403]:
            log_test("1b", True, "Create without auth correctly rejected", 
                    f"Status: {response.status_code}")
        else:
            log_test("1b", False, f"Create without auth should return 401/403, got {response.status_code}", 
                    response.text)
    except Exception as e:
        log_test("1b", False, "Create without auth test exception", str(e))

def test_verify_token(token):
    """Step 2: VERIFY TOKEN"""
    print("\n" + "="*80)
    print("STEP 2: VERIFY TOKEN")
    print("="*80)
    
    # Test 2a: Verify valid token
    try:
        response = requests.get(f"{BACKEND_URL}/api/portal/verify/{token}")
        
        if response.status_code == 200:
            data = response.json()
            valid = data.get("valid")
            project_name = data.get("project_name")
            recipient_email = data.get("recipient_email")
            expires_at = data.get("expires_at")
            
            if valid and project_name == "Website Redesign" and recipient_email == TEST_RECIPIENT_EMAIL:
                log_test("2a", True, "Token verification successful", 
                        f"Project: {project_name}, Email: {recipient_email}, Expires: {expires_at}")
            else:
                log_test("2a", False, "Token verification response invalid", 
                        f"valid={valid}, project={project_name}, email={recipient_email}")
        else:
            log_test("2a", False, f"Token verification failed with status {response.status_code}", 
                    response.text)
    except Exception as e:
        log_test("2a", False, "Token verification exception", str(e))
    
    # Test 2b: Verify bogus token (should fail)
    try:
        response = requests.get(f"{BACKEND_URL}/api/portal/verify/BOGUSTOKEN")
        
        if response.status_code == 404:
            log_test("2b", True, "Bogus token correctly rejected", "Status: 404")
        else:
            log_test("2b", False, f"Bogus token should return 404, got {response.status_code}", 
                    response.text)
    except Exception as e:
        log_test("2b", False, "Bogus token test exception", str(e))

def test_confirm_code(token):
    """Step 3: CONFIRM CODE"""
    print("\n" + "="*80)
    print("STEP 3: CONFIRM VERIFICATION CODE")
    print("="*80)
    
    # Test 3a: Wrong code (should fail and increment attempts)
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/portal/verify/{token}/confirm",
            json={"verification_code": "000000"}
        )
        
        if response.status_code == 401:
            log_test("3a", True, "Wrong code correctly rejected", "Status: 401")
            
            # Verify attempt counter incremented in DB
            client = pymongo.MongoClient(MONGO_URL)
            db = client[DB_NAME]
            link = db.report_links.find_one({"token": token})
            if link and link.get("verification_attempts", 0) == 1:
                log_test("3a-counter", True, "Attempt counter incremented", 
                        f"Attempts: {link.get('verification_attempts')}")
            else:
                log_test("3a-counter", False, "Attempt counter not incremented correctly", 
                        f"Attempts: {link.get('verification_attempts') if link else 'N/A'}")
        else:
            log_test("3a", False, f"Wrong code should return 401, got {response.status_code}", 
                    response.text)
    except Exception as e:
        log_test("3a", False, "Wrong code test exception", str(e))
    
    # Test 3b: Get real code from DB and confirm
    try:
        real_code = get_verification_code_from_db(token)
        if not real_code:
            log_test("3b", False, "Could not fetch verification code from DB", None)
            return False
        
        print(f"  Real verification code from DB: {real_code}")
        
        response = requests.post(
            f"{BACKEND_URL}/api/portal/verify/{token}/confirm",
            json={"verification_code": real_code}
        )
        
        if response.status_code == 200:
            data = response.json()
            verified = data.get("verified")
            
            if verified:
                log_test("3b", True, "Correct code accepted", "verified=true")
                
                # Verify verified_at timestamp set in DB
                client = pymongo.MongoClient(MONGO_URL)
                db = client[DB_NAME]
                link = db.report_links.find_one({"token": token})
                if link and link.get("verified_at"):
                    log_test("3b-timestamp", True, "verified_at timestamp set", 
                            f"Verified at: {link.get('verified_at')}")
                else:
                    log_test("3b-timestamp", False, "verified_at timestamp not set", None)
                
                return True
            else:
                log_test("3b", False, "Correct code not accepted", f"verified={verified}")
                return False
        else:
            log_test("3b", False, f"Correct code confirmation failed with status {response.status_code}", 
                    response.text)
            return False
    except Exception as e:
        log_test("3b", False, "Correct code test exception", str(e))
        return False

def test_fetch_report(token):
    """Step 4: FETCH REPORT"""
    print("\n" + "="*80)
    print("STEP 4: FETCH REPORT")
    print("="*80)
    
    # Test 4a: Fetch report (should work after verification)
    try:
        response = requests.get(f"{BACKEND_URL}/api/portal/report/{token}")
        
        if response.status_code == 200:
            data = response.json()
            project = data.get("project")
            view_count = data.get("view_count")
            
            if project and project.get("name") == "Website Redesign":
                log_test("4a", True, "Report fetched successfully", 
                        f"Project: {project.get('name')}, View count: {view_count}")
                
                # Test 4b: Fetch again to verify view count increments
                response2 = requests.get(f"{BACKEND_URL}/api/portal/report/{token}")
                if response2.status_code == 200:
                    data2 = response2.json()
                    view_count2 = data2.get("view_count")
                    
                    if view_count2 > view_count:
                        log_test("4b", True, "View count incremented", 
                                f"First: {view_count}, Second: {view_count2}")
                    else:
                        log_test("4b", False, "View count did not increment", 
                                f"First: {view_count}, Second: {view_count2}")
                else:
                    log_test("4b", False, f"Second fetch failed with status {response2.status_code}", 
                            response2.text)
            else:
                log_test("4a", False, "Report fetch response invalid", 
                        f"Project: {project.get('name') if project else 'None'}")
        else:
            log_test("4a", False, f"Report fetch failed with status {response.status_code}", 
                    response.text)
    except Exception as e:
        log_test("4a", False, "Report fetch exception", str(e))

def test_unverified_access(admin_token):
    """Step 4c: Test access without verification"""
    print("\n" + "="*80)
    print("STEP 4c: TEST UNVERIFIED ACCESS")
    print("="*80)
    
    # Create a second magic link
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/reports/magic-link",
            json={
                "project_id": TEST_PROJECT_ID,
                "recipient_email": "unverified-test@example.com",
                "report_type": "project",
                "report_period": "whole-project"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            token2 = data.get("token")
            
            # Try to fetch report without confirming
            response2 = requests.get(f"{BACKEND_URL}/api/portal/report/{token2}")
            
            if response2.status_code == 403:
                log_test("4c", True, "Unverified access correctly blocked", "Status: 403")
            else:
                log_test("4c", False, f"Unverified access should return 403, got {response2.status_code}", 
                        response2.text)
        else:
            log_test("4c", False, "Could not create second magic link for test", response.text)
    except Exception as e:
        log_test("4c", False, "Unverified access test exception", str(e))

def test_admin_list_revoke(admin_token, token):
    """Step 5: ADMIN LIST/REVOKE"""
    print("\n" + "="*80)
    print("STEP 5: ADMIN LIST AND REVOKE")
    print("="*80)
    
    # Test 5a: List links without auth (should fail)
    try:
        response = requests.get(f"{BACKEND_URL}/api/admin/report-links")
        
        if response.status_code in [401, 403]:
            log_test("5a", True, "List without auth correctly rejected", 
                    f"Status: {response.status_code}")
        else:
            log_test("5a", False, f"List without auth should return 401/403, got {response.status_code}", 
                    response.text)
    except Exception as e:
        log_test("5a", False, "List without auth test exception", str(e))
    
    # Test 5b: List links with admin auth
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/admin/report-links?project_id={TEST_PROJECT_ID}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 200:
            links = response.json()
            
            # Find our created link
            our_link = None
            for link in links:
                if link.get("token") == token:
                    our_link = link
                    break
            
            if our_link:
                log_test("5b", True, "Admin list successful, created link found", 
                        f"Found {len(links)} links for project")
                link_id = our_link.get("id")
                
                # Test 5c: Revoke the link
                if link_id:
                    response2 = requests.delete(
                        f"{BACKEND_URL}/api/admin/report-links/{link_id}",
                        headers={"Authorization": f"Bearer {admin_token}"}
                    )
                    
                    if response2.status_code == 200:
                        log_test("5c", True, "Link revoked successfully", None)
                        
                        # Test 5d: Verify revoked link is blocked
                        response3 = requests.get(f"{BACKEND_URL}/api/portal/verify/{token}")
                        
                        if response3.status_code == 403:
                            log_test("5d", True, "Revoked link correctly blocked", "Status: 403")
                        elif response3.status_code == 200:
                            data = response3.json()
                            # Check if is_active is false in DB
                            client = pymongo.MongoClient(MONGO_URL)
                            db = client[DB_NAME]
                            link = db.report_links.find_one({"token": token})
                            if link and not link.get("is_active", True):
                                log_test("5d", True, "Revoked link has is_active=false", None)
                            else:
                                log_test("5d", False, "Revoked link still active", 
                                        f"is_active={link.get('is_active') if link else 'N/A'}")
                        else:
                            log_test("5d", False, f"Revoked link verification returned unexpected status {response3.status_code}", 
                                    response3.text)
                    else:
                        log_test("5c", False, f"Link revocation failed with status {response2.status_code}", 
                                response2.text)
                else:
                    log_test("5c", False, "Could not get link_id for revocation", None)
            else:
                log_test("5b", False, "Created link not found in admin list", 
                        f"Found {len(links)} links but our token not present")
        else:
            log_test("5b", False, f"Admin list failed with status {response.status_code}", 
                    response.text)
    except Exception as e:
        log_test("5b", False, "Admin list test exception", str(e))

def test_rate_limit(admin_token):
    """Step 6: RATE LIMIT"""
    print("\n" + "="*80)
    print("STEP 6: RATE LIMIT TEST")
    print("="*80)
    
    # Create a fresh link for rate limit testing
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/reports/magic-link",
            json={
                "project_id": TEST_PROJECT_ID,
                "recipient_email": "ratelimit-test@example.com",
                "report_type": "project",
                "report_period": "whole-project"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("token")
            
            # Try wrong code 3 times
            for i in range(3):
                response2 = requests.post(
                    f"{BACKEND_URL}/api/portal/verify/{token}/confirm",
                    json={"verification_code": "000000"}
                )
                print(f"  Attempt {i+1}: Status {response2.status_code}")
            
            # 4th attempt should be rate limited
            response3 = requests.post(
                f"{BACKEND_URL}/api/portal/verify/{token}/confirm",
                json={"verification_code": "000000"}
            )
            
            if response3.status_code == 429:
                log_test("6", True, "Rate limit enforced after 3 attempts", "Status: 429")
            else:
                log_test("6", False, f"Rate limit should return 429, got {response3.status_code}", 
                        response3.text)
        else:
            log_test("6", False, "Could not create link for rate limit test", response.text)
    except Exception as e:
        log_test("6", False, "Rate limit test exception", str(e))

def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for r in test_results if r["passed"])
    total = len(test_results)
    
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {passed/total*100:.1f}%")
    
    # List failed tests
    failed = [r for r in test_results if not r["passed"]]
    if failed:
        print("\n❌ FAILED TESTS:")
        for r in failed:
            print(f"  - Step {r['step']}: {r['message']}")
            if r['details']:
                print(f"    {r['details']}")
    else:
        print("\n✅ ALL TESTS PASSED!")
    
    return passed == total

def main():
    """Run all tests"""
    print("="*80)
    print("DD PLANNER - MAGIC LINK FEATURE TEST")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test Project: {TEST_PROJECT_ID}")
    print(f"Test Time: {datetime.now().isoformat()}")
    
    # Step 0: Admin login
    admin_token = test_admin_login()
    if not admin_token:
        print("\n❌ FATAL: Admin login failed. Cannot continue.")
        sys.exit(1)
    
    # Step 1: Create magic link
    token = test_create_magic_link(admin_token)
    if not token:
        print("\n❌ FATAL: Magic link creation failed. Cannot continue.")
        sys.exit(1)
    
    # Step 2: Verify token
    test_verify_token(token)
    
    # Step 3: Confirm code
    verified = test_confirm_code(token)
    
    # Step 4: Fetch report (only if verified)
    if verified:
        test_fetch_report(token)
        test_unverified_access(admin_token)
    else:
        print("\n⚠️  Skipping report fetch tests due to verification failure")
    
    # Step 5: Admin list/revoke
    test_admin_list_revoke(admin_token, token)
    
    # Step 6: Rate limit
    test_rate_limit(admin_token)
    
    # Print summary
    all_passed = print_summary()
    
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()
