import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getMyProjectsForStatus, createStatusUpdate, getStatusOptions, checkTimesheetUpdateAllowed } from '../api';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { Textarea } from './ui/textarea';
import { Input } from './ui/input';
import { Alert, AlertDescription } from './ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './ui/dialog';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from './ui/accordion';
import { 
  ClipboardCheck, 
  AlertCircle, 
  CheckCircle2, 
  Clock,
  TrendingUp,
  AlertTriangle,
  Loader2,
  Calendar,
  ChevronRight,
  Plus,
  Trash2,
  ShieldAlert
} from 'lucide-react';
import { toast } from 'sonner';
import { format, parseISO, differenceInDays } from 'date-fns';

const ProjectStatusCheckin = () => {
  const queryClient = useQueryClient();
  const [selectedProject, setSelectedProject] = useState(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  
  // Form state
  const [formData, setFormData] = useState({
    health: 'Green',
    schedule_status: 'On Track',
    accomplishments: '',
    blockers: '',
    next_steps: '',
    notes: ''
  });
  const [newRisks, setNewRisks] = useState([]); // [{description, impact, probability, mitigation, category}]
  const [riskDraft, setRiskDraft] = useState({ description: '', impact: 'Medium', probability: 'Medium', mitigation: '', category: 'Risk' });

  // Check if updates are allowed (Thursday/Friday Sydney time)
  const { data: updateAllowed } = useQuery({
    queryKey: ['timesheetAllowed'],
    queryFn: async () => {
      const response = await checkTimesheetUpdateAllowed();
      return response.data;
    },
    refetchInterval: 60000, // Check every minute
  });

  // Fetch projects user can update
  const { data: projects, isLoading } = useQuery({
    queryKey: ['myProjectsForStatus'],
    queryFn: async () => {
      const response = await getMyProjectsForStatus();
      return response.data;
    },
  });

  // Fetch status options
  const { data: statusOptions } = useQuery({
    queryKey: ['statusOptions'],
    queryFn: async () => {
      const response = await getStatusOptions();
      return response.data;
    },
  });

  // Submit status update mutation
  const submitMutation = useMutation({
    mutationFn: (data) => createStatusUpdate(data),
    onSuccess: () => {
      toast.success('Status update submitted successfully!');
      queryClient.invalidateQueries(['myProjectsForStatus']);
      queryClient.invalidateQueries(['projects']);
      queryClient.invalidateQueries(['actionItems']); // Cross-page: clears "status update due" action item
      queryClient.invalidateQueries(['portfolioHealthScores']); // Cross-page: schedule score
      queryClient.invalidateQueries(['projectStatusUpdates']); // Cross-page: project detail
      setIsDialogOpen(false);
      setSelectedProject(null);
      resetForm();
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to submit status update');
    },
  });

  const resetForm = () => {
    setFormData({
      health: 'Green',
      schedule_status: 'On Track',
      accomplishments: '',
      blockers: '',
      next_steps: '',
      notes: ''
    });
    setNewRisks([]);
    setRiskDraft({ description: '', impact: 'Medium', probability: 'Medium', mitigation: '', category: 'Risk' });
  };

  const openStatusDialog = (project) => {
    setSelectedProject(project);
    
    const currentHealth = project.health || 'Green';
    const currentSchedule = project.schedule_status || 'On Track';
    
    setFormData({
      health: currentHealth,
      schedule_status: currentSchedule,
      accomplishments: '',
      blockers: '',
      next_steps: '',
      notes: ''
    });
    setNewRisks([]);
    setRiskDraft({ description: '', impact: 'Medium', probability: 'Medium', mitigation: '', category: 'Risk' });
    
    setIsDialogOpen(true);
  };

  const handleAddRisk = () => {
    if (!riskDraft.description.trim()) {
      toast.error('Please enter a risk description');
      return;
    }
    setNewRisks(prev => [...prev, { ...riskDraft, description: riskDraft.description.trim() }]);
    setRiskDraft({ description: '', impact: 'Medium', probability: 'Medium', mitigation: '', category: 'Risk' });
  };

  const handleRemoveRisk = (idx) => {
    setNewRisks(prev => prev.filter((_, i) => i !== idx));
  };

  const handleSubmit = () => {
    if (!selectedProject) return;
    
    // Check if updates are allowed (Thursday/Friday)
    if (!updateAllowed?.allowed) {
      toast.error('Status updates are only allowed on Thursday and Friday (Sydney time)');
      return;
    }
    
    submitMutation.mutate({
      project_id: selectedProject.id,
      ...formData,
      new_risks: newRisks.length > 0 ? newRisks : undefined,
    });
  };

  const isUpdateAllowed = updateAllowed?.allowed ?? false;

  const getHealthColor = (health) => {
    const colors = {
      Green: 'bg-[#16B364] text-white',
      Amber: 'bg-[#F4B740] text-white',
      Red: 'bg-[#EF4444] text-white',
    };
    return colors[health] || 'bg-[#667085] text-white';
  };

  const getScheduleColor = (status) => {
    const colors = {
      'On Track': 'bg-[#16B364]/10 text-[#16B364] border-[#16B364]',
      'Ahead of Schedule': 'bg-[#1570EF]/10 text-[#1570EF] border-[#1570EF]',
      'Delayed': 'bg-[#F4B740]/10 text-[#F4B740] border-[#F4B740]',
      'At Risk': 'bg-[#EF4444]/10 text-[#EF4444] border-[#EF4444]',
    };
    return colors[status] || 'bg-[#667085]/10 text-[#667085] border-[#667085]';
  };

  const getHealthIcon = (health) => {
    switch (health) {
      case 'Green': return <CheckCircle2 size={14} className="text-[#16B364]" />;
      case 'Amber': return <AlertTriangle size={14} className="text-[#F4B740]" />;
      case 'Red': return <AlertCircle size={14} className="text-[#EF4444]" />;
      default: return <Clock size={14} className="text-[#667085]" />;
    }
  };

  // Calculate days since last update
  const getDaysSinceUpdate = (project) => {
    if (!project.latest_status?.created_at) return null;
    try {
      const lastUpdate = parseISO(project.latest_status.created_at);
      return differenceInDays(new Date(), lastUpdate);
    } catch {
      return null;
    }
  };

  // Check if update is needed (more than 7 days since last update)
  const needsUpdate = (project) => {
    const days = getDaysSinceUpdate(project);
    return days === null || days >= 7;
  };

  if (isLoading) {
    return (
      <Card data-testid="project-status-checkin">
        <CardHeader>
          <CardTitle className="flex items-center gap-2" style={{ fontFamily: 'Space Grotesk' }}>
            <ClipboardCheck size={20} className="text-[#1570EF]" />
            Project Status Check-in
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-[#667085]">
            <Loader2 className="animate-spin mr-2" size={20} />
            Loading projects...
          </div>
        </CardContent>
      </Card>
    );
  }

  const projectsNeedingUpdate = projects?.filter(needsUpdate) || [];
  const projectsUpToDate = projects?.filter(p => !needsUpdate(p)) || [];

  return (
    <>
      <Card data-testid="project-status-checkin">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2" style={{ fontFamily: 'Space Grotesk' }}>
              <ClipboardCheck size={20} className="text-[#1570EF]" />
              Project Status Check-in
            </CardTitle>
            {projectsNeedingUpdate.length > 0 && (
              <Badge variant="outline" className="border-[#F4B740] text-[#F4B740]">
                {projectsNeedingUpdate.length} need update
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {/* Thursday/Friday restriction banner */}
          {!isUpdateAllowed && updateAllowed && (
            <Alert className="mb-4 bg-amber-50 border-amber-200" data-testid="status-update-restriction-banner">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              <AlertDescription className="text-amber-800">
                <div className="font-medium">Status updates are only available on Thursday and Friday</div>
                <div className="text-sm mt-1 flex items-center gap-2">
                  <Calendar size={14} />
                  <span>Current day (Sydney): <strong>{updateAllowed.current_day}</strong></span>
                  {updateAllowed.next_allowed_day && (
                    <span className="text-amber-600">• Next allowed: <strong>{updateAllowed.next_allowed_day}</strong></span>
                  )}
                </div>
              </AlertDescription>
            </Alert>
          )}
          
          {!projects || projects.length === 0 ? (
            <div className="text-center py-8 text-[#667085]">
              <ClipboardCheck size={48} className="mx-auto mb-4 text-[#98A2B3]" />
              <p>No projects assigned to you</p>
              <p className="text-sm">You'll see your projects here once assigned</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Projects needing update */}
              {projectsNeedingUpdate.length > 0 && (
                <div className="space-y-2">
                  <div className="text-sm font-medium text-[#667085] flex items-center gap-2">
                    <AlertTriangle size={14} className="text-[#F4B740]" />
                    Needs Status Update
                  </div>
                  {projectsNeedingUpdate.map((project) => (
                    <div
                      key={project.id}
                      className={`flex items-center justify-between p-3 border rounded-lg transition-colors ${
                        isUpdateAllowed 
                          ? 'border-[#F4B740]/30 bg-[#FEF6E7] hover:bg-[#FEF0D3] cursor-pointer'
                          : 'border-[#E6E8EC] bg-[#F9FAFB] opacity-75'
                      }`}
                      onClick={() => isUpdateAllowed && openStatusDialog(project)}
                      data-testid={`status-project-${project.id}`}
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-[#0B1220]">{project.name}</span>
                          {project.latest_status && (
                            <Badge className={getHealthColor(project.latest_status.health)} variant="secondary">
                              {project.latest_status.health}
                            </Badge>
                          )}
                        </div>
                        <div className="text-xs text-[#667085] mt-1">
                          {project.latest_status ? (
                            <>Last update: {format(parseISO(project.latest_status.created_at), 'MMM d, yyyy')}</>
                          ) : (
                            <>No status updates yet</>
                          )}
                        </div>
                      </div>
                      <Button 
                        size="sm" 
                        variant="outline" 
                        disabled={!isUpdateAllowed}
                        className={isUpdateAllowed 
                          ? "border-[#F4B740] text-[#F4B740] hover:bg-[#F4B740] hover:text-white"
                          : "border-[#98A2B3] text-[#98A2B3] cursor-not-allowed"
                        }
                      >
                        {isUpdateAllowed ? 'Update Status' : 'Thu/Fri Only'}
                        <ChevronRight size={14} className="ml-1" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}

              {/* Up to date projects */}
              {projectsUpToDate.length > 0 && (
                <Accordion type="single" collapsible className="w-full">
                  <AccordionItem value="up-to-date" className="border-none">
                    <AccordionTrigger className="text-sm font-medium text-[#667085] hover:no-underline py-2">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 size={14} className="text-[#16B364]" />
                        Up to Date ({projectsUpToDate.length})
                      </div>
                    </AccordionTrigger>
                    <AccordionContent>
                      <div className="space-y-2 pt-2">
                        {projectsUpToDate.map((project) => (
                          <div
                            key={project.id}
                            className="flex items-center justify-between p-3 border border-[#E6E8EC] rounded-lg hover:bg-[#F8FAFC] transition-colors cursor-pointer"
                            onClick={() => openStatusDialog(project)}
                          >
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-[#0B1220]">{project.name}</span>
                                {getHealthIcon(project.latest_status?.health)}
                                <Badge variant="outline" className={getScheduleColor(project.latest_status?.schedule_status)}>
                                  {project.latest_status?.schedule_status || 'Unknown'}
                                </Badge>
                              </div>
                              <div className="flex items-center gap-4 mt-1">
                                <div className="flex items-center gap-2 text-xs text-[#667085]">
                                  <Progress value={project.latest_status?.actual_progress || 0} className="w-20 h-1.5" />
                                  <span>{project.latest_status?.actual_progress || 0}%</span>
                                </div>
                                <span className="text-xs text-[#667085]">
                                  Updated {getDaysSinceUpdate(project)} days ago
                                </span>
                              </div>
                            </div>
                            <Button size="sm" variant="ghost" className="text-[#667085]">
                              Update
                              <ChevronRight size={14} className="ml-1" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Status Update Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-w-lg" data-testid="status-update-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <TrendingUp size={20} className="text-[#1570EF]" />
              Update Project Status
            </DialogTitle>
            <DialogDescription>
              {selectedProject?.name} - Weekly check-in
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-4">
            {/* Health & Schedule Status */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-[#0B1220] mb-2 block">
                  Health Status
                </label>
                <Select
                  value={formData.health}
                  onValueChange={(value) => setFormData(prev => ({ ...prev, health: value }))}
                >
                  <SelectTrigger data-testid="health-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(statusOptions?.health_options || ['Green', 'Amber', 'Red']).map(option => (
                      <SelectItem key={option} value={option}>
                        <div className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full ${
                            option === 'Green' ? 'bg-[#16B364]' :
                            option === 'Amber' ? 'bg-[#F4B740]' : 'bg-[#EF4444]'
                          }`} />
                          {option}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium text-[#0B1220] mb-2 block">
                  Schedule Status
                </label>
                <Select
                  value={formData.schedule_status}
                  onValueChange={(value) => setFormData(prev => ({ ...prev, schedule_status: value }))}
                >
                  <SelectTrigger data-testid="schedule-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(statusOptions?.schedule_options || ['On Track', 'Delayed', 'Ahead of Schedule', 'At Risk']).map(option => (
                      <SelectItem key={option} value={option}>{option}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Accomplishments */}
            <div>
              <label className="text-sm font-medium text-[#0B1220] mb-2 block">
                Accomplishments This Week
              </label>
              <Textarea
                value={formData.accomplishments}
                onChange={(e) => setFormData(prev => ({ ...prev, accomplishments: e.target.value }))}
                placeholder="What was completed this week?"
                rows={2}
                data-testid="accomplishments-input"
              />
            </div>

            {/* Blockers */}
            <div>
              <label className="text-sm font-medium text-[#0B1220] mb-2 block">
                Blockers / Issues
              </label>
              <Textarea
                value={formData.blockers}
                onChange={(e) => setFormData(prev => ({ ...prev, blockers: e.target.value }))}
                placeholder="Any blockers or issues? (Will be auto-added to the risk register as Issues.)"
                rows={2}
                data-testid="blockers-input"
              />
              <p className="text-[11px] text-[#667085] mt-1">
                Each blocker (separate by comma or new line) will be auto-promoted to an <strong>Issue</strong> in the risk register.
              </p>
            </div>

            {/* Next Steps */}
            <div>
              <label className="text-sm font-medium text-[#0B1220] mb-2 block">
                Next Steps
              </label>
              <Textarea
                value={formData.next_steps}
                onChange={(e) => setFormData(prev => ({ ...prev, next_steps: e.target.value }))}
                placeholder="What's planned for next week?"
                rows={2}
                data-testid="next-steps-input"
              />
            </div>

            {/* Risks & Issues — inline adder */}
            <div className="rounded-lg border border-[#E6E8EC] bg-[#FAFBFC] p-3 space-y-3" data-testid="inline-risks-section">
              <div className="flex items-center gap-2">
                <ShieldAlert size={16} className="text-amber-600" />
                <span className="text-sm font-medium text-[#0B1220]">Raise a Risk / Issue</span>
                {newRisks.length > 0 && (
                  <Badge variant="outline" className="ml-auto text-xs">{newRisks.length} added</Badge>
                )}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-12 gap-2">
                <div className="md:col-span-6">
                  <Input
                    value={riskDraft.description}
                    onChange={(e) => setRiskDraft(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Risk or issue description"
                    data-testid="risk-description-input"
                  />
                </div>
                <div className="md:col-span-2">
                  <Select value={riskDraft.category} onValueChange={(v) => setRiskDraft(prev => ({ ...prev, category: v }))}>
                    <SelectTrigger data-testid="risk-category-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Risk">Risk</SelectItem>
                      <SelectItem value="Issue">Issue</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="md:col-span-2">
                  <Select value={riskDraft.impact} onValueChange={(v) => setRiskDraft(prev => ({ ...prev, impact: v }))}>
                    <SelectTrigger data-testid="risk-impact-select"><SelectValue placeholder="Impact" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Low">Low impact</SelectItem>
                      <SelectItem value="Medium">Medium impact</SelectItem>
                      <SelectItem value="High">High impact</SelectItem>
                      <SelectItem value="Critical">Critical impact</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="md:col-span-2">
                  <Select value={riskDraft.probability} onValueChange={(v) => setRiskDraft(prev => ({ ...prev, probability: v }))}>
                    <SelectTrigger data-testid="risk-probability-select"><SelectValue placeholder="Probability" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Low">Low probability</SelectItem>
                      <SelectItem value="Medium">Medium probability</SelectItem>
                      <SelectItem value="High">High probability</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Input
                value={riskDraft.mitigation}
                onChange={(e) => setRiskDraft(prev => ({ ...prev, mitigation: e.target.value }))}
                placeholder="Mitigation plan (optional)"
                data-testid="risk-mitigation-input"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleAddRisk}
                data-testid="add-risk-btn"
                className="w-full md:w-auto"
              >
                <Plus size={14} className="mr-1" />
                Add to list
              </Button>

              {newRisks.length > 0 && (
                <ul className="space-y-2 pt-2 border-t border-[#E6E8EC]">
                  {newRisks.map((r, idx) => (
                    <li
                      key={idx}
                      className="flex items-start gap-2 p-2 rounded bg-white border border-[#E6E8EC]"
                      data-testid={`pending-risk-${idx}`}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge variant="outline" className="text-[10px]">{r.category}</Badge>
                          <Badge variant="outline" className="text-[10px]">{r.impact}</Badge>
                          <Badge variant="outline" className="text-[10px]">{r.probability}</Badge>
                        </div>
                        <p className="text-sm text-[#0B1220] mt-1 break-words">{r.description}</p>
                        {r.mitigation && (
                          <p className="text-xs text-[#667085] mt-0.5 break-words">Mitigation: {r.mitigation}</p>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemoveRisk(idx)}
                        className="text-[#667085] hover:text-red-600 p-1"
                        data-testid={`remove-pending-risk-${idx}`}
                      >
                        <Trash2 size={14} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsDialogOpen(false)}
              disabled={submitMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={submitMutation.isPending || !isUpdateAllowed}
              data-testid="submit-status-btn"
            >
              {submitMutation.isPending ? (
                <>
                  <Loader2 size={16} className="mr-2 animate-spin" />
                  Submitting...
                </>
              ) : (
                'Submit Status Update'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default ProjectStatusCheckin;
