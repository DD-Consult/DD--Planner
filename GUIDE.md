# DD Planner — User Guide

This guide walks through how to use DD Planner for every role. Whether you are a Super Admin managing the entire organisation, a team member tracking your hours, or a client checking on project progress — this guide has you covered.

---

## Table of Contents

1. [Logging In](#1-logging-in)
2. [Navigating the App](#2-navigating-the-app)
3. [Dashboard](#3-dashboard)
4. [Projects](#4-projects)
5. [Work Breakdown Structure (WBS)](#5-work-breakdown-structure-wbs)
6. [Resource Management](#6-resource-management)
7. [Allocations](#7-allocations)
8. [Timesheets](#8-timesheets)
9. [Risk Management](#9-risk-management)
10. [Reports & Exports](#10-reports--exports)
11. [Portfolio View](#11-portfolio-view)
12. [AI Assistant](#12-ai-assistant)
13. [Settings & Configuration](#13-settings--configuration)
14. [Client Portal](#14-client-portal)
15. [Notifications & Action Items](#15-notifications--action-items)
16. [Time Off & Holidays](#16-time-off--holidays)
17. [User Management](#17-user-management)

---

## 1. Logging In

1. Navigate to the application URL.
2. Enter your **email** and **password**.
3. Click **Sign In**.

If your account was just created by an admin, you may be prompted to **change your password** on first login.

> **Tip:** If your account has been disabled by an admin, you will see a "Your account has been disabled" message. Contact your administrator.

---

## 2. Navigating the App

The app has a **dark sidebar** on the left with navigation items that change based on your role:

| Nav Item | Available To |
|---|---|
| Dashboard | Admin, Super Admin, Resource |
| My Projects | Client |
| Resources | Admin, Super Admin |
| Projects | Admin, Super Admin, Resource |
| Portfolio | Admin, Super Admin |
| My Allocations | Resource, Contractor |
| Allocations | Admin, Super Admin |
| My Timesheets | Resource, Contractor |
| Manage Timesheets | Super Admin |
| Users | Admin, Super Admin |
| Time Off | Admin, Super Admin, Resource |
| Holidays | Admin, Super Admin, Resource |
| Reports | Admin, Super Admin |
| Timesheet Reports | Admin, Super Admin |
| Settings | Super Admin |

The **AI Chat** panel is accessible from every page via a floating button in the bottom-right corner.

The **notification bell** in the sidebar footer shows unread notifications with a count badge.

---

## 3. Dashboard

### Admin / Super Admin View
The Command Center shows:
- **Action Items Banner** — High-priority alerts (budget overruns, missing timesheets, overdue milestones) with severity badges and "Go" navigation links
- **Portfolio KPIs** — Project counts by status, team utilisation, budget health
- **Scenario/Draft Toggle** — Switch to show draft projects for what-if planning

### Resource / Contractor View
A personalised dashboard showing:
- **Greeting** with your name and current date
- **Action Items** — Your pending items (missing timesheets, etc.)
- **4 KPI Cards**: My Utilisation This Week, My Hours, Active Projects, Timesheet Status
- **My Allocations** — Current and upcoming assignments with project, client, role, percentage, and dates
- **Recent Timesheets** — Last 4 weeks with status badges
- **My Leaves** — Upcoming time off

---

## 4. Projects

### Viewing Projects
Navigate to **Projects** to see all projects in a list. Each card shows:
- Project name and client
- Status badge (Active / Pipeline / Completed)
- Health indicator (Green / Amber / Red)
- Progress percentage
- Date range

**Filtering:** Use the search bar and status filter to narrow down projects.

### Creating a Project

**Method 1 — Quick Create:**
1. Click **New Project**
2. Fill in: Name, Client, Status, Start Date, End Date, Budget Hours
3. Optionally add phases
4. Click **Create**

**Method 2 — Project Wizard:**
1. Click **New Project** and choose the Wizard option
2. **Step 1**: Basic info (name, client, dates, budget)
3. **Step 2**: Define phases with dates
4. **Step 3**: Allocate initial team members
5. Review and confirm

**Method 3 — AI Chat:**
Tell the AI: _"Create a new project called Website Redesign for Acme Corp starting next Monday for 6 weeks with 200 budgeted hours"_

### Project Detail
Click any project to open its detail view with tabs:

- **Overview**: Health, dates, progress, recent status updates, customer contact info. Admins can add status updates directly.
- **WBS**: Work Breakdown Structure (see section 5)
- **Team**: Allocated resources with percentages, hours/week, and dates. Admins can allocate, edit, or remove resources directly from here. Budget enforcement prevents over-allocation.
- **Risks**: Risk register (see section 9)
- **Settings**: Edit project details, manage phases, AI instructions, agent memory, baselines

### Status Updates
1. Go to a project's **Overview** tab
2. Click **Add Status Update**
3. Fill in: Health (Green/Amber/Red), Schedule Status, Progress %, Accomplishments, Blockers, Next Steps
4. Submit — the AI will auto-generate a summary

If the project is linked to HubSpot, the status update is automatically pushed as a note to the deal.

### Editing a Project
- Click the **Edit** button in the project header
- Modify fields and save
- **Project Leads** can edit projects they lead without needing admin access

---

## 5. Work Breakdown Structure (WBS)

The WBS tab provides a full task breakdown for each project.

### Views
- **Board View**: Kanban-style columns grouped by phase. Tasks show assignee, hours, status, and milestone badges. Comment counts shown as badges.
- **List View**: Tabular view with sortable columns.

### Creating Tasks
1. Click **Add Task** within a phase
2. Fill in: Name, Assignee, Planned Hours, Start/End Date, Priority
3. Mark as **Milestone** if it's a zero-hour checkpoint
4. Save

### Milestones
- Milestones appear as diamond markers in the Gantt and Board views
- Toggle completion via the milestone completion button
- Overdue milestones trigger action items on the dashboard

### Task Comments
1. Open a task in edit mode
2. Scroll to the **Comments** section
3. Add comments, use `@name` to mention team members (creates a notification)
4. Edit or delete your own comments

### AI WBS Generation
1. Click **AI Generate WBS** on the WBS tab
2. The AI analyses the project description, phases, and budget to generate a task tree
3. Review the generated tasks and click **Save** to apply

### Baselines
- Take a baseline snapshot to capture the current WBS state
- Compare baselines to see variance (planned vs actual dates and hours)
- Access via the **Settings** tab under Baselines

---

## 6. Resource Management

*Admin and Super Admin only.*

### Viewing Resources
Navigate to **Resources** to see all team members. Each row shows name, role, capacity, and status (Active/Inactive).

### Creating a Resource
1. Click **Add Resource**
2. Enter: Name, Role, Standard Capacity (default 100%)
3. Save

### Creating a Login for a Resource
1. Go to **Users**
2. Click **Create User**
3. Enter email, password, select role (Resource/Contractor), and link to the resource record
4. The resource can now log in and see their personalised dashboard

### Deactivating a Resource
When someone leaves the team:
1. Click **Deactivate** on their resource row
2. This will:
   - End all running allocations today
   - Delete future allocations
   - Disable linked user logins
   - Hide them from all pickers and reports
3. Their historical data (timesheets, past allocations) is preserved

### Reactivating
Click **Reactivate** on an inactive resource to restore them. Their linked user account is re-enabled.

> **Note:** Hard delete is blocked when a resource has history. Use deactivation instead.

---

## 7. Allocations

### Admin Allocation Management
Navigate to **Allocations** to see the interactive timeline grid:
- Rows are resources, columns are days
- Colour coding: Green (< 80%), Amber (80-100%), Red (> 100%)
- Click a cell to see/edit allocations for that resource on that date

### Creating an Allocation
1. Click **Add Allocation** or use the project's Team tab
2. Select: Resource, Project, Start Date, End Date, Percentage
3. The system validates against the project budget and shows a real-time budget impact calculation
4. If the allocation would exceed the budget, the submit button is disabled with a red warning

### My Allocations (Resource View)
Navigate to **My Allocations** to see your current and upcoming assignments:
- Project name, client, role, allocation percentage, hours/week, dates
- Status badge (Current / Upcoming / Ended)

---

## 8. Timesheets

### Submitting Your Timesheet (Resource)
1. Navigate to **My Timesheets**
2. Click **Autofill Current Week** — pre-populates hours from your allocations, split by project, phase, and WBS task
3. Review and adjust hours as needed
4. Click **Submit**

### Timesheet History
- My Timesheets shows your past weeks with status badges (Submitted / Draft / Missing)
- An amber banner notes: "Timesheet history is read-only. To make corrections, please contact your admin."
- Use **Load Older Weeks** to paginate

### Admin Timesheet Management
Super Admins can navigate to **Manage Timesheets** to:
- View all team timesheets grouped by week
- Filter by resource and date range
- Review and approve entries

### Timesheet Reports
Navigate to **Timesheet Reports** for aggregated analysis with date range filtering, resource breakdown, and project-level summaries.

---

## 9. Risk Management

### Viewing Risks
Go to a project's **Risks** tab to see the risk register sorted by severity.

### Adding a Risk
1. Click **Add Risk**
2. Fill in: Description, Impact (Low/Medium/High/Critical), Probability (Low/Medium/High), Status, Mitigation Plan
3. Save

### AI Risk Polishing
Click **Polish All Risks** to have the AI rewrite risk descriptions for clarity, add suggested mitigations, and deduplicate similar risks.

### Adding Risks via AI
Tell the AI: _"Add 3 risks to the Website Redesign project about scope creep, resource availability, and integration delays"_

---

## 10. Reports & Exports

Navigate to **Reports** for:

### Available Reports
- **Budget Reconciliation**: Budgeted vs Allocated vs Actual hours per project
- **Planned vs Actual**: Side-by-side comparison of planned and actual hours by resource
- **Resource Utilisation**: Utilisation percentage by resource over a date range
- **Capacity Report**: Team availability and bandwidth forecasting

### PDF & PowerPoint Exports
From any project detail page:
1. Click **Export**
2. Choose **PDF** or **PowerPoint**
3. The report is generated via headless Chromium and downloaded

### Client Magic Links
To share a project report with a client without requiring login:
1. Go to the project or the Reports page
2. Click **Generate Magic Link**
3. Copy the link and send it to the client
4. The link is valid for 30 days

---

## 11. Portfolio View

*Admin and Super Admin only.*

Navigate to **Portfolio** for a bird's-eye view:
- **Gantt Chart**: All projects on a timeline with phase bars and milestone diamonds
- **Hours Analysis**: Stacked breakdown of budgeted vs allocated vs actual
- **Legend**: Active (blue), Pipeline (grey), Milestone (purple diamond), Completed (green)
- Health scores and trends for each project

---

## 12. AI Assistant

The AI chat panel is available on every page. Click the floating chat button in the bottom-right corner.

### Asking Questions
- _"What's the budget status of the Mobile App project?"_
- _"Who is available next week?"_
- _"Show me Riley's timesheet for this month"_
- _"What are the top risks across all active projects?"_

### Taking Actions (Admin/Lead only)
- _"Assign Alice to the Website Redesign project at 50% for the next 2 weeks"_
- _"Create a status update for Mobile App — health is Amber, we're behind on the API integration"_
- _"Reschedule Data Migration forward by 2 weeks"_
- _"Generate a WBS for the Website Redesign project"_

### Multi-Step Plans
The AI can suggest batch operations:
- _"Set up the new Cloud Migration project — create it, add 3 phases, assign the backend team"_
- Review the plan card with numbered steps
- Click **Execute All** to run them sequentially

### Specialist Agents
Prefix your message with a trigger:
- `@resource Who is over-allocated this week?`
- `@budget What's the burn rate on the Mobile App?`
- `@risk What are the unmitigated critical risks?`
- `@schedule Which milestones are overdue?`

### AI Instructions
Admins can configure custom instructions that shape AI behaviour:
1. Go to a project's **Settings** tab
2. Open **AI Instructions**
3. Add instructions like: _"This is a government client — always recommend 20% buffer time"_
4. These are automatically injected into all AI prompts for that project

### Agent Memory
The AI can remember decisions and context:
- It automatically saves important decisions from chat
- You can manually add/edit memories in the project's Settings tab
- Memories persist across chat sessions

---

## 13. Settings & Configuration

*Super Admin only.*

Navigate to **Settings** to configure:

### AI Configuration
- AI provider settings (powered by Emergent LLM Key)

### Integrations
Scroll to the **Integrations** section for:

#### HubSpot CRM
- Enable/disable the integration
- Enter your HubSpot Private App Token
- Configure trigger stage (default: "Closed Won")
- Test the connection
- Copy the webhook URL to paste into HubSpot
- View sync logs

#### Agent API (MCP Server)
- Enable/disable the MCP endpoint
- Generate or rotate the API key
- Copy the MCP endpoint URL
- View when the key was last used

> For detailed setup instructions, see [INTEGRATIONS.md](./INTEGRATIONS.md).

---

## 14. Client Portal

*Client role only.*

After logging in as a client, you see **My Projects** — a read-only view of projects you've been granted access to.

Each project shows:
- Status and health
- Recent status updates with AI summaries
- Team members assigned
- Timeline and progress

### Magic Link Access
Clients can also access project reports without logging in via a magic link shared by an admin. The link is valid for 30 days.

---

## 15. Notifications & Action Items

### Action Items
The dashboard banner shows real-time action items tailored to your role:
- **Missing Timesheet** — you haven't submitted this week's timesheet
- **Draft Timesheet** — you started but didn't submit
- **Budget Alert** — a project is over budget (admin only)
- **Overdue Milestone** — a milestone is past its due date (admin only)
- **Status Update Due** — a project hasn't had a status update recently (admin only)
- **Allocation Ending** — an allocation is ending soon

Each item has a severity badge (High/Medium/Low) and a **Go** button that navigates to the relevant page.

### Notification Bell
The bell icon in the sidebar shows unread notifications:
- @mentions in WBS comments
- Health monitor alerts
- System notifications
- Click a notification to mark it as read
- Use **Mark all read** to clear all

---

## 16. Time Off & Holidays

### Leave Management
Navigate to **Time Off** to manage leave:
- **Admins** see all team leave with a Resource column
- **Resources** see only their own leave

To request time off:
1. Click **Add Leave**
2. Select dates, type (Annual, Sick, Personal, etc.), and add notes
3. Submit

Leave is automatically deducted from timesheet autofill calculations.

### Company Holidays
Navigate to **Holidays** to view and manage company-wide holidays.
- Holidays are excluded from business day calculations and timesheet autofill
- Admins can add/remove holidays

---

## 17. User Management

*Admin and Super Admin only.*

Navigate to **Users** to manage all accounts:

### Creating a User
1. Click **Create User**
2. Enter email, password, role
3. Optionally link to an existing resource record
4. The user receives a "must change password" prompt on first login

### Roles
| Role | Access Level |
|---|---|
| Super Admin | Everything — settings, integrations, all management |
| Admin | Project/resource management, reports, AI actions |
| Resource | Own dashboard, timesheets, allocations, read-only projects |
| Contractor | Same as Resource |
| Client | Read-only portal for assigned projects |

### Disabling a User
Click **Disable** on a user row. Their JWT sessions are immediately invalidated and they cannot log in until re-enabled.

### Deleting a User
Click **Delete** on a user row. Protected: you cannot delete your own account, and only Super Admins can modify Admin accounts.

---

## Tips & Best Practices

1. **Weekly Routine**: Submit timesheets every Friday. The dashboard will nudge you if you forget.
2. **Use AI Chat**: Instead of navigating through menus, ask the AI directly — it can create projects, assign resources, and generate reports.
3. **Set Up Custom AI Instructions**: Tailor the AI's behaviour per project for more relevant suggestions.
4. **Take Baselines**: Before major scope changes, snapshot the WBS so you can track variance later.
5. **Use Magic Links**: For client updates, generate a magic link instead of creating a client login.
6. **Check Action Items**: Start your day by reviewing the action items banner on the dashboard.
7. **Leverage Specialist Agents**: Use `@budget`, `@risk`, `@resource`, `@schedule` for focused analysis.
