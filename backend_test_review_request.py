#!/usr/bin/env python3
"""
Backend Testing Script - Review Request Verification
Tests the following:
1. GET /api/health returns HTTP 200
2. Authenticate with admin@test.com / admin123
3. Test GET /api/projects/6aabd45b6023b8429321ad6c/export/pdf returns HTTP 200 with valid PDF
4. Verify POST /api/ai/chat returns HTTP 200 with AI response
"""

import requests
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8001"
PROJECT_ID = "6aabd45b6023b8429321ad6c"
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "admin123"

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def log_test(test_name, status, details=""):
    """Log test result with color coding"""
    color = GREEN if status == "PASS" else RED
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {color}{status}{RESET} - {test_name}")
    if details:
        print(f"         {details}")

def test_health_endpoint():
    """Test 1: Verify GET /api/health returns HTTP 200"""
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "unknown")
            database = data.get("database", "unknown")
            api = data.get("api", "unknown")
            
            log_test(
                "GET /api/health",
                "PASS",
                f"Status: {status}, Database: {database}, API: {api}"
            )
            return True, data
        else:
            log_test(
                "GET /api/health",
                "FAIL",
                f"Expected 200, got {response.status_code}: {response.text[:200]}"
            )
            return False, None
    except Exception as e:
        log_test("GET /api/health", "FAIL", f"Exception: {str(e)}")
        return False, None

def test_authentication():
    """Test 2: Authenticate with admin@test.com / admin123"""
    try:
        # FastAPI uses OAuth2PasswordRequestForm which expects form-encoded data
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={
                "username": TEST_EMAIL,
                "password": TEST_PASSWORD
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            user_email = data.get("user", {}).get("email", "unknown")
            user_role = data.get("user", {}).get("role", "unknown")
            
            if token:
                log_test(
                    "POST /api/auth/login",
                    "PASS",
                    f"User: {user_email}, Role: {user_role}, Token: {token[:20]}..."
                )
                return True, token
            else:
                log_test(
                    "POST /api/auth/login",
                    "FAIL",
                    "No access_token in response"
                )
                return False, None
        else:
            log_test(
                "POST /api/auth/login",
                "FAIL",
                f"Expected 200, got {response.status_code}: {response.text[:200]}"
            )
            return False, None
    except Exception as e:
        log_test("POST /api/auth/login", "FAIL", f"Exception: {str(e)}")
        return False, None

def test_pdf_export(token):
    """Test 3: Test GET /api/projects/{project_id}/export/pdf returns HTTP 200 with valid PDF"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/export/pdf",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60  # PDF generation can take time
        )
        
        if response.status_code == 200:
            # Check Content-Type
            content_type = response.headers.get("Content-Type", "")
            content_length = len(response.content)
            content_disposition = response.headers.get("Content-Disposition", "")
            
            # Verify PDF magic bytes
            is_valid_pdf = response.content[:4] == b'%PDF'
            
            if is_valid_pdf:
                log_test(
                    f"GET /api/projects/{PROJECT_ID}/export/pdf",
                    "PASS",
                    f"Content-Type: {content_type}, Size: {content_length / 1024:.1f} KB, Valid PDF: {is_valid_pdf}"
                )
                
                # Save PDF for verification
                pdf_path = f"/tmp/test_export_pdf_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                with open(pdf_path, "wb") as f:
                    f.write(response.content)
                print(f"         PDF saved to: {pdf_path}")
                
                return True, response.content
            else:
                log_test(
                    f"GET /api/projects/{PROJECT_ID}/export/pdf",
                    "FAIL",
                    f"Invalid PDF magic bytes: {response.content[:10]}"
                )
                return False, None
        else:
            log_test(
                f"GET /api/projects/{PROJECT_ID}/export/pdf",
                "FAIL",
                f"Expected 200, got {response.status_code}: {response.text[:200]}"
            )
            return False, None
    except Exception as e:
        log_test(f"GET /api/projects/{PROJECT_ID}/export/pdf", "FAIL", f"Exception: {str(e)}")
        return False, None

def test_ai_chat(token):
    """Test 4: Verify POST /api/ai/chat returns HTTP 200 with AI response"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/ai/chat",
            json={
                "message": "What projects are currently active?",
                "session_id": None
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            ai_response = data.get("response", "")
            session_id = data.get("session_id", "")
            
            if ai_response:
                # Truncate long responses for display
                display_response = ai_response[:150] + "..." if len(ai_response) > 150 else ai_response
                log_test(
                    "POST /api/ai/chat",
                    "PASS",
                    f"Session: {session_id[:20]}..., Response: {display_response}"
                )
                return True, data
            else:
                log_test(
                    "POST /api/ai/chat",
                    "FAIL",
                    "No AI response in response body"
                )
                return False, None
        else:
            log_test(
                "POST /api/ai/chat",
                "FAIL",
                f"Expected 200, got {response.status_code}: {response.text[:200]}"
            )
            return False, None
    except Exception as e:
        log_test("POST /api/ai/chat", "FAIL", f"Exception: {str(e)}")
        return False, None

def main():
    """Run all tests"""
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}Backend Testing - Review Request Verification{RESET}")
    print(f"{BLUE}Base URL: {BASE_URL}{RESET}")
    print(f"{BLUE}Project ID: {PROJECT_ID}{RESET}")
    print(f"{BLUE}Test Credentials: {TEST_EMAIL} / {TEST_PASSWORD}{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")
    
    results = {
        "total": 4,
        "passed": 0,
        "failed": 0
    }
    
    # Test 1: Health Check
    print(f"{YELLOW}Test 1: Health Check{RESET}")
    success, _ = test_health_endpoint()
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
    print()
    
    # Test 2: Authentication
    print(f"{YELLOW}Test 2: Authentication{RESET}")
    success, token = test_authentication()
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
        print(f"\n{RED}Authentication failed. Cannot proceed with remaining tests.{RESET}\n")
        print_summary(results)
        return 1
    print()
    
    # Test 3: PDF Export
    print(f"{YELLOW}Test 3: PDF Export{RESET}")
    success, _ = test_pdf_export(token)
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
    print()
    
    # Test 4: AI Chat
    print(f"{YELLOW}Test 4: AI Chat{RESET}")
    success, _ = test_ai_chat(token)
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
    print()
    
    # Print summary
    print_summary(results)
    
    return 0 if results["failed"] == 0 else 1

def print_summary(results):
    """Print test summary"""
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}Test Summary{RESET}")
    print(f"{BLUE}{'='*80}{RESET}")
    print(f"Total Tests: {results['total']}")
    print(f"{GREEN}Passed: {results['passed']}{RESET}")
    print(f"{RED}Failed: {results['failed']}{RESET}")
    
    if results["failed"] == 0:
        print(f"\n{GREEN}✅ ALL TESTS PASSED{RESET}\n")
    else:
        print(f"\n{RED}❌ SOME TESTS FAILED{RESET}\n")

if __name__ == "__main__":
    sys.exit(main())
