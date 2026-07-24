# DD Planner - Product Requirements Document

## Overview
DD Planner is a full-stack resource planning and project management application for DD Consulting. It provides WBS generation, resource allocation, portfolio Gantt charts, AI-powered reports, and client portal access.

## Tech Stack
- **Frontend**: React, Tailwind CSS, Recharts, React Query, date-fns, shadcn/ui
- **Backend**: FastAPI, Python, Playwright (PDF/PPTX export)
- **Database**: MongoDB
- **AI**: OpenAI GPT-4o (via Emergent LLM Key)
- **DevOps**: Cloud Run, Nginx, Docker

## Completed Features (This Session)

### Bug Fixes
1. **Frontend Compilation Error (P0)** — Missing `</div>` in Risks tab JSX in `ProjectDetail.js`. The risk card JSX had 7 div opens but only 6 closes.
2. **Team Tab Runtime Crash (P1)** — `PhaseAllocationEditor.js` had `<SelectItem value="">` which crashes Radix UI. Changed to `value="default"`.

### Feature: Customer Details (Main Contact)
- Added 4 fields to project schema: `main_contact_name`, `main_contact_email`, `main_contact_phone`, `main_contact_role`
- Edit Project dialog has "Customer Contact (Optional)" section with 2x2 grid
- Project header displays contact info with clickable email/phone links
- Files: `schemas.py`, `projects.py`, `ProjectDetail.js`

### Feature: Milestones Gantt Polish
- Backend enriches project responses with milestones from WBS tasks
- PhaseVisualizer shows diamond markers for milestones
- PortfolioGantt shows milestone diamonds on timeline with tooltip
- WBS Board view shows milestones with purple cards, diamond icon, and MILESTONE badge
- Portfolio Gantt has legend showing Active, Pipeline, Milestone, Completed
- Files: `projects.py`, `reports.py`, `PortfolioGantt.js`, `WBSView.js`

### Feature: Business Days Only (Mon-Fri)
- Created `WeekdayDateInput` component that auto-snaps weekends to Monday
- Created `dateHelpers.js` utility with `snapToWeekday`, `businessDaysBetween`, `addBizDays`
- Replaced 16 date inputs across 6 files with WeekdayDateInput
- Updated effort calculations to use `differenceInBusinessDays`
- Backend `utils.py` has `count_business_days()` and `snap_to_weekday()` functions
- Files: `weekday-date-input.js`, `dateHelpers.js`, `ProjectDetail.js`, `Projects.js`, `AllocationEditor.js`, `WBSTaskDialog.js`, `Allocations.js`, `AIWBSGenerator.js`, `allocations.py`, `reports.py`, `utils.py`

### Feature: AI Smart Reschedule
- New `POST /api/ai/smart-reschedule/{project_id}` endpoint analyzes project schedule health
- AI examines progress, WBS tasks, milestones, allocations, blockers
- Returns recommendation with confidence score, key factors, risk warning
- Preview shows old→new dates and count of affected items
- Updated `reschedule_project` to also shift WBS tasks and snap dates to weekdays
- New `AIRescheduleDialog.js` component with metrics bar, analysis, preview, apply button
- "AI Reschedule" button added to project header in purple
- Files: `ai.py`, `projects.py`, `api.js`, `AIRescheduleDialog.js`, `ProjectDetail.js`

## Previously Completed Features
- WBS Budget Validation toast (api.js interceptor)
- Risks Module: Smart sorting, status badges with icons, AI deduplication
- WBS Milestones: Create milestones, complete/reopen, 0-hour tasks
- Client Portal Magic Link: Generate link, verify token, email notification, 30-day expiry

## Key API Endpoints
- `GET /api/projects/:id` — Returns project with milestones and WBS summary
- `GET /api/portfolio` — Returns portfolio with milestones per project
- `POST /api/reports/magic-link` — Generate client magic link
- `GET /api/portal/verify/:token` — Verify magic link token
- `PATCH /api/wbs/tasks/:id/complete-milestone` — Toggle milestone completion
- `GET /api/wbs/tasks/:id/comments` — List comments for a WBS task
- `POST /api/wbs/tasks/:id/comments` — Add comment to a WBS task
- `PUT /api/wbs/comments/:id` — Edit a comment (author only)
- `DELETE /api/wbs/comments/:id` — Delete a comment (author or admin)
- `GET /api/projects/:id/wbs/comments/counts` — Bulk comment counts for badge display
- `GET /api/dashboard/action-items` — Real-time action items for current user
- `POST /api/notifications/generate` — Manually trigger notification generation (admin only)

