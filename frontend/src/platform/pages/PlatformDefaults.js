import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getPlatformDefaults, updatePlatformDefaults } from '../api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Palette, Settings, Loader2, Save } from 'lucide-react';
import { toast } from 'sonner';

const PlatformDefaults = () => {
  const queryClient = useQueryClient();

  // Form state
  const [primaryColor, setPrimaryColor] = useState('#1E40AF');
  const [accentColor, setAccentColor] = useState('#3B82F6');
  const [workWeekHours, setWorkWeekHours] = useState('40');
  const [timezone, setTimezone] = useState('UTC');

  // Fetch platform defaults
  const { data: defaultsData, isLoading } = useQuery({
    queryKey: ['platformDefaults'],
    queryFn: async () => {
      const response = await getPlatformDefaults();
      return response.data;
    },
  });

  // Initialize form state from query data
  useEffect(() => {
    if (defaultsData) {
      setPrimaryColor(defaultsData.branding?.primary_color || '#1E40AF');
      setAccentColor(defaultsData.branding?.accent_color || '#3B82F6');
      setWorkWeekHours(defaultsData.settings?.work_week_hours?.toString() || '40');
      setTimezone(defaultsData.settings?.timezone || 'UTC');
    }
  }, [defaultsData]);

  // Mutation to update defaults
  const updateMutation = useMutation({
    mutationFn: (data) => updatePlatformDefaults(data),
    onSuccess: () => {
      queryClient.invalidateQueries(['platformDefaults']);
      toast.success('Platform defaults updated');
    },
  });

  const handleSave = () => {
    updateMutation.mutate({
      branding: {
        primary_color: primaryColor,
        accent_color: accentColor,
      },
      settings: {
        work_week_hours: Number(workWeekHours),
        timezone: timezone,
      },
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Platform Defaults</h1>
        <p className="text-slate-400">
          These are the default branding & settings every tenant inherits. Changing a value here
          instantly updates all tenants that haven&apos;t customized that specific setting.
        </p>
      </div>

      {/* Default Branding */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Palette className="h-5 w-5 text-indigo-500" />
            Default Branding
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Primary Color */}
          <div className="space-y-2">
            <Label htmlFor="primary-color" className="text-slate-300">
              Primary Color
            </Label>
            <div className="flex items-center gap-3">
              <input
                type="color"
                id="primary-color"
                value={primaryColor}
                onChange={(e) => setPrimaryColor(e.target.value)}
                className="h-10 w-20 rounded border border-slate-700 bg-slate-800 cursor-pointer"
                data-testid="default-primary-color"
              />
              <Input
                type="text"
                value={primaryColor}
                onChange={(e) => setPrimaryColor(e.target.value)}
                placeholder="#1E40AF"
                className="flex-1 bg-slate-800 border-slate-700 text-slate-200 placeholder:text-slate-500"
              />
            </div>
          </div>

          {/* Accent Color */}
          <div className="space-y-2">
            <Label htmlFor="accent-color" className="text-slate-300">
              Accent Color
            </Label>
            <div className="flex items-center gap-3">
              <input
                type="color"
                id="accent-color"
                value={accentColor}
                onChange={(e) => setAccentColor(e.target.value)}
                className="h-10 w-20 rounded border border-slate-700 bg-slate-800 cursor-pointer"
                data-testid="default-accent-color"
              />
              <Input
                type="text"
                value={accentColor}
                onChange={(e) => setAccentColor(e.target.value)}
                placeholder="#3B82F6"
                className="flex-1 bg-slate-800 border-slate-700 text-slate-200 placeholder:text-slate-500"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Default Settings */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Settings className="h-5 w-5 text-indigo-500" />
            Default Settings
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Work Week Hours */}
          <div className="space-y-2">
            <Label htmlFor="work-week" className="text-slate-300">
              Work Week Hours
            </Label>
            <Input
              id="work-week"
              type="number"
              min="1"
              max="168"
              value={workWeekHours}
              onChange={(e) => setWorkWeekHours(e.target.value)}
              className="bg-slate-800 border-slate-700 text-slate-200 placeholder:text-slate-500"
              data-testid="default-work-week"
            />
            <p className="text-xs text-slate-500">
              Standard work hours per week (1-168)
            </p>
          </div>

          {/* Timezone */}
          <div className="space-y-2">
            <Label htmlFor="timezone" className="text-slate-300">
              Timezone
            </Label>
            <Input
              id="timezone"
              type="text"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              placeholder="America/New_York"
              className="bg-slate-800 border-slate-700 text-slate-200 placeholder:text-slate-500"
              data-testid="default-timezone"
            />
            <p className="text-xs text-slate-500">
              IANA timezone identifier (e.g., America/New_York, Europe/London)
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button
          onClick={handleSave}
          disabled={updateMutation.isPending}
          className="bg-indigo-600 hover:bg-indigo-700 text-white"
          data-testid="save-platform-defaults-button"
        >
          {updateMutation.isPending ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save className="h-4 w-4 mr-2" />
              Save Defaults
            </>
          )}
        </Button>
      </div>
    </div>
  );
};

export default PlatformDefaults;
