# DD Planner

**Full-stack resource planning, project management, and AI-powered consulting operations platform built for DD Consulting.**

DD Planner centralises WBS planning, resource allocation, timesheet tracking, capacity heatmaps, risk management, and AI-driven insights into a single application — with integrations for HubSpot CRM and an MCP Server that lets external AI agents query your portfolio.

---

## Table of Contents

1. [Features at a Glance](#features-at-a-glance)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Getting Started](#getting-started)
5. [Environment Variables](#environment-variables)
6. [Default Accounts](#default-accounts)
7. [Roles & Permissions (RBAC)](#roles--permissions-rbac)
8. [Core Modules](#core-modules)
9. [AI Capabilities](#ai-capabilities)
10. [Integrations](#integrations)
11. [API Reference](#api-reference)
12. [Project Structure](#project-structure)
13. [Related Documentation](#related-documentation)

---

## Features at a Glance

| Category | Highlights |
|---|---|
| **Project Management** | Create projects with phases, WBS breakdown, milestones, Gantt timeline, budget tracking |
| **Resource Planning** | Allocate team members to projects, capacity heatmaps, over-allocation alerts |
| **Timesheets** | Weekly autofill, admin review, timesheet reports with date-range filtering |
| **Risk Management** | Risk register per project, AI-powered risk polishing, deduplication |
| **AI Assistant** | Conversational chat, multi-step action plans, specialist sub-agents (@budget, @risk, @resource, @schedule) |
| **Client Portal** | Read-only project view for clients via login or magic link |
| **Reports & Exports** | PDF/PPTX export, budget reconciliation, planned vs actual, resource utilisation |
| **Integrations** | HubSpot CRM (bi-directional), MCP Server for external AI agents |
| **RBAC** | 5 roles: Super Admin, Admin, Resource, Contractor, Client — each with scoped access |

---

## Architecture

```
                    ┌─────────────────────────────────┐
                    │         React Frontend           │
                    │   (Tailwind, shadcn/ui, Recharts)│
                    │         Port 3000                │
                    └───────────┬─────────────────────┘
                                │ /api/* proxied
                    ┌───────────▼─────────────────────┐
                    │       FastAPI Backend            │
                    │   (Python, Pydantic, Motor)      │
                    │         Port 8001                │
                    └───────────┬─────────────────────┘
                                │
              ┌─────────────────┼─────────────────────┐
              ▼                 ▼                      ▼
        ┌──────────┐   ┌───────────────┐   ┌───────────────────┐
        │ MongoDB  │   │ OpenAI GPT-4o │   │ External Services │
        │ (Motor)  │   │ (Emergent Key)│   │ HubSpot, Resend   │
        └──────────┘   └───────────────┘   └───────────────────┘
```

All frontend API calls go through `/api/*` and are routed to the backend via Kubernetes ingress. The backend communicates with MongoDB asynchronously via Motor.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Tailwind CSS, shadcn/ui, React Query, Recharts, date-fns, Lucide icons |
| Backend | Python 3.11+, FastAPI, Pydantic, Motor (async MongoDB driver), httpx |
| Database | MongoDB (local or Atlas) |
| AI | OpenAI GPT-4o via Emergent LLM Key |
| PDF/PPTX Export | Playwright (headless Chromium) |
| Email | Resend API |
| CRM | HubSpot Private App API |
| Auth | JWT (HS256), bcrypt password hashing |

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ and Yarn
- MongoDB 6+ (local or Atlas connection string)

### 1. Clone and install

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd ../frontend
yarn install
```

### 2. Configure environment

Create `.env` files in both `backend/` and `frontend/` directories. See [Environment Variables](#environment-variables) below.

### 3. Start the application

```bash
# Terminal 1 — Backend
cd backend
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Terminal 2 — Frontend
cd frontend
yarn start
```

The frontend runs on `http://localhost:3000` and proxies `/api/*` requests to `http://localhost:8001`.

### 4. First-time setup

On first startup the backend will:
- Create MongoDB indexes
- Seed demo data (5 resources, 4 projects, 10 allocations, 2 user accounts)
- Backfill baselines for existing projects
- Pre-warm Playwright for PDF exports

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `MONGO_URL` | Yes | MongoDB connection string (e.g. `mongodb://localhost:27017` or Atlas URI) |
| `DB_NAME` | Yes | Database name (default: `resource_planner`) |
| `SECRET_KEY` | Recommended | JWT signing key. Auto-generated from MONGO_URL hash if omitted in production |
| `EMERGENT_LLM_KEY` | For AI features | Universal LLM key for OpenAI GPT-4o access |
| `RESEND_API_KEY` | For email | Resend.com API key for email notifications and magic links |
| `SENDER_EMAIL` | For email | Sender email address (default: `onboarding@resend.dev`) |

### Frontend (`frontend/.env`)

| Variable | Required | Description |
|---|---|---|
| `REACT_APP_BACKEND_URL` | Yes | Base URL of the deployed application (used for export rendering) |

---

## Default Accounts

The application seeds the following accounts on first run:

| Role | Email | Password | Access |
|---|---|---|---|
| Admin | `admin@test.com` | `admin123` | Full project/resource management |
| Client | `client@test.com` | `client123` | Read-only view of assigned projects |

Additional accounts (created manually via the Users page):

| Role | Email | Password | Access |
|---|---|---|---|
| Super Admin | `don@ddconsult.tech` | `Welcome123!` | Everything + Settings, Integrations |
| Resource | `riley@test.com` | `riley123` | Own timesheets, allocations, dashboard |

---

## Roles & Permissions (RBAC)

DD Planner enforces **Role-Based Access Control** across the entire application — REST API, AI chat, and UI navigation.

| Permission | Super Admin | Admin | Resource / Contractor | Client |
|---|---|---|---|---|
| Dashboard (Command Center) | Full portfolio | Full portfolio | Personal dashboard | — |
| Projects (CRUD) | All | All | View allocated projects | View assigned only |
| Resources (CRUD) | All | All | — | — |
| Allocations | Manage all | Manage all | View own only | — |
| Timesheets | Manage all | View reports | Submit own | — |
| WBS / Milestones | Full edit | Full edit | View only | View only |
| Risks | Full edit | Full edit | View only | View only |
| Status Updates | Create/edit | Create/edit | View only | View only |
| AI Chat | Full actions | Full actions | Read-only (query) | Read-only (query) |
| Reports & Exports | All | All | — | — |
| Users Management | All | All | — | — |
| Settings | Full | — | — | — |
| Integrations | Full | — | — | — |
| Client Portal | — | — | — | Full |

**Project Leads** get elevated permissions on projects they lead — can edit project details, manage risks, create status updates, and use AI actions for those projects specifically.

---

## Core Modules

### Projects
- Full lifecycle: Pipeline → Active → Completed
- Multi-phase support with independent dates and budgets
- Project wizard for guided creation with phases and initial team allocations
- Customer contact information (name, email, phone, role)
- Project lead assignment with lead-specific permissions
- Draft/Scenario mode for what-if planning

### Work Breakdown Structure (WBS)
- Hierarchical task tree with Board and List views
- Milestones (zero-hour tasks with diamond markers)
- Task comments with @mentions and notifications
- Drag-and-drop reordering
- AI-powered WBS generation from project description
- Baseline snapshots and variance tracking
- Business-days-only scheduling (Mon–Fri)
- Cascade date changes to dependent tasks

### Resource Management
- Team member profiles with roles and capacity settings
- Activate/deactivate lifecycle (soft delete with history preservation)
- Linked user accounts for login access
- Automatic exclusion of inactive resources from pickers and reports

### Allocations
- Assign resources to projects with percentage and date range
- Budget enforcement — prevents over-allocation beyond project budget
- Interactive timeline heatmap (14-day capacity view)
- Phase-level allocation attribution
- Business days × 8h/day formula (40h work week)

### Timesheets
- Weekly timesheet entry with project/phase/WBS task selection
- Autofill from allocations (pre-populates hours based on current assignments)
- Admin review and approval workflow
- Timesheet reports with date-range filtering and resource breakdown
- Resource dashboard shows timesheet status and nudges for missing entries

### Reports & Exports
- Budget reconciliation (budgeted vs allocated vs actual)
- Planned vs actual hours analysis
- Resource utilisation report
- Capacity report with availability forecasting
- PDF and PowerPoint export via headless Chromium
- Portfolio Gantt with milestone markers

### Risk Management
- Risk register per project (description, impact, probability, status, mitigation)
- AI-powered risk polishing and deduplication
- Smart sorting by severity

### Client Portal
- Dedicated read-only view for client users
- Magic link sharing (30-day expiry, no login required)
- Project health, status updates, and team visibility

### Dashboard
- **Admin Command Center**: Portfolio KPIs, project health overview, action items banner
- **Resource Dashboard**: Personalised view with own utilisation, hours, active projects, timesheet status, upcoming allocations, recent timesheets, and leave schedule

### Notifications & Action Items
- Real-time action items computed per user role
- Types: missing timesheets, draft timesheets, budget alerts, overdue milestones, status update reminders, allocation endings
- Severity levels: high (red), medium (amber), low (blue)
- Bell icon with unread count, auto-refresh every 30 seconds

---

## AI Capabilities

DD Planner includes a built-in AI assistant powered by OpenAI GPT-4o, accessible via the floating chat panel on every page.

### Conversational Chat
- Natural language queries about projects, resources, budgets, and timesheets
- Context-aware: automatically includes relevant project data, allocations, and history
- Role-scoped: admins get full action capabilities; resources and clients get read-only insights

### AI Actions (Admin/Lead only)
- Create/update projects, allocations, risks, status updates
- Reschedule projects with AI-analyzed recommendations
- Polish risks, generate WBS structures, trigger budget analysis
- Multi-step batch plans with "Execute All" button
- Destructive actions require confirmation tokens (10-minute TTL)

### Specialist Sub-Agents
Prefix your chat message with a trigger to activate a focused specialist:
- `@resource` — Capacity and allocation analysis
- `@budget` — Burn rate and financial health
- `@risk` — Risk prioritisation and mitigation
- `@schedule` — Timeline adherence and deadline tracking

### AI Instructions & Memory
- **Custom Instructions**: Per-project or global rules injected into all AI prompts (e.g., "Always recommend buffer time for government clients")
- **Agent Memory**: Save decisions, preferences, and context from chat conversations for future reference
- **AI Feedback**: Thumbs up/down on AI outputs for continuous improvement

### Proactive Health Monitor
- Background daily check analysing: budget overruns, over-allocated resources, stale status updates, overdue milestones, unmitigated high risks
- Critical findings automatically create in-app notifications
- Manual trigger via `POST /api/ai/health-monitor/run`

---

## Integrations

DD Planner supports external integrations configured via **Settings > Integrations** (Super Admin only).

### HubSpot CRM (Bi-directional)
- **Inbound**: When a HubSpot deal moves to a trigger stage (default: "Closed Won"), DD Planner automatically creates a project with mapped fields (deal name, amount, dates, company, contact)
- **Outbound**: When a status update is submitted for a HubSpot-linked project, a note is pushed to the deal in HubSpot
- Setup requires a HubSpot Private App Token

### MCP Server (AI Agent API)
- Exposes DD Planner data as tools for any MCP-compatible AI agent (Gemini, Copilot, VS Code, etc.)
- JSON-RPC 2.0 protocol over HTTP
- Tools: `list_projects`, `get_project_status`, `get_team_capacity`, `get_recent_updates`
- Auth via `X-Agent-Key` header (generated in Settings)

### Email (Resend)
- Magic link delivery for client portal
- Notification emails
- Requires `RESEND_API_KEY` environment variable

> For detailed setup instructions, see [INTEGRATIONS.md](./INTEGRATIONS.md).

---

## API Reference

### Authentication
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/login` | Login (returns JWT) |
| GET | `/api/auth/me` | Get current user |
| POST | `/api/auth/change-password` | Change password |

### Projects
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/projects` | List all projects |
| POST | `/api/projects` | Create project |
| POST | `/api/projects/wizard` | Create project via wizard (with phases + allocations) |
| GET | `/api/projects/:id` | Get project detail (includes milestones, WBS summary) |
| PUT | `/api/projects/:id` | Update project |
| DELETE | `/api/projects/:id` | Delete project |
| POST | `/api/projects/:id/generate-summary` | AI-generate summary |
| POST | `/api/projects/:id/reschedule` | Reschedule project dates |
| GET | `/api/projects/:id/budget-health` | Budget health breakdown |

### Resources
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/resources` | List all resources |
| POST | `/api/resources` | Create resource |
| PUT | `/api/resources/:id` | Update resource |
| DELETE | `/api/resources/:id` | Delete (blocked if has history) |
| POST | `/api/resources/:id/deactivate` | Soft deactivate |
| POST | `/api/resources/:id/reactivate` | Reactivate |

### Allocations
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/allocations` | List all allocations (admin only) |
| POST | `/api/allocations` | Create allocation |
| PUT | `/api/allocations/:id` | Update allocation |
| DELETE | `/api/allocations/:id` | Delete allocation |
| POST | `/api/allocations/validate` | Validate allocation (capacity check) |
| GET | `/api/my-allocations` | Get own allocations (resource) |

### Timesheets
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/timesheets` | Get timesheets (admin: all, resource: own) |
| POST | `/api/timesheets` | Submit timesheet entries |
| GET | `/api/timesheets/history` | Own timesheet history by week |
| GET | `/api/timesheets/autofill` | Auto-fill current week from allocations |

### WBS
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/wbs/:projectId/tasks` | List WBS tasks |
| POST | `/api/wbs/:projectId/tasks` | Create task |
| PUT | `/api/wbs/tasks/:id` | Update task |
| DELETE | `/api/wbs/tasks/:id` | Delete task |
| PATCH | `/api/wbs/tasks/:id/complete-milestone` | Toggle milestone completion |
| GET | `/api/wbs/tasks/:id/comments` | List task comments |
| POST | `/api/wbs/tasks/:id/comments` | Add comment (@mention support) |

### Risks
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/projects/:id/risks` | List project risks |
| POST | `/api/projects/:id/risks` | Create risk |
| PUT | `/api/risks/:id` | Update risk |
| DELETE | `/api/risks/:id` | Delete risk |
| POST | `/api/projects/:id/risks/polish-all` | AI-polish all risks |

### Reports
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/portfolio` | Portfolio overview with milestones |
| GET | `/api/reports/capacity` | Capacity report |
| GET | `/api/reports/planned-vs-actual` | Planned vs actual hours |
| GET | `/api/reports/time-tracking-summary` | Timesheet analysis |
| GET | `/api/reports/resource-utilization` | Resource utilisation |
| POST | `/api/reports/magic-link` | Generate client magic link |

### AI
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ai/chat` | AI chat message |
| POST | `/api/ai/chat/execute-action` | Execute AI-suggested action |
| POST | `/api/ai/chat/execute-plan` | Execute multi-step plan |
| POST | `/api/ai/smart-reschedule/:id` | AI reschedule analysis |
| POST | `/api/ai/health-monitor/run` | Trigger health monitor |
| GET | `/api/ai/health-monitor/report` | Get latest health report |

### Integrations
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/integrations/settings` | Get integration config |
| PUT | `/api/integrations/settings` | Update integration config |
| POST | `/api/integrations/hubspot/test` | Test HubSpot connection |
| POST | `/api/integrations/hubspot/webhook` | HubSpot webhook receiver (public) |
| POST | `/api/integrations/agent-api/regenerate` | Generate/rotate MCP API key |
| GET | `/api/integrations/sync-logs` | View sync audit log |

### MCP Server
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/mcp` | Server manifest (no auth — discovery) |
| POST | `/api/mcp` | JSON-RPC 2.0 endpoint (requires `X-Agent-Key`) |

---

## Project Structure

```
/app
├── backend/
│   ├── server.py                       # FastAPI entrypoint, router registration, startup
│   ├── database.py                     # MongoDB connection, collection definitions
│   ├── utils.py                        # Shared helpers (business days, serialisation, calculations)
│   ├── auth/
│   │   └── dependencies.py             # JWT, bcrypt, get_current_user
│   ├── models/
│   │   └── schemas.py                  # Pydantic models for all entities
│   ├── routes/
│   │   ├── auth.py                     # Login, register, password change
│   │   ├── projects.py                 # Project CRUD, status updates, summaries
│   │   ├── resources.py                # Resource CRUD, activate/deactivate
│   │   ├── allocations.py              # Allocation CRUD, validation
│   │   ├── timesheets.py               # Timesheet submission, autofill, history
│   │   ├── wbs.py                      # WBS tasks, milestones, AI generation
│   │   ├── comments.py                 # WBS task comments, @mentions
│   │   ├── reports.py                  # Portfolio, capacity, exports (PDF/PPTX)
│   │   ├── ai.py                       # AI chat, action execution, reschedule
│   │   ├── ai_instructions.py          # Custom AI instructions CRUD
│   │   ├── ai_memory.py                # Agent memory CRUD
│   │   ├── admin.py                    # User management, notifications, reminders
│   │   ├── baselines.py                # Baseline snapshots and variance
│   │   ├── budget_reconciliation.py    # Budget vs allocated vs actual
│   │   ├── client_portal.py            # Client portal, magic links
│   │   ├── insights.py                 # Health scores, predictions, trends
│   │   ├── action_items.py             # Dashboard action items
│   │   ├── integrations.py             # HubSpot config, webhooks, sync logs
│   │   └── mcp_server.py              # MCP JSON-RPC endpoint
│   └── services/
│       ├── ai_actions.py               # Legacy AI action handlers
│       ├── ai_actions_extended.py       # Registry-based AI actions (tiers 1-3)
│       ├── ai_action_registry.py        # Action registry with destructive flags
│       ├── ai_instructions.py           # Instruction injection helper
│       ├── ai_providers.py              # LLM provider abstraction
│       ├── specialist_agents.py         # @resource/@budget/@risk/@schedule routing
│       ├── health_monitor.py            # Proactive portfolio health checks
│       ├── hubspot.py                   # HubSpot API client
│       ├── baselines.py                 # Baseline logic
│       ├── budget_reconciliation.py     # Budget calculation engine
│       ├── email.py                     # Resend email sending
│       ├── insights.py                  # Health score and prediction engine
│       ├── risk_ai.py                   # AI risk polishing
│       └── exports/                     # PDF/PPTX rendering via Playwright
│
├── frontend/
│   ├── src/
│   │   ├── App.js                      # React router, role-based route guards
│   │   ├── api.js                      # Axios API client with interceptors
│   │   ├── pages/
│   │   │   ├── Dashboard.js            # Admin Command Center / Resource Dashboard
│   │   │   ├── ResourceDashboard.js    # Personalised resource view
│   │   │   ├── Projects.js             # Project list
│   │   │   ├── ProjectDetail.js        # Full project view (Overview, WBS, Team, Risks, Settings)
│   │   │   ├── Portfolio.js            # Portfolio Gantt and analysis
│   │   │   ├── Allocations.js          # Allocation timeline grid
│   │   │   ├── MyAllocations.js        # Resource's own allocations
│   │   │   ├── ManageTimesheets.js     # Admin timesheet management
│   │   │   ├── MyTimesheets.js         # Resource timesheet entry
│   │   │   ├── Resources.js            # Resource management
│   │   │   ├── Users.js                # User account management
│   │   │   ├── Reports.js              # Reports hub
│   │   │   ├── Settings.js             # App settings + Integrations
│   │   │   ├── Leaves.js               # Time off management
│   │   │   ├── Holidays.js             # Company holidays
│   │   │   ├── ClientPortal.js         # Client project view
│   │   │   └── Login.js                # Login page
│   │   ├── components/
│   │   │   ├── Layout.js               # Sidebar, header, notifications, AI chat
│   │   │   ├── ChatPanel.js            # Floating AI chat panel
│   │   │   ├── WBSView.js              # WBS Board + List views
│   │   │   ├── WBSTaskDialog.js        # Task edit dialog
│   │   │   ├── ProjectWizard.js        # Guided project creation
│   │   │   ├── IntegrationsSettings.js # HubSpot + MCP config UI
│   │   │   ├── PortfolioGantt.js       # Interactive Gantt chart
│   │   │   └── ... (30+ components)
│   │   └── utils/
│   │       ├── dateHelpers.js          # Business day calculations
│   │       └── capacityHelpers.js      # Allocation formatting
│   └── tailwind.config.js
│
├── memory/
│   ├── PRD.md                          # Product requirements document
│   └── CHANGELOG.md                    # Session-by-session changes
│
├── GUIDE.md                            # User guide (how to use each feature)
├── INTEGRATIONS.md                     # Integration setup instructions
└── README.md                           # This file
```

---

## Related Documentation

| Document | Description |
|---|---|
| [GUIDE.md](./GUIDE.md) | Step-by-step user guide for every role and feature |
| [INTEGRATIONS.md](./INTEGRATIONS.md) | Detailed integration setup: HubSpot, MCP Server, Resend |
| [memory/PRD.md](./memory/PRD.md) | Full product requirements document |
| [memory/CHANGELOG.md](./memory/CHANGELOG.md) | Session-by-session changelog |

---

## License

Proprietary — DD Consulting. All rights reserved.
