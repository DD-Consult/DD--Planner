import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createProjectWizard, getResources } from '../api';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Checkbox } from './ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import { Badge } from './ui/badge';
import { ChevronRight, ChevronLeft, Plus, Trash2, CheckCircle, Sparkles, Layers } from 'lucide-react';
import { Avatar, AvatarImage, AvatarFallback } from './ui/avatar';
import { toast } from 'sonner';

const STEPS = [
  { id: 1, name: 'Charter', description: 'Project basics' },
  { id: 2, name: 'Phases', description: 'Define milestones' },
  { id: 3, name: 'Resources', description: 'Allocate team' },
  { id: 4, name: 'Risks', description: 'Risk register' },
  { id: 5, name: 'Review', description: 'Confirm & create' },
];

const PHASE_STATUSES = ['Not Started', 'In Progress', 'Completed', 'On Hold'];

const ProjectWizard = ({ open, onOpenChange }) => {
  const [currentStep, setCurrentStep] = useState(1);
  const queryClient = useQueryClient();

  // Wizard state
  const [wizardData, setWizardData] = useState({
    name: '',
    client_name: '',
    status: 'Active',
    start_date: '',
    end_date: '',
    is_draft: false,
    budgeted_hours: '',
    project_lead_id: '',
    google_drive_url: '',
    phases: [],
    allocations: [],
    risks: [],
  });

  // Temporary state for adding new items
  const [newAllocation, setNewAllocation] = useState({
    resource_id: '',
    start_date: '',
    end_date: '',
    percentage: 50,
  });

  const [newRisk, setNewRisk] = useState({
    description: '',
    impact: 'Medium',
    probability: 'Medium',
  });

  const { data: resources } = useQuery({
    queryKey: ['resources'],
    queryFn: async () => {
      const response = await getResources();
      return response.data;
    },
  });

  const wizardMutation = useMutation({
    mutationFn: createProjectWizard,
    onSuccess: (data) => {
      queryClient.invalidateQueries(['projects']);
      queryClient.invalidateQueries(['allocations']);
      queryClient.invalidateQueries(['capacity']);
      onOpenChange(false);
      resetWizard();
      toast.success(`Project created successfully! ${data.data.allocations_created} allocations and ${data.data.risks_created} risks added.`);
    },
    onError: (error) => {
      toast.error(`Failed to create project: ${error.response?.data?.detail || error.message}`);
    },
  });

  const resetWizard = () => {
    setCurrentStep(1);
    setWizardData({
      name: '',
      client_name: '',
      status: 'Active',
      start_date: '',
      end_date: '',
      is_draft: false,
      budgeted_hours: '',
      project_lead_id: '',
      google_drive_url: '',
      phases: [],
      allocations: [],
      risks: [],
    });
    setNewAllocation({ resource_id: '', start_date: '', end_date: '', percentage: 50 });
    setNewRisk({ description: '', impact: 'Medium', probability: 'Medium' });
  };

  const handleNext = () => {
    if (currentStep < 5) setCurrentStep(currentStep + 1);
  };

  const handleBack = () => {
    if (currentStep > 1) setCurrentStep(currentStep - 1);
  };

  // Phase helpers
  const addPhase = () => {
    const lastPhaseEnd = wizardData.phases.length > 0
      ? wizardData.phases[wizardData.phases.length - 1].end_date
      : wizardData.start_date;

    setWizardData({
      ...wizardData,
      phases: [...wizardData.phases, {
        name: '',
        start_date: lastPhaseEnd || wizardData.start_date || '',
        end_date: '',
        status: 'Not Started',
        budgeted_hours: '',
      }],
    });
  };

  const updatePhase = (index, field, value) => {
    const updated = [...wizardData.phases];
    updated[index] = { ...updated[index], [field]: value };
    setWizardData({ ...wizardData, phases: updated });
  };

  const removePhase = (index) => {
    setWizardData({
      ...wizardData,
      phases: wizardData.phases.filter((_, i) => i !== index),
    });
  };

  // Allocation helpers
  const handleAddAllocation = () => {
    if (!newAllocation.resource_id || !newAllocation.start_date || !newAllocation.end_date) {
      toast.error('Please fill in all allocation fields');
      return;
    }
    setWizardData({
      ...wizardData,
      allocations: [...wizardData.allocations, { ...newAllocation }],
    });
    setNewAllocation({
      resource_id: '',
      start_date: wizardData.start_date || '',
      end_date: wizardData.end_date || '',
      percentage: 50,
    });
  };

  const handleRemoveAllocation = (index) => {
    setWizardData({
      ...wizardData,
      allocations: wizardData.allocations.filter((_, i) => i !== index),
    });
  };

  // Risk helpers
  const handleAddRisk = () => {
    if (!newRisk.description) {
      toast.error('Please enter a risk description');
      return;
    }
    setWizardData({
      ...wizardData,
      risks: [...wizardData.risks, { ...newRisk }],
    });
    setNewRisk({ description: '', impact: 'Medium', probability: 'Medium' });
  };

  const handleRemoveRisk = (index) => {
    setWizardData({
      ...wizardData,
      risks: wizardData.risks.filter((_, i) => i !== index),
    });
  };

  const handleSubmit = () => {
    // Sanitize data before submission
    const sanitizedData = {
      ...wizardData,
      budgeted_hours: wizardData.budgeted_hours === '' ? null : parseFloat(wizardData.budgeted_hours),
      google_drive_url: wizardData.google_drive_url || null,
      phases: wizardData.phases.map(p => ({
        ...p,
        budgeted_hours: p.budgeted_hours === '' ? null : parseFloat(p.budgeted_hours)
      }))
    };
    wizardMutation.mutate(sanitizedData);
  };

  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return wizardData.name && wizardData.client_name && wizardData.start_date && wizardData.end_date && wizardData.project_lead_id;
      case 2:
        // Phases are optional, but if added they need name + dates
        return wizardData.phases.every(p => p.name && p.start_date && p.end_date);
      case 3:
        return true;
      case 4:
        return true;
      case 5:
        return true;
      default:
        return false;
    }
  };

  const getResourceName = (resourceId) => {
    return resources?.find(r => r.id === resourceId)?.name || 'Unknown';
  };

  const getImpactColor = (impact) => {
    const colors = {
      Low: 'bg-[#16B364]',
      Medium: 'bg-[#F4B740]',
      High: 'bg-[#EF4444]',
      Critical: 'bg-[#B42318]',
    };
    return colors[impact] || 'bg-[#667085]';
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="project-wizard">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Sparkles size={24} className="text-[#1570EF]" />
            <DialogTitle className="text-2xl">New Project Wizard</DialogTitle>
          </div>
          <DialogDescription>
            Step-by-step project creation with phases, resource allocation, and risk planning
          </DialogDescription>
        </DialogHeader>

        {/* Progress Steps */}
        <div className="py-4">
          <div className="flex items-center justify-between mb-2">
            {STEPS.map((step, index) => (
              <React.Fragment key={step.id}>
                <div className="flex flex-col items-center">
                  <div
                    className={`w-9 h-9 rounded-full flex items-center justify-center border-2 text-sm ${
                      currentStep === step.id
                        ? 'bg-[#1570EF] border-[#1570EF] text-white'
                        : currentStep > step.id
                        ? 'bg-[#16B364] border-[#16B364] text-white'
                        : 'border-[#E6E8EC] text-[#667085]'
                    }`}
                  >
                    {currentStep > step.id ? <CheckCircle size={18} /> : step.id}
                  </div>
                  <div className="mt-1.5 text-xs text-center">
                    <div className="font-medium">{step.name}</div>
                    <div className="text-[#667085] hidden sm:block">{step.description}</div>
                  </div>
                </div>
                {index < STEPS.length - 1 && (
                  <div
                    className={`flex-1 h-0.5 mx-1.5 ${
                      currentStep > step.id ? 'bg-[#16B364]' : 'bg-[#E6E8EC]'
                    }`}
                  />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Step Content */}
        <div className="min-h-[400px] py-2">
          {/* ===== Step 1: Charter ===== */}
          {currentStep === 1 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Project Charter</h3>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="name">Project Name *</Label>
                  <Input
                    id="name"
                    value={wizardData.name}
                    onChange={(e) => setWizardData({ ...wizardData, name: e.target.value })}
                    placeholder="e.g., Website Redesign"
                    data-testid="wizard-project-name"
                  />
                </div>

                <div>
                  <Label htmlFor="client_name">Client Name *</Label>
                  <Input
                    id="client_name"
                    value={wizardData.client_name}
                    onChange={(e) => setWizardData({ ...wizardData, client_name: e.target.value })}
                    placeholder="e.g., Acme Corp"
                    data-testid="wizard-client-name"
                  />
                </div>

                <div>
                  <Label htmlFor="status">Status</Label>
                  <Select
                    value={wizardData.status}
                    onValueChange={(value) => setWizardData({ ...wizardData, status: value })}
                  >
                    <SelectTrigger id="status" data-testid="wizard-status">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Active">Active</SelectItem>
                      <SelectItem value="Pipeline">Pipeline</SelectItem>
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
                    value={wizardData.budgeted_hours}
                    onChange={(e) => setWizardData({ ...wizardData, budgeted_hours: e.target.value })}
                    placeholder="Optional: Total hours budgeted"
                    data-testid="wizard-budget"
                  />
                </div>

                <div>
                  <Label htmlFor="project_lead">Project Lead *</Label>
                  <Select value={wizardData.project_lead_id} onValueChange={(val) => setWizardData({ ...wizardData, project_lead_id: val })}>
                    <SelectTrigger id="project_lead" data-testid="wizard-lead">
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
                    value={wizardData.google_drive_url}
                    onChange={(e) => setWizardData({ ...wizardData, google_drive_url: e.target.value })}
                    placeholder="Optional: https://drive.google.com/..."
                    data-testid="wizard-drive-url"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="start_date">Start Date *</Label>
                    <Input
                      id="start_date"
                      type="date"
                      value={wizardData.start_date}
                      onChange={(e) => setWizardData({ ...wizardData, start_date: e.target.value })}
                      data-testid="wizard-start-date"
                    />
                  </div>
                  <div>
                    <Label htmlFor="end_date">End Date *</Label>
                    <Input
                      id="end_date"
                      type="date"
                      value={wizardData.end_date}
                      onChange={(e) => setWizardData({ ...wizardData, end_date: e.target.value })}
                      data-testid="wizard-end-date"
                    />
                  </div>
                </div>

                <div className="flex items-center space-x-2 p-3 bg-[#FFF8E5] border border-[#F97316] rounded-lg">
                  <Checkbox
                    id="is_draft"
                    checked={wizardData.is_draft}
                    onCheckedChange={(checked) => setWizardData({ ...wizardData, is_draft: checked })}
                    data-testid="wizard-draft-checkbox"
                  />
                  <Label htmlFor="is_draft" className="text-sm font-medium text-[#0B1220] cursor-pointer">
                    Create as Draft/Scenario
                  </Label>
                  <span className="text-xs text-[#667085] ml-2">(For planning purposes only)</span>
                </div>
              </div>
            </div>
          )}

          {/* ===== Step 2: Phases ===== */}
          {currentStep === 2 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold">Project Phases</h3>
                  <p className="text-sm text-[#667085]">
                    Define milestones and phases to track project progress. Optional but recommended.
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addPhase}
                  data-testid="wizard-add-phase"
                >
                  <Plus size={14} className="mr-1" />
                  Add Phase
                </Button>
              </div>

              {wizardData.phases.length === 0 && (
                <div className="border-2 border-dashed border-[#E6E8EC] rounded-lg p-8 text-center">
                  <Layers size={32} className="mx-auto mb-3 text-[#667085]" />
                  <p className="text-sm text-[#667085]">
                    No phases defined yet. Click "Add Phase" to define project milestones.
                  </p>
                  <p className="text-xs text-[#667085] mt-1">
                    A default "Execution Phase" will be created if you skip this step.
                  </p>
                </div>
              )}

              {wizardData.phases.map((phase, index) => (
                <div
                  key={index}
                  className="border border-[#E6E8EC] rounded-lg p-4 space-y-3 bg-white"
                  data-testid={`wizard-phase-${index}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-[#1570EF]">Phase {index + 1}</span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => removePhase(index)}
                      data-testid={`wizard-remove-phase-${index}`}
                    >
                      <Trash2 size={14} className="text-[#EF4444]" />
                    </Button>
                  </div>

                  <div>
                    <Label>Phase Name *</Label>
                    <Input
                      value={phase.name}
                      onChange={(e) => updatePhase(index, 'name', e.target.value)}
                      placeholder="e.g., Discovery, Development, Testing, Launch"
                      data-testid={`wizard-phase-name-${index}`}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label>Start Date *</Label>
                      <Input
                        type="date"
                        value={phase.start_date ? phase.start_date.split('T')[0] : ''}
                        onChange={(e) => updatePhase(index, 'start_date', e.target.value)}
                        data-testid={`wizard-phase-start-${index}`}
                      />
                    </div>
                    <div>
                      <Label>End Date *</Label>
                      <Input
                        type="date"
                        value={phase.end_date ? phase.end_date.split('T')[0] : ''}
                        onChange={(e) => updatePhase(index, 'end_date', e.target.value)}
                        data-testid={`wizard-phase-end-${index}`}
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label>Status</Label>
                      <Select
                        value={phase.status}
                        onValueChange={(value) => updatePhase(index, 'status', value)}
                      >
                        <SelectTrigger data-testid={`wizard-phase-status-${index}`}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {PHASE_STATUSES.map(s => (
                            <SelectItem key={s} value={s}>{s}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>Budget (Hours)</Label>
                      <Input
                        type="number"
                        min="0"
                        step="0.5"
                        value={phase.budgeted_hours || ''}
                        onChange={(e) => updatePhase(index, 'budgeted_hours', e.target.value)}
                        placeholder="Optional"
                        data-testid={`wizard-phase-budget-${index}`}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* ===== Step 3: Resource Allocation ===== */}
          {currentStep === 3 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Resource Allocation Plan</h3>
              <p className="text-sm text-[#667085]">
                Add team members and their allocation percentages for this project.
              </p>

              <div className="border border-[#E6E8EC] rounded-lg p-4 bg-[#F7F7F8]">
                <div className="space-y-3">
                  <div>
                    <Label>Select Resource</Label>
                    <Select
                      value={newAllocation.resource_id}
                      onValueChange={(value) => setNewAllocation({ ...newAllocation, resource_id: value })}
                    >
                      <SelectTrigger data-testid="wizard-resource-select">
                        <SelectValue placeholder="Choose a team member" />
                      </SelectTrigger>
                      <SelectContent>
                        {resources?.map((resource) => (
                          <SelectItem key={resource.id} value={resource.id}>
                            {resource.name} - {resource.role}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <Label>Start Date</Label>
                      <Input
                        type="date"
                        value={newAllocation.start_date}
                        onChange={(e) => setNewAllocation({ ...newAllocation, start_date: e.target.value })}
                        data-testid="wizard-alloc-start"
                      />
                    </div>
                    <div>
                      <Label>End Date</Label>
                      <Input
                        type="date"
                        value={newAllocation.end_date}
                        onChange={(e) => setNewAllocation({ ...newAllocation, end_date: e.target.value })}
                        data-testid="wizard-alloc-end"
                      />
                    </div>
                    <div>
                      <Label>Allocation %</Label>
                      <Input
                        type="number"
                        min="0"
                        max="100"
                        value={newAllocation.percentage}
                        onChange={(e) => setNewAllocation({ ...newAllocation, percentage: parseInt(e.target.value) })}
                        data-testid="wizard-alloc-percentage"
                      />
                    </div>
                  </div>

                  <Button
                    type="button"
                    onClick={handleAddAllocation}
                    size="sm"
                    variant="outline"
                    data-testid="wizard-add-allocation"
                  >
                    <Plus size={16} className="mr-1" />
                    Add Resource
                  </Button>
                </div>
              </div>

              {wizardData.allocations.length > 0 && (
                <div className="space-y-2">
                  <Label>Planned Allocations ({wizardData.allocations.length})</Label>
                  {wizardData.allocations.map((alloc, index) => {
                    const resource = resources?.find(r => r.id === alloc.resource_id);
                    return (
                      <div
                        key={index}
                        className="flex items-center justify-between p-3 border border-[#E6E8EC] rounded-lg bg-white"
                        data-testid={`wizard-allocation-${index}`}
                      >
                        <div className="flex items-center gap-3">
                          <Avatar className="w-8 h-8">
                            <AvatarImage src={resource?.avatar_url} />
                            <AvatarFallback>{resource?.name?.charAt(0)}</AvatarFallback>
                          </Avatar>
                          <div>
                            <div className="font-medium text-sm">{getResourceName(alloc.resource_id)}</div>
                            <div className="text-xs text-[#667085]">
                              {alloc.start_date} to {alloc.end_date} &middot; {alloc.percentage}%
                            </div>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveAllocation(index)}
                          data-testid={`wizard-remove-allocation-${index}`}
                        >
                          <Trash2 size={14} />
                        </Button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* ===== Step 4: Risk Register ===== */}
          {currentStep === 4 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Risk Register</h3>
              <p className="text-sm text-[#667085]">
                Identify potential risks and their impact on the project.
              </p>

              <div className="border border-[#E6E8EC] rounded-lg p-4 bg-[#F7F7F8]">
                <div className="space-y-3">
                  <div>
                    <Label>Risk Description</Label>
                    <Textarea
                      value={newRisk.description}
                      onChange={(e) => setNewRisk({ ...newRisk, description: e.target.value })}
                      placeholder="e.g., Dependency on third-party API may cause delays"
                      rows={2}
                      data-testid="wizard-risk-description"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label>Impact</Label>
                      <Select
                        value={newRisk.impact}
                        onValueChange={(value) => setNewRisk({ ...newRisk, impact: value })}
                      >
                        <SelectTrigger data-testid="wizard-risk-impact">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Low">Low</SelectItem>
                          <SelectItem value="Medium">Medium</SelectItem>
                          <SelectItem value="High">High</SelectItem>
                          <SelectItem value="Critical">Critical</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>Probability</Label>
                      <Select
                        value={newRisk.probability}
                        onValueChange={(value) => setNewRisk({ ...newRisk, probability: value })}
                      >
                        <SelectTrigger data-testid="wizard-risk-probability">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Low">Low</SelectItem>
                          <SelectItem value="Medium">Medium</SelectItem>
                          <SelectItem value="High">High</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <Button
                    type="button"
                    onClick={handleAddRisk}
                    size="sm"
                    variant="outline"
                    data-testid="wizard-add-risk"
                  >
                    <Plus size={16} className="mr-1" />
                    Add Risk
                  </Button>
                </div>
              </div>

              {wizardData.risks.length > 0 && (
                <div className="space-y-2">
                  <Label>Identified Risks ({wizardData.risks.length})</Label>
                  {wizardData.risks.map((risk, index) => (
                    <div
                      key={index}
                      className="flex items-start justify-between p-3 border border-[#E6E8EC] rounded-lg bg-white"
                      data-testid={`wizard-risk-${index}`}
                    >
                      <div className="flex-1">
                        <div className="text-sm mb-2">{risk.description}</div>
                        <div className="flex gap-2">
                          <Badge className={`${getImpactColor(risk.impact)} text-white text-xs`}>
                            Impact: {risk.impact}
                          </Badge>
                          <Badge variant="outline" className="text-xs">
                            Probability: {risk.probability}
                          </Badge>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRemoveRisk(index)}
                        data-testid={`wizard-remove-risk-${index}`}
                      >
                        <Trash2 size={14} />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ===== Step 5: Review & Submit ===== */}
          {currentStep === 5 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Review & Create Project</h3>
              <p className="text-sm text-[#667085]">
                Please review all details before creating the project.
              </p>

              <div className="space-y-4">
                {/* Charter Summary */}
                <div className="border border-[#E6E8EC] rounded-lg p-4">
                  <h4 className="font-semibold mb-3 flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-[#1570EF] text-white text-xs flex items-center justify-center">1</span>
                    Project Charter
                  </h4>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-[#667085]">Name:</span>
                      <div className="font-medium">{wizardData.name}</div>
                    </div>
                    <div>
                      <span className="text-[#667085]">Client:</span>
                      <div className="font-medium">{wizardData.client_name}</div>
                    </div>
                    <div>
                      <span className="text-[#667085]">Status:</span>
                      <div className="font-medium">
                        {wizardData.status}
                        {wizardData.is_draft && <Badge variant="outline" className="ml-2 text-xs">Draft</Badge>}
                      </div>
                    </div>
                    <div>
                      <span className="text-[#667085]">Duration:</span>
                      <div className="font-medium">
                        {wizardData.start_date} to {wizardData.end_date}
                      </div>
                    </div>
                    <div>
                      <span className="text-[#667085]">Budget:</span>
                      <div className="font-medium">
                        {wizardData.budgeted_hours ? `${wizardData.budgeted_hours} hrs` : 'N/A'}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Phases Summary */}
                <div className="border border-[#E6E8EC] rounded-lg p-4">
                  <h4 className="font-semibold mb-3 flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-[#1570EF] text-white text-xs flex items-center justify-center">2</span>
                    Phases ({wizardData.phases.length})
                  </h4>
                  {wizardData.phases.length === 0 ? (
                    <p className="text-sm text-[#667085]">No phases — a default "Execution Phase" will be created</p>
                  ) : (
                    <div className="space-y-2">
                      {wizardData.phases.map((phase, index) => (
                        <div key={index} className="text-sm flex items-center justify-between">
                          <div className="flex flex-col">
                            <span className="font-medium">{phase.name}</span>
                            {phase.budgeted_hours && (
                              <span className="text-[#667085] text-xs">
                                Budget: {phase.budgeted_hours}h
                              </span>
                            )}
                          </div>
                          <span className="text-[#667085] text-xs">
                            {phase.start_date} to {phase.end_date}
                            <Badge variant="outline" className="ml-2 text-xs">{phase.status}</Badge>
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Allocations Summary */}
                <div className="border border-[#E6E8EC] rounded-lg p-4">
                  <h4 className="font-semibold mb-3 flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-[#1570EF] text-white text-xs flex items-center justify-center">3</span>
                    Resource Allocations ({wizardData.allocations.length})
                  </h4>
                  {wizardData.allocations.length === 0 ? (
                    <p className="text-sm text-[#667085]">No resources allocated yet</p>
                  ) : (
                    <div className="space-y-2">
                      {wizardData.allocations.map((alloc, index) => (
                        <div key={index} className="text-sm flex items-center justify-between">
                          <span>{getResourceName(alloc.resource_id)}</span>
                          <span className="text-[#667085]">{alloc.percentage}%</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Risks Summary */}
                <div className="border border-[#E6E8EC] rounded-lg p-4">
                  <h4 className="font-semibold mb-3 flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-[#1570EF] text-white text-xs flex items-center justify-center">4</span>
                    Risks ({wizardData.risks.length})
                  </h4>
                  {wizardData.risks.length === 0 ? (
                    <p className="text-sm text-[#667085]">No risks identified</p>
                  ) : (
                    <div className="space-y-2">
                      {wizardData.risks.map((risk, index) => (
                        <div key={index} className="text-sm">
                          <div className="mb-1">{risk.description}</div>
                          <div className="flex gap-2">
                            <Badge className={`${getImpactColor(risk.impact)} text-white text-xs`}>
                              {risk.impact}
                            </Badge>
                            <Badge variant="outline" className="text-xs">
                              {risk.probability}
                            </Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Navigation Buttons */}
        <div className="flex justify-between border-t border-[#E6E8EC] pt-4">
          <Button
            variant="outline"
            onClick={handleBack}
            disabled={currentStep === 1}
            data-testid="wizard-back"
          >
            <ChevronLeft size={16} className="mr-1" />
            Back
          </Button>

          <div className="flex gap-2">
            <Button
              variant="ghost"
              onClick={() => onOpenChange(false)}
              data-testid="wizard-cancel"
            >
              Cancel
            </Button>
            {currentStep < 5 ? (
              <Button
                onClick={handleNext}
                disabled={!canProceed()}
                data-testid="wizard-next"
              >
                Next
                <ChevronRight size={16} className="ml-1" />
              </Button>
            ) : (
              <Button
                onClick={handleSubmit}
                disabled={wizardMutation.isPending}
                data-testid="wizard-submit"
              >
                {wizardMutation.isPending ? 'Creating...' : 'Create Project'}
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ProjectWizard;
