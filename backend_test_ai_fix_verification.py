#!/usr/bin/env python3
"""
Backend API Testing for AI Summary/Chat Path Fix
Review Request: Verify fix to DD Planner AI summary/chat path

CONTEXT: In production, report's "Status Summary" showed "Could not parse structured summary — 
I'm unable to process your request. Please check the AI configuration." when AI call failed.

FIX APPLIED: Hardened Gemini provider call in services/ai_providers.py:
- 45s timeout instead of 15s
- Ordered model-fallback list
- Error logging

LOCALLY: App uses Emergent provider (EMERGENT_LLM_KEY set in backend/.env)

TEST REQUIREMENTS:
1. AI CHAT - POST /api/ai/chat - verify returns real content, NOT error message
2. REPORT SUMMARY IN PDF - GET /api/projects/{id}/export/pdf - verify Status Summary shows real content
3. REGRESSION - PPT export, health check, projects list

Test credentials: admin@test.com / admin123
Test project: 6ab25bc82be78e05e89230f3 (Website Redesign)
Backend URL: http://localhost:8001
"""

import requests
import json
import subprocess
import os
import re
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8001/api"
TEST_USER = "admin@test.com"
TEST_PASSWORD = "admin123"
TEST_PROJECT_ID = "6ab25bc82be78e05e89230f3"  # Website Redesign

# Global token storage
token = None

