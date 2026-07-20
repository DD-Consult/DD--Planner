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
