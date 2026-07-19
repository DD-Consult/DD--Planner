import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { format, startOfWeek, addDays } from 'date-fns';
import { getResources, getProjects, getTimesheets, createTimesheet, updateTimesheet, deleteTimesheet } from '../api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
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
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { Calendar, Users, Briefcase, Filter, Download, Plus, Edit2, Trash2, X } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../components/ui/dialog';
import { Textarea } from '../components/ui/textarea';

const ManageTimesheets = () => {
  const queryClient = useQueryClient();
  
  // Filter states
  const [selectedResource, setSelectedResource] = useState('all');
  const [selectedProject, setSelectedProject] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const [weekStart, setWeekStart] = useState(() => {
    const today = new Date();
    return format(startOfWeek(today, { weekStartsOn: 1 }), 'yyyy-MM-dd');
  });
  
  // Editing state
  const [editingId, setEditingId] = useState(null);
  const [editValues, setEditValues] = useState({});
  
  // Create new timesheet state
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [createValues, setCreateValues] = useState({
    resource_id: '',
    project_id: '',
    phase_id: '',
    week_start_date: weekStart,
    planned_hours: 0,
    actual_hours: 0,
    notes: '',
    status: 'Draft'
  });
  
  // Fetch data
  const { data: resources } = useQuery({
    queryKey: ['resources'],
    queryFn: async () => {
      const response = await getResources();
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
  
  const { data: timesheets, isLoading } = useQuery({
    queryKey: ['allTimesheets', weekStart],
    queryFn: async () => {
      // For super admin, we need to fetch all timesheets
      // Since there's no direct endpoint, we'll fetch by week
      const response = await getTimesheets(weekStart);
      return response.data;
    },
  });
  
  // Filter timesheets
  const filteredTimesheets = useMemo(() => {
    if (!timesheets) return [];
    
    let filtered = timesheets;
    
    if (selectedResource !== 'all') {
      filtered = filtered.filter(t => t.resource_id === selectedResource);
    }
    
    if (selectedProject !== 'all') {
      filtered = filtered.filter(t => t.project_id === selectedProject);
    }
    
    if (selectedStatus !== 'all') {
      filtered = filtered.filter(t => t.status === selectedStatus);
    }
    
    return filtered;
  }, [timesheets, selectedResource, selectedProject, selectedStatus]);
  
  // Calculate summary stats
  const summary = useMemo(() => {
    if (!filteredTimesheets) return { totalPlanned: 0, totalActual: 0, variance: 0 };
    
    const totalPlanned = filteredTimesheets.reduce((sum, t) => sum + (t.planned_hours || 0), 0);
    const totalActual = filteredTimesheets.reduce((sum, t) => sum + (t.actual_hours || 0), 0);
    const variance = totalActual - totalPlanned;
    
    return { totalPlanned, totalActual, variance };
  }, [filteredTimesheets]);
  
  // Mutations
  const createMutation = useMutation({
    mutationFn: (data) => createTimesheet(data),
    onSuccess: () => {
      toast.success('Timesheet created successfully');
      queryClient.invalidateQueries(['allTimesheets']);
      queryClient.invalidateQueries(['actionItems']); // Cross-page
      queryClient.invalidateQueries(['portfolioHealthScores']); // Cross-page
      setShowCreateDialog(false);
      setCreateValues({
        resource_id: '',
        project_id: '',
        phase_id: '',
        week_start_date: weekStart,
        planned_hours: 0,
        actual_hours: 0,
        notes: '',
        status: 'Draft'
      });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to create timesheet');
    },
  });
  
  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateTimesheet(id, data),
    onSuccess: () => {
      toast.success('Timesheet updated successfully');
      queryClient.invalidateQueries(['allTimesheets']);
      queryClient.invalidateQueries(['actionItems']); // Cross-page
      setEditingId(null);
      setEditValues({});
    },
  });
  
  const deleteMutation = useMutation({
    mutationFn: (id) => deleteTimesheet(id),
    onSuccess: () => {
      toast.success('Timesheet deleted successfully');
      queryClient.invalidateQueries(['allTimesheets']);
      queryClient.invalidateQueries(['actionItems']); // Cross-page
    },
  });
  
  // Helper functions
  const getResourceName = (resourceId) => {
    return resources?.find(r => r.id === resourceId)?.name || 'Unknown';
  };
  
  const getProjectName = (projectId) => {
    return projects?.find(p => p.id === projectId)?.name || 'Unknown';
  };
  
  const getClientName = (projectId) => {
    return projects?.find(p => p.id === projectId)?.client_name || 'Unknown';
  };
  
  // Get phases for selected project in create dialog
  const availablePhases = useMemo(() => {
    if (!createValues.project_id || !projects) return [];
    const project = projects.find(p => p.id === createValues.project_id);
    return project?.phases || [];
  }, [createValues.project_id, projects]);
  
  const handleCreateTimesheet = () => {
    // Validation
    if (!createValues.resource_id) {
      toast.error('Please select a resource');
      return;
    }
    if (!createValues.project_id) {
      toast.error('Please select a project');
      return;
    }
    if (!createValues.phase_id) {
      if (availablePhases.length === 0) {
        toast.error('This project has no phases. Please add phases to the project first.');
      } else {
        toast.error('Please select a phase from the dropdown');
      }
      return;
    }
    
    // Calculate week_end_date (4 days after week_start_date = Friday)
    const weekEndDate = format(addDays(new Date(createValues.week_start_date), 4), 'yyyy-MM-dd');
    
    const timesheetData = {
      ...createValues,
      week_end_date: weekEndDate,
      planned_hours: parseFloat(createValues.planned_hours) || 0,
      actual_hours: parseFloat(createValues.actual_hours) || 0,
    };
    
    console.log('Creating timesheet with data:', timesheetData);
    createMutation.mutate(timesheetData);
  };
  
  const handleEdit = (timesheet) => {
    setEditingId(timesheet.id);
    setEditValues({
      planned_hours: timesheet.planned_hours,
      actual_hours: timesheet.actual_hours,
      notes: timesheet.notes || '',
    });
  };
  
  const handleSave = (id) => {
    const variance = (editValues.actual_hours || 0) - (editValues.planned_hours || 0);
    const variancePercentage = editValues.planned_hours > 0 
      ? (variance / editValues.planned_hours * 100)
      : 0;
    
    updateMutation.mutate({
      id,
      data: {
        ...editValues,
        variance_hours: variance,
        variance_percentage: variancePercentage,
      },
    });
  };
  
  const handleCancel = () => {
    setEditingId(null);
    setEditValues({});
  };
  
  const handleDelete = (id) => {
    if (window.confirm('Are you sure you want to delete this timesheet entry?')) {
      deleteMutation.mutate(id);
    }
  };
  
  const exportToCSV = () => {
    if (!filteredTimesheets || filteredTimesheets.length === 0) {
      toast.error('No data to export');
      return;
    }
    
    const headers = ['Resource', 'Project', 'Client', 'Week Start', 'Planned Hours', 'Actual Hours', 'Variance', 'Status', 'Notes'];
    const rows = filteredTimesheets.map(t => [
      getResourceName(t.resource_id),
      getProjectName(t.project_id),
      getClientName(t.project_id),
      format(new Date(t.week_start_date), 'yyyy-MM-dd'),
      t.planned_hours,
      t.actual_hours,
      t.variance_hours,
      t.status,
      t.notes || ''
    ]);
    
    const csvContent = [headers, ...rows]
      .map(row => row.map(cell => `"${cell}"`).join(','))
      .join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `timesheets_${weekStart}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    toast.success('Report exported successfully');
  };
  
  return (
    <div className="space-y-6" data-testid="manage-timesheets-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Manage Timesheets</h1>
          <p className="text-[#667085] mt-1">View and edit timesheets for all resources</p>
        </div>
        <div className="flex gap-2">
          <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
            <DialogTrigger asChild>
              <Button data-testid="create-timesheet-btn">
                <Plus className="h-4 w-4 mr-2" />
                Create Timesheet
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl w-full max-h-[90vh] overflow-y-auto md:max-h-none">
              <DialogHeader>
                <DialogTitle>Create New Timesheet Entry</DialogTitle>
                <DialogDescription>
                  Create a timesheet entry for any resource. As super admin, you can create entries for any week.
                </DialogDescription>
              </DialogHeader>
              
              <div className="space-y-4 py-4">
                {/* Resource Selection */}
                <div>
                  <Label>Resource *</Label>
                  <Select 
                    value={createValues.resource_id} 
                    onValueChange={(value) => setCreateValues({...createValues, resource_id: value})}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select resource" />
                    </SelectTrigger>
                    <SelectContent>
                      {resources?.map((resource) => (
                        <SelectItem key={resource.id} value={resource.id}>
                          {resource.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                {/* Project Selection */}
                <div>
                  <Label>Project *</Label>
                  <Select 
                    value={createValues.project_id} 
                    onValueChange={(value) => setCreateValues({...createValues, project_id: value, phase_id: ''})}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select project" />
                    </SelectTrigger>
                    <SelectContent>
                      {projects?.map((project) => (
                        <SelectItem key={project.id} value={project.id}>
                          {project.name} - {project.client_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                {/* Phase Selection */}
                <div>
                  <Label>Phase *</Label>
                  <Select 
                    value={createValues.phase_id || undefined} 
                    onValueChange={(value) => {
                      console.log('Phase selected:', value);
                      setCreateValues({...createValues, phase_id: value});
                    }}
                    disabled={!createValues.project_id || availablePhases.length === 0}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={
                        !createValues.project_id 
                          ? "Select project first" 
                          : availablePhases.length === 0 
                            ? "No phases available" 
                            : "Select phase"
                      } />
                    </SelectTrigger>
                    <SelectContent>
                      {availablePhases.length > 0 ? (
                        availablePhases.map((phase) => (
                          <SelectItem key={phase.id} value={phase.id}>
                            {phase.name}
                          </SelectItem>
                        ))
                      ) : (
                        <SelectItem value="no-phases" disabled>
                          No phases available for this project
                        </SelectItem>
                      )}
                    </SelectContent>
                  </Select>
                  {createValues.project_id && availablePhases.length === 0 && (
                    <p className="text-xs text-amber-600 mt-1">
                      This project has no phases defined. Please add phases to the project first.
                    </p>
                  )}
                </div>
                
                {/* Week Starting */}
                <div>
                  <Label>Week Starting *</Label>
                  <Input
                    type="date"
                    value={createValues.week_start_date}
                    onChange={(e) => setCreateValues({...createValues, week_start_date: e.target.value})}
                  />
                  <p className="text-xs text-gray-500 mt-1">Select any Monday (week start)</p>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  {/* Planned Hours */}
                  <div>
                    <Label>Planned Hours *</Label>
                    <Input
                      type="number"
                      step="0.5"
                      min="0"
                      value={createValues.planned_hours}
                      onChange={(e) => setCreateValues({...createValues, planned_hours: e.target.value})}
                    />
                  </div>
                  
                  {/* Actual Hours */}
                  <div>
                    <Label>Actual Hours *</Label>
                    <Input
                      type="number"
                      step="0.5"
                      min="0"
                      value={createValues.actual_hours}
                      onChange={(e) => setCreateValues({...createValues, actual_hours: e.target.value})}
                    />
                  </div>
                </div>
                
                {/* Notes */}
                <div>
                  <Label>Notes (Optional)</Label>
                  <Textarea
                    value={createValues.notes}
                    onChange={(e) => setCreateValues({...createValues, notes: e.target.value})}
                    placeholder="Add any notes about this timesheet entry..."
                    rows={3}
                  />
                </div>
                
                {/* Status */}
                <div>
                  <Label>Status</Label>
                  <Select 
                    value={createValues.status} 
                    onValueChange={(value) => setCreateValues({...createValues, status: value})}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Draft">Draft</SelectItem>
                      <SelectItem value="Submitted">Submitted</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              <div className="flex justify-end gap-2">
                <Button 
                  variant="outline" 
                  onClick={() => setShowCreateDialog(false)}
                  disabled={createMutation.isPending}
                >
                  Cancel
                </Button>
                <Button 
                  onClick={handleCreateTimesheet}
                  disabled={createMutation.isPending}
                >
                  {createMutation.isPending ? 'Creating...' : 'Create Timesheet'}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
          
          <Button onClick={exportToCSV} variant="outline" data-testid="export-csv-btn">
            <Download className="h-4 w-4 mr-2" />
            Export CSV
          </Button>
        </div>
      </div>
      
      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Week Filter */}
            <div>
              <Label className="flex items-center gap-2 mb-2">
                <Calendar className="h-4 w-4" />
                Week Starting
              </Label>
              <Input
                type="date"
                value={weekStart}
                onChange={(e) => setWeekStart(e.target.value)}
                data-testid="week-filter"
              />
            </div>
            
            {/* Resource Filter */}
            <div>
              <Label className="flex items-center gap-2 mb-2">
                <Users className="h-4 w-4" />
                Resource
              </Label>
              <Select value={selectedResource} onValueChange={setSelectedResource}>
                <SelectTrigger data-testid="resource-filter">
                  <SelectValue placeholder="All Resources" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Resources</SelectItem>
                  {resources?.map((resource) => (
                    <SelectItem key={resource.id} value={resource.id}>
                      {resource.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            {/* Project Filter */}
            <div>
              <Label className="flex items-center gap-2 mb-2">
                <Briefcase className="h-4 w-4" />
                Project
              </Label>
              <Select value={selectedProject} onValueChange={setSelectedProject}>
                <SelectTrigger data-testid="project-filter">
                  <SelectValue placeholder="All Projects" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Projects</SelectItem>
                  {projects?.map((project) => (
                    <SelectItem key={project.id} value={project.id}>
                      {project.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            {/* Status Filter */}
            <div>
              <Label className="mb-2">Status</Label>
              <Select value={selectedStatus} onValueChange={setSelectedStatus}>
                <SelectTrigger data-testid="status-filter">
                  <SelectValue placeholder="All Statuses" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="Draft">Draft</SelectItem>
                  <SelectItem value="Submitted">Submitted</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>
      
      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-[#667085]">Total Planned</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary.totalPlanned.toFixed(1)}h</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-[#667085]">Total Actual</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary.totalActual.toFixed(1)}h</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-[#667085]">Variance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${
              summary.variance > 0 ? 'text-red-600' : summary.variance < 0 ? 'text-green-600' : ''
            }`}>
              {summary.variance > 0 ? '+' : ''}{summary.variance.toFixed(1)}h
            </div>
          </CardContent>
        </Card>
      </div>
      
      {/* Timesheets Table */}
      <Card>
        <CardHeader>
          <CardTitle>Timesheet Entries ({filteredTimesheets?.length || 0})</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8 text-[#667085]">Loading timesheets...</div>
          ) : filteredTimesheets?.length === 0 ? (
            <div className="text-center py-8 text-[#667085]">No timesheets found for the selected filters</div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Resource</TableHead>
                    <TableHead>Project / Client</TableHead>
                    <TableHead>Week</TableHead>
                    <TableHead>Planned (h)</TableHead>
                    <TableHead>Actual (h)</TableHead>
                    <TableHead>Variance</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Notes</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredTimesheets.map((timesheet) => (
                    <TableRow key={timesheet.id} data-testid={`timesheet-row-${timesheet.id}`}>
                      <TableCell className="font-medium">{getResourceName(timesheet.resource_id)}</TableCell>
                      <TableCell>
                        <div className="font-medium">{getProjectName(timesheet.project_id)}</div>
                        <div className="text-xs text-gray-500 mt-0.5">{getClientName(timesheet.project_id)}</div>
                      </TableCell>
                      <TableCell>{format(new Date(timesheet.week_start_date), 'MMM d, yyyy')}</TableCell>
                      <TableCell>
                        {editingId === timesheet.id ? (
                          <Input
                            type="number"
                            step="0.5"
                            value={editValues.planned_hours}
                            onChange={(e) => setEditValues({...editValues, planned_hours: parseFloat(e.target.value) || 0})}
                            className="w-20"
                          />
                        ) : (
                          timesheet.planned_hours
                        )}
                      </TableCell>
                      <TableCell>
                        {editingId === timesheet.id ? (
                          <Input
                            type="number"
                            step="0.5"
                            value={editValues.actual_hours}
                            onChange={(e) => setEditValues({...editValues, actual_hours: parseFloat(e.target.value) || 0})}
                            className="w-20"
                          />
                        ) : (
                          timesheet.actual_hours
                        )}
                      </TableCell>
                      <TableCell>
                        <span className={`font-medium ${
                          timesheet.variance_hours > 0 ? 'text-red-600' : 
                          timesheet.variance_hours < 0 ? 'text-green-600' : ''
                        }`}>
                          {timesheet.variance_hours > 0 ? '+' : ''}{timesheet.variance_hours?.toFixed(1) || 0}h
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge variant={timesheet.status === 'Submitted' ? 'default' : 'secondary'}>
                          {timesheet.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {editingId === timesheet.id ? (
                          <Input
                            value={editValues.notes}
                            onChange={(e) => setEditValues({...editValues, notes: e.target.value})}
                            placeholder="Add notes"
                          />
                        ) : (
                          <span className="text-sm text-[#667085]">{timesheet.notes || '-'}</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {editingId === timesheet.id ? (
                          <div className="flex gap-2 justify-end">
                            <Button size="sm" onClick={() => handleSave(timesheet.id)} data-testid="save-btn">
                              Save
                            </Button>
                            <Button size="sm" variant="outline" onClick={handleCancel} data-testid="cancel-btn">
                              Cancel
                            </Button>
                          </div>
                        ) : (
                          <div className="flex gap-2 justify-end">
                            <Button 
                              size="sm" 
                              variant="ghost" 
                              onClick={() => handleEdit(timesheet)}
                              data-testid={`edit-btn-${timesheet.id}`}
                            >
                              <Edit2 className="h-4 w-4" />
                            </Button>
                            <Button 
                              size="sm" 
                              variant="ghost" 
                              onClick={() => handleDelete(timesheet.id)}
                              className="text-red-600 hover:text-red-700 hover:bg-red-50"
                              data-testid={`delete-btn-${timesheet.id}`}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default ManageTimesheets;
