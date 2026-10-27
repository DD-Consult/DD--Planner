"""Admin 'generate realistic sample data' tool (Bedrock-plan Phase 2A).

Creates believable FAKE data in the CURRENT (real) workspace DB for demos,
trials and training — DISTINCT from the isolated read-only public demo. Every
doc is tagged `sample_data: True` and carries a `sample_batch` id so it can be
removed cleanly later.

Idempotent-ish: each generate call adds ONE batch; a hard cap prevents runaway.
remove_sample_data() wipes all `sample_data: True` docs across collections.
"""
from datetime import datetime, timedelta, timezone
import uuid

from database import (
    projects_collection,
    resources_collection,
    allocations_collection,
    wbs_tasks_collection,
    risks_collection,
    status_updates_collection,
    timesheets_collection,
    proposals_collection,
    users_collection,
    report_links_collection,
)
from services.proposals.renderer import load_sample_brief

TAG = "sample_data"
MAX_SAMPLE_PROJECTS = 40  # safety cap across all batches

# Believable fake content (NOT real client/people names).
_RESOURCES = [
    ("Priya Nair", "Senior Consultant", 100),
    ("Liam O'Brien", "Solutions Architect", 100),
    ("Sofia Martinez", "Business Analyst", 80),
    ("Noah Kim", "Full-Stack Engineer", 100),
    ("Ava Thompson", "Change Manager", 60),
    ("Ethan Walsh", "Data Engineer", 100),
]
_PROJECTS = [
    ("Customer Data Platform", "Meridian Retail Group", "Active",
     "Unify fragmented customer data into a single governed platform."),
    ("Claims Automation", "Summit Insurance", "Active",
     "Automate the end-to-end claims intake and triage workflow."),
    ("Field Ops Mobile App", "Harbour Utilities", "Active",
     "Give field crews an offline-first mobile app for work orders."),
    ("Finance Modernisation", "Aurora Manufacturing", "Pipeline",
     "Replace legacy finance processes with an integrated stack."),
]
_RISKS = [
    ("Key SME availability is limited during discovery", "High", "Medium",
     "Agree a RACI and lock SME time in the kickoff."),
    ("Legacy data quality may slow migration", "Medium", "High",
     "Run an early data-profiling spike to size the cleanup."),
    ("Scope creep from adjacent teams", "Medium", "Medium",
     "Use a change log and a weekly scope review."),
]
_WBS = [
    ("Discovery & current-state audit", "done", 40),
    ("Target architecture & design", "in_progress", 60),
    ("Build core integration layer", "in_progress", 120),
    ("Data migration & validation", "todo", 80),
    ("UAT & cutover", "todo", 60),
    ("Hypercare & handover", "todo", 30),
]


async def sample_data_status() -> dict:
    """Counts of existing sample data across collections."""
    out = {}
    for name, col in [
        ("projects", projects_collection), ("resources", resources_collection),
        ("allocations", allocations_collection), ("wbs_tasks", wbs_tasks_collection),
        ("risks", risks_collection), ("status_updates", status_updates_collection),
        ("timesheets", timesheets_collection), ("proposals", proposals_collection),
    ]:
        try:
            out[name] = await col.count_documents({TAG: True})
        except Exception:
            out[name] = 0
    out["total"] = sum(out.values())
    return out


