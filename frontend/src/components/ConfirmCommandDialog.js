import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  createAllocation, 
  createProject, 
  createProjectFull,
  rescheduleProject,
  moveResourceBetweenProjects,
  createBulkRisks,
  bulkGenerateSummaries,
  deleteAllocation,
  getAllocations,
  createStatusUpdate,
  getTimesheetInsights,
  getPlanAllocation,
  moveProjectPhase,
  getProjectBudgetAnalysis
} from '../api';
import { Button } from './ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './ui/dialog';
import { Alert, AlertDescription } from './ui/alert';
import { CheckCircle2, Loader2, AlertCircle, Sparkles, AlertTriangle, Calendar, Users, FileText, ArrowRightLeft, Trash2, RefreshCw, ClipboardCheck, BarChart3, UserPlus, ArrowLeftRight } from 'lucide-react';
import { toast } from 'sonner';

export const ConfirmCommandDialog = ({ isOpen, onClose, parsedCommand }) => {
  const queryClient = useQueryClient();
  const [error, setError] = useState('');
  const [insightResult, setInsightResult] = useState(null);

  const executeMutation = useMutation({
    mutationFn: async () => {
      const { action, data } = parsedCommand;

      // CREATE ALLOCATION
      if (action === 'create_allocation') {
        if (!data.resource_id) {
          throw new Error(`Could not find resource "${data.resource_name}". Please check the name and try again.`);
        }
        if (!data.project_id) {
          throw new Error(`Could not find project "${data.project_name}". Please check the name and try again.`);
        }
        
        const allocationData = {
          resource_id: data.resource_id,
          project_id: data.project_id,
          percentage: data.percentage,
          start_date: data.start_date,
          end_date: data.end_date,
        };
        return createAllocation(allocationData);
      }
      
      // CREATE PROJECT (simple)
      if (action === 'create_project') {
        return createProject(data);
      }

      // CREATE PROJECT FULL (with phases and allocations)
      if (action === 'create_project_full') {
        // Filter out allocations without valid resource IDs
        const validAllocations = (data.allocations || []).filter(a => a.resource_id);
        if (data.allocations?.length > 0 && validAllocations.length === 0) {
          throw new Error('Could not find any of the specified resources. Please check the names and try again.');
        }
        
        return createProjectFull({
          name: data.name,
          client_name: data.client_name,
          status: data.status || 'Pipeline',
          phases: data.phases || [],
          allocations: validAllocations.map(a => ({
            resource_id: a.resource_id,
            percentage: a.percentage || 50,
          })),
        });
      }

      // RESCHEDULE PROJECT
      if (action === 'reschedule_project') {
        if (!data.project_id) {
          throw new Error(`Could not find project "${data.project_name}". Please check the name and try again.`);
        }
        return rescheduleProject(data.project_id, data.weeks_to_shift, data.shift_direction);
      }

      // MOVE RESOURCE
      if (action === 'move_resource') {
        if (!data.resource_id) {
          throw new Error(`Could not find resource "${data.resource_name}".`);
        }
        if (!data.source_project_id) {
          throw new Error(`Could not find source project "${data.source_project_name}".`);
        }
        if (!data.target_project_id) {
          throw new Error(`Could not find target project "${data.target_project_name}".`);
        }
        return moveResourceBetweenProjects(
          data.resource_id, 
          data.source_project_id, 
          data.target_project_id,
          data.new_percentage
        );
      }

      // REMOVE ALLOCATION
      if (action === 'remove_allocation') {
        if (!data.resource_id || !data.project_id) {
          throw new Error('Could not find the resource or project to remove.');
        }
        
        // Find the allocation to remove
        const allocResponse = await getAllocations();
        const alloc = allocResponse.data.find(a => 
          a.resource_id === data.resource_id && a.project_id === data.project_id
        );
        
        if (!alloc) {
          throw new Error(`Resource "${data.resource_name}" is not allocated to project "${data.project_name}".`);
        }
        
        return deleteAllocation(alloc.id);
      }

      // CREATE RISKS (bulk)
      if (action === 'create_risks') {
        if (!data.project_id) {
          throw new Error(`Could not find project "${data.project_name}".`);
        }
        if (!data.risks || data.risks.length === 0) {
          throw new Error('No risks specified to add.');
        }
        return createBulkRisks(data.project_id, data.risks);
      }

      // UPDATE SUMMARIES
      if (action === 'update_summaries') {
        const validProjectIds = (data.projects || [])
          .filter(p => p.id)
          .map(p => p.id);
        
        if (validProjectIds.length === 0) {
          throw new Error('Could not find any of the specified projects.');
        }
        return bulkGenerateSummaries(validProjectIds);
      }

      // PROJECT STATUS UPDATE (Weekly check-in via AI)
      if (action === 'project_status_update') {
        if (!data.project_id) {
          throw new Error(`Could not find project "${data.project_name}".`);
        }
        return createStatusUpdate({
          project_id: data.project_id,
          health: data.health,
          schedule_status: data.schedule_status,
          actual_progress: data.actual_progress,
          accomplishments: data.accomplishments,
          blockers: data.blockers,
          next_steps: data.next_steps,
        });
      }

      // TIMESHEET INSIGHTS
      if (action === 'timesheet_insights') {
        const params = {};
        if (data.project_name) params.project_name = data.project_name;
        if (data.resource_name) params.resource_name = data.resource_name;
        if (data.time_period) params.time_period = data.time_period;
        const response = await getTimesheetInsights(params);
        return response.data;
      }

      // PLAN FUTURE ALLOCATION
      if (action === 'plan_allocation') {
        const params = {};
        if (data.start_date) params.start_date = data.start_date;
        if (data.end_date) params.end_date = data.end_date;
        if (data.required_count) params.required_count = data.required_count;
        const response = await getPlanAllocation(params);
        return response.data;
      }

      // MOVE PROJECT PHASE
      if (action === 'move_project_phase') {
        if (!data.project_id) {
          throw new Error(`Could not find project "${data.project_name}".`);
        }
        return moveProjectPhase(
          data.project_id,
          data.phase_name,
          data.days_to_shift || 0,
          data.weeks_to_shift || 0,
          data.shift_direction || 'forward'
        );
      }

      // BUDGET ANALYSIS
      if (action === 'budget_analysis') {
        if (!data.project_id) {
          throw new Error(`Could not find project "${data.project_name}". Please specify an exact project name.`);
        }
        const response = await getProjectBudgetAnalysis(data.project_id);
        return response.data;
      }
      
      throw new Error('This action type is not yet supported for automatic execution.');
    },
    onSuccess: (result) => {
      const action = parsedCommand?.action;
      // For insight/analysis actions, show results inline
      if (action === 'timesheet_insights' || action === 'plan_allocation' || action === 'budget_analysis') {
        setInsightResult(result);
        toast.success('Analysis complete!');
        return;
      }
      toast.success('Command executed successfully!');
      // Invalidate all relevant queries
      queryClient.invalidateQueries({ queryKey: ['allocations'] });
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      queryClient.invalidateQueries({ queryKey: ['capacity'] });
      queryClient.invalidateQueries({ queryKey: ['risks'] });
      onClose();
    },
    onError: (error) => {
      const message = error.message || error.response?.data?.detail || 'Failed to execute command';
      setError(message);
      toast.error(message);
    },
  });

  if (!parsedCommand) return null;

  const handleConfirm = () => {
    setError('');
    executeMutation.mutate();
  };

  const handleCancel = () => {
    setError('');
    setInsightResult(null);
    onClose();
  };

  // Check for validation issues based on action type
  const getValidationIssues = () => {
    const { action, data } = parsedCommand;
    const issues = [];

    if (action === 'create_allocation') {
      if (!data?.resource_id) issues.push(`Resource "${data?.resource_name}" not found`);
      if (!data?.project_id) issues.push(`Project "${data?.project_name}" not found`);
    }
    else if (action === 'reschedule_project' && !data?.project_id) {
      issues.push(`Project "${data?.project_name}" not found`);
    }
    else if (action === 'move_resource') {
      if (!data?.resource_id) issues.push(`Resource "${data?.resource_name}" not found`);
      if (!data?.source_project_id) issues.push(`Source project "${data?.source_project_name}" not found`);
      if (!data?.target_project_id) issues.push(`Target project "${data?.target_project_name}" not found`);
    }
    else if (action === 'remove_allocation') {
      if (!data?.resource_id) issues.push(`Resource "${data?.resource_name}" not found`);
      if (!data?.project_id) issues.push(`Project "${data?.project_name}" not found`);
    }
    else if (action === 'create_risks' && !data?.project_id) {
      issues.push(`Project "${data?.project_name}" not found`);
    }
    else if (action === 'update_summaries') {
      const missingProjects = (data?.projects || []).filter(p => !p.id);
      if (missingProjects.length > 0) {
        issues.push(`Projects not found: ${missingProjects.map(p => p.name).join(', ')}`);
      }
    }
    else if (action === 'create_project_full') {
      const missingResources = (data?.allocations || []).filter(a => !a.resource_id);
      if (missingResources.length > 0) {
        issues.push(`Resources not found: ${missingResources.map(a => a.resource_name).join(', ')}`);
      }
    }
    else if (action === 'project_status_update' && !data?.project_id) {
      issues.push(`Project "${data?.project_name}" not found`);
    }
    else if (action === 'move_project_phase' && !data?.project_id) {
      issues.push(`Project "${data?.project_name}" not found`);
    }

    return issues;
  };

  const validationIssues = getValidationIssues();
  const hasValidationIssues = validationIssues.length > 0;

  // Get action icon and label
  const getActionInfo = () => {
    const { action } = parsedCommand;
    switch (action) {
      case 'create_allocation':
        return { icon: Users, label: 'Assign Resource', color: 'text-blue-600' };
      case 'create_project':
      case 'create_project_full':
        return { icon: FileText, label: 'Create Project', color: 'text-green-600' };
      case 'reschedule_project':
        return { icon: Calendar, label: 'Reschedule Project', color: 'text-orange-600' };
      case 'move_resource':
        return { icon: ArrowRightLeft, label: 'Move Resource', color: 'text-purple-600' };
      case 'remove_allocation':
        return { icon: Trash2, label: 'Remove Allocation', color: 'text-red-600' };
      case 'create_risks':
        return { icon: AlertTriangle, label: 'Add Risks', color: 'text-amber-600' };
      case 'update_summaries':
        return { icon: RefreshCw, label: 'Update Summaries', color: 'text-cyan-600' };
      case 'project_status_update':
        return { icon: ClipboardCheck, label: 'Status Update', color: 'text-teal-600' };
      case 'timesheet_insights':
        return { icon: BarChart3, label: 'Timesheet Insights', color: 'text-indigo-600' };
      case 'plan_allocation':
        return { icon: UserPlus, label: 'Plan Allocation', color: 'text-emerald-600' };
      case 'move_project_phase':
        return { icon: ArrowLeftRight, label: 'Move Phase', color: 'text-violet-600' };
      case 'budget_analysis':
        return { icon: BarChart3, label: 'Budget Analysis', color: 'text-blue-600' };
      default:
        return { icon: Sparkles, label: 'AI Action', color: 'text-gray-600' };
    }
  };

  const actionInfo = getActionInfo();
  const ActionIcon = actionInfo.icon;

  return (
    <Dialog open={isOpen} onOpenChange={handleCancel}>
      <DialogContent data-testid="confirm-command-dialog" className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles size={20} className="text-[#1570EF]" />
            Confirm AI Command
          </DialogTitle>
          <DialogDescription>
            Please review the parsed action before executing
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Original Query */}
          <div className="bg-[#F7F7F8] border border-[#E6E8EC] rounded-lg p-3">
            <div className="text-xs text-[#667085] mb-1">AI Response:</div>
            <div className="text-sm text-[#0B1220]">{parsedCommand.original_query || 'No description available'}</div>
          </div>

          {/* Parsed Action */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium">
              {hasValidationIssues ? (
                <AlertTriangle size={16} className="text-[#F59E0B]" />
              ) : (
                <CheckCircle2 size={16} className="text-[#16B364]" />
              )}
              Parsed Action
            </div>
            
            {/* Action Type Badge */}
            <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-100 ${actionInfo.color}`}>
              <ActionIcon size={14} />
              <span className="text-sm font-medium">{actionInfo.label}</span>
            </div>

            {/* CREATE ALLOCATION */}
            {parsedCommand.action === 'create_allocation' && (
              <div className="space-y-2 text-sm bg-white border rounded-lg p-3">
                <div className="flex justify-between">
                  <span className="text-[#667085]">Resource:</span>
                  <span className={`font-medium ${!parsedCommand.data?.resource_id ? 'text-red-500' : ''}`}>
                    {parsedCommand.data?.resource_name || 'Unknown'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#667085]">Project:</span>
                  <span className={`font-medium ${!parsedCommand.data?.project_id ? 'text-red-500' : ''}`}>
                    {parsedCommand.data?.project_name || 'Unknown'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#667085]">Allocation:</span>
                  <span className="font-medium">{parsedCommand.data?.percentage}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#667085]">Duration:</span>
                  <span className="font-medium">{parsedCommand.data?.start_date} → {parsedCommand.data?.end_date}</span>
                </div>
              </div>
            )}

            {/* CREATE PROJECT FULL */}
            {parsedCommand.action === 'create_project_full' && (
              <div className="space-y-2 text-sm bg-white border rounded-lg p-3">
                <div className="flex justify-between">
                  <span className="text-[#667085]">Project Name:</span>
                  <span className="font-medium">{parsedCommand.data?.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#667085]">Client:</span>
                  <span className="font-medium">{parsedCommand.data?.client_name}</span>
                </div>
                <div className="text-[#667085] mt-2">Phases:</div>
                <div className="pl-2 space-y-1">
                  {(parsedCommand.data?.phases || []).map((phase, idx) => (
                    <div key={idx} className="flex justify-between text-xs">
                      <span>• {phase.name}</span>
                      <span className="text-[#667085]">{phase.duration_weeks} weeks</span>
                    </div>
                  ))}
                </div>
                {parsedCommand.data?.allocations?.length > 0 && (
                  <>
                    <div className="text-[#667085] mt-2">Team:</div>
                    <div className="pl-2 space-y-1">
                      {parsedCommand.data.allocations.map((alloc, idx) => (
                        <div key={idx} className={`flex justify-between text-xs ${!alloc.resource_id ? 'text-red-500' : ''}`}>
                          <span>• {alloc.resource_name}</span>
                          <span>{alloc.percentage}%</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}

            {/* RESCHEDULE PROJECT */}
            {parsedCommand.action === 'reschedule_project' && (
              <div className="space-y-2 text-sm bg-white border rounded-lg p-3">
                <div className="flex justify-between">
                  <span className="text-[#667085]">Project:</span>
                  <span className={`font-medium ${!parsedCommand.data?.project_id ? 'text-red-500' : ''}`}>
                    {parsedCommand.data?.project_name}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#667085]">Shift:</span>
                  <span className="font-medium">
                    {parsedCommand.data?.weeks_to_shift} weeks {parsedCommand.data?.shift_direction}
                  </span>
                </div>
                <div className="text-xs text-[#667085] mt-2 italic">
                  This will update project dates, all phases, and all resource allocations.
                </div>
              </div>
            )}

            {/* MOVE RESOURCE */}
            {parsedCommand.action === 'move_resource' && (
              <div className="space-y-2 text-sm bg-white border rounded-lg p-3">
                <div className="flex justify-between">
                  <span className="text-[#667085]">Resource:</span>
                  <span className={`font-medium ${!parsedCommand.data?.resource_id ? 'text-red-500' : ''}`}>
                    {parsedCommand.data?.resource_name}
                  </span>
                </div>
                <div className="flex items-center gap-2 my-2">
                  <span className={`${!parsedCommand.data?.source_project_id ? 'text-red-500' : ''}`}>
                    {parsedCommand.data?.source_project_name}
                  </span>
                  <ArrowRightLeft size={14} className="text-[#667085]" />
                  <span className={`${!parsedCommand.data?.target_project_id ? 'text-red-500' : ''}`}>
                    {parsedCommand.data?.target_project_name}
                  </span>
                </div>
                {parsedCommand.data?.new_percentage && (
                  <div className="flex justify-between">
                    <span className="text-[#667085]">New Allocation:</span>
                    <span className="font-medium">{parsedCommand.data.new_percentage}%</span>
                  </div>
                )}
              </div>
            )}

            {/* REMOVE ALLOCATION */}
            {parsedCommand.action === 'remove_allocation' && (
              <div className="space-y-2 text-sm bg-white border rounded-lg p-3">
                <div className="flex justify-between">
                  <span className="text-[#667085]">Resource:</span>
                  <span className={`font-medium ${!parsedCommand.data?.resource_id ? 'text-red-500' : ''}`}>
                    {parsedCommand.data?.resource_name}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#667085]">Remove from:</span>
                  <span className={`font-medium ${!parsedCommand.data?.project_id ? 'text-red-500' : ''}`}>
                    {parsedCommand.data?.project_name}
                  </span>
                </div>
              </div>
            )}

            {/* CREATE RISKS */}
            {parsedCommand.action === 'create_risks' && (
              <div className="space-y-2 text-sm bg-white border rounded-lg p-3">
                <div className="flex justify-between">
                  <span className="text-[#667085]">Project:</span>
                  <span className={`font-medium ${!parsedCommand.data?.project_id ? 'text-red-500' : ''}`}>
                    {parsedCommand.data?.project_name}
                  </span>
                </div>
                <div className="text-[#667085] mt-2">Risks to add:</div>
                <div className="pl-2 space-y-2">
                  {(parsedCommand.data?.risks || []).map((risk, idx) => (
                    <div key={idx} className="text-xs border-l-2 border-amber-400 pl-2">
                      <div>{risk.description}</div>
                      <div className="text-[#667085]">
                        Impact: {risk.impact} | Probability: {risk.probability || 'Medium'}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* UPDATE SUMMARIES */}
            {parsedCommand.action === 'update_summaries' && (
              <div className="space-y-2 text-sm bg-white border rounded-lg p-3">
                <div className="text-[#667085]">Regenerate AI summaries for:</div>
                <div className="pl-2 space-y-1">
                  {(parsedCommand.data?.projects || []).map((project, idx) => (
                    <div key={idx} className={`flex items-center gap-2 ${!project.id ? 'text-red-500' : ''}`}>
                      <span>• {project.name}</span>
                      {!project.id && <span className="text-xs">(not found)</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* PROJECT STATUS UPDATE */}
            {parsedCommand.action === 'project_status_update' && (
              <div className="space-y-2 text-sm bg-white border rounded-lg p-3">
                <div className="flex justify-between">
                  <span className="text-[#667085]">Project:</span>
                  <span className={`font-medium ${!parsedCommand.data?.project_id ? 'text-red-500' : ''}`}>
                    {parsedCommand.data?.project_name}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-[#667085]">Health:</span>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    parsedCommand.data?.health === 'Green' ? 'bg-[#16B364] text-white' :
                    parsedCommand.data?.health === 'Amber' ? 'bg-[#F4B740] text-white' :
                    'bg-[#EF4444] text-white'
                  }`}>
                    {parsedCommand.data?.health}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#667085]">Schedule:</span>
                  <span className="font-medium">{parsedCommand.data?.schedule_status}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#667085]">Progress:</span>
                  <span className="font-medium">{parsedCommand.data?.actual_progress}%</span>
                </div>
                {parsedCommand.data?.accomplishments && (
                  <div className="pt-2 border-t">
                    <div className="text-[#667085] text-xs mb-1">Accomplishments:</div>
                    <div className="text-[#0B1220]">{parsedCommand.data.accomplishments}</div>
                  </div>
                )}
                {parsedCommand.data?.blockers && (
                  <div className="pt-2 border-t">
                    <div className="text-[#667085] text-xs mb-1">Blockers:</div>
                    <div className="text-[#EF4444]">{parsedCommand.data.blockers}</div>
                  </div>
                )}
              </div>
            )}

            {/* TIMESHEET INSIGHTS */}
            {parsedCommand.action === 'timesheet_insights' && (
              <div className="space-y-2 text-sm bg-white border rounded-lg p-3">
                <div className="text-[#667085]">Analyze timesheet data:</div>
                {parsedCommand.data?.project_name && (
                  <div className="flex justify-between">
                    <span className="text-[#667085]">Project:</span>
                    <span className="font-medium">{parsedCommand.data.project_name}</span>
                  </div>
                )}
                {parsedCommand.data?.resource_name && (
                  <div className="flex justify-between">
                    <span className="text-[#667085]">Resource:</span>
                    <span className="font-medium">{parsedCommand.data.resource_name}</span>
                  </div>
                )}
                {insightResult && (
                  <div className="mt-3 space-y-2 border-t pt-3" data-testid="insight-results">
                    <div className="font-medium text-[#0B1220]">Results:</div>
                    {insightResult.summary && (
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="bg-gray-50 p-2 rounded">
                          <div className="text-[#667085]">Planned</div>
                          <div className="font-semibold">{insightResult.summary.total_planned_hours}h</div>
                        </div>
                        <div className="bg-gray-50 p-2 rounded">
                          <div className="text-[#667085]">Actual</div>
                          <div className="font-semibold">{insightResult.summary.total_actual_hours}h</div>
                        </div>
                        <div className={`p-2 rounded ${insightResult.summary.variance_hours > 0 ? 'bg-red-50' : 'bg-green-50'}`}>
                          <div className="text-[#667085]">Variance</div>
                          <div className="font-semibold">{insightResult.summary.variance_hours > 0 ? '+' : ''}{insightResult.summary.variance_hours}h</div>
                        </div>
                        <div className="bg-gray-50 p-2 rounded">
                          <div className="text-[#667085]">Entries</div>
                          <div className="font-semibold">{insightResult.summary.total_entries}</div>
                        </div>
                      </div>
                    )}
                    {insightResult.insights?.length > 0 && (
                      <div className="space-y-1">
                        {insightResult.insights.map((insight, i) => (
                          <div key={i} className="text-xs bg-blue-50 border-l-2 border-blue-400 p-2">{insight}</div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* PLAN ALLOCATION */}
            {parsedCommand.action === 'plan_allocation' && (
              <div className="space-y-2 text-sm bg-white border rounded-lg p-3">
                <div className="text-[#667085]">Find available resources for planning:</div>
                {parsedCommand.data?.start_date && (
                  <div className="flex justify-between">
                    <span className="text-[#667085]">Period:</span>
                    <span className="font-medium">{parsedCommand.data.start_date} to {parsedCommand.data.end_date || 'TBD'}</span>
                  </div>
                )}
                {insightResult && (
                  <div className="mt-3 space-y-2 border-t pt-3" data-testid="plan-results">
                    <div className="font-medium text-[#0B1220]">
                      {insightResult.recommendation}
                    </div>
                    {insightResult.available_resources?.length > 0 && (
                      <div className="space-y-1">
                        <div className="text-xs text-[#667085]">Available resources:</div>
                        {insightResult.available_resources.slice(0, 5).map((r, i) => (
                          <div key={i} className="flex justify-between text-xs bg-green-50 p-1.5 rounded">
                            <span>{r.resource_name}</span>
                            <span className="text-green-700">{r.available_pct}% free</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* MOVE PROJECT PHASE */}
            {parsedCommand.action === 'move_project_phase' && (
              <div className="space-y-2 text-sm bg-white border rounded-lg p-3">
                <div className="flex justify-between">
                  <span className="text-[#667085]">Project:</span>
                  <span className={`font-medium ${!parsedCommand.data?.project_id ? 'text-red-500' : ''}`}>
                    {parsedCommand.data?.project_name}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#667085]">Phase:</span>
                  <span className="font-medium">{parsedCommand.data?.phase_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#667085]">Shift:</span>
                  <span className="font-medium">
                    {parsedCommand.data?.weeks_to_shift > 0 ? `${parsedCommand.data.weeks_to_shift} weeks` : ''}
                    {parsedCommand.data?.days_to_shift > 0 ? `${parsedCommand.data.days_to_shift} days` : ''}
                    {' '}{parsedCommand.data?.shift_direction}
                  </span>
                </div>
              </div>
            )}

            {/* BUDGET ANALYSIS */}
            {parsedCommand.action === 'budget_analysis' && (
              <div className="space-y-2 text-sm bg-white border rounded-lg p-3">
                <div className="flex justify-between">
                  <span className="text-[#667085]">Project:</span>
                  <span className={`font-medium ${!parsedCommand.data?.project_id ? 'text-red-500' : ''}`}>
                    {parsedCommand.data?.project_name || 'Not specified'}
                  </span>
                </div>
                <div className="text-[#667085]">AI will analyze budget vs actual hours, burn rate, and provide recommendations.</div>
                {insightResult && (
                  <div className="mt-3 space-y-3 border-t pt-3" data-testid="budget-analysis-results">
                    {insightResult.narrative && (
                      <div className="bg-[#F5F8FF] border border-[#D1E0FF] rounded p-3 text-sm text-[#0B1220]">
                        {insightResult.narrative}
                      </div>
                    )}
                    {insightResult.burn_rate && insightResult.burn_rate.current_weekly > 0 && (
                      <div className="grid grid-cols-3 gap-2 text-xs">
                        <div className="bg-gray-50 p-2 rounded text-center">
                          <div className="text-[#667085]">Weekly Burn</div>
                          <div className="font-semibold">{insightResult.burn_rate.current_weekly}h</div>
                        </div>
                        <div className="bg-gray-50 p-2 rounded text-center">
                          <div className="text-[#667085]">Projected</div>
                          <div className="font-semibold">{insightResult.burn_rate.projected_total}h</div>
                        </div>
                        <div className={`p-2 rounded text-center ${insightResult.burn_rate.on_track ? 'bg-green-50' : 'bg-red-50'}`}>
                          <div className="text-[#667085]">Status</div>
                          <div className="font-semibold">{insightResult.burn_rate.on_track ? 'On Track' : 'At Risk'}</div>
                        </div>
                      </div>
                    )}
                    {insightResult.alerts?.length > 0 && (
                      <div className="space-y-1">
                        {insightResult.alerts.map((alert, i) => (
                          <div key={i} className={`text-xs p-2 rounded border-l-2 ${
                            alert.severity === 'critical' ? 'bg-red-50 border-red-400' :
                            alert.severity === 'warning' ? 'bg-amber-50 border-amber-400' :
                            'bg-blue-50 border-blue-400'
                          }`}>
                            <span className="font-medium">{alert.title}:</span> {alert.message}
                          </div>
                        ))}
                      </div>
                    )}
                    {insightResult.recommendations?.length > 0 && (
                      <div className="space-y-1">
                        <div className="text-xs font-semibold text-[#667085]">Recommendations:</div>
                        {insightResult.recommendations.map((rec, i) => (
                          <div key={i} className="text-xs bg-green-50 p-2 rounded flex items-start gap-2">
                            <span className={`w-1.5 h-1.5 rounded-full mt-1 shrink-0 ${
                              rec.priority === 'high' ? 'bg-red-500' : rec.priority === 'medium' ? 'bg-amber-500' : 'bg-green-500'
                            }`} />
                            <span><strong>{rec.title}:</strong> {rec.action}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* QUERY (info only) */}
            {parsedCommand.action === 'query' && (
              <div className="bg-[#E6F7FB] border border-[#B2E7F5] rounded-lg p-3">
                <div className="text-sm text-[#0B5566]">
                  <strong>Answer:</strong> {parsedCommand.answer}
                </div>
              </div>
            )}

            {/* Simple CREATE PROJECT */}
            {parsedCommand.action === 'create_project' && (
              <div className="space-y-2 text-sm bg-white border rounded-lg p-3">
                <div className="flex justify-between">
                  <span className="text-[#667085]">Name:</span>
                  <span className="font-medium">{parsedCommand.data?.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#667085]">Client:</span>
                  <span className="font-medium">{parsedCommand.data?.client_name}</span>
                </div>
              </div>
            )}
          </div>

          {/* Validation Warning */}
          {hasValidationIssues && (
            <Alert className="bg-amber-50 border-amber-200">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              <AlertDescription className="text-amber-800">
                <ul className="list-disc list-inside text-sm">
                  {validationIssues.map((issue, idx) => (
                    <li key={idx}>{issue}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}

          {/* Error Message */}
          {error && (
            <Alert variant="destructive" data-testid="confirm-error">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={handleCancel}
            disabled={executeMutation.isPending}
            data-testid="command-cancel"
          >
            Cancel
          </Button>
          {parsedCommand.action !== 'query' && !insightResult && (
            <Button
              type="button"
              onClick={handleConfirm}
              disabled={executeMutation.isPending || hasValidationIssues}
              data-testid="command-confirm"
            >
              {executeMutation.isPending ? (
                <>
                  <Loader2 size={16} className="mr-2 animate-spin" />
                  {['timesheet_insights', 'plan_allocation', 'budget_analysis'].includes(parsedCommand.action) ? 'Analyzing...' : 'Executing...'}
                </>
              ) : (
                ['timesheet_insights', 'plan_allocation', 'budget_analysis'].includes(parsedCommand.action) ? 'Analyze' : 'Confirm & Execute'
              )}
            </Button>
          )}
          {insightResult && (
            <Button type="button" onClick={handleCancel} data-testid="command-close-results">
              Done
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
