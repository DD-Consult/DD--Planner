/**
 * Workspace Branding & Work Policy settings (Step 9 of MULTITENANT_PLAN.md).
 *
 * Two cards, both restricted to super_admin:
 *  1. Branding — workspace name, primary & accent colors, logo (data URL)
 *  2. Work Policy — work_week_hours, timezone (IANA)
 *
 * Uses PATCH endpoints on /api/tenant/branding and /api/tenant/settings.
 * Falls back gracefully in flag=off mode: GET /api/tenant/branding always
 * returns the DD Consulting default tenant.
 */
import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Palette, Clock, Loader2, Upload, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { getTenantBranding, updateTenantBranding, updateTenantSettings } from '../api';

const COMMON_TIMEZONES = [
  'UTC',
  'Australia/Sydney',
  'Australia/Melbourne',
  'Australia/Perth',
  'America/Los_Angeles',
  'America/New_York',
  'America/Chicago',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Asia/Kolkata',
];

const HEX_RE = /^#[0-9A-Fa-f]{6}$/;

export default function WorkspaceBrandingSection({ userRole }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [primaryColor, setPrimaryColor] = useState('#1B2A47');
  const [accentColor, setAccentColor] = useState('#C9A84C');
  const [logoUrl, setLogoUrl] = useState(null);
  const [workWeekHours, setWorkWeekHours] = useState(40);
  const [timezone, setTimezone] = useState('UTC');
  const fileInputRef = useRef(null);

  const { data: branding, isLoading } = useQuery({
    queryKey: ['tenantBranding'],
    queryFn: async () => {
      const r = await getTenantBranding();
      return r.data;
    },
  });

  // Hydrate form state from server data once
  useEffect(() => {
    if (!branding) return;
    setName(branding.name || '');
    setPrimaryColor(branding.branding?.primary_color || '#1B2A47');
    setAccentColor(branding.branding?.accent_color || '#C9A84C');
    setLogoUrl(branding.branding?.logo_url || null);
    setWorkWeekHours(branding.settings?.work_week_hours ?? 40);
    setTimezone(branding.settings?.timezone || 'UTC');
  }, [branding]);

  const brandingMutation = useMutation({
    mutationFn: updateTenantBranding,
    onSuccess: () => {
      toast.success('Branding saved');
      queryClient.invalidateQueries(['tenantBranding']);
    },
    onError: (err) => {
      const detail = err?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Save failed');
    },
  });

  const settingsMutation = useMutation({
    mutationFn: updateTenantSettings,
    onSuccess: () => {
      toast.success('Work policy saved');
      queryClient.invalidateQueries(['tenantBranding']);
    },
    onError: (err) => {
      const detail = err?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Save failed');
    },
  });

  const isSuperAdmin = userRole === 'super_admin';

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-6 flex items-center gap-2 text-slate-500">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading workspace settings...
        </CardContent>
      </Card>
    );
  }

  const handleSaveBranding = () => {
    if (!HEX_RE.test(primaryColor)) return toast.error('Primary color must be #RRGGBB hex');
    if (!HEX_RE.test(accentColor)) return toast.error('Accent color must be #RRGGBB hex');
    brandingMutation.mutate({
      name: name.trim(),
      primary_color: primaryColor,
      accent_color: accentColor,
      logo_url: logoUrl,
    });
  };

  const handleSaveSettings = () => {
    if (workWeekHours < 1 || workWeekHours > 168) return toast.error('Work week must be 1–168 hours');
    if (!timezone.trim()) return toast.error('Timezone required');
    settingsMutation.mutate({
      work_week_hours: Number(workWeekHours),
      timezone: timezone.trim(),
    });
  };

  const handleLogoUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 400_000) {
      toast.error('Logo too large. Please choose an image under 400KB.');
      return;
    }
    const reader = new FileReader();
    reader.onload = (evt) => setLogoUrl(evt.target.result);
    reader.readAsDataURL(file);
  };

  return (
    <div className="space-y-6" data-testid="workspace-branding-section">
      {/* ═════════════ Branding Card ═════════════ */}
      <Card data-testid="workspace-branding-card">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Palette className="w-5 h-5 text-[#1B2A47]" />
            <CardTitle>Workspace Branding</CardTitle>
          </div>
          <CardDescription>
            Customise your workspace name and colors. These appear on exports and the app header.
            {!isSuperAdmin && ' Read-only — only super admins can edit.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="ws-name">Workspace name</Label>
            <Input
              id="ws-name"
              data-testid="workspace-name-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={!isSuperAdmin}
              placeholder="Your Company Name"
              maxLength={100}
            />
            <p className="text-xs text-slate-500 mt-1">Shown as "Prepared by X" on PDF/PPT exports</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="primary-color">Primary color</Label>
              <div className="flex gap-2 items-center">
                <input
                  type="color"
                  data-testid="primary-color-picker"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value.toUpperCase())}
                  disabled={!isSuperAdmin}
                  className="w-12 h-10 rounded border border-slate-200 cursor-pointer"
                />
                <Input
                  id="primary-color"
                  data-testid="primary-color-input"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  disabled={!isSuperAdmin}
                  placeholder="#1B2A47"
                  className="font-mono uppercase"
                  maxLength={7}
                />
              </div>
            </div>
            <div>
              <Label htmlFor="accent-color">Accent color</Label>
              <div className="flex gap-2 items-center">
                <input
                  type="color"
                  data-testid="accent-color-picker"
                  value={accentColor}
                  onChange={(e) => setAccentColor(e.target.value.toUpperCase())}
                  disabled={!isSuperAdmin}
                  className="w-12 h-10 rounded border border-slate-200 cursor-pointer"
                />
                <Input
                  id="accent-color"
                  data-testid="accent-color-input"
                  value={accentColor}
                  onChange={(e) => setAccentColor(e.target.value)}
                  disabled={!isSuperAdmin}
                  placeholder="#C9A84C"
                  className="font-mono uppercase"
                  maxLength={7}
                />
              </div>
            </div>
          </div>

          <div>
            <Label>Logo</Label>
            <div className="flex items-center gap-3">
              {logoUrl ? (
                <img src={logoUrl} alt="Workspace logo" className="w-16 h-16 rounded border border-slate-200 object-contain bg-white" />
              ) : (
                <div className="w-16 h-16 rounded border border-slate-200 border-dashed flex items-center justify-center text-slate-400 bg-slate-50">
                  <Palette className="w-6 h-6" />
                </div>
              )}
              <div className="flex flex-col gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={!isSuperAdmin}
                  data-testid="logo-upload-btn"
                >
                  <Upload className="w-4 h-4 mr-1" /> Upload logo
                </Button>
                {logoUrl && isSuperAdmin && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setLogoUrl(null)}
                    className="text-red-600 hover:text-red-700"
                    data-testid="logo-remove-btn"
                  >
                    <Trash2 className="w-4 h-4 mr-1" /> Remove
                  </Button>
                )}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/svg+xml"
                onChange={handleLogoUpload}
                className="hidden"
              />
            </div>
            <p className="text-xs text-slate-500 mt-1">PNG, JPG, WebP or SVG. Max 400KB.</p>
          </div>

          {/* Live preview */}
          <div className="rounded-lg border border-slate-200 overflow-hidden">
            <div className="text-xs font-medium text-slate-500 px-3 py-2 bg-slate-50 border-b border-slate-200">Preview</div>
            <div style={{ backgroundColor: primaryColor }} className="p-4 text-white flex items-center justify-between">
              <span className="font-semibold">{name || 'Your Workspace'}</span>
              <span style={{ color: accentColor }} className="text-sm font-bold">CONFIDENTIAL</span>
            </div>
          </div>

          {isSuperAdmin && (
            <div className="flex justify-end">
              <Button
                onClick={handleSaveBranding}
                disabled={brandingMutation.isPending}
                data-testid="save-branding-btn"
                className="bg-[#1B2A47] hover:bg-[#111C33]"
              >
                {brandingMutation.isPending ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving...</>
                ) : 'Save Branding'}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ═════════════ Work Policy Card ═════════════ */}
      <Card data-testid="workspace-policy-card">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-[#1B2A47]" />
            <CardTitle>Work Policy</CardTitle>
          </div>
          <CardDescription>
            Standard work-week hours and default timezone for scheduling & reminders.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="work-week-hours">Standard work week (hours)</Label>
              <Input
                id="work-week-hours"
                data-testid="work-week-hours-input"
                type="number"
                min={1}
                max={168}
                value={workWeekHours}
                onChange={(e) => setWorkWeekHours(e.target.value)}
                disabled={!isSuperAdmin}
              />
              <p className="text-xs text-slate-500 mt-1">Default: 40 (5 × 8-hour days)</p>
            </div>
            <div>
              <Label htmlFor="tz-select">Timezone</Label>
              <select
                id="tz-select"
                data-testid="timezone-select"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                disabled={!isSuperAdmin}
                className="flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400 disabled:opacity-50"
              >
                {COMMON_TIMEZONES.map(tz => (
                  <option key={tz} value={tz}>{tz}</option>
                ))}
                {!COMMON_TIMEZONES.includes(timezone) && timezone && (
                  <option value={timezone}>{timezone} (custom)</option>
                )}
              </select>
            </div>
          </div>

          {isSuperAdmin && (
            <div className="flex justify-end">
              <Button
                onClick={handleSaveSettings}
                disabled={settingsMutation.isPending}
                data-testid="save-policy-btn"
                className="bg-[#1B2A47] hover:bg-[#111C33]"
              >
                {settingsMutation.isPending ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving...</>
                ) : 'Save Work Policy'}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
