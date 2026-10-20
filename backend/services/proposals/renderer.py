"""Adapter around the locked v4 proposal generator.

The v4 system (services/proposals/v4/) is a self-contained HTML generator that
turns a JSON brief into a finished, styled, nine-chapter client-facing proposal.
It performs ALL pricing arithmetic, bar/chevron widths and validation internally
so a miscalculation can never reach a client.

This adapter:
  * imports the v4 ``build(data)`` function (string-substitution only, no network)
  * injects our own tracking endpoint in place of the template's webhook token
  * injects a robots "noindex" meta so secure proposal links aren't indexed
  * returns the finished HTML (plus any non-fatal generator warnings)

It deliberately does NOT re-implement any of the v4 logic — the v4 files are the
single source of truth for layout, pricing and brand rules.
"""
from __future__ import annotations

import copy
import importlib.util
import os
import sys
from pathlib import Path
from typing import Tuple

_V4_DIR = Path(__file__).parent / "v4"
_GENERATOR_PATH = _V4_DIR / "generate_proposal.py"

# Load the v4 generator module from its file path. Loaded once and cached.
_generator = None


def _load_generator():
    global _generator
    if _generator is not None:
        return _generator
    spec = importlib.util.spec_from_file_location("dd_proposal_v4_generator", _GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    # Ensure the v4 dir is importable for its relative asset/template reads
    if str(_V4_DIR) not in sys.path:
        sys.path.insert(0, str(_V4_DIR))
    spec.loader.exec_module(module)
    _generator = module
    return _generator


def load_sample_brief() -> dict:
    """Return the v4 sample brief dict — used as the starting scaffold for a new
    proposal so the PM/AI always edit a valid, fully-populated structure rather
    than an empty form."""
    import json
    sample_path = _V4_DIR / "sample-proposal-data.json"
    return json.loads(sample_path.read_text(encoding="utf-8"))


def load_case_studies() -> dict:
    """Return the approved case-study library (id -> entry), minus the _readme."""
    import json
    lib = json.loads((_V4_DIR / "case-studies.json").read_text(encoding="utf-8"))
    lib.pop("_readme", None)
    return lib


def validate_brief(data: dict):
    """Run the v4 validator. Raises SystemExit (converted by caller) on hard errors.
    Returns the list of non-fatal warnings collected during validation."""
    gen = _load_generator()
    gen.WARNINGS.clear()
    gen.validate(data)
    return list(gen.WARNINGS)


def render_proposal_html(
    data: dict,
    *,
    tracking_url: str = "",
    noindex: bool = True,
) -> Tuple[str, list]:
    """Render the full client-facing proposal HTML from a brief dict.

    Args:
        data: the proposal brief (same shape as sample-proposal-data.json).
        tracking_url: backend endpoint the page should POST engagement events to.
            Replaces the template's {{TRACKING_WEBHOOK_URL}} token. If empty, the
            page's tracking fetch simply fails silently (by design).
        noindex: when True, inject <meta name="robots" content="noindex,nofollow">.

    Returns:
        (html, warnings)
    """
    gen = _load_generator()
    gen.WARNINGS.clear()

    # Work on a copy so we never mutate the caller's stored brief.
    brief = copy.deepcopy(data)
    # Point the page's tracking at our backend endpoint (or a harmless placeholder).
    brief["tracking_webhook_url"] = tracking_url or "about:blank"

    html = gen.build(brief)

    if noindex:
        meta = '<meta name="robots" content="noindex,nofollow">'
        if "<head>" in html:
            html = html.replace("<head>", "<head>\n  " + meta, 1)
        else:
            html = meta + html

    return html, list(gen.WARNINGS)
