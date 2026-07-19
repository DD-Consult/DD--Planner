import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getResources, createResource, updateResource, deleteResource, getMe } from '../api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '../components/ui/dialog';
import { Avatar, AvatarImage, AvatarFallback } from '../components/ui/avatar';
import { Plus, Edit, Trash2 } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';

const Resources = ({ token }) => {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingResource, setEditingResource] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    role: '',
    standard_capacity: 100,
    avatar_url: '',
  });

  const queryClient = useQueryClient();

  const { data: userData } = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const response = await getMe();
      return response.data;
    },
  });

  const { data: resources, isLoading } = useQuery({
    queryKey: ['resources'],
    queryFn: async () => {
      const response = await getResources();
      return response.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: createResource,
    onSuccess: () => {
      queryClient.invalidateQueries(['resources']);
      setIsDialogOpen(false);
      resetForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateResource(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['resources']);
      setIsDialogOpen(false);
      resetForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteResource,
    onSuccess: () => {
      queryClient.invalidateQueries(['resources']);
    },
  });

  const resetForm = () => {
    setFormData({ name: '', role: '', standard_capacity: 100, avatar_url: '' });
    setEditingResource(null);
  };

  const handleOpenDialog = (resource = null) => {
    if (resource) {
      setEditingResource(resource);
      setFormData({
        name: resource.name,
        role: resource.role,
        standard_capacity: resource.standard_capacity,
        avatar_url: resource.avatar_url || '',
      });
    } else {
      resetForm();
    }
    setIsDialogOpen(true);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (editingResource) {
      updateMutation.mutate({ id: editingResource.id, data: formData });
    } else {
      createMutation.mutate(formData);
    }
  };

  const handleDelete = (id) => {
    if (window.confirm('Are you sure you want to delete this resource?')) {
      deleteMutation.mutate(id);
    }
  };

  const isAdmin = userData?.role === 'admin' || userData?.role === 'super_admin';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold" style={{ fontFamily: 'Space Grotesk' }}>
            Resources
          </h1>
          <p className="text-sm text-[#667085] mt-1">Manage team members and their capacities</p>
        </div>
        {isAdmin && (
          <Button onClick={() => handleOpenDialog()} data-testid="add-resource-button">
            <Plus size={16} className="mr-2" />
            Add Resource
          </Button>
        )}
      </div>

      {/* Resources Table */}
      {isLoading ? (
        <div className="text-center py-12 text-[#667085]">
          <p>Loading resources...</p>
        </div>
      ) : (
        <div className="bg-white border border-[#E6E8EC] rounded-lg overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Resource</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Standard Capacity</TableHead>
                {isAdmin && <TableHead className="text-right">Actions</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {resources?.map((resource) => (
                <TableRow key={resource.id} data-testid={`resource-${resource.id}`}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <Avatar className="w-10 h-10">
                        <AvatarImage src={resource.avatar_url} />
                        <AvatarFallback>{resource.name.charAt(0)}</AvatarFallback>
                      </Avatar>
                      <span className="font-medium">{resource.name}</span>
                    </div>
                  </TableCell>
                  <TableCell>{resource.role}</TableCell>
                  <TableCell>{resource.standard_capacity}%</TableCell>
                  {isAdmin && (
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleOpenDialog(resource)}
                          data-testid={`edit-resource-${resource.id}`}
                        >
                          <Edit size={14} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(resource.id)}
                          data-testid={`delete-resource-${resource.id}`}
                        >
                          <Trash2 size={14} />
                        </Button>
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent data-testid="resource-dialog">
          <DialogHeader>
            <DialogTitle>{editingResource ? 'Edit Resource' : 'Add New Resource'}</DialogTitle>
            <DialogDescription>
              {editingResource
                ? 'Update resource information'
                : 'Add a new team member to track their capacity'}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4 mt-4">
            <div>
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
                data-testid="resource-name-input"
              />
            </div>

            <div>
              <Label htmlFor="role">Role</Label>
              <Input
                id="role"
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                required
                data-testid="resource-role-input"
              />
            </div>

            <div>
              <Label htmlFor="standard_capacity">Standard Capacity (%)</Label>
              <Input
                id="standard_capacity"
                type="number"
                min="0"
                max="100"
                value={formData.standard_capacity}
                onChange={(e) =>
                  setFormData({ ...formData, standard_capacity: parseInt(e.target.value) })
                }
                required
                data-testid="resource-capacity-input"
              />
            </div>

            <div>
              <Label htmlFor="avatar_url">Avatar URL (optional)</Label>
              <Input
                id="avatar_url"
                type="url"
                value={formData.avatar_url}
                onChange={(e) => setFormData({ ...formData, avatar_url: e.target.value })}
                data-testid="resource-avatar-input"
              />
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsDialogOpen(false)}
                data-testid="cancel-button"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={createMutation.isLoading || updateMutation.isLoading}
                data-testid="submit-resource"
              >
                {createMutation.isLoading || updateMutation.isLoading
                  ? 'Saving...'
                  : editingResource
                  ? 'Update'
                  : 'Create'}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Resources;
