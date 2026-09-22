#!/usr/bin/env python3
"""
Test script to verify PDF and PPT export endpoints
Verifies that 503 error is resolved for project exports
"""

import requests
import sys
import os
from pathlib import Path

# Test configuration
BASE_URL = "https://base-product-check.preview.emergentagent.com/api"
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "admin123"
PROJECT_ID = "6aabd45b6023b8429321ad6c"

def login():
    """Login and get JWT token"""
    print(f"🔐 Logging in as {TEST_EMAIL}...")
    
    # OAuth2PasswordRequestForm expects form-encoded data
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if response.status_code != 200:
        print(f"❌ Login failed: {response.status_code}")
        print(f"Response: {response.text}")
        return None
    
    data = response.json()
    token = data.get("access_token")
    print(f"✅ Login successful, token received")
    return token

def test_pdf_export(token):
    """Test PDF export endpoint"""
    print(f"\n📄 Testing PDF export for project {PROJECT_ID}...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/projects/{PROJECT_ID}/export/pdf",
        headers=headers,
        timeout=60  # PDF generation can take time
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print(f"Content-Disposition: {response.headers.get('Content-Disposition')}")
    print(f"Content Length: {len(response.content)} bytes")
    
    if response.status_code == 503:
        print("❌ CRITICAL: 503 Service Unavailable error detected!")
        return False
    elif response.status_code == 500:
        print("❌ CRITICAL: 500 Internal Server Error detected!")
        print(f"Response: {response.text[:500]}")
        return False
    elif response.status_code != 200:
        print(f"❌ FAILED: Unexpected status code {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return False
    
    # Verify content type
    content_type = response.headers.get('Content-Type', '')
    if 'application/pdf' not in content_type:
        print(f"❌ FAILED: Expected application/pdf, got {content_type}")
        return False
    
    # Verify content is not empty
    if len(response.content) == 0:
        print("❌ FAILED: PDF content is empty")
        return False
    
    # Verify PDF magic bytes
    if not response.content.startswith(b'%PDF'):
        print("❌ FAILED: Content does not start with PDF magic bytes")
        return False
    
    # Save PDF for verification
    pdf_path = "/tmp/test_export.pdf"
    with open(pdf_path, "wb") as f:
        f.write(response.content)
    print(f"✅ PDF saved to {pdf_path}")
    
    # Verify with pdfinfo
    try:
        import subprocess
        result = subprocess.run(
            ["pdfinfo", pdf_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✅ PDF file is valid (verified with pdfinfo)")
            # Extract page count
            for line in result.stdout.split('\n'):
                if 'Pages:' in line:
                    print(f"   {line.strip()}")
        else:
            print("⚠️  Could not verify PDF with pdfinfo")
    except Exception as e:
        print(f"⚠️  Could not verify PDF: {e}")
    
    print("✅ PDF export test PASSED")
    return True

def test_ppt_export(token):
    """Test PPT export endpoint"""
    print(f"\n📊 Testing PPT export for project {PROJECT_ID}...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/projects/{PROJECT_ID}/export/ppt",
        headers=headers,
        timeout=60  # PPT generation can take time
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print(f"Content-Disposition: {response.headers.get('Content-Disposition')}")
    print(f"Content Length: {len(response.content)} bytes")
    
    if response.status_code == 503:
        print("❌ CRITICAL: 503 Service Unavailable error detected!")
        return False
    elif response.status_code == 500:
        print("❌ CRITICAL: 500 Internal Server Error detected!")
        print(f"Response: {response.text[:500]}")
        return False
    elif response.status_code != 200:
        print(f"❌ FAILED: Unexpected status code {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return False
    
    # Verify content type
    content_type = response.headers.get('Content-Type', '')
    expected_mime = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    if expected_mime not in content_type:
        print(f"❌ FAILED: Expected {expected_mime}, got {content_type}")
        return False
    
    # Verify content is not empty
    if len(response.content) == 0:
        print("❌ FAILED: PPT content is empty")
        return False
    
    # Verify PPTX magic bytes (ZIP format)
    if not response.content.startswith(b'PK'):
        print("❌ FAILED: Content does not start with ZIP magic bytes (PPTX is ZIP-based)")
        return False
    
    # Save PPTX for verification
    pptx_path = "/tmp/test_export.pptx"
    with open(pptx_path, "wb") as f:
        f.write(response.content)
    print(f"✅ PPTX saved to {pptx_path}")
    
    # Verify with python-pptx
    try:
        from pptx import Presentation
        prs = Presentation(pptx_path)
        slide_count = len(prs.slides)
        print(f"✅ PPTX file is valid (verified with python-pptx)")
        print(f"   Slides: {slide_count}")
    except Exception as e:
        print(f"⚠️  Could not verify PPTX: {e}")
    
    print("✅ PPT export test PASSED")
    return True

def test_nonexistent_project(token):
    """Test that non-existent project returns 404"""
    print(f"\n🔍 Testing non-existent project (should return 404)...")
    
    headers = {"Authorization": f"Bearer {token}"}
    fake_id = "000000000000000000000000"
    
    response = requests.get(
        f"{BASE_URL}/projects/{fake_id}/export/pdf",
        headers=headers,
        timeout=30
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 404:
        print("✅ Correctly returns 404 for non-existent project")
        return True
    else:
        print(f"❌ FAILED: Expected 404, got {response.status_code}")
        return False

def test_unauthorized_access():
    """Test that missing auth returns 401"""
    print(f"\n🔒 Testing unauthorized access (should return 401)...")
    
    response = requests.get(
        f"{BASE_URL}/projects/{PROJECT_ID}/export/pdf",
        timeout=30
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 401:
        print("✅ Correctly returns 401 for missing auth")
        return True
    else:
        print(f"❌ FAILED: Expected 401, got {response.status_code}")
        return False

def main():
    print("=" * 70)
    print("PDF & PPT Export Endpoints Verification")
    print("Testing for 503 error resolution")
    print("=" * 70)
    
    results = []
    
    # Test 1: Login
    token = login()
    if not token:
        print("\n❌ CRITICAL: Cannot proceed without authentication")
        sys.exit(1)
    results.append(("Login", True))
    
    # Test 2: PDF Export
    results.append(("PDF Export", test_pdf_export(token)))
    
    # Test 3: PPT Export
    results.append(("PPT Export", test_ppt_export(token)))
    
    # Test 4: Non-existent project
    results.append(("404 Handling", test_nonexistent_project(token)))
    
    # Test 5: Unauthorized access
    results.append(("401 Handling", test_unauthorized_access()))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:20s} {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - No 503 or 500 errors detected!")
        print("✅ PDF export endpoint working correctly")
        print("✅ PPT export endpoint working correctly")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
