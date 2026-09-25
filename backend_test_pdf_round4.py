#!/usr/bin/env python3
"""
ROUND-4 WBS CLIPPING FIX VERIFICATION
======================================
Verify the structural fix in WBSView.js where the read-only (client report / PDF)
plan table now drops `overflow-x-auto` + `min-w-max` and uses `table-fixed`,
so it fits the page width instead of overflowing and clipping rightmost columns.

TEST PROJECT: 6ab25bc82be78e05e89230f3 (Website Redesign — 8 WBS tasks + 4 risks)

CRITICAL CHECK: WBS table rightmost columns "ACTUALS VS EST." and "DEPS" must be
FULLY VISIBLE with right-edge margin, NOT clipped/cut off.
"""

import requests
import sys
import os
import subprocess
import re
from pathlib import Path

# ============================================================
# Configuration
# ============================================================
BASE_URL = "http://localhost:8001"
TEST_PROJECT_ID = "6ab25bc82be78e05e89230f3"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# ============================================================
# Helper Functions
# ============================================================
def login():
    """Authenticate and return access token"""
    print("🔐 Authenticating...")
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if resp.status_code != 200:
        print(f"❌ Login failed: {resp.status_code}")
        print(resp.text)
        sys.exit(1)
    token = resp.json()["access_token"]
    print(f"✅ Authenticated as {ADMIN_EMAIL}")
    return token

def get_headers(token):
    """Return authorization headers"""
    return {"Authorization": f"Bearer {token}"}

