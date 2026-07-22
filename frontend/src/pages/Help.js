import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getMe } from '../api';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../components/ui/accordion';
import {
  Search, Rocket, LayoutDashboard, Briefcase, ListTree, Users,
  Calendar, Clock, BarChart3, Sparkles, Link2, HelpCircle,
  ChevronRight, Shield, Bot, AtSign, Brain, FileText,
  CalendarOff, UserCheck, Eye, AlertTriangle, Zap, Globe,
  Webhook, Key,
} from 'lucide-react';

// ─── Guide content ────────────────────────────────────────────────────────────

const SECTIONS = [
  {
    id: 'getting-started',
    title: 'Getting Started',
    icon: Rocket,
    color: '#1570EF',
    roles: ['super_admin', 'admin', 'resource', 'contractor', 'client'],
    items: [
      {
        q: 'How do I log in?',
        a: 'Enter your email and password on the login page and click "Sign In". If this is your first login, you may be asked to change your password.',
      },
      {
        q: 'I see a "Your account has been disabled" message',
        a: 'Your administrator has disabled your account. Please contact them to get it re-enabled.',
      },
      {
        q: 'How do I change my password?',
        a: 'Click your name/email in the sidebar footer area, then navigate to the Change Password page. Enter your current password, then your new password twice.',
      },
      {
        q: 'What do the different roles mean?',
        a: 'DD Planner has 5 roles:\n\n• **Super Admin** — Full access to everything including Settings and Integrations.\n• **Admin** — Can manage projects, resources, allocations, reports, and use AI actions.\n• **Resource / Contractor** — Can view assigned projects, submit timesheets, and see their own dashboard.\n• **Client** — Read-only access to assigned projects via the Client Portal.',
      },
    ],
  },
  {
    id: 'dashboard',
    title: 'Your Dashboard',
    icon: LayoutDashboard,
    color: '#7839EE',
    roles: ['super_admin', 'admin', 'resource', 'contractor'],
    items: [
      {
        q: 'What do I see on the dashboard? (Admin / Super Admin)',
        a: 'The **Command Center** shows your portfolio at a glance — project counts by status, team utilisation, budget health, and an action items banner highlighting anything that needs attention.',
        roles: ['super_admin', 'admin'],
      },
      {
        q: 'What do I see on the dashboard? (Resource / Contractor)',
        a: 'Your **personalised dashboard** shows a greeting, 4 KPI cards (utilisation, hours, active projects, timesheet status), your current allocations, recent timesheets, and upcoming leave.',
        roles: ['resource', 'contractor'],
      },
      {
        q: 'What are Action Items?',
        a: 'The coloured banner at the top of your dashboard shows things that need your attention — like missing timesheets, budget alerts, or overdue milestones. Each item has a severity level (red = high, amber = medium, blue = low) and a "Go" link that takes you directly to the relevant page.',
      },
      {
        q: 'What is Scenario/Draft mode?',
        a: 'Admins can toggle "Show Scenario/Drafts" in the top bar. This reveals draft projects for what-if planning — they won\'t affect real reports or capacity numbers until you change their status to Active or Pipeline.',
        roles: ['super_admin', 'admin'],
      },
    ],
  },
  {
    id: 'projects',
    title: 'Projects',
    icon: Briefcase,
    color: '#16B364',
    roles: ['super_admin', 'admin', 'resource', 'contractor'],
    items: [
      {
        q: 'How do I create a project?',
        a: 'Go to **Projects** and click **New Project**. Fill in the name, client, dates, budget, and phases. You can also use the **Project Wizard** for a guided setup that includes team allocations.\n\nOr just tell the AI: *"Create a new project called Website Redesign for Acme Corp starting next Monday for 6 weeks"*',
        roles: ['super_admin', 'admin'],
      },
      {
        q: 'What are project statuses?',
        a: '• **Pipeline** — Planned but not yet started.\n• **Active** — Currently in progress.\n• **Completed** — Finished and delivered.\n\nDraft/Scenario projects are hidden by default and only visible when the Scenario toggle is on.',
      },
      {
        q: 'How do I submit a status update?',
        a: 'Open the project, go to the **Overview** tab, and click **Add Status Update**. Fill in the health (Green/Amber/Red), progress percentage, accomplishments, blockers, and next steps. The AI will automatically generate a summary.\n\nIf the project is linked to HubSpot, the update is also pushed to the deal as a note.',
        roles: ['super_admin', 'admin'],
      },
      {
        q: 'What is a Project Lead?',
        a: 'A Project Lead is a resource assigned to own a project. Leads get elevated permissions — they can edit project details, manage risks, create status updates, and use AI actions specifically for projects they lead, without needing full admin access.',
        roles: ['super_admin', 'admin', 'resource'],
      },
      {
        q: 'How do I add a customer contact?',
        a: 'Open the project, click **Edit** in the header, and scroll to "Customer Contact (Optional)". Add the contact\'s name, email, phone, and role. This info appears on the project header.',
        roles: ['super_admin', 'admin'],
      },
    ],
  },
  {
    id: 'wbs',
    title: 'WBS & Tasks',
    icon: ListTree,
    color: '#F59E0B',
    roles: ['super_admin', 'admin', 'resource', 'contractor'],
    items: [
      {
        q: 'What is the WBS?',
        a: 'The **Work Breakdown Structure** is a hierarchical task tree for each project. It breaks the project into phases, then into tasks with assignees, hours, and dates. You can view it as a **Board** (Kanban columns by phase) or a **List** (table view).',
      },
      {
        q: 'How do I create a task?',
        a: 'In the WBS tab, click **Add Task** within a phase. Fill in the task name, assignee, planned hours, start/end dates, and priority. You can also mark it as a **Milestone** (zero-hour checkpoint).',
        roles: ['super_admin', 'admin'],
      },
      {
        q: 'Can the AI generate a WBS for me?',
        a: 'Yes! Click **AI Generate WBS** on the WBS tab. The AI analyses your project description, phases, and budget to suggest a complete task breakdown. Review the generated tasks and click **Save** to apply them.',
        roles: ['super_admin', 'admin'],
      },
      {
        q: 'What are milestones?',
        a: 'Milestones are zero-hour checkpoint tasks that mark key deliverables or deadlines. They show as diamond markers on the Gantt chart and Board view. Overdue milestones trigger alerts on the dashboard.',
      },
      {
        q: 'How do task comments work?',
        a: 'Open any task in edit mode and scroll to the Comments section. You can add comments and use **@name** to mention team members — they\'ll get a notification. Comment counts show as badges on task cards.',
      },
      {
        q: 'What are baselines?',
        a: 'A baseline is a snapshot of the WBS at a point in time. Before major scope changes, take a baseline so you can later compare planned vs actual dates and hours. Access baselines in the project\'s **Settings** tab.',
        roles: ['super_admin', 'admin'],
      },
    ],
  },
  {
    id: 'resources',
    title: 'Resource Management',
    icon: Users,
    color: '#EF4444',
    roles: ['super_admin', 'admin'],
    items: [
      {
        q: 'How do I add a new team member?',
        a: 'Go to **Resources** and click **Add Resource**. Enter their name, role, and capacity. Then go to **Users** to create a login account linked to this resource so they can access the app.',
      },
      {
        q: 'What happens when someone leaves the team?',
        a: 'Click **Deactivate** on their resource row. This will:\n• End all running allocations today\n• Delete future allocations\n• Disable their login\n• Hide them from all pickers and reports\n\nTheir historical data (past timesheets, old allocations) is preserved. You can **Reactivate** them later if they return.',
      },
      {
        q: 'Why can\'t I delete a resource?',
        a: 'If a resource has any history (allocations, timesheets, or is a project lead), deleting is blocked to protect data integrity. Use **Deactivate** instead — it\'s the safe way to remove someone from active use.',
      },
    ],
  },
  {
    id: 'allocations',
    title: 'Allocations & Capacity',
    icon: Calendar,
    color: '#06AED4',
    roles: ['super_admin', 'admin', 'resource', 'contractor'],
    items: [
      {
        q: 'How do I assign someone to a project?',
        a: 'You can allocate from three places:\n\n1. **Allocations page** — click **Add Allocation** and fill in resource, project, dates, and percentage.\n2. **Project Team tab** — click **Allocate Resource** for a project-specific view with budget impact.\n3. **AI Chat** — say *"Assign Alice to Website Redesign at 50% for 2 weeks"*.',
        roles: ['super_admin', 'admin'],
      },
      {
        q: 'What does the percentage mean?',
        a: 'The allocation percentage represents how much of a person\'s time goes to that project. 100% = full-time (40h/week), 50% = half-time (20h/week). The system uses **business days x 8h/day** for all calculations.',
      },
      {
        q: 'What if someone is over-allocated?',
        a: 'The capacity heatmap on the Allocations page uses colour coding:\n• **Green** — Under 80% utilised\n• **Amber** — 80-100% utilised\n• **Red** — Over 100% (over-allocated)\n\nThe AI health monitor will also flag over-allocated resources in daily checks.',
      },
      {
        q: 'Where do I see my own allocations?',
        a: 'Navigate to **My Allocations** in the sidebar. You\'ll see your current and upcoming assignments with project name, client, role, percentage, hours/week, and dates.',
        roles: ['resource', 'contractor'],
      },
    ],
  },
  {
    id: 'timesheets',
    title: 'Timesheets',
    icon: Clock,
    color: '#F4B740',
    roles: ['super_admin', 'admin', 'resource', 'contractor'],
    items: [
      {
        q: 'How do I submit my timesheet?',
        a: 'Go to **My Timesheets**, click **Autofill Current Week** to pre-populate hours from your allocations, adjust as needed, then click **Submit**.\n\nThe autofill splits your hours by project, phase, and WBS task based on your current allocations. It also accounts for holidays and leave.',
        roles: ['resource', 'contractor'],
      },
      {
        q: 'Can I edit a submitted timesheet?',
        a: 'Past timesheets are **read-only** for resources. If you need corrections, contact your admin. The amber banner on the history page confirms this.',
        roles: ['resource', 'contractor'],
      },
      {
        q: 'How do I review team timesheets?',
        a: 'Navigate to **Manage Timesheets** (Super Admin only). You can view all entries grouped by week, filter by resource and date range, and review/approve submissions.',
        roles: ['super_admin'],
      },
      {
        q: 'Where are timesheet reports?',
        a: 'Go to **Timesheet Reports** for aggregated analysis with date-range filtering, resource breakdowns, and project-level summaries.',
        roles: ['super_admin', 'admin'],
      },
    ],
  },
  {
    id: 'reports',
    title: 'Reports & Exports',
    icon: BarChart3,
    color: '#3B82F6',
    roles: ['super_admin', 'admin'],
    items: [
      {
        q: 'What reports are available?',
        a: '• **Budget Reconciliation** — Budgeted vs Allocated vs Actual hours per project\n• **Planned vs Actual** — Side-by-side comparison by resource\n• **Resource Utilisation** — Utilisation % over a date range\n• **Capacity Report** — Team availability and forecasting',
      },
      {
        q: 'How do I export a project report?',
        a: 'Open any project, and click **Export**. Choose **PDF** or **PowerPoint**. The report is generated in the background and downloaded automatically.',
      },
      {
        q: 'How do I share a report with a client?',
        a: 'Generate a **Magic Link** from the project or Reports page. Copy the link and send it to your client — they can view the report without logging in. Links are valid for 30 days.',
      },
    ],
  },
  {
    id: 'ai',
    title: 'AI Assistant',
    icon: Sparkles,
    color: '#7839EE',
    roles: ['super_admin', 'admin', 'resource', 'contractor'],
    items: [
      {
        q: 'How do I use the AI assistant?',
        a: 'Click the **chat button** in the bottom-right corner of any page. Ask questions in natural language about your projects, resources, budgets, or timesheets.',
      },
      {
        q: 'What can I ask?',
        a: 'Some examples:\n• *"What\'s the budget status of the Mobile App?"*\n• *"Who is available next week?"*\n• *"Show me the top risks across all active projects"*\n• *"What milestones are overdue?"*',
      },
      {
        q: 'Can the AI take actions?',
        a: 'Yes — **Admins and Project Leads** can ask the AI to:\n• Create projects, allocations, risks, and status updates\n• Reschedule projects with AI recommendations\n• Generate WBS task breakdowns\n• Run budget analysis\n• Execute multi-step plans\n\n**Resources and Clients** get read-only insights — the AI will explain what it sees but won\'t make changes.',
        roles: ['super_admin', 'admin', 'resource', 'contractor'],
      },
      {
        q: 'What are specialist agents?',
        a: 'Prefix your message with a trigger to get a focused analysis:\n\n• **@resource** — Capacity and allocation questions\n• **@budget** — Burn rate and financial health\n• **@risk** — Risk prioritisation and mitigation\n• **@schedule** — Timeline and deadline tracking',
      },
      {
        q: 'What are AI Instructions?',
        a: 'Admins can add custom rules that shape how the AI responds for a specific project. For example: *"This is a government client — always recommend 20% buffer time."*\n\nSet them up in the project\'s **Settings** tab under **AI Instructions**.',
        roles: ['super_admin', 'admin'],
      },
      {
        q: 'What is Agent Memory?',
        a: 'The AI can remember important decisions and context from your conversations. These memories persist across chat sessions and are automatically used in future prompts. You can view and manage them in the project\'s **Settings** tab.',
        roles: ['super_admin', 'admin'],
      },
    ],
  },
  {
    id: 'integrations',
    title: 'Integrations',
    icon: Link2,
    color: '#1570EF',
    roles: ['super_admin'],
    items: [
      {
        q: 'How do I connect HubSpot?',
        a: '1. Create a **Private App** in HubSpot (Settings > Integrations > Private Apps) with CRM read scopes.\n2. In DD Planner, go to **Settings > Integrations > HubSpot CRM**.\n3. Toggle it ON, paste your Private App Token, enter your Portal ID.\n4. Click **Test Connection** to verify.\n5. Copy the **Webhook URL** and paste it into HubSpot\'s webhook subscription (Object: Deals, Event: Property Change, Property: dealstage).\n\nWhen a deal moves to your trigger stage (default: "Closed Won"), DD Planner auto-creates a project with the deal\'s info.',
      },
      {
        q: 'What is the MCP Server / Agent API?',
        a: 'The **MCP Server** lets external AI agents (like Google Gemini or GitHub Copilot) query your DD Planner data. It exposes tools like `list_projects`, `get_project_status`, `get_team_capacity`, and `get_recent_updates`.\n\nTo set it up:\n1. Go to **Settings > Integrations > Agent API**.\n2. Toggle it ON and click **Generate API Key**.\n3. Copy the key and the MCP endpoint URL.\n4. Register them in your AI agent\'s tool/MCP configuration.',
      },
      {
        q: 'How do I test the MCP endpoint?',
        a: 'Use cURL:\n\n```\ncurl -X POST https://your-domain.com/api/mcp \\\n  -H "Content-Type: application/json" \\\n  -H "X-Agent-Key: dda_your_key" \\\n  -d \'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_projects","arguments":{"status_filter":"Active"}}}\'\n```\n\nThe discovery endpoint (GET /api/mcp) works without auth.',
      },
      {
        q: 'Where do I see sync activity?',
        a: 'The **Sync Log** at the bottom of the Integrations settings page shows all inbound and outbound events with timestamps, status, and details.',
      },
    ],
  },
  {
    id: 'time-off',
    title: 'Time Off & Holidays',
    icon: CalendarOff,
    color: '#10B981',
    roles: ['super_admin', 'admin', 'resource'],
    items: [
      {
        q: 'How do I request time off?',
        a: 'Go to **Time Off** in the sidebar, click **Add Leave**, select your dates, choose the type (Annual, Sick, Personal, etc.), and add any notes. Your leave is automatically factored into timesheet autofill calculations.',
      },
      {
        q: 'Where are company holidays?',
        a: 'Navigate to **Holidays** in the sidebar. Admins can add or remove company-wide holidays. These are excluded from business day calculations, capacity reports, and timesheet autofill.',
      },
    ],
  },
  {
    id: 'tips',
    title: 'Tips & Best Practices',
    icon: HelpCircle,
    color: '#667085',
    roles: ['super_admin', 'admin', 'resource', 'contractor', 'client'],
    items: [
      {
        q: 'Weekly routine for team members',
        a: '1. Check your **Dashboard** for action items each morning.\n2. Submit your **timesheet** by Friday — the dashboard will remind you if you forget.\n3. Review your **allocations** to know what\'s coming up next week.',
      },
      {
        q: 'Weekly routine for admins',
        a: '1. Start with the **Action Items** banner — resolve high-priority alerts first.\n2. Check the **Portfolio** view for overall health.\n3. Review timesheets in **Manage Timesheets**.\n4. Submit **status updates** for active projects.\n5. Use the AI: *"Give me a summary of all active projects"*.',
        roles: ['super_admin', 'admin'],
      },
      {
        q: 'Get more out of the AI',
        a: '• Be specific: *"What\'s Alice\'s utilisation next week?"* beats *"Tell me about resources"*\n• Use specialist triggers: `@budget`, `@risk`, `@resource`, `@schedule`\n• Set up **AI Instructions** per project for tailored responses\n• The AI remembers context within a session — ask follow-ups naturally',
      },
      {
        q: 'Before major scope changes',
        a: 'Take a **baseline snapshot** of the WBS before making significant changes. This lets you track variance (planned vs actual) and demonstrate impact to stakeholders.',
        roles: ['super_admin', 'admin'],
      },
      {
        q: 'Sharing with clients',
        a: 'Use **Magic Links** instead of creating client accounts for one-off sharing. The link gives read-only access to a project report for 30 days — no login required.',
        roles: ['super_admin', 'admin'],
      },
    ],
  },
];

