#!/usr/bin/env python3
"""
DD Planner Proposal Phase 2a Verification Test
===============================================
Final re-verification of "create proposal from project" with DEEP-MERGE coercion fix.

The coercion now deep-merges AI output onto the full scaffold so preview/render can
NEVER 500 on missing nested fields (e.g. understanding.challenges), and repairs
structural fields (options a/b/c, gates=4, stages 1-4, recommended_path).

CRITICAL SUCCESS CRITERIA:
- preview returns 200 in ALL cases across all 3 AI runs + non-AI + ai-draft
- Report any single 500/400 with response body
"""

import requests
import time
import sys
from datetime import datetime

# Backend URL from frontend/.env
BACKEND_URL = "https://proposal-approve.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "don@ddconsult.tech"
ADMIN_PASSWORD = "@Ddplanner2026"

# ANSI color codes for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def log(msg, color=RESET):
    """Print colored log message"""
    print(f"{color}{msg}{RESET}")

def log_success(msg):
    log(f"✅ {msg}", GREEN)

def log_error(msg):
    log(f"❌ {msg}", RED)

def log_info(msg):
    log(f"ℹ️  {msg}", BLUE)

def log_warning(msg):
    log(f"⚠️  {msg}", YELLOW)

class TestResults:
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def add_pass(self, test_name):
        self.total += 1
        self.passed += 1
        log_success(f"PASS: {test_name}")
    
    def add_fail(self, test_name, reason):
        self.total += 1
        self.failed += 1
        self.errors.append(f"{test_name}: {reason}")
        log_error(f"FAIL: {test_name}")
        log_error(f"  Reason: {reason}")
    
    def summary(self):
        log_info(f"\n{'='*80}")
        log_info(f"TEST SUMMARY")
        log_info(f"{'='*80}")
        log_info(f"Total tests: {self.total}")
        log_success(f"Passed: {self.passed}")
        if self.failed > 0:
            log_error(f"Failed: {self.failed}")
            log_error("\nFailed tests:")
            for error in self.errors:
                log_error(f"  - {error}")
        else:
            log_success("All tests passed! ✨")
        log_info(f"{'='*80}\n")
        return self.failed == 0

results = TestResults()

