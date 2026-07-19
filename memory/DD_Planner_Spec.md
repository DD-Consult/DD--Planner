# DD Planner — Business Requirements, Functional & Technical Specification

**Document Version:** 1.0  
**Date:** March 2026  
**Author:** DD Consult Engineering  
**Status:** Current State Documentation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Business Requirements](#2-business-requirements)
3. [User Roles & Personas](#3-user-roles--personas)
4. [Functional Specification](#4-functional-specification)
5. [Technical Specification](#5-technical-specification)
6. [Data Model](#6-data-model)
7. [API Reference](#7-api-reference)
8. [Security & Access Control](#8-security--access-control)
9. [AI Integration](#9-ai-integration)
10. [Business Rules & Constraints](#10-business-rules--constraints)
11. [Non-Functional Requirements](#11-non-functional-requirements)
12. [Known Limitations & Technical Debt](#12-known-limitations--technical-debt)
13. [Future Roadmap](#13-future-roadmap)

---

## 1. Executive Summary

DD Planner is a full-stack resource planning and capacity management application built for DD Consult. It enables the firm to manage projects, allocate staff across engagements, track time (planned vs. actual), submit weekly status check-ins, and leverage AI-powered analytics for budget oversight and natural-language project management.

### Business Goals

- **Centralise** project and resource data into a single platform, replacing spreadsheets.
- **Improve visibility** into staff utilisation, project health, and budget burn rates.
- **Reduce admin overhead** via AI-assisted project management (natural language commands, auto-generated summaries, budget analysis).
- **Enforce governance** with role-based access, time-bounded timesheet windows, and audit-friendly status updates.

---

## 2. Business Requirements

### BR-01: Project Management
The system must allow administrators to create, edit, and track projects with defined phases, timelines, budgets, and risk registers.

### BR-02: Resource Management
The system must maintain a registry of staff (resources) with their roles, capacity, and availability.

### BR-03: Resource Allocation
Administrators must be able to assign resources to projects for defined periods at specified capacity percentages, with role assignments per engagement.

### BR-04: Time Tracking
Staff must be able to log planned and actual hours per project/phase each week. The system must calculate variance and support draft/submit workflows.

### BR-05: Timesheet Governance
Time entry must be restricted to a defined window each week (currently Thursday 00:00 to Monday 12:00 PM, Sydney time) to enforce weekly cadence.

### BR-06: Project Status Check-ins
Project leads and resources must be able to submit weekly status updates including health (RAG), schedule status, progress percentage, accomplishments, blockers, and next steps.

### BR-07: Budget Tracking
Each project and phase may have budgeted hours. The system must aggregate actual hours against budgets and provide variance reporting.

### BR-08: Reporting
Stakeholders need a cross-project "Planned vs. Actuals" dashboard showing budget health, variance, and risk indicators across the entire portfolio.

### BR-09: AI-Powered Insights
The system must provide AI-generated analysis including budget burn assessment, portfolio-level insights, and natural language command interpretation for project management tasks.

### BR-10: Role-Based Access Control
Different user types (Super Admin, Admin, Resource, Client) must have appropriately scoped access to data and functionality.

### BR-11: Leave & Holiday Management
The system must track staff leave (vacation, sick) and company-wide holidays for capacity planning purposes.

### BR-12: Data Integrity
Administrators must have tools to identify and clean up orphaned data (e.g., allocations referencing deleted projects or resources).

---

## 3. User Roles & Personas

| Role | Description | Access Level |
|------|-------------|-------------|
| **Super Admin** | System owner (e.g., firm principal). Full access to all features including AI settings, user management, all timesheets, data cleanup, and reporting. | Full |
| **Admin** | Office/project managers. Can manage projects, resources, allocations, users, leaves, holidays. Cannot configure AI settings. | High |
| **Resource** | Consultants/staff members. Can view their assigned projects, log timesheets, submit status check-ins, view allocations. | Standard |
| **Client** | External stakeholders. View-only access to their assigned projects via a portal. | Read-only |

### Permission Matrix

| Feature | Super Admin | Admin | Resource | Client |
|---------|:-----------:|:-----:|:--------:|:------:|
| Dashboard | Y | Y | Y | - |
| Projects (CRUD) | Y | Y | View | View (own) |
| Resources (CRUD) | Y | Y | - | - |
| Allocations | Y | Y | View | - |
| Timesheets (own) | Y | Y | Y | - |
| Timesheets (all) | Y | - | - | - |
| Status Check-ins | Y | Y | Y (own projects) | - |
| Reports | Y | Y | - | - |
| Users Management | Y | Y | - | - |
| AI Settings | Y | - | - | - |
| Data Cleanup | Y | Y | - | - |
| Settings Page | Y | - | - | - |
| Leaves / Holidays | Y | Y | View | - |
| Client Portal | - | - | - | Y |

---

## 4. Functional Specification

### 4.1 Authentication & User Management

**F-AUTH-01: Login**
- OAuth2 password-based authentication (email + password).
- Returns JWT token (24-hour expiry).
- On first login, users with `must_change_password` flag are directed to change their password.

**F-AUTH-02: Password Management**
- Users can change their own password (old + new password required).
- Super admins can reset any user's password to `Welcome123!` and set the `must_change_password` flag.

**F-AUTH-03: User Account Creation**
- Admins create resource user accounts linked to a resource record via `resource_id`.
- User record stores: email, hashed password, role, resource_id, must_change_password, allowed_project_ids.

**F-AUTH-04: Avatar**
- Users can set a profile avatar via URL (including DiceBear generated avatars).

---

### 4.2 Project Management

**F-PROJ-01: Project CRUD**
- Create projects with: name, client name, status (Active/Pipeline/Completed), start date, end date, phases, budgeted hours.
- Each phase has: name, start date, end date, status, and optional budgeted hours.
- All phases are assigned a UUID on creation (auto-generated if missing).
- Projects can be flagged as drafts (`is_draft`).

**F-PROJ-02: Project Wizard**
- 5-step guided creation: Charter > Phases > Resources > Risks > Review.
- Creates project, allocations, and risks in a single transaction.

**F-PROJ-03: Project Detail View**
- Tabs: Overview, Phases, Time Tracking, Status Updates, Risks, AI Analysis.
- Time Tracking tab shows budgeted vs. actual hours breakdown by phase.
- AI Budget Analysis section auto-loads on the Time Tracking tab.

**F-PROJ-04: Project Summary Generation**
- AI-generated executive summaries based on the latest status update data.
- Summaries can also be manually edited.

**F-PROJ-05: Project Rescheduling**
- Shift all project and phase dates forward or backward by a specified number of weeks.

---

### 4.3 Resource Management

**F-RES-01: Resource CRUD**
- Create/update/delete resources with: name, role, standard capacity (default 100%).
- Super admin only for create/delete.

**F-RES-02: User-Resource Linking**
- Each user account can be linked to a resource record via `resource_id` (set at user creation).
- Fallback matching: exact email match on resource, then normalised name matching from email prefix (handles dot-separated emails like `first.last@domain`).

---

### 4.4 Resource Allocation

**F-ALLOC-01: Allocation CRUD**
- Assign a resource to a project for a date range at a percentage (or hours).
- Each allocation can specify a project role (from predefined list) and phase assignments.
- Supports confirmation workflow: Pending > Confirmed.

**F-ALLOC-02: Allocation Confirmation**
- Resources can confirm their own allocations with actual percentage during the timesheet window.
- Admins can confirm any allocation.

**F-ALLOC-03: Grouped View**
- Allocations page displays assignments grouped by staff member with collapsible sections, search, and utilisation badges.

**F-ALLOC-04: Move Resource**
- Transfer a resource between projects (close source allocation, create target allocation).

---

### 4.5 Time Tracking (Timesheets)

**F-TS-01: Timesheet Entry**
- Resources log planned and actual hours per project/phase per week.
- System calculates variance (actual - planned) and variance percentage.
- Status workflow: Draft > Submitted.

**F-TS-02: Auto-Fill**
- System can auto-generate timesheet entries for a week based on current allocations.
- Calculates planned hours from allocation percentage (100% = 40 hrs/week, pro-rated for partial weeks).

**F-TS-03: Super Admin Timesheet Management**
- Super admins can view and edit all users' timesheets via a dedicated "Manage Timesheets" page.

**F-TS-04: Timesheet Window**
- Time entry and submission restricted to: **Thursday 00:00 to Monday 12:00 PM (Sydney/AEDT time)**.
- Outside this window, the UI shows the next allowed day.
- Super admins may be exempt for management tasks.

**F-TS-05: Week Submission**
- Submit all draft timesheets for a week in bulk (changes status to "Submitted").

---

### 4.6 Project Status Check-ins

**F-STATUS-01: Weekly Check-in**
- Resources/leads submit per-project updates with:
  - Health: Green / Amber / Red
  - Schedule Status: On Track / Delayed / Ahead of Schedule / At Risk
  - Actual Progress: 0-100%
  - Accomplishments, Blockers, Next Steps, Notes (free text)
- AI auto-generates an executive summary for each check-in.

**F-STATUS-02: History**
- View historical status updates per project (latest 10 by default).
- Latest update's health/schedule/progress is surfaced on the project card.

**F-STATUS-03: My Projects**
- Resources see only projects they are allocated to (or all active projects for admins).

---

### 4.7 Reporting

**F-RPT-01: Planned vs. Actuals Dashboard**
- Portfolio-level summary cards: Total Budget, Total Actual, Variance, At Risk count.
- Project comparison table with columns: Project, Budget, Actual, Variance, % Used, Health.
- Search by project/client name, filter by health status, sortable columns.
- Clicking a row navigates to the project detail page.

**F-RPT-02: AI Portfolio Insights**
- AI-generated narrative summary of portfolio budget health.
- Alerts (critical/warning/info) for over-budget or at-risk projects.
- Recommendations with priority levels.
- Project highlights with status indicators.

**F-RPT-03: Capacity Report**
- Resource utilisation over a date range showing allocation percentages.

**F-RPT-04: Per-Project Time Report**
- Planned vs. actual hours breakdown by phase for a single project.

---

### 4.8 Leave & Holiday Management

**F-LEAVE-01: Leave Tracking**
- Admins create leave entries: resource, date range, type (Vacation/Sick/Public Holiday), notes.

**F-LEAVE-02: Holidays**
- Admins manage company-wide holidays: name, date, description.
- Holidays can be deleted.

---

### 4.9 AI Command Bar

**F-AI-01: Natural Language Commands**
- Users press Ctrl+K (Cmd+K on Mac) to open the AI command bar.
- Type natural language commands like "Assign Alice to Mobile App at 60%".
- AI parses intent and entities, shows confirmation dialog before execution.

**F-AI-02: Supported Intents**
- `CREATE_ALLOCATION` — Assign resource to project
- `CHECK_AVAILABILITY` — Check resource availability
- `PROJECT_STATUS_UPDATE` — Update project health/progress
- `ADD_RISK` — Add risk to project
- `MOVE_RESOURCE` — Transfer between projects
- `RESCHEDULE_PROJECT` — Shift project dates
- `TIMESHEET_INSIGHTS` — Analyse timesheet data
- `PLAN_FUTURE_ALLOCATION` — Suggest allocation plans
- `MOVE_PROJECT_PHASE` — Shift a specific phase
- `BUDGET_ANALYSIS` — Analyse project budget vs. actuals
- `SEARCH` / `GENERAL_QUERY` — Information queries

---

### 4.10 Settings & Administration

**F-SETTINGS-01: AI Configuration (Super Admin Only)**
- App-wide LLM provider and API key configuration stored server-side.
- Supports OpenAI and Google Gemini providers.
- Emergent LLM key serves as automatic fallback.
- API key is masked when displayed.

**F-SETTINGS-02: Data Cleanup (Admin)**
- Scan for orphaned records (allocations/timesheets/status updates referencing deleted projects or resources).
- Execute cleanup to remove orphaned records.

**F-SETTINGS-03: Profile Avatar**
- All users can customise their avatar.

---

### 4.11 Client Portal

**F-CLIENT-01: Client View**
- Clients see only projects assigned to them (via `allowed_project_ids`).
- Read-only access to project details.

---

## 5. Technical Specification

### 5.1 Architecture

```
┌─────────────────────────────────────────────────┐
│                   Client (Browser)               │
│     React 18 + TanStack Query + Shadcn/UI       │
│              Tailwind CSS                        │
└──────────────────┬──────────────────────────────┘
                   │ HTTPS (Kubernetes Ingress)
                   │ /api/* → Backend (port 8001)
                   │ /*     → Frontend (port 3000)
┌──────────────────▼──────────────────────────────┐
│              FastAPI (Python 3.11)               │
│        Motor (async MongoDB driver)              │
│        JWT Authentication (jose)                 │
│        Pydantic validation                       │
└──────────────────┬──────────────────────────────┘
                   │
         ┌─────────┼──────────┐
         ▼                    ▼
┌────────────────┐  ┌─────────────────┐
│   MongoDB      │  │  AI Services    │
│  (Atlas or     │  │  - OpenAI API   │
│   local)       │  │  - Gemini API   │
│                │  │  - Emergent LLM │
└────────────────┘  └─────────────────┘
```

### 5.2 Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend Framework | React (CRA) | 18.x |
| State Management | TanStack Query | 5.x |
| UI Components | Shadcn/UI + Tailwind CSS | Latest |
| Icons | Lucide React | Latest |
| Toasts | Sonner | Latest |
| HTTP Client | Axios | Latest |
| Backend Framework | FastAPI | Latest |
| Database Driver | Motor (async) | Latest |
| Database | MongoDB | 6.x+ |
| Authentication | JWT (python-jose) | Latest |
| Password Hashing | bcrypt | Latest |
| AI Integration | emergentintegrations library | Latest |
| HTTP Client (Backend) | httpx | Latest |
| Timezone | pytz (Australia/Sydney) | Latest |

### 5.3 Frontend Architecture

```
/app/frontend/src/
├── App.js                 # Router, auth state, protected routes
├── api.js                 # Axios instance, all API functions
├── index.css              # Global styles + Tailwind
├── contexts/
│   └── SandboxContext.js   # Draft/scenario mode context
├── pages/
│   ├── Login.js            # Auth page
│   ├── ChangePassword.js   # Password change flow
│   ├── Dashboard.js        # Main dashboard with tabs
│   ├── Projects.js         # Project list
│   ├── ProjectDetail.js    # Single project (tabs: overview, phases, time, status, risks, AI)
│   ├── ProjectReport.js    # Project report view
│   ├── Resources.js        # Resource management
│   ├── Allocations.js      # Grouped allocation view
│   ├── Reports.js          # Planned vs. Actuals dashboard
│   ├── ManageTimesheets.js # Super admin timesheet management
│   ├── Settings.js         # AI config + avatar + data cleanup
│   ├── Users.js            # User management
│   ├── Holidays.js         # Holiday management
│   ├── Leaves.js           # Leave management
│   └── ClientPortal.js     # Client-facing project view
└── components/
    ├── Layout.js            # App shell, sidebar navigation
    ├── CommandBar.js        # AI command bar (Ctrl+K)
    ├── ConfirmCommandDialog.js  # AI command confirmation modal
    ├── ProjectWizard.js     # 5-step project creation
    ├── TimesheetWeeklyCheckin.js # Timesheet entry component
    ├── ProjectStatusCheckin.js  # Status update form
    ├── WeeklyCheckin.js     # Allocation confirmation
    ├── AllocationEditor.js  # Allocation form
    ├── InteractiveTimelineGrid.js # Visual timeline
    ├── TimelineGrid.js      # Read-only timeline
    ├── PhaseVisualizer.js   # Phase Gantt-style display
    └── ui/                  # Shadcn/UI component library
```

### 5.4 Backend Architecture

Single-file FastAPI server (`/app/backend/server.py`, ~4900 lines) containing:
- Pydantic models for request/response validation
- JWT auth middleware and role-based dependency injection
- CRUD endpoints for all entities
- AI integration layer (OpenAI, Gemini, Emergent)
- Reporting/aggregation endpoints
- Data migration and cleanup utilities

### 5.5 Environment Variables

| Variable | Location | Purpose |
|----------|----------|---------|
| `MONGO_URL` | backend/.env | MongoDB connection string |
| `DB_NAME` | backend/.env | Database name (`resource_planner`) |
| `SECRET_KEY` | backend/.env | JWT signing key |
| `EMERGENT_LLM_KEY` | backend/.env | Fallback AI API key |
| `REACT_APP_BACKEND_URL` | frontend/.env | API base URL for preview/production |

---

## 6. Data Model

### 6.1 Collections

#### `users`
```json
{
  "_id": ObjectId,
  "email": "string (unique)",
  "password_hash": "bcrypt hash",
  "role": "super_admin | admin | resource | client",
  "resource_id": "string (FK to resources._id, optional)",
  "must_change_password": "boolean",
  "allowed_project_ids": ["string"],
  "avatar_url": "string (optional)"
}
```

#### `resources`
```json
{
  "_id": ObjectId,
  "name": "string",
  "role": "string (job title, e.g. Developer, Consultant)",
  "email": "string (optional)",
  "standard_capacity": "integer (default 100)",
  "department": "string (optional)",
  "skills": ["string"],
  "avatar_url": "string (optional)"
}
```

#### `projects`
```json
{
  "_id": ObjectId,
  "name": "string",
  "client_name": "string",
  "status": "Active | Pipeline | Completed",
  "start_date": "datetime",
  "end_date": "datetime",
  "is_draft": "boolean",
  "budgeted_hours": "float (optional, project-level budget)",
  "phases": [
    {
      "id": "UUID string",
      "name": "string",
      "start_date": "string (YYYY-MM-DD)",
      "end_date": "string (YYYY-MM-DD)",
      "status": "string",
      "budgeted_hours": "float (optional, phase-level budget)"
    }
  ],
  "status_summary": "string (AI-generated or manual)",
  "status_summary_updated_at": "ISO datetime string",
  "health": "Green | Amber | Red (from latest status update)",
  "schedule_status": "On Track | Delayed | Ahead of Schedule | At Risk",
  "actual_progress": "integer 0-100",
  "created_at": "datetime"
}
```

#### `allocations`
```json
{
  "_id": ObjectId,
  "resource_id": "string (FK to resources._id)",
  "project_id": "string (FK to projects._id)",
  "start_date": "datetime",
  "end_date": "datetime",
  "percentage": "integer (0-100)",
  "hours": "integer (optional, alternative to percentage)",
  "allocation_type": "percentage | hours",
  "role": "string (project-specific role)",
  "actual_percentage": "integer (confirmed by resource)",
  "confirmation_status": "Pending | Confirmed",
  "phase_names": ["string"]
}
```

#### `timesheets`
```json
{
  "_id": ObjectId,
  "resource_id": "string (FK to resources._id)",
  "project_id": "string (FK to projects._id)",
  "phase_id": "string (UUID, FK to project phase, optional)",
  "week_start_date": "datetime",
  "week_end_date": "datetime",
  "planned_hours": "float",
  "actual_hours": "float",
  "variance_hours": "float (calculated: actual - planned)",
  "variance_percentage": "float (calculated)",
  "notes": "string (optional)",
  "status": "Draft | Submitted",
  "auto_filled": "boolean",
  "modified_by_user": "boolean",
  "submitted_at": "datetime (optional)",
  "created_at": "datetime"
}
```

#### `status_updates`
```json
{
  "_id": ObjectId,
  "project_id": "string (FK to projects._id)",
  "updated_by": "string (email)",
  "updated_by_name": "string",
  "update_date": "ISO date string",
  "health": "Green | Amber | Red",
  "schedule_status": "On Track | Delayed | Ahead of Schedule | At Risk",
  "actual_progress": "integer 0-100",
  "accomplishments": "string",
  "blockers": "string",
  "next_steps": "string",
  "notes": "string",
  "ai_generated_summary": "string",
  "week_start_date": "string",
  "created_at": "ISO datetime"
}
```

#### `risks`
```json
{
  "_id": ObjectId,
  "project_id": "string (FK to projects._id)",
  "description": "string",
  "impact": "Low | Medium | High | Critical",
  "probability": "Low | Medium | High"
}
```

#### `leaves`
```json
{
  "_id": ObjectId,
  "resource_id": "string (FK to resources._id)",
  "start_date": "datetime",
  "end_date": "datetime",
  "type": "Vacation | Sick | Public Holiday",
  "notes": "string (optional)"
}
```

#### `holidays`
```json
{
  "_id": ObjectId,
  "name": "string",
  "date": "datetime",
  "description": "string (optional)"
}
```

#### `settings`
```json
{
  "_id": ObjectId,
  "type": "ai_config",
  "ai_provider": "openai | gemini",
  "ai_api_key": "string (encrypted at rest via MongoDB Atlas)"
}
```

### 6.2 Indexes

- `users.email` — unique
- `allocations.resource_id`
- `allocations.project_id`
- `timesheets.resource_id`
- `timesheets.project_id`
- `status_updates.project_id`

---

## 7. API Reference

### 7.1 Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/login` | None | Login (OAuth2 form data) |
| POST | `/api/auth/register` | Admin | Create new user |
| GET | `/api/auth/me` | Any | Get current user profile |
| PUT | `/api/auth/avatar` | Any | Update avatar URL |
| POST | `/api/auth/change-password` | Any | Change own password |

### 7.2 Admin

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/admin/create-resource-user` | Admin+ | Create user linked to resource |
| GET | `/api/admin/users` | Admin+ | List all users |
| PUT | `/api/admin/users/{id}/role` | Admin+ | Change user role |
| PUT | `/api/admin/users/{id}/reset-password` | Admin+ | Reset to Welcome123! |
| GET | `/api/admin/data-cleanup/scan` | Admin+ | Scan for orphaned data |
| POST | `/api/admin/data-cleanup/execute` | Admin+ | Delete orphaned data |
| GET | `/api/admin/export-database` | Super Admin | Export all collections |
| POST | `/api/admin/migrate-phase-ids` | Super Admin | Fix missing phase UUIDs |

### 7.3 AI Settings

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/settings/ai` | Super Admin | Get app-wide AI config (masked key) |
| PUT | `/api/settings/ai` | Super Admin | Set provider + API key |
| DELETE | `/api/settings/ai` | Super Admin | Clear AI config (revert to Emergent fallback) |

### 7.4 Resources

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/resources` | Any | List all resources |
| POST | `/api/resources` | Super Admin | Create resource |
| PUT | `/api/resources/{id}` | Admin+ | Update resource |
| DELETE | `/api/resources/{id}` | Super Admin | Delete resource |
| GET | `/api/users/me/resource` | Any | Get current user's linked resource |

### 7.5 Projects

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/projects` | Any | List all projects |
| GET | `/api/projects/{id}` | Any | Get project detail (includes actual_hours, health) |
| POST | `/api/projects` | Admin+ | Create project |
| PUT | `/api/projects/{id}` | Admin+ | Update project |
| DELETE | `/api/projects/{id}` | Admin+ | Delete project |
| POST | `/api/projects/wizard` | Admin+ | Create via wizard (project + allocations + risks) |
| POST | `/api/projects/create-full` | Admin+ | Create with full data |
| GET | `/api/projects/{id}/phases` | Any | List project phases |
| GET | `/api/projects/{id}/risks` | Any | List project risks |
| GET | `/api/projects/{id}/allocations` | Any | List project allocations |
| POST | `/api/projects/{id}/reschedule` | Admin+ | Shift project dates |
| POST | `/api/projects/{id}/move-phase` | Admin+ | Shift a specific phase |
| POST | `/api/projects/{id}/generate-summary` | Admin+ | Generate AI summary |
| PATCH | `/api/projects/{id}/summary` | Admin+ | Manually edit summary |

### 7.6 Allocations

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/allocations` | Any | List all (enriched with resource/project names) |
| POST | `/api/allocations` | Admin+ | Create allocation |
| PUT | `/api/allocations/{id}` | Admin+ | Update allocation |
| PUT | `/api/allocations/{id}/confirm` | Any | Confirm allocation (timesheet window) |
| DELETE | `/api/allocations/{id}` | Admin+ | Delete allocation |
| GET | `/api/allocations/by-cell` | Any | Get allocations for grid cell |
| POST | `/api/allocations/move-resource` | Admin+ | Move resource between projects |
| GET | `/api/allocation-roles` | Any | List predefined roles |

### 7.7 Timesheets

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/timesheets` | Any | Create timesheet entry |
| GET | `/api/timesheets/my-week` | Any | Get week's timesheets (personal or all) |
| PUT | `/api/timesheets/{id}` | Any | Update timesheet |
| DELETE | `/api/timesheets/{id}` | Any | Delete draft timesheet |
| POST | `/api/timesheets/auto-fill` | Any | Auto-fill from allocations |
| POST | `/api/timesheets/submit-week` | Any | Submit all drafts for week |
| GET | `/api/timesheet/can-update` | Any | Check if timesheet window is open |

### 7.8 Status Updates

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/status-updates` | Any | Submit status check-in |
| GET | `/api/status-updates/project/{id}` | Any | Get project status history |
| GET | `/api/status-updates/latest/{id}` | Any | Get latest status update |
| GET | `/api/status-updates/my-projects` | Any | Get projects user can update |
| GET | `/api/status-options` | Any | Get health/schedule options |

### 7.9 Reporting

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/reports/planned-vs-actual/overview` | Any | Portfolio budget overview |
| GET | `/api/reports/planned-vs-actual/project/{id}` | Any | Per-project time report |
| GET | `/api/reports/time-tracking/summary` | Any | Time tracking dashboard |
| GET | `/api/reports/capacity` | Any | Capacity report by date range |

### 7.10 AI

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/ai/command` | Any | Natural language command (app-wide key) |
| GET | `/api/ai/project-budget-analysis/{id}` | Any | AI budget analysis for project |
| GET | `/api/ai/portfolio-budget-analysis` | Any | AI portfolio-level analysis |
| POST | `/api/ai/timesheet-insights` | Any | AI timesheet analysis |
| POST | `/api/ai/plan-allocation` | Any | AI allocation recommendation |

### 7.11 Leaves & Holidays

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/leaves` | Any | List all leaves |
| POST | `/api/leaves` | Admin+ | Create leave |
| DELETE | `/api/leaves/{id}` | Admin+ | Delete leave |
| GET | `/api/holidays` | Any | List all holidays |
| POST | `/api/holidays` | Admin+ | Create holiday |
| DELETE | `/api/holidays/{id}` | Admin+ | Delete holiday |

### 7.12 Client Portal

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/client/projects` | Client | Get assigned projects |

---

## 8. Security & Access Control

### 8.1 Authentication Flow
1. User submits email + password to `/api/auth/login`.
2. Server validates credentials against bcrypt hash.
3. Server returns JWT token (HS256, 24-hour expiry).
4. Client stores token in `localStorage` and sends in `Authorization: Bearer <token>` header.

### 8.2 Role-Based Access
- Four dependency injection guards: `require_admin`, `require_super_admin`, `require_admin_or_above`, `require_resource_or_above`.
- Frontend enforces route-level access via `ProtectedRoute` wrapper and `allowedRoles` prop.
- Navigation items filtered by user role.

### 8.3 Data Isolation
- Resources can only create/edit their own timesheets (verified via `find_user_resource`).
- Clients see only projects in their `allowed_project_ids`.
- Super admins have full cross-user access for timesheet management.

### 8.4 API Key Security
- App-wide AI API key stored in MongoDB `settings` collection (server-side only).
- Frontend never receives the raw key — only a masked version.
- Emergent LLM key stored in backend `.env`, never exposed to frontend.

---

## 9. AI Integration

### 9.1 Architecture

```
User Request
     │
     ▼
get_ai_config()  ──► 1. Check MongoDB settings (app-wide key)
     │                2. Fallback to EMERGENT_LLM_KEY
     ▼
Provider Router
     ├── "openai"  ──► OpenAI API (gpt-4o-mini)
     ├── "gemini"  ──► Google Gemini API (gemini-2.5-flash)
     └── "emergent" ──► Emergent LLM (via emergentintegrations library)
```

### 9.2 AI Features

| Feature | Endpoint | Model Used | Input | Output |
|---------|----------|-----------|-------|--------|
| Command Bar | `/api/ai/command` | App-wide config | Natural language query | Structured intent + entities |
| Project Budget Analysis | `/api/ai/project-budget-analysis/{id}` | Emergent LLM | Project budget/actuals data | JSON: narrative, burn rate, alerts, recommendations |
| Portfolio Analysis | `/api/ai/portfolio-budget-analysis` | Emergent LLM | All project summaries | JSON: narrative, alerts, recommendations, highlights |
| Status Summary | Inline (status-updates) | App-wide config | Status update data | Executive summary text |
| Timesheet Insights | `/api/ai/timesheet-insights` | Emergent LLM | Timesheet data | Analysis text |
| Allocation Planning | `/api/ai/plan-allocation` | Emergent LLM | Resource/project data | Allocation recommendations |

### 9.3 Fallback Strategy
1. Try app-wide configured provider (OpenAI or Gemini).
2. If that fails, automatically fall back to Emergent LLM key.
3. If both fail, return error with guidance.

---

## 10. Business Rules & Constraints

### 10.1 Timesheet Window
- **Open:** Thursday 00:00 (Sydney) to Monday 12:00 PM (Sydney).
- **Closed:** Monday 12:00 PM to Wednesday 23:59 (Sydney).
- Applies to: timesheet creation/editing, allocation confirmation, week submission.
- Checked via `is_timesheet_update_allowed()` function.

### 10.2 Budget Health Classification
| Condition | Health Status |
|-----------|--------------|
| Actual hours > Budget | `over_budget` |
| Actual hours > 80% of Budget | `at_risk` |
| Actual hours <= 80% of Budget | `on_track` |
| No budget set | `no_budget` |

### 10.3 Phase ID Management
- All project phases must have a UUID `id` field.
- `ensure_phase_ids()` auto-generates UUIDs for phases missing them.
- Applied on project creation, update, and server startup (migration).

### 10.4 Working Hours Calculation
- 100% allocation = 40 hours/week.
- Pro-rated for partial weeks based on date overlap.
- `calculate_weekly_hours(percentage, alloc_start, alloc_end, week_start, week_end)`.

### 10.5 User-Resource Linking Priority
1. Direct `resource_id` FK on user record (most reliable).
2. Exact email match on resource record.
3. Normalised name matching (handles `first.last@domain` → "First Last").
4. First-name match from email prefix.
5. Containment match on normalised strings.

---

## 11. Non-Functional Requirements

### 11.1 Performance
- MongoDB connection pool: 10-50 connections.
- API timeouts: 5s server selection, 10s connection, 30s socket.
- Frontend uses TanStack Query with stale-time caching.
- AI endpoints may take 3-10 seconds (LLM latency).

### 11.2 Availability
- Backend managed via Supervisor (auto-restart on crash).
- MongoDB Atlas for production (replica set, majority write concern).
- Hot reload enabled for development.

### 11.3 Scalability
- Single-server deployment currently.
- MongoDB Atlas scales horizontally.
- Stateless JWT auth allows horizontal API scaling.

### 11.4 Browser Support
- Modern browsers (Chrome, Firefox, Safari, Edge — latest 2 versions).
- Mobile-responsive UI (Tailwind breakpoints).

---

## 12. Known Limitations & Technical Debt

### 12.1 Architecture
- **Single-file backend:** `server.py` is ~4900 lines. Should be refactored into route modules (`/routes/auth.py`, `/routes/projects.py`, etc.).
- **No automated test suite in CI/CD.** Tests exist but are run manually.

### 12.2 User-Resource Linking
- The name-matching fallback in `find_user_resource()` is fragile for unusual email formats (e.g., `ckun63@gmail.com` → "Chandni Gupta" requires the `resource_id` FK).
- **Recommendation:** Ensure all users have `resource_id` set at account creation. The name-matching fallback should be treated as a safety net, not primary logic.

### 12.3 Timesheet Restrictions
- The timesheet window applies uniformly. There is no per-project or per-user override mechanism.
- Super admin exemption from timesheet window is not explicitly implemented for all endpoints.

### 12.4 Data Validation
- Phase budgets are optional and don't auto-sum to project budget.
- No prevention of overlapping allocations for the same resource/project.

### 12.5 Security
- JWT token stored in localStorage (XSS vulnerable; consider HttpOnly cookies for production hardening).
- No rate limiting on login attempts.
- AI API key stored in plaintext in MongoDB (encrypted at rest via Atlas, but not application-level encryption).

---

## 13. Future Roadmap

### P1 — Near-term
- **User-Resource FK Refactor:** Ensure all user accounts have `resource_id` set; add admin UI to fix/link existing accounts.
- **Server Modularisation:** Break `server.py` into route modules for maintainability.

### P2 — Medium-term
- **GCP Deployment:** Dockerfile, Cloud Run/GKE configuration, CI/CD pipeline.
- **Email Notifications:** Automated weekly report emails to stakeholders.
- **Audit Log:** Track who changed what and when.

### P3 — Longer-term
- **Client Dashboards:** Secure, view-only shareable links for clients.
- **Advanced Capacity Planning:** What-if scenario modelling for resource allocation.
- **Integration:** Calendar sync (Google Calendar), Slack notifications.

---

*End of Document*
