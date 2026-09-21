#!/usr/bin/env python3
"""
Cloud Run Deployment Configuration and Export Service Verification
Tests the following:
1. cloudbuild.yaml configuration (service name, memory, cpu, min-instances)
2. renderer.py isolated context lifecycle and safe Chromium args
3. Export PDF endpoint with specific project ID
4. Export PPT endpoint with specific project ID
5. Health endpoint
"""
import requests
import yaml
import re
import sys
from pathlib import Path

# Test configuration
BASE_URL = "http://localhost:8001"
PROJECT_ID = "6aabd45b6023b8429321ad6c"
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "admin123"

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_test(msg):
    print(f"{BLUE}[TEST]{RESET} {msg}")

def print_pass(msg):
    print(f"{GREEN}✅ PASS:{RESET} {msg}")

def print_fail(msg):
    print(f"{RED}❌ FAIL:{RESET} {msg}")

def print_info(msg):
    print(f"{YELLOW}ℹ INFO:{RESET} {msg}")

def login():
    """Login and get JWT token"""
    print_test("Logging in to get JWT token...")
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code == 200:
        token = response.json().get("access_token")
        print_pass(f"Login successful, token obtained")
        return token
    else:
        print_fail(f"Login failed: {response.status_code} - {response.text}")
        return None

def verify_cloudbuild_yaml():
    """Verify cloudbuild.yaml has correct Cloud Run configuration"""
    print_test("Verifying cloudbuild.yaml configuration...")
    
    cloudbuild_path = Path("/app/cloudbuild.yaml")
    if not cloudbuild_path.exists():
        print_fail("cloudbuild.yaml not found")
        return False
    
    with open(cloudbuild_path, 'r') as f:
        content = f.read()
    
    try:
        config = yaml.safe_load(content)
    except Exception as e:
        print_fail(f"Failed to parse cloudbuild.yaml: {e}")
        return False
    
    # Find the deploy step
    deploy_step = None
    for step in config.get('steps', []):
        if step.get('entrypoint') == 'gcloud' and 'deploy' in step.get('args', []):
            deploy_step = step
            break
    
    if not deploy_step:
        print_fail("Deploy step not found in cloudbuild.yaml")
        return False
    
    args = deploy_step.get('args', [])
    
    # Check service name
    try:
        service_idx = args.index('ddplan')
        print_pass(f"Service name: 'ddplan' ✅")
    except ValueError:
        print_fail("Service name 'ddplan' not found in deploy args")
        return False
    
    # Check memory
    try:
        memory_idx = args.index('--memory')
        memory_value = args[memory_idx + 1]
        if memory_value == '2Gi':
            print_pass(f"Memory: {memory_value} ✅")
        else:
            print_fail(f"Memory is {memory_value}, expected 2Gi")
            return False
    except (ValueError, IndexError):
        print_fail("--memory flag not found or invalid")
        return False
    
    # Check CPU
    try:
        cpu_idx = args.index('--cpu')
        cpu_value = args[cpu_idx + 1]
        if cpu_value == '2':
            print_pass(f"CPU: {cpu_value} ✅")
        else:
            print_fail(f"CPU is {cpu_value}, expected 2")
            return False
    except (ValueError, IndexError):
        print_fail("--cpu flag not found or invalid")
        return False
    
    # Check min-instances
    try:
        min_inst_idx = args.index('--min-instances')
        min_inst_value = args[min_inst_idx + 1]
        if min_inst_value == '1':
            print_pass(f"Min instances: {min_inst_value} ✅")
        else:
            print_fail(f"Min instances is {min_inst_value}, expected 1")
            return False
    except (ValueError, IndexError):
        print_fail("--min-instances flag not found or invalid")
        return False
    
    print_pass("cloudbuild.yaml configuration verified successfully")
    return True

def verify_renderer_py():
    """Verify renderer.py has isolated context lifecycle and safe Chromium args"""
    print_test("Verifying renderer.py implementation...")
    
    renderer_path = Path("/app/backend/services/exports/renderer.py")
    if not renderer_path.exists():
        print_fail("renderer.py not found")
        return False
    
    with open(renderer_path, 'r') as f:
        content = f.read()
    
    # Check for isolated context lifecycle (context creation and cleanup)
    context_patterns = [
        r'context\s*=\s*await\s+_get_fresh_context\(',
        r'await\s+context\.close\(\)',
        r'finally:\s*\n\s*await\s+context\.close\(\)'
    ]
    
    isolated_context = all(re.search(pattern, content) for pattern in context_patterns)
    if isolated_context:
        print_pass("Isolated context lifecycle: contexts are created fresh and closed in finally blocks ✅")
    else:
        print_fail("Isolated context lifecycle not properly implemented")
        return False
    
    # Check for safe Chromium args
    safe_args = [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu'
    ]
    
    all_args_present = all(arg in content for arg in safe_args)
    if all_args_present:
        print_pass(f"Safe Chromium args present: {', '.join(safe_args)} ✅")
    else:
        missing_args = [arg for arg in safe_args if arg not in content]
        print_fail(f"Missing safe Chromium args: {', '.join(missing_args)}")
        return False
    
    # Check that contexts are not reused across requests
    if '_get_fresh_context' in content:
        print_pass("Using _get_fresh_context() for each render operation ✅")
    else:
        print_fail("Not using fresh contexts for each render")
        return False
    
    print_pass("renderer.py implementation verified successfully")
    return True