def print_header(title):
    """Print a formatted test header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def print_test(test_name):
    """Print a test name"""
    print(f"\n[TEST] {test_name}")

def print_pass(message):
    """Print a pass message"""
    print(f"✅ PASS: {message}")

def print_fail(message):
    """Print a fail message"""
    print(f"❌ FAIL: {message}")

def print_info(message):
    """Print an info message"""
    print(f"ℹ️  INFO: {message}")

def login():
    """Login and get JWT token"""
    print_header("AUTHENTICATION")
    print_test("POST /api/auth/login")
    
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={
            "username": TEST_USER,
            "password": TEST_PASSWORD
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        global token
        data = response.json()
        token = data.get("access_token")
        print_pass(f"Login successful. Token: {token[:20]}...")
        return True
    else:
        print_fail(f"Login failed: {response.text}")
        return False

def get_headers():
    """Get authorization headers"""
    return {"Authorization": f"Bearer {token}"}

def test_ai_chat():
    """
    TEST 1: AI CHAT
    POST /api/ai/chat with JSON body
    - Assert HTTP 200
    - Assert response JSON has non-empty "response" field
    - CRITICAL: response must NOT be the failure string
    """
    print_header("TEST 1: AI CHAT ENDPOINT")
    print_test("POST /api/ai/chat")
    
    payload = {
        "message": "Return a JSON object with keys executive_summary and project_objective describing a website redesign project.",
        "session_id": None
    }
    
    print(f"Request payload: {json.dumps(payload, indent=2)}")
    
    response = requests.post(
        f"{BASE_URL}/ai/chat",
        headers={**get_headers(), "Content-Type": "application/json"},
        json=payload,
        timeout=60
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print_fail(f"Expected HTTP 200, got {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return False
    
    print_pass("HTTP 200 received")
    
    try:
        data = response.json()
        print(f"Response keys: {list(data.keys())}")
        
        # Check for response field
        if "response" not in data:
            print_fail("Response JSON missing 'response' field")
            print(f"Response: {json.dumps(data, indent=2)[:500]}")
            return False
        
        response_text = data.get("response", "")
        
        if not response_text or len(response_text.strip()) == 0:
            print_fail("Response field is empty")
            return False
        
        print_pass(f"Response field is non-empty ({len(response_text)} chars)")
        
        # CRITICAL CHECK: Must NOT be the failure message
        failure_messages = [
            "I'm unable to process your request right now. Please check the AI configuration in Settings.",
            "I'm unable to process your request",
            "Please check the AI configuration",
            "Could not parse structured summary"
        ]
        
        for failure_msg in failure_messages:
            if failure_msg.lower() in response_text.lower():
                print_fail(f"Response contains failure message: '{failure_msg}'")
                print(f"Response text: {response_text[:300]}")
                return False
        
        print_pass("Response does NOT contain failure messages")
        
        # Print first 200 chars of response
        print_info(f"Response preview (first 200 chars):")
        print(f"    {response_text[:200]}...")
        
        # Check if response looks like valid content
        if len(response_text) < 20:
            print_fail(f"Response too short ({len(response_text)} chars), likely not real content")
            return False
        
        print_pass("AI chat endpoint working correctly - returns real content")
        return True
        
    except json.JSONDecodeError as e:
        print_fail(f"Failed to parse JSON response: {e}")
        print(f"Response text: {response.text[:500]}")
        return False
    except Exception as e:
        print_fail(f"Unexpected error: {e}")
        return False

def test_pdf_export_with_status_summary():
    """
    TEST 2: REPORT SUMMARY IN PDF
    GET /api/projects/{id}/export/pdf
    - Assert HTTP 200, application/pdf
    - Assert PDF is valid and full report (~1 MB+, not ~4KB fallback)
    - Render pages to PNG and check Status Summary section
    - Must show REAL generated content (EXECUTIVE SUMMARY, PROJECT OBJECTIVE)
    - Must NOT show "Could not parse structured summary" or failure messages
    """
    print_header("TEST 2: PDF EXPORT WITH AI STATUS SUMMARY")
    print_test(f"GET /api/projects/{TEST_PROJECT_ID}/export/pdf")
    
    response = requests.get(
        f"{BASE_URL}/projects/{TEST_PROJECT_ID}/export/pdf",
        headers=get_headers(),
        timeout=120
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print_fail(f"Expected HTTP 200, got {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return False
    
    print_pass("HTTP 200 received")
    
    # Check Content-Type
    content_type = response.headers.get("Content-Type", "")
    if "application/pdf" not in content_type:
        print_fail(f"Expected Content-Type 'application/pdf', got '{content_type}'")
        return False
    
    print_pass(f"Content-Type is application/pdf")
    
    # Check PDF size
    pdf_size = len(response.content)
    pdf_size_kb = pdf_size / 1024
    print_info(f"PDF size: {pdf_size_kb:.1f} KB ({pdf_size} bytes)")
    
    if pdf_size < 100000:  # Less than ~100KB is likely fallback
        print_fail(f"PDF size too small ({pdf_size_kb:.1f} KB), likely fallback PDF")
        return False
    
    print_pass(f"PDF size is substantial ({pdf_size_kb:.1f} KB), full report confirmed")
    
    # Check PDF magic bytes
    if not response.content.startswith(b'%PDF'):
        print_fail("PDF magic bytes not found")
        return False
    
    print_pass("PDF magic bytes verified (%PDF)")
    
    # Save PDF to temp file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = f"/tmp/test_ai_pdf_{TEST_PROJECT_ID}_{timestamp}.pdf"
    with open(pdf_path, "wb") as f:
        f.write(response.content)
    
    print_info(f"PDF saved to: {pdf_path}")
    
    # Get page count using pdfinfo
    try:
        result = subprocess.run(
            ["pdfinfo", pdf_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            # Extract page count
            for line in result.stdout.split("\n"):
                if line.startswith("Pages:"):
                    page_count = int(line.split(":")[1].strip())
                    print_info(f"Page count: {page_count}")
                    
                    if page_count < 2:
                        print_fail(f"Page count too low ({page_count}), likely incomplete report")
                        return False
                    
                    print_pass(f"PDF has {page_count} pages (multi-page report)")
                    break
        else:
            print_info("Could not get page count with pdfinfo")
    except Exception as e:
        print_info(f"Could not get page count: {e}")
    
    # Render PDF pages to PNG for visual inspection
    print_test("Rendering PDF pages to PNG for Status Summary verification")
    
    try:
        # Render all pages at 90 DPI
        result = subprocess.run(
            ["pdftoppm", "-png", "-r", "90", pdf_path, f"/tmp/pdf_page_ai_{TEST_PROJECT_ID}"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print_fail(f"pdftoppm failed: {result.stderr}")
            return False
        
        print_pass("PDF pages rendered to PNG")
        
        # List generated PNG files
        png_files = sorted([f for f in os.listdir("/tmp") if f.startswith(f"pdf_page_ai_{TEST_PROJECT_ID}")])
        print_info(f"Generated {len(png_files)} PNG files")
        
        # Now we need to check the Status Summary section
        # The Status Summary is typically on page 2 of the report
        # We'll use OCR or text extraction to verify content
        
        # Try to extract text from PDF using pdftotext
        print_test("Extracting text from PDF to verify Status Summary content")
        
        result = subprocess.run(
            ["pdftotext", pdf_path, "-"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            pdf_text = result.stdout
            print_info(f"Extracted {len(pdf_text)} characters of text from PDF")
            
            # Check for Status Summary section
            if "Status Summary" not in pdf_text and "STATUS SUMMARY" not in pdf_text:
                print_fail("'Status Summary' section not found in PDF text")
                print_info("PDF text preview:")
                print(pdf_text[:1000])
                return False
            
            print_pass("'Status Summary' section found in PDF")
            
            # CRITICAL CHECK: Must NOT contain failure messages
            failure_messages = [
                "Could not parse structured summary",
                "I'm unable to process your request",
                "Please check the AI configuration",
                "Generating client status summary"
            ]
            
            found_failure = False
            for failure_msg in failure_messages:
                if failure_msg in pdf_text:
                    print_fail(f"PDF contains failure message: '{failure_msg}'")
                    found_failure = True
            
            if found_failure:
                # Extract Status Summary section
                status_summary_start = pdf_text.find("Status Summary")
                if status_summary_start == -1:
                    status_summary_start = pdf_text.find("STATUS SUMMARY")
                
                if status_summary_start != -1:
                    status_summary_text = pdf_text[status_summary_start:status_summary_start+500]
                    print_info("Status Summary section preview:")
                    print(status_summary_text)
                
                return False
            
            print_pass("PDF does NOT contain failure messages")
            
            # Check for expected content in Status Summary
            expected_content = [
                "EXECUTIVE SUMMARY",
                "PROJECT OBJECTIVE"
            ]
            
            found_content = []
            for content in expected_content:
                if content in pdf_text or content.lower() in pdf_text.lower():
                    found_content.append(content)
                    print_pass(f"Found expected content: '{content}'")
            
            if len(found_content) < 1:
                print_fail("Status Summary does not contain expected content (EXECUTIVE SUMMARY, PROJECT OBJECTIVE)")
                # Extract Status Summary section
                status_summary_start = pdf_text.find("Status Summary")
                if status_summary_start == -1:
                    status_summary_start = pdf_text.find("STATUS SUMMARY")
                
                if status_summary_start != -1:
                    status_summary_text = pdf_text[status_summary_start:status_summary_start+800]
                    print_info("Status Summary section preview:")
                    print(status_summary_text)
                
                return False
            
            print_pass(f"Status Summary contains real generated content ({len(found_content)}/{len(expected_content)} expected sections found)")
            
            # Extract and display Status Summary section
            status_summary_start = pdf_text.find("Status Summary")
            if status_summary_start == -1:
                status_summary_start = pdf_text.find("STATUS SUMMARY")
            
            if status_summary_start != -1:
                # Find the end of Status Summary section (next major section or ~1000 chars)
                status_summary_end = status_summary_start + 1000
                for next_section in ["Project Timeline", "PROJECT TIMELINE", "Risk Register", "RISK REGISTER"]:
                    idx = pdf_text.find(next_section, status_summary_start)
                    if idx != -1 and idx < status_summary_end:
                        status_summary_end = idx
                
                status_summary_text = pdf_text[status_summary_start:status_summary_end]
                print_info("Status Summary section content:")
                print("-" * 80)
                print(status_summary_text.strip())
                print("-" * 80)
            
            print_pass("PDF Status Summary shows REAL generated content")
            return True
        else:
            print_fail(f"pdftotext failed: {result.stderr}")
            return False
        
    except Exception as e:
        print_fail(f"Error rendering/analyzing PDF: {e}")
        return False

def test_regression():
    """
    TEST 3: REGRESSION TESTS
    - GET /api/projects/{id}/export/ppt returns 200 valid PPTX
    - GET /api/health returns 200
    - GET /api/projects returns 4 projects
    """
    print_header("TEST 3: REGRESSION TESTS")
    
    # Test 3.1: PPT Export
    print_test(f"GET /api/projects/{TEST_PROJECT_ID}/export/ppt")
    
    response = requests.get(
        f"{BASE_URL}/projects/{TEST_PROJECT_ID}/export/ppt",
        headers=get_headers(),
        timeout=120
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print_fail(f"Expected HTTP 200, got {response.status_code}")
        return False
    
    print_pass("HTTP 200 received")
    
    # Check Content-Type
    content_type = response.headers.get("Content-Type", "")
    expected_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    if expected_type not in content_type:
        print_fail(f"Expected Content-Type '{expected_type}', got '{content_type}'")
        return False
    
    print_pass("Content-Type is correct")
    
    # Check PPTX size
    pptx_size = len(response.content)
    pptx_size_kb = pptx_size / 1024
    print_info(f"PPTX size: {pptx_size_kb:.1f} KB")
    
    # Check ZIP magic bytes (PPTX is a ZIP file)
    if not response.content.startswith(b'PK'):
        print_fail("PPTX ZIP magic bytes not found")
        return False
    
    print_pass("PPTX ZIP magic bytes verified (PK)")
    
    # Test 3.2: Health Check
    print_test("GET /api/health")
    
    response = requests.get(f"{BASE_URL}/health", timeout=10)
    
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print_fail(f"Expected HTTP 200, got {response.status_code}")
        return False
    
    print_pass("HTTP 200 received")
    
    try:
        data = response.json()
        print(f"Health response: {json.dumps(data, indent=2)}")
        print_pass("Health endpoint working")
    except:
        print_fail("Failed to parse health response")
        return False
    
    # Test 3.3: Projects List
    print_test("GET /api/projects")
    
    response = requests.get(
        f"{BASE_URL}/projects",
        headers=get_headers(),
        timeout=10
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print_fail(f"Expected HTTP 200, got {response.status_code}")
        return False
    
    print_pass("HTTP 200 received")
    
    try:
        data = response.json()
        project_count = len(data)
        print_info(f"Projects count: {project_count}")
        
        if project_count != 4:
            print_fail(f"Expected 4 projects, got {project_count}")
            return False
        
        print_pass("Projects list returns 4 projects")
        
        # Check if test project exists
        test_project = next((p for p in data if p.get("id") == TEST_PROJECT_ID), None)
        if not test_project:
            print_fail(f"Test project {TEST_PROJECT_ID} not found in projects list")
            return False
        
        print_pass(f"Test project found: {test_project.get('name')}")
        
    except Exception as e:
        print_fail(f"Failed to parse projects response: {e}")
        return False
    
    print_pass("All regression tests passed")
    return True

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("  AI SUMMARY/CHAT PATH FIX VERIFICATION")
    print("  Backend URL: " + BASE_URL)
    print("  Test Project: " + TEST_PROJECT_ID)
    print("="*80)
    
    # Login
    if not login():
        print("\n❌ OVERALL RESULT: FAILED (login failed)")
        return False
    
    # Run tests
    results = {
        "AI Chat": test_ai_chat(),
        "PDF Export with Status Summary": test_pdf_export_with_status_summary(),
        "Regression Tests": test_regression()
    }
    
    # Print summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n" + "="*80)
        print("  ✅ OVERALL RESULT: PASS")
        print("  AI chat returns real content (not failure message)")
        print("  PDF Status Summary shows real content (not error message)")
        print("  All regression tests passed")
        print("="*80)
        return True
    else:
        print("\n" + "="*80)
        print("  ❌ OVERALL RESULT: FAIL")
        print(f"  {total - passed} test(s) failed")
        print("="*80)
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
