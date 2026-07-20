"""
Specialist Agent Routing
========================
Detects @mention keywords in user messages and returns a focused specialist
system prompt header that gets prepended to the main AI prompt.

Usage:
  from services.specialist_agents import detect_specialist, get_specialist_header

  specialist = detect_specialist(user_message)  # e.g. "resource", "budget", None
  if specialist:
      system_prompt = get_specialist_header(specialist) + main_system_prompt
"""
from __future__ import annotations
import re
from typing import Optional

SPECIALIST_MODES = {
    "resource": {
        "label": "Resource Optimizer",
        "trigger_patterns": [r"@resource", r"\bresource\s+agent\b", r"\b@res\b"],
        "header": """SPECIALIST MODE ACTIVE: RESOURCE OPTIMIZER
You are focused exclusively on resource capacity and allocation. Your job:
- Identify who is over-allocated, under-utilised, or at risk of burnout
- Surface availability windows and upcoming capacity gaps
- Recommend practical rebalancing: who to move, by how much, when
- Flag single points of failure (projects with only one resource)
- Be direct about bottlenecks blocking multiple workstreams
Lead with the 2-3 most critical capacity findings. Use % and names — no vague descriptions.
When you suggest a fix, also emit the matching `create_allocation` or `update_allocation` action.""",
    },
    "budget": {
        "label": "Budget Analyst",
        "trigger_patterns": [r"@budget", r"\bbudget\s+agent\b", r"\b@fin\b"],
        "header": """SPECIALIST MODE ACTIVE: BUDGET ANALYST
You are focused exclusively on financial health across the portfolio. Your job:
- Calculate burn rate and forecast to completion for each active project
- Flag projects tracking over budget now OR likely to overshoot
- Identify where actual hours diverge most from planned
- Surface the biggest budget risks: what will cause cost overruns?
- Recommend concrete mitigations (scope cuts, resource changes, timeline adjustments)
Lead with actual numbers: budgeted vs actuals vs forecast. No hand-waving.""",
    },
    "risk": {
        "label": "Risk Manager",
        "trigger_patterns": [r"@risk", r"\brisk\s+agent\b", r"\b@risks?\b"],
        "header": """SPECIALIST MODE ACTIVE: RISK MANAGER
You are focused exclusively on project risks and issues. Your job:
- Rank active risks by combined impact × probability
- Surface risks with no mitigation plan (highest urgency)
- Identify risk patterns appearing across multiple projects
- Flag stale risks: active risks last updated more than 30 days ago
- Recommend escalation paths for Critical / High items
Lead with the top 3-5 risks that need immediate attention. Be specific about why each one matters now.""",
    },
    "schedule": {
        "label": "Schedule Coordinator",
        "trigger_patterns": [r"@schedule", r"\bschedule\s+agent\b", r"\b@sched\b"],
        "header": """SPECIALIST MODE ACTIVE: SCHEDULE COORDINATOR
You are focused exclusively on timeline health. Your job:
- Identify projects running behind schedule or at risk of deadline slippage
- Surface overdue WBS milestones and tasks blocking progress
- Predict completion dates based on current velocity vs planned
- Highlight schedule interdependencies: delayed project A blocks project B
- Recommend reschedule actions with concrete shift_days estimates
Lead with what's late right now, then what's about to be late. Use dates and names — be precise.""",
    },
}


def detect_specialist(message: str) -> Optional[str]:
    """Return the specialist key (e.g. 'resource') if a trigger is found, else None."""
    msg_lower = message.lower()
    for key, spec in SPECIALIST_MODES.items():
        for pattern in spec["trigger_patterns"]:
            if re.search(pattern, msg_lower):
                return key
    return None


def get_specialist_header(specialist_key: str) -> str:
    """Return the specialist header to prepend to the system prompt."""
    spec = SPECIALIST_MODES.get(specialist_key)
    if not spec:
        return ""
    return f"\n{'='*70}\n{spec['header']}\n{'='*70}\n\n"


def get_specialist_label(specialist_key: str) -> str:
    """Human-readable label for the specialist mode."""
    spec = SPECIALIST_MODES.get(specialist_key)
    return spec["label"] if spec else "General"


def list_specialist_triggers() -> str:
    """Build the @-mention docs for the system prompt."""
    lines = ["\nSPECIALIST MODES — prepend your message to activate focused analysis:"]
    for key, spec in SPECIALIST_MODES.items():
        lines.append(f"  @{key} — {spec['label']}: {spec['header'].split(chr(10))[1]}")
    return "\n".join(lines)
