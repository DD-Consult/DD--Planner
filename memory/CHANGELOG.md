# DD Planner — Changelog

## Session: Destructive Action Guards & manage_phases Fix (Feb 2026)

### Issue 1 Fixed: Destructive AI Actions Now Require Confirmation
- `remove_allocation` and `delete_wbs_task` registered in the new action registry with `is_destructive=True`
- Non-super-admin users now receive a confirmation token prompt before these actions execute
- Super admins bypass confirmation (by design)
- System prompt updated to mark both actions as `[destructive]`
- 74/74 regression tests green (iter 24)

### Issue 2 Fixed: manage_phases Merge Mode (Default)
- `manage_phases` now defaults to `mode='merge'`: only supplied phases are updated/added; existing phases not in the payload are preserved
- Pass `mode='replace'` for full-replace (old behavior)
- Prevents accidental phase data loss from partial AI-generated phase lists
- System prompt updated: lead section now documents merge-by-default behavior

---

## Session: AI Agent — Agentic & Multi-Agent Features (Feb 2026)

### Feature a: Multi-Step Batch Plans
- AI can emit `action_plan` blocks with an ordered steps array
- Chat endpoint detects `action_plan` and does NOT auto-execute — holds for user review
- `PlanCard` component in ChatPanel.js shows numbered steps with description and "Execute All" button
- `POST /api/ai/chat/execute-plan` executes steps sequentially via full dispatch_action flow
- Per-step results shown inline; partial success handled gracefully
- Admin-only endpoint (non-admins get 403)

### Feature b: Proactive Project Health Monitor
- `services/health_monitor.py` analyzes: budget overruns (>80%, 100%+), over-allocated resources, stale status updates (14/21 day thresholds), overdue milestones, unmitigated high/critical risks
- `POST /api/ai/health-monitor/run` — admin-only, returns structured findings with overall_health, summary, findings array
- `GET /api/ai/health-monitor/report` — returns most recently saved report
- Critical findings automatically create in-app notifications for admin users
- Background daily task scheduled at server startup (runs every 24h after 1h warm-up)
- `run_health_check` AI action triggers analysis from chat
- New `ai_health_reports` MongoDB collection

### Feature d: Specialist Sub-Agents
- @resource, @budget, @risk, @schedule triggers detected in chat messages
- Each activates a focused specialist system prompt header prepended to the main prompt
- Resource: capacity/allocation focus | Budget: burn rate/financial | Risk: risk prioritization | Schedule: timeline adherence
- No new infrastructure needed — routes through existing dispatch system
- `services/specialist_agents.py` with trigger patterns and specialist headers

### Feature f: Agent Memory per Project
- New `ai_memory` MongoDB collection: scope (project/global), title, content, category (decision/preference/context/note)
- Full CRUD API: `GET/POST/PUT/DELETE /api/ai/memory`
- `GET /api/ai/memory/project/{project_id}` returns project + global memories
- `save_memory` AI action saves decisions/context from chat to memory
- Memories auto-injected into chat system prompts (global + project-specific)
- `AIMemoryPanel.js` component added to Project Settings tab
- 39/39 tests green (iter 25)