## New Features (This Session — Fork 2)

### Feature: WBS Task Comments
- New `wbs_comments` MongoDB collection for task-level discussion
- Full CRUD API (create, read, update, delete) with author-only edit/admin delete
- @mention support creates in-app notifications for mentioned users
- `WBSCommentSection` component integrated into WBSTaskDialog (edit mode only)
- Comment count badges (💬N) displayed on task cards in Board and List views
- Relative timestamps ("just now", "2 hours ago", "yesterday")
- Inline editing with Save/Cancel and "(edited)" indicator
- Files: `routes/comments.py`, `database.py`, `schemas.py`, `WBSCommentSection.js`, `WBSTaskDialog.js`, `WBSView.js`, `api.js`

### Feature: Dashboard Action Items & Alerts
- New `GET /api/dashboard/action-items` computes real-time pending actions per user
- Role-based: Resources see missing timesheets, Admins additionally see budget alerts, overdue milestones, status update reminders
- Action types: missing_timesheet, draft_timesheet, status_update_due, budget_alert_critical, budget_alert_warning, allocation_ending, overdue_milestone
- Severity levels: high (red), medium (amber), low (blue)
- Dashboard banner with expand/collapse, severity badges, "Go →" navigation links
- Dismissible per session, auto-refreshes every 5 minutes
- `POST /api/notifications/generate` endpoint for admin-triggered bulk notification creation
- Files: `routes/action_items.py`, `Dashboard.js`, `api.js`
## Recent Enhancements (Deep Review Session)

### Bug Fix: Calculation Consistency (Critical)
- **Fixed backend `budget_reconciliation.py`**: `_allocated_hours_for_range()` was using CALENDAR days (including weekends). Now uses business days × 8h/day.
- **Fixed backend `projects.py`**: `compute_allocation_hours()` was using 38h/week (7.6h/day). Now uses business_days × 8h/day.
- **Standard formula everywhere**: `allocated_hours = (percentage / 100) × business_days × 8`
- Files: `services/budget_reconciliation.py`, `routes/projects.py`

### Feature: Add Status Update from Project Detail
- New "Add Status Update" button on the project detail Overview tab (next to "Recent Status Updates")
- Full dialog with: Health, Schedule Status, Progress %, Accomplishments, Blockers, Next Steps, Notes
- No Thursday/Friday time restriction (available anytime from project detail page)
- Auto-refreshes status updates list after submission
- Files: `ProjectDetail.js`

