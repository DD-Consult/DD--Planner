import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import {
  getIntegrationSettings, updateIntegrationSettings,
  testHubSpotConnection, regenerateAgentApiKey, getIntegrationSyncLogs,
} from '../api';
import { toast } from 'sonner';
import {
  Loader2, CheckCircle2, XCircle, Copy, RefreshCw, Eye, EyeOff,
  Link2, Webhook, Bot, AlertTriangle, Clock, ChevronDown, ChevronUp,
  Zap, Globe,
} from 'lucide-react';

// ─── helpers ──────────────────────────────────────────────────────────────────

function CopyButton({ value, label = '' }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <Button type="button" variant="outline" size="sm" onClick={copy} className="shrink-0">
      {copied ? <CheckCircle2 size={14} className="text-green-600" /> : <Copy size={14} />}
      {label && <span className="ml-1 text-xs">{copied ? 'Copied!' : label}</span>}
    </Button>
  );
}

function SectionHeader({ icon: Icon, color, title, description, badge }) {
  return (
    <div className="flex items-center gap-3 mb-5">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center`} style={{ background: `${color}18` }}>
        <Icon size={20} style={{ color }} />
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <h3 className="text-base font-semibold" style={{ fontFamily: 'Space Grotesk' }}>{title}</h3>
          {badge && <span className="text-xs px-2 py-0.5 rounded-full bg-[#F2F7FF] text-[#1570EF] border border-[#C9DEFF]">{badge}</span>}
        </div>
        <p className="text-sm text-[#667085]">{description}</p>
      </div>
    </div>
  );
}

// ─── Sync log row ─────────────────────────────────────────────────────────────

function SyncLogRow({ log }) {
  const statusColor = log.status === 'success' ? 'text-green-600' : log.status === 'error' ? 'text-red-600' : 'text-amber-600';
  const directionColor = log.direction === 'inbound' ? '#1570EF' : '#7839EE';
  return (
    <div className="flex items-start gap-3 py-2 border-b border-[#F2F4F7] last:border-0 text-sm">
      <span className="text-xs font-mono rounded px-1.5 py-0.5 text-white shrink-0 mt-0.5"
        style={{ background: directionColor }}>
        {log.direction === 'inbound' ? '↓ IN' : '↑ OUT'}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-[#0B1220]">{log.event_type?.replace(/_/g, ' ')}</span>
          <span className={`text-xs ${statusColor}`}>{log.status}</span>
        </div>
        <p className="text-xs text-[#667085] truncate">{log.detail}</p>
      </div>
      <span className="text-xs text-[#98A2B3] shrink-0">{log.created_at ? new Date(log.created_at).toLocaleString() : ''}</span>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function IntegrationsSettings() {
  const qc = useQueryClient();

  // Fetch settings
  const { data: settings, isLoading } = useQuery({
    queryKey: ['integrationSettings'],
    queryFn: async () => { const r = await getIntegrationSettings(); return r.data; },
    staleTime: 0,
  });

  // Fetch sync logs
  const { data: syncLogs = [], refetch: refetchLogs } = useQuery({
    queryKey: ['integrationSyncLogs'],
    queryFn: async () => { const r = await getIntegrationSyncLogs(30); return r.data; },
  });

  // ── HubSpot state ────────────────────────────────────────────────────────
  const [hsEnabled, setHsEnabled] = useState(false);
  const [hsToken, setHsToken] = useState('');
  const [hsPortalId, setHsPortalId] = useState('');
  const [hsTriggerStage, setHsTriggerStage] = useState('closedwon');
  const [hsSyncUpdates, setHsSyncUpdates] = useState(true);
  const [hsDefaultStatus, setHsDefaultStatus] = useState('Pipeline');
  const [showToken, setShowToken] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [isTesting, setIsTesting] = useState(false);

  // ── Agent API state ───────────────────────────────────────────────────────
  const [agentEnabled, setAgentEnabled] = useState(false);
  const [newApiKey, setNewApiKey] = useState('');
  const [showLogs, setShowLogs] = useState(false);

  // Populate from fetched settings
  useEffect(() => {
    if (!settings) return;
    const hs = settings.hubspot || {};
    setHsEnabled(hs.enabled ?? false);
    setHsPortalId(hs.portal_id || '');
    setHsTriggerStage(hs.trigger_stage || 'closedwon');
    setHsSyncUpdates(hs.sync_status_updates ?? true);
    setHsDefaultStatus(hs.default_project_status || 'Pipeline');
    const agent = settings.agent_api || {};
    setAgentEnabled(agent.enabled ?? false);
  }, [settings]);

  // ── Save HubSpot settings ──────────────────────────────────────────────────
  const saveHsMutation = useMutation({
    mutationFn: () => updateIntegrationSettings({
      hubspot: {
        enabled: hsEnabled,
        private_app_token: hsToken || '',   // empty = keep existing
        portal_id: hsPortalId,
        trigger_stage: hsTriggerStage,
        sync_status_updates: hsSyncUpdates,
        default_project_status: hsDefaultStatus,
      },
    }),
    onSuccess: () => {
      toast.success('HubSpot settings saved');
      setHsToken('');
      qc.invalidateQueries(['integrationSettings']);
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Save failed'),
  });

  // ── Test HubSpot ───────────────────────────────────────────────────────────
  const handleTestHubSpot = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const r = await testHubSpotConnection(hsToken || undefined);
      setTestResult(r.data);
      refetchLogs();
    } catch (err) {
      setTestResult({ ok: false, message: err.response?.data?.detail || 'Request failed' });
    } finally {
      setIsTesting(false);
    }
  };

  // ── Save agent API settings ────────────────────────────────────────────────
  const saveAgentMutation = useMutation({
    mutationFn: () => updateIntegrationSettings({ agent_api: { enabled: agentEnabled } }),
    onSuccess: () => {
      toast.success('Agent API settings saved');
      qc.invalidateQueries(['integrationSettings']);
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Save failed'),
  });

  // ── Regenerate agent key ───────────────────────────────────────────────────
  const regenMutation = useMutation({
    mutationFn: regenerateAgentApiKey,
    onSuccess: (r) => {
      setNewApiKey(r.data.api_key);
      setAgentEnabled(true);
      qc.invalidateQueries(['integrationSettings']);
      toast.success('New API key generated — save it now!');
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to generate key'),
  });

  const backendUrl = process.env.REACT_APP_BACKEND_URL || window.location.origin;
  const mcpEndpoint = `${backendUrl}/api/mcp`;
  const webhookEndpoint = `${backendUrl}/api/integrations/hubspot/webhook`;

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-8 justify-center text-[#667085]">
        <Loader2 size={18} className="animate-spin" /><span className="text-sm">Loading integration settings...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">

      {/* ── HubSpot ── */}
      <div className="bg-white border border-[#E6E8EC] rounded-lg p-6" data-testid="hubspot-settings">
        <SectionHeader
          icon={Link2}
          color="#FF7A59"
          title="HubSpot CRM"
          description="Sync deals inbound as projects and push status updates back as deal notes"
          badge="Bi-directional"
        />

        {/* Enable toggle */}
        <div className="flex items-center justify-between p-3 bg-[#F9FAFB] rounded-lg border border-[#E6E8EC] mb-5">
          <div>
            <p className="text-sm font-medium text-[#0B1220]">Enable HubSpot Integration</p>
            <p className="text-xs text-[#667085]">Activates webhook listener and status update push</p>
          </div>
          <Switch checked={hsEnabled} onCheckedChange={setHsEnabled} data-testid="hubspot-enabled-toggle" />
        </div>

        <div className="space-y-4">
          {/* Private App Token */}
          <div>
            <Label htmlFor="hs-token">
              Private App Token
              {settings?.hubspot?.private_app_token === true && (
                <span className="ml-2 text-xs text-green-600 font-normal">(saved)</span>
              )}
            </Label>
            <div className="flex gap-2 mt-1">
              <div className="relative flex-1">
                <Input
                  id="hs-token"
                  type={showToken ? 'text' : 'password'}
                  value={hsToken}
                  onChange={(e) => setHsToken(e.target.value)}
                  placeholder={settings?.hubspot?.private_app_token === true ? '••••••••••••••••••••••• (saved — paste to replace)' : 'pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'}
                  className="pr-10"
                  data-testid="hubspot-token-input"
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#667085] hover:text-[#0B1220]"
                  onClick={() => setShowToken(!showToken)}
                >
                  {showToken ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleTestHubSpot}
                disabled={isTesting}
                data-testid="test-hubspot-btn"
              >
                {isTesting ? <Loader2 size={14} className="animate-spin mr-1" /> : <Zap size={14} className="mr-1" />}
                Test
              </Button>
            </div>
            <p className="text-xs text-[#667085] mt-1">
              Get it from <a href="https://app.hubspot.com/private-apps" target="_blank" rel="noopener noreferrer" className="text-[#1570EF] hover:underline">HubSpot → Settings → Private Apps</a>
            </p>
            {testResult && (
              <div className={`mt-2 flex items-center gap-2 text-sm ${testResult.ok ? 'text-green-700' : 'text-red-700'}`} data-testid="test-result">
                {testResult.ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                {testResult.message}
              </div>
            )}
          </div>

          {/* Portal ID */}
          <div>
            <Label htmlFor="hs-portal">Portal ID</Label>
            <Input
              id="hs-portal"
              value={hsPortalId}
              onChange={(e) => setHsPortalId(e.target.value)}
              placeholder="12345678"
              className="mt-1"
              data-testid="hubspot-portal-id"
            />
            <p className="text-xs text-[#667085] mt-1">Found in HubSpot URL: app.hubspot.com/contacts/<strong>PORTAL_ID</strong>/</p>
          </div>

          {/* Trigger stage + project defaults */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="hs-stage">Trigger Deal Stage</Label>
              <Input
                id="hs-stage"
                value={hsTriggerStage}
                onChange={(e) => setHsTriggerStage(e.target.value)}
                placeholder="closedwon"
                className="mt-1"
                data-testid="hubspot-trigger-stage"
              />
              <p className="text-xs text-[#667085] mt-1">Internal stage ID (e.g. closedwon)</p>
            </div>
            <div>
              <Label htmlFor="hs-status">Default Project Status</Label>
              <select
                id="hs-status"
                value={hsDefaultStatus}
                onChange={(e) => setHsDefaultStatus(e.target.value)}
                className="mt-1 w-full border border-[#E6E8EC] rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#1570EF]"
                data-testid="hubspot-default-status"
              >
                <option value="Pipeline">Pipeline</option>
                <option value="Active">Active</option>
              </select>
            </div>
          </div>

          {/* Sync status updates toggle */}
          <div className="flex items-center justify-between p-3 bg-[#F9FAFB] rounded-lg border border-[#E6E8EC]">
            <div>
              <p className="text-sm font-medium text-[#0B1220]">Push status updates to HubSpot</p>
              <p className="text-xs text-[#667085]">Creates a note on the linked deal when a status update is submitted</p>
            </div>
            <Switch checked={hsSyncUpdates} onCheckedChange={setHsSyncUpdates} data-testid="hs-sync-updates-toggle" />
          </div>

          {/* Webhook URL */}
          <div>
            <Label>Webhook URL</Label>
            <div className="flex gap-2 mt-1">
              <Input readOnly value={webhookEndpoint} className="font-mono text-xs bg-[#F9FAFB]" data-testid="webhook-url" />
              <CopyButton value={webhookEndpoint} label="Copy" />
            </div>
            <p className="text-xs text-[#667085] mt-1">
              Add this URL in HubSpot → Private App → Webhooks tab. Subscribe to <strong>Deal → propertyChange → dealstage</strong>
            </p>
          </div>

          {/* Field mapping reference */}
          <div className="border border-[#E6E8EC] rounded-lg overflow-hidden">
            <div className="bg-[#F9FAFB] px-4 py-2 text-xs font-semibold text-[#667085] uppercase tracking-wider">Field Mapping</div>
            <div className="divide-y divide-[#F2F4F7]">
              {[
                { hs: 'dealname', dd: 'Project Name' },
                { hs: 'amount', dd: 'Budget Value (£)' },
                { hs: 'closedate', dd: 'End Date' },
                { hs: 'createdate', dd: 'Start Date' },
                { hs: 'Company (associated)', dd: 'Client Name' },
                { hs: 'Contact name/email/phone', dd: 'Main Contact' },
              ].map(({ hs, dd }) => (
                <div key={hs} className="flex items-center px-4 py-2 text-sm">
                  <span className="font-mono text-xs text-[#667085] w-48">{hs}</span>
                  <span className="text-[#98A2B3] mr-3">→</span>
                  <span className="text-[#0B1220]">{dd}</span>
                </div>
              ))}
            </div>
          </div>

          <Button onClick={() => saveHsMutation.mutate()} disabled={saveHsMutation.isPending} data-testid="save-hubspot-btn">
            {saveHsMutation.isPending ? <><Loader2 size={14} className="mr-2 animate-spin" />Saving...</> : 'Save HubSpot Settings'}
          </Button>
        </div>
      </div>

      {/* ── Agent API / MCP ── */}
      <div className="bg-white border border-[#E6E8EC] rounded-lg p-6" data-testid="agent-api-settings">
        <SectionHeader
          icon={Bot}
          color="#7839EE"
          title="AI Agent API (MCP Server)"
          description="Connect Gemini, Copilot or any AI agent to query project data in natural language"
          badge="MCP 2025"
        />

        {/* Enable toggle */}
        <div className="flex items-center justify-between p-3 bg-[#F9FAFB] rounded-lg border border-[#E6E8EC] mb-5">
          <div>
            <p className="text-sm font-medium text-[#0B1220]">Enable Agent API</p>
            <p className="text-xs text-[#667085]">Exposes project data as MCP tools for AI agents</p>
          </div>
          <Switch checked={agentEnabled} onCheckedChange={setAgentEnabled} data-testid="agent-api-toggle" />
        </div>

        <div className="space-y-4">
          {/* MCP endpoint */}
          <div>
            <Label>MCP Server Endpoint</Label>
            <div className="flex gap-2 mt-1">
              <Input readOnly value={mcpEndpoint} className="font-mono text-xs bg-[#F9FAFB]" data-testid="mcp-endpoint-url" />
              <CopyButton value={mcpEndpoint} label="Copy" />
            </div>
            <p className="text-xs text-[#667085] mt-1">Paste into Gemini Studio, Copilot Studio, or any MCP-compatible client</p>
          </div>

          {/* API Key */}
          <div>
            <Label>Agent API Key</Label>
            {newApiKey ? (
              <div className="mt-1">
                <div className="flex gap-2">
                  <Input readOnly value={newApiKey} className="font-mono text-xs bg-amber-50 border-amber-200" data-testid="new-api-key" />
                  <CopyButton value={newApiKey} label="Copy" />
                </div>
                <p className="text-xs text-amber-600 mt-1 flex items-center gap-1">
                  <AlertTriangle size={12} /> Save this key now — it won't be shown in full again
                </p>
              </div>
            ) : (
              <div className="mt-1">
                {settings?.agent_api?.api_key_masked ? (
                  <div className="flex items-center gap-3 p-3 bg-[#F9FAFB] border border-[#E6E8EC] rounded-md">
                    <span className="font-mono text-xs text-[#667085]">{settings.agent_api.api_key_masked}</span>
                    <Badge className="bg-green-100 text-green-700 text-xs">Active</Badge>
                  </div>
                ) : (
                  <p className="text-sm text-[#98A2B3] italic">No key generated yet</p>
                )}
              </div>
            )}
          </div>

          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => regenMutation.mutate()}
              disabled={regenMutation.isPending}
              data-testid="regenerate-api-key-btn"
            >
              {regenMutation.isPending ? <Loader2 size={14} className="mr-2 animate-spin" /> : <RefreshCw size={14} className="mr-2" />}
              {settings?.agent_api?.api_key ? 'Rotate Key' : 'Generate Key'}
            </Button>
            <Button
              onClick={() => saveAgentMutation.mutate()}
              disabled={saveAgentMutation.isPending}
              data-testid="save-agent-api-btn"
            >
              {saveAgentMutation.isPending ? <><Loader2 size={14} className="mr-2 animate-spin" />Saving...</> : 'Save Agent API Settings'}
            </Button>
          </div>

          {/* Available tools */}
          <div className="border border-[#E6E8EC] rounded-lg overflow-hidden">
            <div className="bg-[#F9FAFB] px-4 py-2 text-xs font-semibold text-[#667085] uppercase tracking-wider">Available MCP Tools</div>
            <div className="divide-y divide-[#F2F4F7]">
              {[
                { name: 'list_projects', desc: 'List all projects with health, progress and status' },
                { name: 'get_project_status', desc: 'Full status for a specific project including latest update' },
                { name: 'get_team_capacity', desc: 'Who is over-allocated, on the bench, or available' },
                { name: 'get_recent_updates', desc: 'Status updates submitted in the last N days' },
              ].map(({ name, desc }) => (
                <div key={name} className="flex items-start px-4 py-2.5 text-sm gap-3">
                  <span className="font-mono text-xs bg-purple-50 text-purple-700 px-2 py-0.5 rounded shrink-0">{name}</span>
                  <span className="text-[#667085]">{desc}</span>
                </div>
              ))}
            </div>
          </div>

          {/* How to connect */}
          <div className="bg-[#F2F7FF] border border-[#C9DEFF] rounded-lg p-4">
            <p className="text-xs font-semibold text-[#1570EF] mb-2">How to connect in Gemini Studio / Copilot Studio:</p>
            <ol className="space-y-1 text-xs text-[#475467] list-decimal list-inside">
              <li>Generate an API key above</li>
              <li>Copy the MCP Server Endpoint URL</li>
              <li>In Gemini: Agents → Tools → Add MCP Server → enter the URL + API key in <code className="bg-white px-1 rounded">X-Agent-Key</code> header</li>
              <li>In Copilot Studio: Actions → Add MCP Server → Streamable HTTP → paste URL</li>
              <li>Ask your AI agent: <em>"What's the status of the Website Redesign project?"</em></li>
            </ol>
          </div>
        </div>
      </div>

      {/* ── Coming Soon CRMs ── */}
      <div className="bg-white border border-[#E6E8EC] rounded-lg p-6">
        <SectionHeader
          icon={Globe}
          color="#98A2B3"
          title="More Integrations"
          description="Additional CRM connectors — coming soon"
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[
            { name: 'Salesforce', desc: 'Enterprise CRM — bi-directional deal sync', color: '#00A1E0' },
            { name: 'Pipedrive', desc: 'Sales-focused CRM — pipeline to project flow', color: '#1B4F72' },
            { name: 'Monday.com', desc: 'Work OS — board → project sync', color: '#FF3D57' },
            { name: 'Slack', desc: 'Post status updates to project channels', color: '#4A154B' },
          ].map(({ name, desc, color }) => (
            <div key={name} className="flex items-center gap-3 p-3 border border-dashed border-[#E6E8EC] rounded-lg opacity-60">
              <div className="w-8 h-8 rounded-md flex items-center justify-center shrink-0" style={{ background: `${color}18` }}>
                <Globe size={14} style={{ color }} />
              </div>
              <div>
                <p className="text-sm font-medium text-[#0B1220]">{name}</p>
                <p className="text-xs text-[#667085]">{desc}</p>
              </div>
              <Badge variant="outline" className="ml-auto text-xs shrink-0">Soon</Badge>
            </div>
          ))}
        </div>
      </div>

      {/* ── Sync Log ── */}
      <div className="bg-white border border-[#E6E8EC] rounded-lg p-6" data-testid="sync-log-section">
        <div
          className="flex items-center justify-between cursor-pointer"
          onClick={() => { setShowLogs(!showLogs); if (!showLogs) refetchLogs(); }}
        >
          <div className="flex items-center gap-3">
            <Clock size={18} className="text-[#667085]" />
            <div>
              <h3 className="text-base font-semibold" style={{ fontFamily: 'Space Grotesk' }}>Sync Log</h3>
              <p className="text-sm text-[#667085]">Last 30 integration events</p>
            </div>
          </div>
          {showLogs ? <ChevronUp size={16} className="text-[#667085]" /> : <ChevronDown size={16} className="text-[#667085]" />}
        </div>
        {showLogs && (
          <div className="mt-4">
            {syncLogs.length === 0 ? (
              <p className="text-sm text-[#98A2B3] text-center py-4">No sync events yet</p>
            ) : (
              <div>
                {syncLogs.map((log, i) => <SyncLogRow key={i} log={log} />)}
              </div>
            )}
          </div>
        )}
      </div>

    </div>
  );
}
