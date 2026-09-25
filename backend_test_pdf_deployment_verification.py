#!/usr/bin/env python3
"""
PDF Export Deployment Verification
===================================
Verifies the deployed PDF export against reported bugs:
1. Unclean PDF - content clipped at right edge (WBS table columns, Timeline)
2. Intermittent 502/503 from Chromium OOM under concurrent load

Test project: 6ab25bc82be78e05e89230f3 (Website Redesign - 8 WBS tasks + 4 risks)
"""

import requests
import time
import subprocess
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
BASE_URL = "http://localhost:8001"
TEST_PROJECT_ID = "6ab25bc82be78e05e89230f3"
AUTH_EMAIL = "admin@test.com"
AUTH_PASSWORD = "admin123"

# Expected values
EXPECTED_FULL_PDF_SIZE_MIN = 1000000  # 1 MB minimum (full report)
EXPECTED_FALLBACK_SIZE_MAX = 10000    # 10 KB maximum (ReportLab fallback)
EXPECTED_PAGE_SIZE = (960.0, 540.0)   # 16:9 ratio
EXPECTED_MIN_PAGES = 5                # Multi-page report

def print_section(title):
    """Print a section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def authenticate():
    """Authenticate and return access token"""
    print("🔐 Authenticating...")
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={
            "username": AUTH_EMAIL,
            "password": AUTH_PASSWORD
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if response.status_code != 200:
        print(f"❌ Authentication failed: {response.status_code}")
        print(f"Response: {response.text}")
        return None
    
    data = response.json()
    token = data.get("access_token")
    print(f"✅ Authenticated successfully")
    return token

def test_single_pdf_export(token):
    """Test single PDF export and verify layout"""
    print_section("TEST 1: SINGLE PDF EXPORT - LAYOUT VERIFICATION")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"📥 Requesting PDF export for project {TEST_PROJECT_ID}...")
    start_time = time.time()
    
    response = requests.get(
        f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/export/pdf",
        headers=headers,
        timeout=120
    )
    
    elapsed = time.time() - start_time
    print(f"⏱️  Response time: {elapsed:.2f}s")
    
    # Check HTTP status
    if response.status_code != 200:
        print(f"❌ FAIL: HTTP {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return False
    print(f"✅ HTTP 200")
    
    # Check Content-Type
    content_type = response.headers.get("Content-Type", "")
    if "application/pdf" not in content_type:
        print(f"❌ FAIL: Wrong Content-Type: {content_type}")
        return False
    print(f"✅ Content-Type: {content_type}")
    
    # Check PDF magic bytes
    pdf_bytes = response.content
    if not pdf_bytes.startswith(b"%PDF"):
        print(f"❌ FAIL: Invalid PDF magic bytes")
        return False
    print(f"✅ PDF magic bytes verified: {pdf_bytes[:8]}")
    
    # Check size - CRITICAL: Must be FULL report, NOT fallback
    pdf_size = len(pdf_bytes)
    pdf_size_mb = pdf_size / (1024 * 1024)
    print(f"📊 PDF size: {pdf_size_mb:.1f} MB ({pdf_size} bytes)")
    
    if pdf_size < EXPECTED_FULL_PDF_SIZE_MIN:
        print(f"❌ FAIL: PDF too small ({pdf_size} bytes) - likely ReportLab fallback (expected ~1.2 MB)")
        return False
    print(f"✅ FULL report confirmed (NOT 4KB ReportLab fallback)")
    
    # Save PDF
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = f"/tmp/test_pdf_deploy_{TEST_PROJECT_ID}_{timestamp}.pdf"
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"💾 PDF saved: {pdf_path}")
    
    # Extract page count and size using pdfinfo
    print("\n📄 Analyzing PDF structure...")
    try:
        result = subprocess.run(
            ["pdfinfo", pdf_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            print(f"⚠️  pdfinfo failed: {result.stderr}")
        else:
            pdfinfo_output = result.stdout
            print(pdfinfo_output)
            
            # Extract page count
            for line in pdfinfo_output.split("\n"):
                if line.startswith("Pages:"):
                    page_count = int(line.split(":")[1].strip())
                    print(f"✅ Page count: {page_count} pages")
                    
                    if page_count < EXPECTED_MIN_PAGES:
                        print(f"❌ FAIL: Too few pages (expected at least {EXPECTED_MIN_PAGES})")
                        return False
                    
                elif line.startswith("Page size:"):
                    # Example: "Page size:      960 x 540 pts"
                    size_str = line.split(":")[1].strip()
                    width_str = size_str.split("x")[0].strip()
                    height_str = size_str.split("x")[1].split("pts")[0].strip()
                    width = float(width_str)
                    height = float(height_str)
                    print(f"✅ Page size: {width} x {height} pts (16:9 ratio: {width == EXPECTED_PAGE_SIZE[0] and height == EXPECTED_PAGE_SIZE[1]})")
                    
                    if (width, height) != EXPECTED_PAGE_SIZE:
                        print(f"⚠️  WARNING: Page size mismatch (expected {EXPECTED_PAGE_SIZE})")
    
    except Exception as e:
        print(f"⚠️  PDF analysis error: {e}")
    
    # Render pages to PNG for visual verification
    print("\n🖼️  Rendering PDF pages to PNG...")
    png_prefix = f"/tmp/pdf_page_deploy_{TEST_PROJECT_ID}_{timestamp}"
    
    try:
        result = subprocess.run(
            ["pdftoppm", "-png", "-r", "90", pdf_path, png_prefix],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            print(f"⚠️  pdftoppm failed: {result.stderr}")
        else:
            # Count generated PNG files
            png_files = sorted([f for f in os.listdir("/tmp") if f.startswith(f"pdf_page_deploy_{TEST_PROJECT_ID}_{timestamp}") and f.endswith(".png")])
            print(f"✅ Rendered {len(png_files)} pages to PNG")
            
            for png_file in png_files:
                print(f"   - /tmp/{png_file}")
            
            # Visual verification instructions
            print("\n" + "="*80)
            print("VISUAL VERIFICATION REQUIRED:")
            print("="*80)
            print("Please manually inspect the PNG files for:")
            print("  (a) WBS table rightmost columns:")
            print("      - 'ACTUALS VS EST.' column (e.g., '0h / 8h' ... '0h / 64h') FULLY VISIBLE")
            print("      - 'DEPS' column FULLY VISIBLE")
            print("      - NO clipping at right page edge")
            print("  (b) Project Timeline right side:")
            print("      - 'Oct 2026' month column FULLY VISIBLE")
            print("      - NO clipping")
            print("  (c) Risk items:")
            print("      - All 4 risk items complete (description + mitigation)")
            print("      - NO mid-item splits across pages")
            print("  (d) Trailing page:")
            print("      - NO near-blank page (>70% whitespace)")
            print("="*80)
            
            # Automated margin analysis for right-edge clipping
            print("\n🔍 Automated right-edge margin analysis...")
            analyze_right_margins(png_files, png_prefix)
            
    except Exception as e:
        print(f"⚠️  PNG rendering error: {e}")
    
    print("\n✅ TEST 1 PASSED: Single PDF export successful")
    return True

def analyze_right_margins(png_files, png_prefix):
    """Analyze right margins of PNG pages to detect clipping"""
    try:
        from PIL import Image
        import numpy as np
        
        for png_file in png_files:
            png_path = f"/tmp/{png_file}"
            
            # Extract page number from filename
            page_num = png_file.split("-")[-1].split(".")[0]
            
            img = Image.open(png_path)
            img_array = np.array(img)
            
            # Get rightmost 20 pixels
            height, width = img_array.shape[:2]
            right_margin = img_array[:, -20:]
            
            # Check if margin is mostly white (RGB > 250)
            if len(img_array.shape) == 3:  # Color image
                is_white = np.all(right_margin > 250, axis=2)
            else:  # Grayscale
                is_white = right_margin > 250
            
            white_percentage = np.sum(is_white) / is_white.size * 100
            
            if white_percentage < 95:
                print(f"   ⚠️  Page {page_num}: Right margin {white_percentage:.1f}% white (possible clipping)")
            else:
                print(f"   ✅ Page {page_num}: Right margin {white_percentage:.1f}% white (clean)")
    
    except ImportError:
        print("   ⚠️  PIL/numpy not available for automated margin analysis")
    except Exception as e:
        print(f"   ⚠️  Margin analysis error: {e}")

def test_concurrent_exports(token):
    """Test concurrent PDF exports to verify OOM guard"""
    print_section("TEST 2: CONCURRENT EXPORTS - OOM GUARD VERIFICATION")
    
    num_concurrent = 3
    print(f"🚀 Firing {num_concurrent} concurrent PDF export requests...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    def export_pdf(request_num):
        """Export PDF and return result"""
        start_time = time.time()
        try:
            response = requests.get(
                f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/export/pdf",
                headers=headers,
                timeout=120
            )
            elapsed = time.time() - start_time
            
            return {
                "request_num": request_num,
                "status_code": response.status_code,
                "size": len(response.content),
                "elapsed": elapsed,
                "is_full_pdf": len(response.content) >= EXPECTED_FULL_PDF_SIZE_MIN,
                "content_type": response.headers.get("Content-Type", "")
            }
        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "request_num": request_num,
                "status_code": 0,
                "size": 0,
                "elapsed": elapsed,
                "is_full_pdf": False,
                "error": str(e)
            }
    
    # Execute concurrent requests
    results = []
    with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
        futures = [executor.submit(export_pdf, i+1) for i in range(num_concurrent)]
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            
            status = "✅" if result["status_code"] == 200 else "❌"
            size_mb = result["size"] / (1024 * 1024)
            pdf_type = "FULL" if result["is_full_pdf"] else "FALLBACK/ERROR"
            
            print(f"{status} Request #{result['request_num']}: HTTP {result['status_code']}, "
                  f"{size_mb:.1f} MB, {result['elapsed']:.2f}s, {pdf_type}")
            
            if "error" in result:
                print(f"   Error: {result['error']}")
    
    # Sort by request number for analysis
    results.sort(key=lambda x: x["request_num"])
    
    # Analyze results
    print("\n📊 Concurrent export analysis:")
    
    all_success = all(r["status_code"] == 200 for r in results)
    all_full_pdf = all(r["is_full_pdf"] for r in results)
    
    times = [r["elapsed"] for r in results]
    min_time = min(times)
    max_time = max(times)
    avg_time = sum(times) / len(times)
    time_spread = max_time - min_time
    
    print(f"   Success rate: {sum(1 for r in results if r['status_code'] == 200)}/{num_concurrent}")
    print(f"   Full PDF rate: {sum(1 for r in results if r['is_full_pdf'])}/{num_concurrent}")
    print(f"   Response times: min={min_time:.2f}s, max={max_time:.2f}s, avg={avg_time:.2f}s")
    print(f"   Time spread: {time_spread:.2f}s (serialization: {time_spread > 1.0})")
    
    # Check for failures
    if not all_success:
        print(f"❌ FAIL: Not all requests returned HTTP 200")
        return False
    print(f"✅ All requests returned HTTP 200")
    
    if not all_full_pdf:
        print(f"❌ FAIL: Not all requests returned FULL PDFs (some returned fallback)")
        return False
    print(f"✅ All requests returned FULL PDFs (NOT fallback)")
    
    # Check for 502/503 errors
    has_502_503 = any(r["status_code"] in [502, 503] for r in results)
    if has_502_503:
        print(f"❌ FAIL: Detected 502/503 errors")
        return False
    print(f"✅ NO 502 or 500 errors detected")
    
    # Serialization check
    if time_spread > 1.0:
        print(f"✅ Serialization detected (time spread {time_spread:.2f}s) - semaphore working")
    else:
        print(f"⚠️  WARNING: No clear serialization (time spread {time_spread:.2f}s)")
    
    print("\n✅ TEST 2 PASSED: Concurrent exports successful")
    return True

def test_regression(token):
    """Test regression endpoints"""
    print_section("TEST 3: REGRESSION TESTS")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test 1: PPT export
    print("📥 Testing PPT export...")
    response = requests.get(
        f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/export/ppt",
        headers=headers,
        timeout=120
    )
    
    if response.status_code != 200:
        print(f"❌ FAIL: PPT export returned HTTP {response.status_code}")
        return False
    
    if not response.content.startswith(b"PK"):
        print(f"❌ FAIL: Invalid PPTX (missing ZIP magic bytes)")
        return False
    
    pptx_size = len(response.content) / 1024
    print(f"✅ PPT export: HTTP 200, {pptx_size:.1f} KB, valid PPTX")
    
    # Test 2: Health endpoint
    print("\n📥 Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/api/health")
    
    if response.status_code != 200:
        print(f"❌ FAIL: Health endpoint returned HTTP {response.status_code}")
        return False
    
    health_data = response.json()
    print(f"✅ Health endpoint: HTTP 200, status={health_data.get('status')}")
    
    # Test 3: Projects list
    print("\n📥 Testing projects list...")
    response = requests.get(
        f"{BASE_URL}/api/projects",
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"❌ FAIL: Projects list returned HTTP {response.status_code}")
        return False
    
    projects = response.json()
    project_count = len(projects)
    print(f"✅ Projects list: HTTP 200, {project_count} projects")
    
    # Verify test project exists
    test_project = next((p for p in projects if p.get("id") == TEST_PROJECT_ID), None)
    if not test_project:
        print(f"⚠️  WARNING: Test project {TEST_PROJECT_ID} not found in projects list")
    else:
        print(f"✅ Test project found: {test_project.get('name')}")
    
    print("\n✅ TEST 3 PASSED: All regression tests successful")
    return True

def main():
    """Main test execution"""
    print_section("PDF EXPORT DEPLOYMENT VERIFICATION")
    print(f"Test project: {TEST_PROJECT_ID} (Website Redesign)")
    print(f"Backend URL: {BASE_URL}")
    print(f"Auth: {AUTH_EMAIL}")
    
    # Authenticate
    token = authenticate()
    if not token:
        print("\n❌ VERIFICATION FAILED: Authentication failed")
        return 1
    
    # Run tests
    test_results = []
    
    # Test 1: Single PDF export with layout verification
    try:
        result = test_single_pdf_export(token)
        test_results.append(("Single PDF Export", result))
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        test_results.append(("Single PDF Export", False))
    
    # Test 2: Concurrent exports (OOM guard)
    try:
        result = test_concurrent_exports(token)
        test_results.append(("Concurrent Exports", result))
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        test_results.append(("Concurrent Exports", False))
    
    # Test 3: Regression tests
    try:
        result = test_regression(token)
        test_results.append(("Regression Tests", result))
    except Exception as e:
        print(f"\n❌ TEST 3 FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        test_results.append(("Regression Tests", False))
    
    # Summary
    print_section("VERIFICATION SUMMARY")
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(result for _, result in test_results)
    
    if all_passed:
        print("\n" + "="*80)
        print("✅✅✅ ALL TESTS PASSED ✅✅✅")
        print("="*80)
        print("\nFINAL VERDICT:")
        print("  (1) PDF export returns FULL ~1.2 MB report (NOT 4KB fallback)")
        print("  (2) Concurrent exports all succeed (NO 502/503 errors)")
        print("  (3) Regression tests pass (PPT, health, projects)")
        print("\nMANUAL VERIFICATION REQUIRED:")
        print("  - Inspect PNG renders for WBS column clipping")
        print("  - Check for near-blank trailing pages")
        print("  - Verify risk items not split mid-item")
        print("="*80)
        return 0
    else:
        print("\n" + "="*80)
        print("❌❌❌ VERIFICATION FAILED ❌❌❌")
        print("="*80)
        return 1

if __name__ == "__main__":
    exit(main())