### UX Fix: Decoupled Phase Editing from Project Header
- Settings tab "Edit Phases" now opens a LOCAL inline editor (doesn't affect the project header)
- Separate state: `isEditingPhases` / `editedPhases` (independent from `isEditingProject`)
- Save only updates phases without touching other project fields
- Header "Edit Project" button still works as before for full project editing
- Files: `ProjectDetail.js`

### Feature: Full Allocation Management from Project Detail
- **Allocate Resource button** on Team tab — opens dialog to assign resources directly from the project page
- **Edit/Delete buttons** on each allocation row in the Team table (admin-only)
- **Allocation dialog** with: resource selector, auto-filled dates, percentage slider, role input
- **Budget enforcement**: Real-time budget impact calculation showing budgeted vs allocated vs new hours
  - RED warning + disabled submit when allocation would exceed project budget
  - Accounts for existing allocation when editing (subtracts old hours before comparing)
  - Uses business days × 8h formula consistently
- **Delete confirmation** using AlertDialog with proper warning text
- Files: `ProjectDetail.js`

## Credentials
- Demo Admin: admin@test.com / admin123
- Super Admin: don@ddconsult.tech / Welcome123!

### Feature: AI Learning & Guidance System
- **AI Custom Instructions**: Per-project and global instructions that get auto-injected into all AI prompts
  - New `ai_instructions` collection with scope (global/project), category, instructions text, active/inactive toggle
  - Categories: all, risk_polish, status_summary, wbs_generation, reschedule, chat
  - CRUD API: `GET/POST/PUT/DELETE /api/ai/instructions`
  - Instructions injected into: risk polishing, AI chat, smart reschedule, budget analysis, WBS generation
  - `AIInstructionsPanel` component in Project Settings tab with card-based UI, inline editing, active toggle
- **AI Feedback Loop**: Thumbs up/down on AI outputs stored for future prompt refinement
  - New `ai_feedback` collection tracking feature, rating, input/output summaries, user comments
  - `POST /api/ai/feedback` endpoint + `GET /api/ai/feedback/stats` for analytics
  - `AIFeedbackButtons` component integrated after status summaries and AI reschedule analysis
- **Service Layer**: `services/ai_instructions.py` helper fetches applicable instructions and formats them for prompt injection
- Files: `services/ai_instructions.py`, `routes/ai_instructions.py`, `AIInstructionsPanel.js`, `AIFeedbackButtons.js`, `risk_ai.py`, `ai.py`, `wbs.py`, `projects.py`, `ProjectDetail.js`, `AIRescheduleDialog.js`

## Session: Timing/Budget Consistency Overhaul (June 2026)

### User Decisions
- Standard work week: **40 hours** (8h/day, Mon-Fri) app-wide
- Budget hierarchy source of truth: **project-level budget**; phases/WBS roll up to it
- Auto-fill keeps defaulting actual_hours = planned_hours

### Canonical Calculation Layer (`backend/utils.py`)
- `HOURS_PER_WEEK=40`, `coerce_date`, `allocation_weekly_hours` (hours-type = TOTAL over range),
  `compute_allocation_hours(alloc, clip_start, clip_end)`, `compute_phase_allocated_hours(alloc, phase)`
  (per-phase % wins → phase_names filter → clipped to phase dates), `leaf_estimated_hours`,
  `wbs_parent_id_set` / `is_leaf_task` (handles dual identity: Mongo _id vs internal uuid id)

### Fixed Inconsistencies
1. 38h vs 40h week mix (validate_allocation, my-allocations, portfolio baseline, phase-allocations) → all 40h
2. hours-type allocation semantics (total vs weekly conflict) → TOTAL over range everywhere
3. Phase allocated attribution: 3 conflicting methods → one canonical (no double counting; phase sums = project total)
4. WBS estimates: leaf-only sums in budget-status, project wbs_summary, reconciliation (was double counting parents)
5. Auto-fill: phase-overlap filter, per-phase %, holiday+leave deduction, split only when no per-phase %
6. insights.py dead queries (status:'approved', $hours field, 'Done' casing) → real actuals now flow into predictions/health
7. ProjectDetail.js Total Effort: calendar days → business days
8. time-tracking summary week boundary: UTC → Sydney tz
9. create_allocation %-from-hours: int() → round()

### Testing
- 14/14 backend tests pass: `backend/tests/test_iteration19_consistency.py` (report: test_reports/iteration_19.json)
- Note: admin@test.com promoted to super_admin in local DB for testing

### Backlog / P2
- Rename `wbs_summary.completion_percentage` (it's hours-burn, not completion) — unused in UI currently
- Consider making HOURS_PER_WEEK a configurable org setting
- Capacity report endpoint is /api/reports/capacity (docs naming)

## Session: AI Agent Review, Conversational Tone & Non-Admin Lockdown (June 2026)

### AI Action Inventory (reviewed)
- 46 actions total: 17 legacy (`services/ai_actions.py`) + 29 registry (`services/ai_actions_extended.py`, tiers 1-3)
- Safety layers: admin permission, confirm tokens for destructive ops (10-min TTL), audit log, single-level undo, hallucination guard

### Changes Implemented
1. **Conversational persona** in chat system prompt (routes/ai.py): colleague-on-Slack tone, prose-first, numbers woven into sentences, bullets only for 3+ comparisons, natural action confirmations ("✅ Done — ...")
2. **SECURITY FIX (critical)**: dispatch_action permission check moved BEFORE legacy fallback — previously ANY authenticated user (resource/client) could execute all 17 legacy actions (add_risk, remove_allocation, delete_wbs_task, create_project...) via chat or /api/ai/chat/execute-action
3. **Role-scoped chat data**: resource/contractor → only allocated/lead projects + own timesheets; client → only allowed_project_ids, no timesheets, no allocation percentages (team names OK); users-list & change-log context blocks admin-only; leaves → own only for non-admins
4. **Read-only mode** for non-admins: no action docs in prompt, conversational refusal + drafts the change request for an admin; action blocks stripped as defense-in-depth
5. Fixed `create_leave` AI handler storing `reason` → now stores `type`/`notes` (matches Leave schema/UI)

### Testing
- 12/12 pass: backend/tests/test_iteration20_ai_security.py (report: test_reports/iteration_20.json)
- Reusable regression suites: test_iteration19_consistency.py (budget math), test_iteration20_ai_security.py (AI permissions)

### Known review findings NOT yet fixed (user to decide)
- Legacy `remove_allocation` / `delete_wbs_task` auto-execute for admins with no confirm token (registry deletes require one)
- `manage_phases` replaces whole phases array — partial list from AI could drop phases silently
- routes/ai.py is 1800+ lines — candidate for splitting

## Session: Project Lead Permissions (June 2026)

### User Decisions
- Leads get FULL project editing on projects they lead: details/dates/budget/phases + risks + status updates
- Applies to both REST API/UI and AI chat; AI actions strictly limited to led projects

### Implemented
- `utils.user_leads_project(user, project_id)` — admin OR linked resource == project_lead_id
- REST now lead-or-admin: PUT /api/projects/{id}, POST /api/projects/{id}/reschedule, PUT /api/status-updates/{id}; lead fallback added to risks create/update/delete and status update create (previously allocation-only)
- AI: LEAD_ALLOWED_ACTIONS whitelist in ai_action_registry (update_project, manage_phases, reschedule_project, sync_phase_to_wbs, update_project_dates/status, add/update/delete_risk, polish_all_risks, create_status_update) enforced per-project via _resolve_action_project_id (risk_id→project lookup)
- Chat PROJECT LEAD MODE prompt section (led project IDs + action docs); auto-execute enabled for leads (can_act)
- Frontend: edit-status-update button visible to leads (isLead in ProjectDetail.js)
- BUG FIX (pre-existing): reschedule endpoint 500 — snap_to_weekday returns date, BSON needs datetime (allocation date writes)

### Testing
- 12/12 pass: backend/tests/test_iteration21_lead_permissions.py; iteration 19+20 suites re-run green (20's escalation test updated: riley is now legitimately lead of Website Redesign, so it targets Mobile App)

## Session: Resource/User Delete & Deactivate Lifecycle (June 2026)

### User Decisions
- Hard delete blocked when resource has history (allocations/timesheets/lead refs) → 409, deactivate instead
- Deactivation auto-ends allocations: future ones deleted, running ones end today
- Deactivating a resource auto-disables linked user login(s); reactivate re-enables

### Implemented
- Resources: POST /{id}/deactivate, /{id}/reactivate; guarded DELETE (409 with history counts); `active` flag on Resource schema
- Users: PUT /api/admin/users/{id}/status?disabled=, DELETE /api/admin/users/{id}; guards (no self-target; only super_admin touches admin accounts)
- `disabled` flag now ENFORCED at login (403) and get_current_user (kills existing JWT sessions) — integration_expert playbook consulted
- Inactive resources excluded from: capacity report, timesheet/allocation reminders, new allocation creation (400)
- AI actions: deactivate_resource/reactivate_resource added; delete_resource guarded same as REST (incl. project_lead check after test-agent bug find)
- Fixed AI create_leave field mismatch earlier; utils: deactivate_resource_core/reactivate_resource_core shared by REST + AI
- Frontend: Resources page Status column + Deactivate/Reactivate buttons + 409 toast; Users page Disable/Enable + Delete buttons + Disabled badge

### Testing
- 13/13 pass: backend/tests/test_iteration22_lifecycle.py; 38/38 regression (iters 19-21); frontend UI verified by testing agent

## Session: Hide Deactivated Resources Everywhere (June 2026)
- Deactivated resources now hidden from: ALL pickers/dropdowns (17 sites: allocations dialogs, project wizard, lead pickers, WBS assignee, leaves, timesheet filters), Allocations timeline rows, Dashboard roles, and report endpoints (planned-vs-actual breakdown, time-tracking summary, resource-utilization, capacity) + AI chat/suggestion contexts
- Resources page intentionally still shows them (Inactive badge) for management; historical name lookups unaffected (GET /api/resources returns all, filtering per-consumer)
- Testing agent found 2 leaked pickers (Allocations dialog, ProjectWizard alloc step) — fixed & UI-verified; 51/51 regression green
- Data fix: restored Riley as Website Redesign lead; purged leaked TEST_ resources from earlier test runs


## Session: Destructive Action Guards & manage_phases Fix (Feb 2026)
- `remove_allocation` and `delete_wbs_task` now require confirmation tokens (registered with `is_destructive=True`)
- `manage_phases` defaults to merge mode — only supplied phases change; others preserved. `mode='replace'` for full replace.
- 74/74 regression tests green (iter 24)

## Session: AI Agent — Agentic Features (Feb 2026)
- **Multi-Step Batch Plans**: `action_plan` AI format + `POST /api/ai/chat/execute-plan` + PlanCard frontend
- **Proactive Health Monitor**: `services/health_monitor.py` + daily background task + `POST /api/ai/health-monitor/run` + `GET /api/ai/health-monitor/report`
- **Specialist Sub-Agents**: @resource / @budget / @risk / @schedule routing via `services/specialist_agents.py`
- **Agent Memory**: `ai_memory` collection + full CRUD `/api/ai/memory` + `save_memory` AI action + `AIMemoryPanel.js` in project settings + auto-injection into chat prompts
- New MongoDB collections: `ai_memory`, `ai_health_reports`

## Session: Resource/Staff View Audit & Fixes (Feb 2026)

### Issues Found & Fixed
1. **Allocations scoped**: `GET /api/allocations` now filters to own `resource_id` for non-admin users. `/allocations` route restricted to `admin`/`super_admin` only. `My Allocations` nav item now resource-only (removed from admin nav to avoid duplication).
2. **Leaves scoped**: `GET /api/leaves` filters by own resource for non-admin. `POST /api/leaves` — resources can create their own leave (no `resource_id` required; auto-filled by backend). `DELETE` — resources can only delete their own entries (403 otherwise). Admins still have full control.
3. **My Timesheets page**: New `GET /api/timesheets/history` returns own timesheet entries grouped by week. New `/my-timesheets` route + `MyTimesheets.js` with: read-only history view, autofill current week, submit button, amber warning banner "Timesheet history is read-only. To make corrections, please contact your admin.", "Load older weeks" pagination.
4. **Leaves.js** rewritten to be role-aware: admin sees full team list + Resource column; resource sees only own entries + hides Resource column.
5. **AddLeaveDialog**: Added `preselectedResourceId` prop — when set (resource users), hides resource picker and auto-fills from linked resource.
6. **LeaveCreate schema**: `resource_id` changed to `Optional[str]` (backend auto-fills for resource users).
- 21/21 new tests green (iter 26), 113/113 total regression green

- 39/39 tests green (iter 25), 74/74 total regression

## Session: Integration Layer — HubSpot + MCP Server (Jul 2026)

### Features Built

**1. HubSpot Bi-directional CRM Integration**
- **Inbound** (HubSpot → DD Planner): `POST /api/integrations/hubspot/webhook` receives deal stage change events. When stage = configured trigger (default: closedwon) → auto-creates project with field mapping: dealname→name, amount→budget_value, closedate→end_date, company→client_name, contact→main_contact
- **Outbound** (DD Planner → HubSpot): When a status update is submitted, pushes a formatted engagement note to the linked HubSpot deal (fire-and-forget, non-fatal if HubSpot is unavailable)
- `services/hubspot.py` — API client: get_deal, get_deal_company_name, get_deal_primary_contact, map_deal_to_project, push_status_update_to_hubspot, test_hubspot_connection, append_sync_log

**2. Integrations Settings UI (super_admin only)**
- New section at bottom of Settings page — `components/IntegrationsSettings.js`
- HubSpot card: enable toggle, Private App Token (masked, show/hide), Portal ID, trigger stage, default project status, sync updates toggle, "Test Connection" button with live result, webhook URL (copyable)
- Agent API card: enable toggle, MCP endpoint URL (copyable), generate/rotate API key with amber "save now" warning
- More Integrations: Salesforce, Pipedrive, Monday.com, Slack (coming soon)
- Sync Log: collapsible last-30-events audit log

**3. MCP Server (AI Agent API)**
- `GET /api/mcp` — server manifest/discovery (no auth — allows Gemini/Copilot to discover)
- `POST /api/mcp` — JSON-RPC 2.0 endpoint (X-Agent-Key auth required)
- Supports: `initialize`, `tools/list`, `tools/call`
- Tools: `list_projects`, `get_project_status`, `get_team_capacity`, `get_recent_updates`
- Any MCP-compatible AI (Gemini Studio, Copilot Studio, VS Code Copilot) can register `POST /api/mcp` + API key

**4. Integration Settings Storage**
- `integration_settings` MongoDB collection (org_id='default') — multi-tenant ready
- `integration_sync_logs` MongoDB collection — audit log for all inbound/outbound events
- API: GET/PUT `/api/integrations/settings`, `/api/integrations/agent-api/regenerate`, `/api/integrations/sync-logs`

**Bug Fix:** `RESEND_API_KEY` import missing in admin.py → caused 500 on `/api/reminders/status` → fixed

- Testing: 36/36 pass (iter 29)
- Files: `services/hubspot.py`, `routes/integrations.py`, `routes/mcp_server.py`, `components/IntegrationsSettings.js`, `pages/Settings.js`, `database.py`, `server.py`, `routes/projects.py`, `api.js`

## Session: Personalised Resource Dashboard (Jul 2026)

### Feature: ResourceDashboard for resource/contractor users
- **Trigger**: `Dashboard.js` detects `role === 'resource' || 'contractor'` and renders `<ResourceDashboard>` instead of the admin Command Center (conditional return after all hooks, no Rules of Hooks violation)
- **Personalised greeting**: "Good morning/afternoon/evening, [First Name]" with role + date subtitle
- **Action Items Banner**: same as admin — shows high/medium/low items with expand/dismiss; auto-refreshes every 5 min
- **Timesheet Nudge**: standalone banner if action items dismissed and timesheet is missing
- **4 KPI Cards**: My Utilization This Week (%), My Hours This Week (h), Active Projects (count), Timesheet Status (Not Submitted / Draft / Up to Date badge)
- **My Allocations**: current + upcoming allocations with project name, client, role, %, h/wk, dates, status badge; "View all" → /my-allocations
- **Recent Timesheets**: last 4 weeks with status badges + hours logged; empty state CTA → /my-timesheets
- **My Leaves**: upcoming leaves with status badges; empty state CTA → /time-off
- Data sources: `GET /api/my-allocations?period=month`, `GET /api/timesheets/history?weeks=4`, `GET /api/leaves`, `GET /api/dashboard/action-items`
- Files: `ResourceDashboard.js` (new), `Dashboard.js` (early return added)
- Testing: 23/23 tests pass (iter 28)

## Session: Resource Flow E2E Test + Allocation Hours Bug Fix (Jul 2026)

### Bug Fixed: Allocation Hours Inconsistency
- **Root cause**: `formatAllocation(percentage, standard_capacity)` in `capacityHelpers.js` multiplied allocation % by `standard_capacity` — e.g. 50% on an 80%-capacity resource showed "16h" in "Allocation" column but "20h" in "Hours/Week" column.
- **Backend was always correct**: `allocation_weekly_hours()` in `utils.py` uses `(percentage/100) * 40` ignoring `standard_capacity`.
- **Fix**: `formatAllocation` now uses 40h base always. `MyAllocations.js` "Allocation" column shows `X% · Y.0h/wk` using backend pre-calculated `alloc.weekly_hours`.
- 29/29 E2E tests green (iter 27), 163/163 total regression



## Session: Comprehensive Documentation (Feb 2026)

### Created Documentation
1. **README.md** (542 lines) — Complete project overview with architecture diagram, tech stack, setup instructions, environment variables, RBAC matrix, core modules, AI capabilities, integrations overview, full API reference, and project structure
2. **GUIDE.md** (486 lines) — Step-by-step user guide covering all 17 feature areas with role-specific workflows for Super Admin, Admin, Resource, Contractor, and Client
3. **INTEGRATIONS.md** (392 lines) — Detailed setup instructions for HubSpot CRM (Private App creation, webhook config, field mapping), MCP Server (API key generation, example JSON-RPC requests, Gemini/Copilot connection), and Resend email. Includes troubleshooting tables and security notes.

### In-App Help & Guide Page
- New `/help` route accessible to ALL roles (sidebar nav item "Help & Guide")
- Role-aware content: Super Admin sees all 12 sections (incl. Integrations), Resource sees 9 sections (no admin-only content), Client sees 2 sections (Getting Started + Tips)
- Features: search/filter, quick-nav cards, collapsible accordion FAQ, rich text rendering with bullet points and numbered lists
- Files: `pages/Help.js` (new), `App.js` (route added), `Layout.js` (nav item added)
- Testing: 9/9 frontend tests pass (iter 30)

### Pending Tasks (Backlog)

## Bug Fix: Capacity Calculation for Part-Time Resources (Feb 2026)

### Root Cause
`capacity_used_percentage` was the raw sum of allocation percentages (e.g. 145%) compared against `standard_capacity` (e.g. 30%). The over-capacity message said "145% of standard capacity (30%)" which was mathematically incorrect and misleading — the resource was actually at 483% of their capacity.

### Fix
- Backend (`routes/allocations.py`): `capacity_used_percentage` now calculated relative to `standard_capacity`: `(raw_sum / std_cap) * 100`. New fields added: `raw_allocation_pct`, `available_hours_per_week`.
- Frontend (`MyAllocations.js`): Shows "of X% capacity" subtitle for part-time resources. Over-capacity banner shows "Allocated: Xh/wk — Available: Yh/wk (Z% capacity)".
- Frontend (`ResourceDashboard.js`): Utilization KPI now relative to standard capacity. Hours sub-text shows dynamic available hours instead of hardcoded "40h/week".
- For 100% capacity resources, behavior is unchanged.
- Testing: 11/11 backend + 8/8 frontend tests pass (iter 31). Verified 30%, 50%, 0%, and 100% capacity scenarios.

## Bug Fix: Allocation Hours Now Respect Standard Capacity (Feb 2026)

### Root Cause
`allocation_weekly_hours()` always used `(percentage/100) * 40h` regardless of the resource's `standard_capacity`. A 50% capacity (part-time) resource allocated at 100% showed 40h/wk instead of 20h/wk.

### Fix
- `allocation_weekly_hours(alloc, standard_capacity)` now computes: `(percentage/100) × (std_cap/100) × 40h`
- Updated all callers: my-allocations, compute_allocation_hours, compute_phase_allocated_hours
- For 100% capacity resources: unchanged (100% alloc = 40h/wk)
- For 50% capacity: 100% alloc = 20h/wk, 50% alloc = 10h/wk
- For 30% capacity: 100% alloc = 12h/wk

### Feature: Total Hours Allocation Mode
- Allocation dialogs (Allocations page + ProjectDetail Team tab) now have a **Percentage / Total Hours** toggle
- In "Total Hours" mode, user enters the total hours for the period (e.g. 40h over 2 weeks)
- Backend computes the equivalent percentage relative to the resource's capacity and business days
- ProjectDetail dialog shows live h/wk calculation with capacity context (e.g. "50% = 10.0h/wk (resource at 50% capacity)")
- Testing: 7/7 backend + 8/8 frontend tests pass (iter 32)



### Follow-up Fix: Allocations Page Capacity Display (Feb 2026)
- `capacityHelpers.js` — `formatAllocation(pct, stdCap)` now computes h/wk as `(pct/100) × (stdCap/100) × 40`
- Allocations page resource group header "X% of capacity" now uses `getCapacityPct()` which divides raw alloc sum by standard_capacity
- `groupedByResource` useMemo enriched with `standard_capacity` from resources list
- Summary stats (Available/At Capacity/Over) use capacity-relative values
- Timeline heatmap cells use capacity-relative percentages
- ProjectDetail `calculateAllocationEffort` respects standard_capacity for Est. Hours column
- Testing: 5/8 UI tests pass in iter 33 → root cause found (missing standard_capacity in groupedByResource) → fixed

- P1: Refactor `<ResourceSelect>` reusable component
- P1: Timesheet reminder / dashboard nudge for missing timesheets
- P2: "Show inactive" toggle on Resources page
- P2: Offboarding summary dialog when deactivating a resource
- P2: "Lead" badge on project header + lead dashboard widget
- P2: Read-only badge in AI Chat panel for non-admins
