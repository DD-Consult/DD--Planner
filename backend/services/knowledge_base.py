"""
AI Knowledge Base
=================
Indexes DD Planner's documentation (GUIDE.md, README.md, INTEGRATIONS.md) into
MongoDB as searchable sections. Provides keyword-based retrieval for AI chat so
the copilot can answer "how do I…" questions and troubleshoot, citing the
source section.

Design notes:
- No embedding cost — keyword TF-IDF-lite scoring is fast and deterministic
- Docs are split by markdown headings (## and ###) → one row per section
- Each section is enriched with `keywords` (title terms + notable bigrams from body)
- `retrieve(query, top_k)` returns the top matching sections
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

from database import ai_knowledge_base_collection

# Registered docs → their friendly source label
DOC_FILES: Dict[str, str] = {
    "/app/GUIDE.md": "GUIDE",
    "/app/README.md": "README",
    "/app/INTEGRATIONS.md": "INTEGRATIONS",
}

# Extra tiny knowledge chips — quick facts the AI should always know
INLINE_KB: List[Dict] = [
    {
        "source": "APP",
        "section_path": "App → Roles",
        "title": "User roles overview",
        "content": (
            "DD Planner has these roles: super_admin (full org control), admin "
            "(full project control), lead (edit projects they lead), resource "
            "(log time, view own allocations), contractor (like resource + limited "
            "project access), client (read-only view of their allocated projects)."
        ),
    },
    {
        "source": "APP",
        "section_path": "App → Capacity",
        "title": "Standard capacity math",
        "content": (
            "A resource's weekly hours = (allocation % / 100) × (standard_capacity / 100) × 40. "
            "A 50%-capacity resource allocated at 100% has 20h/week. A 100%-capacity resource "
            "allocated at 50% has 20h/week. Always show capacity relative to standard_capacity."
        ),
    },
    {
        "source": "APP",
        "section_path": "App → AI Actions",
        "title": "AI can act on your behalf",
        "content": (
            "In the AI chat, you can ask it to create/update projects, allocate resources, "
            "log timesheets, add risks, generate WBS, and more. Destructive actions require "
            "confirmation. You can undo the last action with the Undo button."
        ),
    },
]

_kb_collection = ai_knowledge_base_collection  # sections + metadata (tenant-aware LazyCollection)

# Stopwords for lightweight scoring
_STOP = {
    "the", "and", "or", "for", "with", "to", "of", "in", "on", "a", "an", "is",
    "are", "be", "at", "by", "as", "it", "this", "that", "how", "do", "i", "you",
    "we", "my", "your", "our", "can", "will", "would", "should", "may", "if",
    "so", "but", "not", "no", "yes", "from", "into", "up", "out", "any", "all",
    "just", "also", "then", "than", "when", "which", "what", "why", "who",
    "there", "their", "have", "has", "had", "was", "were", "am", "does", "did",
    "please", "help", "me", "us", "us", "them", "these", "those",
}

# Boost score for critical topic words
_BOOST = {
    "timesheet", "timesheets", "allocation", "allocations", "resource",
    "resources", "project", "projects", "wbs", "risk", "risks", "capacity",
    "budget", "phase", "phases", "milestone", "milestones", "hubspot",
    "integration", "integrations", "mcp", "role", "roles", "permission",
    "permissions", "lead", "admin", "client", "portal", "reschedule",
    "gantt", "chat", "ai", "leave", "leaves", "holiday", "holidays",
    "baseline", "baselines", "status", "update", "updates", "notification",
    "notifications", "reset", "password", "login", "auth", "authentication",
}


def _tokenize(text: str) -> List[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP and len(w) > 1]


# ─────────────────────────────────────────────────────────────────────────
# Markdown chunker
# ─────────────────────────────────────────────────────────────────────────

def _split_markdown_sections(source: str, text: str) -> List[Dict]:
    """Split markdown into sections by ## / ### headings. Each section keeps
    the heading chain (breadcrumb) so citations can be precise."""
    sections: List[Dict] = []
    current_h1 = None
    current_h2 = None
    current_h3 = None
    buffer: List[str] = []

    def _flush():
        if not buffer:
            return
        content = "\n".join(buffer).strip()
        if len(content) < 20:
            return
        parts = [p for p in [current_h1, current_h2, current_h3] if p]
        section_path = f"{source} → " + " → ".join(parts) if parts else source
        title = current_h3 or current_h2 or current_h1 or source
        sections.append({
            "source": source,
            "section_path": section_path,
            "title": title,
            "content": content,
        })

    for line in text.splitlines():
        h1 = re.match(r"^#\s+(.*)$", line)
        h2 = re.match(r"^##\s+(.*)$", line)
        h3 = re.match(r"^###\s+(.*)$", line)
        if h1:
            _flush()
            buffer = []
            current_h1 = h1.group(1).strip()
            current_h2 = None
            current_h3 = None
        elif h2:
            _flush()
            buffer = []
            current_h2 = h2.group(1).strip()
            current_h3 = None
        elif h3:
            _flush()
            buffer = []
            current_h3 = h3.group(1).strip()
        else:
            buffer.append(line)
    _flush()
    return sections


# ─────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────

async def reindex() -> Dict:
    """Rebuild the knowledge base from disk. Safe to call anytime."""
    await _kb_collection.delete_many({})
    total = 0
    for path, source in DOC_FILES.items():
        if not os.path.exists(path):
            continue
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
        sections = _split_markdown_sections(source, text)
        for sec in sections:
            keywords = list(set(_tokenize(sec["title"] + " " + sec["content"])))
            sec["keywords"] = keywords[:80]  # cap
            sec["indexed_at"] = datetime.now(timezone.utc)
        if sections:
            await _kb_collection.insert_many(sections)
            total += len(sections)
    # Inject inline chips
    for chip in INLINE_KB:
        chip = dict(chip)
        chip["keywords"] = list(set(_tokenize(chip["title"] + " " + chip["content"])))
        chip["indexed_at"] = datetime.now(timezone.utc)
        await _kb_collection.insert_one(chip)
        total += 1
    return {"indexed_sections": total, "sources": list(DOC_FILES.values()) + ["APP"]}


async def status() -> Dict:
    count = await _kb_collection.count_documents({})
    last = None
    if count > 0:
        latest = await _kb_collection.find_one(sort=[("indexed_at", -1)])
        if latest and latest.get("indexed_at"):
            last = latest["indexed_at"].isoformat()
    by_source: Dict[str, int] = {}
    async for row in _kb_collection.aggregate([{"$group": {"_id": "$source", "n": {"$sum": 1}}}]):
        by_source[row["_id"]] = row["n"]
    return {
        "total_sections": count,
        "last_indexed_at": last,
        "by_source": by_source,
    }


def _score(query_tokens: List[str], section: Dict) -> float:
    """Simple additive score: keyword overlap + boosted topic words +
    small bonus for query terms appearing in the title."""
    kw = set(section.get("keywords") or [])
    title_tokens = set(_tokenize(section.get("title") or ""))
    score = 0.0
    for t in query_tokens:
        if t in kw:
            score += 2.0 if t in _BOOST else 1.0
        if t in title_tokens:
            score += 1.5
    return score


async def retrieve(query: str, top_k: int = 4, min_score: float = 1.5) -> List[Dict]:
    """Return top-scoring sections for a query. Empty list if nothing relevant."""
    if not query or not query.strip():
        return []
    tokens = _tokenize(query)
    if not tokens:
        return []
    # Pre-filter with $in on keywords to avoid scanning irrelevant docs
    docs = await _kb_collection.find(
        {"keywords": {"$in": tokens}},
        {"source": 1, "section_path": 1, "title": 1, "content": 1, "keywords": 1},
    ).to_list(length=200)
    scored = [(_score(tokens, d), d) for d in docs]
    scored = [s for s in scored if s[0] >= min_score]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [dict(d, _score=round(s, 2)) for s, d in scored[:top_k]]


def looks_like_help_query(msg: str) -> bool:
    """Cheap heuristic: does this message look like a how-to / troubleshoot
    question we should enrich with KB context?"""
    if not msg:
        return False
    m = msg.lower().strip()
    triggers = (
        "how do i", "how do you", "how can i", "how to", "how does",
        "why can't i", "why cant i", "why is", "why does", "why isn't",
        "what does", "what is the", "what is a", "what is an",
        "where do i", "where is", "where can i", "where's the",
        "explain ", "guide me", "help me", "walk me through",
        "troubleshoot", "not working", "broken", "error", "can't ",
        "can i ", "is there a way", "what happens if",
    )
    return any(t in m for t in triggers)


def format_kb_context(sections: List[Dict]) -> str:
    """Format retrieved sections as a system-prompt block. Compact & cite-able."""
    if not sections:
        return ""
    lines = ["", "DOCUMENTATION CONTEXT (cite the section when you use it):"]
    for i, s in enumerate(sections, 1):
        # Trim overly long content to keep prompt lean
        content = s.get("content") or ""
        if len(content) > 900:
            content = content[:900] + "…"
        lines.append(f"[{i}] {s.get('section_path')}")
        lines.append(content)
        lines.append("")
    lines.append(
        "When you use the above, cite the section like: (see " +
        (sections[0].get("section_path") or "docs") + "). "
        "If the docs don't answer the question, say so plainly and suggest what to check."
    )
    return "\n".join(lines)
