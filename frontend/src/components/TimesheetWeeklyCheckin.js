import React, { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getMyWeekTimesheets, 
  autoFillTimesheets, 
  updateTimesheet, 
  deleteTimesheet,
  submitWeekTimesheets,
  getProjects,
  checkTimesheetUpdateAllowed,
  createTimesheet,
  getMyResource,
  getResources,
  getWBSTasksForTimesheet
} from '../api';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import { Textarea } from './ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import { 
  CheckCircle2, 
  Clock, 
  AlertTriangle, 
  Calendar,
  Sparkles,
  Trash2,
  Save,
  Send,
  Plus,
  X
} from 'lucide-react';
import { toast } from 'sonner';
import { format, addDays } from 'date-fns';

const TimesheetWeeklyCheckin = () => {
  const queryClient = useQueryClient();
  
  // Get current week start (Monday) - safer implementation
  const currentWeekStart = useMemo(() => {
    const today = new Date();
    const day = today.getDay();
    const diff = today.getDate() - day + (day === 0 ? -6 : 1); // Adjust when day is Sunday
    const monday = new Date(today.setDate(diff));
    return format(monday, 'yyyy-MM-dd');
  }, []);
  
  const [editingId, setEditingId] = useState(null);
  const [editValues, setEditValues] = useState({});
  const [showAddForm, setShowAddForm] = useState(false);
  const [newEntry, setNewEntry] = useState({
    resource_id: '',
    project_id: '',
    phase_id: '',
    planned_hours: 0,
    actual_hours: 0,
    notes: '',
    task_id: '',
    task_name: '',
  });

  // Check if timesheet updates are allowed (Thursday/Friday Sydney time)
  const { data: timesheetAllowed } = useQuery({
    queryKey: ['timesheetAllowed'],
    queryFn: async () => {
      const response = await checkTimesheetUpdateAllowed();
      return response.data;
    },
    refetchInterval: 60000, // Check every minute
  });

  // Get timesheets for current week
  const { data: timesheets = [], isLoading: timesheetsLoading } = useQuery({
    queryKey: ['myWeekTimesheets', currentWeekStart],
    queryFn: async () => {
      const response = await getMyWeekTimesheets(currentWeekStart);
      return response.data;
    },
  });

  // Get projects for display
  const { data: projects = [] } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await getProjects();
      return response.data;
    },
  });

  // Get current user's resource ID
  const { data: myResource } = useQuery({
    queryKey: ['myResource'],
    queryFn: async () => {
      try {
        const response = await getMyResource();
        return response.data;
      } catch {
        return null; // Super admins may not have a linked resource
      }
    },
  });

  // Get all resources (for resource selector when no linked resource)
  const { data: allResources = [] } = useQuery({
    queryKey: ['resources'],
    queryFn: async () => {
      const response = await getResources();
      return response.data;
    },
  });

  // Active projects with phases (for the add entry dropdown)
  const activeProjects = useMemo(() => {
    return projects.filter(p => p.status === 'Active' && p.phases?.length > 0);
  }, [projects]);

  // Phases for selected project
  const selectedProjectPhases = useMemo(() => {
    if (!newEntry.project_id) return [];
    const project = projects.find(p => p.id === newEntry.project_id);
    return project?.phases || [];
  }, [newEntry.project_id, projects]);

  // WBS tasks for selected project (for task dropdown in Add Entry)
  const { data: availableWBSTasks = [] } = useQuery({
    queryKey: ['wbsTasksForTimesheet', newEntry.project_id, newEntry.phase_id],
    queryFn: async () => {
      if (!newEntry.project_id) return [];
      const response = await getWBSTasksForTimesheet(
        newEntry.project_id,
        newEntry.phase_id || null
      );
      return response.data;
    },
    enabled: !!newEntry.project_id,
  });

  // Auto-fill mutation
  const autoFillMutation = useMutation({
    mutationFn: () => autoFillTimesheets(currentWeekStart),
    onSuccess: (data) => {
      toast.success(`Auto-filled ${data.created + data.updated} timesheet entries`);
      queryClient.invalidateQueries(['myWeekTimesheets']);
    },
    onError: () => {
      toast.error('Failed to auto-fill timesheets');
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateTimesheet(id, data),
    onSuccess: () => {
      toast.success('Timesheet updated');
      queryClient.invalidateQueries(['myWeekTimesheets']);
      setEditingId(null);
      setEditValues({});
    },
    onError: () => {
      toast.error('Failed to update timesheet');
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id) => deleteTimesheet(id),
    onSuccess: () => {
      toast.success('Timesheet deleted');
      queryClient.invalidateQueries(['myWeekTimesheets']);
    },
    onError: () => {
      toast.error('Failed to delete timesheet');
    },
  });

  // Submit week mutation
  const submitMutation = useMutation({
    mutationFn: () => submitWeekTimesheets(currentWeekStart),
    onSuccess: (data) => {
      toast.success(`Submitted ${data.submitted_count} timesheets for the week`);
      queryClient.invalidateQueries(['myWeekTimesheets']);
      queryClient.invalidateQueries(['actionItems']); // Cross-page: clears "missing timesheet" action item
      queryClient.invalidateQueries(['portfolioHealthScores']); // Cross-page: budget score
    },
    onError: (error) => {
      const message = error.response?.data?.detail || 'Failed to submit timesheets';
      toast.error(message);
    },
  });

  // Create new entry mutation
  const createMutation = useMutation({
    mutationFn: (data) => createTimesheet(data),
    onSuccess: () => {
      toast.success('Timesheet entry added');
      queryClient.invalidateQueries(['myWeekTimesheets']);
      setShowAddForm(false);
      setNewEntry({ resource_id: '', project_id: '', phase_id: '', planned_hours: 0, actual_hours: 0, notes: '', task_id: '', task_name: '' });
    },
    onError: (error) => {
      const message = error.response?.data?.detail || 'Failed to add entry';
      toast.error(message);
    },
  });

  // Handle add new entry
  const handleAddEntry = () => {
    if (!newEntry.project_id || !newEntry.phase_id) {
      toast.error('Please select a project and phase');
      return;
    }
    const resourceId = myResource?.id || newEntry.resource_id;
    if (!resourceId) {
      toast.error('Please select a resource');
      return;
    }
    const weekEnd = format(addDays(new Date(currentWeekStart), 4), 'yyyy-MM-dd');
    createMutation.mutate({
      resource_id: resourceId,
      project_id: newEntry.project_id,
      phase_id: newEntry.phase_id,
      week_start_date: currentWeekStart,
      week_end_date: weekEnd,
      planned_hours: newEntry.planned_hours || 0,
      actual_hours: newEntry.actual_hours || 0,
      notes: newEntry.notes || '',
      status: 'Draft',
      task_id: newEntry.task_id || null,
      task_name: newEntry.task_name || null,
    });
  };

  // Get project name and client name (from enriched timesheet data)
  const getProjectDisplay = (timesheet) => {
    // Use enriched data from backend if available
    if (timesheet.project_name && timesheet.client_name) {
      return {
        projectName: timesheet.project_name,
        clientName: timesheet.client_name,
        phaseName: timesheet.phase_name || 'N/A'
      };
    }
    
    // Fallback to local lookup
    const project = projects.find(p => p.id === timesheet.project_id);
    return {
      projectName: project?.name || 'Unknown Project',
      clientName: project?.client_name || 'Unknown Client',
      phaseName: 'N/A'
    };
  };

  // Calculate totals
  const totals = useMemo(() => {
    const planned = timesheets.reduce((sum, t) => sum + (t.planned_hours || 0), 0);
    const actual = timesheets.reduce((sum, t) => sum + (t.actual_hours || 0), 0);
    const variance = actual - planned;
    return { planned, actual, variance };
  }, [timesheets]);

  // Handle edit start
  const handleEditStart = (timesheet) => {
    setEditingId(timesheet.id);
    setEditValues({
      actual_hours: timesheet.actual_hours,
      notes: timesheet.notes || '',
    });
  };

  // Handle edit cancel
  const handleEditCancel = () => {
    setEditingId(null);
    setEditValues({});
  };

  // Handle edit save
  const handleEditSave = (timesheetId) => {
    updateMutation.mutate({ id: timesheetId, data: editValues });
  };

  // Handle delete
  const handleDelete = (timesheetId) => {
    if (confirm('Are you sure you want to delete this timesheet entry?')) {
      deleteMutation.mutate(timesheetId);
    }
  };

  // Variance color helper
  const getVarianceColor = (variance) => {
    if (variance === 0) return 'text-gray-600';
    if (variance > 0) return 'text-amber-600';
    return 'text-emerald-600';
  };

  const getVarianceBadge = (variance) => {
    if (variance === 0) return <Badge variant="outline">On Track</Badge>;
    if (variance > 0) return <Badge className="bg-amber-100 text-amber-800">Over</Badge>;
    return <Badge className="bg-emerald-100 text-emerald-800">Under</Badge>;
  };

  const hasAnyDrafts = timesheets.some(t => t.status === 'Draft');
  const allSubmitted = timesheets.length > 0 && timesheets.every(t => t.status === 'Submitted');

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Clock className="w-5 h-5" />
              My Weekly Timesheet
            </CardTitle>
            <p className="text-sm text-gray-500 mt-1">
              Week: {format(new Date(currentWeekStart), 'MMM d')} - {format(addDays(new Date(currentWeekStart), 4), 'MMM d, yyyy')}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowAddForm(!showAddForm)}
              disabled={timesheetsLoading}
              data-testid="add-timesheet-entry-btn"
            >
              <Plus className="w-4 h-4 mr-1" />
              Add Entry
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => autoFillMutation.mutate()}
              disabled={autoFillMutation.isPending || timesheetsLoading}
              data-testid="prefill-timesheets-btn"
            >
              <Sparkles className="w-4 h-4 mr-1" />
              {autoFillMutation.isPending ? 'Pre-filling...' : 'Pre-fill'}
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Add Entry Form */}
        {showAddForm && (
          <div className="border border-[#1570EF] rounded-lg p-4 bg-blue-50/50 space-y-3" data-testid="add-entry-form">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold text-[#0B1220]">Add Timesheet Entry</h4>
              <Button variant="ghost" size="sm" onClick={() => setShowAddForm(false)}>
                <X className="w-4 h-4" />
              </Button>
            </div>

            {/* Resource selector (only if no linked resource) */}
            {!myResource && (
              <div>
                <Label className="text-xs">Resource *</Label>
                <Select
                  value={newEntry.resource_id}
                  onValueChange={(value) => setNewEntry({ ...newEntry, resource_id: value })}
                >
                  <SelectTrigger data-testid="add-entry-resource-select">
                    <SelectValue placeholder="Select resource" />
                  </SelectTrigger>
                  <SelectContent>
                    {allResources.filter((r) => r.active !== false).map((r) => (
                      <SelectItem key={r.id} value={r.id}>
                        {r.name} — {r.role}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Project *</Label>
                <Select
                  value={newEntry.project_id}
                  onValueChange={(value) => setNewEntry({ ...newEntry, project_id: value, phase_id: '', task_id: '', task_name: '' })}
                >
                  <SelectTrigger data-testid="add-entry-project-select">
                    <SelectValue placeholder="Select project" />
                  </SelectTrigger>
                  <SelectContent>
                    {activeProjects.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.name} ({p.client_name})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label className="text-xs">Phase *</Label>
                <Select
                  value={newEntry.phase_id}
                  onValueChange={(value) => setNewEntry({ ...newEntry, phase_id: value, task_id: '', task_name: '' })}
                  disabled={!newEntry.project_id}
                >
                  <SelectTrigger data-testid="add-entry-phase-select">
                    <SelectValue placeholder={newEntry.project_id ? 'Select phase' : 'Select project first'} />
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
            </div>

            {/* WBS Task selector (optional) */}
            {availableWBSTasks.length > 0 && (
              <div>
                <Label className="text-xs">Task (optional)</Label>
                <Select
                  value={newEntry.task_id || '__none__'}
                  onValueChange={(value) => {
                    if (value === '__none__') {
                      setNewEntry({ ...newEntry, task_id: '', task_name: '' });
                    } else {
                      const task = availableWBSTasks.find(t => t.id === value);
                      setNewEntry({
                        ...newEntry,
                        task_id: value,
                        task_name: task?.name || '',
                      });
                    }
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="No task (general hours)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">No task (general hours)</SelectItem>
                    {availableWBSTasks.map((task) => (
                      <SelectItem key={task.id} value={task.id}>
                        <span>{task.name}</span>
                        {task.phase_name && (
                          <span className="text-gray-400 ml-1 text-xs">· {task.phase_name}</span>
                        )}
                        {task.estimated_hours > 0 && (
                          <span className="text-gray-300 ml-1 text-xs">~{task.estimated_hours}h</span>
                        )}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label className="text-xs">Planned Hours</Label>
                <Input
                  type="number"
                  step="0.5"
                  min="0"
                  value={newEntry.planned_hours}
                  onChange={(e) => setNewEntry({ ...newEntry, planned_hours: parseFloat(e.target.value) || 0 })}
                  data-testid="add-entry-planned-hours"
                />
              </div>
              <div>
                <Label className="text-xs">Actual Hours</Label>
                <Input
                  type="number"
                  step="0.5"
                  min="0"
                  value={newEntry.actual_hours}
                  onChange={(e) => setNewEntry({ ...newEntry, actual_hours: parseFloat(e.target.value) || 0 })}
                  data-testid="add-entry-actual-hours"
                />
              </div>
              <div>
                <Label className="text-xs">Notes (optional)</Label>
                <Input
                  value={newEntry.notes}
                  onChange={(e) => setNewEntry({ ...newEntry, notes: e.target.value })}
                  placeholder="Brief note..."
                  data-testid="add-entry-notes"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowAddForm(false)}>
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleAddEntry}
                disabled={!newEntry.project_id || !newEntry.phase_id || (!myResource && !newEntry.resource_id) || createMutation.isPending}
                data-testid="add-entry-submit"
              >
                {createMutation.isPending ? 'Adding...' : 'Add Entry'}
              </Button>
            </div>
          </div>
        )}

        {/* Day restriction banner */}
        {timesheetAllowed && !timesheetAllowed.allowed && (
          <Alert className="bg-amber-50 border-amber-200">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            <AlertDescription className="text-amber-800">
              <strong>Timesheet updates are only available on Thursday and Friday</strong>
              <br />
              <span className="text-sm">
                Current day (Sydney): <strong>{timesheetAllowed.current_day}</strong>
                {' • Next allowed: '}
                <strong>{timesheetAllowed.next_allowed_day || 'Thursday'}</strong>
              </span>
            </AlertDescription>
          </Alert>
        )}

        {/* Success banner for submitted timesheets */}
        {allSubmitted && (
          <Alert className="bg-emerald-50 border-emerald-200">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            <AlertDescription className="text-emerald-800">
              All timesheets for this week have been submitted!
            </AlertDescription>
          </Alert>
        )}

        {/* Timesheet entries */}
        {timesheetsLoading ? (
          <div className="text-center py-8 text-gray-500">
            <Clock className="w-8 h-8 mx-auto mb-2 animate-spin" />
            <p>Loading timesheets...</p>
          </div>
        ) : timesheets.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <Calendar className="w-12 h-12 mx-auto mb-3 opacity-40" />
            <p className="font-medium">No timesheets for this week</p>
            <p className="text-sm mt-1">Click "Pre-fill" to auto-generate from your allocations, or "Add Entry" to log time manually</p>
          </div>
        ) : (
          <div className="space-y-3">
            {/* Table header */}
            <div className="grid grid-cols-12 gap-2 px-3 py-2 bg-gray-50 rounded-md text-sm font-medium text-gray-700">
              <div className="col-span-3">Project / Client</div>
              <div className="col-span-2 text-right">Planned</div>
              <div className="col-span-2 text-right">Actual</div>
              <div className="col-span-2 text-right">Variance</div>
              <div className="col-span-2 text-center">Status</div>
              <div className="col-span-1 text-center">Actions</div>
            </div>

            {/* Timesheet rows */}
            {timesheets.map((timesheet) => {
              const displayInfo = getProjectDisplay(timesheet);
              return (
              <div 
                key={timesheet.id}
                className="border border-gray-200 rounded-lg p-3 hover:bg-gray-50 transition-colors"
              >
                {editingId === timesheet.id ? (
                  // Edit mode
                  <div className="space-y-3">
                    <div className="grid grid-cols-12 gap-2 items-center">
                      <div className="col-span-3">
                        <div className="font-medium text-sm">{displayInfo.projectName}</div>
                        <div className="text-xs text-gray-500 mt-0.5">{displayInfo.clientName}</div>
                      </div>
                      <div className="col-span-2 text-right text-sm text-gray-600">
                        {timesheet.planned_hours}h
                      </div>
                      <div className="col-span-2">
                        <Input
                          type="number"
                          step="0.5"
                          value={editValues.actual_hours}
                          onChange={(e) => setEditValues({ ...editValues, actual_hours: parseFloat(e.target.value) })}
                          className="text-right"
                        />
                      </div>
                      <div className="col-span-2 text-right text-sm">
                        <span className={getVarianceColor(editValues.actual_hours - timesheet.planned_hours)}>
                          {(editValues.actual_hours - timesheet.planned_hours).toFixed(1)}h
                        </span>
                      </div>
                      <div className="col-span-3 flex gap-2">
                        <Button
                          size="sm"
                          onClick={() => handleEditSave(timesheet.id)}
                          disabled={updateMutation.isPending}
                        >
                          <Save className="w-3 h-3 mr-1" />
                          Save
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={handleEditCancel}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                    <div>
                      <Label className="text-xs">Notes (optional)</Label>
                      <Textarea
                        value={editValues.notes}
                        onChange={(e) => setEditValues({ ...editValues, notes: e.target.value })}
                        placeholder="Add notes about this week's work..."
                        className="text-sm mt-1"
                        rows={2}
                      />
                    </div>
                  </div>
                ) : (
                  // View mode
                  <div className="space-y-2">
                    <div className="grid grid-cols-12 gap-2 items-center">
                      <div className="col-span-3">
                        <div className="font-medium text-sm">{displayInfo.projectName}</div>
                        <div className="text-xs text-gray-500 mt-0.5">{displayInfo.clientName}</div>
                        {timesheet.task_name && (
                          <div className="text-xs text-[#1570EF] mt-0.5 font-medium">📋 {timesheet.task_name}</div>
                        )}
                        {timesheet.auto_filled && !timesheet.modified_by_user && (
                          <Badge variant="outline" className="text-xs mt-1">Auto-filled</Badge>
                        )}
                      </div>
                      <div className="col-span-2 text-right text-sm text-gray-600">
                        {timesheet.planned_hours}h
                      </div>
                      <div className="col-span-2 text-right text-sm font-medium">
                        {timesheet.actual_hours}h
                      </div>
                      <div className="col-span-2 text-right text-sm">
                        <span className={getVarianceColor(timesheet.variance_hours)}>
                          {timesheet.variance_hours > 0 ? '+' : ''}{timesheet.variance_hours.toFixed(1)}h
                        </span>
                      </div>
                      <div className="col-span-2 text-center">
                        {getVarianceBadge(timesheet.variance_hours)}
                      </div>
                      <div className="col-span-1 flex justify-center gap-1">
                        {timesheet.status === 'Draft' && (
                          <>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleEditStart(timesheet)}
                              data-testid={`edit-timesheet-${timesheet.id}`}
                            >
                              Edit
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-red-600 hover:text-red-700"
                              onClick={() => handleDelete(timesheet.id)}
                              data-testid={`delete-timesheet-${timesheet.id}`}
                            >
                              <Trash2 className="w-3 h-3" />
                            </Button>
                          </>
                        )}
                        {timesheet.status === 'Submitted' && (
                          <Badge variant="outline" className="bg-blue-50 text-blue-700">
                            Submitted
                          </Badge>
                        )}
                      </div>
                    </div>
                    {timesheet.notes && (
                      <div className="text-xs text-gray-600 pl-3 border-l-2 border-gray-200">
                        {timesheet.notes}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
            })}

            {/* Totals row */}
            <div className="grid grid-cols-12 gap-2 px-3 py-3 bg-gray-100 rounded-md font-medium">
              <div className="col-span-3">Total</div>
              <div className="col-span-2 text-right">{totals.planned.toFixed(1)}h</div>
              <div className="col-span-2 text-right">{totals.actual.toFixed(1)}h</div>
              <div className="col-span-2 text-right">
                <span className={getVarianceColor(totals.variance)}>
                  {totals.variance > 0 ? '+' : ''}{totals.variance.toFixed(1)}h
                </span>
              </div>
              <div className="col-span-3"></div>
            </div>
          </div>
        )}

        {/* Submit button */}
        {hasAnyDrafts && (
          <div className="pt-4 border-t">
            <Button
              className="w-full"
              onClick={() => submitMutation.mutate()}
              disabled={!timesheetAllowed?.allowed || submitMutation.isPending}
            >
              <Send className="w-4 h-4 mr-2" />
              {submitMutation.isPending ? 'Submitting...' : 'Submit Week'}
            </Button>
            {!timesheetAllowed?.allowed && (
              <p className="text-xs text-amber-600 text-center mt-2">
                Submissions are only allowed on Thursday and Friday
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default TimesheetWeeklyCheckin;
