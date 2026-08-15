import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getTenants,
  updateTenant,
  getTenantModules,
  bulkUpdateTenantModules,
  getTenantUsers,
  impersonateTenant,
} from '../api';
import { setAuthToken } from '../../api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Switch } from '../../components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui/table';
import { ArrowLeft, Save, UserRoundCog, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import { format, parseISO } from 'date-fns';

const PlatformTenantDetail = () => {
  const { slug } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Overview tab states
  const [editedName, setEditedName] = useState('');
  const [editedPrimaryColor, setEditedPrimaryColor] = useState('');
  const [editedAccentColor, setEditedAccentColor] = useState('');
  const [editedWorkWeek, setEditedWorkWeek] = useState('');
  const [editedTimezone, setEditedTimezone] = useState('');

  // Modules tab states
  const [moduleStates, setModuleStates] = useState({});

  // Fetch tenant details
  const { data: tenants } = useQuery({
    queryKey: ['platformTenants'],
    queryFn: async () => {
      const response = await getTenants();
      return response.data;
    },
  });

  const tenant = tenants?.find((t) => t.slug === slug);

  // Fetch tenant modules
  const { data: modulesData, isLoading: modulesLoading } = useQuery({
    queryKey: ['tenantModules', slug],
    queryFn: async () => {
      const response = await getTenantModules(slug);
      return response.data;
    },
    enabled: !!slug,
  });

  // Fetch tenant users
  const { data: users, isLoading: usersLoading } = useQuery({
    queryKey: ['tenantUsers', slug],
    queryFn: async () => {
      const response = await getTenantUsers(slug);
      return response.data;
    },
    enabled: !!slug,
  });

  // Initialize form states when tenant data loads
  React.useEffect(() => {
    if (tenant) {
      setEditedName(tenant.name || '');
      setEditedPrimaryColor(tenant.primary_color || '#1E40AF');
      setEditedAccentColor(tenant.accent_color || '#3B82F6');
      setEditedWorkWeek(tenant.work_week_hours?.toString() || '40');
      setEditedTimezone(tenant.timezone || 'UTC');
    }
  }, [tenant]);

  // Initialize module states
  React.useEffect(() => {
    if (modulesData?.modules) {
      const states = {};
      modulesData.modules.forEach((m) => {
        states[m.module_key] = m.enabled;
      });
      setModuleStates(states);
    }
  }, [modulesData]);

  const updateTenantMutation = useMutation({
    mutationFn: (data) => updateTenant(slug, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['platformTenants']);
      toast.success('Tenant updated successfully');
    },
  });

  const updateModulesMutation = useMutation({
    mutationFn: (modules) => bulkUpdateTenantModules(slug, modules),
    onSuccess: () => {
      queryClient.invalidateQueries(['tenantModules', slug]);
      toast.success('Modules updated successfully');
    },
    onError: (error) => {
      // Error already shown by interceptor
    },
  });

  const impersonateMutation = useMutation({
    mutationFn: () => impersonateTenant(slug),
    onSuccess: (response) => {
      const tenantToken = response.data.access_token;
      localStorage.setItem('token', tenantToken);
      setAuthToken(tenantToken);
      window.open('/', '_blank');
      toast.success('Impersonation session started (15 min)', { duration: 3000 });
    },
  });

  const handleSaveOverview = () => {
    updateTenantMutation.mutate({
      name: editedName,
      primary_color: editedPrimaryColor,
      accent_color: editedAccentColor,
      work_week_hours: parseFloat(editedWorkWeek),
      timezone: editedTimezone,
    });
  };

  const handleSaveModules = () => {
    updateModulesMutation.mutate(moduleStates);
  };

  const handleModuleToggle = (moduleKey, enabled) => {
    setModuleStates((prev) => ({
      ...prev,
      [moduleKey]: enabled,
    }));
  };

  const handleImpersonate = () => {
    if (window.confirm(`Start impersonation session for "${tenant?.name}"? This will be audit-logged.`)) {
      impersonateMutation.mutate();
    }
  };

  if (!tenant) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-slate-400">Tenant not found</div>
      </div>
    );
  }

  // Group modules by category
  const groupedModules = modulesData?.modules?.reduce((acc, module) => {
    const category = module.category || 'Other';
    if (!acc[category]) acc[category] = [];
    acc[category].push(module);
    return acc;
  }, {}) || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/platform/tenants')}
          className="text-slate-400 hover:text-white hover:bg-slate-800"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Tenants
        </Button>
        <div className="flex-1">
          <h1 className="text-3xl font-bold text-white mb-1" data-testid="tenant-detail-title">
            {tenant.name}
          </h1>
          <p className="text-slate-400 font-mono text-sm">{tenant.slug}</p>
        </div>
        <Badge
          variant="outline"
          className={
            tenant.status === 'active'
              ? 'border-green-700 text-green-400 bg-green-900/20'
              : 'border-amber-700 text-amber-400 bg-amber-900/20'
          }
        >
          {tenant.status}
        </Badge>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList className="bg-slate-900 border border-slate-800">
          <TabsTrigger value="overview" className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white">
            Overview
          </TabsTrigger>
          <TabsTrigger value="modules" className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white">
            Modules
          </TabsTrigger>
          <TabsTrigger value="users" className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white">
            Users
          </TabsTrigger>
          <TabsTrigger value="impersonate" className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white">
            Impersonate
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <Card className="bg-slate-900 border-slate-800">
            <CardHeader>
              <CardTitle className="text-white">Basic Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-slate-400 text-sm">Slug</Label>
                  <p className="text-white font-mono mt-1">{tenant.slug}</p>
                </div>
                <div>
                  <Label className="text-slate-400 text-sm">Database Name</Label>
                  <p className="text-white font-mono mt-1">{tenant.db_name}</p>
                </div>
                <div>
                  <Label className="text-slate-400 text-sm">Status</Label>
                  <p className="text-white mt-1">{tenant.status}</p>
                </div>
                <div>
                  <Label className="text-slate-400 text-sm">Created At</Label>
                  <p className="text-white mt-1">
                    {tenant.created_at ? format(parseISO(tenant.created_at), 'MMM d, yyyy HH:mm') : '—'}
                  </p>
                </div>
                <div>
                  <Label className="text-slate-400 text-sm">Owner Email</Label>
                  <p className="text-white mt-1">{tenant.owner_email || '—'}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800">
            <CardHeader>
              <CardTitle className="text-white">Editable Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="name" className="text-slate-300">Tenant Name</Label>
                <Input
                  id="name"
                  value={editedName}
                  onChange={(e) => setEditedName(e.target.value)}
                  className="bg-slate-800 border-slate-700 text-white mt-1"
                  data-testid="edit-tenant-name"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="primaryColor" className="text-slate-300">Primary Color</Label>
                  <div className="flex gap-2 mt-1">
                    <Input
                      id="primaryColor"
                      type="color"
                      value={editedPrimaryColor}
                      onChange={(e) => setEditedPrimaryColor(e.target.value)}
                      className="w-20 h-10 bg-slate-800 border-slate-700"
                    />
                    <Input
                      type="text"
                      value={editedPrimaryColor}
                      onChange={(e) => setEditedPrimaryColor(e.target.value)}
                      className="flex-1 bg-slate-800 border-slate-700 text-white font-mono"
                    />
                  </div>
                </div>

                <div>
                  <Label htmlFor="accentColor" className="text-slate-300">Accent Color</Label>
                  <div className="flex gap-2 mt-1">
                    <Input
                      id="accentColor"
                      type="color"
                      value={editedAccentColor}
                      onChange={(e) => setEditedAccentColor(e.target.value)}
                      className="w-20 h-10 bg-slate-800 border-slate-700"
                    />
                    <Input
                      type="text"
                      value={editedAccentColor}
                      onChange={(e) => setEditedAccentColor(e.target.value)}
                      className="flex-1 bg-slate-800 border-slate-700 text-white font-mono"
                    />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="workWeek" className="text-slate-300">Work Week Hours</Label>
                  <Input
                    id="workWeek"
                    type="number"
                    value={editedWorkWeek}
                    onChange={(e) => setEditedWorkWeek(e.target.value)}
                    className="bg-slate-800 border-slate-700 text-white mt-1"
                  />
                </div>

                <div>
                  <Label htmlFor="timezone" className="text-slate-300">Timezone</Label>
                  <Input
                    id="timezone"
                    value={editedTimezone}
                    onChange={(e) => setEditedTimezone(e.target.value)}
                    className="bg-slate-800 border-slate-700 text-white mt-1"
                  />
                </div>
              </div>

              <div className="flex justify-end pt-4">
                <Button
                  onClick={handleSaveOverview}
                  disabled={updateTenantMutation.isPending}
                  className="bg-indigo-600 hover:bg-indigo-700"
                  data-testid="save-overview-button"
                >
                  <Save className="h-4 w-4 mr-2" />
                  {updateTenantMutation.isPending ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Modules Tab */}
        <TabsContent value="modules" className="space-y-6">
          <Card className="bg-slate-900 border-slate-800">
            <CardHeader>
              <CardTitle className="text-white">Module Configuration</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {modulesLoading ? (
                <p className="text-slate-400 text-center py-8">Loading modules...</p>
              ) : (
                <>
                  {Object.entries(groupedModules).map(([category, modules]) => (
                    <div key={category} className="space-y-3">
                      <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
                        {category}
                      </h3>
                      <div className="space-y-2">
                        {modules.map((module) => (
                          <div
                            key={module.module_key}
                            className="flex items-center justify-between p-4 bg-slate-800 rounded-lg"
                          >
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <p className="text-white font-medium">{module.name}</p>
                                {module.is_core && (
                                  <Badge variant="outline" className="border-blue-700 text-blue-400 bg-blue-900/20 text-xs">
                                    Core
                                  </Badge>
                                )}
                              </div>
                              <p className="text-sm text-slate-400 mt-1">{module.description}</p>
                              {module.depends_on && module.depends_on.length > 0 && (
                                <p className="text-xs text-slate-500 mt-1">
                                  Depends on: {module.depends_on.join(', ')}
                                </p>
                              )}
                            </div>
                            <Switch
                              checked={moduleStates[module.module_key] || false}
                              onCheckedChange={(checked) => handleModuleToggle(module.module_key, checked)}
                              disabled={module.is_core}
                              data-testid={`module-toggle-${module.module_key}`}
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                  
                  <div className="flex justify-end pt-4 border-t border-slate-800">
                    <Button
                      onClick={handleSaveModules}
                      disabled={updateModulesMutation.isPending}
                      className="bg-indigo-600 hover:bg-indigo-700"
                      data-testid="save-modules-button"
                    >
                      <Save className="h-4 w-4 mr-2" />
                      {updateModulesMutation.isPending ? 'Saving...' : 'Save Module Configuration'}
                    </Button>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Users Tab */}
        <TabsContent value="users" className="space-y-6">
          <Card className="bg-slate-900 border-slate-800">
            <CardHeader>
              <CardTitle className="text-white">Tenant Users</CardTitle>
            </CardHeader>
            <CardContent>
              {usersLoading ? (
                <p className="text-slate-400 text-center py-8">Loading users...</p>
              ) : users && users.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow className="border-slate-800 hover:bg-slate-800/50">
                      <TableHead className="text-slate-400">Email</TableHead>
                      <TableHead className="text-slate-400">Role</TableHead>
                      <TableHead className="text-slate-400">Must Change Password</TableHead>
                      <TableHead className="text-slate-400">Created At</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.map((user) => (
                      <TableRow key={user.id} className="border-slate-800 hover:bg-slate-800/50">
                        <TableCell className="text-white">{user.email}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="border-slate-700 text-slate-300">
                            {user.role}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {user.must_change_password ? (
                            <Badge variant="outline" className="border-amber-700 text-amber-400 bg-amber-900/20">
                              Yes
                            </Badge>
                          ) : (
                            <span className="text-slate-500">No</span>
                          )}
                        </TableCell>
                        <TableCell className="text-slate-400 text-sm">
                          {user.created_at ? format(parseISO(user.created_at), 'MMM d, yyyy') : '—'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-slate-500 text-center py-8">No users found</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Impersonate Tab */}
        <TabsContent value="impersonate" className="space-y-6">
          <Card className="bg-slate-900 border-slate-800">
            <CardHeader>
              <CardTitle className="text-white">Support Impersonation</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-start gap-3 p-4 bg-amber-900/20 border border-amber-700 rounded-lg">
                <AlertCircle className="h-5 w-5 text-amber-400 mt-0.5" />
                <div className="text-sm text-amber-300">
                  <p className="font-semibold mb-1">Warning: This action is audit-logged</p>
                  <p>
                    Impersonation creates a temporary 15-minute session as super_admin in the tenant workspace.
                    All actions performed during this session are tracked in the audit log.
                  </p>
                </div>
              </div>

              <div className="flex justify-center py-8">
                <Button
                  size="lg"
                  onClick={handleImpersonate}
                  disabled={impersonateMutation.isPending}
                  className="bg-indigo-600 hover:bg-indigo-700"
                  data-testid="impersonate-button"
                >
                  <UserRoundCog className="h-5 w-5 mr-2" />
                  {impersonateMutation.isPending
                    ? 'Starting session...'
                    : 'Open workspace as super_admin (15 min session)'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default PlatformTenantDetail;
