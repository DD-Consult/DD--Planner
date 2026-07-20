import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getProjects, createProject, updateProject, deleteProject, getMe, getProjectAllocations, createAllocation, deleteAllocation, getResources, getAllocations } from '../api';
import { format, parseISO } from 'date-fns';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import WeekdayDateInput from '../components/ui/weekday-date-input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Plus, Edit, Trash2, Sparkles, Folder, Bell } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../components/ui/tooltip';
import ProjectWizard from '../components/ProjectWizard';
import AllocationEditor from '../components/AllocationEditor';
import { enrichProjects, ProjectStatusGroups } from '../components/ProjectStatusTable';

const Projects = ({ token }) => {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isWizardOpen, setIsWizardOpen] = useState(false);
  const [editingProject, setEditingProject] = useState(null);
  const [phases, setPhases] = useState([]);
  const [editAllocations, setEditAllocations] = useState([]);
  const [existingAllocations, setExistingAllocations] = useState([]);
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    name: '',
    client_name: '',
    project_objective: '',
    status: 'Active',
    is_draft: false,
    start_date: '',
    end_date: '',
    budgeted_hours: '',
    project_lead_id: '',
    google_drive_url: '',
  });

  const queryClient = useQueryClient();

  const { data: userData } = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const response = await getMe();
      return response.data;
    },
  });

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await getProjects();
      return response.data;
    },
  });

  const { data: resources } = useQuery({
    queryKey: ['resources'],
    queryFn: async () => { const r = await getResources(); return r.data; },
  });

  const { data: allocations } = useQuery({
    queryKey: ['allocations'],
    queryFn: async () => { const r = await getAllocations(); return r.data; },
  });

  const createMutation = useMutation({
    mutationFn: createProject,
    onSuccess: () => {
      queryClient.invalidateQueries(['projects']);
      queryClient.invalidateQueries(['portfolioHealthScores']);
      queryClient.invalidateQueries(['actionItems']);
      setIsDialogOpen(false);
      resetForm();
      toast.success('Project created successfully');
    },
    onError: (error) => {
      console.error('Create project error:', error);
      toast.error('Failed to create project');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateProject(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['projects']);
      queryClient.invalidateQueries(['portfolioHealthScores']);
      queryClient.invalidateQueries(['actionItems']);
      setIsDialogOpen(false);
      resetForm();
      toast.success('Project updated successfully');
    },
    onError: (error) => {
      console.error('Update project error:', error);
      toast.error('Failed to update project');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteProject,
    onSuccess: () => {
      queryClient.invalidateQueries(['projects']);
      queryClient.invalidateQueries(['portfolioHealthScores']);
      queryClient.invalidateQueries(['actionItems']);
    },
  });

  const resetForm = () => {
    setFormData({
      name: '',
      client_name: '',
      project_objective: '',
      status: 'Active',
      is_draft: false,
      start_date: '',
      end_date: '',
      budgeted_hours: '',
      project_lead_id: '',
      google_drive_url: '',
    });
    setPhases([]);
    setEditingProject(null);
  };

  const handleOpenDialog = async (project = null, e) => {
    if (e) e.stopPropagation();
    if (project) {
      setEditingProject(project);
      setFormData({
        name: project.name,
        client_name: project.client_name,
        project_objective: project.project_objective || '',
        status: project.status,
        is_draft: project.is_draft || false,
        start_date: project.start_date.split('T')[0],
        end_date: project.end_date.split('T')[0],
        budgeted_hours: project.budgeted_hours || '',
        project_lead_id: project.project_lead_id || '',
        google_drive_url: project.google_drive_url || '',
      });
      setPhases(project.phases || []);
      
      // Fetch existing allocations for this project
      try {
        const response = await getProjectAllocations(project.id);
        const existingAllocs = response.data.map(alloc => ({
          ...alloc,
          start_date: alloc.start_date.split('T')[0],
          end_date: alloc.end_date.split('T')[0],
          allocation_type: alloc.allocation_type || 'percentage',
        }));
        setExistingAllocations(existingAllocs);
        setEditAllocations(existingAllocs);
      } catch (err) {
        console.error('Failed to fetch allocations:', err);
        setExistingAllocations([]);
        setEditAllocations([]);
      }
    } else {
      resetForm();
      setExistingAllocations([]);
      setEditAllocations([]);
    }
    setIsDialogOpen(true);
  };

  // Allocation mutations
  const createAllocationMutation = useMutation({
    mutationFn: createAllocation,
    onSuccess: () => {
      queryClient.invalidateQueries(['allocations']);
    },
  });

  const deleteAllocationMutation = useMutation({
    mutationFn: deleteAllocation,
    onSuccess: () => {
      queryClient.invalidateQueries(['allocations']);
    },
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    const submitData = { ...formData };
    
    // Sanitize budgeted_hours
    if (submitData.budgeted_hours === '') {
      submitData.budgeted_hours = null;
    } else {
      submitData.budgeted_hours = parseFloat(submitData.budgeted_hours);
    }
    
    // Sanitize google_drive_url
    if (!submitData.google_drive_url) submitData.google_drive_url = null;

    if (phases.length > 0) {
      submitData.phases = phases.map(p => ({
        ...p,
        budgeted_hours: p.budgeted_hours === '' ? null : parseFloat(p.budgeted_hours)
      }));
    }
    
    if (editingProject) {
      // Update project
      try {
        await updateMutation.mutateAsync({ id: editingProject.id, data: submitData });
        
        // Handle allocation changes
        // Find allocations to delete (in existing but not in edit)
        const toDelete = existingAllocations.filter(
          existing => !editAllocations.find(edit => edit.id === existing.id)
        );
        
        // Find allocations to add (in edit but no id, meaning new)
        const toAdd = editAllocations.filter(alloc => !alloc.id);
        
        // Delete removed allocations
        for (const alloc of toDelete) {
          try {
            await deleteAllocation(alloc.id);
          } catch (err) {
            console.error('Failed to delete allocation:', err);
          }
        }
        
        // Add new allocations
        for (const alloc of toAdd) {
          try {
            await createAllocation({
              ...alloc,
              project_id: editingProject.id,
            });
          } catch (err) {
            console.error('Failed to create allocation:', err);
          }
        }
        
        queryClient.invalidateQueries(['allocations']);
      } catch (error) {
        console.error("Error updating project:", error);
      }
    } else {
      createMutation.mutate(submitData);
    }
  };

  const handleDelete = (id, e) => {
    if (e && e.stopPropagation) e.stopPropagation();
    if (window.confirm('Are you sure you want to delete this project?')) {
      deleteMutation.mutate(id);
    }
  };

  const handleRowClick = (projectId) => {
    navigate(`/projects/${projectId}`);
  };

  // Enrich projects with team/phase/health/progress — shared with Dashboard for consistency
  const enrichedProjects = React.useMemo(
    () => enrichProjects(projects, allocations, resources),
    [projects, allocations, resources]
  );

  const applyPhaseTemplate = () => {
    const template = [
      { name: 'Discovery',  start_date: '', end_date: '', status: 'Not Started', budgeted_hours: '' },
      { name: 'Initiate',   start_date: '', end_date: '', status: 'Not Started', budgeted_hours: '' },
      { name: 'Plan',       start_date: '', end_date: '', status: 'Not Started', budgeted_hours: '' },
      { name: 'Execute',    start_date: '', end_date: '', status: 'Not Started', budgeted_hours: '' },
      { name: 'Close',      start_date: '', end_date: '', status: 'Not Started', budgeted_hours: '' },
    ];
    setPhases(template);
    toast.success('DD phase template applied — add your dates to each phase');
  };

  const addPhase = () => {
    setPhases([...phases, { name: '', start_date: '', end_date: '', status: 'Not Started', budgeted_hours: '' }]);
  };

  const removePhase = (index) => {
    setPhases(phases.filter((_, i) => i !== index));
  };

  const updatePhase = (index, field, value) => {
    const updatedPhases = [...phases];
    updatedPhases[index][field] = value;
    setPhases(updatedPhases);
  };

  const getStatusBadge = (status) => {
    const variants = {
      Active: 'bg-[#16B364] text-white',
      Pipeline: 'bg-[#F4B740] text-[#0B1220]',
      Completed: 'bg-[#667085] text-white',
    };
    return <Badge className={variants[status] || 'bg-[#667085] text-white'}>{status}</Badge>;
  };

  const isAdmin = userData?.role === 'admin' || userData?.role === 'super_admin';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold flex items-center gap-3" style={{ fontFamily: 'Space Grotesk' }}>
            <Folder size={32} />
            Projects
          </h1>
          <p className="text-sm text-[#667085] mt-1">Manage client projects and timelines</p>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            <Button 
              onClick={() => setIsWizardOpen(true)} 
              data-testid="new-project-wizard"
              className="bg-[#1570EF] text-white hover:bg-[#0E5FD9] shadow-md"
            >
              <Sparkles size={16} className="mr-2" />
              New Project Wizard
            </Button>
            <Button 
              variant="outline" 
              onClick={(e) => handleOpenDialog(null, e)} 
              data-testid="add-project-button"
              className="border-[#1570EF] text-[#1570EF] hover:bg-[#1570EF] hover:text-white"
            >
              <Plus size={16} className="mr-2" />
              Quick Add
            </Button>
          </div>
        )}
      </div>

      {/* Projects — rich rows grouped by status (Active expanded by default) */}
      {isLoading ? (
        <div className="text-center py-12 text-[#667085]">
          <p>Loading projects...</p>
        </div>
      ) : projects?.length === 0 ? (
        <div className="bg-white border border-[#E6E8EC] rounded-lg p-12 text-center">
          <Folder size={48} className="mx-auto mb-4 text-[#98A2B3]" />
          <p className="text-[#667085] mb-4">No projects yet</p>
          {isAdmin && (
            <Button onClick={() => setIsWizardOpen(true)}>
              <Sparkles size={16} className="mr-2" />
              Create Your First Project
            </Button>
          )}
        </div>
      ) : (
        <ProjectStatusGroups
          projects={enrichedProjects}
          isAdmin={isAdmin}
          onEdit={(project) => handleOpenDialog(project, null)}
          onDelete={(pid) => handleDelete(pid, null)}
        />
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="project-dialog">
          <DialogHeader>
            <DialogTitle>{editingProject ? 'Edit Project' : 'Add New Project'}</DialogTitle>
            <DialogDescription>
              {editingProject
                ? 'Update project information and phases'
                : 'Create a new client project'}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-6 mt-4">
            {/* Basic Information */}
            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-[#0B1220]">Basic Information</h3>
              
              <div>
                <Label htmlFor="name">Project Name *</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                  data-testid="project-name-input"
                />
              </div>

              <div>
                <Label htmlFor="client_name">Client Name *</Label>
                <Input
                  id="client_name"
                  value={formData.client_name}
                  onChange={(e) => setFormData({ ...formData, client_name: e.target.value })}
                  required
                  data-testid="project-client-input"
                />
              </div>

              <div>
                <Label htmlFor="project_objective">Project Objective / Outcome</Label>
                <textarea
                  id="project_objective"
                  className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 resize-none"
                  value={formData.project_objective}
                  onChange={(e) => setFormData({ ...formData, project_objective: e.target.value })}
                  placeholder="Describe what this project is designed to deliver in business terms..."
                  rows={3}
                  data-testid="project-objective-input"
                />
              </div>

              <div>
                <Label htmlFor="status">Status *</Label>
                <Select
                  value={formData.status}
                  onValueChange={(value) => setFormData({ ...formData, status: value })}
                >
                  <SelectTrigger id="status" data-testid="project-status-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Active">Active</SelectItem>
                    <SelectItem value="Pipeline">Pipeline</SelectItem>
                    <SelectItem value="Completed">Completed</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="budgeted_hours">Total Project Budget (Hours)</Label>
                <Input
                  id="budgeted_hours"
                  type="number"
                  min="0"
                  step="0.5"
                  value={formData.budgeted_hours}
                  onChange={(e) => setFormData({ ...formData, budgeted_hours: e.target.value })}
                  placeholder="Optional: Total hours budgeted for project"
                  data-testid="project-budget-input"
                />
              </div>

              <div>
                <Label htmlFor="project_lead">Project Lead *</Label>
                <Select value={formData.project_lead_id} onValueChange={(val) => setFormData({ ...formData, project_lead_id: val })}>
                  <SelectTrigger id="project_lead" data-testid="project-lead-select">
                    <SelectValue placeholder="Select project lead" />
                  </SelectTrigger>
                  <SelectContent>
                    {resources?.filter(r => r.active !== false).map(r => (
                      <SelectItem key={r.id} value={r.id}>{r.name} ({r.role})</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="google_drive_url">Google Drive Folder URL</Label>
                <Input
                  id="google_drive_url"
                  type="url"
                  value={formData.google_drive_url}
                  onChange={(e) => setFormData({ ...formData, google_drive_url: e.target.value })}
                  placeholder="Optional: https://drive.google.com/..."
                  data-testid="project-drive-url"
                />
              </div>

              <div className="flex items-center space-x-2 p-3 bg-blue-50 rounded-lg border border-blue-200">
                <Checkbox
                  id="is_draft"
                  checked={formData.is_draft}
                  onCheckedChange={(checked) => setFormData({ ...formData, is_draft: checked })}
                  data-testid="project-draft-checkbox"
                />
                <div className="flex-1">
                  <label
                    htmlFor="is_draft"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                  >
                    Mark as Draft/Scenario
                  </label>
                  <p className="text-xs text-gray-600 mt-1">
                    Draft projects are hidden from dashboard unless "Show Scenario/Drafts" toggle is ON
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="start_date">Start Date *</Label>
                  <WeekdayDateInput
                    id="start_date"
                    value={formData.start_date}
                    onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                    required
                    data-testid="project-start-date-input"
                  />
                </div>
                <div>
                  <Label htmlFor="end_date">End Date *</Label>
                  <WeekdayDateInput
                    id="end_date"
                    value={formData.end_date}
                    onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                    required
                    data-testid="project-end-date-input"
                  />
                </div>
              </div>
            </div>

            {/* Phases Section */}
            <div className="space-y-4 border-t border-[#E6E8EC] pt-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-[#0B1220]">Project Phases (Optional)</h3>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={applyPhaseTemplate}
                    className="text-[#1B2A47] border-[#1B2A47] hover:bg-[#1B2A47] hover:text-white"
                    data-testid="use-template-btn"
                  >
                    Use DD Template
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={addPhase}
                    data-testid="add-phase-button"
                  >
                    <Plus size={14} className="mr-1" />
                    Add Phase
                  </Button>
                </div>
              </div>

              {phases.length === 0 && (
                <p className="text-xs text-[#667085] italic">No phases defined. Add phases to track project milestones.</p>
              )}

              {phases.map((phase, index) => (
                <div key={index} className="border border-[#E6E8EC] rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-[#667085]">Phase {index + 1}</span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => removePhase(index)}
                      data-testid={`remove-phase-${index}`}
                    >
                      <Trash2 size={14} className="text-[#EF4444]" />
                    </Button>
                  </div>

                  <div>
                    <Label htmlFor={`phase-name-${index}`}>Phase Name</Label>
                    <Input
                      id={`phase-name-${index}`}
                      value={phase.name}
                      onChange={(e) => updatePhase(index, 'name', e.target.value)}
                      placeholder="e.g., Discovery, Development, Launch"
                      data-testid={`phase-name-${index}`}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label htmlFor={`phase-start-${index}`}>Start Date</Label>
                      <WeekdayDateInput
                        id={`phase-start-${index}`}
                        value={phase.start_date}
                        onChange={(e) => updatePhase(index, 'start_date', e.target.value)}
                        data-testid={`phase-start-${index}`}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`phase-end-${index}`}>End Date</Label>
                      <WeekdayDateInput
                        id={`phase-end-${index}`}
                        value={phase.end_date}
                        onChange={(e) => updatePhase(index, 'end_date', e.target.value)}
                        data-testid={`phase-end-${index}`}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label htmlFor={`phase-status-${index}`}>Status</Label>
                      <Select
                        value={phase.status}
                        onValueChange={(value) => updatePhase(index, 'status', value)}
                      >
                        <SelectTrigger id={`phase-status-${index}`} data-testid={`phase-status-${index}`}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Not Started">Not Started</SelectItem>
                          <SelectItem value="In Progress">In Progress</SelectItem>
                          <SelectItem value="Completed">Completed</SelectItem>
                          <SelectItem value="On Hold">On Hold</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label htmlFor={`phase-budget-${index}`}>Budget (Hours)</Label>
                      <Input
                        id={`phase-budget-${index}`}
                        type="number"
                        min="0"
                        step="0.5"
                        value={phase.budgeted_hours || ''}
                        onChange={(e) => updatePhase(index, 'budgeted_hours', e.target.value)}
                        placeholder="Optional"
                        data-testid={`phase-budget-${index}`}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Resource Allocations Section - Only show when editing */}
            {editingProject && (
              <div className="space-y-4 border-t border-[#E6E8EC] pt-4">
                <AllocationEditor
                  allocations={editAllocations}
                  onAllocationsChange={setEditAllocations}
                  projectStartDate={formData.start_date}
                  projectEndDate={formData.end_date}
                  showTitle={true}
                />
              </div>
            )}

            <div className="flex justify-end gap-2 pt-4 border-t border-[#E6E8EC]">
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
                data-testid="submit-project"
              >
                {createMutation.isLoading || updateMutation.isLoading
                  ? 'Saving...'
                  : editingProject
                  ? 'Update Project'
                  : 'Create Project'}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Project Wizard */}
      <ProjectWizard open={isWizardOpen} onOpenChange={setIsWizardOpen} />
    </div>
  );
};

export default Projects;
