import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getResources, getAllocationRoles, getProjectPhases, getProjects, createAllocation, validateAllocation } from '../api';
import { Button } from './ui/button';
import { Input } from './ui/input';
import WeekdayDateInput from './ui/weekday-date-input';
import { Label } from './ui/label';
import { Checkbox } from './ui/checkbox';
import { Alert, AlertDescription } from './ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import { Badge } from './ui/badge';
import { Plus, Trash2, Clock, Percent, AlertCircle, Layers } from 'lucide-react';
import { Avatar, AvatarImage, AvatarFallback } from './ui/avatar';
import { differenceInDays, differenceInBusinessDays, parseISO, format } from 'date-fns';
import { toast } from 'sonner';
import BudgetConfirmDialog from './BudgetConfirmDialog';

const AllocationEditor = ({ 
  allocations = [], 
  onAllocationsChange, 
  projectId: initialProjectId,
  projectStartDate: initialStartDate,
  projectEndDate: initialEndDate,
  showTitle = true,
  standaloneMode = false // When true, allows project selection and direct API submission
}) => {
  const queryClient = useQueryClient();
  const [selectedProjectId, setSelectedProjectId] = useState(initialProjectId || '');
  const [projectStartDate, setProjectStartDate] = useState(initialStartDate || '');
  const [projectEndDate, setProjectEndDate] = useState(initialEndDate || '');
  
  const [newAllocation, setNewAllocation] = useState({
    resource_id: '',
    start_date: initialStartDate || '',
    end_date: initialEndDate || '',
    percentage: 50,
    hours: 40,
    allocation_type: 'percentage',
    role: '',
    customRole: '',
    selectedPhases: [],
  });
  
  const [dateError, setDateError] = useState('');
  const [showBudgetDialog, setShowBudgetDialog] = useState(false);
  const [pendingValidation, setPendingValidation] = useState(null);

  // Fetch all projects for standalone mode
  const { data: projectsData } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await getProjects();
      return response.data;
    },
    enabled: standaloneMode,
  });

  // Fetch project phases if projectId is provided
  const { data: phasesData } = useQuery({
    queryKey: ['projectPhases', selectedProjectId],
    queryFn: async () => {
      const response = await getProjectPhases(selectedProjectId);
      return response.data;
    },
    enabled: !!selectedProjectId,
  });

  const projectPhases = phasesData?.phases || [];

  // Mutation for standalone mode
  const createMutation = useMutation({
    mutationFn: (allocationData) => createAllocation(allocationData),
    onSuccess: () => {
      toast.success('Allocation created successfully!');
      queryClient.invalidateQueries(['allocations']);
      queryClient.invalidateQueries(['capacity']);
      // Reset form
      setNewAllocation({
        resource_id: '',
        start_date: projectStartDate || '',
        end_date: projectEndDate || '',
        percentage: 50,
        hours: 40,
        allocation_type: 'percentage',
        role: '',
        customRole: '',
        selectedPhases: [],
      });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to create allocation');
    },
  });

  // Handle project selection in standalone mode
  const handleProjectSelect = (projectId) => {
    setSelectedProjectId(projectId);
    const project = projectsData?.find(p => p.id === projectId);
    if (project) {
      const startDate = project.start_date?.split('T')[0] || '';
      const endDate = project.end_date?.split('T')[0] || '';
      setProjectStartDate(startDate);
      setProjectEndDate(endDate);
      setNewAllocation(prev => ({
        ...prev,
        start_date: startDate,
        end_date: endDate,
        selectedPhases: [],
      }));
    }
  };

  // Update dates when project dates change
  useEffect(() => {
    if (initialStartDate && !newAllocation.start_date) {
      setNewAllocation(prev => ({ ...prev, start_date: initialStartDate }));
      setProjectStartDate(initialStartDate);
    }
    if (initialEndDate && !newAllocation.end_date) {
      setNewAllocation(prev => ({ ...prev, end_date: initialEndDate }));
      setProjectEndDate(initialEndDate);
    }
  }, [initialStartDate, initialEndDate]);

  const { data: resources } = useQuery({
    queryKey: ['resources'],
    queryFn: async () => {
      const response = await getResources();
      return response.data;
    },
  });

  const { data: rolesData } = useQuery({
    queryKey: ['allocationRoles'],
    queryFn: async () => {
      const response = await getAllocationRoles();
      return response.data;
    },
  });

  const predefinedRoles = rolesData?.roles || [
    'Project Lead',
    'Developer',
    'Designer',
    'QA Engineer',
    'Consultant',
    'Analyst',
    'Support',
  ];

  // Calculate hours from percentage or vice versa (uses business days Mon-Fri)
  const calculateHours = (percentage, startDate, endDate) => {
    if (!startDate || !endDate) return 0;
    const days = Math.abs(differenceInBusinessDays(new Date(endDate), new Date(startDate))) + 1;
    return Math.round((percentage / 100) * days * 8);
  };

  const calculatePercentage = (hours, startDate, endDate) => {
    if (!startDate || !endDate) return 0;
    const days = Math.abs(differenceInBusinessDays(new Date(endDate), new Date(startDate))) + 1;
    const totalHours = days * 8;
    return Math.min(100, Math.round((hours / totalHours) * 100));
  };

  // Handle phase selection - auto-fill dates
  const handlePhaseToggle = (phaseName, phase) => {
    const currentSelected = [...newAllocation.selectedPhases];
    const phaseIndex = currentSelected.indexOf(phaseName);
    
    if (phaseIndex > -1) {
      // Remove phase
      currentSelected.splice(phaseIndex, 1);
    } else {
      // Add phase
      currentSelected.push(phaseName);
    }
    
    // Calculate date range from selected phases
    if (currentSelected.length > 0) {
      const selectedPhaseData = projectPhases.filter(p => currentSelected.includes(p.name));
      
      // Get earliest start and latest end
      let earliestStart = null;
      let latestEnd = null;
      
      selectedPhaseData.forEach(p => {
        if (p.start_date) {
          const startDate = new Date(p.start_date);
          if (!earliestStart || startDate < earliestStart) {
            earliestStart = startDate;
          }
        }
        if (p.end_date) {
          const endDate = new Date(p.end_date);
          if (!latestEnd || endDate > latestEnd) {
            latestEnd = endDate;
          }
        }
      });
      
      const newStartDate = earliestStart ? format(earliestStart, 'yyyy-MM-dd') : newAllocation.start_date;
      const newEndDate = latestEnd ? format(latestEnd, 'yyyy-MM-dd') : newAllocation.end_date;
      
      setNewAllocation(prev => ({
        ...prev,
        selectedPhases: currentSelected,
        start_date: newStartDate,
        end_date: newEndDate,
        hours: calculateHours(prev.percentage, newStartDate, newEndDate),
      }));
    } else {
      // No phases selected, reset to project dates
      setNewAllocation(prev => ({
        ...prev,
        selectedPhases: currentSelected,
        start_date: projectStartDate || '',
        end_date: projectEndDate || '',
        hours: calculateHours(prev.percentage, projectStartDate, projectEndDate),
      }));
    }
  };

  // Validate dates against project range
  const validateDates = (startDate, endDate) => {
    if (!startDate || !endDate || !projectStartDate || !projectEndDate) {
      setDateError('');
      return true;
    }
    
    const allocStart = new Date(startDate);
    const allocEnd = new Date(endDate);
    const projStart = new Date(projectStartDate);
    const projEnd = new Date(projectEndDate);
    
    if (allocStart < projStart) {
      setDateError(`Start date cannot be before project start (${projectStartDate})`);
      return false;
    }
    if (allocEnd > projEnd) {
      setDateError(`End date cannot be after project end (${projectEndDate})`);
      return false;
    }
    
    setDateError('');
    return true;
  };

  const handleAllocationTypeChange = (type) => {
    if (type === 'hours') {
      const hours = calculateHours(newAllocation.percentage, newAllocation.start_date, newAllocation.end_date);
      setNewAllocation({ ...newAllocation, allocation_type: type, hours });
    } else {
      const percentage = calculatePercentage(newAllocation.hours, newAllocation.start_date, newAllocation.end_date);
      setNewAllocation({ ...newAllocation, allocation_type: type, percentage });
    }
  };

  const handlePercentageChange = (value) => {
    const percentage = parseInt(value) || 0;
    const hours = calculateHours(percentage, newAllocation.start_date, newAllocation.end_date);
    setNewAllocation({ ...newAllocation, percentage, hours });
  };

  const handleHoursChange = (value) => {
    const hours = parseInt(value) || 0;
    const percentage = calculatePercentage(hours, newAllocation.start_date, newAllocation.end_date);
    setNewAllocation({ ...newAllocation, hours, percentage });
  };

  const handleDateChange = (field, value) => {
    const updated = { ...newAllocation, [field]: value };
    // Recalculate based on current type
    if (updated.allocation_type === 'percentage') {
      updated.hours = calculateHours(updated.percentage, updated.start_date, updated.end_date);
    } else {
      updated.percentage = calculatePercentage(updated.hours, updated.start_date, updated.end_date);
    }
    setNewAllocation(updated);
    validateDates(updated.start_date, updated.end_date);
  };

  const performAllocationSave = (allocationToAdd) => {
    if (standaloneMode) {
      // In standalone mode, submit directly to API
      createMutation.mutate(allocationToAdd);
    } else {
      // In embedded mode, use the callback
      onAllocationsChange([...allocations, allocationToAdd]);
      
      // Reset form but keep dates
      setNewAllocation({
        resource_id: '',
        start_date: newAllocation.start_date,
        end_date: newAllocation.end_date,
        percentage: 50,
        hours: calculateHours(50, newAllocation.start_date, newAllocation.end_date),
        allocation_type: 'percentage',
        role: '',
        customRole: '',
        selectedPhases: [],
      });
    }
  };

  const handleAddAllocation = async () => {
    // In standalone mode, require project selection
    if (standaloneMode && !selectedProjectId) {
      toast.error('Please select a project first');
      return;
    }
    
    if (!newAllocation.resource_id || !newAllocation.start_date || !newAllocation.end_date) {
      toast.error('Please fill in resource, start date, and end date');
      return;
    }
    
    if (!validateDates(newAllocation.start_date, newAllocation.end_date)) {
      return;
    }
    
    const role = newAllocation.role === 'Custom' ? newAllocation.customRole : newAllocation.role;
    
    const allocationToAdd = {
      resource_id: newAllocation.resource_id,
      project_id: standaloneMode ? selectedProjectId : initialProjectId,
      start_date: newAllocation.start_date,
      end_date: newAllocation.end_date,
      percentage: newAllocation.percentage,
      hours: newAllocation.hours,
      allocation_type: newAllocation.allocation_type,
      role: role || null,
      phase_names: newAllocation.selectedPhases.length > 0 ? newAllocation.selectedPhases : null,
    };

    // Pre-validate against project budget
    try {
      const validationPayload = {
        project_id: allocationToAdd.project_id,
        resource_id: allocationToAdd.resource_id,
        start_date: allocationToAdd.start_date,
        end_date: allocationToAdd.end_date,
        percentage: allocationToAdd.percentage,
        hours: allocationToAdd.hours,
        allocation_type: allocationToAdd.allocation_type,
        exclude_allocation_id: null,
      };
      const res = await validateAllocation(validationPayload);
      const v = res?.data;
      if (v && (v.status === 'warning' || v.status === 'exceeded')) {
        setPendingValidation({ validation: v, allocation: allocationToAdd });
        setShowBudgetDialog(true);
        return; // Wait for user confirmation
      }
      // ok or no_budget → proceed silently
    } catch (e) {
      // Validation API failed — don't block, just proceed
      console.warn('Budget validation skipped due to error:', e?.message);
    }

    performAllocationSave(allocationToAdd);
  };

  const handleBudgetConfirm = () => {
    setShowBudgetDialog(false);
    if (pendingValidation?.allocation) {
      performAllocationSave(pendingValidation.allocation);
    }
    setPendingValidation(null);
  };

  const handleBudgetCancel = () => {
    setShowBudgetDialog(false);
    setPendingValidation(null);
  };

  const handleRemoveAllocation = (index) => {
    onAllocationsChange(allocations.filter((_, i) => i !== index));
  };

  const getResourceName = (resourceId) => {
    return resources?.find(r => r.id === resourceId)?.name || 'Unknown';
  };

  const getResourceById = (resourceId) => {
    return resources?.find(r => r.id === resourceId);
  };

  return (
    <div className="space-y-4">
      {showTitle && (
        <>
          <h3 className="text-lg font-semibold">Resource Allocation</h3>
          <p className="text-sm text-[#667085]">
            Add team members and specify their allocation for this project.
          </p>
        </>
      )}

      {/* Add Allocation Form */}
      <div className="border border-[#E6E8EC] rounded-lg p-4 bg-[#F7F7F8]">
        <div className="space-y-3">
          {/* Project Selection (only in standalone mode) */}
          {standaloneMode && (
            <div>
              <Label>Select Project *</Label>
              <Select
                value={selectedProjectId}
                onValueChange={handleProjectSelect}
              >
                <SelectTrigger data-testid="alloc-project-select">
                  <SelectValue placeholder="Choose a project" />
                </SelectTrigger>
                <SelectContent>
                  {projectsData?.filter(p => p.status !== 'Completed').map((project) => (
                    <SelectItem key={project.id} value={project.id}>
                      {project.name} ({project.client_name})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Resource Selection */}
          <div>
            <Label>Select Resource *</Label>
            <Select
              value={newAllocation.resource_id}
              onValueChange={(value) => setNewAllocation({ ...newAllocation, resource_id: value })}
            >
              <SelectTrigger data-testid="alloc-resource-select">
                <SelectValue placeholder="Choose a team member" />
              </SelectTrigger>
              <SelectContent>
                {resources?.filter((resource) => resource.active !== false).map((resource) => (
                  <SelectItem key={resource.id} value={resource.id}>
                    {resource.name} - {resource.role}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Phase Selection (only show if project has phases) */}
          {projectPhases.length > 0 && (
            <div>
              <Label className="flex items-center gap-2">
                <Layers size={14} />
                Assign to Phase(s)
              </Label>
              <div className="mt-2 space-y-2 max-h-32 overflow-y-auto border border-[#E6E8EC] rounded-md p-2 bg-white">
                {projectPhases.map((phase) => (
                  <div key={phase.id} className="flex items-center space-x-2">
                    <Checkbox
                      id={`phase-${phase.id}`}
                      checked={newAllocation.selectedPhases.includes(phase.name)}
                      onCheckedChange={() => handlePhaseToggle(phase.name, phase)}
                      data-testid={`phase-checkbox-${phase.id}`}
                    />
                    <label
                      htmlFor={`phase-${phase.id}`}
                      className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 flex-1"
                    >
                      {phase.name}
                      {phase.start_date && phase.end_date && (
                        <span className="text-xs text-[#667085] ml-2">
                          ({format(parseISO(phase.start_date), 'MMM d')} - {format(parseISO(phase.end_date), 'MMM d')})
                        </span>
                      )}
                    </label>
                  </div>
                ))}
              </div>
              {newAllocation.selectedPhases.length > 0 && (
                <p className="text-xs text-[#1570EF] mt-1">
                  Dates auto-filled from selected phases: {newAllocation.selectedPhases.join(', ')}
                </p>
              )}
            </div>
          )}

          {/* Role Selection */}
          <div>
            <Label>Project Role</Label>
            <Select
              value={newAllocation.role}
              onValueChange={(value) => setNewAllocation({ ...newAllocation, role: value })}
            >
              <SelectTrigger data-testid="alloc-role-select">
                <SelectValue placeholder="Select role for this project" />
              </SelectTrigger>
              <SelectContent>
                {predefinedRoles.map((role) => (
                  <SelectItem key={role} value={role}>
                    {role}
                  </SelectItem>
                ))}
                <SelectItem value="Custom">Custom...</SelectItem>
              </SelectContent>
            </Select>
            {newAllocation.role === 'Custom' && (
              <Input
                className="mt-2"
                placeholder="Enter custom role"
                value={newAllocation.customRole}
                onChange={(e) => setNewAllocation({ ...newAllocation, customRole: e.target.value })}
                data-testid="alloc-custom-role"
              />
            )}
          </div>

          {/* Date Range */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Start Date *</Label>
              <WeekdayDateInput
                value={newAllocation.start_date}
                min={projectStartDate}
                max={projectEndDate}
                onChange={(e) => handleDateChange('start_date', e.target.value)}
                data-testid="alloc-start-date"
              />
            </div>
            <div>
              <Label>End Date *</Label>
              <WeekdayDateInput
                value={newAllocation.end_date}
                min={projectStartDate}
                max={projectEndDate}
                onChange={(e) => handleDateChange('end_date', e.target.value)}
                data-testid="alloc-end-date"
              />
            </div>
          </div>
          
          {/* Date validation error */}
          {dateError && (
            <Alert variant="destructive" className="py-2">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{dateError}</AlertDescription>
            </Alert>
          )}

          {/* Allocation Type Toggle */}
          <div>
            <Label>Allocation Type</Label>
            <div className="flex gap-2 mt-1">
              <Button
                type="button"
                variant={newAllocation.allocation_type === 'percentage' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleAllocationTypeChange('percentage')}
                data-testid="alloc-type-percentage"
              >
                <Percent size={14} className="mr-1" />
                Percentage
              </Button>
              <Button
                type="button"
                variant={newAllocation.allocation_type === 'hours' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleAllocationTypeChange('hours')}
                data-testid="alloc-type-hours"
              >
                <Clock size={14} className="mr-1" />
                Hours
              </Button>
            </div>
          </div>

          {/* Allocation Value */}
          <div className="grid grid-cols-2 gap-3">
            {newAllocation.allocation_type === 'percentage' ? (
              <>
                <div>
                  <Label>Allocation %</Label>
                  <Input
                    type="number"
                    min="0"
                    max="100"
                    value={newAllocation.percentage}
                    onChange={(e) => handlePercentageChange(e.target.value)}
                    data-testid="alloc-percentage"
                  />
                </div>
                <div>
                  <Label className="text-[#667085]">Equivalent Hours</Label>
                  <div className="h-10 px-3 py-2 border border-[#E6E8EC] rounded-md bg-[#F8FAFC] text-[#667085] flex items-center">
                    ≈ {newAllocation.hours} hours
                  </div>
                </div>
              </>
            ) : (
              <>
                <div>
                  <Label>Total Hours</Label>
                  <Input
                    type="number"
                    min="0"
                    value={newAllocation.hours}
                    onChange={(e) => handleHoursChange(e.target.value)}
                    data-testid="alloc-hours"
                  />
                </div>
                <div>
                  <Label className="text-[#667085]">Equivalent %</Label>
                  <div className="h-10 px-3 py-2 border border-[#E6E8EC] rounded-md bg-[#F8FAFC] text-[#667085] flex items-center">
                    ≈ {newAllocation.percentage}%
                  </div>
                </div>
              </>
            )}
          </div>

          <Button
            type="button"
            onClick={handleAddAllocation}
            size="sm"
            variant="outline"
            disabled={!!dateError}
            data-testid="add-allocation-btn"
          >
            <Plus size={16} className="mr-1" />
            Add Resource
          </Button>
        </div>
      </div>

      {/* Allocations List */}
      {allocations.length > 0 && (
        <div className="space-y-2">
          <Label>Planned Allocations ({allocations.length})</Label>
          {allocations.map((alloc, index) => {
            const resource = getResourceById(alloc.resource_id);
            return (
              <div
                key={index}
                className="flex items-center justify-between p-3 border border-[#E6E8EC] rounded-lg bg-white"
                data-testid={`allocation-item-${index}`}
              >
                <div className="flex items-center gap-3">
                  <Avatar className="w-8 h-8">
                    <AvatarImage src={resource?.avatar_url} />
                    <AvatarFallback>{resource?.name?.charAt(0) || '?'}</AvatarFallback>
                  </Avatar>
                  <div>
                    <div className="font-medium text-sm flex items-center gap-2">
                      {getResourceName(alloc.resource_id)}
                      {alloc.role && (
                        <Badge variant="outline" className="text-xs">
                          {alloc.role}
                        </Badge>
                      )}
                    </div>
                    <div className="text-xs text-[#667085]">
                      {alloc.start_date} to {alloc.end_date} • 
                      {alloc.allocation_type === 'hours' 
                        ? ` ${alloc.hours}h (${alloc.percentage}%)`
                        : ` ${alloc.percentage}% (${alloc.hours}h)`
                      }
                      {alloc.phase_names && alloc.phase_names.length > 0 && (
                        <span className="ml-1 text-[#1570EF]">
                          • {alloc.phase_names.join(', ')}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleRemoveAllocation(index)}
                  data-testid={`remove-allocation-${index}`}
                >
                  <Trash2 size={14} className="text-[#EF4444]" />
                </Button>
              </div>
            );
          })}
        </div>
      )}

      <BudgetConfirmDialog
        open={showBudgetDialog}
        onOpenChange={(open) => { if (!open) handleBudgetCancel(); }}
        validation={pendingValidation?.validation}
        onConfirm={handleBudgetConfirm}
        onCancel={handleBudgetCancel}
      />
    </div>
  );
};

export default AllocationEditor;
