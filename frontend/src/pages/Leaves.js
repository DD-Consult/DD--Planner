import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getLeaves, deleteLeave, getResources, getMyResource, getPendingLeaves, approveLeave, rejectLeave } from '../api';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { CalendarOff, Plus, Trash2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { format } from 'date-fns';
import { AddLeaveDialog } from '../components/AddLeaveDialog';
import { useQuery as useMe } from '@tanstack/react-query';
import { getMe } from '../api';

const Leaves = () => {
  const queryClient = useQueryClient();
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  // Get current user role
  const { data: meData } = useMe({
    queryKey: ['me'],
    queryFn: async () => {
      const res = await getMe();
      return res.data;
    },
  });
  const isAdmin = meData?.role === 'admin' || meData?.role === 'super_admin';
  const isResource = !isAdmin && (meData?.role === 'resource' || meData?.role === 'contractor');

  // Fetch pending leaves for admin approval queue
  const { data: pendingLeaves } = useQuery({
    queryKey: ['pendingLeaves'],
    queryFn: async () => {
      const response = await getPendingLeaves();
      return response.data;
    },
    enabled: isAdmin,
  });

  // Fetch leaves (backend already scopes for non-admins)
  const { data: leaves, isLoading: leavesLoading } = useQuery({
    queryKey: ['leaves'],
    queryFn: async () => {
      const response = await getLeaves();
      return response.data;
    },
  });

  // Fetch resources for the dialog — admins get full list, resources get own
  const { data: resources } = useQuery({
    queryKey: ['resources'],
    queryFn: async () => {
      const response = await getResources();
      return response.data;
    },
    enabled: isAdmin,
  });

  // Resource user: fetch own resource profile for the dialog
  const { data: ownResourceData } = useQuery({
    queryKey: ['myResource'],
    queryFn: async () => {
      const res = await getMyResource();
      return res.data;
    },
    enabled: isResource,
  });

  // Build resource list for AddLeaveDialog
  const dialogResources = isAdmin
    ? (resources || []).filter((r) => r.active !== false)
    : ownResourceData
    ? [{ id: ownResourceData.id, name: ownResourceData.name, role: ownResourceData.role }]
    : [];

  // Delete leave mutation
  const deleteMutation = useMutation({
    mutationFn: deleteLeave,
    onSuccess: () => {
      toast.success('Leave deleted');
      queryClient.invalidateQueries({ queryKey: ['leaves'] });
      queryClient.invalidateQueries({ queryKey: ['capacity'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to delete leave');
    },
  });

  // Approve leave mutation
  const approveMutation = useMutation({
    mutationFn: ({ id, note }) => approveLeave(id, note),
    onSuccess: () => {
      toast.success('Leave approved');
      queryClient.invalidateQueries({ queryKey: ['pendingLeaves'] });
      queryClient.invalidateQueries({ queryKey: ['leaves'] });
      queryClient.invalidateQueries({ queryKey: ['capacity'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to approve leave');
    },
  });

  // Reject leave mutation
  const rejectMutation = useMutation({
    mutationFn: ({ id, note }) => rejectLeave(id, note),
    onSuccess: () => {
      toast.success('Leave rejected');
      queryClient.invalidateQueries({ queryKey: ['pendingLeaves'] });
      queryClient.invalidateQueries({ queryKey: ['leaves'] });
      queryClient.invalidateQueries({ queryKey: ['capacity'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to reject leave');
    },
  });

  const handleDelete = (id) => {
    if (window.confirm('Are you sure you want to delete this time off entry?')) {
      deleteMutation.mutate(id);
    }
  };

  const handleApprove = (id) => {
    approveMutation.mutate({ id, note: null });
  };

  const handleReject = (id) => {
    const reason = window.prompt('Optional reason for rejection:');
    // User can cancel (null) or provide empty/non-empty string
    if (reason !== null) {
      rejectMutation.mutate({ id, note: reason || undefined });
    }
  };

  const getLeaveTypeColor = (type) => {
    const colors = {
      vacation: 'bg-[#E6F7FB] text-[#0B5566] border-[#B2E7F5]',
      'Annual Leave': 'bg-[#E6F7FB] text-[#0B5566] border-[#B2E7F5]',
      sick: 'bg-[#FFF8E5] text-[#7A4E00] border-[#FCD34D]',
      'Sick Leave': 'bg-[#FFF8E5] text-[#7A4E00] border-[#FCD34D]',
      personal: 'bg-[#F0F2F5] text-[#475467] border-[#D0D5DD]',
      other: 'bg-[#F7F7F8] text-[#667085] border-[#E6E8EC]',
    };
    return colors[type] || colors.other;
  };

  const getStatusColor = (status) => {
    const normalizedStatus = (status || 'Approved').toLowerCase();
    if (normalizedStatus === 'pending') return 'bg-amber-100 text-amber-700 border-amber-200';
    if (normalizedStatus === 'approved') return 'bg-green-100 text-green-700 border-green-200';
    if (normalizedStatus === 'rejected') return 'bg-red-100 text-red-700 border-red-200';
    return 'bg-green-100 text-green-700 border-green-200'; // default to approved for legacy
  };

  const getResourceName = (resourceId) => {
    if (ownResourceData && ownResourceData.id === resourceId) return ownResourceData.name;
    const resource = resources?.find((r) => r.id === resourceId);
    return resource ? `${resource.name} (${resource.role})` : resourceId;
  };

  return (
    <div className="space-y-6" data-testid="leaves-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold flex items-center gap-3" style={{ fontFamily: 'Space Grotesk' }}>
            <CalendarOff size={32} />
            {isAdmin ? 'Time Off Management' : 'My Time Off'}
          </h1>
          <p className="text-sm text-[#667085] mt-1">
            {isAdmin
              ? 'Manage vacation, sick leave, and other time off for resources'
              : 'Submit time off requests for manager approval'}
          </p>
        </div>
        <Button
          onClick={() => setIsDialogOpen(true)}
          data-testid="add-leave-button"
          disabled={isResource && !ownResourceData}
        >
          <Plus size={16} className="mr-2" />
          {isResource ? 'Request Time Off' : 'Add Time Off'}
        </Button>
      </div>

      {/* Pending Approvals Section (Admin Only) */}
      {isAdmin && pendingLeaves && pendingLeaves.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4" data-testid="pending-approvals-section">
          <h2 className="text-lg font-semibold mb-3 text-amber-900" style={{ fontFamily: 'Space Grotesk' }}>
            Pending Approvals ({pendingLeaves.length})
          </h2>
          <div className="space-y-3">
            {pendingLeaves.map((leave) => (
              <div
                key={leave._id || leave.id}
                className="bg-white border border-amber-200 rounded-md p-3 flex items-center justify-between"
                data-testid={`pending-leave-${leave._id || leave.id}`}
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium text-[#0B1220]">{leave.resource_name}</span>
                    <Badge className={getLeaveTypeColor(leave.type)}>
                      {leave.type}
                    </Badge>
                  </div>
                  <div className="text-sm text-[#667085]">
                    {format(new Date(leave.start_date), 'MMM d, yyyy')} → {format(new Date(leave.end_date), 'MMM d, yyyy')}
                  </div>
                  {leave.notes && (
                    <div className="text-xs text-[#667085] mt-1 italic">&quot;{leave.notes}&quot;</div>
                  )}
                </div>
                <div className="flex items-center gap-2 ml-4">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleApprove(leave._id || leave.id)}
                    disabled={approveMutation.isPending || rejectMutation.isPending}
                    data-testid={`approve-leave-${leave._id || leave.id}`}
                    className="bg-green-50 hover:bg-green-100 text-green-700 border-green-300"
                  >
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleReject(leave._id || leave.id)}
                    disabled={approveMutation.isPending || rejectMutation.isPending}
                    data-testid={`reject-leave-${leave._id || leave.id}`}
                    className="bg-red-50 hover:bg-red-100 text-red-700 border-red-300"
                  >
                    Reject
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Leaves Table */}
      <div className="bg-white border border-[#E6E8EC] rounded-lg">
        {leavesLoading ? (
          <div className="p-8 text-center text-[#667085]">
            <Loader2 className="animate-spin mx-auto mb-2" size={24} />
            Loading time off entries...
          </div>
        ) : leaves?.length === 0 ? (
          <div className="p-8 text-center">
            <CalendarOff size={48} className="mx-auto mb-4 text-[#98A2B3]" />
            <p className="text-[#667085] mb-4">No time off entries yet</p>
            <Button variant="outline" onClick={() => setIsDialogOpen(true)}>
              <Plus size={16} className="mr-2" />
              Add First Time Off
            </Button>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                {isAdmin && <TableHead>Resource</TableHead>}
                <TableHead>Type</TableHead>
                <TableHead>Start Date</TableHead>
                <TableHead>End Date</TableHead>
                <TableHead>Notes</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {leaves?.map((leave) => (
                <TableRow key={leave._id || leave.id} data-testid={`leave-row-${leave._id || leave.id}`}>
                  {isAdmin && (
                    <TableCell className="font-medium">
                      {getResourceName(leave.resource_id)}
                    </TableCell>
                  )}
                  <TableCell>
                    <Badge className={getLeaveTypeColor(leave.type)}>
                      {leave.type}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {format(new Date(leave.start_date), 'MMM d, yyyy')}
                  </TableCell>
                  <TableCell>
                    {format(new Date(leave.end_date), 'MMM d, yyyy')}
                  </TableCell>
                  <TableCell className="text-[#667085] text-sm">
                    {leave.notes || '—'}
                  </TableCell>
                  <TableCell>
                    <Badge
                      className={getStatusColor(leave.status)}
                      data-testid={`leave-status-${leave._id || leave.id}`}
                    >
                      {(leave.status || 'Approved')}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(leave._id || leave.id)}
                      disabled={deleteMutation.isPending}
                      data-testid={`delete-leave-${leave._id || leave.id}`}
                    >
                      <Trash2 size={16} className="text-[#EF4444]" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {/* Add Leave Dialog */}
      <AddLeaveDialog
        isOpen={isDialogOpen}
        onClose={() => setIsDialogOpen(false)}
        resources={dialogResources}
        preselectedResourceId={isResource ? ownResourceData?.id : undefined}
      />
    </div>
  );
};

export default Leaves;