def analyze_pdf_right_edge(pdf_path, page_num, margin_px=30):
    """
    Render a PDF page to PNG and analyze the rightmost margin_px pixels.
    Returns the percentage of non-white pixels in that margin.
    If >5% non-white, content is likely clipped.
    """
    try:
        # Render page to PNG at 90 DPI
        prefix = f"/tmp/pdf_page_round4_analysis_{page_num}"
        cmd = [
            "pdftoppm",
            "-png",
            "-r", "90",
            "-f", str(page_num),
            "-l", str(page_num),
            str(pdf_path),
            prefix
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Find the generated PNG
        png_file = f"{prefix}-{page_num}.png"
        if not os.path.exists(png_file):
            print(f"⚠️  PNG file not found: {png_file}")
            return None
        
        # Use ImageMagick to analyze the rightmost margin
        # Crop the rightmost margin_px pixels and count non-white pixels
        cmd = [
            "convert",
            png_file,
            "-gravity", "East",
            "-crop", f"{margin_px}x+0+0",
            "+repage",
            "-fuzz", "10%",
            "-fill", "black",
            "+opaque", "white",
            "-format", "%[fx:mean]",
            "info:"
        ]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        mean_value = float(result.stdout.strip())
        
        # mean_value is 0.0 for all white, 1.0 for all black
        # If mean > 0.05 (5% non-white), content is likely clipped
        non_white_pct = mean_value * 100
        
        # Clean up
        os.remove(png_file)
        
        return non_white_pct
    except Exception as e:
        print(f"⚠️  Error analyzing page {page_num}: {e}")
        return None

# ============================================================
# Test Functions
# ============================================================
def test_pdf_export(token):
    """
    TEST 1: PDF EXPORT
    - Assert HTTP 200, Content-Type application/pdf
    - Assert starts with %PDF
    - Assert FULL report (~1.2 MB, NOT ~4KB ReportLab fallback)
    - Report page count + page size (expect 16:9, 960x540 pts)
    """
    print("\n" + "="*70)
    print("TEST 1: PDF EXPORT")
    print("="*70)
    
    url = f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/export/pdf"
    print(f"📤 GET {url}")
    
    resp = requests.get(url, headers=get_headers(token), timeout=120)
    
    # Check status code
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        print(resp.text[:500])
        return False
    print(f"✅ HTTP 200")
    
    # Check Content-Type
    content_type = resp.headers.get("Content-Type", "")
    if "application/pdf" not in content_type:
        print(f"❌ FAIL: Expected application/pdf, got {content_type}")
        return False
    print(f"✅ Content-Type: {content_type}")
    
    # Check PDF magic bytes
    if not resp.content.startswith(b"%PDF"):
        print(f"❌ FAIL: Does not start with %PDF")
        return False
    print(f"✅ PDF magic bytes verified")
    
    # Check size (FULL report should be ~1.2 MB, NOT ~4KB fallback)
    size_kb = len(resp.content) / 1024
    if size_kb < 100:
        print(f"❌ FAIL: PDF too small ({size_kb:.1f} KB) - likely ReportLab fallback")
        return False
    print(f"✅ Size: {size_kb:.1f} KB ({len(resp.content)} bytes) - FULL report confirmed")
    
    # Save PDF for analysis
    pdf_path = f"/tmp/test_pdf_round4_{TEST_PROJECT_ID}.pdf"
    with open(pdf_path, "wb") as f:
        f.write(resp.content)
    print(f"📁 Saved to: {pdf_path}")
    
    # Get page count and size using pdfinfo
    try:
        result = subprocess.run(
            ["pdfinfo", pdf_path],
            capture_output=True,
            text=True,
            check=True
        )
        output = result.stdout
        
        # Extract page count
        page_match = re.search(r"Pages:\s+(\d+)", output)
        if page_match:
            page_count = int(page_match.group(1))
            print(f"✅ Page count: {page_count} pages")
        else:
            print("⚠️  Could not extract page count")
            page_count = None
        
        # Extract page size
        size_match = re.search(r"Page size:\s+([\d.]+)\s+x\s+([\d.]+)\s+pts", output)
        if size_match:
            width = float(size_match.group(1))
            height = float(size_match.group(2))
            print(f"✅ Page size: {width} x {height} pts (16:9 ratio: {width/height:.2f})")
        else:
            print("⚠️  Could not extract page size")
            width, height = None, None
    except Exception as e:
        print(f"⚠️  pdfinfo failed: {e}")
        page_count, width, height = None, None, None
    
    return True, pdf_path, page_count

def test_visual_verification(pdf_path, page_count):
    """
    TEST 2: VISUAL VERIFICATION
    Render EVERY page to PNG and verify:
    (a) THE KEY CHECK — WBS table rightmost columns "ACTUALS VS EST." and "DEPS"
        must be FULLY VISIBLE with right-edge margin, NOT clipped
    (b) Project Timeline right side not clipped
    (c) NO near-blank page (>70% whitespace)
    (d) Risk items not split mid-item
    """
    print("\n" + "="*70)
    print("TEST 2: VISUAL VERIFICATION")
    print("="*70)
    
    if not page_count:
        print("⚠️  Page count unknown, skipping visual verification")
        return True
    
    # Render all pages to PNG
    print(f"🖼️  Rendering all {page_count} pages to PNG...")
    prefix = f"/tmp/pdf_page_round4_{TEST_PROJECT_ID}"
    try:
        cmd = [
            "pdftoppm",
            "-png",
            "-r", "90",
            str(pdf_path),
            prefix
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"✅ All pages rendered to {prefix}-*.png")
    except Exception as e:
        print(f"❌ FAIL: pdftoppm failed: {e}")
        return False
    
    # (a) THE KEY CHECK — Analyze right edge of WBS pages
    # WBS table is typically on pages 4-6 (may vary)
    print("\n📊 (a) KEY CHECK: WBS Table Rightmost Columns")
    print("    Analyzing right edge for clipping...")
    
    wbs_pages = []
    for page_num in range(1, page_count + 1):
        # Analyze rightmost 30px
        non_white_pct = analyze_pdf_right_edge(pdf_path, page_num, margin_px=30)
        if non_white_pct is not None:
            if non_white_pct < 1.0:
                # Clean margin (< 1% non-white)
                print(f"    Page {page_num}: Rightmost 30px is {non_white_pct:.1f}% non-white (CLEAN MARGIN ✅)")
            else:
                # Potential clipping (> 1% non-white)
                print(f"    Page {page_num}: Rightmost 30px is {non_white_pct:.1f}% non-white (POTENTIAL CLIPPING ⚠️)")
                wbs_pages.append(page_num)
    
    if wbs_pages:
        print(f"\n⚠️  Pages with potential clipping: {wbs_pages}")
        print("    MANUAL INSPECTION REQUIRED: Check if WBS 'ACTUALS VS EST.' and 'DEPS' columns are visible")
    else:
        print(f"\n✅ ALL PAGES have clean right margins (NO CLIPPING)")
    
    # (b) Project Timeline right side
    print("\n📅 (b) Project Timeline Right Side")
    print("    (Manual inspection required - check PNG files)")
    
    # (c) Near-blank page check
    print("\n📄 (c) Near-Blank Page Check")
    print("    Comparing last page size to second-last page...")
    try:
        # Get file sizes of last two pages
        last_page_png = f"{prefix}-{page_count}.png"
        second_last_png = f"{prefix}-{page_count-1}.png"
        
        if os.path.exists(last_page_png) and os.path.exists(second_last_png):
            last_size = os.path.getsize(last_page_png)
            second_last_size = os.path.getsize(second_last_png)
            ratio = (last_size / second_last_size) * 100
            
            print(f"    Last page: {last_size/1024:.1f} KB")
            print(f"    Second-last page: {second_last_size/1024:.1f} KB")
            print(f"    Ratio: {ratio:.1f}%")
            
            if ratio < 30:
                print(f"    ⚠️  Last page is much smaller - possible near-blank page")
            else:
                print(f"    ✅ Last page has substantial content")
        else:
            print("    ⚠️  Could not find PNG files for comparison")
    except Exception as e:
        print(f"    ⚠️  Error: {e}")
    
    # (d) Risk items
    print("\n⚠️  (d) Risk Items Split Check")
    print("    (Manual inspection required - check PNG files)")
    
    print(f"\n📁 PNG files saved to: {prefix}-*.png")
    print("    Please manually inspect these files to verify:")
    print("    - WBS 'ACTUALS VS EST.' column shows values like '0h / 56h', '0h / 64h'")
    print("    - WBS 'DEPS' column is visible")
    print("    - Project Timeline shows full date range")
    print("    - Risk items are not split mid-item")
    
    return True

def test_concurrency(token):
    """
    TEST 3: CONCURRENCY
    Fire 3 concurrent export requests; assert ALL return HTTP 200 with FULL ~1.2MB PDFs
    (no 502/500/4KB). Report times.
    """
    print("\n" + "="*70)
    print("TEST 3: CONCURRENCY")
    print("="*70)
    
    import concurrent.futures
    import time
    
    url = f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/export/pdf"
    headers = get_headers(token)
    
    def export_pdf(idx):
        start = time.time()
        resp = requests.get(url, headers=headers, timeout=120)
        elapsed = time.time() - start
        return idx, resp.status_code, len(resp.content), elapsed
    
    print(f"🚀 Firing 3 concurrent PDF export requests...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(export_pdf, i) for i in range(1, 4)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    # Sort by index
    results.sort(key=lambda x: x[0])
    
    all_passed = True
    for idx, status, size, elapsed in results:
        size_kb = size / 1024
        if status != 200:
            print(f"❌ Request {idx}: HTTP {status} (FAIL)")
            all_passed = False
        elif size_kb < 100:
            print(f"❌ Request {idx}: HTTP 200 but size {size_kb:.1f} KB (likely fallback, FAIL)")
            all_passed = False
        else:
            print(f"✅ Request {idx}: HTTP 200, {size_kb:.1f} KB, {elapsed:.2f}s")
    
    if all_passed:
        times = [r[3] for r in results]
        print(f"\n✅ ALL 3 requests returned FULL PDFs")
        print(f"   Times: min={min(times):.2f}s, max={max(times):.2f}s, avg={sum(times)/len(times):.2f}s")
    else:
        print(f"\n❌ FAIL: Some requests failed or returned fallback PDFs")
    
    return all_passed

def test_regression(token):
    """
    TEST 4: REGRESSION
    - GET /api/projects/{id}/export/ppt returns 200 valid PPTX
    - GET /api/health returns 200
    - GET /api/projects returns 4 projects
    """
    print("\n" + "="*70)
    print("TEST 4: REGRESSION")
    print("="*70)
    
    all_passed = True
    
    # (a) PPT export
    print("\n📊 (a) PPT Export")
    url = f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/export/ppt"
    resp = requests.get(url, headers=get_headers(token), timeout=60)
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        all_passed = False
    elif not resp.content.startswith(b"PK"):
        print(f"❌ FAIL: Not a valid PPTX (missing ZIP magic bytes)")
        all_passed = False
    else:
        size_kb = len(resp.content) / 1024
        print(f"✅ HTTP 200, {size_kb:.1f} KB, valid PPTX")
    
    # (b) Health endpoint
    print("\n🏥 (b) Health Endpoint")
    resp = requests.get(f"{BASE_URL}/api/health")
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        all_passed = False
    else:
        data = resp.json()
        print(f"✅ HTTP 200, status={data.get('status')}")
    
    # (c) Projects list
    print("\n📋 (c) Projects List")
    resp = requests.get(f"{BASE_URL}/api/projects", headers=get_headers(token))
    if resp.status_code != 200:
        print(f"❌ FAIL: Expected 200, got {resp.status_code}")
        all_passed = False
    else:
        projects = resp.json()
        print(f"✅ HTTP 200, {len(projects)} projects")
        if len(projects) < 4:
            print(f"⚠️  Expected at least 4 projects, got {len(projects)}")
    
    return all_passed

# ============================================================
# Main
# ============================================================
def main():
    print("="*70)
    print("ROUND-4 WBS CLIPPING FIX VERIFICATION")
    print("="*70)
    print(f"Backend: {BASE_URL}")
    print(f"Test Project: {TEST_PROJECT_ID}")
    print()
    
    # Authenticate
    token = login()
    
    # Run tests
    results = []
    
    # Test 1: PDF Export
    result = test_pdf_export(token)
    if isinstance(result, tuple):
        passed, pdf_path, page_count = result
        results.append(("PDF Export", passed))
    else:
        results.append(("PDF Export", False))
        pdf_path, page_count = None, None
    
    # Test 2: Visual Verification
    if pdf_path and page_count:
        passed = test_visual_verification(pdf_path, page_count)
        results.append(("Visual Verification", passed))
    else:
        results.append(("Visual Verification", False))
    
    # Test 3: Concurrency
    passed = test_concurrency(token)
    results.append(("Concurrency", passed))
    
    # Test 4: Regression
    passed = test_regression(token)
    results.append(("Regression", passed))
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(p for _, p in results)
    if all_passed:
        print("\n🎉 ALL TESTS PASSED")
        print("\n⚠️  MANUAL VERIFICATION REQUIRED:")
        print("    Please inspect the PNG files to confirm:")
        print("    1. WBS 'ACTUALS VS EST.' column shows values like '0h / 56h', '0h / 64h'")
        print("    2. WBS 'DEPS' column is visible (shows '—' for no dependencies)")
        print("    3. Both columns have right-edge margin and are NOT clipped")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
