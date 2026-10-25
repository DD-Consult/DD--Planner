import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getLeaves, deleteLeave, getResources, getMyResource, getPendingLeaves, approveLeave, rejectLeave, setLeaveStatus, getWhosOut, getTimeOffVisibility, setTimeOffVisibility } from '../api';
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Switch } from '../components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Label } from '../components/ui/label';
import { CalendarOff, Plus, Trash2, Loader2, MoreHorizontal, Users } from 'lucide-react';
import { toast } from 'sonner';
import { format, parseISO } from 'date-fns';
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
  const isSuperAdmin = meData?.role === 'super_admin';
  // Everyone except super admin now has an OWN-ONLY view (incl. regular admins).
  const ownOnly = !isSuperAdmin;

  // Who's out this week — data
  const { data: whosOutData } = useQuery({
    queryKey: ['whosOut'],
    queryFn: async () => {
      const response = await getWhosOut();
      return response.data;
    },
  });

  // Time off visibility config
  const { data: visibilityData } = useQuery({
    queryKey: ['timeoffVisibility'],
    queryFn: async () => {
      const response = await getTimeOffVisibility();
      return response.data;
    },
  });

  // Local state for visibility config (super_admin only)
  const [localEnabled, setLocalEnabled] = useState(false);
  const [localAudience, setLocalAudience] = useState('admins');

  useEffect(() => {
    if (visibilityData) {
      setLocalEnabled(visibilityData.enabled || false);
      setLocalAudience(visibilityData.audience || 'admins');
    }
  }, [visibilityData]);

  // Mutation to update visibility
  const updateVisibilityMutation = useMutation({
    mutationFn: setTimeOffVisibility,
    onSuccess: () => {
      toast.success('Visibility updated');
      queryClient.invalidateQueries({ queryKey: ['timeoffVisibility'] });
      queryClient.invalidateQueries({ queryKey: ['whosOut'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to update visibility');
    },
  });

  // Fetch pending leaves for the approval queue (super_admin only — only they can approve)
  const { data: pendingLeaves } = useQuery({
    queryKey: ['pendingLeaves'],
    queryFn: async () => {
      const response = await getPendingLeaves();
      return response.data;
    },
    enabled: isSuperAdmin,
  });

  // Fetch leaves (backend scopes: super_admin sees all, everyone else own-only)
  const { data: leaves, isLoading: leavesLoading } = useQuery({
    queryKey: ['leaves'],
    queryFn: async () => {
      const response = await getLeaves();
      return response.data;
    },
  });

  // Full resource list is only needed by super admins (for the Resource column
  // name lookup and the request-for-anyone picker).
  const { data: resources } = useQuery({
    queryKey: ['resources'],
    queryFn: async () => {
      const response = await getResources();
      return response.data;
    },
    enabled: isSuperAdmin,
  });

  // Own resource profile — needed by everyone who is own-only (staff, contractors
  // AND regular admins) so they can request their OWN time off.
  const { data: ownResourceData } = useQuery({
    queryKey: ['myResource'],
    queryFn: async () => {
      const res = await getMyResource();
      return res.data;
    },
    enabled: ownOnly,
  });

  // Build resource list for AddLeaveDialog — super admin can pick anyone;
  // everyone else can only request for themselves.
  const dialogResources = isSuperAdmin
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

  // Change status of ANY leave (super_admin) — approve/reject/re-open already-decided entries
  const setStatusMutation = useMutation({
    mutationFn: ({ id, status, note }) => setLeaveStatus(id, status, note),
    onSuccess: (_res, variables) => {
      toast.success(`Leave set to ${variables.status}`);
      queryClient.invalidateQueries({ queryKey: ['pendingLeaves'] });
      queryClient.invalidateQueries({ queryKey: ['leaves'] });
      queryClient.invalidateQueries({ queryKey: ['capacity'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to update leave status');
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

  // Super_admin: change the decision on any leave (incl. already-approved / legacy)
  const handleSetStatus = (id, status) => {
    if (status === 'Approved') {
      setStatusMutation.mutate({ id, status });
      return;
    }
    const label = status === 'Rejected' ? 'revoke / reject' : 're-open to pending';
    const reason = window.prompt(`Optional note for this change (${label}):`);
    if (reason !== null) {
      setStatusMutation.mutate({ id, status, note: reason || undefined });
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
            {isSuperAdmin ? 'Time Off Management' : 'My Time Off'}
          </h1>
          <p className="text-sm text-[#667085] mt-1">
            {isSuperAdmin
              ? 'Review and approve time off requests. All requests require approval.'
              : 'Submit time off requests — all requests are reviewed and approved by a super admin'}
          </p>
        </div>
        <Button
          onClick={() => setIsDialogOpen(true)}
          data-testid="add-leave-button"
          disabled={ownOnly && !ownResourceData}
        >
          <Plus size={16} className="mr-2" />
          Request Time Off
        </Button>
      </div>

      {/* Pending Approvals Section (super_admin only — only they can approve) */}
      {isSuperAdmin && pendingLeaves && pendingLeaves.length > 0 && (
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
                  <div className="text-xs text-[#98A2B3] mt-1" data-testid={`pending-leave-meta-${leave._id || leave.id}`}>
                    Requested{leave.created_at ? ` on ${format(new Date(leave.created_at), 'MMM d, yyyy h:mm a')}` : ''}
                    {leave.submitted_by ? ` by ${leave.submitted_by}` : ''}
                  </div>
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

      {/* Who's out this week card */}
      {(isSuperAdmin || (whosOutData?.entries && whosOutData.entries.length > 0) || (visibilityData?.enabled && visibilityData.audience === 'everyone')) && (
        <Card data-testid="whos-out-card" className="border-[#E6E8EC]">
          <CardHeader>
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <CardTitle className="flex items-center gap-2 text-xl" style={{ fontFamily: 'Space Grotesk', color: '#1570EF' }}>
                  <Users size={24} />
                  Who&apos;s out
                  {whosOutData?.scope === 'team' && (
                    <span className="text-xs text-[#667085] font-normal ml-2">(your team)</span>
                  )}
                </CardTitle>
                {whosOutData?.window && (
                  <CardDescription className="mt-1">
                    {format(parseISO(whosOutData.window.start), 'EEE MMM d')} – {format(parseISO(whosOutData.window.end), 'EEE MMM d')}
                  </CardDescription>
                )}
              </div>
              
              {/* Super-admin visibility controls */}
              {isSuperAdmin && (
                <div className="ml-4 space-y-3 p-3 bg-[#F7F9FC] rounded-md border border-[#E6E8EC]">
                  <div className="flex items-center gap-3">
                    <Switch
                      id="whos-out-enabled"
                      checked={localEnabled}
                      onCheckedChange={setLocalEnabled}
                      data-testid="whos-out-enabled-toggle"
                    />
                    <Label htmlFor="whos-out-enabled" className="text-sm font-medium cursor-pointer">
                      Share &apos;who&apos;s out&apos; with the team
                    </Label>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <Label htmlFor="whos-out-audience" className="text-sm text-[#667085] whitespace-nowrap">
                      Visible to:
                    </Label>
                    <Select value={localAudience} onValueChange={setLocalAudience}>
                      <SelectTrigger id="whos-out-audience" className="h-8 text-xs" data-testid="whos-out-audience-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="admins">Admins only</SelectItem>
                        <SelectItem value="leads">Project leads</SelectItem>
                        <SelectItem value="everyone">Everyone</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <Button
                    size="sm"
                    onClick={() => updateVisibilityMutation.mutate({ enabled: localEnabled, audience: localAudience })}
                    disabled={updateVisibilityMutation.isPending}
                    data-testid="whos-out-save-btn"
                    style={{ backgroundColor: '#1570EF' }}
                    className="w-full"
                  >
                    {updateVisibilityMutation.isPending ? <Loader2 size={14} className="animate-spin mr-2" /> : null}
                    Save
                  </Button>
                  
                  <p className="text-xs text-[#667085] mt-2">
                    Shows names, dates and leave type only — never the reason/notes.
                  </p>
                </div>
              )}
            </div>
          </CardHeader>
          
          <CardContent>
            {!whosOutData?.entries || whosOutData.entries.length === 0 ? (
              <p className="text-[#667085] text-sm">Nobody is on approved leave this week.</p>
            ) : (
              <div className="space-y-2" data-testid="whos-out-list">
                {whosOutData.entries.map((entry) => (
                  <div
                    key={entry.resource_id}
                    data-testid={`whos-out-row-${entry.resource_id}`}
                    className="flex items-center justify-between p-3 bg-[#F7F9FC] rounded-md border border-[#E6E8EC]"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-semibold text-[#0B1220]">{entry.name}</span>
                        <Badge className={getLeaveTypeColor(entry.type)}>
                          {entry.type}
                        </Badge>
                      </div>
                      <div className="text-xs text-[#667085]">{entry.role}</div>
                    </div>
                    <div className="text-sm text-[#667085] text-right">
                      {format(parseISO(entry.start_date), 'MMM d')} – {format(parseISO(entry.end_date), 'MMM d')}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
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
                {isSuperAdmin && <TableHead>Resource</TableHead>}
                <TableHead>Type</TableHead>
                <TableHead>Start Date</TableHead>
                <TableHead>End Date</TableHead>
                <TableHead>Notes</TableHead>
                <TableHead>Requested</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {leaves?.map((leave) => (
                <TableRow key={leave._id || leave.id} data-testid={`leave-row-${leave._id || leave.id}`}>
                  {isSuperAdmin && (
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
                  <TableCell className="text-[#667085] text-xs" data-testid={`leave-requested-${leave._id || leave.id}`}>
                    {leave.created_at ? (
                      <>
                        <div>{format(new Date(leave.created_at), 'MMM d, yyyy h:mm a')}</div>
                        {leave.submitted_by && <div className="text-[#98A2B3]">by {leave.submitted_by}</div>}
                      </>
                    ) : (
                      '—'
                    )}
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
                    <div className="flex items-center justify-end gap-1">
                      {isSuperAdmin && (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              data-testid={`change-status-${leave._id || leave.id}`}
                              title="Change status"
                            >
                              <MoreHorizontal size={16} />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            {(leave.status || 'Approved') !== 'Approved' && (
                              <DropdownMenuItem
                                data-testid={`set-approved-${leave._id || leave.id}`}
                                onClick={() => handleSetStatus(leave._id || leave.id, 'Approved')}
                              >
                                Approve
                              </DropdownMenuItem>
                            )}
                            {(leave.status || 'Approved') !== 'Rejected' && (
                              <DropdownMenuItem
                                data-testid={`set-rejected-${leave._id || leave.id}`}
                                onClick={() => handleSetStatus(leave._id || leave.id, 'Rejected')}
                                className="text-red-600"
                              >
                                {(leave.status || 'Approved') === 'Approved' ? 'Revoke (reject)' : 'Reject'}
                              </DropdownMenuItem>
                            )}
                            {(leave.status || 'Approved') !== 'Pending' && (
                              <DropdownMenuItem
                                data-testid={`set-pending-${leave._id || leave.id}`}
                                onClick={() => handleSetStatus(leave._id || leave.id, 'Pending')}
                              >
                                Re-open to Pending
                              </DropdownMenuItem>
                            )}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(leave._id || leave.id)}
                        disabled={deleteMutation.isPending}
                        data-testid={`delete-leave-${leave._id || leave.id}`}
                      >
                        <Trash2 size={16} className="text-[#EF4444]" />
                      </Button>
                    </div>
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
        preselectedResourceId={ownOnly ? ownResourceData?.id : undefined}
      />
    </div>
  );
};

export default Leaves;
