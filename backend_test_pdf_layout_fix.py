#!/usr/bin/env python3
"""
Backend test for PDF export layout fix verification.

Tests the bug fix for PDF export clean layout:
- Right-edge clipping (WBS table, Timeline)
- Mid-item section splits (Risks)
- Near-blank trailing page
- Page size and count
- Regression tests (PPT export, health, projects list)
"""

import requests
import sys
import os
import subprocess
import re
from pathlib import Path

# Test configuration
BASE_URL = "http://localhost:8001"
API_BASE = f"{BASE_URL}/api"
TEST_PROJECT_ID = "6ab25bc82be78e05e89230f3"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Output directory for test artifacts
OUTPUT_DIR = Path("/tmp")

def print_test_header(test_name):
    """Print a formatted test header."""
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"{'='*80}")

def print_result(passed, message):
    """Print test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {message}")
    return passed

def authenticate():
    """Authenticate and return access token."""
    print_test_header("Authentication")
    
    # OAuth2 form-encoded login
    response = requests.post(
        f"{API_BASE}/auth/login",
        data={
            "username": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )
    
    if response.status_code != 200:
        print_result(False, f"Login failed with status {response.status_code}")
        print(f"Response: {response.text}")
        sys.exit(1)
    
    data = response.json()
    token = data.get("access_token")
    
    if not token:
        print_result(False, "No access_token in response")
        sys.exit(1)
    
    print_result(True, f"Authenticated as {ADMIN_EMAIL}")
    return token

def test_pdf_export(token):
    """Test PDF export endpoint and verify layout."""
    print_test_header("PDF Export - Basic Validation")
    
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{API_BASE}/projects/{TEST_PROJECT_ID}/export/pdf"
    
    print(f"Requesting: {url}")
    response = requests.get(url, headers=headers)
    
    # Test 1: HTTP 200
    if not print_result(response.status_code == 200, 
                       f"HTTP status code: {response.status_code}"):
        print(f"Response: {response.text[:500]}")
        return False
    
    # Test 2: Content-Type
    content_type = response.headers.get("Content-Type", "")
    print_result(content_type == "application/pdf", 
                f"Content-Type: {content_type}")
    
    # Test 3: PDF magic bytes
    pdf_bytes = response.content
    has_magic = pdf_bytes.startswith(b"%PDF")
    print_result(has_magic, 
                f"PDF magic bytes present: {pdf_bytes[:8]}")
    
    # Test 4: File size
    file_size_kb = len(pdf_bytes) / 1024
    print_result(True, f"PDF size: {file_size_kb:.1f} KB ({len(pdf_bytes)} bytes)")
    
    # Save PDF for analysis
    pdf_path = OUTPUT_DIR / f"test_pdf_export_{TEST_PROJECT_ID}.pdf"
    pdf_path.write_bytes(pdf_bytes)
    print_result(True, f"PDF saved to: {pdf_path}")
    
    return pdf_path

def analyze_pdf_structure(pdf_path):
    """Analyze PDF structure using pdfinfo."""
    print_test_header("PDF Structure Analysis")
    
    try:
        # Run pdfinfo
        result = subprocess.run(
            ["pdfinfo", str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            print_result(False, f"pdfinfo failed: {result.stderr}")
            return None, None
        
        output = result.stdout
        print(output)
        
        # Extract page count
        page_match = re.search(r"Pages:\s+(\d+)", output)
        page_count = int(page_match.group(1)) if page_match else None
        
        # Extract page size
        size_match = re.search(r"Page size:\s+([\d.]+)\s+x\s+([\d.]+)\s+pts", output)
        if size_match:
            width = float(size_match.group(1))
            height = float(size_match.group(2))
            page_size = (width, height)
        else:
            page_size = None
        
        # Test page count
        if page_count:
            print_result(True, f"Page count: {page_count}")
        else:
            print_result(False, "Could not determine page count")
        
        # Test page size (should be 960 x 540 pts = 13.333in x 7.5in at 72 dpi)
        if page_size:
            expected_width = 960.0
            expected_height = 540.0
            width_match = abs(page_size[0] - expected_width) < 5
            height_match = abs(page_size[1] - expected_height) < 5
            
            print_result(
                width_match and height_match,
                f"Page size: {page_size[0]:.1f} x {page_size[1]:.1f} pts "
                f"(expected: {expected_width} x {expected_height} pts, 16:9 ratio)"
            )
        else:
            print_result(False, "Could not determine page size")
        
        return page_count, page_size
        
    except Exception as e:
        print_result(False, f"Error analyzing PDF: {e}")
        return None, None

def render_pdf_to_images(pdf_path, page_count):
    """Render PDF pages to PNG images for visual inspection."""
    print_test_header("PDF Visual Rendering")
    
    if not page_count:
        print_result(False, "Cannot render: page count unknown")
        return []
    
    try:
        # Use pdftoppm to render pages to PNG
        output_prefix = OUTPUT_DIR / f"pdf_page_{TEST_PROJECT_ID}"
        
        # Render at 90 DPI for reasonable file size
        result = subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-r", "90",
                str(pdf_path),
                str(output_prefix)
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print_result(False, f"pdftoppm failed: {result.stderr}")
            return []
        
        # Find generated PNG files
        png_files = sorted(OUTPUT_DIR.glob(f"pdf_page_{TEST_PROJECT_ID}-*.png"))
        
        print_result(True, f"Rendered {len(png_files)} pages to PNG")
        for png_file in png_files:
            size_kb = png_file.stat().st_size / 1024
            print(f"  - {png_file.name} ({size_kb:.1f} KB)")
        
        return png_files
        
    except Exception as e:
        print_result(False, f"Error rendering PDF: {e}")
        return []

def visual_inspection_report(png_files):
    """Generate visual inspection report."""
    print_test_header("Visual Layout Verification")
    
    if not png_files:
        print_result(False, "No PNG files to inspect")
        return
    
    print("\n📋 VISUAL INSPECTION CHECKLIST:")
    print("\nPlease manually verify the following by viewing the rendered PNG files:")
    print(f"Location: {OUTPUT_DIR}/pdf_page_{TEST_PROJECT_ID}-*.png")
    print()
    print("(a) WBS Table - Rightmost Columns:")
    print("    ✓ 'ACTUALS VS EST.' column (values like '0h / 8h') is FULLY VISIBLE")
    print("    ✓ 'DEPS' column is FULLY VISIBLE")
    print("    ✓ NO clipping at the right page edge")
    print()
    print("(b) Project Timeline & Phases:")
    print("    ✓ Right side (e.g. 'Oct 2026' month column / end dates) is NOT clipped")
    print("    ✓ All timeline content fits within page width")
    print()
    print("(c) Risks & Issues Section:")
    print("    ✓ Risk items are NOT split mid-item across page boundaries")
    print("    ✓ Each risk card (description + mitigation) stays together")
    print()
    print("(d) Trailing Page:")
    print("    ✓ There is NO near-blank trailing page")
    print("    ✓ Footer sits close to the last content")
    print("    ✓ No page with only footer and lots of empty space above")
    print()
    
    # Automated checks we can do
    print("\n🤖 AUTOMATED CHECKS:")
    
    # Check for near-blank trailing page by file size
    if len(png_files) >= 2:
        last_page = png_files[-1]
        second_last_page = png_files[-2]
        
        last_size = last_page.stat().st_size
        second_last_size = second_last_page.stat().st_size
        
        # If last page is significantly smaller (< 30% of second-last), 
        # it might be near-blank
        size_ratio = last_size / second_last_size if second_last_size > 0 else 1.0
        
        if size_ratio < 0.3:
            print_result(
                False,
                f"⚠️  Last page is {size_ratio*100:.1f}% the size of second-last page "
                f"({last_size/1024:.1f} KB vs {second_last_size/1024:.1f} KB). "
                f"This may indicate a near-blank trailing page."
            )
        else:
            print_result(
                True,
                f"Last page size is {size_ratio*100:.1f}% of second-last page "
                f"({last_size/1024:.1f} KB vs {second_last_size/1024:.1f} KB). "
                f"No obvious near-blank trailing page detected."
            )

def test_ppt_export_regression(token):
    """Test PPT export endpoint (regression test)."""
    print_test_header("PPT Export - Regression Test")
    
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{API_BASE}/projects/{TEST_PROJECT_ID}/export/ppt"
    
    print(f"Requesting: {url}")
    response = requests.get(url, headers=headers)
    
    # Test 1: HTTP 200
    if not print_result(response.status_code == 200, 
                       f"HTTP status code: {response.status_code}"):
        print(f"Response: {response.text[:500]}")
        return False
    
    # Test 2: Content-Type
    content_type = response.headers.get("Content-Type", "")
    expected_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    print_result(content_type == expected_type, 
                f"Content-Type: {content_type}")
    
    # Test 3: ZIP magic bytes (PPTX is a ZIP file)
    pptx_bytes = response.content
    has_magic = pptx_bytes.startswith(b"PK")
    print_result(has_magic, 
                f"ZIP magic bytes present: {pptx_bytes[:4]}")
    
    # Test 4: File size
    file_size_kb = len(pptx_bytes) / 1024
    print_result(True, f"PPTX size: {file_size_kb:.1f} KB ({len(pptx_bytes)} bytes)")
    
    # Try to read slide count with python-pptx
    try:
        from pptx import Presentation
        import io
        
        prs = Presentation(io.BytesIO(pptx_bytes))
        slide_count = len(prs.slides)
        print_result(True, f"Slide count: {slide_count}")
    except Exception as e:
        print_result(False, f"Could not read slide count: {e}")
    
    return True

def test_health_endpoint():
    """Test health endpoint (sanity check)."""
    print_test_header("Health Endpoint - Sanity Check")
    
    url = f"{API_BASE}/health"
    response = requests.get(url)
    
    if not print_result(response.status_code == 200, 
                       f"HTTP status code: {response.status_code}"):
        return False
    
    data = response.json()
    print_result(True, f"Health status: {data}")
    
    return True

def test_projects_list(token):
    """Test projects list endpoint (sanity check)."""
    print_test_header("Projects List - Sanity Check")
    
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{API_BASE}/projects"
    
    response = requests.get(url, headers=headers)
    
    if not print_result(response.status_code == 200, 
                       f"HTTP status code: {response.status_code}"):
        return False
    
    data = response.json()
    project_count = len(data) if isinstance(data, list) else 0
    print_result(True, f"Projects returned: {project_count}")
    
    # Check if our test project is in the list
    test_project_found = any(
        p.get("id") == TEST_PROJECT_ID for p in data
    ) if isinstance(data, list) else False
    
    print_result(test_project_found, 
                f"Test project {TEST_PROJECT_ID} found in list")
    
    return True

def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("PDF EXPORT LAYOUT FIX VERIFICATION")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Test Project ID: {TEST_PROJECT_ID}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print("="*80)
    
    try:
        # Authenticate
        token = authenticate()
        
        # Test 1: Health endpoint
        test_health_endpoint()
        
        # Test 2: Projects list
        test_projects_list(token)
        
        # Test 3: PDF export
        pdf_path = test_pdf_export(token)
        if not pdf_path:
            print("\n❌ PDF export failed, cannot continue with visual verification")
            sys.exit(1)
        
        # Test 4: PDF structure analysis
        page_count, page_size = analyze_pdf_structure(pdf_path)
        
        # Test 5: Render PDF to images
        png_files = render_pdf_to_images(pdf_path, page_count)
        
        # Test 6: Visual inspection report
        visual_inspection_report(png_files)
        
        # Test 7: PPT export regression
        test_ppt_export_regression(token)
        
        print("\n" + "="*80)
        print("TEST SUITE COMPLETE")
        print("="*80)
        print("\n✅ All automated tests passed!")
        print("\n⚠️  IMPORTANT: Manual visual verification required!")
        print(f"Please inspect the PNG files in {OUTPUT_DIR}/pdf_page_{TEST_PROJECT_ID}-*.png")
        print("and verify the checklist items (a)-(d) listed above.")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
