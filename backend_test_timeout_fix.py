#!/usr/bin/env python3
"""
MongoDB Atlas Timeout Fix Verification Test Suite
Bug: 502 errors on Cloud Run cold-start due to aggressive timeouts (3s/5s)
Fix: Raised serverSelectionTimeoutMS to 15000ms, connectTimeoutMS to 10000ms
"""
import requests
import time
import sys
import subprocess

# Backend URL from review request
BASE_URL = "https://a0ac7ee9-2785-4339-ad6f-6886af7a3f1a.preview.emergentagent.com"
API_URL = f"{BASE_URL}/api"

# Test credentials from review request
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"
PLATFORM_EMAIL = "don@ddconsult.tech"
PLATFORM_PASSWORD = "Welcome123!"

# Test results tracking
test_results = []
jwt_token = None
platform_token = None

def log_test(test_num, description, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    result = f"Test {test_num}: {status} - {description}"
    if details:
        result += f"\n    Details: {details}"
    print(result)
    test_results.append({
        "test": test_num,
        "description": description,
        "passed": passed,
        "details": details
    })
    return passed

def test_1_health_check():
    """Test 1: GET /api/health → 200 with status: healthy, database: connected"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=30)
        data = response.json()
        
        passed = (
            response.status_code == 200 and
            data.get("status") == "healthy" and
            data.get("database") == "connected"
        )
        
        details = f"HTTP {response.status_code}, status={data.get('status')}, database={data.get('database')}"
        return log_test(1, "GET /api/health", passed, details)
    except Exception as e:
        return log_test(1, "GET /api/health", False, f"Exception: {str(e)}")

def test_2_tenant_login():
    """Test 2: POST /api/auth/login (admin@test.com/admin123) → 200 with JWT"""
    global jwt_token
    try:
        response = requests.post(
            f"{API_URL}/auth/login",
            data={
                "username": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            jwt_token = data.get("access_token")
            passed = jwt_token is not None
            details = f"HTTP {response.status_code}, JWT token received: {jwt_token[:20]}..." if jwt_token else "No token"
        else:
            passed = False
            details = f"HTTP {response.status_code}, Response: {response.text[:200]}"
        
        return log_test(2, "POST /api/auth/login (tenant admin)", passed, details)
    except Exception as e:
        return log_test(2, "POST /api/auth/login (tenant admin)", False, f"Exception: {str(e)}")

def test_3_auth_me():
    """Test 3: GET /api/auth/me with JWT → 200"""
    if not jwt_token:
        return log_test(3, "GET /api/auth/me", False, "No JWT token from test 2")
    
    try:
        response = requests.get(
            f"{API_URL}/auth/me",
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=30
        )
        
        passed = response.status_code == 200
        if passed:
            data = response.json()
            details = f"HTTP {response.status_code}, User: {data.get('email')}, Role: {data.get('role')}"
        else:
            details = f"HTTP {response.status_code}, Response: {response.text[:200]}"
        
        return log_test(3, "GET /api/auth/me", passed, details)
    except Exception as e:
        return log_test(3, "GET /api/auth/me", False, f"Exception: {str(e)}")

def test_4_projects():
    """Test 4: GET /api/projects with JWT → 200, exactly 4 projects"""
    if not jwt_token:
        return log_test(4, "GET /api/projects", False, "No JWT token from test 2")
    
    try:
        response = requests.get(
            f"{API_URL}/projects",
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            project_count = len(data) if isinstance(data, list) else 0
            passed = project_count == 4
            details = f"HTTP {response.status_code}, Projects count: {project_count} (expected 4)"
        else:
            passed = False
            details = f"HTTP {response.status_code}, Response: {response.text[:200]}"
        
        return log_test(4, "GET /api/projects", passed, details)
    except Exception as e:
        return log_test(4, "GET /api/projects", False, f"Exception: {str(e)}")

def test_5_tenant_modules():
    """Test 5: GET /api/tenant/modules → 200, 17 modules"""
    if not jwt_token:
        return log_test(5, "GET /api/tenant/modules", False, "No JWT token from test 2")
    
    try:
        response = requests.get(
            f"{API_URL}/tenant/modules",
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            modules = data.get("modules", {})
            module_count = len(modules)
            passed = module_count == 17
            details = f"HTTP {response.status_code}, Modules count: {module_count} (expected 17)"
        else:
            passed = False
            details = f"HTTP {response.status_code}, Response: {response.text[:200]}"
        
        return log_test(5, "GET /api/tenant/modules", passed, details)
    except Exception as e:
        return log_test(5, "GET /api/tenant/modules", False, f"Exception: {str(e)}")

def test_6_platform_status():
    """Test 6: GET /api/platform/status (no auth) → 200, platform_db_ready: true"""
    try:
        response = requests.get(f"{API_URL}/platform/status", timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            platform_db_ready = data.get("platform_db_ready")
            passed = platform_db_ready is True
            details = f"HTTP {response.status_code}, platform_db_ready={platform_db_ready}, multi_tenant_enabled={data.get('multi_tenant_enabled')}"
        else:
            passed = False
            details = f"HTTP {response.status_code}, Response: {response.text[:200]}"
        
        return log_test(6, "GET /api/platform/status", passed, details)
    except Exception as e:
        return log_test(6, "GET /api/platform/status", False, f"Exception: {str(e)}")

def test_7_platform_login():
    """Test 7: POST /api/platform/auth/login (don@ddconsult.tech/Welcome123!) → 200"""
    global platform_token
    try:
        response = requests.post(
            f"{API_URL}/platform/auth/login",
            data={
                "username": PLATFORM_EMAIL,
                "password": PLATFORM_PASSWORD
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            platform_token = data.get("access_token")
            passed = platform_token is not None
            details = f"HTTP {response.status_code}, Platform token received: {platform_token[:20]}..." if platform_token else "No token"
        else:
            passed = False
            details = f"HTTP {response.status_code}, Response: {response.text[:200]}"
        
        return log_test(7, "POST /api/platform/auth/login", passed, details)
    except Exception as e:
        return log_test(7, "POST /api/platform/auth/login", False, f"Exception: {str(e)}")

def test_8_verify_database_py_timeout():
    """Test 8: Verify /app/backend/database.py has serverSelectionTimeoutMS=15000"""
    try:
        with open("/app/backend/database.py", "r") as f:
            content = f.read()
        
        has_15000 = "serverSelectionTimeoutMS=15000" in content
        has_10000 = "connectTimeoutMS=10000" in content
        passed = has_15000 and has_10000
        
        details = f"serverSelectionTimeoutMS=15000: {has_15000}, connectTimeoutMS=10000: {has_10000}"
        return log_test(8, "Verify database.py timeout code", passed, details)
    except Exception as e:
        return log_test(8, "Verify database.py timeout code", False, f"Exception: {str(e)}")

def test_9_verify_platform_db_py_timeout():
    """Test 9: Verify /app/backend/platform_db.py has serverSelectionTimeoutMS=15000"""
    try:
        with open("/app/backend/platform_db.py", "r") as f:
            content = f.read()
        
        has_15000 = "serverSelectionTimeoutMS=15000" in content
        has_10000 = "connectTimeoutMS=10000" in content
        passed = has_15000 and has_10000
        
        details = f"serverSelectionTimeoutMS=15000: {has_15000}, connectTimeoutMS=10000: {has_10000}"
        return log_test(9, "Verify platform_db.py timeout code", passed, details)
    except Exception as e:
        return log_test(9, "Verify platform_db.py timeout code", False, f"Exception: {str(e)}")

def test_10_restart_backend():
    """Test 10: Restart backend and wait 8 seconds"""
    try:
        print("\n🔄 Restarting backend service...")
        result = subprocess.run(
            ["sudo", "supervisorctl", "-c", "/etc/supervisor/supervisord.conf", "restart", "backend"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print(f"Restart output: {result.stdout}")
        if result.stderr:
            print(f"Restart stderr: {result.stderr}")
        
        print("⏳ Waiting 8 seconds for backend to initialize...")
        time.sleep(8)
        
        passed = result.returncode == 0
        details = f"Exit code: {result.returncode}, Output: {result.stdout.strip()}"
        return log_test(10, "Restart backend service", passed, details)
    except Exception as e:
        return log_test(10, "Restart backend service", False, f"Exception: {str(e)}")

def test_11_health_after_restart():
    """Test 11: GET /api/health after restart → 200 (not 503, not 502)"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=30)
        data = response.json()
        
        passed = (
            response.status_code == 200 and
            data.get("status") == "healthy" and
            data.get("database") == "connected"
        )
        
        details = f"HTTP {response.status_code}, status={data.get('status')}, database={data.get('database')}"
        
        if response.status_code in [502, 503]:
            details += " ❌ CRITICAL: Got 502/503 error after restart!"
        
        return log_test(11, "GET /api/health after restart", passed, details)
    except Exception as e:
        return log_test(11, "GET /api/health after restart", False, f"Exception: {str(e)}")

def test_12_login_after_restart():
    """Test 12: POST /api/auth/login after restart → 200 (not 502)"""
    try:
        response = requests.post(
            f"{API_URL}/auth/login",
            data={
                "username": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD
            },
            timeout=30
        )
        
        passed = response.status_code == 200
        
        if passed:
            data = response.json()
            token = data.get("access_token")
            details = f"HTTP {response.status_code}, JWT token received: {token[:20]}..." if token else "No token"
        else:
            details = f"HTTP {response.status_code}, Response: {response.text[:200]}"
        
        if response.status_code == 502:
            details += " ❌ CRITICAL: Got 502 error after restart!"
        
        return log_test(12, "POST /api/auth/login after restart", passed, details)
    except Exception as e:
        return log_test(12, "POST /api/auth/login after restart", False, f"Exception: {str(e)}")

def check_backend_logs():
    """Check backend logs for startup messages"""
    print("\n📋 Checking backend logs for startup messages...")
    try:
        result = subprocess.run(
            ["tail", "-n", "100", "/var/log/supervisor/backend.err.log"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        logs = result.stdout
        
        # Look for key startup messages
        has_startup_bg = "[STARTUP-BG] Platform DB" in logs
        has_ready = "Application marked READY" in logs
        has_timeout_error = "Timeout:" in logs or "No replica set members found" in logs
        
        print(f"  [STARTUP-BG] Platform DB message: {'✅ Found' if has_startup_bg else '❌ Not found'}")
        print(f"  Application marked READY message: {'✅ Found' if has_ready else '❌ Not found'}")
        print(f"  Timeout errors: {'❌ Found (BAD)' if has_timeout_error else '✅ None (GOOD)'}")
        
        if has_timeout_error:
            print("\n⚠️  WARNING: Timeout errors found in logs:")
            for line in logs.split("\n"):
                if "Timeout:" in line or "No replica set members found" in line:
                    print(f"    {line}")
        
        return not has_timeout_error
        
    except Exception as e:
        print(f"  ❌ Error checking logs: {str(e)}")
        return False

def main():
    print("=" * 80)
    print("MongoDB Atlas Timeout Fix Verification Test Suite")
    print("=" * 80)
    print(f"Backend URL: {BASE_URL}")
    print(f"Feature flag: MULTI_TENANT_ENABLED=false")
    print(f"Test credentials: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print("=" * 80)
    print()
    
    # Run all tests
    test_1_health_check()
    test_2_tenant_login()
    test_3_auth_me()
    test_4_projects()
    test_5_tenant_modules()
    test_6_platform_status()
    test_7_platform_login()
    test_8_verify_database_py_timeout()
    test_9_verify_platform_db_py_timeout()
    test_10_restart_backend()
    test_11_health_after_restart()
    test_12_login_after_restart()
    
    # Check logs
    logs_ok = check_backend_logs()
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed_count = sum(1 for r in test_results if r["passed"])
    total_count = len(test_results)
    
    print(f"Tests passed: {passed_count}/{total_count}")
    print()
    
    # Show failed tests
    failed_tests = [r for r in test_results if not r["passed"]]
    if failed_tests:
        print("❌ FAILED TESTS:")
        for r in failed_tests:
            print(f"  Test {r['test']}: {r['description']}")
            if r['details']:
                print(f"    {r['details']}")
        print()
    
    # Final verdict
    all_passed = passed_count == total_count and logs_ok
    
    print("=" * 80)
    if all_passed:
        print("✅ TIMEOUT FIX VERDICT: PASS")
        print("   - All 12 tests passed")
        print("   - No 502 errors detected")
        print("   - Timeout code verified in both database.py and platform_db.py")
        print("   - Backend startup successful after restart")
        print("   - No timeout errors in logs")
    else:
        print("❌ TIMEOUT FIX VERDICT: FAIL")
        if failed_tests:
            print(f"   - {len(failed_tests)} test(s) failed")
        if not logs_ok:
            print("   - Timeout errors found in backend logs")
    print("=" * 80)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
