#!/usr/bin/env python3
"""
Cold-Start Fix Verification Test Suite
Tests the non-blocking startup fix for GCP Cloud Run 502 issue.
"""
import requests
import time
import subprocess
import sys
from datetime import datetime

# Backend URL from environment
BACKEND_URL = "https://base-product-check.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"
PLATFORM_EMAIL = "don@ddconsult.tech"
PLATFORM_PASSWORD = "Welcome123!"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def log(message, color=Colors.BLUE):
    print(f"{color}{message}{Colors.RESET}")

def test_result(test_name, passed, details=""):
    if passed:
        log(f"✅ TEST {test_name}: PASSED {details}", Colors.GREEN)
    else:
        log(f"❌ TEST {test_name}: FAILED {details}", Colors.RED)
    return passed

def restart_backend():
    """Restart the backend service using supervisorctl."""
    log("\n🔄 Restarting backend service...", Colors.YELLOW)
    try:
        result = subprocess.run(
            ["sudo", "supervisorctl", "-c", "/etc/supervisor/supervisord.conf", "restart", "backend"],
            capture_output=True,
            text=True,
            timeout=10
        )
        log(f"Restart command output: {result.stdout.strip()}")
        if result.returncode != 0:
            log(f"Restart stderr: {result.stderr.strip()}", Colors.RED)
            return False
        return True
    except Exception as e:
        log(f"Failed to restart backend: {e}", Colors.RED)
        return False

def check_health_endpoint(endpoint="/api/health", max_wait_seconds=2):
    """Check health endpoint and measure response time."""
    url = f"{BACKEND_URL}{endpoint}"
    start_time = time.time()
    
    try:
        response = requests.get(url, timeout=max_wait_seconds)
        elapsed = time.time() - start_time
        
        return {
            "success": True,
            "status_code": response.status_code,
            "elapsed_ms": int(elapsed * 1000),
            "response": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
            "error": None
        }
    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        return {
            "success": False,
            "status_code": None,
            "elapsed_ms": int(elapsed * 1000),
            "response": None,
            "error": "TIMEOUT"
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "success": False,
            "status_code": None,
            "elapsed_ms": int(elapsed * 1000),
            "response": None,
            "error": str(e)
        }

def test_immediate_login(max_wait_seconds=3):
    """Test login within 3 seconds of restart."""
    url = f"{API_BASE}/auth/login"
    start_time = time.time()
    
    try:
        response = requests.post(
            url,
            data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=max_wait_seconds
        )
        elapsed = time.time() - start_time
        
        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "elapsed_ms": int(elapsed * 1000),
            "has_token": "access_token" in response.json() if response.status_code == 200 else False,
            "error": None
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "success": False,
            "status_code": None,
            "elapsed_ms": int(elapsed * 1000),
            "has_token": False,
            "error": str(e)
        }