def authenticate():
    """Authenticate and return JWT token"""
    log_info("Authenticating as admin...")
    
    # OAuth2PasswordRequestForm expects form-encoded data
    response = requests.post(
        f"{API_BASE}/auth/login",
        data={
            "username": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if response.status_code != 200:
        log_error(f"Authentication failed: {response.status_code}")
        log_error(f"Response: {response.text}")
        sys.exit(1)
    
    token = response.json()["access_token"]
    log_success(f"Authenticated successfully as {ADMIN_EMAIL}")
    return token

def get_first_project(token):
    """Get first project ID from projects list"""
    log_info("Fetching projects...")
    
    response = requests.get(
        f"{API_BASE}/projects",
        params={"scope": "all"},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code != 200:
        log_error(f"Failed to fetch projects: {response.status_code}")
        log_error(f"Response: {response.text}")
        sys.exit(1)
    
    projects = response.json()
    if not projects:
        log_error("No projects found")
        sys.exit(1)
    
    project = projects[0]
    project_id = project["id"]
    project_name = project.get("name", "Unknown")
    log_success(f"Selected project: {project_name} (ID: {project_id})")
    return project_id

def validate_proposal_structure(data, test_name):
    """Validate proposal structure has required fields"""
    errors = []
    
    # Check options are exactly a, b, c
    options = data.get("data", {}).get("options", [])
    option_paths = {o.get("path") for o in options if isinstance(o, dict)}
    if option_paths != {"a", "b", "c"}:
        errors.append(f"options paths are {option_paths}, expected {{a, b, c}}")
    
    # Check gates = 4
    gates = data.get("data", {}).get("success", {}).get("gates", [])
    if len(gates) != 4:
        errors.append(f"gates count is {len(gates)}, expected 4")
    
    # Check stage_deliverables has keys 1-4
    stage_deliverables = data.get("data", {}).get("plan", {}).get("stage_deliverables", {})
    expected_keys = {"1", "2", "3", "4"}
    actual_keys = set(stage_deliverables.keys())
    if actual_keys != expected_keys:
        errors.append(f"stage_deliverables keys are {actual_keys}, expected {expected_keys}")
    
    # Check pricing_model has path_a/b/c
    pricing_model = data.get("data", {}).get("pricing_model", {})
    if not all(f"path_{k}" in pricing_model for k in ("a", "b", "c")):
        errors.append(f"pricing_model missing path_a/b/c keys")
    
    # Check team is non-empty
    team = data.get("data", {}).get("team", [])
    if not team:
        errors.append("team is empty")
    
    if errors:
        results.add_fail(f"{test_name} - Structure validation", "; ".join(errors))
        return False
    else:
        results.add_pass(f"{test_name} - Structure validation")
        return True

def test_from_project_with_ai(token, project_id, run_number):
    """Test POST /api/proposals/from-project with use_ai=true"""
    test_name = f"RUN {run_number}: from-project with AI"
    log_info(f"\n{'='*80}")
    log_info(f"Starting {test_name}...")
    log_info(f"{'='*80}")
    
    start_time = time.time()
    
    # Step 1: Create proposal from project with AI
    log_info("Step 1: POST /api/proposals/from-project (use_ai=true)...")
    response = requests.post(
        f"{API_BASE}/proposals/from-project",
        json={
            "project_id": project_id,
            "use_ai": True
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=75  # Allow up to 75s for AI processing
    )
    
    elapsed = time.time() - start_time
    log_info(f"Response time: {elapsed:.2f}s")
    
    if response.status_code != 200:
        results.add_fail(
            f"{test_name} - from-project endpoint",
            f"HTTP {response.status_code}: {response.text[:500]}"
        )
        return None
    
    log_success(f"from-project returned 200 in {elapsed:.2f}s")
    
    # Validate response structure
    data = response.json()
    proposal_id = data.get("id")
    if not proposal_id:
        results.add_fail(f"{test_name} - from-project endpoint", "No proposal ID in response")
        return None
    
    log_success(f"Proposal created: {proposal_id}")
    
    # Validate structure
    if not validate_proposal_structure(data, test_name):
        return None
    
    results.add_pass(f"{test_name} - from-project endpoint")
    
    # Step 2: Immediately preview the proposal
    log_info("Step 2: POST /api/proposals/{id}/preview...")
    preview_response = requests.post(
        f"{API_BASE}/proposals/{proposal_id}/preview",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    
    if preview_response.status_code != 200:
        results.add_fail(
            f"{test_name} - preview endpoint",
            f"HTTP {preview_response.status_code}: {preview_response.text[:500]}"
        )
        return None
    
    # Validate preview response
    html = preview_response.text
    if len(html) < 10000:
        results.add_fail(
            f"{test_name} - preview endpoint",
            f"HTML length {len(html)} < 10000"
        )
        return None
    
    # Check client name is in HTML
    client_name = data.get("data", {}).get("client_name", "")
    if client_name and client_name not in html:
        log_warning(f"Client name '{client_name}' not found in HTML (may be OK if empty)")
    else:
        log_success(f"Client name '{client_name}' found in HTML")
    
    log_success(f"preview returned 200 with {len(html):,} bytes HTML")
    results.add_pass(f"{test_name} - preview endpoint")
    
    log_success(f"{test_name} COMPLETED SUCCESSFULLY ✨")
    return proposal_id

def test_from_project_without_ai(token, project_id):
    """Test POST /api/proposals/from-project with use_ai=false"""
    test_name = "Non-AI: from-project without AI"
    log_info(f"\n{'='*80}")
    log_info(f"Starting {test_name}...")
    log_info(f"{'='*80}")
    
    # Step 1: Create proposal from project without AI
    log_info("Step 1: POST /api/proposals/from-project (use_ai=false)...")
    response = requests.post(
        f"{API_BASE}/proposals/from-project",
        json={
            "project_id": project_id,
            "use_ai": False
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    
    if response.status_code != 200:
        results.add_fail(
            f"{test_name} - from-project endpoint",
            f"HTTP {response.status_code}: {response.text[:500]}"
        )
        return None
    
    log_success("from-project returned 200")
    
    # Validate response structure
    data = response.json()
    proposal_id = data.get("id")
    if not proposal_id:
        results.add_fail(f"{test_name} - from-project endpoint", "No proposal ID in response")
        return None
    
    log_success(f"Proposal created: {proposal_id}")
    
    # Validate structure
    if not validate_proposal_structure(data, test_name):
        return None
    
    results.add_pass(f"{test_name} - from-project endpoint")
    
    # Step 2: Preview the proposal
    log_info("Step 2: POST /api/proposals/{id}/preview...")
    preview_response = requests.post(
        f"{API_BASE}/proposals/{proposal_id}/preview",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    
    if preview_response.status_code != 200:
        results.add_fail(
            f"{test_name} - preview endpoint",
            f"HTTP {preview_response.status_code}: {preview_response.text[:500]}"
        )
        return None
    
    # Validate preview response
    html = preview_response.text
    if len(html) < 10000:
        results.add_fail(
            f"{test_name} - preview endpoint",
            f"HTML length {len(html)} < 10000"
        )
        return None
    
    log_success(f"preview returned 200 with {len(html):,} bytes HTML")
    results.add_pass(f"{test_name} - preview endpoint")
    
    log_success(f"{test_name} COMPLETED SUCCESSFULLY ✨")
    return proposal_id

def test_ai_draft_graceful(token):
    """Test ai-draft graceful path: create blank proposal, ai-draft, preview"""
    test_name = "AI-draft graceful path"
    log_info(f"\n{'='*80}")
    log_info(f"Starting {test_name}...")
    log_info(f"{'='*80}")
    
    # Step 1: Create blank proposal
    log_info("Step 1: POST /api/proposals (blank proposal)...")
    response = requests.post(
        f"{API_BASE}/proposals",
        json={
            "client_name": "Test Co"
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    
    if response.status_code != 200:
        results.add_fail(
            f"{test_name} - create blank proposal",
            f"HTTP {response.status_code}: {response.text[:500]}"
        )
        return None
    
    data = response.json()
    proposal_id = data.get("id")
    if not proposal_id:
        results.add_fail(f"{test_name} - create blank proposal", "No proposal ID in response")
        return None
    
    log_success(f"Blank proposal created: {proposal_id}")
    results.add_pass(f"{test_name} - create blank proposal")
    
    # Step 2: AI draft
    log_info("Step 2: POST /api/proposals/{id}/ai-draft...")
    draft_response = requests.post(
        f"{API_BASE}/proposals/{proposal_id}/ai-draft",
        json={
            "message": "cloud migration proposal for a logistics firm, recommend discovery first"
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=75  # Allow up to 75s for AI processing
    )
    
    # CRITICAL: Must return 200, NEVER 500
    if draft_response.status_code != 200:
        results.add_fail(
            f"{test_name} - ai-draft endpoint",
            f"HTTP {draft_response.status_code}: {draft_response.text[:500]}"
        )
        return None
    
    draft_data = draft_response.json()
    assistant_message = draft_data.get("assistant_message", "")
    
    # Check if AI was available or gracefully degraded
    if "temporarily unavailable" in assistant_message.lower():
        log_warning("AI temporarily unavailable (graceful degradation)")
    else:
        log_success("AI draft completed successfully")
    
    log_success("ai-draft returned 200 (NEVER 500) ✅")
    results.add_pass(f"{test_name} - ai-draft endpoint")
    
    # Step 3: Preview MUST be 200
    log_info("Step 3: POST /api/proposals/{id}/preview...")
    preview_response = requests.post(
        f"{API_BASE}/proposals/{proposal_id}/preview",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    
    if preview_response.status_code != 200:
        results.add_fail(
            f"{test_name} - preview endpoint",
            f"HTTP {preview_response.status_code}: {preview_response.text[:500]}"
        )
        return None
    
    html = preview_response.text
    if len(html) < 10000:
        results.add_fail(
            f"{test_name} - preview endpoint",
            f"HTML length {len(html)} < 10000"
        )
        return None
    
    log_success(f"preview returned 200 with {len(html):,} bytes HTML")
    results.add_pass(f"{test_name} - preview endpoint")
    
    log_success(f"{test_name} COMPLETED SUCCESSFULLY ✨")
    return proposal_id

def test_negative_bogus_project_id(token):
    """Test negative case: POST /api/proposals/from-project with bogus project_id"""
    test_name = "Negative: bogus project_id"
    log_info(f"\n{'='*80}")
    log_info(f"Starting {test_name}...")
    log_info(f"{'='*80}")
    
    log_info("POST /api/proposals/from-project with bogus project_id...")
    response = requests.post(
        f"{API_BASE}/proposals/from-project",
        json={
            "project_id": "000000000000000000000000",
            "use_ai": False
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    
    if response.status_code != 404:
        results.add_fail(
            test_name,
            f"Expected HTTP 404, got {response.status_code}: {response.text[:500]}"
        )
        return
    
    log_success("Correctly returned 404 for bogus project_id")
    results.add_pass(test_name)

def main():
    """Main test execution"""
    log_info(f"\n{'='*80}")
    log_info("DD PLANNER PROPOSAL PHASE 2A VERIFICATION TEST")
    log_info("DEEP-MERGE Coercion Fix Verification")
    log_info(f"{'='*80}\n")
    log_info(f"Backend URL: {BACKEND_URL}")
    log_info(f"Test started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Authenticate
    token = authenticate()
    
    # Get first project
    project_id = get_first_project(token)
    
    # TEST 1-3: Three AI runs
    log_info(f"\n{'='*80}")
    log_info("PHASE 1: THREE AI RUNS")
    log_info(f"{'='*80}")
    for i in range(1, 4):
        test_from_project_with_ai(token, project_id, i)
        if i < 3:
            log_info("\nWaiting 2 seconds before next AI run...")
            time.sleep(2)
    
    # TEST 4: Non-AI run
    log_info(f"\n{'='*80}")
    log_info("PHASE 2: NON-AI RUN")
    log_info(f"{'='*80}")
    test_from_project_without_ai(token, project_id)
    
    # TEST 5: AI-draft graceful path
    log_info(f"\n{'='*80}")
    log_info("PHASE 3: AI-DRAFT GRACEFUL PATH")
    log_info(f"{'='*80}")
    test_ai_draft_graceful(token)
    
    # TEST 6: Negative case
    log_info(f"\n{'='*80}")
    log_info("PHASE 4: NEGATIVE TESTS")
    log_info(f"{'='*80}")
    test_negative_bogus_project_id(token)
    
    # Print summary
    success = results.summary()
    
    log_info(f"Test completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
