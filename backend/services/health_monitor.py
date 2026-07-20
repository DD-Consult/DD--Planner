"""
Proactive Project Health Monitor
==================================
Runs AI-powered health analysis across the entire portfolio.
Creates notifications for critical findings, stores reports in ai_health_reports.

Can be triggered:
  1. On-demand via POST /api/ai/health-monitor/run
  2. As a daily background task started at server startup
  3. Via AI chat action `run_health_check`
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from bson import ObjectId

from database import (
    projects_collection, resources_collection, allocations_collection,
    timesheets_collection, risks_collection, status_updates_collection,
    wbs_tasks_collection, notifications_collection, ai_health_reports_collection,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────
# Core analysis helpers
# ─────────────────────────────────────────────────────────────────────────

async def _get_portfolio_snapshot() -> dict:
    """Fetch minimal portfolio data needed for health analysis."""
    now = datetime.now(timezone.utc)

    projects = await projects_collection.find({"status": {"$in": ["Active", "Pipeline"]}}).to_list(length=500)
    resources = await resources_collection.find({"active": {"$ne": False}}).to_list(length=500)
    allocations = await allocations_collection.find().to_list(length=5000)
    risks = await risks_collection.find({"status": {"$in": ["Active", "Accepted"]}}).to_list(length=2000)
    timesheets = await timesheets_collection.find().to_list(length=10000)
    status_updates = await status_updates_collection.find().sort("created_at", -1).to_list(length=500)
    wbs_tasks = await wbs_tasks_collection.find().to_list(length=5000)

    # Index for quick lookup
    latest_status: Dict[str, dict] = {}
    for su in status_updates:
        pid = su.get("project_id")
        if pid and pid not in latest_status:
            latest_status[pid] = su

    resource_map = {str(r["_id"]): r.get("name", "?") for r in resources}
    project_map = {str(p["_id"]): p.get("name", "?") for p in projects}

    return {
        "now": now,
        "projects": projects,
        "resources": resources,
        "allocations": allocations,
        "risks": risks,
        "timesheets": timesheets,
        "wbs_tasks": wbs_tasks,
        "latest_status": latest_status,
        "resource_map": resource_map,
        "project_map": project_map,
    }


def _dt_utc(dt) -> datetime | None:
    """Ensure a datetime is UTC-aware. Returns None if input is None or unparseable."""
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            return None
    if isinstance(dt, datetime):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def _check_budget_alerts(projects, timesheets) -> List[dict]:
    findings = []
    ts_by_project: Dict[str, List[dict]] = {}
    for t in timesheets:
        pid = t.get("project_id", "")
        ts_by_project.setdefault(pid, []).append(t)

    for p in projects:
        if p.get("status") != "Active":
            continue
        pid = str(p["_id"])
        budgeted = p.get("budgeted_hours") or 0
        if not budgeted:
            continue
        actual = sum(t.get("actual_hours", 0) for t in ts_by_project.get(pid, []))
        pct = (actual / budgeted) * 100 if budgeted else 0
        if pct >= 100:
            findings.append({
                "type": "budget_overrun",
                "severity": "critical",
                "project_id": pid,
                "project_name": p.get("name"),
                "message": f"'{p.get('name')}' has consumed {actual:.0f}h of {budgeted:.0f}h budget ({pct:.0f}%) — over budget",
                "value": pct,
            })
        elif pct >= 80:
            findings.append({
                "type": "budget_warning",
                "severity": "high",
                "project_id": pid,
                "project_name": p.get("name"),
                "message": f"'{p.get('name')}' is at {pct:.0f}% budget utilisation ({actual:.0f}h / {budgeted:.0f}h) — approaching limit",
                "value": pct,
            })
    return findings


def _check_over_allocations(resources, allocations, now) -> List[dict]:
    findings = []
    allocs_by_res: Dict[str, List[dict]] = {}
    for a in allocations:
        rid = a.get("resource_id", "")
        allocs_by_res.setdefault(rid, []).append(a)

    for r in resources:
        rid = str(r["_id"])
        active_allocs = [
            a for a in allocs_by_res.get(rid, [])
            if _dt_utc(a.get("start_date")) and _dt_utc(a.get("end_date"))
            and _dt_utc(a["start_date"]) <= now <= _dt_utc(a["end_date"])
        ]
        total_pct = sum(a.get("percentage", 0) for a in active_allocs)
        if total_pct > 120:
            findings.append({
                "type": "over_allocation",
                "severity": "critical",
                "resource_id": rid,
                "resource_name": r.get("name"),
                "message": f"{r.get('name')} is critically over-allocated at {total_pct}% across {len(active_allocs)} project(s)",
                "value": total_pct,
            })
        elif total_pct > 100:
            findings.append({
                "type": "over_allocation",
                "severity": "high",
                "resource_id": rid,
                "resource_name": r.get("name"),
                "message": f"{r.get('name')} is over-allocated at {total_pct}% — needs redistribution",
                "value": total_pct,
            })
    return findings


def _check_stale_updates(projects, latest_status, now) -> List[dict]:
    findings = []
    cutoff_critical = now - timedelta(days=21)
    cutoff_warning = now - timedelta(days=14)

    for p in projects:
        if p.get("status") != "Active":
            continue
        pid = str(p["_id"])
        su = latest_status.get(pid)
        if not su:
            findings.append({
                "type": "stale_status",
                "severity": "high",
                "project_id": pid,
                "project_name": p.get("name"),
                "message": f"'{p.get('name')}' has never had a status update — add one to track progress",
                "value": None,
            })
            continue
        created = su.get("created_at") or su.get("week_start_date")
        created_dt = _dt_utc(created)
        if created_dt:
            if created_dt < cutoff_critical:
                days_ago = (now - created_dt).days
                findings.append({
                    "type": "stale_status",
                    "severity": "high",
                    "project_id": pid,
                    "project_name": p.get("name"),
                    "message": f"'{p.get('name')}' has no status update in {days_ago} days — overdue",
                    "value": days_ago,
                })
            elif created_dt < cutoff_warning:
                days_ago = (now - created_dt).days
                findings.append({
                    "type": "stale_status",
                    "severity": "medium",
                    "project_id": pid,
                    "project_name": p.get("name"),
                    "message": f"'{p.get('name')}' last updated {days_ago} days ago",
                    "value": days_ago,
                })
    return findings


def _check_overdue_milestones(wbs_tasks, now) -> List[dict]:
    findings = []
    overdue: Dict[str, int] = {}  # project_id → count

    for task in wbs_tasks:
        if not task.get("is_milestone"):
            continue
        if task.get("status") in ("done", "completed"):
            continue
        end_dt = _dt_utc(task.get("end_date"))
        if end_dt and end_dt < now:
            pid = task.get("project_id", "")
            overdue[pid] = overdue.get(pid, 0) + 1

    for pid, count in overdue.items():
        findings.append({
            "type": "overdue_milestone",
            "severity": "high",
            "project_id": pid,
            "message": f"Project has {count} overdue milestone(s) — schedule review needed",
            "value": count,
        })
    return findings


def _check_stale_risks(risks, now) -> List[dict]:
    findings = []
    stale_cutoff = now - timedelta(days=30)

    stale_critical = [
        r for r in risks
        if r.get("impact") in ("High", "Critical")
        and r.get("probability") in ("High", "Medium")
        and not r.get("mitigation")
    ]

    if stale_critical:
        # Group by project
        by_project: Dict[str, int] = {}
        for r in stale_critical:
            pid = r.get("project_id", "unknown")
            by_project[pid] = by_project.get(pid, 0) + 1
        for pid, count in by_project.items():
            findings.append({
                "type": "unmitigated_risks",
                "severity": "high",
                "project_id": pid,
                "message": f"Project has {count} high/critical risk(s) with no mitigation plan",
                "value": count,
            })
    return findings


# ─────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────

async def run_health_monitor(triggered_by: str = "system", save_report: bool = True) -> dict:
    """
    Run the full portfolio health analysis.
    Returns the health report dict.
    """
    logger.info(f"[HealthMonitor] Starting health check (triggered by: {triggered_by})")
    now = datetime.now(timezone.utc)

    try:
        snap = await _get_portfolio_snapshot()
    except Exception as e:
        logger.error(f"[HealthMonitor] Failed to load portfolio snapshot: {e}")
        return {"error": str(e), "findings": []}

    all_findings: List[dict] = []
    all_findings.extend(_check_budget_alerts(snap["projects"], snap["timesheets"]))
    all_findings.extend(_check_over_allocations(snap["resources"], snap["allocations"], snap["now"]))
    all_findings.extend(_check_stale_updates(snap["projects"], snap["latest_status"], snap["now"]))
    all_findings.extend(_check_overdue_milestones(snap["wbs_tasks"], snap["now"]))
    all_findings.extend(_check_stale_risks(snap["risks"], snap["now"]))

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_findings.sort(key=lambda f: severity_order.get(f.get("severity", "low"), 3))

    critical_count = sum(1 for f in all_findings if f.get("severity") == "critical")
    high_count = sum(1 for f in all_findings if f.get("severity") == "high")

    report = {
        "triggered_by": triggered_by,
        "created_at": now.isoformat(),
        "projects_analyzed": len(snap["projects"]),
        "findings": all_findings,
        "summary": {
            "total_findings": len(all_findings),
            "critical": critical_count,
            "high": high_count,
            "medium": sum(1 for f in all_findings if f.get("severity") == "medium"),
            "low": sum(1 for f in all_findings if f.get("severity") == "low"),
        },
        "overall_health": "Critical" if critical_count > 0 else ("At Risk" if high_count > 0 else "Healthy"),
    }

    if save_report:
        await ai_health_reports_collection.insert_one(dict(report))

    # Create notifications for critical findings
    critical_findings = [f for f in all_findings if f.get("severity") == "critical"]
    notif_count = 0
    for finding in critical_findings[:5]:  # Cap at 5 notifications per run
        try:
            # Find project lead or notify all admins
            from database import users_collection
            admins = await users_collection.find(
                {"role": {"$in": ["admin", "super_admin"]}, "disabled": {"$ne": True}}
            ).to_list(length=20)
            for admin in admins[:3]:  # Notify up to 3 admins
                await notifications_collection.insert_one({
                    "user_email": admin.get("email"),
                    "message": f"[Health Alert] {finding['message']}",
                    "link": f"/projects/{finding.get('project_id', '')}",
                    "type": "alert",
                    "read": False,
                    "severity": finding.get("severity"),
                    "created_at": now.isoformat(),
                    "source": "health_monitor",
                })
                notif_count += 1
        except Exception as e:
            logger.warning(f"[HealthMonitor] Failed to create notification: {e}")

    report["notifications_created"] = notif_count
    logger.info(
        f"[HealthMonitor] Complete — {len(all_findings)} findings "
        f"({critical_count} critical, {high_count} high), {notif_count} notifications sent"
    )
    return report


async def get_latest_report() -> dict | None:
    """Get the most recently saved health report."""
    doc = await ai_health_reports_collection.find_one({}, sort=[("created_at", -1)])
    if not doc:
        return None
    doc.pop("_id", None)
    return doc
