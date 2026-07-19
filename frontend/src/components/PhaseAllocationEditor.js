import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { CalendarDays, Save, AlertCircle } from 'lucide-react';
import api from '../api';

const PhaseAllocationEditor = ({ projectId }) => {
  const queryClient = useQueryClient();
  const [hasChanges, setHasChanges] = useState(false);
  const [localChanges, setLocalChanges] = useState({});

  // Fetch phase allocations data using the shared API client
  // (relative `/api` baseURL + auth interceptor — works in preview & prod).
  const { data, isLoading, error } = useQuery({
    queryKey: ['phaseAllocations', projectId],
    queryFn: async () => {
      const response = await api.get(`/projects/${projectId}/phase-allocations`);
      return response.data;
    },
    enabled: !!projectId
  });

  // Update phase allocation mutation
  const updateMutation = useMutation({
    mutationFn: async ({ allocationId, phaseAllocations }) => {
      const response = await api.put(
        `/allocations/${allocationId}/phase-allocations`,
        { phase_allocations: phaseAllocations }
      );
      return response.data;
    },
    onSuccess: () => {
      toast.success('Phase allocations updated successfully');
      queryClient.invalidateQueries(['phaseAllocations', projectId]);
      queryClient.invalidateQueries(['projectAllocations', projectId]);
      setHasChanges(false);
      setLocalChanges({});
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to update phase allocations');
    }
  });

  const handlePhaseAllocationChange = (allocationId, phaseId, percentage) => {
    setLocalChanges(prev => ({
      ...prev,
      [allocationId]: {
        ...(prev[allocationId] || {}),
        [phaseId]: percentage
      }
    }));
    setHasChanges(true);
  };

  const getPhaseAllocationValue = (allocation, phaseId) => {
    // Check local changes first
    if (localChanges[allocation.id]?.[phaseId] !== undefined) {
      return localChanges[allocation.id][phaseId];
    }

    // Check if there's a phase-specific allocation
    const phaseAllocs = allocation.phase_allocations || [];
    const phaseAlloc = phaseAllocs.find(pa => pa.phase_id === phaseId);
    
    if (phaseAlloc && phaseAlloc.percentage !== undefined) {
      return phaseAlloc.percentage;
    }

    // Return sentinel value to indicate "use project default"
    return 'default';
  };

  const saveAllChanges = () => {
    // For each allocation that has changes, update it
    Object.entries(localChanges).forEach(([allocationId, phaseChanges]) => {
      // Build phase_allocations array
      const allocation = data?.allocations?.find(a => a.id === allocationId);
      if (!allocation) return;

      const phaseAllocations = data.phases.map(phase => {
        const percentage = phaseChanges[phase.id] !== undefined 
          ? phaseChanges[phase.id] 
          : getPhaseAllocationValue(allocation, phase.id);

        return {
          phase_id: phase.id,
          percentage: percentage === 'default' ? allocation.percentage : parseInt(percentage),
          hours: null
        };
      });

      updateMutation.mutate({ allocationId, phaseAllocations });
    });
  };

  const calculateHours = (percentage, resourceCapacity = 100) => {
    if (percentage === 'default' || percentage === '' || percentage === null || percentage === undefined) return null;
    const baseHours = (resourceCapacity / 100) * 40;
    return ((parseInt(percentage) / 100) * baseHours).toFixed(1);
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-8">
          <div className="text-center text-gray-600">Loading phase allocations...</div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="py-8">
          <div className="flex items-center justify-center gap-2 text-red-600">
            <AlertCircle className="h-5 w-5" />
            <span>Failed to load phase allocations</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  const allocations = data?.allocations || [];
  const phases = data?.phases || [];

  if (allocations.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Phase Allocations</CardTitle>
          <CardDescription>
            Allocate resources at different percentages per phase
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-gray-600">
            No resource allocations found. Add team members first.
          </div>
        </CardContent>
      </Card>
    );
  }

  if (phases.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Phase Allocations</CardTitle>
          <CardDescription>
            Allocate resources at different percentages per phase
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-gray-600">
            No project phases defined. Add phases to the project first.
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Phase-Based Allocations</CardTitle>
            <CardDescription>
              Set different allocation percentages per phase. Leave blank to use project-level allocation.
            </CardDescription>
          </div>
          {hasChanges && (
            <Button 
              onClick={saveAllChanges}
              disabled={updateMutation.isLoading}
              className="gap-2"
            >
              <Save className="h-4 w-4" />
              Save Changes
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b">
                <th className="text-left py-3 px-4 font-semibold text-gray-700">
                  Resource
                </th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">
                  Project Default
                </th>
                {phases.map(phase => (
                  <th key={phase.id} className="text-left py-3 px-4 font-semibold text-gray-700">
                    <div className="flex items-center gap-2">
                      <CalendarDays className="h-4 w-4" />
                      {phase.name}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {allocations.map(allocation => {
                const projectPercentage = allocation.percentage || 0;
                const resourceCapacity = allocation.resource_standard_capacity || 100;
                const projectHours = calculateHours(projectPercentage, resourceCapacity);

                return (
                  <tr key={allocation.id} className="border-b hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <div>
                        <div className="font-medium">{allocation.resource_name}</div>
                        {allocation.resource_role && (
                          <div className="text-sm text-gray-500">{allocation.resource_role}</div>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant="outline" className="font-semibold">
                        {projectPercentage}% ({projectHours}h)
                      </Badge>
                    </td>
                    {phases.map(phase => {
                      const currentValue = getPhaseAllocationValue(allocation, phase.id);
                      const displayPercentage = currentValue === 'default' ? projectPercentage : currentValue;
                      const displayHours = calculateHours(displayPercentage, resourceCapacity);
                      const isUsingDefault = currentValue === 'default';

                      return (
                        <td key={phase.id} className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            <Select
                              value={currentValue.toString()}
                              onValueChange={(value) => handlePhaseAllocationChange(allocation.id, phase.id, value)}
                            >
                              <SelectTrigger className="w-40">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="default">
                                  Project Default ({projectPercentage}%)
                                </SelectItem>
                                <SelectItem value="0">0%</SelectItem>
                                <SelectItem value="25">25%</SelectItem>
                                <SelectItem value="50">50%</SelectItem>
                                <SelectItem value="75">75%</SelectItem>
                                <SelectItem value="100">100%</SelectItem>
                              </SelectContent>
                            </Select>
                            {!isUsingDefault && (
                              <Badge variant="secondary" className="text-xs">
                                {displayHours}h
                              </Badge>
                            )}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-5 w-5 text-blue-600 mt-0.5" />
            <div className="text-sm text-blue-900">
              <p className="font-semibold mb-1">How Phase Allocations Work:</p>
              <ul className="list-disc list-inside space-y-1 text-blue-800">
                <li>Set different allocation percentages per phase (e.g., 100% in Phase 1, 50% in Phase 2)</li>
                <li>Leave as "Project Default" to use the project-level allocation for all phases</li>
                <li>WBS tasks will only be assigned to resources allocated to that phase</li>
                <li>Timesheets will validate against phase-specific allocations</li>
                <li>Standard full-time capacity is 40 hours per week (100%)</li>
              </ul>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default PhaseAllocationEditor;