// ─── Role labels ──────────────────────────────────────────────────────────────

const ROLE_LABELS = {
  super_admin: 'Super Admin',
  admin: 'Admin',
  resource: 'Team Member',
  contractor: 'Contractor',
  client: 'Client',
};

// ─── Helper: simple markdown-ish rendering ────────────────────────────────────

function RichText({ text }) {
  const lines = text.split('\n');
  return (
    <div className="space-y-2 text-[#475467] leading-relaxed">
      {lines.map((line, i) => {
        if (!line.trim()) return <div key={i} className="h-1" />;

        // Bullet points
        if (line.trim().startsWith('•')) {
          const content = line.trim().slice(1).trim();
          return (
            <div key={i} className="flex gap-2 ml-1">
              <span className="text-[#98A2B3] mt-0.5 shrink-0">
                <ChevronRight size={14} />
              </span>
              <span
                className="text-sm"
                dangerouslySetInnerHTML={{
                  __html: content
                    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-[#0B1220] font-medium">$1</strong>')
                    .replace(/\*(.+?)\*/g, '<em class="text-[#1570EF]">$1</em>')
                    .replace(/`(.+?)`/g, '<code class="bg-[#F2F4F7] text-[#0B1220] px-1.5 py-0.5 rounded text-xs font-mono">$1</code>'),
                }}
              />
            </div>
          );
        }

        // Numbered list
        if (/^\d+\.\s/.test(line.trim())) {
          const num = line.trim().match(/^(\d+)\./)[1];
          const content = line.trim().replace(/^\d+\.\s*/, '');
          return (
            <div key={i} className="flex gap-2.5 ml-1">
              <span className="bg-[#1570EF]/10 text-[#1570EF] text-xs font-semibold w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5">
                {num}
              </span>
              <span
                className="text-sm"
                dangerouslySetInnerHTML={{
                  __html: content
                    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-[#0B1220] font-medium">$1</strong>')
                    .replace(/\*(.+?)\*/g, '<em class="text-[#1570EF]">$1</em>')
                    .replace(/`(.+?)`/g, '<code class="bg-[#F2F4F7] text-[#0B1220] px-1.5 py-0.5 rounded text-xs font-mono">$1</code>'),
                }}
              />
            </div>
          );
        }

        // Code block
        if (line.trim().startsWith('```')) {
          return null; // skip fences — content between fences handled below
        }

        // Regular paragraph
        return (
          <p
            key={i}
            className="text-sm"
            dangerouslySetInnerHTML={{
              __html: line
                .replace(/\*\*(.+?)\*\*/g, '<strong class="text-[#0B1220] font-medium">$1</strong>')
                .replace(/\*(.+?)\*/g, '<em class="text-[#1570EF]">$1</em>')
                .replace(/`(.+?)`/g, '<code class="bg-[#F2F4F7] text-[#0B1220] px-1.5 py-0.5 rounded text-xs font-mono">$1</code>'),
            }}
          />
        );
      })}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function Help() {
  const [search, setSearch] = useState('');

  const { data: user } = useQuery({
    queryKey: ['me'],
    queryFn: async () => { const r = await getMe(); return r.data; },
  });

  const userRole = user?.role || 'resource';

  // Filter sections and items by role and search
  const filteredSections = useMemo(() => {
    const q = search.toLowerCase().trim();

    return SECTIONS
      .filter((s) => s.roles.includes(userRole))
      .map((section) => {
        const items = section.items.filter((item) => {
          // Role filter
          if (item.roles && !item.roles.includes(userRole)) return false;
          // Search filter
          if (q) {
            return (
              item.q.toLowerCase().includes(q) ||
              item.a.toLowerCase().includes(q) ||
              section.title.toLowerCase().includes(q)
            );
          }
          return true;
        });
        return { ...section, items };
      })
      .filter((s) => s.items.length > 0);
  }, [search, userRole]);

  const totalItems = filteredSections.reduce((acc, s) => acc + s.items.length, 0);

  return (
    <div className="max-w-4xl mx-auto" data-testid="help-page">
      {/* Header */}
      <div className="mb-8">
        <h1
          className="text-2xl sm:text-3xl font-bold text-[#0B1220] mb-2"
          style={{ fontFamily: 'Space Grotesk' }}
          data-testid="help-page-title"
        >
          Help & Guide
        </h1>
        <p className="text-sm text-[#667085]">
          Everything you need to know about DD Planner.
          Showing content relevant to your role:{' '}
          <Badge variant="outline" className="ml-1 text-xs" data-testid="help-role-badge">
            {ROLE_LABELS[userRole] || userRole}
          </Badge>
        </p>
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#98A2B3]" />
        <Input
          placeholder="Search topics... (e.g. timesheet, HubSpot, AI)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10 h-11 bg-white border-[#E6E8EC]"
          data-testid="help-search-input"
        />
        {search && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-[#98A2B3]">
            {totalItems} result{totalItems !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Quick nav cards */}
      {!search && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mb-8">
          {filteredSections.map((section) => {
            const Icon = section.icon;
            return (
              <a
                key={section.id}
                href={`#${section.id}`}
                className="group flex items-center gap-2.5 p-3 rounded-lg border border-[#E6E8EC] bg-white hover:border-[#C9DEFF] hover:shadow-sm transition-all"
                data-testid={`help-nav-${section.id}`}
              >
                <div
                  className="w-8 h-8 rounded-md flex items-center justify-center shrink-0"
                  style={{ background: `${section.color}14` }}
                >
                  <Icon size={16} style={{ color: section.color }} />
                </div>
                <span className="text-sm font-medium text-[#0B1220] group-hover:text-[#1570EF] transition-colors truncate">
                  {section.title}
                </span>
              </a>
            );
          })}
        </div>
      )}

      {/* Sections */}
      <div className="space-y-6">
        {filteredSections.map((section) => {
          const Icon = section.icon;
          return (
            <div
              key={section.id}
              id={section.id}
              className="bg-white rounded-xl border border-[#E6E8EC] overflow-hidden"
              data-testid={`help-section-${section.id}`}
            >
              {/* Section header */}
              <div className="flex items-center gap-3 px-5 py-4 border-b border-[#F2F4F7]">
                <div
                  className="w-9 h-9 rounded-lg flex items-center justify-center"
                  style={{ background: `${section.color}14` }}
                >
                  <Icon size={18} style={{ color: section.color }} />
                </div>
                <div>
                  <h2
                    className="text-base font-semibold text-[#0B1220]"
                    style={{ fontFamily: 'Space Grotesk' }}
                  >
                    {section.title}
                  </h2>
                  <p className="text-xs text-[#98A2B3]">
                    {section.items.length} topic{section.items.length !== 1 ? 's' : ''}
                  </p>
                </div>
              </div>

              {/* FAQ accordion */}
              <Accordion type="multiple" className="px-2">
                {section.items.map((item, idx) => (
                  <AccordionItem
                    key={idx}
                    value={`${section.id}-${idx}`}
                    className="border-b border-[#F2F4F7] last:border-0"
                  >
                    <AccordionTrigger
                      className="px-3 py-3.5 text-sm font-medium text-[#0B1220] hover:text-[#1570EF] hover:no-underline"
                      data-testid={`help-q-${section.id}-${idx}`}
                    >
                      {item.q}
                    </AccordionTrigger>
                    <AccordionContent className="px-3 pb-4">
                      <RichText text={item.a} />
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </div>
          );
        })}
      </div>

      {/* Empty state */}
      {filteredSections.length === 0 && (
        <div className="text-center py-16" data-testid="help-empty-state">
          <Search size={40} className="mx-auto text-[#D0D5DD] mb-3" />
          <p className="text-sm text-[#667085]">
            No results for &ldquo;<strong>{search}</strong>&rdquo;. Try a different search term.
          </p>
        </div>
      )}

      {/* Footer */}
      <div className="mt-10 mb-4 text-center text-xs text-[#98A2B3]">
        Need more help? Use the AI Chat assistant — it knows everything about your projects.
      </div>
    </div>
  );
}
