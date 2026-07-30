import React, { useState, useMemo, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getMyTimesheetHistory, autoFillTimesheets, submitWeekTimesheets, getAllActiveProjectsSummary, createTimesheet, getMe, getMyAllocations, aiParseTimesheetPhrase, updateTimesheet } from '../api';
import { format, startOfWeek, addDays } from 'date-fns';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Clock, AlertCircle, ChevronDown, ChevronRight, Zap, Send, CheckCircle, Plus, AlertTriangle, Sparkles, Loader2, Pencil, X as XIcon, Save } from 'lucide-react';
import { toast } from 'sonner';

const getCurrentWeekStart = () => {
  const monday = startOfWeek(new Date(), { weekStartsOn: 1 });
  return format(monday, 'yyyy-MM-dd');
};

const STATUS_COLORS = {
  Submitted: 'bg-green-100 text-green-700 border-green-200',
  Draft: 'bg-amber-100 text-amber-700 border-amber-200',
  Approved: 'bg-blue-100 text-blue-700 border-blue-200',
};

const WeekBlock = ({ week, isCurrentWeek, onAutofill, onSubmit, onAddEntry, onUpdateEntry, autofilling, submitting, updatingId }) => {
  const [expanded, setExpanded] = useState(isCurrentWeek);
  const [editingId, setEditingId] = useState(null);
  const [editValues, setEditValues] = useState({ planned_hours: 0, actual_hours: 0, notes: '' });
  const entries = week.entries || [];
  const allSubmitted = entries.length > 0 && entries.every((e) => e.status === 'Submitted');

  const startEdit = (entry) => {
    setEditingId(entry.id);
    setEditValues({
      planned_hours: entry.planned_hours ?? 0,
      actual_hours: entry.actual_hours ?? 0,
      notes: entry.notes || '',
    });
  };
  const cancelEdit = () => {
    setEditingId(null);
    setEditValues({ planned_hours: 0, actual_hours: 0, notes: '' });
  };
  const saveEdit = () => {
    onUpdateEntry(editingId, {
      planned_hours: Number(editValues.planned_hours) || 0,
      actual_hours: Number(editValues.actual_hours) || 0,
      notes: editValues.notes || '',
    });
  };

  // Close edit mode when a save completes (parent clears updatingId back to null)
  const prevUpdatingId = useRef(null);
  useEffect(() => {
    if (editingId && prevUpdatingId.current === editingId && updatingId === null) {
      setEditingId(null);
    }
    prevUpdatingId.current = updatingId;
  }, [updatingId, editingId]);

  let weekLabel;
  try {
    weekLabel = `Week of ${format(new Date(week.week_start + 'T00:00:00'), 'MMM d, yyyy')}`;
  } catch {
    weekLabel = week.week_start;
  }

  return (
    <div
      className={`border rounded-xl overflow-hidden transition-all ${isCurrentWeek ? 'border-[#1570EF]/40 shadow-sm' : 'border-[#E4E7EC]'}`}
      data-testid={`week-block-${week.week_start}`}
    >
      {/* Week header row */}
      <div
        className={`flex items-center justify-between px-4 py-3 cursor-pointer select-none ${isCurrentWeek ? 'bg-[#1570EF]/5' : 'bg-[#F9FAFB]'}`}
        onClick={() => setExpanded((e) => !e)}
      >
        <div className="flex items-center gap-3">
          {expanded ? <ChevronDown size={16} className="text-[#667085]" /> : <ChevronRight size={16} className="text-[#667085]" />}
          <div>
            <span className="text-sm font-semibold text-[#101828]">{weekLabel}</span>
            {isCurrentWeek && (
              <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-[#1570EF] text-white font-medium">Current week</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-4">
          {entries.length > 0 ? (
            <>
              <span className="text-xs text-[#667085]">
                {week.total_actual?.toFixed(1)}h actual / {week.total_planned?.toFixed(1)}h planned
              </span>
              {allSubmitted ? (
                <CheckCircle size={16} className="text-green-600" />
              ) : (
                <span className="text-xs text-amber-600 font-medium">
                  {entries.filter((e) => e.status === 'Draft').length} draft
                </span>
              )}
            </>
          ) : (
            <span className="text-xs text-[#98A2B3]">No entries</span>
          )}
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-4">
          {/* Current week actions */}
          {isCurrentWeek && (
            <div className="flex gap-2 pt-3 pb-2">
              <Button
                size="sm"
                variant="outline"
                onClick={(e) => { e.stopPropagation(); onAutofill(); }}
                disabled={autofilling}
                className="h-8 text-xs gap-1.5"
                data-testid="autofill-btn"
              >
                <Zap size={13} className="text-[#1570EF]" />
                {autofilling ? 'Autofilling...' : 'Autofill from allocations'}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={(e) => { e.stopPropagation(); onAddEntry(); }}
                className="h-8 text-xs gap-1.5"
                data-testid="add-entry-btn"
              >
                <Plus size={13} />
                Add Entry
              </Button>
              {entries.some((e) => e.status === 'Draft') && (
                <Button
                  size="sm"
                  onClick={(e) => { e.stopPropagation(); onSubmit(); }}
                  disabled={submitting}
                  className="h-8 text-xs gap-1.5 bg-[#1570EF] hover:bg-[#0F5DC9]"
                  data-testid="submit-week-btn"
                >
                  <Send size={13} />
                  {submitting ? 'Submitting...' : 'Submit week'}
                </Button>
              )}
            </div>
          )}

          {entries.length === 0 ? (
            <p className="text-xs text-[#98A2B3] py-2">No timesheet entries for this week. Use Autofill or Add Entry to get started.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">Project</TableHead>
                  <TableHead className="text-xs">Phase</TableHead>
                  <TableHead className="text-xs text-right">Planned h</TableHead>
                  <TableHead className="text-xs text-right">Actual h</TableHead>
                  <TableHead className="text-xs text-right">Variance</TableHead>
                  <TableHead className="text-xs">Status</TableHead>
                  {isCurrentWeek && <TableHead className="text-xs w-20 text-right">Actions</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.map((entry, idx) => {
                  const isEditing = editingId === entry.id;
                  const isRowSaving = updatingId === entry.id;
                  // Only Draft rows in the current week can be edited
                  const canEdit = isCurrentWeek && entry.status === 'Draft' && !!entry.id;
                  return (
                    <TableRow key={entry.id || idx} data-testid={`timesheet-row-${entry.id || idx}`}>
                      <TableCell className="text-xs font-medium">
                        {entry.project_name || entry.project_id}
                        {entry.task_name && (
                          <span className="block text-[10px] text-[#98A2B3] mt-0.5">{entry.task_name}</span>
                        )}
                        {isEditing && (
                          <input
                            type="text"
                            value={editValues.notes}
                            onChange={(e) => setEditValues(v => ({ ...v, notes: e.target.value }))}
                            placeholder="Notes (optional)"
                            className="mt-1 w-full text-xs px-2 py-1 border rounded"
                            data-testid={`edit-notes-${entry.id}`}
                          />
                        )}
                      </TableCell>
                      <TableCell className="text-xs">{entry.phase_name || '-'}</TableCell>
                      <TableCell className="text-xs text-right">
                        {isEditing ? (
                          <input
                            type="number"
                            step="0.25"
                            min="0"
                            value={editValues.planned_hours}
                            onChange={(e) => setEditValues(v => ({ ...v, planned_hours: e.target.value }))}
                            className="w-16 text-xs px-2 py-1 border rounded text-right"
                            data-testid={`edit-planned-${entry.id}`}
                          />
                        ) : entry.planned_hours}
                      </TableCell>
                      <TableCell className="text-xs text-right font-medium">
                        {isEditing ? (
                          <input
                            type="number"
                            step="0.25"
                            min="0"
                            value={editValues.actual_hours}
                            onChange={(e) => setEditValues(v => ({ ...v, actual_hours: e.target.value }))}
                            className="w-16 text-xs px-2 py-1 border rounded text-right"
                            data-testid={`edit-actual-${entry.id}`}
                          />
                        ) : entry.actual_hours}
                      </TableCell>
                      <TableCell className="text-xs text-right">
                        <span className={entry.variance_hours > 0 ? 'text-red-600' : entry.variance_hours < 0 ? 'text-green-600' : ''}>
                          {entry.variance_hours > 0 ? '+' : ''}{entry.variance_hours}h
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={`text-[10px] ${STATUS_COLORS[entry.status] || ''}`}>
                          {entry.status}
                        </Badge>
                      </TableCell>
                      {isCurrentWeek && (
                        <TableCell className="text-right">
                          {canEdit && !isEditing && (
                            <button
                              onClick={() => startEdit(entry)}
                              className="p-1 rounded hover:bg-[#F2F3F5] text-[#1570EF]"
                              title="Edit entry"
                              data-testid={`edit-entry-${entry.id}`}
                            >
                              <Pencil size={13} />
                            </button>
                          )}
                          {isEditing && (
                            <div className="flex items-center gap-1 justify-end">
                              <button
                                onClick={saveEdit}
                                disabled={isRowSaving}
                                className="p-1 rounded hover:bg-emerald-50 text-emerald-600 disabled:opacity-50"
                                title="Save"
                                data-testid={`save-entry-${entry.id}`}
                              >
                                {isRowSaving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                              </button>
                              <button
                                onClick={cancelEdit}
                                disabled={isRowSaving}
                                className="p-1 rounded hover:bg-red-50 text-red-600 disabled:opacity-50"
                                title="Cancel"
                                data-testid={`cancel-edit-${entry.id}`}
                              >
                                <XIcon size={13} />
                              </button>
                            </div>
                          )}
                        </TableCell>
                      )}
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </div>
      )}
    </div>
  );
};

// ─── Main component ───────────────────────────────────────────────────────────

const MyTimesheets = () => {
  const queryClient = useQueryClient();
  const currentWeekStart = getCurrentWeekStart();
  const currentWeekEnd = format(addDays(new Date(currentWeekStart + 'T00:00:00'), 4), 'yyyy-MM-dd');
  const [weeksToLoad, setWeeksToLoad] = useState(12);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [addForm, setAddForm] = useState({
    project_id: '',
    phase_id: '',
    planned_hours: 0,
    actual_hours: 0,
    notes: '',
  });
  // AI NL input state
  const [aiPhrase, setAiPhrase] = useState('');
  const [aiParsed, setAiParsed] = useState(null);
  const [aiError, setAiError] = useState(null);

  const { data: userData } = useQuery({
    queryKey: ['me'],
    queryFn: async () => { const r = await getMe(); return r.data; },
  });

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['myTimesheetHistory', weeksToLoad],
    queryFn: async () => {
      const res = await getMyTimesheetHistory(weeksToLoad);
      return res.data;
    },
  });

  const { data: allProjectsData } = useQuery({
    queryKey: ['allActiveProjects'],
    queryFn: async () => { const r = await getAllActiveProjectsSummary(); return r.data; },
    enabled: showAddDialog,
  });

  const { data: myAllocsData } = useQuery({
    queryKey: ['myAllocations', 'month'],
    queryFn: async () => { const r = await getMyAllocations('month'); return r.data; },
  });

  const autofillMutation = useMutation({
    mutationFn: () => autoFillTimesheets(currentWeekStart),
    onSuccess: (res) => {
      const count = res.data?.created || res.data?.entries_created || 0;
      toast.success(`Autofilled ${count} timesheet entry(s) from your allocations`);
      queryClient.invalidateQueries(['myTimesheetHistory']);
      refetch();
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Autofill failed'),
  });

  const submitMutation = useMutation({
    mutationFn: () => submitWeekTimesheets(currentWeekStart),
    onSuccess: (res) => {
      toast.success(`Submitted ${res.data?.submitted_count || 0} timesheet entry(s)`);
      queryClient.invalidateQueries(['myTimesheetHistory']);
      refetch();
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Submission failed'),
  });

  const createEntryMutation = useMutation({
    mutationFn: (entryData) => createTimesheet(entryData),
    onSuccess: () => {
      toast.success('Timesheet entry added');
      queryClient.invalidateQueries(['myTimesheetHistory']);
      refetch();
      setShowAddDialog(false);
      setAddForm({ project_id: '', phase_id: '', planned_hours: 0, actual_hours: 0, notes: '' });
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to create entry'),
  });

  const [updatingRowId, setUpdatingRowId] = useState(null);
  const updateEntryMutation = useMutation({
    mutationFn: ({ id, data }) => updateTimesheet(id, data),
    onMutate: ({ id }) => setUpdatingRowId(id),
    onSuccess: () => {
      toast.success('Entry updated');
      queryClient.invalidateQueries(['myTimesheetHistory']);
      refetch();
      setUpdatingRowId(null);
    },
    onError: (err) => {
      setUpdatingRowId(null);
      toast.error(err?.response?.data?.detail || 'Failed to update entry');
    },
  });

  const aiParseMutation = useMutation({
    mutationFn: (phrase) => aiParseTimesheetPhrase(phrase),
    onSuccess: (res) => {
      const d = res.data;
      if (!d.matched) {
        setAiParsed(null);
        setAiError(d.clarification_needed || 'Could not understand your phrase');
      } else {
        setAiParsed(d);
        setAiError(null);
      }
    },
    onError: (err) => {
      setAiParsed(null);
      setAiError(err?.response?.data?.detail || 'AI parse failed');
    },
  });

  const aiConfirmMutation = useMutation({
    mutationFn: async () => {
      if (!aiParsed) return;
      // Compute week_end_date (Fri)
      const wkStart = new Date(aiParsed.week_start_date + 'T00:00:00');
      const wkEnd = new Date(wkStart);
      wkEnd.setDate(wkEnd.getDate() + 4);
      return createTimesheet({
        resource_id: aiParsed.resource_id,
        project_id: aiParsed.project_id,
        phase_id: aiParsed.phase_id,
        week_start_date: aiParsed.week_start_date,
        week_end_date: wkEnd.toISOString().slice(0, 10),
        planned_hours: aiParsed.actual_hours,
        actual_hours: aiParsed.actual_hours,
        notes: aiParsed.notes || aiParsed.original_phrase,
      });
    },
    onSuccess: () => {
      toast.success('Entry created from AI');
      queryClient.invalidateQueries(['myTimesheetHistory']);
      refetch();
      setAiPhrase('');
      setAiParsed(null);
    },
    onError: (err) => toast.error(err?.response?.data?.detail || 'Create failed'),
  });

  const resource = data?.resource;
  const weeks = data?.weeks || [];

  // Check if resource is allocated to the selected project
  const allocationForProject = useMemo(() => {
    if (!addForm.project_id || !myAllocsData?.allocations) return null;
    return myAllocsData.allocations.find(a => a.project_id === addForm.project_id);
  }, [addForm.project_id, myAllocsData]);

  // Get phases for selected project
  const selectedProjectPhases = useMemo(() => {
    if (!addForm.project_id || !allProjectsData) return [];
    const proj = allProjectsData.find(p => p.id === addForm.project_id);
    return proj?.phases || [];
  }, [addForm.project_id, allProjectsData]);

  const handleAddEntry = () => {
    if (!resource) {
      toast.error('No resource profile linked to your account');
      return;
    }
    if (!addForm.project_id) {
      toast.error('Please select a project');
      return;
    }
    if (!addForm.phase_id) {
      toast.error('Please select a phase');
      return;
    }
    if (addForm.actual_hours <= 0) {
      toast.error('Please enter actual hours');
      return;
    }
    createEntryMutation.mutate({
      resource_id: resource.id,
      project_id: addForm.project_id,
      phase_id: addForm.phase_id,
      week_start_date: currentWeekStart,
      week_end_date: currentWeekEnd,
      planned_hours: parseFloat(addForm.planned_hours) || 0,
      actual_hours: parseFloat(addForm.actual_hours),
      notes: addForm.notes || '',
      status: 'Draft',
    });
  };

  // Over-allocation warning
  const overAllocWarning = useMemo(() => {
    if (!addForm.actual_hours || !allocationForProject) return null;
    const weeklyHrs = allocationForProject.weekly_hours || 0;
    if (weeklyHrs > 0 && addForm.actual_hours > weeklyHrs) {
      return `You are logging ${addForm.actual_hours}h but your allocation is ${weeklyHrs.toFixed(1)}h/wk for this project.`;
    }
    return null;
  }, [addForm.actual_hours, allocationForProject]);

  return (
    <div className="max-w-4xl mx-auto space-y-6" data-testid="my-timesheets-page">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-[#0B1220]">My Timesheets</h1>
        {resource && (
          <p className="text-sm text-[#667085] mt-1">
            {resource.name} &middot; {resource.role}
          </p>
        )}
      </div>

      {/* Read-only warning banner */}
      <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-50 border border-amber-200" data-testid="readonly-banner">
        <AlertCircle size={18} className="text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-amber-800">Only current week is editable</p>
          <p className="text-xs text-amber-700 mt-0.5">
            You can autofill, add, and <strong>edit</strong> entries for the current week. Past weeks are read-only — contact your admin to correct submitted entries.
          </p>
        </div>
      </div>

      {/* AI Quick-log */}
      <div className="rounded-xl border border-purple-200 bg-gradient-to-r from-purple-50 to-blue-50 p-4" data-testid="ai-quick-log">
        <div className="flex items-center gap-2 mb-2">
          <Sparkles size={16} className="text-purple-600" />
          <h3 className="text-sm font-semibold text-[#0B1220]">Quick log with AI</h3>
          <span className="text-xs text-[#667085]">— describe what you did, we'll fill in the rest</span>
        </div>
        <div className="flex gap-2">
          <Input
            value={aiPhrase}
            onChange={(e) => { setAiPhrase(e.target.value); setAiError(null); setAiParsed(null); }}
            placeholder="e.g. Log 4h on Acme API design yesterday"
            className="bg-white"
            onKeyDown={(e) => { if (e.key === 'Enter' && aiPhrase.trim() && !aiParseMutation.isPending) aiParseMutation.mutate(aiPhrase.trim()); }}
            data-testid="ai-log-input"
          />
          <Button
            onClick={() => aiParseMutation.mutate(aiPhrase.trim())}
            disabled={!aiPhrase.trim() || aiParseMutation.isPending}
            className="bg-purple-600 text-white hover:bg-purple-700"
            data-testid="ai-log-parse-btn"
          >
            {aiParseMutation.isPending ? <Loader2 size={14} className="mr-1 animate-spin" /> : <Sparkles size={14} className="mr-1" />}
            Parse
          </Button>
        </div>
        {aiError && (
          <div className="mt-3 p-2 bg-orange-50 border border-orange-200 rounded text-xs text-orange-800">
            {aiError}
          </div>
        )}
        {aiParsed && (
          <div className="mt-3 p-3 bg-white rounded-lg border border-[#E6E8EC]">
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-[#0B1220] mb-2">
              <div><b>Project:</b> {aiParsed.project_name}{aiParsed.client_name && ` (${aiParsed.client_name})`}</div>
              {aiParsed.phase_name && <div><b>Phase:</b> {aiParsed.phase_name}</div>}
              <div><b>Hours:</b> {aiParsed.actual_hours}</div>
              <div><b>Date:</b> {aiParsed.date}</div>
              {!aiParsed.is_allocated && (
                <div className="text-amber-700 text-xs italic">Not currently allocated to this project — will still be logged</div>
              )}
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={() => aiConfirmMutation.mutate()}
                disabled={aiConfirmMutation.isPending}
                data-testid="ai-log-confirm-btn"
              >
                {aiConfirmMutation.isPending ? <Loader2 size={12} className="mr-1 animate-spin" /> : <CheckCircle size={12} className="mr-1" />}
                Confirm & save
              </Button>
              <Button size="sm" variant="outline" onClick={() => { setAiParsed(null); setAiPhrase(''); }}>
                Cancel
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="text-center py-12 text-[#667085]">
          <Clock className="animate-pulse mx-auto mb-3" size={32} />
          Loading your timesheet history...
        </div>
      ) : !resource ? (
        <div className="text-center py-12 border border-dashed border-[#D0D5DD] rounded-xl">
          <Clock size={32} className="text-[#D0D5DD] mx-auto mb-3" />
          <p className="text-[#667085]">No resource profile linked to your account.</p>
          <p className="text-xs text-[#98A2B3] mt-1">Contact your admin to set up your profile.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {/* Ensure current week always appears first even if no entries */}
          {!weeks.find((w) => w.week_start === currentWeekStart) && (
            <WeekBlock
              key="current-empty"
              week={{ week_start: currentWeekStart, entries: [], total_planned: 0, total_actual: 0 }}
              isCurrentWeek
              onAutofill={() => autofillMutation.mutate()}
              onSubmit={() => submitMutation.mutate()}
              onAddEntry={() => setShowAddDialog(true)}
              onUpdateEntry={(id, data) => updateEntryMutation.mutate({ id, data })}
              autofilling={autofillMutation.isPending}
              submitting={submitMutation.isPending}
              updatingId={updatingRowId}
            />
          )}
          {weeks.map((week) => (
            <WeekBlock
              key={week.week_start}
              week={week}
              isCurrentWeek={week.week_start === currentWeekStart}
              onAutofill={() => autofillMutation.mutate()}
              onSubmit={() => submitMutation.mutate()}
              onAddEntry={() => setShowAddDialog(true)}
              onUpdateEntry={(id, data) => updateEntryMutation.mutate({ id, data })}
              autofilling={autofillMutation.isPending}
              submitting={submitMutation.isPending}
              updatingId={updatingRowId}
            />
          ))}

          {/* Load more */}
          {weeks.length >= weeksToLoad && (
            <div className="text-center pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setWeeksToLoad((n) => n + 12)}
                className="text-xs"
              >
                Load older weeks
              </Button>
            </div>
          )}

          {weeks.length === 0 && (
            <div className="text-center py-8 text-[#98A2B3] text-sm">
              No timesheet entries found in the last {weeksToLoad} weeks.
            </div>
          )}
        </div>
      )}

      {/* Add Entry Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent className="max-w-lg" data-testid="add-entry-dialog">
          <DialogHeader>
            <DialogTitle>Add Timesheet Entry</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Project */}
            <div>
              <Label className="text-sm font-medium mb-1.5 block">Project *</Label>
              <Select
                value={addForm.project_id}
                onValueChange={(v) => setAddForm({ ...addForm, project_id: v, phase_id: '' })}
              >
                <SelectTrigger data-testid="ts-project-select">
                  <SelectValue placeholder="Select a project" />
                </SelectTrigger>
                <SelectContent>
                  {allProjectsData?.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name} — {p.client_name || 'No client'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {addForm.project_id && !allocationForProject && (
                <p className="text-xs text-amber-600 mt-1 flex items-center gap-1">
                  <AlertTriangle size={12} />
                  You are not currently allocated to this project
                </p>
              )}
            </div>

            {/* Phase */}
            <div>
              <Label className="text-sm font-medium mb-1.5 block">Phase *</Label>
              <Select
                value={addForm.phase_id}
                onValueChange={(v) => setAddForm({ ...addForm, phase_id: v })}
                disabled={!addForm.project_id}
              >
                <SelectTrigger data-testid="ts-phase-select">
                  <SelectValue placeholder={addForm.project_id ? 'Select a phase' : 'Select a project first'} />
                </SelectTrigger>
                <SelectContent>
                  {selectedProjectPhases.map((phase) => (
                    <SelectItem key={phase.id} value={phase.id}>
                      {phase.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Hours */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-sm font-medium mb-1.5 block">Planned Hours</Label>
                <Input
                  type="number"
                  min="0"
                  step="0.5"
                  value={addForm.planned_hours}
                  onChange={(e) => setAddForm({ ...addForm, planned_hours: e.target.value })}
                  data-testid="ts-planned-hours"
                />
              </div>
              <div>
                <Label className="text-sm font-medium mb-1.5 block">Actual Hours *</Label>
                <Input
                  type="number"
                  min="0"
                  step="0.5"
                  value={addForm.actual_hours}
                  onChange={(e) => setAddForm({ ...addForm, actual_hours: e.target.value })}
                  data-testid="ts-actual-hours"
                />
              </div>
            </div>

            {/* Over-allocation warning */}
            {overAllocWarning && (
              <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-50 border border-amber-200" data-testid="over-alloc-warning">
                <AlertTriangle size={16} className="text-amber-600 mt-0.5 shrink-0" />
                <p className="text-xs text-amber-800">{overAllocWarning}</p>
              </div>
            )}

            {/* Not-allocated info */}
            {addForm.project_id && !allocationForProject && (
              <div className="flex items-start gap-2 p-3 rounded-lg bg-blue-50 border border-blue-200">
                <AlertCircle size={16} className="text-blue-600 mt-0.5 shrink-0" />
                <p className="text-xs text-blue-800">
                  You can still log time to this project even without a formal allocation. Your admin will see the entry.
                </p>
              </div>
            )}

            {/* Notes */}
            <div>
              <Label className="text-sm font-medium mb-1.5 block">Notes (optional)</Label>
              <Input
                value={addForm.notes}
                onChange={(e) => setAddForm({ ...addForm, notes: e.target.value })}
                placeholder="What did you work on?"
                data-testid="ts-notes"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleAddEntry}
              disabled={createEntryMutation.isPending}
              className="bg-[#1570EF] hover:bg-[#0F5DC9]"
              data-testid="ts-submit-entry"
            >
              {createEntryMutation.isPending ? 'Adding...' : 'Add Entry'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default MyTimesheets;
