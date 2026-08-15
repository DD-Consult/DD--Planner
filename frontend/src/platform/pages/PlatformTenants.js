import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getTenants, createTenant, deleteTenant, updateTenant, impersonateTenant } from '../api';
import { setAuthToken } from '../../api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../../components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui/table';
import { Search, Plus, Eye, UserRoundCog, Ban, CheckCircle, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

const PlatformTenants = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  
  // Form states
  const [slug, setSlug] = useState('');
  const [name, setName] = useState('');
  const [ownerEmail, setOwnerEmail] = useState('');
  const [ownerPassword, setOwnerPassword] = useState('');

  const { data: tenants, isLoading } = useQuery({
    queryKey: ['platformTenants'],
    queryFn: async () => {
      const response = await getTenants();
      return response.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: (data) => createTenant(data),
    onSuccess: () => {
      queryClient.invalidateQueries(['platformTenants']);
      toast.success('Tenant created successfully');
      setIsCreateDialogOpen(false);
      resetForm();
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ slug, status }) => updateTenant(slug, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries(['platformTenants']);
      toast.success('Tenant status updated');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (slug) => deleteTenant(slug),
    onSuccess: () => {
      queryClient.invalidateQueries(['platformTenants']);
      toast.success('Tenant deleted');
    },
    onError: (error) => {
      // Error already handled by interceptor
    },
  });

  const impersonateMutation = useMutation({
    mutationFn: (slug) => impersonateTenant(slug),
    onSuccess: (response) => {
      const tenantToken = response.data.access_token;
      // Store tenant token and open in new tab
      localStorage.setItem('token', tenantToken);
      setAuthToken(tenantToken);
      window.open('/', '_blank');
      toast.success('Impersonation session started (15 min)', { duration: 3000 });
    },
  });

  const resetForm = () => {
    setSlug('');
    setName('');
    setOwnerEmail('');
    setOwnerPassword('');
  };

  const handleSlugChange = (value) => {
    // Auto-format to lowercase with hyphens
    const formatted = value.toLowerCase().replace(/[^a-z0-9-]/g, '');
    setSlug(formatted);
  };

  const handleCreate = () => {
    if (!slug || !name || !ownerEmail || !ownerPassword) {
      toast.error('All fields are required');
      return;
    }
    
    createMutation.mutate({
      slug,
      name,
      owner_email: ownerEmail,
      owner_password: ownerPassword,
    });
  };

  const handleToggleStatus = (tenant) => {
    const newStatus = tenant.status === 'active' ? 'suspended' : 'active';
    updateStatusMutation.mutate({ slug: tenant.slug, status: newStatus });
  };

  const handleDelete = (tenant) => {
    if (window.confirm(`Are you sure you want to delete tenant "${tenant.name}"? This action cannot be undone.`)) {
      deleteMutation.mutate(tenant.slug);
    }
  };

  const handleImpersonate = (tenant) => {
    if (window.confirm(`Start impersonation session for "${tenant.name}"? This will be audit-logged.`)) {
      impersonateMutation.mutate(tenant.slug);
    }
  };

  const filteredTenants = tenants?.filter((t) =>
    t.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    t.slug.toLowerCase().includes(searchTerm.toLowerCase()) ||
    t.owner_email?.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2" data-testid="tenants-title">
            Tenants
          </h1>
          <p className="text-slate-400">Manage all tenant workspaces</p>
        </div>
        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button className="bg-indigo-600 hover:bg-indigo-700" data-testid="create-tenant-button">
              <Plus className="h-4 w-4 mr-2" />
              New Tenant
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-slate-900 border-slate-800 text-white">
            <DialogHeader>
              <DialogTitle>Create New Tenant</DialogTitle>
              <DialogDescription className="text-slate-400">
                Set up a new tenant workspace with an owner account.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div>
                <Label htmlFor="slug" className="text-slate-300">Slug (URL identifier)</Label>
                <Input
                  id="slug"
                  placeholder="acme-corp"
                  value={slug}
                  onChange={(e) => handleSlugChange(e.target.value)}
                  className="bg-slate-800 border-slate-700 text-white"
                  data-testid="tenant-slug-input"
                />
                <p className="text-xs text-slate-500 mt-1">Lowercase letters, numbers, and hyphens only</p>
              </div>
              <div>
                <Label htmlFor="name" className="text-slate-300">Tenant Name</Label>
                <Input
                  id="name"
                  placeholder="Acme Corporation"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="bg-slate-800 border-slate-700 text-white"
                  data-testid="tenant-name-input"
                />
              </div>
              <div>
                <Label htmlFor="ownerEmail" className="text-slate-300">Owner Email</Label>
                <Input
                  id="ownerEmail"
                  type="email"
                  placeholder="admin@acme.com"
                  value={ownerEmail}
                  onChange={(e) => setOwnerEmail(e.target.value)}
                  className="bg-slate-800 border-slate-700 text-white"
                  data-testid="tenant-owner-email-input"
                />
              </div>
              <div>
                <Label htmlFor="ownerPassword" className="text-slate-300">Owner Password</Label>
                <Input
                  id="ownerPassword"
                  type="password"
                  placeholder="Strong password"
                  value={ownerPassword}
                  onChange={(e) => setOwnerPassword(e.target.value)}
                  className="bg-slate-800 border-slate-700 text-white"
                  data-testid="tenant-owner-password-input"
                />
              </div>
              <div className="flex justify-end gap-2 mt-6">
                <Button
                  variant="outline"
                  onClick={() => {
                    setIsCreateDialogOpen(false);
                    resetForm();
                  }}
                  className="border-slate-700 text-slate-300 hover:bg-slate-800"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleCreate}
                  disabled={createMutation.isPending}
                  className="bg-indigo-600 hover:bg-indigo-700"
                  data-testid="tenant-create-submit"
                >
                  {createMutation.isPending ? 'Creating...' : 'Create Tenant'}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Search */}
      <Card className="bg-slate-900 border-slate-800">
        <CardContent className="p-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-500" />
            <Input
              placeholder="Search tenants by name, slug, or owner email..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10 bg-slate-800 border-slate-700 text-white placeholder:text-slate-500"
              data-testid="tenants-search-input"
            />
          </div>
        </CardContent>
      </Card>

      {/* Tenants Table */}
      <Card className="bg-slate-900 border-slate-800">
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-slate-400">Loading tenants...</p>
            </div>
          ) : filteredTenants.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-slate-500">No tenants found</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-slate-800 hover:bg-slate-800/50">
                  <TableHead className="text-slate-400">Slug</TableHead>
                  <TableHead className="text-slate-400">Name</TableHead>
                  <TableHead className="text-slate-400">Status</TableHead>
                  <TableHead className="text-slate-400">Owner Email</TableHead>
                  <TableHead className="text-slate-400">Modules</TableHead>
                  <TableHead className="text-slate-400 text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredTenants.map((tenant) => (
                  <TableRow key={tenant.slug} className="border-slate-800 hover:bg-slate-800/50">
                    <TableCell className="font-mono text-sm text-slate-300">{tenant.slug}</TableCell>
                    <TableCell className="text-white font-medium">{tenant.name}</TableCell>
                    <TableCell>
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
                    </TableCell>
                    <TableCell className="text-slate-300 text-sm">{tenant.owner_email || '—'}</TableCell>
                    <TableCell className="text-slate-400 text-sm">
                      {tenant.enabled_modules_count || 0} enabled
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-slate-400 hover:text-white hover:bg-slate-800"
                          onClick={() => navigate(`/platform/tenants/${tenant.slug}`)}
                          data-testid={`view-tenant-${tenant.slug}`}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-indigo-400 hover:text-indigo-300 hover:bg-slate-800"
                          onClick={() => handleImpersonate(tenant)}
                          disabled={impersonateMutation.isPending}
                          data-testid={`impersonate-tenant-${tenant.slug}`}
                        >
                          <UserRoundCog className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className={
                            tenant.status === 'active'
                              ? 'text-amber-400 hover:text-amber-300 hover:bg-slate-800'
                              : 'text-green-400 hover:text-green-300 hover:bg-slate-800'
                          }
                          onClick={() => handleToggleStatus(tenant)}
                          disabled={updateStatusMutation.isPending}
                          data-testid={`toggle-status-${tenant.slug}`}
                        >
                          {tenant.status === 'active' ? <Ban className="h-4 w-4" /> : <CheckCircle className="h-4 w-4" />}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-red-400 hover:text-red-300 hover:bg-slate-800"
                          onClick={() => handleDelete(tenant)}
                          disabled={deleteMutation.isPending || tenant.is_default}
                          data-testid={`delete-tenant-${tenant.slug}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default PlatformTenants;
