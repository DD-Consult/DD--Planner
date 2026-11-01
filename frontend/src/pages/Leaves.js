import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getLeaves, deleteLeave, getResources, getMyResource, getPendingLeaves, approveLeave, rejectLeave, setLeaveStatus, getWhosOut, getTimeOffVisibility, setTimeOffVisibility, getLeaveCalendar, getLeaveBalances, upsertLeaveAllocation, deleteLeaveAllocation, getLeaveAttachment, deleteLeaveAttachment, addLeaveAttachment } from '../api';
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
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '../components/ui/popover';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Switch } from '../components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { CalendarOff, Plus, Trash2, Loader2, MoreHorizontal, Users, ChevronLeft, ChevronRight, CalendarDays, Paperclip, Download, X, Upload } from 'lucide-react';
import { toast } from 'sonner';
import { format, parseISO, startOfMonth, endOfMonth, eachDayOfInterval, addMonths, subMonths, isSameDay, getDay } from 'date-fns';
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
  const isAdmin = meData?.role === 'admin' || meData?.role === 'super_admin';

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

  // ── Team leave calendar ─────────────────────────────────────────────────
  const [showCalendar, setShowCalendar] = useState(false);
  const [calMonth, setCalMonth] = useState(() => startOfMonth(new Date()));
  const calStart = format(startOfMonth(calMonth), 'yyyy-MM-dd');
  const calEnd = format(endOfMonth(calMonth), 'yyyy-MM-dd');
  const { data: calendarData } = useQuery({
    queryKey: ['leaveCalendar', calStart],
    queryFn: async () => {
      const response = await getLeaveCalendar(calStart, calEnd);
      return response.data;
    },
    enabled: showCalendar,
  });
  
  // ── Leave Balances ──────────────────────────────────────────────────────
  const [balancesResourceId, setBalancesResourceId] = useState('');
  const [balancesYear, setBalancesYear] = useState(new Date().getFullYear());
  const [editingAllocation, setEditingAllocation] = useState(null); // {resource_id, leave_type, year, value}

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

  // Leave balances query — declared AFTER resources/ownResourceData to avoid TDZ.
  const { data: balancesData, refetch: refetchBalances } = useQuery({
    queryKey: ['leaveBalances', balancesResourceId, balancesYear],
    queryFn: async () => {
      const response = await getLeaveBalances(
        balancesResourceId || (ownOnly ? undefined : ''),
        balancesYear
      );
      return response.data;
    },
    enabled: !!balancesResourceId || ownOnly,
  });

  // Auto-select first resource for admin/super admin when resources load.
  useEffect(() => {
    if (isSuperAdmin && resources && resources.length > 0 && !balancesResourceId) {
      const firstActive = resources.find((r) => r.active !== false) || resources[0];
      if (firstActive) setBalancesResourceId(firstActive.id);
    }
  }, [isSuperAdmin, resources, balancesResourceId]);

  // Auto-select own resource for non-admin (own-only) users.
  useEffect(() => {
    if (ownOnly && ownResourceData && !balancesResourceId) {
      setBalancesResourceId(ownResourceData.id);
    }
  }, [ownOnly, ownResourceData, balancesResourceId]);


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
  
  // Upsert leave allocation mutation
  const upsertAllocationMutation = useMutation({
    mutationFn: upsertLeaveAllocation,
    onSuccess: () => {
      toast.success('Allocation updated');
      queryClient.invalidateQueries({ queryKey: ['leaveBalances'] });
      setEditingAllocation(null);
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to update allocation');
    },
  });
  
  // Delete leave allocation mutation
  const deleteAllocationMutation = useMutation({
    mutationFn: ({ resourceId, leaveType, year }) => deleteLeaveAllocation(resourceId, leaveType, year),
    onSuccess: () => {
      toast.success('Allocation reset to default');
      queryClient.invalidateQueries({ queryKey: ['leaveBalances'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to reset allocation');
    },
  });
  
  // Delete attachment mutation
  const deleteAttachmentMutation = useMutation({
    mutationFn: ({ leaveId, attachmentId }) => deleteLeaveAttachment(leaveId, attachmentId),
    onSuccess: () => {
      toast.success('Attachment removed');
      queryClient.invalidateQueries({ queryKey: ['leaves'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to remove attachment');
    },
  });
  
  // Add attachment mutation (for existing leaves)
  const addAttachmentMutation = useMutation({
    mutationFn: ({ leaveId, attachment }) => addLeaveAttachment(leaveId, attachment),
    onSuccess: () => {
      toast.success('Attachment added');
      queryClient.invalidateQueries({ queryKey: ['leaves'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to add attachment');
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
  
  const handleSaveAllocation = () => {
    if (!editingAllocation) return;
    upsertAllocationMutation.mutate({
      resource_id: editingAllocation.resource_id,
      leave_type: editingAllocation.leave_type,
      year: parseInt(editingAllocation.year, 10),
      allocated: parseFloat(editingAllocation.value),
    });
  };
  
  const handleResetAllocation = (resourceId, leaveType, year) => {
    if (window.confirm('Reset this allocation to the default calculated value?')) {
      deleteAllocationMutation.mutate({ resourceId, leaveType, year: parseInt(year, 10) });
    }
  };
  
  const handleDownloadAttachment = async (leaveId, attachmentId, filename) => {
    try {
      const response = await getLeaveAttachment(leaveId, attachmentId);
      const { data_base64, content_type } = response.data;
      const dataUrl = `data:${content_type};base64,${data_base64}`;
      const link = document.createElement('a');
      link.href = dataUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (error) {
      toast.error('Failed to download attachment');
    }
  };
  
  const handleDeleteAttachment = (leaveId, attachmentId) => {
    if (window.confirm('Are you sure you want to delete this attachment?')) {
      deleteAttachmentMutation.mutate({ leaveId, attachmentId });
    }
  };
  
  const handleAddAttachmentToExisting = async (leaveId, file) => {
    if (!file) return;
    
    // Validate file
    const maxSize = 5 * 1024 * 1024; // 5MB
    const allowedTypes = ['application/pdf', 'image/png', 'image/jpeg'];
    if (file.size > maxSize) {
      toast.error('File too large (max 5MB)');
      return;
    }
    if (!allowedTypes.includes(file.type)) {
      toast.error('Invalid file type (only PDF, PNG, JPEG allowed)');
      return;
    }
    
    // Read file as base64
    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const dataUrl = e.target.result;
        const base64 = dataUrl.split(',')[1]; // Strip prefix
        await addAttachmentMutation.mutateAsync({
          leaveId,
          attachment: {
            filename: file.name,
            content_type: file.type,
            data_base64: base64,
          },
        });
      } catch (error) {
        toast.error('Failed to add attachment');
      }
    };
    reader.readAsDataURL(file);
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

      {/* Team Leave Calendar */}
      <Card className="border-[#E6E8EC]" data-testid="leave-calendar-section">
        <CardHeader className="cursor-pointer" onClick={() => setShowCalendar((s) => !s)}>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-base">
              <CalendarDays size={18} className="text-[#1570EF]" />
              Team calendar
            </CardTitle>
            <span className="text-xs text-[#667085]">{showCalendar ? 'Hide' : 'Show'}</span>
          </div>
        </CardHeader>
        {showCalendar && (
          <CardContent>
            <div className="flex items-center justify-between mb-3">
              <Button variant="outline" size="sm" onClick={() => setCalMonth((m) => subMonths(m, 1))} data-testid="cal-prev">
                <ChevronLeft size={16} />
              </Button>
              <div className="font-medium text-[#0B1220]">{format(calMonth, 'MMMM yyyy')}</div>
              <Button variant="outline" size="sm" onClick={() => setCalMonth((m) => addMonths(m, 1))} data-testid="cal-next">
                <ChevronRight size={16} />
              </Button>
            </div>
            {/* Weekday headers (Mon-Sun) */}
            <div className="grid grid-cols-7 gap-1 text-[11px] text-[#667085] font-medium mb-1">
              {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d) => (
                <div key={d} className="text-center">{d}</div>
              ))}
            </div>
            <div className="grid grid-cols-7 gap-1">
              {(() => {
                const days = eachDayOfInterval({ start: startOfMonth(calMonth), end: endOfMonth(calMonth) });
                // Leading blanks so day-1 sits under its weekday (Mon=0).
                const firstDow = (getDay(startOfMonth(calMonth)) + 6) % 7; // convert Sun=0 -> Mon=0
                const blanks = Array.from({ length: firstDow });
                const hol = (calendarData?.holidays) || [];
                const entries = (calendarData?.entries) || [];
                return (
                  <>
                    {blanks.map((_, i) => <div key={`b${i}`} />)}
                    {days.map((day) => {
                      const key = format(day, 'yyyy-MM-dd');
                      const dayHols = hol.filter((h) => h.date === key);
                      const isPublic = dayHols.some((h) => h.is_public_holiday);
                      const dayEntries = entries.filter((e) => {
                        try { return parseISO(e.start_date) <= day && parseISO(e.end_date) >= day; }
                        catch { return false; }
                      });
                      return (
                        <div
                          key={key}
                          data-testid={`cal-day-${key}`}
                          className={`min-h-[64px] rounded-md border p-1 text-[10px] ${isPublic ? 'bg-amber-50 border-amber-200' : 'bg-white border-[#E6E8EC]'}`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-[#667085]">{format(day, 'd')}</span>
                            {isPublic && <span className="text-amber-700" title="Public holiday">★</span>}
                          </div>
                          {dayHols.map((h, i) => (
                            <div key={`h${i}`} className="truncate text-amber-700" title={h.name}>{h.name}</div>
                          ))}
                          {dayEntries.slice(0, 3).map((e, i) => (
                            <div
                              key={`e${i}`}
                              className={`truncate mt-0.5 px-1 rounded ${e.status === 'Pending' ? 'border border-dashed border-[#98A2B3] text-[#667085]' : 'bg-[#E6F0FD] text-[#1570EF]'}`}
                              title={`${e.name} · ${e.type}${e.status === 'Pending' ? ' (pending)' : ''}`}
                            >
                              {e.worked_holiday ? '↔ ' : ''}{(e.day_portion && e.day_portion !== 'full') ? '½ ' : ''}{e.name.split(' ')[0]} · {e.type}
                            </div>
                          ))}
                          {dayEntries.length > 3 && <div className="text-[#98A2B3]">+{dayEntries.length - 3} more</div>}
                        </div>
                      );
                    })}
                  </>
                );
              })()}
            </div>
            {calendarData?.can_see_pending && (
              <p className="text-[11px] text-[#98A2B3] mt-2">Pending requests shown with a dashed border. Reasons/notes are private.</p>
            )}
          </CardContent>
        )}
      </Card>

      {/* Leave Balances */}
      <Card className="border-[#E6E8EC]" data-testid="leave-balances-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg" style={{ fontFamily: 'Space Grotesk' }}>
            Leave Balances
          </CardTitle>
          <CardDescription>
            {isSuperAdmin ? 'View and manage leave balances for any resource' : 'Your leave balances for the selected year'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Filters */}
          <div className="flex gap-3">
            {isSuperAdmin && (
              <div className="flex-1">
                <Label htmlFor="balance-resource" className="text-xs">Resource</Label>
                <Select value={balancesResourceId} onValueChange={setBalancesResourceId}>
                  <SelectTrigger id="balance-resource" data-testid="balance-resource-select" className="h-9">
                    <SelectValue placeholder="Select a resource" />
                  </SelectTrigger>
                  <SelectContent>
                    {resources?.filter((r) => r.active !== false).map((r) => (
                      <SelectItem key={r.id} value={r.id}>
                        {r.name} - {r.role}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className={isSuperAdmin ? 'w-40' : 'flex-1'}>
              <Label htmlFor="balance-year" className="text-xs">Year</Label>
              <Select value={String(balancesYear)} onValueChange={(val) => setBalancesYear(parseInt(val))}>
                <SelectTrigger id="balance-year" data-testid="balance-year-select" className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[2023, 2024, 2025, 2026, 2027].map((y) => (
                    <SelectItem key={y} value={String(y)}>{y}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          
          {/* Balances Table */}
          {!balancesData || balancesData.length === 0 ? (
            <p className="text-sm text-[#667085] py-4">No balances available for the selected resource/year.</p>
          ) : (
            <div className="border border-[#E6E8EC] rounded-md overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Type</TableHead>
                    <TableHead className="text-xs">Allocated</TableHead>
                    <TableHead className="text-xs">Taken</TableHead>
                    <TableHead className="text-xs">Pending</TableHead>
                    <TableHead className="text-xs">Available</TableHead>
                    {isSuperAdmin && <TableHead className="text-xs text-right">Actions</TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {balancesData.map((bal) => {
                    const isTracked = bal.accrual_method !== 'none';
                    const isNegative = isTracked && bal.available !== null && bal.available < 0;
                    const isEditing = editingAllocation && editingAllocation.leave_type === bal.leave_type;
                    
                    return (
                      <TableRow key={bal.leave_type} data-testid={`balance-row-${bal.leave_type}`}>
                        <TableCell className="font-medium text-sm">
                          <div className="flex items-center gap-2">
                            {bal.leave_type}
                            {bal.is_override && (
                              <Badge variant="outline" className="text-xs bg-purple-50 text-purple-700 border-purple-200">
                                override
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-sm">
                          {isEditing ? (
                            <Input
                              type="number"
                              step="0.5"
                              value={editingAllocation.value}
                              onChange={(e) => setEditingAllocation({...editingAllocation, value: e.target.value})}
                              data-testid={`allocation-override-input-${bal.leave_type}`}
                              className="h-7 w-20 text-xs"
                            />
                          ) : isTracked ? (
                            bal.allocated !== null ? bal.allocated : '—'
                          ) : (
                            <span className="text-[#98A2B3]">Not tracked</span>
                          )}
                        </TableCell>
                        <TableCell className="text-sm">{isTracked ? bal.taken : '—'}</TableCell>
                        <TableCell className="text-sm">{isTracked ? bal.pending : '—'}</TableCell>
                        <TableCell className={`text-sm ${isNegative ? 'text-red-600 font-semibold' : ''}`}>
                          {isTracked ? (bal.available !== null ? bal.available : '—') : '—'}
                        </TableCell>
                        {isSuperAdmin && (
                          <TableCell className="text-right">
                            {isTracked && (
                              <div className="flex items-center justify-end gap-1">
                                {isEditing ? (
                                  <>
                                    <Button
                                      size="sm"
                                      onClick={handleSaveAllocation}
                                      disabled={upsertAllocationMutation.isPending}
                                      data-testid={`save-allocation-${bal.leave_type}`}
                                      className="h-7 text-xs"
                                      style={{ backgroundColor: '#1570EF' }}
                                    >
                                      {upsertAllocationMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : 'Save'}
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={() => setEditingAllocation(null)}
                                      className="h-7 text-xs"
                                    >
                                      Cancel
                                    </Button>
                                  </>
                                ) : (
                                  <>
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => setEditingAllocation({ resource_id: bal.resource_id, leave_type: bal.leave_type, year: bal.year, value: bal.allocated || '' })}
                                      data-testid={`edit-allocation-${bal.leave_type}`}
                                      className="h-7 text-xs"
                                    >
                                      Edit
                                    </Button>
                                    {bal.is_override && (
                                      <Button
                                        size="sm"
                                        variant="ghost"
                                        onClick={() => handleResetAllocation(bal.resource_id, bal.leave_type, bal.year)}
                                        disabled={deleteAllocationMutation.isPending}
                                        data-testid={`reset-allocation-${bal.leave_type}`}
                                        className="h-7 text-xs text-red-600"
                                      >
                                        Reset
                                      </Button>
                                    )}
                                  </>
                                )}
                              </div>
                            )}
                          </TableCell>
                        )}
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

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
                <TableHead>Attachments</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {leaves?.map((leave) => {
                const leaveId = leave._id || leave.id;
                const hasAttachments = leave.attachments && leave.attachments.length > 0;
                const canManageAttachments = isSuperAdmin || (ownResourceData && leave.resource_id === ownResourceData.id);
                
                return (
                  <TableRow key={leaveId} data-testid={`leave-row-${leaveId}`}>
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
                    <TableCell className="text-[#667085] text-xs" data-testid={`leave-requested-${leaveId}`}>
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
                        data-testid={`leave-status-${leaveId}`}
                      >
                        {(leave.status || 'Approved')}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {hasAttachments ? (
                        <Popover>
                          <PopoverTrigger asChild>
                            <Button variant="ghost" size="sm" data-testid={`attachments-btn-${leaveId}`}>
                              <Paperclip size={14} className="text-[#1570EF] mr-1" />
                              <span className="text-xs">{leave.attachments.length}</span>
                            </Button>
                          </PopoverTrigger>
                          <PopoverContent className="w-80" data-testid={`attachments-popover-${leaveId}`}>
                            <div className="space-y-2">
                              <h4 className="font-medium text-sm mb-2">Attachments</h4>
                              {leave.attachments.map((att) => (
                                <div key={att.id} className="flex items-center justify-between p-2 bg-[#F7F9FC] rounded border border-[#E6E8EC]">
                                  <div className="flex-1 min-w-0">
                                    <div className="text-xs font-medium truncate">{att.filename}</div>
                                    <div className="text-[10px] text-[#667085]">
                                      {(att.size / 1024).toFixed(1)} KB · {format(new Date(att.uploaded_at), 'MMM d, yyyy')}
                                    </div>
                                  </div>
                                  <div className="flex items-center gap-1 ml-2">
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => handleDownloadAttachment(leaveId, att.id, att.filename)}
                                      data-testid={`download-attachment-${att.id}`}
                                      title="Download"
                                    >
                                      <Download size={14} className="text-[#1570EF]" />
                                    </Button>
                                    {canManageAttachments && (
                                      <Button
                                        size="sm"
                                        variant="ghost"
                                        onClick={() => handleDeleteAttachment(leaveId, att.id)}
                                        disabled={deleteAttachmentMutation.isPending}
                                        data-testid={`delete-attachment-${att.id}`}
                                        title="Remove"
                                      >
                                        <X size={14} className="text-[#EF4444]" />
                                      </Button>
                                    )}
                                  </div>
                                </div>
                              ))}
                              {canManageAttachments && leave.attachments.length < 3 && (
                                <div className="pt-2 border-t border-[#E6E8EC]">
                                  <Label htmlFor={`add-attachment-${leaveId}`} className="cursor-pointer">
                                    <div className="flex items-center justify-center gap-2 p-2 bg-[#F7F9FC] rounded border border-dashed border-[#98A2B3] hover:bg-[#E6F0FD] transition-colors">
                                      <Upload size={14} className="text-[#1570EF]" />
                                      <span className="text-xs text-[#1570EF]">Add attachment</span>
                                    </div>
                                  </Label>
                                  <input
                                    id={`add-attachment-${leaveId}`}
                                    type="file"
                                    accept=".pdf,.png,.jpg,.jpeg"
                                    className="hidden"
                                    onChange={(e) => {
                                      if (e.target.files && e.target.files[0]) {
                                        handleAddAttachmentToExisting(leaveId, e.target.files[0]);
                                        e.target.value = ''; // Reset
                                      }
                                    }}
                                    data-testid={`add-attachment-input-${leaveId}`}
                                  />
                                </div>
                              )}
                            </div>
                          </PopoverContent>
                        </Popover>
                      ) : canManageAttachments ? (
                        <div>
                          <Label htmlFor={`add-attachment-${leaveId}`} className="cursor-pointer">
                            <Button variant="ghost" size="sm" asChild data-testid={`add-attachment-btn-${leaveId}`}>
                              <span>
                                <Upload size={14} className="text-[#98A2B3]" />
                              </span>
                            </Button>
                          </Label>
                          <input
                            id={`add-attachment-${leaveId}`}
                            type="file"
                            accept=".pdf,.png,.jpg,.jpeg"
                            className="hidden"
                            onChange={(e) => {
                              if (e.target.files && e.target.files[0]) {
                                handleAddAttachmentToExisting(leaveId, e.target.files[0]);
                                e.target.value = ''; // Reset
                              }
                            }}
                            data-testid={`add-attachment-input-${leaveId}`}
                          />
                        </div>
                      ) : (
                        <span className="text-xs text-[#98A2B3]">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        {isSuperAdmin && (
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                data-testid={`change-status-${leaveId}`}
                                title="Change status"
                              >
                                <MoreHorizontal size={16} />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              {(leave.status || 'Approved') !== 'Approved' && (
                                <DropdownMenuItem
                                  data-testid={`set-approved-${leaveId}`}
                                  onClick={() => handleSetStatus(leaveId, 'Approved')}
                                >
                                  Approve
                                </DropdownMenuItem>
                              )}
                              {(leave.status || 'Approved') !== 'Rejected' && (
                                <DropdownMenuItem
                                  data-testid={`set-rejected-${leaveId}`}
                                  onClick={() => handleSetStatus(leaveId, 'Rejected')}
                                  className="text-red-600"
                                >
                                  {(leave.status || 'Approved') === 'Approved' ? 'Revoke (reject)' : 'Reject'}
                                </DropdownMenuItem>
                              )}
                              {(leave.status || 'Approved') !== 'Pending' && (
                                <DropdownMenuItem
                                  data-testid={`set-pending-${leaveId}`}
                                  onClick={() => handleSetStatus(leaveId, 'Pending')}
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
                          onClick={() => handleDelete(leaveId)}
                          disabled={deleteMutation.isPending}
                          data-testid={`delete-leave-${leaveId}`}
                        >
                          <Trash2 size={16} className="text-[#EF4444]" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
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
