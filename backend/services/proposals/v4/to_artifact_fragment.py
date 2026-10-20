#!/usr/bin/env python3
"""
to_artifact_fragment.py
-----------------------
Turns a finished proposal page (from generate_proposal.py) into the
fragment format the Claude Artifact tool publishes: no doctype/html/head/
body, just <title>, font links, <style>, the page body and its <script>.

Used only for the live prototype link, so the demo is always built FROM the
real generated page and can never drift from the template.

    python3 to_artifact_fragment.py sample-proposal-generated.html fragment.html \
        --title "Meridian Health Proposal" [--sample-pill]
"""
import argparse
import re
from pathlib import Path

SAMPLE_CSS = (".sample-pill{font-family:var(--heading);font-size:10.5px;font-weight:600;text-transform:uppercase;"
              "letter-spacing:.05em;background:var(--card);border:1px solid var(--line);color:var(--muted);"
              "border-radius:999px;padding:4px 10px;white-space:nowrap;flex:none;}")


def convert(html, title, sample_pill):
    links = re.findall(r'<link[^>]+fonts\.(?:googleapis|gstatic)\.com[^>]*>', html)
    style = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
    body = re.search(r"<body>(.*)</body>", html, re.S).group(1)
    if sample_pill:
        style += "\n  " + SAMPLE_CSS
        marker = '<span class="name">DD CONSULTING</span></div>'
        assert marker in body, "brand marker not found"
        body = body.replace(marker, marker + '<span class="sample-pill">Sample · fictional client</span>', 1)
    return f"<title>{title}</title>\n" + "\n".join(links) + f"\n<style>{style}</style>\n{body.strip()}\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--title", required=True)
    ap.add_argument("--sample-pill", action="store_true")
    a = ap.parse_args()
    out = convert(Path(a.src).read_text(encoding="utf-8"), a.title, a.sample_pill)
    Path(a.dst).write_text(out, encoding="utf-8")
    print(f"Wrote {a.dst} ({len(out):,} bytes)")


if __name__ == "__main__":
    main()
