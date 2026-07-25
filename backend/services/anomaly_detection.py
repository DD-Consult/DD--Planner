"""
Anomaly Detection Service
=========================
Statistical anomaly scanner across the portfolio. Complements the existing
Health Monitor by flagging patterns that are *unusual for this org*, not just
absolute thresholds.

Detects:
  • Timesheet drop         — a normally-active resource suddenly stops logging
  • Timesheet surge        — sudden spike in a resource's hours (potential
                              back-fill / dumping)
  • Burn-rate spike        — project consuming much more than its historical
                              weekly average
  • Activity blackout      — Active project with zero timesheet activity for
                              the last 14 days
  • Capacity crunch        — portfolio load jumped >25% week-over-week
  • Health trend downgrade — project's status updates degrading over time
                              (e.g. Green → Amber → Red)

Design:
- Baselines built from the last 8 weeks (fast enough for on-demand + daily)
- Every finding includes: type, severity, message, actor(s), metric, baseline,
  current, and (when possible) a suggested action
"""
from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from database import (
    projects_collection, resources_collection, timesheets_collection,
    allocations_collection, status_updates_collection, ai_health_reports_collection,
)

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


def _iso_week_start(d: datetime) -> datetime:
    """Monday 00:00 UTC of the ISO week containing d."""
    d = d.astimezone(timezone.utc)
    monday = d - timedelta(days=d.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


# ─────────────────────────────────────────────────────────────────────────
# Detectors
# ─────────────────────────────────────────────────────────────────────────

async def _detect_timesheet_anomalies(now: datetime) -> List[dict]:
    """Compare each resource's last-week hours against their 8-week rolling
    baseline. Flag drops and spikes."""
    findings: List[dict] = []
    window_end = _iso_week_start(now)  # start of current week (Mon 00:00)
    window_start = window_end - timedelta(weeks=8)
    last_week_start = window_end - timedelta(weeks=1)

    resources = await resources_collection.find({"active": {"$ne": False}}).to_list(length=500)
    if not resources:
        return findings

    ts = await timesheets_collection.find({
        "week_start_date": {"$gte": window_start.isoformat().split("T")[0]},
    }).to_list(length=10000)

    # Group hours by (resource_id, week_start)
    by_res: Dict[str, Dict[str, float]] = {}
    for t in ts:
        rid = str(t.get("resource_id", ""))
        wk = t.get("week_start_date", "")
        if not (rid and wk):
            continue
        actual = float(t.get("actual_hours") or 0)
        by_res.setdefault(rid, {}).setdefault(wk, 0.0)
        by_res[rid][wk] += actual

    for r in resources:
        rid = str(r["_id"])
        weekly = by_res.get(rid, {})
        history = [
            v for k, v in weekly.items()
            if k < last_week_start.date().isoformat()
        ]
        if len(history) < 4:  # not enough baseline
            continue
        current = weekly.get(last_week_start.date().isoformat(), 0.0)
        avg = statistics.mean(history)
        stdev = statistics.pstdev(history) if len(history) > 1 else 0

        # Drop: current is well below baseline and baseline was substantive
        if avg >= 15 and current <= max(avg * 0.30, 5):
            findings.append({
                "type": "timesheet_drop",
                "severity": "high" if current == 0 else "medium",
                "resource_id": rid,
                "resource_name": r.get("name"),
                "message": (
                    f"{r.get('name')} logged {current:.0f}h last week vs {avg:.0f}h avg "
                    f"— check-in required"
                ),
                "metric": "weekly_hours",
                "baseline": round(avg, 1),
                "current": round(current, 1),
                "suggested_action": "Reach out — possible leave, blocker, or capacity issue.",
            })
        # Surge: current is much larger than baseline (potential dumping)
        elif avg > 5 and current > avg + max(stdev * 2, 15) and current > avg * 1.6:
            findings.append({
                "type": "timesheet_surge",
                "severity": "low",
                "resource_id": rid,
                "resource_name": r.get("name"),
                "message": (
                    f"{r.get('name')} logged {current:.0f}h last week vs {avg:.0f}h avg "
                    f"— unusually high (possible back-fill)"
                ),
                "metric": "weekly_hours",
                "baseline": round(avg, 1),
                "current": round(current, 1),
                "suggested_action": "Verify timing accuracy of the entries.",
            })
    return findings


async def _detect_burn_rate_spikes(now: datetime) -> List[dict]:
    """Flag projects whose recent weekly burn is far above their historical
    weekly average."""
    findings: List[dict] = []
    window_end = _iso_week_start(now)
    window_start = window_end - timedelta(weeks=8)
    last_week = (window_end - timedelta(weeks=1)).date().isoformat()

    projects = await projects_collection.find({"status": "Active"}).to_list(length=500)
    ts = await timesheets_collection.find({
        "week_start_date": {"$gte": window_start.isoformat().split("T")[0]},
    }).to_list(length=20000)

    by_proj: Dict[str, Dict[str, float]] = {}
    for t in ts:
        pid = str(t.get("project_id", ""))
        wk = t.get("week_start_date", "")
        if not (pid and wk):
            continue
        by_proj.setdefault(pid, {}).setdefault(wk, 0.0)
        by_proj[pid][wk] += float(t.get("actual_hours") or 0)

    for p in projects:
        pid = str(p["_id"])
        weekly = by_proj.get(pid, {})
        if len(weekly) < 4:
            continue
        history = [v for k, v in weekly.items() if k < last_week]
        current = weekly.get(last_week, 0.0)
        if not history:
            continue
        avg = statistics.mean(history)
        # Only flag if current is meaningfully high AND >= 2x average
        if avg >= 8 and current >= avg * 2 and current - avg >= 15:
            findings.append({
                "type": "burn_rate_spike",
                "severity": "medium",
                "project_id": pid,
                "project_name": p.get("name"),
                "message": (
                    f"'{p.get('name')}' burned {current:.0f}h last week vs "
                    f"{avg:.0f}h weekly avg — investigate scope creep or crunch"
                ),
                "metric": "weekly_burn_hours",
                "baseline": round(avg, 1),
                "current": round(current, 1),
                "suggested_action": "Review status update & timesheet detail for last week.",
            })
    return findings


async def _detect_activity_blackout(now: datetime) -> List[dict]:
    """Active projects with zero timesheet activity in the last 14 days."""
    findings: List[dict] = []
    cutoff = (now - timedelta(days=14)).date().isoformat()

    projects = await projects_collection.find({"status": "Active"}).to_list(length=500)
    recent_ts = await timesheets_collection.find(
        {"week_start_date": {"$gte": cutoff}, "actual_hours": {"$gt": 0}},
        {"project_id": 1},
    ).to_list(length=20000)
    active_pids = {str(t.get("project_id")) for t in recent_ts}

    for p in projects:
        pid = str(p["_id"])
        if pid in active_pids:
            continue
        # Skip brand-new projects (< 14 days old)
        start = _dt_utc(p.get("start_date"))
        if start and (now - start).days < 14:
            continue
        findings.append({
            "type": "activity_blackout",
            "severity": "high",
            "project_id": pid,
            "project_name": p.get("name"),
            "message": (
                f"'{p.get('name')}' has zero timesheet activity in the last 14 days "
                f"despite being Active"
            ),
            "metric": "days_since_activity",
            "baseline": None,
            "current": None,
            "suggested_action": "Confirm project is truly active — move to On Hold if paused.",
        })
    return findings


async def _detect_health_trend_downgrade(now: datetime) -> List[dict]:
    """Detect a downward trend in status update health (Green → Amber → Red)."""
    findings: List[dict] = []
    horizon = now - timedelta(weeks=6)

    projects = await projects_collection.find({"status": "Active"}).to_list(length=500)
    updates = await status_updates_collection.find(
        {"created_at": {"$gte": horizon}}
    ).sort("created_at", 1).to_list(length=2000)

    by_proj: Dict[str, List[dict]] = {}
    for su in updates:
        pid = str(su.get("project_id", ""))
        by_proj.setdefault(pid, []).append(su)

    order = {"Green": 3, "Amber": 2, "Red": 1}
    for p in projects:
        pid = str(p["_id"])
        history = by_proj.get(pid, [])
        if len(history) < 3:
            continue
        recent = history[-3:]
        scores = [order.get(su.get("health", "Amber"), 2) for su in recent]
        # Monotone decreasing? and last is Amber or Red?
        is_downgrade = scores[0] > scores[1] > scores[2] and scores[-1] <= 2
        if is_downgrade:
            findings.append({
                "type": "health_downgrade",
                "severity": "high" if scores[-1] == 1 else "medium",
                "project_id": pid,
                "project_name": p.get("name"),
                "message": (
                    f"'{p.get('name')}' health trending down: "
                    + " → ".join(su.get("health", "?") for su in recent)
                ),
                "metric": "health_trend",
                "baseline": recent[0].get("health"),
                "current": recent[-1].get("health"),
                "suggested_action": "Escalate — schedule mitigation review.",
            })
    return findings


async def _detect_capacity_crunch(now: datetime) -> List[dict]:
    """Compare this week's total allocation load vs last week."""
    findings: List[dict] = []
    this_week_start = _iso_week_start(now)
    last_week_start = this_week_start - timedelta(weeks=1)
    this_week_end = this_week_start + timedelta(days=7)
    last_week_end = this_week_start

    allocs = await allocations_collection.find().to_list(length=5000)

    def _load_for(range_start: datetime, range_end: datetime) -> float:
        total = 0.0
        for a in allocs:
            s = _dt_utc(a.get("start_date"))
            e = _dt_utc(a.get("end_date"))
            if not (s and e):
                continue
            # Overlap
            if e < range_start or s > range_end:
                continue
            total += float(a.get("percentage") or 0)
        return total

    curr = _load_for(this_week_start, this_week_end)
    prev = _load_for(last_week_start, last_week_end)
    if prev >= 100 and curr >= prev * 1.25 and curr - prev >= 100:
        findings.append({
            "type": "capacity_crunch",
            "severity": "medium",
            "message": (
                f"Portfolio load jumped from {prev:.0f}% to {curr:.0f}% "
                f"({(curr-prev)/prev*100:.0f}% WoW increase) — check for hiring/rebalancing"
            ),
            "metric": "portfolio_load_pct",
            "baseline": round(prev, 1),
            "current": round(curr, 1),
            "suggested_action": "Consider deferring lower-priority projects or hiring.",
        })
    return findings


# ─────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────

async def run_anomaly_scan(triggered_by: str = "system", save_report: bool = True) -> dict:
    """Run all detectors. Returns a report dict."""
    logger.info(f"[Anomaly] Starting scan (triggered by: {triggered_by})")
    now = datetime.now(timezone.utc)

    findings: List[dict] = []
    for detector in (
        _detect_timesheet_anomalies,
        _detect_burn_rate_spikes,
        _detect_activity_blackout,
        _detect_health_trend_downgrade,
        _detect_capacity_crunch,
    ):
        try:
            findings.extend(await detector(now))
        except Exception as e:
            logger.exception(f"[Anomaly] Detector {detector.__name__} failed: {e}")

    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: sev_order.get(f.get("severity", "low"), 3))

    report = {
        "triggered_by": triggered_by,
        "created_at": now.isoformat(),
        "type": "anomaly_scan",
        "findings": findings,
        "summary": {
            "total_findings": len(findings),
            "critical": sum(1 for f in findings if f.get("severity") == "critical"),
            "high": sum(1 for f in findings if f.get("severity") == "high"),
            "medium": sum(1 for f in findings if f.get("severity") == "medium"),
            "low": sum(1 for f in findings if f.get("severity") == "low"),
        },
    }

    if save_report:
        try:
            await ai_health_reports_collection.insert_one(dict(report))
        except Exception as e:
            logger.warning(f"[Anomaly] Failed to save report: {e}")

    logger.info(f"[Anomaly] Scan complete — {len(findings)} findings")
    return report


async def get_latest_anomaly_report() -> dict | None:
    doc = await ai_health_reports_collection.find_one(
        {"type": "anomaly_scan"}, sort=[("created_at", -1)]
    )
    if not doc:
        return None
    doc.pop("_id", None)
    return doc
