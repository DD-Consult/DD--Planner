# DD Planner — Integrations Setup Guide

This guide covers how to set up and configure external integrations for DD Planner. All integration configuration is managed from **Settings > Integrations** (accessible to Super Admin users only).

---

## Table of Contents

1. [HubSpot CRM Integration](#1-hubspot-crm-integration)
2. [MCP Server (AI Agent API)](#2-mcp-server-ai-agent-api)
3. [Email Notifications (Resend)](#3-email-notifications-resend)
4. [Troubleshooting](#4-troubleshooting)

---

## 1. HubSpot CRM Integration

DD Planner integrates with HubSpot CRM bi-directionally:
- **Inbound**: When a deal reaches a trigger stage in HubSpot (e.g., "Closed Won"), a project is automatically created in DD Planner.
- **Outbound**: When a status update is submitted on a HubSpot-linked project, a note is pushed to the deal in HubSpot.

### Prerequisites
- A HubSpot account (any tier — Free, Starter, Professional, or Enterprise)
- A HubSpot **Private App** with the required scopes

### Step 1: Create a HubSpot Private App

1. Log in to your HubSpot account
2. Go to **Settings** (gear icon in the top nav)
3. Navigate to **Integrations > Private Apps**
4. Click **Create a private app**
5. Give it a name (e.g., "DD Planner Sync")
6. Under the **Scopes** tab, enable the following:
   - `crm.objects.deals.read` — Read deals
   - `crm.objects.companies.read` — Read company names
   - `crm.objects.contacts.read` — Read contact details
   - `crm.objects.owners.read` — Test connection
   - `crm.objects.deals.write` — (Optional) For future write-back
   - `crm.schemas.deals.read` — Read deal properties
   - `sales-email-read` — (Optional) For engagement creation
7. Click **Create app**
8. **Copy the access token** — you will need it in the next step

### Step 2: Configure in DD Planner

1. Log in to DD Planner as a **Super Admin**
2. Navigate to **Settings** (sidebar)
3. Scroll down to **Integrations**
4. In the **HubSpot CRM** card:
   - Toggle **Enabled** to ON
   - Paste your **Private App Token** from Step 1
   - Enter your **Portal ID** (found in HubSpot under Settings > Account Defaults, or in your URL: `app.hubspot.com/contacts/{PORTAL_ID}`)
   - Set the **Trigger Stage** (default: `closedwon`) — this is the deal stage that triggers project creation
   - Set the **Default Project Status** for newly created projects (default: `Pipeline`)
   - Toggle **Sync Status Updates** to ON if you want status updates pushed back to HubSpot
5. Click **Save**
6. Click **Test Connection** — you should see "Connected — portal owner: your-email@company.com"

### Step 3: Set Up the HubSpot Webhook

To receive real-time deal events from HubSpot, configure a webhook subscription:

1. In the DD Planner **Integrations** settings, copy the **Webhook URL** (shown below the HubSpot configuration). It will look like:
   ```
   https://your-domain.com/api/integrations/hubspot/webhook
   ```

2. In HubSpot, go to **Settings > Integrations > Private Apps**
3. Select your private app
4. Go to the **Webhooks** tab
5. Click **Create subscription**
6. Configure:
   - **Object type**: Deals
   - **Event type**: Property change
   - **Property**: Deal Stage (`dealstage`)
7. Enter the **Target URL** from step 1
8. Save the subscription

### How It Works

**Inbound Flow (HubSpot → DD Planner):**
```
HubSpot Deal stage changes to "Closed Won"
    ↓
HubSpot sends webhook to /api/integrations/hubspot/webhook
    ↓
DD Planner fetches full deal details (name, amount, dates)
    ↓
Resolves associated company name and primary contact
    ↓
Creates a new project with mapped fields:
  - Deal Name → Project Name
  - Amount → Budget Value
  - Close Date → End Date
  - Company → Client Name
  - Contact → Main Contact (name, email, phone, role)
    ↓
Event logged in Sync Log
```

**Outbound Flow (DD Planner → HubSpot):**
```
Admin submits a status update on a project
    ↓
If project has a linked HubSpot deal ID
    AND sync_status_updates is enabled
    ↓
DD Planner pushes a formatted note to the HubSpot deal
  (health, progress, accomplishments, blockers, next steps)
    ↓
Event logged in Sync Log
```

### Field Mapping Reference

| HubSpot Deal Field | DD Planner Project Field |
|---|---|
| `dealname` | `name` |
| `amount` | `budget_value` |
| `createdate` | `start_date` |
| `closedate` | `end_date` |
| `description` | `description` |
| Associated Company name | `client_name` |
| Associated Contact | `main_contact_name`, `main_contact_email`, `main_contact_phone`, `main_contact_role` |

### Sync Log

All inbound and outbound events are logged and viewable in the **Sync Log** section at the bottom of the Integrations settings page. Each log entry shows:
- Direction (Inbound / Outbound)
- Event type
- Status (Success / Error / Skipped)
- Detail message
- Timestamp

---

## 2. MCP Server (AI Agent API)

DD Planner can act as an **MCP (Model Context Protocol) Server**, allowing external AI agents (such as Google Gemini, GitHub Copilot, or any MCP-compatible client) to query your project data programmatically.

### What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io/) is an open standard that allows AI models to discover and use external tools. DD Planner implements the MCP JSON-RPC 2.0 specification over HTTP, exposing your project data as tools that any compatible AI can call.

### Available Tools

| Tool | Description |
|---|---|
| `list_projects` | List all projects with health, progress, and status. Optional filter by status (Active/Pipeline/Completed/All). |
| `get_project_status` | Get full status details for a project — health, team, latest update, risks. Search by name or ID. |
| `get_team_capacity` | Current team utilisation — who is over-allocated, available, or on the bench. |
| `get_recent_updates` | Recent status updates across all projects (or filtered by project). Configurable lookback period. |

### Step 1: Enable and Generate an API Key

1. Log in as **Super Admin**
2. Go to **Settings > Integrations**
3. In the **Agent API (MCP)** card:
   - Toggle **Enabled** to ON
   - Click **Generate API Key**
   - **Copy the key immediately** — it will not be shown in full again
   - The key format is `dda_` followed by a 48-character hex string
4. Click **Save**

### Step 2: Configure Your AI Agent

#### Discovery Endpoint (No Auth)
Your AI agent can discover available tools by calling:
```
GET https://your-domain.com/api/mcp
```

This returns the server manifest with capabilities and tool definitions. No authentication required.

#### JSON-RPC Endpoint (Requires Auth)
All tool calls go through:
```
POST https://your-domain.com/api/mcp
Header: X-Agent-Key: dda_your_key_here
Content-Type: application/json
```

### Step 3: Example Requests

#### Initialize (handshake)
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {}
}
```

#### List available tools
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

#### Call a tool — List all active projects
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "list_projects",
    "arguments": {
      "status_filter": "Active"
    }
  }
}
```

#### Call a tool — Get project status by name
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "get_project_status",
    "arguments": {
      "project_name": "Website Redesign"
    }
  }
}
```

#### Call a tool — Get team capacity
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "get_team_capacity",
    "arguments": {}
  }
}
```

#### Call a tool — Get recent updates (last 7 days)
```json
{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "tools/call",
  "params": {
    "name": "get_recent_updates",
    "arguments": {
      "days": 7
    }
  }
}
```

### Testing with cURL

```bash
# Discovery (no auth needed)
curl https://your-domain.com/api/mcp

# List active projects
curl -X POST https://your-domain.com/api/mcp \
  -H "Content-Type: application/json" \
  -H "X-Agent-Key: dda_your_key_here" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "list_projects",
      "arguments": {"status_filter": "Active"}
    }
  }'
```

### Connecting to Google Gemini

To use DD Planner as a tool source for Gemini:

1. In **Google AI Studio** or your Gemini integration:
   - Register the MCP endpoint URL: `https://your-domain.com/api/mcp`
   - Set the authentication header: `X-Agent-Key: dda_your_key_here`
2. Gemini will call `GET /api/mcp` to discover available tools
3. When a user asks about project status, team capacity, etc., Gemini will call `POST /api/mcp` with the appropriate tool

### Connecting to VS Code / Copilot

If your MCP client supports HTTP-based MCP servers:
1. Add the MCP server URL: `https://your-domain.com/api/mcp`
2. Configure the `X-Agent-Key` header in your MCP client settings
3. The tools will appear in your AI assistant's available tools

### Rotating the API Key

If you suspect the key has been compromised:
1. Go to **Settings > Integrations > Agent API**
2. Click **Regenerate Key**
3. Copy the new key and update all connected agents
4. The old key is immediately invalidated

---

## 3. Email Notifications (Resend)

DD Planner uses [Resend](https://resend.com) for sending emails (magic link invitations, notification digests).

### Step 1: Create a Resend Account

1. Go to [resend.com](https://resend.com) and sign up
2. Verify your email domain (or use their sandbox domain for testing)
3. Navigate to **API Keys** and create a new API key

### Step 2: Configure Environment Variable

Add the following to your `backend/.env` file:

```
RESEND_API_KEY=re_your_api_key_here
SENDER_EMAIL=notifications@yourdomain.com
```

- `RESEND_API_KEY` — Your Resend API key
- `SENDER_EMAIL` — The "from" address for emails. Must be a verified domain in Resend, or use `onboarding@resend.dev` for testing.

### Step 3: Restart the Backend

After updating the `.env` file, restart the backend service for the changes to take effect.

### What Emails are Sent?

| Email Type | Trigger | Content |
|---|---|---|
| Client Magic Link | Admin generates a magic link for a project | Link to access project report (30-day expiry) |
| Notifications | Triggered by admin or system | Action items, reminders, alerts |

---

## 4. Troubleshooting

### HubSpot

| Issue | Solution |
|---|---|
| "Test Connection" fails | Verify your Private App Token has the correct scopes. Check that the token hasn't expired. |
| Webhook not triggering | Verify the webhook URL is correct and publicly accessible. Check HubSpot's webhook logs for delivery status. Ensure the subscription is for `dealstage` property changes. |
| Project not created on deal close | Check the trigger stage matches your HubSpot pipeline's "Closed Won" stage ID. View the Sync Log for error details. |
| Duplicate projects | DD Planner checks for existing `hubspot_deal_id` before creating. If a project already exists for a deal, it's skipped (logged as "skipped" in Sync Log). |
| Status update not pushed | Verify `Sync Status Updates` is toggled ON. Check that the project has a `hubspot_deal_id` (only HubSpot-sourced projects get outbound sync). View Sync Log for errors. |

### MCP Server

| Issue | Solution |
|---|---|
| 401 "Missing X-Agent-Key" | Include the `X-Agent-Key` header in your POST request. GET requests to `/api/mcp` don't require auth. |
| 401 "Invalid agent API key" | Verify the key matches. Keys are case-sensitive. Check if it was rotated. |
| 403 "Agent API is disabled" | Go to Settings > Integrations and toggle Agent API to ON. |
| Tool returns empty results | Verify you have projects in the database. Check the `status_filter` parameter. |
| Discovery works but tool calls fail | Discovery (GET) doesn't require auth. Tool calls (POST) require a valid `X-Agent-Key`. |

### Resend Email

| Issue | Solution |
|---|---|
| Emails not sending | Verify `RESEND_API_KEY` is set in `backend/.env`. Restart the backend after adding it. |
| "Sender address not verified" | Use a domain verified in Resend, or use `onboarding@resend.dev` for testing. |
| Magic link email not received | Check spam folders. Verify the recipient email is correct. Check backend logs for Resend API errors. |

### General

| Issue | Solution |
|---|---|
| Integration settings not loading | Ensure you're logged in as Super Admin. Other roles cannot access integration settings. |
| Sync Log empty | Events are only logged when integrations are actively used. Run a Test Connection to generate a log entry. |
| Settings not saving | Check browser console for errors. Ensure the backend is running and accessible. |

---

## Security Notes

1. **Private App Tokens** are stored encrypted in the database and never exposed in full via the API. The Settings UI shows a masked version.
2. **Agent API Keys** are generated server-side with cryptographic randomness. They are only shown in full once at generation time.
3. **Webhook endpoints** accept unauthenticated requests (required by HubSpot's architecture). They validate the integration is enabled and the token is configured before processing.
4. All integration events are **audit logged** in the Sync Log with timestamps, status, and detail messages.
5. **Key rotation** is available for both HubSpot tokens and Agent API keys. Rotating a key immediately invalidates the previous one.