def test_export_pdf(token):
    """Test PDF export endpoint"""
    print_test(f"Testing GET /api/projects/{PROJECT_ID}/export/pdf...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/export/pdf",
        headers=headers,
        timeout=60
    )
    
    if response.status_code == 200:
        content_type = response.headers.get('Content-Type', '')
        content_length = len(response.content)
        content_disposition = response.headers.get('Content-Disposition', '')
        
        print_pass(f"HTTP 200 OK ✅")
        print_info(f"Content-Type: {content_type}")
        print_info(f"Content-Length: {content_length} bytes ({content_length / 1024:.1f} KB)")
        print_info(f"Content-Disposition: {content_disposition}")
        
        # Verify it's a valid PDF
        if response.content[:4] == b'%PDF':
            print_pass("Valid PDF file (magic bytes verified) ✅")
        else:
            print_fail("Response is not a valid PDF file")
            return False
        
        if 'application/pdf' in content_type:
            print_pass("Correct Content-Type ✅")
        else:
            print_fail(f"Incorrect Content-Type: {content_type}")
            return False
        
        return True
    else:
        print_fail(f"HTTP {response.status_code} - {response.text[:200]}")
        return False

def test_export_ppt(token):
    """Test PPT export endpoint"""
    print_test(f"Testing GET /api/projects/{PROJECT_ID}/export/ppt...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/export/ppt",
        headers=headers,
        timeout=60
    )
    
    if response.status_code == 200:
        content_type = response.headers.get('Content-Type', '')
        content_length = len(response.content)
        content_disposition = response.headers.get('Content-Disposition', '')
        
        print_pass(f"HTTP 200 OK ✅")
        print_info(f"Content-Type: {content_type}")
        print_info(f"Content-Length: {content_length} bytes ({content_length / 1024:.1f} KB)")
        print_info(f"Content-Disposition: {content_disposition}")
        
        # Verify it's a valid PPTX (ZIP file with PK magic bytes)
        if response.content[:2] == b'PK':
            print_pass("Valid PPTX file (ZIP magic bytes verified) ✅")
        else:
            print_fail("Response is not a valid PPTX file")
            return False
        
        expected_mime = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        if expected_mime in content_type:
            print_pass("Correct Content-Type ✅")
        else:
            print_fail(f"Incorrect Content-Type: {content_type}")
            return False
        
        return True
    else:
        print_fail(f"HTTP {response.status_code} - {response.text[:200]}")
        return False

def test_health_endpoint():
    """Test health endpoint"""
    print_test("Testing GET /api/health...")
    
    response = requests.get(f"{BASE_URL}/api/health", timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        print_pass(f"HTTP 200 OK ✅")
        print_info(f"Response: {data}")
        
        # Verify expected fields
        if data.get('status') == 'healthy':
            print_pass("Status: healthy ✅")
        else:
            print_fail(f"Status is not healthy: {data.get('status')}")
            return False
        
        if data.get('database') == 'connected':
            print_pass("Database: connected ✅")
        else:
            print_fail(f"Database not connected: {data.get('database')}")
            return False
        
        return True
    else:
        print_fail(f"HTTP {response.status_code} - {response.text}")
        return False

def main():
    print("\n" + "="*80)
    print("Cloud Run Deployment Configuration and Export Service Verification")
    print("="*80 + "\n")
    
    results = {}
    
    # Test 1: Verify cloudbuild.yaml
    print("\n" + "-"*80)
    print("TEST 1: Verify cloudbuild.yaml Configuration")
    print("-"*80)
    results['cloudbuild'] = verify_cloudbuild_yaml()
    
    # Test 2: Verify renderer.py
    print("\n" + "-"*80)
    print("TEST 2: Verify renderer.py Implementation")
    print("-"*80)
    results['renderer'] = verify_renderer_py()
    
    # Test 3: Health endpoint (no auth required)
    print("\n" + "-"*80)
    print("TEST 3: Health Endpoint")
    print("-"*80)
    results['health'] = test_health_endpoint()
    
    # Login for authenticated tests
    print("\n" + "-"*80)
    print("Authentication")
    print("-"*80)
    token = login()
    
    if not token:
        print_fail("Cannot proceed with export tests without authentication")
        results['pdf_export'] = False
        results['ppt_export'] = False
    else:
        # Test 4: PDF export
        print("\n" + "-"*80)
        print("TEST 4: PDF Export Endpoint")
        print("-"*80)
        results['pdf_export'] = test_export_pdf(token)
        
        # Test 5: PPT export
        print("\n" + "-"*80)
        print("TEST 5: PPT Export Endpoint")
        print("-"*80)
        results['ppt_export'] = test_export_ppt(token)
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    for test_name, passed in results.items():
        status = f"{GREEN}✅ PASS{RESET}" if passed else f"{RED}❌ FAIL{RESET}"
        print(f"{test_name.upper()}: {status}")
    
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed ({passed_tests/total_tests*100:.1f}%)")
    
    if passed_tests == total_tests:
        print(f"\n{GREEN}🎉 ALL TESTS PASSED{RESET}")
        return 0
    else:
        print(f"\n{RED}⚠️  SOME TESTS FAILED{RESET}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
