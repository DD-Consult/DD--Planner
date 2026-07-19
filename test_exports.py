#!/usr/bin/env python3
"""
Smoke test for PDF and PPT export endpoints with client mode support.
Tests all 4 export variations (PDF internal, PDF client, PPT internal, PPT client).
"""
import requests
import sys

BASE_URL = "http://localhost:8001"

def main():
    print("=" * 60)
    print("Export Endpoints Smoke Test")
    print("=" * 60)
    
    # Login
    print("\n1. Logging in as admin...")
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": "admin@test.com", "password": "admin123"}
    )
    if r.status_code != 200:
        print(f"❌ Login failed: {r.status_code}")
        print(r.text)
        return False
    
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Login successful")
    
    # Get first project
    print("\n2. Fetching projects...")
    r = requests.get(f"{BASE_URL}/api/projects", headers=headers)
    if r.status_code != 200:
        print(f"❌ Failed to fetch projects: {r.status_code}")
        return False
    
    projects = r.json()
    if not projects:
        print("❌ No projects found")
        return False
    
    project_id = projects[0]["id"]
    project_name = projects[0]["name"]
    print(f"✅ Found project: {project_name} (ID: {project_id})")
    
    # Test all 4 export endpoints
    test_cases = [
        ("PDF Internal", f"/api/projects/{project_id}/export/pdf", False, "application/pdf", b"%PDF"),
        ("PDF Client", f"/api/projects/{project_id}/export/pdf?client=true", False, "application/pdf", b"%PDF"),
        ("PPT Internal", f"/api/projects/{project_id}/export/ppt", False, "application/vnd.openxmlformats-officedocument.presentationml.presentation", b"PK"),
        ("PPT Client", f"/api/projects/{project_id}/export/ppt?client=true", False, "application/vnd.openxmlformats-officedocument.presentationml.presentation", b"PK"),
    ]
    
    results = []
    
    for name, endpoint, should_fail, expected_content_type, magic_bytes in test_cases:
        print(f"\n3. Testing {name}...")
        r = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
        
        if r.status_code != 200:
            print(f"❌ {name} failed: {r.status_code}")
            print(f"   Response: {r.text[:200]}")
            results.append((name, False))
            continue
        
        # Check content type
        content_type = r.headers.get("Content-Type", "")
        if expected_content_type not in content_type:
            print(f"❌ {name} wrong content type: {content_type}")
            results.append((name, False))
            continue
        
        # Check magic bytes
        if not r.content.startswith(magic_bytes):
            print(f"❌ {name} invalid file format (magic bytes: {r.content[:4]})")
            results.append((name, False))
            continue
        
        # Check file size
        size_kb = len(r.content) / 1024
        print(f"✅ {name} generated successfully ({size_kb:.1f} KB)")
        results.append((name, True))
    
    # Compare client vs internal outputs
    print("\n4. Verifying client and internal modes produce different outputs...")
    
    r_pdf_internal = requests.get(f"{BASE_URL}/api/projects/{project_id}/export/pdf", headers=headers)
    r_pdf_client = requests.get(f"{BASE_URL}/api/projects/{project_id}/export/pdf?client=true", headers=headers)
    
    if r_pdf_internal.content == r_pdf_client.content:
        print("❌ PDF: Internal and client PDFs are identical (should differ!)")
        results.append(("PDF differentiation", False))
    else:
        print("✅ PDF: Internal and client PDFs are different")
        results.append(("PDF differentiation", True))
    
    r_ppt_internal = requests.get(f"{BASE_URL}/api/projects/{project_id}/export/ppt", headers=headers)
    r_ppt_client = requests.get(f"{BASE_URL}/api/projects/{project_id}/export/ppt?client=true", headers=headers)
    
    if r_ppt_internal.content == r_ppt_client.content:
        print("❌ PPT: Internal and client PPTs are identical (should differ!)")
        results.append(("PPT differentiation", False))
    else:
        print("✅ PPT: Internal and client PPTs are different")
        results.append(("PPT differentiation", True))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"{status} {name}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n🎉 All tests passed!")
        return True
    else:
        print("\n⚠️  Some tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
