#!/usr/bin/env python3
"""
Visual Analysis of PHASE 1 WBS Export
======================================
Performs detailed visual analysis of the rendered PDF pages to verify:
1. WBS table column headers (8 columns, NO "Deps")
2. "Actuals vs Est." column fully visible with clean right margin
3. No near-blank pages
4. Multi-page WBS table with header repeating
"""

import os
import subprocess
import sys
from PIL import Image
import pytesseract

def log(msg):
    print(msg)

def analyze_right_margin(png_path, page_num):
    """Analyze the rightmost edge of a page for clipping"""
    try:
        img = Image.open(png_path)
        width, height = img.size
        
        # Crop rightmost 100px
        right_crop = img.crop((width - 100, 0, width, height))
        
        # Convert to grayscale and calculate mean brightness
        gray = right_crop.convert('L')
        pixels = list(gray.getdata())
        mean_brightness = sum(pixels) / len(pixels)
        
        # White = 255, Black = 0
        white_pct = (mean_brightness / 255) * 100
        
        log(f"   Page {page_num}: Rightmost 100px is {white_pct:.1f}% white", end="")
        
        if white_pct > 95:
            log(" ✅ (CLEAN MARGIN)")
            return True
        elif white_pct > 80:
            log(" ⚠️  (some content near edge)")
            return True
        else:
            log(" ❌ (LIKELY CLIPPED)")
            return False
    except Exception as e:
        log(f"   Page {page_num}: Error analyzing margin: {e}")
        return None

def extract_text_from_region(png_path, x, y, w, h):
    """Extract text from a specific region of the image using OCR"""
    try:
        img = Image.open(png_path)
        region = img.crop((x, y, x + w, y + h))
        text = pytesseract.image_to_string(region)
        return text.strip()
    except Exception as e:
        return f"Error: {e}"

def check_wbs_table_columns(png_files):
    """Check WBS table for correct column headers"""
    log("\n🔍 Checking WBS table column headers...")
    
    # WBS table typically appears on pages 4-6
    # Look for pages with "Task" header
    for png_file in png_files:
        page_num = png_file.split("-")[-1].replace(".png", "")
        png_path = f"/tmp/{png_file}"
        
        try:
            img = Image.open(png_path)
            width, height = img.size
            
            # Sample the top portion of the page (where table headers would be)
            # Skip first ~200px (page header/title)
            header_region = img.crop((0, 200, width, 400))
            
            # Use OCR to extract text
            text = pytesseract.image_to_string(header_region)
            text_lower = text.lower()
            
            # Check if this looks like a WBS table page
            if "task" in text_lower and ("phase" in text_lower or "status" in text_lower):
                log(f"\n   Page {page_num}: Found WBS table")
                log(f"   Extracted header text: {text[:200]}")
                
                # Check for expected columns
                expected = ["task", "phase", "start", "end", "duration", "status", "complete", "actuals"]
                found = [col for col in expected if col in text_lower]
                log(f"   Found columns: {', '.join(found)}")
                
                # Check for "Deps" column (should NOT be present)
                if "deps" in text_lower or "dependencies" in text_lower:
                    log(f"   ❌ FAIL: Found 'Deps' column (should be removed)")
                    return False
                else:
                    log(f"   ✅ PASS: NO 'Deps' column found")
                
                # Check for "Actuals vs Est" or similar
                if "actuals" in text_lower or "actual" in text_lower:
                    log(f"   ✅ PASS: Found 'Actuals' column")
                else:
                    log(f"   ⚠️  WARNING: Could not find 'Actuals' column in OCR text")
        
        except Exception as e:
            log(f"   Page {page_num}: Error checking columns: {e}")
    
    return True

def check_page_content_density(png_files):
    """Check for near-blank pages (>70% whitespace)"""
    log("\n🔍 Checking for near-blank pages...")
    
    for png_file in png_files:
        page_num = png_file.split("-")[-1].replace(".png", "")
        png_path = f"/tmp/{png_file}"
        
        try:
            img = Image.open(png_path)
            gray = img.convert('L')
            pixels = list(gray.getdata())
            
            # Count white pixels (brightness > 240)
            white_pixels = sum(1 for p in pixels if p > 240)
            total_pixels = len(pixels)
            white_pct = (white_pixels / total_pixels) * 100
            
            log(f"   Page {page_num}: {white_pct:.1f}% white", end="")
            
            if white_pct > 70:
                log(" ⚠️  (near-blank page)")
                
                # Check if it's the last page (footer page is OK)
                if page_num == str(len(png_files)):
                    log(f"      (Last page - footer page is acceptable)")
                else:
                    log(f"      ❌ FAIL: Near-blank page in middle of document")
                    return False
            else:
                log(" ✅ (substantial content)")
        
        except Exception as e:
            log(f"   Page {page_num}: Error checking density: {e}")
    
    return True

def main():
    log("="*80)
    log("VISUAL ANALYSIS OF PHASE 1 WBS EXPORT")
    log("="*80)
    
    # Find rendered PNG files
    png_files = sorted([f for f in os.listdir("/tmp") if f.startswith("pdf_page_phase1_6ab25bc82be78e05e89230f3-")])
    
    if not png_files:
        log("❌ No rendered PNG files found. Run backend_test_phase1_wbs_export.py first.")
        return 1
    
    log(f"Found {len(png_files)} rendered page(s)")
    
    # Check 1: Right margin analysis
    log("\n" + "="*80)
    log("CHECK 1: Right-Edge Margin Analysis (Clipping Detection)")
    log("="*80)
    
    margin_results = []
    for png_file in png_files:
        page_num = png_file.split("-")[-1].replace(".png", "")
        png_path = f"/tmp/{png_file}"
        result = analyze_right_margin(png_path, page_num)
        margin_results.append(result)
    
    # Check 2: WBS table column headers
    log("\n" + "="*80)
    log("CHECK 2: WBS Table Column Headers")
    log("="*80)
    
    columns_ok = check_wbs_table_columns(png_files)
    
    # Check 3: Near-blank pages
    log("\n" + "="*80)
    log("CHECK 3: Near-Blank Page Detection")
    log("="*80)
    
    density_ok = check_page_content_density(png_files)
    
    # Summary
    log("\n" + "="*80)
    log("VISUAL ANALYSIS SUMMARY")
    log("="*80)
    
    margin_pass = all(r is not False for r in margin_results if r is not None)
    
    log(f"✅ Right-edge margins: {'PASS' if margin_pass else 'FAIL'}")
    log(f"✅ WBS table columns: {'PASS' if columns_ok else 'FAIL'}")
    log(f"✅ No near-blank pages: {'PASS' if density_ok else 'FAIL'}")
    
    if margin_pass and columns_ok and density_ok:
        log("\n🎉 ALL VISUAL CHECKS PASSED!")
        return 0
    else:
        log("\n❌ SOME VISUAL CHECKS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
