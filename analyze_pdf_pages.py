#!/usr/bin/env python3
"""
Analyze PDF pages for sparse content and visual verification
"""

from PIL import Image
import numpy as np
from pathlib import Path

def analyze_page_whitespace(png_path):
    """Analyze how much whitespace is in a page"""
    img = Image.open(png_path)
    img_array = np.array(img)
    
    # Convert to grayscale if needed
    if len(img_array.shape) == 3:
        # Calculate brightness (simple average of RGB)
        gray = np.mean(img_array[:, :, :3], axis=2)
    else:
        gray = img_array
    
    # Count pixels that are "white" (brightness > 240)
    white_pixels = np.sum(gray > 240)
    total_pixels = gray.size
    
    whitespace_percent = (white_pixels / total_pixels) * 100
    
    return whitespace_percent

def analyze_right_edge_clipping(png_path, edge_width=100):
    """Check if content is clipped at right edge"""
    img = Image.open(png_path)
    img_array = np.array(img)
    
    # Get rightmost edge_width pixels
    if len(img_array.shape) == 3:
        right_edge = img_array[:, -edge_width:, :3]
        gray = np.mean(right_edge, axis=2)
    else:
        right_edge = img_array[:, -edge_width:]
        gray = right_edge
    
    # Count white pixels in right edge
    white_pixels = np.sum(gray > 240)
    total_pixels = gray.size
    
    white_percent = (white_pixels / total_pixels) * 100
    
    return white_percent

# Analyze all pages
png_files = sorted(Path("/tmp").glob("pdf_page_status_summary_6ab25bc82be78e05e89230f3-*.png"))

print("=" * 80)
print("PDF PAGE ANALYSIS")
print("=" * 80)

for png_file in png_files:
    page_num = png_file.stem.split("-")[-1]
    file_size_kb = png_file.stat().st_size / 1024
    
    whitespace = analyze_page_whitespace(png_file)
    right_edge_white = analyze_right_edge_clipping(png_file, edge_width=100)
    
    # Determine if page is sparse (>75% whitespace)
    is_sparse = whitespace > 75
    sparse_indicator = "⚠️  SPARSE" if is_sparse else "✅ OK"
    
    # Determine if right edge has clipping (< 90% white means content at edge)
    has_clipping = right_edge_white < 90
    clip_indicator = "⚠️  CLIPPED" if has_clipping else "✅ CLEAN"
    
    print(f"\nPage {page_num}:")
    print(f"  File size: {file_size_kb:.1f} KB")
    print(f"  Whitespace: {whitespace:.1f}% {sparse_indicator}")
    print(f"  Right edge (100px): {right_edge_white:.1f}% white {clip_indicator}")

print("\n" + "=" * 80)
print("ANALYSIS SUMMARY")
print("=" * 80)

# Check for sparse pages
sparse_pages = []
for png_file in png_files:
    page_num = png_file.stem.split("-")[-1]
    whitespace = analyze_page_whitespace(png_file)
    if whitespace > 75:
        sparse_pages.append(page_num)

if sparse_pages:
    print(f"⚠️  SPARSE PAGES DETECTED: {', '.join(sparse_pages)}")
    print("   Pages with >75% whitespace are considered sparse/near-blank")
else:
    print("✅ NO SPARSE PAGES: All pages have substantial content")

# Check for clipping
clipped_pages = []
for png_file in png_files:
    page_num = png_file.stem.split("-")[-1]
    right_edge_white = analyze_right_edge_clipping(png_file, edge_width=100)
    if right_edge_white < 90:
        clipped_pages.append(page_num)

if clipped_pages:
    print(f"⚠️  POTENTIAL CLIPPING: Pages {', '.join(clipped_pages)}")
    print("   Right edge has <90% white pixels (content may be clipped)")
else:
    print("✅ NO CLIPPING: All pages have clean right margins")

print("\n" + "=" * 80)
