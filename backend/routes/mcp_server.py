"""
MCP (Model Context Protocol) server for DD Planner.

Exposes project data as tools that any MCP-compatible AI agent (Gemini, Copilot, etc.)
can query using natural language.

Protocol: JSON-RPC 2.0 over HTTP (Streamable HTTP — MCP 2025 spec)
Auth:      X-Agent-Key header (API key from integration_settings)

Endpoints:
  GET  /api/mcp          — server info + capabilities (no auth required, allows discovery)
  POST /api/mcp          — JSON-RPC 2.0 endpoint (requires X-Agent-Key)
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from database import (
    projects_collection,
    allocations_collection,
    resources_collection,
    status_updates_collection,
    integration_settings_collection,
)

logger = logging.getLogger(__name__)
router = APIRouter()

ORG_ID = "default"

# ─── Tool definitions ─────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "list_projects",
        "description": "List all projects with their current health, progress and status. Optionally filter by status (Active, Pipeline, Completed).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status_filter": {
                    "type": "string",
                    "description": "Optional status filter: Active, Pipeline, Completed, or All",
                    "default": "Active",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_project_status",
        "description": "Get the full status details for a specific project — health, progress, recent status update, team members, and risks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "The project name (partial match supported)",
                },
                "project_id": {
                    "type": "string",
                    "description": "The exact project ID (optional — use if name is ambiguous)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_team_capacity",
        "description": "Get current team capacity — who is over-allocated, who is on the bench, and who is available.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_recent_updates",
        "description": "Get the most recent status updates submitted across all projects (or for a specific project) in the last N days.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "How many days back to look (default 14)",
                    "default": 14,
                },
                "project_name": {
                    "type": "string",
                    "description": "Optional project name filter",
                },
            },
            "required": [],
        },
    },
]


# ─── Auth helper ──────────────────────────────────────────────────────────────

async def _validate_agent_key(request: Request):
    """Validate X-Agent-Key header against the stored agent API key."""
    key = request.headers.get("X-Agent-Key") or request.headers.get("x-agent-key")
    if not key:
        raise HTTPException(status_code=401, detail="Missing X-Agent-Key header")

    doc = await integration_settings_collection.find_one({"org_id": ORG_ID})
    if not doc:
        raise HTTPException(status_code=401, detail="Agent API not configured")

    agent = doc.get("agent_api", {})
    if not agent.get("enabled"):
        raise HTTPException(status_code=403, detail="Agent API is disabled")

    stored_key = agent.get("api_key", "")
    if not stored_key or key != stored_key:
        raise HTTPException(status_code=401, detail="Invalid agent API key")

    # Update last_used_at
    await integration_settings_collection.update_one(
        {"org_id": ORG_ID},
        {"$set": {"agent_api.last_used_at": datetime.now(timezone.utc)}},
    )


# ─── Tool implementations ─────────────────────────────────────────────────────

def _serialize(doc: dict) -> dict:
    """Remove MongoDB _id and convert dates to strings."""
    result = {}
    for k, v in doc.items():
        if k == "_id":
            result["id"] = str(v)
        elif hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        elif isinstance(v, list):
            result[k] = [_serialize(i) if isinstance(i, dict) else i for i in v]
        elif isinstance(v, dict):
            result[k] = _serialize(v)
        else:
            result[k] = v
    return result


async def tool_list_projects(args: dict) -> Any:
    status_filter = args.get("status_filter", "Active")
    query = {} if status_filter == "All" else {"status": status_filter}

    cursor = projects_collection.find(query, {
        "_id": 1, "name": 1, "client_name": 1, "status": 1,
        "health": 1, "actual_progress": 1, "start_date": 1, "end_date": 1,
        "schedule_status": 1, "project_lead_name": 1,
    }).sort("name", 1)
    projects = await cursor.to_list(length=200)

    return [
        {
            "id": str(p["_id"]),
            "name": p.get("name", ""),
            "client": p.get("client_name", ""),
            "status": p.get("status", ""),
            "health": p.get("health", "Unknown"),
            "progress_pct": p.get("actual_progress", 0),
            "start_date": str(p.get("start_date", ""))[:10],
            "end_date": str(p.get("end_date", ""))[:10],
            "schedule_status": p.get("schedule_status", ""),
            "lead": p.get("project_lead_name", ""),
        }
        for p in projects
    ]


async def tool_get_project_status(args: dict) -> Any:
    from bson import ObjectId

    project = None
    project_id = args.get("project_id", "")
    project_name = args.get("project_name", "")

    if project_id:
        try:
            project = await projects_collection.find_one({"_id": ObjectId(project_id)})
        except Exception:
            pass

    if not project and project_name:
        import re
        regex = re.compile(re.escape(project_name), re.IGNORECASE)
        project = await projects_collection.find_one({"name": {"$regex": regex}})

    if not project:
        return {"error": "Project not found"}

    proj_id = str(project["_id"])

    # Latest status update
    latest_update = await status_updates_collection.find_one(
        {"project_id": proj_id},
        sort=[("created_at", -1)],
    )

    # Team members via allocations
    allocs = await allocations_collection.find({"project_id": proj_id}).to_list(length=100)
    resource_ids = list({a["resource_id"] for a in allocs})
    resources = await resources_collection.find(
        {"_id": {"$in": [__import__("bson").ObjectId(rid) for rid in resource_ids if rid]}},
        {"name": 1, "role": 1},
    ).to_list(length=50)

    result = {
        "id": proj_id,
        "name": project.get("name", ""),
        "client": project.get("client_name", ""),
        "status": project.get("status", ""),
        "health": project.get("health", "Unknown"),
        "progress_pct": project.get("actual_progress", 0),
        "start_date": str(project.get("start_date", ""))[:10],
        "end_date": str(project.get("end_date", ""))[:10],
        "schedule_status": project.get("schedule_status", ""),
        "lead": project.get("project_lead_name", ""),
        "description": project.get("description", ""),
        "team": [{"name": r.get("name"), "role": r.get("role")} for r in resources],
        "latest_status_update": None,
    }

    if latest_update:
        blockers = latest_update.get("blockers", [])
        result["latest_status_update"] = {
            "date": str(latest_update.get("created_at", ""))[:10],
            "health": latest_update.get("health", ""),
            "progress_pct": latest_update.get("actual_progress", 0),
            "summary": latest_update.get("ai_generated_summary") or latest_update.get("accomplishments", ""),
            "blockers": blockers if isinstance(blockers, list) else [blockers],
            "next_steps": latest_update.get("next_steps", ""),
            "submitted_by": latest_update.get("updated_by", ""),
        }

    return result


async def tool_get_team_capacity(args: dict) -> Any:
    from datetime import date

    today = date.today()
    today_str = today.isoformat()

    resources = await resources_collection.find(
        {"active": {"$ne": False}},
        {"_id": 1, "name": 1, "role": 1},
    ).to_list(length=200)

    allocs = await allocations_collection.find({
        "start_date": {"$lte": datetime.combine(today, datetime.min.time())},
        "end_date":   {"$gte": datetime.combine(today, datetime.min.time())},
    }).to_list(length=1000)

    alloc_map: dict[str, int] = {}
    for a in allocs:
        rid = a["resource_id"]
        alloc_map[rid] = alloc_map.get(rid, 0) + (a.get("percentage") or 0)

    result = []
    for r in resources:
        rid = str(r["_id"])
        pct = alloc_map.get(rid, 0)
        result.append({
            "name": r.get("name"),
            "role": r.get("role"),
            "current_utilization_pct": min(pct, 200),
            "status": "over-allocated" if pct > 100 else "available" if pct < 50 else "allocated",
        })

    result.sort(key=lambda x: -x["current_utilization_pct"])
    return result


async def tool_get_recent_updates(args: dict) -> Any:
    days = int(args.get("days", 14))
    project_name_filter = args.get("project_name", "")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query: dict = {"created_at": {"$gte": cutoff}}
    if project_name_filter:
        import re
        projects_cursor = projects_collection.find(
            {"name": {"$regex": re.compile(re.escape(project_name_filter), re.IGNORECASE)}},
            {"_id": 1, "name": 1},
        )
        matching = await projects_cursor.to_list(length=20)
        ids = [str(p["_id"]) for p in matching]
        if ids:
            query["project_id"] = {"$in": ids}

    cursor = status_updates_collection.find(
        query,
        {"_id": 0, "project_id": 1, "health": 1, "actual_progress": 1,
         "accomplishments": 1, "blockers": 1, "next_steps": 1,
         "ai_generated_summary": 1, "updated_by": 1, "created_at": 1},
    ).sort("created_at", -1).limit(20)
    updates = await cursor.to_list(length=20)

    # Enrich with project names
    proj_ids = list({u["project_id"] for u in updates})
    projs = await projects_collection.find(
        {"_id": {"$in": [__import__("bson").ObjectId(pid) for pid in proj_ids if pid]}},
        {"_id": 1, "name": 1},
    ).to_list(length=50)
    proj_map = {str(p["_id"]): p.get("name", "") for p in projs}

    result = []
    for u in updates:
        blockers = u.get("blockers", [])
        result.append({
            "project": proj_map.get(u["project_id"], u["project_id"]),
            "date": str(u.get("created_at", ""))[:10],
            "health": u.get("health", ""),
            "progress_pct": u.get("actual_progress", 0),
            "summary": u.get("ai_generated_summary") or u.get("accomplishments", ""),
            "blockers": blockers if isinstance(blockers, list) else [blockers],
            "submitted_by": u.get("updated_by", ""),
        })
    return result


# ─── Tool dispatcher ──────────────────────────────────────────────────────────

TOOL_MAP = {
    "list_projects": tool_list_projects,
    "get_project_status": tool_get_project_status,
    "get_team_capacity": tool_get_team_capacity,
    "get_recent_updates": tool_get_recent_updates,
}


async def _dispatch_tool(name: str, args: dict) -> Any:
    fn = TOOL_MAP.get(name)
    if not fn:
        raise ValueError(f"Unknown tool: {name}")
    return await fn(args)


# ─── MCP Discovery (no auth) ──────────────────────────────────────────────────

@router.get("/api/mcp")
async def mcp_server_info():
    """MCP server manifest — returns server capabilities and tool list for discovery."""
    return {
        "protocolVersion": "2025-03-26",
        "serverInfo": {
            "name": "DD Planner MCP Server",
            "version": "1.0.0",
            "description": "Exposes DD Planner project data, team capacity and status updates as MCP tools for AI agents.",
        },
        "capabilities": {
            "tools": {},
        },
        "tools": TOOLS,
    }


# ─── MCP JSON-RPC endpoint ────────────────────────────────────────────────────

@router.post("/api/mcp")
async def mcp_rpc(request: Request):
    """
    MCP JSON-RPC 2.0 endpoint.
    Accepts: initialize / tools/list / tools/call
    Auth: X-Agent-Key header
    """
    await _validate_agent_key(request)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
            status_code=400,
        )

    rpc_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    def ok(result):
        return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": result})

    def err(code: int, message: str):
        return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}})

    try:
        if method == "initialize":
            return ok({
                "protocolVersion": "2025-03-26",
                "serverInfo": {"name": "DD Planner MCP Server", "version": "1.0.0"},
                "capabilities": {"tools": {}},
            })

        elif method == "tools/list":
            return ok({"tools": TOOLS})

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            if not tool_name:
                return err(-32602, "Missing tool name")

            data = await _dispatch_tool(tool_name, tool_args)
            import json
            return ok({
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(data, indent=2, default=str),
                    }
                ],
                "isError": False,
            })

        else:
            return err(-32601, f"Method not found: {method}")

    except ValueError as e:
        return err(-32602, str(e))
    except Exception as e:
        logger.exception(f"[MCP] Unhandled error in {method}: {e}")
        return err(-32603, f"Internal error: {str(e)}")
