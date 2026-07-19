import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { format } from 'date-fns';
import { AlertTriangle, Plus, Edit2, Trash2 } from 'lucide-react';
import { createAllocation, updateAllocation, deleteAllocation, getAllocationsByCell } from '../api';
import { Button } from './ui/button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from './ui/sheet';
import { Label } from './ui/label';
import { Input } from './ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import { Avatar, AvatarImage, AvatarFallback } from './ui/avatar';
import { Badge } from './ui/badge';

const InteractiveTimelineGrid = ({ capacityData, resources, projects, onDateChange }) => {
  const [selectedCell, setSelectedCell] = useState(null);
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [selectedAllocation, setSelectedAllocation] = useState(null);
  const [formData, setFormData] = useState({
    project_id: '',
    start_date: '',
    end_date: '',
    percentage: 50,
  });

  const queryClient = useQueryClient();

  // Query to fetch allocations for a specific cell when clicked
  const { data: cellAllocations, refetch: refetchCellAllocations } = useQuery({
    queryKey: ['cellAllocations', selectedCell?.resource.resource_id, selectedCell?.dayData.date],
    queryFn: async () => {
      if (!selectedCell) return [];
      const response = await getAllocationsByCell(
        selectedCell.resource.resource_id,
        selectedCell.dayData.date
      );
      return response.data;
    },
    enabled: false, // Only run when we manually trigger it
  });

  const createMutation = useMutation({
    mutationFn: createAllocation,
    onSuccess: () => {
      queryClient.invalidateQueries(['capacity']);
      queryClient.invalidateQueries(['allocations']);
      setIsSheetOpen(false);
      resetForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateAllocation(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['capacity']);
      queryClient.invalidateQueries(['allocations']);
      setIsSheetOpen(false);
      resetForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteAllocation,
    onSuccess: () => {
      queryClient.invalidateQueries(['capacity']);
      queryClient.invalidateQueries(['allocations']);
      setIsSheetOpen(false);
      resetForm();
    },
  });

  const resetForm = () => {
    setFormData({ project_id: '', start_date: '', end_date: '', percentage: 50 });
    setSelectedAllocation(null);
    setEditMode(false);
  };

  const handleCellClick = async (resource, dayData) => {
    setSelectedCell({ resource, dayData });
    
    // Fetch allocations for this cell
    const result = await refetchCellAllocations();
    const allocations = result.data || [];

    if (allocations.length > 0) {
      // Edit mode - show first allocation (or we could show a list)
      const firstAlloc = allocations[0];
      setEditMode(true);
      setSelectedAllocation(firstAlloc);
      setFormData({
        project_id: firstAlloc.project_id,
        start_date: firstAlloc.start_date.split('T')[0], // Extract YYYY-MM-DD
        end_date: firstAlloc.end_date.split('T')[0], // Extract YYYY-MM-DD
        percentage: firstAlloc.percentage,
      });
    } else {
      // Create mode
      setEditMode(false);
      setFormData({
        project_id: '',
        start_date: dayData.date,
        end_date: dayData.date,
        percentage: 50,
      });
    }
    
    setIsSheetOpen(true);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (editMode && selectedAllocation) {
      updateMutation.mutate({
        id: selectedAllocation.id,
        data: {
          percentage: parseInt(formData.percentage),
          start_date: formData.start_date,
          end_date: formData.end_date,
          project_id: formData.project_id,
        },
      });
    } else {
      if (selectedCell && formData.project_id) {
        createMutation.mutate({
          resource_id: selectedCell.resource.resource_id,
          project_id: formData.project_id,
          start_date: formData.start_date,
          end_date: formData.end_date,
          percentage: parseInt(formData.percentage),
        });
      }
    }
  };

  const handleDelete = () => {
    if (window.confirm('Are you sure you want to delete this allocation?')) {
      deleteMutation.mutate(selectedAllocation.id);
    }
  };

  if (!capacityData || !capacityData.resources || capacityData.resources.length === 0) {
    return (
      <div className="text-center py-12 text-[#667085]">
        <p>No capacity data available</p>
      </div>
    );
  }

  const firstResource = capacityData.resources[0];
  const days = firstResource.days || [];

  return (
    <>
      <div className="overflow-auto border border-[#E6E8EC] rounded-lg bg-white" data-testid="timeline-grid">
        <div className="min-w-max">
          {/* Header Row */}
          <div
            className="grid sticky top-0 z-10 bg-[#F7F7F8] border-b border-[#E6E8EC]"
            style={{ gridTemplateColumns: `220px repeat(${days.length}, 48px)` }}
          >
            <div className="px-4 py-3 text-xs font-medium text-[#475467] border-r border-[#E6E8EC]">
              Resource
            </div>
            {days.map((day) => (
              <div
                key={day.date}
                className="px-2 py-3 text-xs text-center text-[#475467] border-l border-[#F0F2F5]"
              >
                <div>{format(new Date(day.date), 'MMM')}</div>
                <div className="font-semibold">{format(new Date(day.date), 'd')}</div>
              </div>
            ))}
          </div>

          {/* Resource Rows */}
          {capacityData.resources.map((resource) => (
            <div
              key={resource.resource_id}
              className="grid border-b border-[#E6E8EC] hover:bg-[#FCFCFD]"
              style={{ gridTemplateColumns: `220px repeat(${days.length}, 48px)` }}
            >
              {/* Resource Info Column */}
              <div className="px-4 py-3 flex items-center gap-3 border-r border-[#E6E8EC] bg-white sticky left-0 z-5">
                <Avatar className="w-8 h-8">
                  <AvatarImage src={resources?.find(r => r.id === resource.resource_id)?.avatar_url} />
                  <AvatarFallback>{resource.name.charAt(0)}</AvatarFallback>
                </Avatar>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{resource.name}</div>
                  <div className="text-xs text-[#667085] truncate">{resource.role}</div>
                </div>
              </div>

              {/* Day Cells */}
              {resource.days.map((dayData) => {
                // Determine cell style based on status
                let cellClass = `timeline-cell flex items-center justify-center ${dayData.color} cursor-pointer relative group`;
                
                // Special styling for leave days
                if (dayData.color === 'leave') {
                  cellClass = `timeline-cell flex items-center justify-center bg-[#F0F0F0] cursor-pointer relative group`;
                }
                
                return (
                  <div
                    key={dayData.date}
                    className={cellClass}
                    onClick={() => handleCellClick(resource, dayData)}
                    data-testid={`cell-${resource.resource_id}-${dayData.date}`}
                    title={
                      dayData.on_leave
                        ? `${dayData.leave_type} - Click to manage`
                        : `${dayData.load}% capacity - Click to ${dayData.load > 0 ? 'edit' : 'add'}`
                    }
                    style={
                      dayData.color === 'leave'
                        ? {
                            backgroundImage:
                              'repeating-linear-gradient(45deg, #F0F0F0, #F0F0F0 4px, #E0E0E0 4px, #E0E0E0 8px)',
                          }
                        : {}
                    }
                  >
                    {/* Edit indicator on hover */}
                    {(dayData.load > 0 || dayData.on_leave) && (
                      <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-10 transition-all flex items-center justify-center">
                        <Edit2 size={12} className="text-white opacity-0 group-hover:opacity-100" />
                      </div>
                    )}
                    
                    {/* Leave indicator */}
                    {dayData.on_leave && dayData.load === 0 && (
                      <span className="text-xs text-[#667085] font-medium">LEAVE</span>
                    )}
                    
                    {/* Overload on leave day */}
                    {dayData.color === 'red' && dayData.on_leave && (
                      <>
                        <AlertTriangle size={14} className="text-white" />
                        <span className="text-xs text-white font-medium ml-1">{dayData.load}</span>
                      </>
                    )}
                    
                    {/* Normal allocation display */}
                    {!dayData.on_leave && dayData.color === 'red' && (
                      <AlertTriangle size={14} className="text-white" />
                    )}
                    {!dayData.on_leave && dayData.load > 0 && dayData.load <= 100 && (
                      <span className="text-xs text-white font-medium">{dayData.load}</span>
                    )}
                    {!dayData.on_leave && dayData.load > 100 && (
                      <span className="text-xs text-white font-medium">{dayData.load}</span>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 mt-4 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded" style={{ backgroundColor: '#16B364' }}></div>
          <span className="text-[#475467]">{'< 80% (Safe)'}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded" style={{ backgroundColor: '#F4B740' }}></div>
          <span className="text-[#475467]">80-100% (At capacity)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded" style={{ backgroundColor: '#EF4444' }}></div>
          <span className="text-[#475467]">{`> 100% (Over-allocated)`}</span>
        </div>
      </div>

      {/* Edit/Create Sheet */}
      <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
        <SheetContent data-testid="allocation-sheet">
          <SheetHeader>
            <SheetTitle>
              {editMode ? 'Edit Allocation' : 'Create Allocation'}
            </SheetTitle>
            <SheetDescription>
              {editMode
                ? `Update allocation for ${selectedCell?.resource.name}`
                : `Add a new allocation for ${selectedCell?.resource.name}`}
            </SheetDescription>
          </SheetHeader>

          <form onSubmit={handleSubmit} className="space-y-4 mt-6">
            <div>
              <Label htmlFor="project">Project</Label>
              <Select
                value={formData.project_id}
                onValueChange={(value) => setFormData({ ...formData, project_id: value })}
              >
                <SelectTrigger id="project" data-testid="project-select">
                  <SelectValue placeholder="Select a project" />
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

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="start_date">Start Date</Label>
                <Input
                  id="start_date"
                  type="date"
                  value={formData.start_date}
                  onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                  data-testid="start-date-input"
                />
              </div>
              <div>
                <Label htmlFor="end_date">End Date</Label>
                <Input
                  id="end_date"
                  type="date"
                  value={formData.end_date}
                  onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                  data-testid="end-date-input"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="percentage">Allocation Percentage</Label>
              <Input
                id="percentage"
                type="number"
                min="0"
                max="200"
                value={formData.percentage}
                onChange={(e) => setFormData({ ...formData, percentage: e.target.value })}
                data-testid="percentage-input"
              />
              <p className="text-xs text-[#667085] mt-1">
                Current total: {selectedCell?.dayData.load || 0}%
              </p>
            </div>

            {editMode && cellAllocations && cellAllocations.length > 1 && (
              <div className="p-3 bg-[#FFF8E5] border border-[#F4B740] rounded-lg">
                <p className="text-xs text-[#7A4E00]">
                  ⚠️ This resource has {cellAllocations.length} allocations on this date.
                  Currently editing the first one.
                </p>
              </div>
            )}

            <div className="flex gap-2 mt-6">
              <Button
                type="submit"
                className="flex-1"
                disabled={!formData.project_id || createMutation.isLoading || updateMutation.isLoading}
                data-testid="submit-allocation"
              >
                {createMutation.isLoading || updateMutation.isLoading
                  ? 'Saving...'
                  : editMode
                  ? 'Update'
                  : 'Create'}
              </Button>
              {editMode && (
                <Button
                  type="button"
                  variant="destructive"
                  onClick={handleDelete}
                  disabled={deleteMutation.isLoading}
                  data-testid="delete-allocation"
                >
                  <Trash2 size={16} />
                </Button>
              )}
            </div>
          </form>
        </SheetContent>
      </Sheet>
    </>
  );
};

export default InteractiveTimelineGrid;
