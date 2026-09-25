#!/usr/bin/env python3
"""
Visual Verification Analysis for PDF Export ROUND-3
Analyzes PNG renders to detect right-edge clipping
"""

from PIL import Image
import os

def analyze_right_edge(png_path, page_num):
    """Analyze right edge of PNG to detect clipping"""
    try:
        img = Image.open(png_path)
        width, height = img.size
        
        # Sample the rightmost 50 pixels
        right_edge_width = 50
        
        # Count non-white pixels in the right edge
        non_white_count = 0
        total_pixels = 0
        
        for y in range(height):
            for x in range(width - right_edge_width, width):
                pixel = img.getpixel((x, y))
                total_pixels += 1
                
                # Check if pixel is not white (allowing for slight variations)
                if isinstance(pixel, tuple):
                    r, g, b = pixel[:3]
                    if r < 250 or g < 250 or b < 250:
                        non_white_count += 1
                else:
                    if pixel < 250:
                        non_white_count += 1
        
        # Calculate percentage of non-white pixels in right edge
        non_white_percentage = (non_white_count / total_pixels) * 100
        
        # If more than 5% of right edge is non-white, likely clipped
        is_clipped = non_white_percentage > 5
        
        return {
            "page": page_num,
            "width": width,
            "height": height,
            "right_edge_non_white_pct": non_white_percentage,
            "is_clipped": is_clipped
        }
        
    except Exception as e:
        return {
            "page": page_num,
            "error": str(e)
        }

def main():
    print("=" * 80)
    print("VISUAL VERIFICATION ANALYSIS - PDF EXPORT ROUND-3")
    print("=" * 80)
    
    project_id = "6ab25bc82be78e05e89230f3"
    png_prefix = f"pdf_page_round3_{project_id}"
    
    # Find all PNG files
    png_files = sorted([f for f in os.listdir("/tmp") if f.startswith(png_prefix) and f.endswith(".png")])
    
    print(f"\nFound {len(png_files)} PNG files to analyze\n")
    
    results = []
    for png_file in png_files:
        # Extract page number from filename
        page_num = int(png_file.split("-")[-1].replace(".png", ""))
        png_path = f"/tmp/{png_file}"
        
        result = analyze_right_edge(png_path, page_num)
        results.append(result)
        
        if "error" in result:
            print(f"❌ Page {page_num}: Error - {result['error']}")
        else:
            status = "❌ CLIPPED" if result["is_clipped"] else "✅ NO CLIPPING"
            print(f"{status} - Page {page_num}: Right edge {result['right_edge_non_white_pct']:.1f}% non-white "
                  f"(size: {result['width']}x{result['height']})")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    clipped_pages = [r for r in results if r.get("is_clipped", False)]
    
    if clipped_pages:
        print(f"❌ CLIPPING DETECTED on {len(clipped_pages)} page(s):")
        for r in clipped_pages:
            print(f"   - Page {r['page']}: {r['right_edge_non_white_pct']:.1f}% non-white in right edge")
    else:
        print("✅ NO CLIPPING DETECTED - All pages have clean right margins")
    
    print("\nInterpretation:")
    print("  - < 5% non-white in right edge = Clean margin (NO clipping)")
    print("  - > 5% non-white in right edge = Likely clipped content")
    print("=" * 80)

if __name__ == "__main__":
    main()
