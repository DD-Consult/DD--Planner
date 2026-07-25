"""
Project Forecasting Service
===========================
Predictive analytics for schedule slip and budget overrun risk.

For each active project, computes a `slip_risk` score (0-100) and a
`projected_end_date` based on:

- Velocity: actual weekly burn vs planned weekly burn
- WBS completion: expected % complete vs actual % complete
- Time buffer: days remaining vs work remaining at current velocity
- Health trend: recent status update health arc
- Milestone health: overdue / at-risk milestone count

Provides:
  • forecast_project(project_id) → single-project forecast
  • forecast_portfolio() → all active projects, sorted by risk
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from bson import ObjectId

from database import (
    projects_collection, timesheets_collection, allocations_collection,
    wbs_tasks_collection, status_updates_collection,
)
from utils import serialize_doc

logger = logging.getLogger(__name__)


def _dt_utc(x):
    if x is None:
        return None
    if isinstance(x, str):
        try:
            x = datetime.fromisoformat(x.replace("Z", "+00:00"))
        except Exception:
            return None
    if isinstance(x, datetime):
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    return None


def _business_days_between(start: datetime, end: datetime) -> int:
    """Count Mon-Fri days from start (inclusive) to end (inclusive)."""
    if not (start and end) or end < start:
        return 0
    days = 0
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days += 1
        cur += timedelta(days=1)
    return days


# ─────────────────────────────────────────────────────────────────────────
# Signal calculations
# ─────────────────────────────────────────────────────────────────────────

def _velocity_signal(actual_hours: float, planned_hours: float,
                     elapsed_bd: int, total_bd: int) -> Dict:
    """Compare velocity (hours/day) actual vs planned."""
    if total_bd <= 0 or planned_hours <= 0 or elapsed_bd <= 0:
        return {"score": 0, "narrative": "Not enough elapsed time to measure velocity."}
    planned_per_day = planned_hours / total_bd
    actual_per_day = actual_hours / elapsed_bd
    if planned_per_day <= 0:
        return {"score": 0, "narrative": "No planned rate to compare against."}
    ratio = actual_per_day / planned_per_day
    # ratio < 1 → behind, ratio > 1 → ahead (or dumping/scope creep)
    if ratio < 0.6:
        score = 30  # meaningfully behind
        narrative = f"Team is burning {ratio*100:.0f}% of planned rate — significantly behind."
    elif ratio < 0.85:
        score = 15
        narrative = f"Team burning {ratio*100:.0f}% of planned rate — mildly behind."
    elif ratio > 1.6:
        score = 20  # overheating, will exhaust budget
        narrative = f"Team burning {ratio*100:.0f}% of plan — likely to run out of budget early."
    elif ratio > 1.25:
        score = 10
        narrative = f"Team burning {ratio*100:.0f}% of plan — running hot."
    else:
        score = 0
        narrative = f"Velocity is healthy ({ratio*100:.0f}% of plan)."
    return {"score": score, "ratio": round(ratio, 2), "narrative": narrative}


def _wbs_completion_signal(wbs_tasks: List[dict], elapsed_pct: float) -> Dict:
    """Expected % complete (elapsed_pct) vs actual % complete."""
    leaf_tasks = [t for t in wbs_tasks if t.get("estimated_hours", 0) > 0 and not t.get("is_milestone")]
    if not leaf_tasks:
        return {"score": 0, "narrative": "No WBS estimates to measure completion."}
    total_est = sum(float(t.get("estimated_hours") or 0) for t in leaf_tasks)
    done_est = sum(
        float(t.get("estimated_hours") or 0) for t in leaf_tasks
        if (t.get("status") or "").lower() in ("done", "completed")
    )
    actual_pct = (done_est / total_est * 100) if total_est else 0
    gap = elapsed_pct - actual_pct
    if gap > 25:
        return {"score": 25, "actual_pct": round(actual_pct, 1), "expected_pct": round(elapsed_pct, 1),
                "narrative": f"Only {actual_pct:.0f}% of WBS complete, expected {elapsed_pct:.0f}% — {gap:.0f}pp behind."}
    if gap > 12:
        return {"score": 12, "actual_pct": round(actual_pct, 1), "expected_pct": round(elapsed_pct, 1),
                "narrative": f"WBS at {actual_pct:.0f}%, tracking {gap:.0f}pp behind expected."}
    if gap < -10:
        return {"score": 0, "actual_pct": round(actual_pct, 1), "expected_pct": round(elapsed_pct, 1),
                "narrative": f"WBS at {actual_pct:.0f}%, ahead of expected."}
    return {"score": 0, "actual_pct": round(actual_pct, 1), "expected_pct": round(elapsed_pct, 1),
            "narrative": f"WBS on track ({actual_pct:.0f}% vs expected {elapsed_pct:.0f}%)."}


def _time_buffer_signal(remaining_bd: int, remaining_hours: float,
                        recent_weekly_burn: float) -> Dict:
    """At current velocity, will the remaining work fit in the remaining time?"""
    if remaining_bd <= 0:
        return {"score": 30, "narrative": "Deadline has passed — schedule needs rescheduling."}
    if recent_weekly_burn <= 0:
        return {"score": 0, "narrative": "No recent burn — cannot forecast completion."}
    daily_burn = recent_weekly_burn / 5.0
    if daily_burn <= 0:
        return {"score": 0, "narrative": ""}
    days_needed = remaining_hours / daily_burn if daily_burn > 0 else 0
    projected_finish = days_needed / 5 * 7  # convert business days back to calendar days for readability
    slip_days = days_needed - remaining_bd
    if slip_days > remaining_bd * 0.5:
        return {"score": 25, "slip_business_days": round(slip_days, 0),
                "narrative": f"At current pace, {days_needed:.0f} business days needed but only {remaining_bd} remain — big slip."}
    if slip_days > 5:
        return {"score": 15, "slip_business_days": round(slip_days, 0),
                "narrative": f"At current pace, project runs {slip_days:.0f} business days late."}
    if slip_days < -10:
        return {"score": 0, "slip_business_days": round(slip_days, 0),
                "narrative": "Ahead of schedule at current velocity."}
    return {"score": 0, "slip_business_days": round(slip_days, 0),
            "narrative": "On track to finish on time at current velocity."}


def _health_trend_signal(status_updates: List[dict]) -> Dict:
    """Recent status update health arc."""
    if len(status_updates) < 2:
        return {"score": 0, "narrative": "Not enough status updates to detect a trend."}
    recent = sorted(status_updates, key=lambda x: _dt_utc(x.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc))[-3:]
    order = {"Green": 3, "Amber": 2, "Red": 1}
    scores = [order.get(su.get("health", "Amber"), 2) for su in recent]
    latest = scores[-1]
    trend = "→"
    if len(scores) >= 2 and scores[-1] < scores[0]:
        trend = "↓"
    elif len(scores) >= 2 and scores[-1] > scores[0]:
        trend = "↑"
    if latest == 1:
        return {"score": 15, "narrative": f"Latest status is Red ({trend} trend)."}
    if latest == 2 and trend == "↓":
        return {"score": 10, "narrative": f"Status downgrading toward Amber ({trend})."}
    if latest == 2:
        return {"score": 5, "narrative": f"Latest status is Amber ({trend})."}
    return {"score": 0, "narrative": f"Health steady/positive ({trend})."}


def _milestone_signal(wbs_tasks: List[dict], now: datetime) -> Dict:
    milestones = [t for t in wbs_tasks if t.get("is_milestone")]
    if not milestones:
        return {"score": 0, "narrative": "No milestones defined."}
    overdue = 0
    at_risk = 0
    horizon = now + timedelta(days=14)
    for m in milestones:
        if (m.get("status") or "").lower() in ("done", "completed"):
            continue
        end = _dt_utc(m.get("end_date"))
        if not end:
            continue
        if end < now:
            overdue += 1
        elif end < horizon:
            at_risk += 1
    if overdue >= 2:
        return {"score": 20, "overdue": overdue, "at_risk": at_risk,
                "narrative": f"{overdue} milestone(s) overdue, {at_risk} at risk within 2 weeks."}
    if overdue == 1:
        return {"score": 12, "overdue": overdue, "at_risk": at_risk,
                "narrative": f"1 milestone overdue, {at_risk} at risk within 2 weeks."}
    if at_risk >= 2:
        return {"score": 8, "overdue": 0, "at_risk": at_risk,
                "narrative": f"{at_risk} milestones at risk in the next 2 weeks."}
    return {"score": 0, "overdue": 0, "at_risk": at_risk, "narrative": "Milestones on track."}


def _label_for(score: int) -> str:
    if score >= 65:
        return "Critical"
    if score >= 40:
        return "High"
    if score >= 20:
        return "Medium"
    return "Low"


# ─────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────

async def forecast_project(project_id: str) -> Optional[dict]:
    try:
        p = await projects_collection.find_one({"_id": ObjectId(project_id)})
    except Exception:
        return None
    if not p:
        return None
    return await _forecast_one(p)


async def _forecast_one(p: dict) -> dict:
    pid = str(p["_id"])
    now = datetime.now(timezone.utc)
    start = _dt_utc(p.get("start_date")) or now
    end = _dt_utc(p.get("end_date")) or now

    total_bd = _business_days_between(start, end)
    elapsed_bd = _business_days_between(start, min(now, end))
    remaining_bd = max(_business_days_between(now, end) - 1, 0)  # exclude 'today'
    elapsed_pct = (elapsed_bd / total_bd * 100) if total_bd else 0

    # Gather signals
    ts = await timesheets_collection.find({"project_id": pid}).to_list(length=10000)
    actual_hours = sum(float(t.get("actual_hours") or 0) for t in ts)

    # Recent (last 3 weeks) burn
    cutoff = (now - timedelta(weeks=3)).date().isoformat()
    recent_burn = sum(
        float(t.get("actual_hours") or 0) for t in ts
        if (t.get("week_start_date") or "") >= cutoff
    )
    recent_weekly_burn = recent_burn / 3 if recent_burn else 0

    planned = float(p.get("budgeted_hours") or 0)
    remaining_hours = max(planned - actual_hours, 0)

    wbs = await wbs_tasks_collection.find({"project_id": pid}).to_list(length=2000)
    su = await status_updates_collection.find({"project_id": pid}).sort("created_at", -1).to_list(length=10)

    signals = {
        "velocity": _velocity_signal(actual_hours, planned, elapsed_bd, total_bd),
        "wbs_completion": _wbs_completion_signal(wbs, elapsed_pct),
        "time_buffer": _time_buffer_signal(remaining_bd, remaining_hours, recent_weekly_burn),
        "health_trend": _health_trend_signal(su),
        "milestones": _milestone_signal(wbs, now),
    }
    slip_score = min(sum(s.get("score", 0) for s in signals.values()), 100)

    # Projected end date at current velocity
    projected_end = None
    if recent_weekly_burn > 0 and remaining_hours > 0:
        days_needed = remaining_hours / (recent_weekly_burn / 5.0)
        # walk business days forward
        cur = now
        walked = 0
        while walked < days_needed:
            cur += timedelta(days=1)
            if cur.weekday() < 5:
                walked += 1
        projected_end = cur.date().isoformat()

    return {
        "project_id": pid,
        "project_name": p.get("name"),
        "status": p.get("status"),
        "planned_end_date": end.date().isoformat() if end else None,
        "projected_end_date": projected_end,
        "slip_business_days": signals["time_buffer"].get("slip_business_days"),
        "slip_risk_score": slip_score,
        "slip_risk_label": _label_for(slip_score),
        "elapsed_pct": round(elapsed_pct, 1),
        "actual_hours": round(actual_hours, 1),
        "planned_hours": round(planned, 1),
        "recent_weekly_burn": round(recent_weekly_burn, 1),
        "signals": signals,
        "top_factors": [
            {"name": k, "narrative": v.get("narrative", ""), "score": v.get("score", 0)}
            for k, v in sorted(signals.items(), key=lambda kv: -kv[1].get("score", 0)) if v.get("score", 0) > 0
        ][:3],
    }


async def forecast_portfolio() -> dict:
    """Forecast all Active projects, sorted by slip risk (high → low)."""
    projects = await projects_collection.find({"status": "Active"}).to_list(length=500)
    forecasts = []
    for p in projects:
        try:
            forecasts.append(await _forecast_one(p))
        except Exception as e:
            logger.warning(f"[Forecast] Skipping {p.get('name')}: {e}")
    forecasts.sort(key=lambda f: -f.get("slip_risk_score", 0))

    at_risk_30d = [
        f for f in forecasts
        if f.get("slip_risk_score", 0) >= 40
        or (f.get("slip_business_days") and f.get("slip_business_days", 0) > 5)
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "projects_analyzed": len(forecasts),
        "at_risk_30d_count": len(at_risk_30d),
        "forecasts": forecasts,
        "summary": {
            "critical": sum(1 for f in forecasts if f.get("slip_risk_label") == "Critical"),
            "high": sum(1 for f in forecasts if f.get("slip_risk_label") == "High"),
            "medium": sum(1 for f in forecasts if f.get("slip_risk_label") == "Medium"),
            "low": sum(1 for f in forecasts if f.get("slip_risk_label") == "Low"),
        },
    }