async def generate_sample_data(created_by: str = "") -> dict:
    """Generate ONE batch of believable sample data in the current workspace DB."""
    # Safety cap
    existing_projects = await projects_collection.count_documents({TAG: True})
    if existing_projects >= MAX_SAMPLE_PROJECTS:
        return {"status": "capped",
                "message": f"Sample-data cap reached ({MAX_SAMPLE_PROJECTS} projects). Remove existing sample data first.",
                "counts": await sample_data_status()}

    batch = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc)
    today = datetime(now.year, now.month, now.day)
    counts = {"resources": 0, "projects": 0, "allocations": 0, "wbs_tasks": 0,
              "risks": 0, "status_updates": 0, "timesheets": 0, "proposals": 0}

    def _meta():
        return {TAG: True, "sample_batch": batch, "created_at": now.isoformat()}

    # Resources
    resource_ids = []
    try:
        for name, role, cap in _RESOURCES:
            doc = {"name": f"{name}", "role": role, "standard_capacity": cap, "active": True,
                   "avatar_url": f"https://api.dicebear.com/7.x/avataaars/svg?seed={name.replace(' ', '')}{batch}",
                   **_meta()}
            r = await resources_collection.insert_one(doc)
            resource_ids.append(str(r.inserted_id))
            counts["resources"] += 1
    except Exception as e:
        print(f"[sample_data] resources: {e}")

    # Projects (+ phases)
    project_ids = []
    try:
        for i, (pname, client, status, objective) in enumerate(_PROJECTS):
            start = today - timedelta(days=20 + i * 5)
            end = today + timedelta(days=50 + i * 10)
            mid = start + (end - start) / 2
            phases = [
                {"id": str(uuid.uuid4()), "name": "Discovery & Design", "start_date": start,
                 "end_date": mid, "status": "Active"},
                {"id": str(uuid.uuid4()), "name": "Build & Rollout", "start_date": mid,
                 "end_date": end, "status": "Pending"},
            ]
            doc = {"name": f"{pname}", "client_name": client, "status": status,
                   "start_date": start, "end_date": end, "phases": phases,
                   "budgeted_hours": 300 + i * 120, "project_objective": objective,
                   "health": ["Green", "Amber", "Green", "Green"][i % 4],
                   "schedule_status": "On Track",
                   "main_contact_name": "Jordan Blake", "main_contact_email": f"contact@{client.split()[0].lower()}-demo.test",
                   **_meta()}
            pr = await projects_collection.insert_one(doc)
            project_ids.append((str(pr.inserted_id), phases, start, end))
            counts["projects"] += 1
    except Exception as e:
        print(f"[sample_data] projects: {e}")

    # Allocations (spread resources across projects; include an over-allocation)
    try:
        for pi, (pid, phases, pstart, pend) in enumerate(project_ids):
            for ri in range(3):  # 3 resources per project
                rid = resource_ids[(pi + ri) % len(resource_ids)] if resource_ids else None
                if not rid:
                    continue
                pct = [70, 60, 50][ri]
                if pi == 0 and ri == 0:
                    pct = 120  # deliberate over-allocation for the heatmap
                await allocations_collection.insert_one({
                    "resource_id": rid, "project_id": pid, "percentage": pct,
                    "allocation_type": "percentage", "role": _RESOURCES[(pi + ri) % len(_RESOURCES)][1],
                    "start_date": pstart, "end_date": pend, **_meta()})
                counts["allocations"] += 1
    except Exception as e:
        print(f"[sample_data] allocations: {e}")

    # WBS tasks with a dependency chain + a milestone
    try:
        for (pid, phases, pstart, pend) in project_ids[:3]:  # active-ish projects
            prev_id = None
            for ti, (tname, tstatus, est) in enumerate(_WBS):
                tstart = pstart + timedelta(days=ti * 7)
                tend = tstart + timedelta(days=6)
                task = {
                    "project_id": pid, "name": tname, "status": tstatus,
                    "phase_id": phases[0]["id"] if ti < 3 else phases[1]["id"],
                    "assigned_to": resource_ids[ti % len(resource_ids)] if resource_ids else None,
                    "estimated_hours": est, "start_date": tstart.isoformat(), "end_date": tend.isoformat(),
                    "order": ti, "dependencies": [prev_id] if prev_id else [],
                    "is_milestone": ti == len(_WBS) - 1, **_meta()}
                res = await wbs_tasks_collection.insert_one(task)
                prev_id = str(res.inserted_id)
                counts["wbs_tasks"] += 1
    except Exception as e:
        print(f"[sample_data] wbs: {e}")

    # Risks (active projects)
    try:
        for (pid, _ph, _s, _e) in project_ids[:3]:
            for desc, impact, prob, mit in _RISKS:
                await risks_collection.insert_one({
                    "project_id": pid, "description": desc, "impact": impact,
                    "probability": prob, "mitigation": mit, "status": "Active",
                    "category": "Risk", **_meta()})
                counts["risks"] += 1
    except Exception as e:
        print(f"[sample_data] risks: {e}")

    # Status updates with AI-style summaries
    try:
        for idx, (pid, _ph, _s, _e) in enumerate(project_ids[:3]):
            await status_updates_collection.insert_one({
                "project_id": pid, "updated_by": created_by or "sample@dd",
                "update_date": now.isoformat(), "created_at": now.isoformat(),
                "health": ["Green", "Amber", "Green"][idx], "schedule_status": "On Track",
                "actual_progress": [45, 30, 20][idx],
                "accomplishments": "Completed discovery interviews and signed off the current-state audit.",
                "blockers": "Awaiting access to the legacy billing extract.",
                "next_steps": "Finalise target architecture and begin the integration spike.",
                "ai_generated_summary": "The project is tracking to plan with discovery complete; the main watch-item is legacy data access, which could affect the migration timeline if not resolved this week.",
                **_meta()})
            counts["status_updates"] += 1
    except Exception as e:
        print(f"[sample_data] status_updates: {e}")

    # A couple of timesheets (current week) for the first project
    try:
        if project_ids and resource_ids:
            pid0, phases0 = project_ids[0][0], project_ids[0][1]
            week_start = today - timedelta(days=today.weekday())
            for ri in range(2):
                await timesheets_collection.insert_one({
                    "resource_id": resource_ids[ri], "project_id": pid0,
                    "phase_id": phases0[0]["id"], "week_start_date": week_start,
                    "week_end_date": week_start + timedelta(days=4),
                    "planned_hours": 24, "actual_hours": 22 + ri, "variance_hours": -2 + ri,
                    "variance_percentage": 0, "status": "Submitted",
                    "auto_filled": False, "modified_by_user": True,
                    "submitted_at": now.isoformat(), "created_at": now.isoformat(), **_meta()})
                counts["timesheets"] += 1
    except Exception as e:
        print(f"[sample_data] timesheets: {e}")

    # A couple of proposals (one Sent, one Confirmed linked to a project)
    try:
        import secrets
        brief = load_sample_brief()
        b1 = dict(brief); b1["client_name"] = "Meridian Retail Group"; b1["proposal_title"] = "Customer Data Platform"
        await proposals_collection.insert_one({
            "token": secrets.token_urlsafe(32), "status": "Sent", "data": b1,
            "created_by": created_by or "sample@dd", "created_at": now, "updated_at": now,
            "sent_at": now, "valid_until_date": None, "accepted_by": None, "accepted_path": None,
            "accepted_at": None, "decline_reason": None, "declined_at": None, "confirmed_at": None,
            "linked_project_id": None, "linked_client_user_id": None, "linked_report_token": None,
            "last_client_activity_at": now, **_meta()})
        counts["proposals"] += 1
        if project_ids:
            b2 = dict(brief); b2["client_name"] = "Summit Insurance"; b2["proposal_title"] = "Claims Automation"
            await proposals_collection.insert_one({
                "token": secrets.token_urlsafe(32), "status": "Confirmed", "data": b2,
                "created_by": created_by or "sample@dd", "created_at": now, "updated_at": now,
                "sent_at": now, "valid_until_date": None, "accepted_by": "Jordan Blake, COO",
                "accepted_path": "a", "accepted_at": now, "decline_reason": None, "declined_at": None,
                "confirmed_at": now, "linked_project_id": project_ids[1][0] if len(project_ids) > 1 else None,
                "linked_client_user_id": None, "linked_report_token": None,
                "last_client_activity_at": now, **_meta()})
            counts["proposals"] += 1
    except Exception as e:
        print(f"[sample_data] proposals: {e}")

    return {"status": "ok", "batch": batch, "counts": counts,
            "message": f"Generated sample data: {sum(counts.values())} records across {counts['projects']} projects."}


async def remove_sample_data() -> dict:
    """Delete ALL sample data (sample_data: True) across collections."""
    removed = {}
    cols = {
        "projects": projects_collection, "resources": resources_collection,
        "allocations": allocations_collection, "wbs_tasks": wbs_tasks_collection,
        "risks": risks_collection, "status_updates": status_updates_collection,
        "timesheets": timesheets_collection, "proposals": proposals_collection,
        "report_links": report_links_collection, "users": users_collection,
    }
    for name, col in cols.items():
        try:
            r = await col.delete_many({TAG: True})
            removed[name] = r.deleted_count
        except Exception as e:
            print(f"[sample_data] remove {name}: {e}")
            removed[name] = 0
    removed["total"] = sum(removed.values())
    return {"status": "ok", "removed": removed}