def get_auth_token():
    """Get authentication token for regression tests."""
    url = f"{API_BASE}/auth/login"
    try:
        response = requests.post(
            url,
            data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get("access_token")
    except Exception as e:
        log(f"Failed to get auth token: {e}", Colors.RED)
    return None

def check_backend_logs():
    """Check backend logs for startup messages."""
    log("\n📋 Checking backend logs for startup messages...", Colors.BLUE)
    try:
        result = subprocess.run(
            ["tail", "-n", "100", "/var/log/supervisor/backend.err.log"],
            capture_output=True,
            text=True,
            timeout=5
        )
        logs = result.stdout
        
        checks = {
            "ready_message": "Application marked READY — uvicorn will start serving now" in logs,
            "indexes_created": "[STARTUP-BG] Database indexes created successfully" in logs,
            "platform_initialized": "[STARTUP-BG] Platform DB already initialized" in logs or "[STARTUP-BG] Platform DB seeded" in logs,
            "full_init_complete": "[STARTUP-BG] Full initialisation complete" in logs,
        }
        
        return checks, logs
    except Exception as e:
        log(f"Failed to check logs: {e}", Colors.RED)
        return {}, ""

def run_regression_tests(token):
    """Run standard regression tests."""
    log("\n🔍 Running regression tests...", Colors.BLUE)
    headers = {"Authorization": f"Bearer {token}"}
    results = {}
    
    # Test 1: GET /api/projects
    try:
        response = requests.get(f"{API_BASE}/projects", headers=headers, timeout=10)
        project_count = len(response.json()) if response.status_code == 200 else 0
        results["projects"] = {
            "passed": response.status_code == 200 and project_count == 4,
            "status_code": response.status_code,
            "count": project_count,
            "expected": 4
        }
    except Exception as e:
        results["projects"] = {"passed": False, "error": str(e)}
    
    # Test 2: GET /api/resources
    try:
        response = requests.get(f"{API_BASE}/resources", headers=headers, timeout=10)
        resource_count = len(response.json()) if response.status_code == 200 else 0
        results["resources"] = {
            "passed": response.status_code == 200 and resource_count == 5,
            "status_code": response.status_code,
            "count": resource_count,
            "expected": 5
        }
    except Exception as e:
        results["resources"] = {"passed": False, "error": str(e)}
    
    # Test 3: GET /api/allocations
    try:
        response = requests.get(f"{API_BASE}/allocations", headers=headers, timeout=10)
        allocation_count = len(response.json()) if response.status_code == 200 else 0
        results["allocations"] = {
            "passed": response.status_code == 200 and allocation_count == 10,
            "status_code": response.status_code,
            "count": allocation_count,
            "expected": 10
        }
    except Exception as e:
        results["allocations"] = {"passed": False, "error": str(e)}
    
    # Test 4: GET /api/tenant/modules
    try:
        response = requests.get(f"{API_BASE}/tenant/modules", headers=headers, timeout=10)
        module_count = len(response.json().get("modules", {})) if response.status_code == 200 else 0
        results["modules"] = {
            "passed": response.status_code == 200 and module_count == 17,
            "status_code": response.status_code,
            "count": module_count,
            "expected": 17
        }
    except Exception as e:
        results["modules"] = {"passed": False, "error": str(e)}
    
    # Test 5: POST /api/platform/auth/login
    try:
        response = requests.post(
            f"{API_BASE}/platform/auth/login",
            data={"username": PLATFORM_EMAIL, "password": PLATFORM_PASSWORD},
            timeout=10
        )
        results["platform_login"] = {
            "passed": response.status_code == 200,
            "status_code": response.status_code,
            "has_token": "access_token" in response.json() if response.status_code == 200 else False
        }
    except Exception as e:
        results["platform_login"] = {"passed": False, "error": str(e)}
    
    # Test 6: GET /api/platform/status
    try:
        response = requests.get(f"{API_BASE}/platform/status", timeout=10)
        data = response.json() if response.status_code == 200 else {}
        results["platform_status"] = {
            "passed": response.status_code == 200 and data.get("platform_db_ready") == True,
            "status_code": response.status_code,
            "platform_db_ready": data.get("platform_db_ready")
        }
    except Exception as e:
        results["platform_status"] = {"passed": False, "error": str(e)}
    
    return results

def main():
    log("=" * 80, Colors.BLUE)
    log("COLD-START FIX VERIFICATION TEST SUITE", Colors.BLUE)
    log("=" * 80, Colors.BLUE)
    log(f"Backend URL: {BACKEND_URL}")
    log(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_tests_passed = True
    
    # ========================================================================
    # TEST 1: Cold-start behavior - restart and hit /api/health within 2 seconds
    # ========================================================================
    log("\n" + "=" * 80, Colors.YELLOW)
    log("TEST 1: Cold-start behavior (restart + /api/health within 2 seconds)", Colors.YELLOW)
    log("=" * 80, Colors.YELLOW)
    
    if not restart_backend():
        log("❌ Failed to restart backend, cannot continue with cold-start tests", Colors.RED)
        return 1
    
    # Wait 1 second for supervisor to start the process
    time.sleep(1)
    
    # Hit /api/health within 2 seconds
    result = check_health_endpoint("/api/health", max_wait_seconds=2)
    
    test_1_passed = (
        result["success"] and 
        result["status_code"] == 200 and
        result["elapsed_ms"] < 2000
    )
    
    log(f"Status Code: {result['status_code']}")
    log(f"Response Time: {result['elapsed_ms']}ms")
    log(f"Response: {result['response']}")
    
    if result["error"]:
        log(f"Error: {result['error']}", Colors.RED)
    
    all_tests_passed &= test_result("1", test_1_passed, 
        f"(HTTP {result['status_code']}, {result['elapsed_ms']}ms)")
    
    # ========================================================================
    # TEST 2: Immediate login within 3 seconds of restart
    # ========================================================================
    log("\n" + "=" * 80, Colors.YELLOW)
    log("TEST 2: Immediate login (within 3 seconds of restart)", Colors.YELLOW)
    log("=" * 80, Colors.YELLOW)
    
    if not restart_backend():
        log("❌ Failed to restart backend for test 2", Colors.RED)
        all_tests_passed = False
    else:
        time.sleep(1)
        
        result = test_immediate_login(max_wait_seconds=3)
        
        test_2_passed = (
            result["success"] and 
            result["status_code"] == 200 and
            result["has_token"] and
            result["elapsed_ms"] < 3000
        )
        
        log(f"Status Code: {result['status_code']}")
        log(f"Response Time: {result['elapsed_ms']}ms")
        log(f"Has JWT Token: {result['has_token']}")
        
        if result["error"]:
            log(f"Error: {result['error']}", Colors.RED)
        
        all_tests_passed &= test_result("2", test_2_passed,
            f"(HTTP {result['status_code']}, {result['elapsed_ms']}ms, token={result['has_token']})")
    
    # ========================================================================
    # TEST 3: Repeat health check 5 times with 1-second gap
    # ========================================================================
    log("\n" + "=" * 80, Colors.YELLOW)
    log("TEST 3: Repeat health check 5 times (1-second gap)", Colors.YELLOW)
    log("=" * 80, Colors.YELLOW)
    
    if not restart_backend():
        log("❌ Failed to restart backend for test 3", Colors.RED)
        all_tests_passed = False
    else:
        time.sleep(1)
        
        test_3_results = []
        for i in range(5):
            result = check_health_endpoint("/api/health", max_wait_seconds=2)
            test_3_results.append(result)
            
            log(f"Attempt {i+1}/5: HTTP {result['status_code']}, {result['elapsed_ms']}ms")
            
            if i < 4:  # Don't sleep after the last attempt
                time.sleep(1)
        
        test_3_passed = all(
            r["success"] and r["status_code"] == 200 and r["elapsed_ms"] < 100
            for r in test_3_results
        )
        
        avg_response_time = sum(r["elapsed_ms"] for r in test_3_results) / len(test_3_results)
        log(f"Average response time: {int(avg_response_time)}ms")
        
        all_tests_passed &= test_result("3", test_3_passed,
            f"(5/5 returned HTTP 200 in <100ms, avg={int(avg_response_time)}ms)")
    
    # ========================================================================
    # TEST 4: Verify background init logs after 15 seconds
    # ========================================================================
    log("\n" + "=" * 80, Colors.YELLOW)
    log("TEST 4: Verify background initialization (wait 15 seconds)", Colors.YELLOW)
    log("=" * 80, Colors.YELLOW)
    
    log("Waiting 15 seconds for background initialization to complete...")
    time.sleep(15)
    
    log_checks, logs = check_backend_logs()
    
    log("\nLog checks:")
    for check_name, found in log_checks.items():
        status = "✅" if found else "❌"
        log(f"{status} {check_name}: {found}")
    
    test_4_passed = all(log_checks.values())
    all_tests_passed &= test_result("4", test_4_passed,
        f"({sum(log_checks.values())}/{len(log_checks)} startup messages found)")
    
    # ========================================================================
    # TEST 5: Standard regression tests
    # ========================================================================
    log("\n" + "=" * 80, Colors.YELLOW)
    log("TEST 5: Standard regression tests", Colors.YELLOW)
    log("=" * 80, Colors.YELLOW)
    
    token = get_auth_token()
    if not token:
        log("❌ Failed to get auth token for regression tests", Colors.RED)
        all_tests_passed = False
    else:
        regression_results = run_regression_tests(token)
        
        for test_name, result in regression_results.items():
            if result.get("passed"):
                if "count" in result:
                    log(f"✅ {test_name}: {result['count']}/{result['expected']}", Colors.GREEN)
                else:
                    log(f"✅ {test_name}: PASSED", Colors.GREEN)
            else:
                log(f"❌ {test_name}: FAILED - {result.get('error', 'unexpected result')}", Colors.RED)
                all_tests_passed = False
        
        test_5_passed = all(r.get("passed", False) for r in regression_results.values())
        all_tests_passed &= test_result("5", test_5_passed,
            f"({sum(1 for r in regression_results.values() if r.get('passed'))}/{len(regression_results)} regression tests passed)")
    
    # ========================================================================
    # TEST 6: Verify code changes with grep
    # ========================================================================
    log("\n" + "=" * 80, Colors.YELLOW)
    log("TEST 6: Verify code changes in server.py", Colors.YELLOW)
    log("=" * 80, Colors.YELLOW)
    
    code_checks = {}
    
    # Check for _app_ready = True before asyncio.create_task
    try:
        result = subprocess.run(
            ["grep", "-n", "_app_ready = True", "/app/backend/server.py"],
            capture_output=True,
            text=True,
            timeout=5
        )
        code_checks["app_ready_flag"] = result.returncode == 0
        if result.returncode == 0:
            log(f"✅ Found '_app_ready = True' at line: {result.stdout.strip()}", Colors.GREEN)
    except Exception as e:
        code_checks["app_ready_flag"] = False
        log(f"❌ Failed to check _app_ready flag: {e}", Colors.RED)
    
    # Check for _full_startup_init function
    try:
        result = subprocess.run(
            ["grep", "-n", "def _full_startup_init", "/app/backend/server.py"],
            capture_output=True,
            text=True,
            timeout=5
        )
        code_checks["full_startup_init"] = result.returncode == 0
        if result.returncode == 0:
            log(f"✅ Found '_full_startup_init' function at line: {result.stdout.strip()}", Colors.GREEN)
    except Exception as e:
        code_checks["full_startup_init"] = False
        log(f"❌ Failed to check _full_startup_init: {e}", Colors.RED)
    
    # Check for "uvicorn will start serving now" message
    try:
        result = subprocess.run(
            ["grep", "-n", "uvicorn will start serving now", "/app/backend/server.py"],
            capture_output=True,
            text=True,
            timeout=5
        )
        code_checks["serving_message"] = result.returncode == 0
        if result.returncode == 0:
            log(f"✅ Found 'uvicorn will start serving now' at line: {result.stdout.strip()}", Colors.GREEN)
    except Exception as e:
        code_checks["serving_message"] = False
        log(f"❌ Failed to check serving message: {e}", Colors.RED)
    
    test_6_passed = all(code_checks.values())
    all_tests_passed &= test_result("6", test_6_passed,
        f"({sum(code_checks.values())}/{len(code_checks)} code patterns found)")
    
    # ========================================================================
    # TEST 7: Check for errors in logs
    # ========================================================================
    log("\n" + "=" * 80, Colors.YELLOW)
    log("TEST 7: Check for errors in backend logs", Colors.YELLOW)
    log("=" * 80, Colors.YELLOW)
    
    try:
        result = subprocess.run(
            ["tail", "-n", "200", "/var/log/supervisor/backend.err.log"],
            capture_output=True,
            text=True,
            timeout=5
        )
        logs = result.stdout
        
        error_patterns = ["AttributeError", "TypeError", "Traceback"]
        errors_found = []
        
        for pattern in error_patterns:
            if pattern in logs:
                errors_found.append(pattern)
        
        if errors_found:
            log(f"⚠️ Found error patterns in logs: {', '.join(errors_found)}", Colors.YELLOW)
            # Show last 20 lines of logs
            log("\nLast 20 lines of backend logs:", Colors.YELLOW)
            log_lines = logs.split('\n')
            for line in log_lines[-20:]:
                log(line, Colors.YELLOW)
        else:
            log("✅ No critical errors found in logs", Colors.GREEN)
        
        test_7_passed = len(errors_found) == 0
        all_tests_passed &= test_result("7", test_7_passed,
            f"({len(errors_found)} error patterns found)")
    except Exception as e:
        log(f"❌ Failed to check logs: {e}", Colors.RED)
        all_tests_passed = False
    
    # ========================================================================
    # FINAL VERDICT
    # ========================================================================
    log("\n" + "=" * 80, Colors.BLUE)
    log("FINAL VERDICT", Colors.BLUE)
    log("=" * 80, Colors.BLUE)
    
    if all_tests_passed:
        log("✅ COLD-START FIX VERDICT: PASS", Colors.GREEN)
        log("All tests passed successfully. The non-blocking startup fix is working correctly.", Colors.GREEN)
        return 0
    else:
        log("❌ COLD-START FIX VERDICT: FAIL", Colors.RED)
        log("Some tests failed. Please review the results above.", Colors.RED)
        return 1

if __name__ == "__main__":
    sys.exit(main())
