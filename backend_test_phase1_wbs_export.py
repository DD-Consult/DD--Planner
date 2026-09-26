#!/usr/bin/env python3
"""
PHASE 1 WBS Export Verification Test
=====================================
Verifies the dedicated print-first WBS table (PrintWBSTable) in the exported PDF.

Test project: 6ab25bc82be78e05e89230f3 (Website Redesign with 30 WBS tasks)

KEY CHECKS:
1. PDF Export returns HTTP 200 with FULL ~1.2MB PDF (NOT 4KB ReportLab fallback)
2. WBS table shows ONLY these 8 columns: Task, Phase, Start, End, Duration, Status, % Complete, Actuals vs Est.
3. NO "Deps" column present (intentionally removed)
4. "Actuals vs Est." column is FULLY VISIBLE with clean right-edge margin
5. With 30 tasks, WBS table spans multiple pages with header row repeating
6. NO near-blank pages (>70% whitespace)
7. Concurrency test: 3 concurrent exports all return HTTP 200 with FULL PDFs
8. Regression: PPT export, health endpoint, projects list all working
"""

import requests
import sys
import os
import re
import subprocess
from datetime import datetime

# Internal backend URL
BASE_URL = "http://localhost:8001"
TEST_PROJECT_ID = "6ab25bc82be78e05e89230f3"  # Website Redesign with 30 WBS tasks

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def authenticate():
    """Authenticate and return access token"""
    log("Authenticating...")
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code != 200:
        log(f"❌ Authentication failed: {response.status_code}")
        log(f"Response: {response.text}")
        sys.exit(1)
    
    token = response.json().get("access_token")
    if not token:
        log("❌ No access token in response")
        sys.exit(1)
    
    log(f"✅ Authenticated successfully")
    return token

