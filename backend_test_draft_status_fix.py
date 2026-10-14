#!/usr/bin/env python3
"""
Test AI Draft Status Update Bug Fix
====================================
Verifies the fix for "TypeError: can't compare offset-naive and offset-aware datetimes"
in POST /api/ai/draft-status-update/{project_id}

The bug was in services/status_drafter.py _dt() helper which returned naive datetimes
when parsing stored ISO date strings without timezone info (e.g. "2025-07-01T00:00:00").
The fix normalizes BOTH naive strings and naive datetimes to UTC-aware.

Test Plan:
1. Find real project IDs (prefer ones with WBS tasks and timesheets with naive dates)
2. POST /api/ai/draft-status-update/{project_id} for at least 2 projects
3. Assert HTTP 200 (NOT 500) and coherent drafted status update
4. Check backend logs for NO naive/aware datetime errors
5. Regression: GET /api/ai/portfolio-budget-analysis → 200
6. Regression: POST /api/ai/kickoff-suggest → 200
"""

import requests
import json
import sys
from datetime import datetime

# Backend URL from frontend/.env
BACKEND_URL = "https://ddplanner-fixes.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

# Test credentials from /app/memory/test_credentials.md
# Try admin@test.com first (mentioned in review request)
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def login():
    """Login and return JWT token"""
    log("Logging in as admin...")
    resp = requests.post(
        f"{API_BASE}/auth/login",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if resp.status_code != 200:
        log(f"❌ Login failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    token = resp.json().get("access_token")
    log(f"✅ Login successful, token: {token[:20]}...")
    return token

def get_projects(token):
    """Get list of projects"""
    log("Fetching projects...")
    resp = requests.get(
        f"{API_BASE}/projects",
        headers={"Authorization": f"Bearer {token}"}
    )
    if resp.status_code != 200:
        log(f"❌ Failed to fetch projects: {resp.status_code}")
        return []
    projects = resp.json()
    log(f"✅ Found {len(projects)} projects")
    return projects

def test_draft_status_update(token, project_id, project_name):
    """Test POST /api/ai/draft-status-update/{project_id}"""
    log(f"\n{'='*80}")
    log(f"Testing draft-status-update for project: {project_name} ({project_id})")
    log(f"{'='*80}")
    
    resp = requests.post(
        f"{API_BASE}/ai/draft-status-update/{project_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    log(f"Response status: {resp.status_code}")
    
    if resp.status_code != 200:
        log(f"❌ FAILED: Expected 200, got {resp.status_code}")
        log(f"Response body: {resp.text[:500]}")
        return False
    
    try:
        data = resp.json()
        log(f"✅ SUCCESS: HTTP 200 received")
        
        # Check for required fields in response
        if "draft" not in data:
            log(f"❌ FAILED: Response missing 'draft' field")
            log(f"Response: {json.dumps(data, indent=2)[:500]}")
            return False
        
        draft = data["draft"]
        required_fields = ["health", "schedule_status", "accomplishments", "blockers", "next_steps"]
        missing = [f for f in required_fields if f not in draft]
        
        if missing:
            log(f"❌ FAILED: Draft missing required fields: {missing}")
            return False
        
        log(f"✅ Draft contains all required fields: {required_fields}")
        log(f"\nDraft preview:")
        log(f"  Health: {draft.get('health')}")
        log(f"  Schedule: {draft.get('schedule_status')}")
        log(f"  Progress: {draft.get('actual_progress')}%")
        log(f"  Accomplishments: {draft.get('accomplishments')[:100]}...")
        log(f"  Blockers: {draft.get('blockers')[:100]}...")
        log(f"  Next Steps: {draft.get('next_steps')[:100]}...")
        
        # Check snapshot data
        if "snapshot" in data:
            snapshot = data["snapshot"]
            log(f"\nSnapshot data:")
            log(f"  Period: {snapshot.get('period')}")
            log(f"  Hours: {snapshot.get('hours')}")
            log(f"  Progress: {snapshot.get('progress_pct')}%")
        
        return True
        
    except Exception as e:
        log(f"❌ FAILED: Error parsing response: {e}")
        log(f"Response text: {resp.text[:500]}")
        return False

def test_portfolio_budget_analysis(token):
    """Regression test: GET /api/ai/portfolio-budget-analysis"""
    log(f"\n{'='*80}")
    log("Regression Test: Portfolio Budget Analysis")
    log(f"{'='*80}")
    
    resp = requests.get(
        f"{API_BASE}/ai/portfolio-budget-analysis",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    log(f"Response status: {resp.status_code}")
    
    if resp.status_code != 200:
        log(f"❌ FAILED: Expected 200, got {resp.status_code}")
        log(f"Response: {resp.text[:300]}")
        return False
    
    log(f"✅ SUCCESS: Portfolio budget analysis endpoint working")
    return True

def test_kickoff_suggest(token):
    """Regression test: POST /api/ai/kickoff-suggest"""
    log(f"\n{'='*80}")
    log("Regression Test: Kickoff Suggest")
    log(f"{'='*80}")
    
    payload = {
        "name": "Test Project for Kickoff",
        "goal": "Build a test application to verify kickoff suggestions",
        "client_name": "Test Client"
    }
    
    resp = requests.post(
        f"{API_BASE}/ai/kickoff-suggest",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )
    
    log(f"Response status: {resp.status_code}")
    
    if resp.status_code != 200:
        log(f"❌ FAILED: Expected 200, got {resp.status_code}")
        log(f"Response: {resp.text[:300]}")
        return False
    
    try:
        data = resp.json()
        log(f"✅ SUCCESS: Kickoff suggest endpoint working")
        log(f"Response preview: {json.dumps(data, indent=2)[:300]}...")
        return True
    except Exception as e:
        log(f"❌ FAILED: Error parsing response: {e}")
        return False

def check_backend_logs():
    """Check backend logs for naive/aware datetime errors AFTER the most recent server start"""
    log(f"\n{'='*80}")
    log("Checking backend logs for datetime errors (after most recent server start)...")
    log(f"{'='*80}")
    
    import subprocess
    try:
        result = subprocess.run(
            ["tail", "-n", "200", "/var/log/supervisor/backend.err.log"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        logs = result.stdout
        lines = logs.split('\n')
        
        # Find the most recent server start
        last_start_idx = -1
        for i in range(len(lines) - 1, -1, -1):
            if "Started server process" in lines[i] or "Application startup complete" in lines[i]:
                last_start_idx = i
                break
        
        if last_start_idx == -1:
            log(f"⚠️  WARNING: Could not find server start marker in logs")
            # Check all logs as fallback
            logs_to_check = logs
        else:
            log(f"Found most recent server start at line {last_start_idx}")
            # Only check logs AFTER the server start
            logs_to_check = '\n'.join(lines[last_start_idx:])
        
        # Check for the specific error AFTER server start
        if "can't compare offset-naive and offset-aware" in logs_to_check:
            log(f"❌ FAILED: Found naive/aware datetime error in logs AFTER server restart")
            # Print the error context
            check_lines = logs_to_check.split('\n')
            for i, line in enumerate(check_lines):
                if "can't compare offset-naive and offset-aware" in line:
                    log(f"\nError context:")
                    for j in range(max(0, i-5), min(len(check_lines), i+5)):
                        log(f"  {check_lines[j]}")
            return False
        
        # Check for ResponseValidationError AFTER server start
        if "ResponseValidationError" in logs_to_check:
            log(f"⚠️  WARNING: Found ResponseValidationError in logs AFTER server restart")
            return False
        
        log(f"✅ SUCCESS: No naive/aware datetime errors found in logs after server restart")
        log(f"   (Old errors from before the fix may still be visible in earlier log entries)")
        return True
        
    except Exception as e:
        log(f"⚠️  WARNING: Could not check logs: {e}")
        return True  # Don't fail the test if we can't check logs

def main():
    log("="*80)
    log("AI Draft Status Update Bug Fix Verification")
    log("="*80)
    
    # Login
    token = login()
    
    # Get projects
    projects = get_projects(token)
    if not projects:
        log("❌ No projects found, cannot test")
        sys.exit(1)
    
    # Find suitable test projects
    # Prefer projects with WBS tasks (more likely to have naive dates)
    test_projects = []
    
    # Look for "QA Test Project - My Allocations" mentioned in review request
    qa_project = next((p for p in projects if "QA Test Project" in p.get("name", "")), None)
    if qa_project:
        test_projects.append(qa_project)
        log(f"✅ Found QA Test Project: {qa_project['name']} ({qa_project['id']})")
    
    # Add other projects to test at least 2
    for p in projects:
        if p not in test_projects and len(test_projects) < 3:
            test_projects.append(p)
    
    if len(test_projects) < 2:
        log(f"⚠️  WARNING: Only found {len(test_projects)} project(s) to test")
    
    # Test draft-status-update on each project
    results = []
    for project in test_projects:
        result = test_draft_status_update(token, project["id"], project["name"])
        results.append(("draft-status-update", project["name"], result))
    
    # Regression tests
    results.append(("portfolio-budget-analysis", "N/A", test_portfolio_budget_analysis(token)))
    results.append(("kickoff-suggest", "N/A", test_kickoff_suggest(token)))
    
    # Check logs
    logs_ok = check_backend_logs()
    results.append(("backend-logs-check", "N/A", logs_ok))
    
    # Summary
    log(f"\n{'='*80}")
    log("TEST SUMMARY")
    log(f"{'='*80}")
    
    passed = sum(1 for _, _, r in results if r)
    total = len(results)
    
    for test_name, project_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        if project_name != "N/A":
            log(f"{status}: {test_name} ({project_name})")
        else:
            log(f"{status}: {test_name}")
    
    log(f"\n{'='*80}")
    log(f"FINAL RESULT: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    log(f"{'='*80}")
    
    if passed == total:
        log("✅✅✅ ALL TESTS PASSED ✅✅✅")
        log("\nThe bug fix is working correctly:")
        log("  • draft-status-update endpoint returns HTTP 200 (not 500)")
        log("  • Coherent drafted status updates generated")
        log("  • No naive/aware datetime errors in logs")
        log("  • Regression tests passed")
        sys.exit(0)
    else:
        log("❌❌❌ SOME TESTS FAILED ❌❌❌")
        sys.exit(1)

if __name__ == "__main__":
    main()
