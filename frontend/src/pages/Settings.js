import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Avatar, AvatarImage, AvatarFallback } from '../components/ui/avatar';
import { Settings as SettingsIcon, Key, Sparkles, CheckCircle2, XCircle, User, Camera, Loader2, Trash2, AlertTriangle, Database, ShieldCheck, Bell, Mail, Clock, Link2 } from 'lucide-react';
import { toast } from 'sonner';
import { getMe, updateAvatar, scanOrphanedData, executeDataCleanup, getAiSettings, updateAiSettings, clearAiSettings, checkTimesheetReminders, checkAllocationReminders, getReminderStatus } from '../api';
import IntegrationsSettings from '../components/IntegrationsSettings';

const Settings = () => {
  const queryClient = useQueryClient();
  const [provider, setProvider] = useState('openai');
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState('');

  // Avatar state
  const [avatarUrl, setAvatarUrl] = useState('');
  const [avatarPreview, setAvatarPreview] = useState('');

  // Data cleanup state
  const [scanResult, setScanResult] = useState(null);
  const [isScanning, setIsScanning] = useState(false);
  const [isCleaning, setIsCleaning] = useState(false);

  // Fetch current user data
  const { data: userData } = useQuery({
    queryKey: ['me'],
    queryFn: async () => { const r = await getMe(); return r.data; },
  });

  const isSuperAdmin = userData?.role === 'super_admin';
  const isAdmin = userData?.role === 'admin' || isSuperAdmin;

  // Fetch app-wide AI settings (super_admin only)
  const { data: aiSettings, isLoading: aiSettingsLoading, refetch: refetchAiSettings } = useQuery({
    queryKey: ['aiSettings'],
    queryFn: async () => { const r = await getAiSettings(); return r.data; },
    enabled: isSuperAdmin,
    staleTime: 0, // Always refetch when component mounts
    refetchOnMount: 'always',
  });

  // Load saved provider from AI settings
  useEffect(() => {
    if (aiSettings) {
      setProvider(aiSettings.provider || 'openai');
    }
  }, [aiSettings]);

  // Avatar update mutation
  const avatarMutation = useMutation({
    mutationFn: (url) => updateAvatar(url),
    onSuccess: () => {
      toast.success('Avatar updated successfully!');
      queryClient.invalidateQueries(['me']);
      queryClient.invalidateQueries(['resources']);
      setAvatarPreview('');
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || 'Failed to update avatar');
    },
  });

  // AI settings mutation
  const saveMutation = useMutation({
    mutationFn: ({ prov, key }) => updateAiSettings(prov, key),
    onSuccess: async () => {
      toast.success('AI settings saved for the whole app!');
      setApiKey('');
      setError('');
      // Force immediate refetch to show updated values
      await queryClient.invalidateQueries(['aiSettings']);
      refetchAiSettings();
    },
    onError: (err) => {
      setError(err.response?.data?.detail || 'Failed to save settings');
      toast.error('Failed to save AI settings');
    },
  });

  const clearMutation = useMutation({
    mutationFn: clearAiSettings,
    onSuccess: () => {
      toast.success('AI settings cleared. Emergent key will be used as fallback.');
      setApiKey('');
      setProvider('openai');
      queryClient.invalidateQueries(['aiSettings']);
    },
  });

  // Set avatar URL from user data
  useEffect(() => {
    if (userData?.avatar_url) setAvatarUrl(userData.avatar_url);
  }, [userData]);

  const handleSave = () => {
    if (!apiKey.trim()) {
      setError('API Key is required');
      return;
    }
    if (provider === 'openai' && !apiKey.startsWith('sk-')) {
      setError('OpenAI API keys should start with "sk-"');
      return;
    }
    saveMutation.mutate({ prov: provider, key: apiKey });
  };

  const handleAvatarPreview = (url) => setAvatarPreview(url);
  const handleAvatarSave = () => {
    if (!avatarPreview.trim()) { toast.error('Please enter an avatar URL'); return; }
    avatarMutation.mutate(avatarPreview);
    setAvatarUrl(avatarPreview);
  };
  const generateRandomAvatar = () => {
    const seed = Math.random().toString(36).substring(7);
    setAvatarPreview(`https://api.dicebear.com/7.x/avataaars/svg?seed=${seed}`);
  };
  const maskApiKey = (key) => {
    if (!key) return '';
    if (key.length < 8) return key;
    return key.substring(0, 7) + '\u2022'.repeat(key.length - 7);
  };

  const currentAvatarUrl = avatarPreview || avatarUrl || userData?.avatar_url;

  return (
    <div className="space-y-6" data-testid="settings-page">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-semibold flex items-center gap-3" style={{ fontFamily: 'Space Grotesk' }}>
          <SettingsIcon size={32} />
          Settings
        </h1>
        <p className="text-sm text-[#667085] mt-1">Configure your profile, AI integrations and system preferences</p>
      </div>

      {/* Profile Avatar Section */}
      <div className="bg-white border border-[#E6E8EC] rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-[#F2F7FF] flex items-center justify-center"><User size={20} className="text-[#1570EF]" /></div>
          <div>
            <h3 className="text-lg font-semibold" style={{ fontFamily: 'Space Grotesk' }}>Profile Avatar</h3>
            <p className="text-sm text-[#667085]">Customize your profile picture</p>
          </div>
        </div>
        <div className="flex flex-col md:flex-row gap-6 mt-6">
          <div className="flex flex-col items-center gap-3">
            <div className="relative">
              <Avatar className="w-24 h-24 border-4 border-[#E6E8EC]">
                <AvatarImage src={currentAvatarUrl} />
                <AvatarFallback className="text-2xl bg-[#1570EF] text-white">{userData?.email?.charAt(0)?.toUpperCase() || '?'}</AvatarFallback>
              </Avatar>
              <div className="absolute -bottom-1 -right-1 w-8 h-8 rounded-full bg-[#1570EF] flex items-center justify-center"><Camera size={14} className="text-white" /></div>
            </div>
            <span className="text-sm text-[#667085]">{userData?.email}</span>
          </div>
          <div className="flex-1 space-y-4">
            <div>
              <Label htmlFor="avatar-url">Avatar URL</Label>
              <Input id="avatar-url" type="url" value={avatarPreview} onChange={(e) => handleAvatarPreview(e.target.value)} placeholder="https://example.com/your-avatar.png" className="mt-1" data-testid="avatar-url-input" />
              <p className="text-xs text-[#667085] mt-1">Enter a URL to your profile picture (PNG, JPG, or SVG)</p>
            </div>
            <div>
              <Label>Quick Options</Label>
              <div className="flex flex-wrap gap-2 mt-2">
                <Button type="button" variant="outline" size="sm" onClick={generateRandomAvatar} data-testid="random-avatar-btn">Generate Random</Button>
                <Button type="button" variant="outline" size="sm" onClick={() => handleAvatarPreview(`https://api.dicebear.com/7.x/initials/svg?seed=${userData?.email || 'user'}`)}>Use Initials</Button>
                <Button type="button" variant="outline" size="sm" onClick={() => handleAvatarPreview(`https://api.dicebear.com/7.x/bottts/svg?seed=${userData?.email || 'user'}`)}>Robot Style</Button>
              </div>
            </div>
            <div className="flex gap-2">
              <Button onClick={handleAvatarSave} disabled={!avatarPreview || avatarMutation.isPending} data-testid="save-avatar-btn">
                {avatarMutation.isPending ? <><Loader2 size={16} className="mr-2 animate-spin" />Saving...</> : <><CheckCircle2 size={16} className="mr-2" />Save Avatar</>}
              </Button>
              {avatarPreview && <Button variant="outline" onClick={() => setAvatarPreview('')}>Cancel</Button>}
            </div>
          </div>
        </div>
      </div>

      {/* AI Integration Section — super_admin only */}
      {isSuperAdmin && (
        <div className="bg-white border border-[#E6E8EC] rounded-lg p-6" data-testid="ai-settings-section">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-lg bg-[#F2F7FF] flex items-center justify-center"><Sparkles size={20} className="text-[#1570EF]" /></div>
            <div>
              <h3 className="text-lg font-semibold" style={{ fontFamily: 'Space Grotesk' }}>AI Configuration</h3>
              <p className="text-sm text-[#667085]">App-wide AI provider settings &mdash; applies to all users</p>
            </div>
            <span className="ml-auto flex items-center gap-1 text-xs text-[#667085] bg-[#F9FAFB] border border-[#E6E8EC] rounded px-2 py-1"><ShieldCheck size={12} /> Super Admin only</span>
          </div>

          {aiSettingsLoading ? (
            <div className="flex items-center gap-2 py-6 justify-center text-[#667085]"><Loader2 size={18} className="animate-spin" /><span className="text-sm">Loading settings...</span></div>
          ) : (
            <div className="space-y-4 mt-6">
              {/* Current status */}
              <div className="bg-[#F9FAFB] border border-[#E6E8EC] rounded-lg p-4">
                <div className="text-xs font-semibold text-[#667085] uppercase tracking-wider mb-2">Current Status</div>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-[#667085]">Provider:</span>
                    <span className="font-medium capitalize">{aiSettings?.has_key ? aiSettings.provider : 'Not configured'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#667085]">API Key:</span>
                    <span className="font-mono text-xs">{aiSettings?.has_key ? aiSettings.api_key_masked : 'None'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#667085]">Emergent Fallback:</span>
                    <span className={`flex items-center gap-1 ${aiSettings?.has_emergent_fallback ? 'text-[#16B364]' : 'text-[#667085]'}`}>
                      {aiSettings?.has_emergent_fallback ? <><CheckCircle2 size={14} />Active</> : <><XCircle size={14} />Not configured</>}
                    </span>
                  </div>
                </div>
              </div>

              {/* Provider Selection */}
              <div>
                <Label htmlFor="provider">LLM Provider</Label>
                <Select value={provider} onValueChange={setProvider}>
                  <SelectTrigger id="provider" data-testid="provider-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="openai">OpenAI (GPT-4o-mini)</SelectItem>
                    <SelectItem value="gemini">Google Gemini (Flash)</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-[#667085] mt-1">This provider will be used for all AI features across the app</p>
              </div>

              {/* API Key Input */}
              <div>
                <Label htmlFor="api-key">{aiSettings?.has_key ? 'Update API Key' : 'API Key'}</Label>
                <div className="relative">
                  <Key size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-[#667085]" />
                  <Input
                    id="api-key" type="password" value={apiKey} onChange={(e) => { setApiKey(e.target.value); setError(''); }}
                    placeholder={provider === 'openai' ? 'sk-...' : 'AIza...'}
                    className="pl-10" data-testid="api-key-input"
                  />
                </div>
                <div className="mt-2 text-xs text-[#667085]">
                  {provider === 'openai' ? (
                    <span>Get your API key from <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer" className="text-[#1570EF] hover:underline">OpenAI Platform</a></span>
                  ) : (
                    <span>Get your API key from <a href="https://makersuite.google.com/app/apikey" target="_blank" rel="noopener noreferrer" className="text-[#1570EF] hover:underline">Google AI Studio</a></span>
                  )}
                </div>
              </div>

              {/* Info */}
              <div className="bg-[#F7F7F8] border border-[#E6E8EC] rounded-lg p-4">
                <div className="flex gap-3">
                  <Key size={16} className="text-[#667085] flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-[#667085]">
                    <strong className="text-[#0B1220]">App-wide key:</strong> This API key is stored securely on the server and used by all AI features (Command Bar, Budget Analysis, Portfolio Insights, Status Summaries). If the key fails, the Emergent backup key is used automatically.
                  </div>
                </div>
              </div>

              {error && (
                <Alert variant="destructive" data-testid="error-alert">
                  <XCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <div className="flex gap-2 pt-2">
                <Button onClick={handleSave} disabled={saveMutation.isPending} data-testid="save-settings">
                  {saveMutation.isPending ? <><Loader2 size={16} className="mr-2 animate-spin" />Saving...</> : <><Key size={16} className="mr-2" />Save Settings</>}
                </Button>
                {aiSettings?.has_key && (
                  <Button variant="outline" onClick={() => clearMutation.mutate()} disabled={clearMutation.isPending} data-testid="clear-settings">
                    Clear Settings
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Usage Instructions */}
      <div className="bg-[#F7F7F8] border border-[#E6E8EC] rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4" style={{ fontFamily: 'Space Grotesk' }}>How to Use AI Commands</h3>
        <div className="space-y-3 text-sm text-[#667085]">
          <div className="flex gap-3">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-[#1570EF] text-white flex items-center justify-center text-xs font-semibold">1</div>
            <div><strong className="text-[#0B1220]">Open Command Bar:</strong> Press <kbd className="px-2 py-1 bg-white border border-[#E6E8EC] rounded text-xs font-mono">Ctrl+K</kbd> (or <kbd className="px-2 py-1 bg-white border border-[#E6E8EC] rounded text-xs font-mono">Cmd+K</kbd> on Mac)</div>
          </div>
          <div className="flex gap-3">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-[#1570EF] text-white flex items-center justify-center text-xs font-semibold">2</div>
            <div><strong className="text-[#0B1220]">Type your command:</strong> Use natural language like "Assign Alice to Mobile App at 60%"</div>
          </div>
          <div className="flex gap-3">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-[#1570EF] text-white flex items-center justify-center text-xs font-semibold">3</div>
            <div><strong className="text-[#0B1220]">Confirm action:</strong> Review the parsed command and click "Confirm"</div>
          </div>
        </div>
        <div className="mt-4 pt-4 border-t border-[#E6E8EC]">
          <strong className="text-sm text-[#0B1220]">Example Commands:</strong>
          <ul className="mt-2 space-y-1 text-sm text-[#667085] list-disc list-inside">
            <li>"Put John on Website Redesign at 75% for 2 weeks"</li>
            <li>"Website project is delayed, at 50% complete"</li>
            <li>"Add high impact risk about API delays to Project X"</li>
          </ul>
        </div>
      </div>

      {/* DATA CLEANUP - Admin only */}
      {isAdmin && (
        <div className="bg-white border border-[#E6E8EC] rounded-lg p-6" data-testid="data-cleanup-section">
          <h2 className="text-lg font-semibold text-[#0B1220] flex items-center gap-2 mb-1" style={{ fontFamily: 'Space Grotesk' }}>
            <Database size={20} className="text-[#EF4444]" />
            Data Cleanup
          </h2>
          <p className="text-sm text-[#667085] mb-4">Scan and remove orphaned records that reference deleted resources or projects.</p>
          <div className="flex items-center gap-3 mb-4">
            <Button variant="outline" onClick={async () => {
              setIsScanning(true); setScanResult(null);
              try { const res = await scanOrphanedData(); setScanResult(res.data); }
              catch (err) { toast.error(err.response?.data?.detail || 'Scan failed'); }
              finally { setIsScanning(false); }
            }} disabled={isScanning} data-testid="scan-orphaned-btn">
              {isScanning ? <Loader2 size={16} className="mr-2 animate-spin" /> : <Database size={16} className="mr-2" />}
              {isScanning ? 'Scanning...' : 'Scan for Orphaned Data'}
            </Button>
          </div>
          {scanResult && (
            <div className="space-y-3">
              {scanResult.total_orphaned === 0 ? (
                <Alert className="bg-green-50 border-green-200" data-testid="cleanup-no-orphans">
                  <CheckCircle2 className="h-4 w-4 text-green-600" /><AlertDescription className="text-green-800">No orphaned data found. Database is clean.</AlertDescription>
                </Alert>
              ) : (
                <>
                  <Alert className="bg-amber-50 border-amber-200" data-testid="cleanup-orphans-found">
                    <AlertTriangle className="h-4 w-4 text-amber-600" />
                    <AlertDescription className="text-amber-800">
                      Found <strong>{scanResult.total_orphaned}</strong> orphaned records:
                      <ul className="mt-1 list-disc list-inside text-sm">
                        {scanResult.orphaned_allocations > 0 && <li>{scanResult.orphaned_allocations} allocations</li>}
                        {scanResult.orphaned_timesheets > 0 && <li>{scanResult.orphaned_timesheets} timesheets</li>}
                        {scanResult.orphaned_status_updates > 0 && <li>{scanResult.orphaned_status_updates} status updates</li>}
                      </ul>
                    </AlertDescription>
                  </Alert>
                  <Button variant="destructive" onClick={async () => {
                    if (!window.confirm(`Delete ${scanResult.total_orphaned} orphaned records? This cannot be undone.`)) return;
                    setIsCleaning(true);
                    try {
                      const res = await executeDataCleanup();
                      toast.success(`Cleanup complete: ${res.data.deleted.total} records removed`);
                      setScanResult(null);
                      queryClient.invalidateQueries(['allocations']);
                      queryClient.invalidateQueries(['timesheets']);
                    } catch (err) { toast.error(err.response?.data?.detail || 'Cleanup failed'); }
                    finally { setIsCleaning(false); }
                  }} disabled={isCleaning} data-testid="execute-cleanup-btn">
                    {isCleaning ? <Loader2 size={16} className="mr-2 animate-spin" /> : <Trash2 size={16} className="mr-2" />}
                    {isCleaning ? 'Cleaning...' : `Delete ${scanResult.total_orphaned} Orphaned Records`}
                  </Button>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {/* Reminder System (Admin only) */}
      {isAdmin && (
        <div className="bg-white border border-[#E6E8EC] rounded-lg p-6" data-testid="reminder-settings">
          <div className="flex items-center gap-3 mb-4">
            <Bell className="text-[#1570EF]" size={24} />
            <div>
              <h3 className="font-semibold">Reminder System</h3>
              <p className="text-sm text-[#667085]">Send reminders for timesheets and ending allocations</p>
            </div>
          </div>

          <ReminderSection />
        </div>
      )}

      {/* Integrations — super_admin only */}
      {isSuperAdmin && (
        <div data-testid="integrations-section">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-lg bg-[#F2F7FF] flex items-center justify-center"><Link2 size={20} className="text-[#1570EF]" /></div>
            <div>
              <h2 className="text-lg font-semibold" style={{ fontFamily: 'Space Grotesk' }}>Integrations</h2>
              <p className="text-sm text-[#667085]">Connect DD Planner to CRMs and AI agents</p>
            </div>
            <span className="ml-auto flex items-center gap-1 text-xs text-[#667085] bg-[#F9FAFB] border border-[#E6E8EC] rounded px-2 py-1"><ShieldCheck size={12} /> Super Admin only</span>
          </div>
          <IntegrationsSettings />
        </div>
      )}
    </div>
  );
};

// Separate component for reminder section to use hooks
const ReminderSection = () => {
  const [isLoadingStatus, setIsLoadingStatus] = useState(false);
  const [reminderStatus, setReminderStatus] = useState(null);
  const [isSendingTimesheets, setIsSendingTimesheets] = useState(false);
  const [isSendingAllocations, setIsSendingAllocations] = useState(false);

  const loadStatus = async () => {
    setIsLoadingStatus(true);
    try {
      const res = await getReminderStatus();
      setReminderStatus(res.data);
    } catch (err) {
      toast.error('Failed to load reminder status');
    } finally {
      setIsLoadingStatus(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const handleSendTimesheetReminders = async () => {
    setIsSendingTimesheets(true);
    try {
      const res = await checkTimesheetReminders();
      toast.success(`Sent ${res.data.reminders_sent} timesheet reminders`);
      loadStatus();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to send reminders');
    } finally {
      setIsSendingTimesheets(false);
    }
  };

  const handleSendAllocationReminders = async () => {
    setIsSendingAllocations(true);
    try {
      const res = await checkAllocationReminders();
      toast.success(`Sent ${res.data.reminders_sent} allocation reminders`);
      loadStatus();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to send reminders');
    } finally {
      setIsSendingAllocations(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Status Summary */}
      {reminderStatus && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-[#F9FAFB] rounded-lg">
          <div>
            <div className="text-2xl font-bold text-[#0B1220]">{reminderStatus.pending_timesheets}</div>
            <div className="text-xs text-[#667085]">Pending Timesheets</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-[#F4B740]">{reminderStatus.allocations_ending_soon}</div>
            <div className="text-xs text-[#667085]">Allocations Ending (14d)</div>
          </div>
          <div>
            <div className="text-xs text-[#667085]">Current Week</div>
            <div className="text-sm font-medium">{reminderStatus.current_week}</div>
          </div>
          <div>
            <div className="text-xs text-[#667085]">Email Status</div>
            <div className={`text-sm font-medium flex items-center gap-1 ${reminderStatus.email_configured ? 'text-[#16B364]' : 'text-[#F4B740]'}`}>
              <Mail size={14} />
              {reminderStatus.email_configured ? 'Configured' : 'Not Configured'}
            </div>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-3">
        <Button
          variant="outline"
          onClick={handleSendTimesheetReminders}
          disabled={isSendingTimesheets}
          data-testid="send-timesheet-reminders-btn"
        >
          {isSendingTimesheets ? <Loader2 size={16} className="mr-2 animate-spin" /> : <Clock size={16} className="mr-2" />}
          {isSendingTimesheets ? 'Sending...' : 'Send Timesheet Reminders'}
        </Button>

        <Button
          variant="outline"
          onClick={handleSendAllocationReminders}
          disabled={isSendingAllocations}
          data-testid="send-allocation-reminders-btn"
        >
          {isSendingAllocations ? <Loader2 size={16} className="mr-2 animate-spin" /> : <Bell size={16} className="mr-2" />}
          {isSendingAllocations ? 'Sending...' : 'Send Allocation Reminders'}
        </Button>

        <Button
          variant="ghost"
          onClick={loadStatus}
          disabled={isLoadingStatus}
        >
          {isLoadingStatus ? <Loader2 size={16} className="animate-spin" /> : 'Refresh Status'}
        </Button>
      </div>

      <p className="text-xs text-[#667085]">
        Timesheet reminders are sent Thu-Mon. Allocation reminders notify staff when assignments end within 14 days.
        {!reminderStatus?.email_configured && (
          <span className="block mt-1 text-[#F4B740]">
            Note: Email notifications require RESEND_API_KEY to be configured in environment.
          </span>
        )}
      </p>
    </div>
  );
};

export default Settings;
