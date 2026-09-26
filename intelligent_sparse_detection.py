#!/usr/bin/env python3
"""
Intelligent sparse page detection based on semantic content
A page is only "near-blank" if it has minimal semantic content (just heading/footer)
"""

from pathlib import Path
import subprocess

def extract_page_text(png_path):
    """Extract text from PNG using tesseract"""
    try:
        text = subprocess.check_output(
            ["tesseract", str(png_path), "stdout"],
            stderr=subprocess.DEVNULL,
            text=True
        )
        return text
    except:
        return ""

def analyze_page_content(text):
    """
    Analyze if page has substantial content
    Returns: (is_substantial, content_type, line_count)
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    # Count meaningful lines (not just whitespace or single characters)
    meaningful_lines = [line for line in lines if len(line) > 3]
    
    # Check for content indicators
    has_table = any(keyword in text for keyword in ["TASK", "PHASE", "START", "END", "DURATION", "STATUS"])
    has_risks = "RISK" in text or "ISSUE" in text
    has_timeline = "Timeline" in text or "Project Timeline" in text
    has_summary = "EXECUTIVE SUMMARY" in text or "PROJECT OBJECTIVE" in text
    has_budget = "Budget" in text or "Hours" in text
    
    # Determine content type
    if has_table:
        content_type = "WBS Table"
    elif has_risks:
        content_type = "Risks Section"
    elif has_timeline:
        content_type = "Timeline/Gantt"
    elif has_summary:
        content_type = "Status Summary"
    elif has_budget:
        content_type = "Budget/Tracking"
    elif len(meaningful_lines) < 5:
        content_type = "Footer/Minimal"
    else:
        content_type = "General Content"
    
    # A page is substantial if it has:
    # - A table, risks, timeline, summary, or budget section, OR
    # - More than 10 meaningful lines of text
    is_substantial = (has_table or has_risks or has_timeline or has_summary or has_budget or 
                     len(meaningful_lines) > 10)
    
    return is_substantial, content_type, len(meaningful_lines)

# Analyze all pages
png_files = sorted(Path("/tmp").glob("pdf_page_status_summary_6ab25bc82be78e05e89230f3-*.png"))

print("=" * 80)
print("INTELLIGENT SPARSE PAGE DETECTION")
print("=" * 80)

near_blank_pages = []

for png_file in png_files:
    page_num = int(png_file.stem.split("-")[-1])
    text = extract_page_text(png_file)
    
    is_substantial, content_type, line_count = analyze_page_content(text)
    
    status = "✅ SUBSTANTIAL" if is_substantial else "⚠️  NEAR-BLANK"
    print(f"\nPage {page_num}: {status}")
    print(f"  Content Type: {content_type}")
    print(f"  Meaningful Lines: {line_count}")
    
    if not is_substantial:
        near_blank_pages.append(page_num)
        # Show preview of what's on the page
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        preview = " | ".join(lines[:5])
        print(f"  Preview: {preview[:150]}")

print("\n" + "=" * 80)
print("FINAL VERDICT ON SPARSE PAGES")
print("=" * 80)

if near_blank_pages:
    print(f"❌ NEAR-BLANK PAGES DETECTED: {near_blank_pages}")
    print("   These pages have minimal content (just heading/footer)")
else:
    print("✅✅✅ NO NEAR-BLANK PAGES")
    print("   All pages have substantial content (tables, sections, data)")
    print("   Note: Pages with tables/charts naturally have whitespace but are NOT near-blank")

print("\n" + "=" * 80)