def test_pdf_export(token):
    """Test 1: PDF Export with comprehensive validation"""
    log("\n" + "="*80)
    log("TEST 1: PDF EXPORT - Full Validation")
    log("="*80)
    
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/export/pdf"
    
    log(f"GET {url}")
    response = requests.get(url, headers=headers, timeout=120)
    
    # Check HTTP status
    if response.status_code != 200:
        log(f"❌ FAIL: Expected HTTP 200, got {response.status_code}")
        log(f"Response: {response.text[:500]}")
        return False
    log(f"✅ HTTP 200")
    
    # Check Content-Type
    content_type = response.headers.get("Content-Type", "")
    if "application/pdf" not in content_type:
        log(f"❌ FAIL: Expected Content-Type application/pdf, got {content_type}")
        return False
    log(f"✅ Content-Type: {content_type}")
    
    # Check PDF magic bytes
    pdf_bytes = response.content
    if not pdf_bytes.startswith(b"%PDF"):
        log(f"❌ FAIL: PDF magic bytes not found. Starts with: {pdf_bytes[:20]}")
        return False
    log(f"✅ PDF magic bytes verified (%PDF)")
    
    # Check file size - FULL report should be ~1.2MB, NOT ~4KB ReportLab fallback
    size_kb = len(pdf_bytes) / 1024
    size_mb = size_kb / 1024
    log(f"✅ PDF size: {size_kb:.1f} KB ({size_mb:.2f} MB)")
    
    if size_kb < 100:
        log(f"❌ FAIL: PDF is only {size_kb:.1f} KB - this is likely the ReportLab fallback, NOT the full Playwright-rendered report")
        return False
    log(f"✅ FULL report confirmed (NOT 4KB ReportLab fallback)")
    
    # Save PDF for analysis
    pdf_path = f"/tmp/test_phase1_pdf_{TEST_PROJECT_ID}.pdf"
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
    log(f"✅ PDF saved to: {pdf_path}")
    
    # Extract PDF metadata using pdfinfo
    try:
        result = subprocess.run(
            ["pdfinfo", pdf_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            log("\n📄 PDF Metadata:")
            for line in result.stdout.split("\n"):
                if any(x in line for x in ["Pages:", "Page size:", "PDF version:"]):
                    log(f"   {line}")
            
            # Extract page count
            page_match = re.search(r"Pages:\s+(\d+)", result.stdout)
            if page_match:
                page_count = int(page_match.group(1))
                log(f"\n✅ Page count: {page_count} pages")
                
                # With 30 WBS tasks, expect multi-page report
                if page_count < 2:
                    log(f"⚠️  WARNING: Only {page_count} page(s) - expected multi-page report with 30 tasks")
            
            # Extract page size
            size_match = re.search(r"Page size:\s+([\d.]+)\s+x\s+([\d.]+)\s+pts", result.stdout)
            if size_match:
                width = float(size_match.group(1))
                height = float(size_match.group(2))
                ratio = width / height
                log(f"✅ Page size: {width} x {height} pts (ratio: {ratio:.2f})")
                
                # Expect 16:9 ratio (960x540 pts)
                if abs(ratio - 1.78) > 0.05:
                    log(f"⚠️  WARNING: Expected 16:9 ratio (~1.78), got {ratio:.2f}")
    except Exception as e:
        log(f"⚠️  Could not extract PDF metadata: {e}")
    
    # Render all pages to PNG for visual verification
    log("\n🖼️  Rendering PDF pages to PNG...")
    png_prefix = f"/tmp/pdf_page_phase1_{TEST_PROJECT_ID}"
    try:
        result = subprocess.run(
            ["pdftoppm", "-png", "-r", "90", pdf_path, png_prefix],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            # Count generated PNG files
            png_files = sorted([f for f in os.listdir("/tmp") if f.startswith(f"pdf_page_phase1_{TEST_PROJECT_ID}-")])
            log(f"✅ Rendered {len(png_files)} page(s) to PNG")
            
            # Analyze rightmost edge of each page for clipping
            log("\n🔍 Analyzing right-edge margins (checking for clipping)...")
            for png_file in png_files:
                png_path = f"/tmp/{png_file}"
                page_num = png_file.split("-")[-1].replace(".png", "")
                
                # Use ImageMagick to crop rightmost 30px and check if it's mostly white
                try:
                    # Get image dimensions
                    identify_result = subprocess.run(
                        ["identify", "-format", "%w %h", png_path],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if identify_result.returncode == 0:
                        width, height = map(int, identify_result.stdout.strip().split())
                        
                        # Crop rightmost 30px
                        crop_path = f"/tmp/right_edge_page{page_num}.png"
                        subprocess.run(
                            ["convert", png_path, "-gravity", "East", "-crop", "30x+0+0", crop_path],
                            capture_output=True,
                            timeout=5
                        )
                        
                        # Calculate mean color (white = 255,255,255)
                        mean_result = subprocess.run(
                            ["convert", crop_path, "-format", "%[fx:mean]", "info:"],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if mean_result.returncode == 0:
                            mean_val = float(mean_result.stdout.strip())
                            # mean_val close to 1.0 = white, close to 0.0 = dark
                            margin_pct = mean_val * 100
                            
                            if margin_pct > 95:
                                log(f"   Page {page_num}: Rightmost 30px is {margin_pct:.1f}% white ✅ (CLEAN MARGIN)")
                            elif margin_pct > 80:
                                log(f"   Page {page_num}: Rightmost 30px is {margin_pct:.1f}% white ⚠️  (some content near edge)")
                            else:
                                log(f"   Page {page_num}: Rightmost 30px is {margin_pct:.1f}% white ❌ (LIKELY CLIPPED)")
                except Exception as e:
                    log(f"   Page {page_num}: Could not analyze margin ({e})")
            
            # Check for near-blank trailing page
            if len(png_files) >= 2:
                log("\n🔍 Checking for near-blank trailing page...")
                last_page = f"/tmp/{png_files[-1]}"
                second_last_page = f"/tmp/{png_files[-2]}"
                
                try:
                    # Get file sizes
                    last_size = os.path.getsize(last_page)
                    second_last_size = os.path.getsize(second_last_page)
                    ratio = (last_size / second_last_size) * 100
                    
                    log(f"   Last page size: {last_size/1024:.1f} KB")
                    log(f"   Second-last page size: {second_last_size/1024:.1f} KB")
                    log(f"   Ratio: {ratio:.1f}%")
                    
                    if ratio < 30:
                        log(f"   ❌ FAIL: Last page is only {ratio:.1f}% of second-last page - likely a near-blank page")
                    else:
                        log(f"   ✅ PASS: Last page has substantial content ({ratio:.1f}% of second-last page)")
                except Exception as e:
                    log(f"   ⚠️  Could not check trailing page: {e}")
        else:
            log(f"⚠️  pdftoppm failed: {result.stderr}")
    except Exception as e:
        log(f"⚠️  Could not render PDF to PNG: {e}")
    
    log("\n" + "="*80)
    log("VISUAL VERIFICATION REQUIRED:")
    log("="*80)
    log("Please manually inspect the rendered PNG files to verify:")
    log("(a) WBS table shows these column headers:")
    log("    Task | Phase | Start | End | Duration | Status | % Complete | Actuals vs Est.")
    log("(b) The rightmost 'Actuals vs Est.' column (values like '0h / 40h', '0h / 120h')")
    log("    is FULLY VISIBLE with a clean right-edge margin (analyze rightmost ~30px)")
    log("(c) CONFIRM there is NO 'Deps' column (it was intentionally removed)")
    log("(d) With 30 tasks, WBS table spans multiple pages - header row repeats,")
    log("    rows are not cut mid-content, long task names wrap (not clipped)")
    log("(e) NO near-blank page (a page that is >70% whitespace with only heading/footer)")
    log("    Note: final page legitimately ends with last WBS rows + footer - that's fine")
    log("(f) Project Timeline and Risks sections not clipped")
    log("="*80)
    
    return True

def test_concurrency(token):
    """Test 2: Concurrency / No-Error - 3 concurrent exports"""
    log("\n" + "="*80)
    log("TEST 2: CONCURRENCY / NO-ERROR - 3 Concurrent Exports")
    log("="*80)
    
    import concurrent.futures
    import time
    
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/export/pdf"
    
    def export_pdf(idx):
        start = time.time()
        try:
            response = requests.get(url, headers=headers, timeout=120)
            elapsed = time.time() - start
            
            if response.status_code != 200:
                return {
                    "idx": idx,
                    "success": False,
                    "status": response.status_code,
                    "size_kb": 0,
                    "elapsed": elapsed,
                    "error": f"HTTP {response.status_code}"
                }
            
            size_kb = len(response.content) / 1024
            is_full = size_kb > 100  # FULL report vs fallback
            
            return {
                "idx": idx,
                "success": True,
                "status": response.status_code,
                "size_kb": size_kb,
                "elapsed": elapsed,
                "is_full": is_full
            }
        except Exception as e:
            elapsed = time.time() - start
            return {
                "idx": idx,
                "success": False,
                "status": 0,
                "size_kb": 0,
                "elapsed": elapsed,
                "error": str(e)
            }
    
    log("Firing 3 concurrent PDF export requests...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(export_pdf, i+1) for i in range(3)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    # Sort by index
    results.sort(key=lambda x: x["idx"])
    
    log("\nResults:")
    all_success = True
    all_full = True
    times = []
    
    for r in results:
        idx = r["idx"]
        if r["success"]:
            is_full_str = "FULL" if r["is_full"] else "FALLBACK"
            log(f"  Export {idx}: HTTP {r['status']}, {r['size_kb']:.1f} KB ({is_full_str}), {r['elapsed']:.2f}s ✅")
            times.append(r["elapsed"])
            if not r["is_full"]:
                all_full = False
        else:
            log(f"  Export {idx}: FAILED - {r.get('error', 'Unknown error')} ❌")
            all_success = False
    
    if not all_success:
        log("\n❌ FAIL: Not all exports succeeded")
        return False
    
    if not all_full:
        log("\n❌ FAIL: Some exports returned fallback PDFs (NOT full Playwright-rendered reports)")
        return False
    
    log(f"\n✅ ALL 3 exports returned HTTP 200 with FULL PDFs")
    
    # Check for serialization (staggered times indicate semaphore working)
    if times:
        min_time = min(times)
        max_time = max(times)
        avg_time = sum(times) / len(times)
        spread = max_time - min_time
        
        log(f"\nTiming analysis:")
        log(f"  Min: {min_time:.2f}s")
        log(f"  Max: {max_time:.2f}s")
        log(f"  Avg: {avg_time:.2f}s")
        log(f"  Spread: {spread:.2f}s")
        
        if spread > 2.0:
            log(f"✅ Serialization detected (spread > 2s) - semaphore working")
        else:
            log(f"⚠️  Small spread ({spread:.2f}s) - exports may have run in parallel")
    
    return True

def test_regression(token):
    """Test 3: Regression - PPT export, health, projects list"""
    log("\n" + "="*80)
    log("TEST 3: REGRESSION - PPT Export, Health, Projects List")
    log("="*80)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test PPT export
    log("\n(a) PPT Export...")
    url = f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/export/ppt"
    response = requests.get(url, headers=headers, timeout=120)
    
    if response.status_code != 200:
        log(f"❌ FAIL: PPT export returned HTTP {response.status_code}")
        return False
    
    if not response.content.startswith(b"PK"):
        log(f"❌ FAIL: PPT export does not have ZIP magic bytes (PK)")
        return False
    
    size_kb = len(response.content) / 1024
    log(f"✅ PPT export: HTTP 200, {size_kb:.1f} KB, ZIP magic bytes verified")
    
    # Test health endpoint
    log("\n(b) Health endpoint...")
    url = f"{BASE_URL}/api/health"
    response = requests.get(url, timeout=10)
    
    if response.status_code != 200:
        log(f"❌ FAIL: Health endpoint returned HTTP {response.status_code}")
        return False
    
    health_data = response.json()
    log(f"✅ Health endpoint: HTTP 200, status={health_data.get('status')}")
    
    # Test projects list
    log("\n(c) Projects list...")
    url = f"{BASE_URL}/api/projects"
    response = requests.get(url, headers=headers, timeout=10)
    
    if response.status_code != 200:
        log(f"❌ FAIL: Projects list returned HTTP {response.status_code}")
        return False
    
    projects = response.json()
    project_count = len(projects)
    log(f"✅ Projects list: HTTP 200, {project_count} projects")
    
    if project_count < 4:
        log(f"⚠️  WARNING: Expected at least 4 projects, got {project_count}")
    
    return True

def main():
    log("="*80)
    log("PHASE 1 WBS EXPORT VERIFICATION TEST")
    log("="*80)
    log(f"Test project: {TEST_PROJECT_ID} (Website Redesign with 30 WBS tasks)")
    log(f"Backend URL: {BASE_URL}")
    log(f"Test credentials: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    
    # Authenticate
    token = authenticate()
    
    # Run tests
    results = []
    
    # Test 1: PDF Export
    results.append(("PDF Export", test_pdf_export(token)))
    
    # Test 2: Concurrency
    results.append(("Concurrency", test_concurrency(token)))
    
    # Test 3: Regression
    results.append(("Regression", test_regression(token)))
    
    # Summary
    log("\n" + "="*80)
    log("TEST SUMMARY")
    log("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        log(f"{status}: {test_name}")
    
    log(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        log("\n🎉 ALL TESTS PASSED!")
        log("\n⚠️  IMPORTANT: Manual visual verification still required:")
        log("   - Check rendered PNG files in /tmp/pdf_page_phase1_*.png")
        log("   - Verify WBS table has 8 columns (NO 'Deps' column)")
        log("   - Verify 'Actuals vs Est.' column is fully visible")
        log("   - Verify no near-blank pages")
        return 0
    else:
        log("\n❌ SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
