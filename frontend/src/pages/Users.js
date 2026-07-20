import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getAllUsers, 
  getResources, 
  createResourceUser, 
  updateUserRole, 
  resetUserPassword,
  createClientUser,
  getClientUsers,
  updateClientUser,
  deleteClientUser,
  setUserStatus,
  deleteUser,
  getProjects
} from '../api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { Checkbox } from '../components/ui/checkbox';
import { UserPlus, Shield, User, AlertCircle, Key, Pencil, Trash2, Copy, Users as UsersIcon, Ban, UserCheck } from 'lucide-react';
import { toast } from 'sonner';

const Users = () => {
  const queryClient = useQueryClient();
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isCreateClientDialogOpen, setIsCreateClientDialogOpen] = useState(false);
  const [isEditClientDialogOpen, setIsEditClientDialogOpen] = useState(false);
  const [editingClient, setEditingClient] = useState(null);
  const [selectedResource, setSelectedResource] = useState('');
  const [email, setEmail] = useState('');
  
  // Client form states
  const [clientEmail, setClientEmail] = useState('');
  const [clientPassword, setClientPassword] = useState('');
  const [clientCompany, setClientCompany] = useState('');
  const [selectedProjects, setSelectedProjects] = useState([]);
  const [createdCredentials, setCreatedCredentials] = useState(null);

  const { data: users, isLoading: usersLoading } = useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      const response = await getAllUsers();
      return response.data;
    },
  });

  const { data: resources } = useQuery({
    queryKey: ['resources'],
    queryFn: async () => {
      const response = await getResources();
      return response.data;
    },
  });

  const { data: clients, isLoading: clientsLoading } = useQuery({
    queryKey: ['clientUsers'],
    queryFn: async () => {
      const response = await getClientUsers();
      return response.data;
    },
  });

  const { data: projects } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await getProjects();
      return response.data;
    },
  });

  const createUserMutation = useMutation({
    mutationFn: ({ resourceId, email }) => createResourceUser(resourceId, email),
    onSuccess: () => {
      toast.success('Resource user created successfully!');
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setIsCreateDialogOpen(false);
      setSelectedResource('');
      setEmail('');
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to create user');
    },
  });

  const createClientMutation = useMutation({
    mutationFn: (data) => createClientUser(data),
    onSuccess: (response) => {
      toast.success('Client user created successfully!');
      setCreatedCredentials({
        email: clientEmail,
        password: clientPassword
      });
      queryClient.invalidateQueries({ queryKey: ['clientUsers'] });
      setClientEmail('');
      setClientPassword('');
      setClientCompany('');
      setSelectedProjects([]);
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to create client user');
    },
  });

  const updateClientMutation = useMutation({
    mutationFn: ({ userId, data }) => updateClientUser(userId, data),
    onSuccess: () => {
      toast.success('Client updated successfully!');
      queryClient.invalidateQueries({ queryKey: ['clientUsers'] });
      setIsEditClientDialogOpen(false);
      setEditingClient(null);
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to update client');
    },
  });

  const deleteClientMutation = useMutation({
    mutationFn: (userId) => deleteClientUser(userId),
    onSuccess: () => {
      toast.success('Client deleted successfully!');
      queryClient.invalidateQueries({ queryKey: ['clientUsers'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to delete client');
    },
  });

  const updateRoleMutation = useMutation({
    mutationFn: ({ userId, newRole }) => updateUserRole(userId, newRole),
    onSuccess: () => {
      toast.success('User role updated successfully!');
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to update role');
    },
  });

  const resetPasswordMutation = useMutation({
    mutationFn: (userId) => resetUserPassword(userId),
    onSuccess: (data) => {
      toast.success(data.data.message || 'Password reset successfully');
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to reset password');
    },
  });

  const userStatusMutation = useMutation({
    mutationFn: ({ userId, disabled }) => setUserStatus(userId, disabled),
    onSuccess: (data) => {
      toast.success(data.data.message || 'User status updated');
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to update user status');
    },
  });

  const deleteUserMutation = useMutation({
    mutationFn: (userId) => deleteUser(userId),
    onSuccess: (data) => {
      toast.success(data.data.message || 'User deleted');
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to delete user');
    },
  });

  const handleToggleUserStatus = (user) => {
    const action = user.disabled ? 'enable' : 'disable';
    if (window.confirm(`Are you sure you want to ${action} ${user.email}?${user.disabled ? '' : ' They will be logged out and unable to sign in.'}`)) {
      userStatusMutation.mutate({ userId: user.id, disabled: !user.disabled });
    }
  };

  const handleDeleteUser = (user) => {
    if (window.confirm(`Permanently delete the login account for ${user.email}? Project history is not affected.`)) {
      deleteUserMutation.mutate(user.id);
    }
  };

  const generatePassword = () => {
    const numbers = Math.floor(Math.random() * 90000) + 10000;
    const password = `Client#${numbers}`;
    setClientPassword(password);
  };

  const handleCreateUser = (e) => {
    e.preventDefault();
    if (!selectedResource || !email) {
      toast.error('Please select a resource and enter an email');
      return;
    }
    createUserMutation.mutate({ resourceId: selectedResource, email });
  };

  const handleCreateClient = () => {
    if (!clientEmail || !clientPassword || !clientCompany) {
      toast.error('Please fill in all required fields (email, password, company name)');
      return;
    }
    createClientMutation.mutate({
      email: clientEmail,
      password: clientPassword,
      company_name: clientCompany,
      allowed_project_ids: selectedProjects
    });
  };

  const handleEditClient = (client) => {
    setEditingClient(client);
    setClientCompany(client.company_name);
    setSelectedProjects(client.allowed_project_ids || []);
    setClientPassword('');
    setIsEditClientDialogOpen(true);
  };

  const handleUpdateClient = () => {
    if (!editingClient || !clientCompany) {
      toast.error('Please fill in required fields');
      return;
    }
    
    const updateData = {
      company_name: clientCompany,
      allowed_project_ids: selectedProjects
    };
    
    if (clientPassword) {
      updateData.password = clientPassword;
    }

    updateClientMutation.mutate({ 
      userId: editingClient.id, 
      data: updateData 
    });
  };

  const handleDeleteClient = (client) => {
    if (window.confirm(`Are you sure you want to delete ${client.email}?`)) {
      deleteClientMutation.mutate(client.id);
    }
  };

  const handleResetPassword = (userId) => {
    if (window.confirm('Are you sure you want to reset this user\'s password to "Welcome123!"?')) {
      resetPasswordMutation.mutate(userId);
    }
  };

  const handleRoleChange = (userId, newRole) => {
    updateRoleMutation.mutate({ userId, newRole });
  };

  const handleProjectSelection = (projectId, checked) => {
    if (checked) {
      setSelectedProjects([...selectedProjects, projectId]);
    } else {
      setSelectedProjects(selectedProjects.filter(id => id !== projectId));
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard!');
  };

  const getRoleBadge = (role) => {
    const roleColors = {
      super_admin: 'bg-[#EF4444] text-white',
      admin: 'bg-[#F4B740] text-white',
      resource: 'bg-[#1570EF] text-white',
      client: 'bg-[#667085] text-white',
    };
    const roleLabels = {
      super_admin: 'Super Admin',
      admin: 'Admin',
      resource: 'Resource User',
      client: 'Client',
    };
    return (
      <Badge className={roleColors[role] || 'bg-gray-500'}>
        {roleLabels[role] || role}
      </Badge>
    );
  };

  const getResourceName = (resourceId) => {
    if (!resourceId || !resources) return '-';
    const resource = resources.find(r => r.id === resourceId);
    return resource?.name || '-';
  };

  const getProjectNames = (projectIds) => {
    if (!projectIds || !projects) return [];
    return projects.filter(p => projectIds.includes(p.id));
  };

  const resetCreateClientForm = () => {
    setClientEmail('');
    setClientPassword('');
    setClientCompany('');
    setSelectedProjects([]);
    setCreatedCredentials(null);
    setIsCreateClientDialogOpen(false);
  };

  const resetEditClientForm = () => {
    setClientCompany('');
    setClientPassword('');
    setSelectedProjects([]);
    setEditingClient(null);
    setIsEditClientDialogOpen(false);
  };

  if (usersLoading) {
    return <div className="p-6">Loading users...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold" style={{ fontFamily: 'Space Grotesk' }}>
            User Management
          </h1>
          <p className="text-sm text-[#667085] mt-1">
            Manage user accounts and roles
          </p>
        </div>
      </div>

      <Tabs defaultValue="resource" className="space-y-6">
        <TabsList className="grid w-full grid-cols-2 max-w-[400px]">
          <TabsTrigger value="resource" data-testid="resource-tab">Resource Users</TabsTrigger>
          <TabsTrigger value="client" data-testid="client-tab">Client Accounts</TabsTrigger>
        </TabsList>

        {/* Resource Users Tab */}
        <TabsContent value="resource" className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold" style={{ fontFamily: 'Space Grotesk' }}>
                Resource Users
              </h2>
              <p className="text-sm text-[#667085]">Internal team members and contractors</p>
            </div>
            
            <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
              <DialogTrigger asChild>
                <Button className="bg-[#1570EF] hover:bg-[#0E5FD9]" data-testid="create-user-btn">
                  <UserPlus size={16} className="mr-2" />
                  Create Resource User
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create Resource User</DialogTitle>
                  <DialogDescription>
                    Create a user account linked to a resource. Default password: Welcome123!
                  </DialogDescription>
                </DialogHeader>
                <form onSubmit={handleCreateUser} className="space-y-4">
                  <div>
                    <Label htmlFor="resource">Select Resource</Label>
                    <Select value={selectedResource} onValueChange={setSelectedResource}>
                      <SelectTrigger>
                        <SelectValue placeholder="Choose a resource" />
                      </SelectTrigger>
                      <SelectContent>
                        {resources?.filter((resource) => resource.active !== false).map((resource) => (
                          <SelectItem key={resource.id} value={resource.id}>
                            {resource.name} - {resource.role}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label htmlFor="email">Email Address</Label>
                    <Input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="user@ddconsult.tech"
                      required
                    />
                  </div>

                  <div className="bg-[#FFF8E5] border border-[#F4B740] rounded p-3 text-sm">
                    <p className="text-[#7A4E00]">
                      <strong>Default Password:</strong> Welcome123!
                      <br />
                      User will be required to change password on first login.
                    </p>
                  </div>

                  <Button type="submit" className="w-full" disabled={createUserMutation.isLoading}>
                    {createUserMutation.isLoading ? 'Creating...' : 'Create User'}
                  </Button>
                </form>
              </DialogContent>
            </Dialog>
          </div>

          <Card>
            <CardHeader>
              <CardTitle style={{ fontFamily: 'Space Grotesk' }}>All Users</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow className="bg-[#F8FAFC]">
                    <TableHead className="font-semibold">Email</TableHead>
                    <TableHead className="font-semibold">Role</TableHead>
                    <TableHead className="font-semibold">Linked Resource</TableHead>
                    <TableHead className="font-semibold">Status</TableHead>
                    <TableHead className="font-semibold">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users?.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell className="font-medium">{user.email}</TableCell>
                      <TableCell>{getRoleBadge(user.role)}</TableCell>
                      <TableCell>{getResourceName(user.resource_id)}</TableCell>
                      <TableCell>
                        {user.disabled ? (
                          <Badge variant="outline" className="border-[#D92D20] text-[#B42318]" data-testid={`user-status-disabled-${user.id}`}>
                            <AlertCircle size={12} className="mr-1" />
                            Disabled
                          </Badge>
                        ) : user.must_change_password ? (
                          <Badge variant="outline" className="border-[#F4B740] text-[#7A4E00]">
                            <AlertCircle size={12} className="mr-1" />
                            Password Reset Required
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="border-[#16B364] text-[#065F46]">
                            Active
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Select
                            value={user.role}
                            onValueChange={(newRole) => handleRoleChange(user.id, newRole)}
                          >
                            <SelectTrigger className="w-[140px]">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="super_admin">Super Admin</SelectItem>
                              <SelectItem value="admin">Admin</SelectItem>
                              <SelectItem value="resource">Resource User</SelectItem>
                              <SelectItem value="contractor">Contractor</SelectItem>
                              <SelectItem value="client">Client</SelectItem>
                            </SelectContent>
                          </Select>
                          <Button 
                            variant="outline" 
                            size="icon" 
                            onClick={() => handleResetPassword(user.id)}
                            title="Reset Password to Default"
                            className="h-9 w-9"
                          >
                            <Key size={14} />
                          </Button>
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => handleToggleUserStatus(user)}
                            title={user.disabled ? 'Enable account' : 'Disable account (blocks login immediately)'}
                            className={`h-9 w-9 ${user.disabled ? 'text-[#067647]' : 'text-[#B54708]'}`}
                            data-testid={`toggle-user-status-${user.id}`}
                          >
                            {user.disabled ? <UserCheck size={14} /> : <Ban size={14} />}
                          </Button>
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => handleDeleteUser(user)}
                            title="Delete login account (project history unaffected)"
                            className="h-9 w-9 text-[#B42318]"
                            data-testid={`delete-user-${user.id}`}
                          >
                            <Trash2 size={14} />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {users?.length === 0 && (
                <div className="text-center py-12 text-[#667085]">
                  <User size={48} className="mx-auto mb-4 text-[#98A2B3]" />
                  <p>No users found</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Client Accounts Tab */}
        <TabsContent value="client" className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold" style={{ fontFamily: 'Space Grotesk' }}>
                Client Accounts
              </h2>
              <p className="text-sm text-[#667085]">External client users with project access</p>
            </div>
            
            <Dialog open={isCreateClientDialogOpen} onOpenChange={setIsCreateClientDialogOpen}>
              <DialogTrigger asChild>
                <Button className="bg-[#1570EF] hover:bg-[#0E5FD9]" data-testid="add-client-btn">
                  <UsersIcon size={16} className="mr-2" />
                  Add Client
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-md">
                <DialogHeader>
                  <DialogTitle>Add Client User</DialogTitle>
                  <DialogDescription>
                    Create a client account with project access
                  </DialogDescription>
                </DialogHeader>

                {createdCredentials ? (
                  <div className="space-y-4">
                    <div className="bg-[#ECFDF5] border border-[#16B364] rounded p-4">
                      <h3 className="font-semibold text-[#065F46] mb-2">Client Created Successfully!</h3>
                      <div className="space-y-2 text-sm">
                        <div>
                          <span className="font-medium">Email: </span>
                          <span className="text-[#374151]">{createdCredentials.email}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">Password: </span>
                          <span className="text-[#374151] font-mono">{createdCredentials.password}</span>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => copyToClipboard(createdCredentials.password)}
                            className="h-6 w-6 p-0"
                          >
                            <Copy size={12} />
                          </Button>
                        </div>
                      </div>
                    </div>
                    <Button onClick={resetCreateClientForm} className="w-full">
                      Add Another Client
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div>
                      <Label htmlFor="clientEmail">Email Address *</Label>
                      <Input
                        id="clientEmail"
                        type="email"
                        value={clientEmail}
                        onChange={(e) => setClientEmail(e.target.value)}
                        placeholder="client@company.com"
                      />
                    </div>

                    <div>
                      <Label htmlFor="clientPassword">Password *</Label>
                      <div className="flex gap-2">
                        <Input
                          id="clientPassword"
                          type="text"
                          value={clientPassword}
                          onChange={(e) => setClientPassword(e.target.value)}
                          placeholder="Enter password"
                        />
                        <Button
                          type="button"
                          variant="outline"
                          onClick={generatePassword}
                          className="px-3"
                        >
                          Generate
                        </Button>
                      </div>
                    </div>

                    <div>
                      <Label htmlFor="clientCompany">Company Name *</Label>
                      <Input
                        id="clientCompany"
                        type="text"
                        value={clientCompany}
                        onChange={(e) => setClientCompany(e.target.value)}
                        placeholder="Company Inc."
                      />
                    </div>

                    <div>
                      <Label>Assigned Projects</Label>
                      <div className="max-h-32 overflow-y-auto border rounded p-2 space-y-2">
                        {projects?.map((project) => (
                          <div key={project.id} className="flex items-center space-x-2">
                            <Checkbox
                              id={`project-${project.id}`}
                              checked={selectedProjects.includes(project.id)}
                              onCheckedChange={(checked) => handleProjectSelection(project.id, checked)}
                            />
                            <Label htmlFor={`project-${project.id}`} className="text-sm">
                              {project.name}
                            </Label>
                          </div>
                        ))}
                      </div>
                    </div>

                    <Button
                      type="button"
                      className="w-full"
                      disabled={createClientMutation.isPending || createClientMutation.isLoading}
                      onClick={handleCreateClient}
                      data-testid="create-client-submit-btn"
                    >
                      {(createClientMutation.isPending || createClientMutation.isLoading) ? 'Creating...' : 'Create Client'}
                    </Button>
                  </div>
                )}
              </DialogContent>
            </Dialog>
          </div>

          <Card>
            <CardContent className="p-0">
              {clientsLoading ? (
                <div className="p-6 text-center">Loading client accounts...</div>
              ) : clients?.length === 0 ? (
                <div className="p-12 text-center text-[#667085]">
                  <UsersIcon size={48} className="mx-auto mb-4 text-[#98A2B3]" />
                  <p>No client accounts yet</p>
                  <p className="text-sm mt-1">Create your first client account to get started</p>
                </div>
              ) : (
                <Table data-testid="client-table">
                  <TableHeader>
                    <TableRow className="bg-[#F8FAFC]">
                      <TableHead className="font-semibold">Email</TableHead>
                      <TableHead className="font-semibold">Company</TableHead>
                      <TableHead className="font-semibold">Assigned Projects</TableHead>
                      <TableHead className="font-semibold">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {clients?.map((client) => {
                      const assignedProjects = getProjectNames(client.allowed_project_ids || []);
                      return (
                        <TableRow key={client.id}>
                          <TableCell className="font-medium">{client.email}</TableCell>
                          <TableCell>{client.company_name}</TableCell>
                          <TableCell>
                            <div className="flex flex-wrap gap-1">
                              {assignedProjects.slice(0, 3).map((project) => (
                                <Badge key={project.id} variant="outline" className="text-xs">
                                  {project.name}
                                </Badge>
                              ))}
                              {assignedProjects.length > 3 && (
                                <Badge variant="outline" className="text-xs">
                                  +{assignedProjects.length - 3} more
                                </Badge>
                              )}
                              {assignedProjects.length === 0 && (
                                <span className="text-[#667085] text-sm">No projects</span>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Button
                                variant="outline"
                                size="icon"
                                onClick={() => handleEditClient(client)}
                                className="h-8 w-8"
                                title="Edit client"
                              >
                                <Pencil size={14} />
                              </Button>
                              <Button
                                variant="outline"
                                size="icon"
                                onClick={() => handleDeleteClient(client)}
                                className="h-8 w-8 text-[#EF4444] hover:text-[#DC2626]"
                                title="Delete client"
                              >
                                <Trash2 size={14} />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Edit Client Dialog */}
      <Dialog open={isEditClientDialogOpen} onOpenChange={setIsEditClientDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Client</DialogTitle>
            <DialogDescription>
              Update client information and project access
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="editClientCompany">Company Name</Label>
              <Input
                id="editClientCompany"
                type="text"
                value={clientCompany}
                onChange={(e) => setClientCompany(e.target.value)}
              />
            </div>

            <div>
              <Label>Assigned Projects</Label>
              <div className="max-h-32 overflow-y-auto border rounded p-2 space-y-2">
                {projects?.map((project) => (
                  <div key={project.id} className="flex items-center space-x-2">
                    <Checkbox
                      id={`edit-project-${project.id}`}
                      checked={selectedProjects.includes(project.id)}
                      onCheckedChange={(checked) => handleProjectSelection(project.id, checked)}
                    />
                    <Label htmlFor={`edit-project-${project.id}`} className="text-sm">
                      {project.name}
                    </Label>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <Label htmlFor="editClientPassword">New Password (optional)</Label>
              <div className="flex gap-2">
                <Input
                  id="editClientPassword"
                  type="text"
                  value={clientPassword}
                  onChange={(e) => setClientPassword(e.target.value)}
                  placeholder="Leave empty to keep current password"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={generatePassword}
                  className="px-3"
                >
                  Generate
                </Button>
              </div>
            </div>

            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={resetEditClientForm}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button 
                type="button"
                className="flex-1" 
                disabled={updateClientMutation.isPending || updateClientMutation.isLoading}
                onClick={handleUpdateClient}
                data-testid="update-client-btn"
              >
                {(updateClientMutation.isPending || updateClientMutation.isLoading) ? 'Updating...' : 'Update Client'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Users;