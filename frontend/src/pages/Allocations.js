import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getAllocations,
  createAllocation,
  updateAllocation,
  deleteAllocation,
  getResources,
  getProjects,
  getMe,
} from '../api';
import { format, parseISO, startOfWeek, endOfWeek, addWeeks, subWeeks, startOfMonth, endOfMonth, addMonths, addDays, isAfter, isBefore, isWithinInterval } from 'date-fns';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { Switch } from '../components/ui/switch';
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
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '../components/ui/collapsible';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../components/ui/tabs';
import { Plus, Edit, Trash2, ChevronDown, ChevronRight, ChevronLeft, Users, Search, Briefcase, Calendar, GanttChart, Eye, EyeOff, Filter, X } from 'lucide-react';
import { toast } from 'sonner';
import { formatAllocation } from '../utils/capacityHelpers';

const Allocations = () => {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingAllocation, setEditingAllocation] = useState(null);
  const [expandedResources, setExpandedResources] = useState({});
  const [expandedProjects, setExpandedProjects] = useState({});
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('weekly'); // 'weekly', 'resource', 'project', 'timeline'
  const [showPastAllocations, setShowPastAllocations] = useState(false);
  const [timelineWeeks, setTimelineWeeks] = useState(8);
  
  // Time period filter state
  const [timePeriod, setTimePeriod] = useState('this_week'); // 'this_week', 'next_week', 'this_month', 'next_month', 'custom'
  const [customStartDate, setCustomStartDate] = useState('');
  const [customEndDate, setCustomEndDate] = useState('');
  const [selectedProject, setSelectedProject] = useState('all');
  const [weekOffset, setWeekOffset] = useState(0); // For navigating weeks
  
  const [formData, setFormData] = useState({
    resource_id: '',
    project_id: '',
    start_date: '',
    end_date: '',
    percentage: 50,
  });

  const queryClient = useQueryClient();
  const today = new Date();

  const { data: userData } = useQuery({
    queryKey: ['me'],
    queryFn: async () => { const r = await getMe(); return r.data; },
  });

  const { data: allocations, isLoading } = useQuery({
    queryKey: ['allocations'],
    queryFn: async () => { const r = await getAllocations(); return r.data; },
  });

  const { data: resources } = useQuery({
    queryKey: ['resources'],
    queryFn: async () => { const r = await getResources(); return r.data; },
  });

  const { data: projects } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => { const r = await getProjects(); return r.data; },
  });

  const isAdmin = userData?.role === 'admin' || userData?.role === 'super_admin';

  // Calculate the current filter date range
  const filterDateRange = useMemo(() => {
    const baseDate = addWeeks(today, weekOffset);
    
    switch (timePeriod) {
      case 'this_week':
        return {
          start: startOfWeek(baseDate, { weekStartsOn: 1 }),
          end: addDays(startOfWeek(baseDate, { weekStartsOn: 1 }), 4), // Friday (business days only)
          label: weekOffset === 0 ? 'This Week' : format(startOfWeek(baseDate, { weekStartsOn: 1 }), 'MMM d') + ' - ' + format(addDays(startOfWeek(baseDate, { weekStartsOn: 1 }), 4), 'MMM d, yyyy')
        };
      case 'next_week':
        const nextWeekStart = startOfWeek(addWeeks(baseDate, 1), { weekStartsOn: 1 });
        return {
          start: nextWeekStart,
          end: addDays(nextWeekStart, 4), // Friday (business days only)
          label: 'Next Week'
        };
      case 'this_month':
        return {
          start: startOfMonth(baseDate),
          end: endOfMonth(baseDate),
          label: format(baseDate, 'MMMM yyyy')
        };
      case 'next_month':
        const nextMonth = addMonths(baseDate, 1);
        return {
          start: startOfMonth(nextMonth),
          end: endOfMonth(nextMonth),
          label: format(nextMonth, 'MMMM yyyy')
        };
      case 'custom':
        return {
          start: customStartDate ? parseISO(customStartDate) : null,
          end: customEndDate ? parseISO(customEndDate) : null,
          label: customStartDate && customEndDate ? `${format(parseISO(customStartDate), 'MMM d')} - ${format(parseISO(customEndDate), 'MMM d, yyyy')}` : 'Custom Range'
        };
      default:
        return {
          start: startOfWeek(today, { weekStartsOn: 1 }),
          end: addDays(startOfWeek(today, { weekStartsOn: 1 }), 4), // Friday (business days only)
          label: 'This Week'
        };
    }
  }, [timePeriod, weekOffset, today, customStartDate, customEndDate]);

  // Check if an allocation is active during the filter period
  const isAllocationActiveInPeriod = (alloc, period) => {
    if (!period.start || !period.end) return true;
    
    const allocStart = alloc.start_date ? parseISO(alloc.start_date.split('T')[0]) : null;
    const allocEnd = alloc.end_date ? parseISO(alloc.end_date.split('T')[0]) : null;
    
    if (!allocStart || !allocEnd) return false;
    
    // Check if allocation overlaps with the filter period
    return !(isAfter(allocStart, period.end) || isBefore(allocEnd, period.start));
  };

  // Filter allocations based on time period and project
  const filteredAllocations = useMemo(() => {
    if (!allocations) return [];
    
    let filtered = allocations;
    
    // Filter by time period (for weekly view and filtered views)
    if (viewMode === 'weekly' || viewMode === 'resource' || viewMode === 'project') {
      filtered = filtered.filter(alloc => isAllocationActiveInPeriod(alloc, filterDateRange));
    }
    
    // Filter by project
    if (selectedProject !== 'all') {
      filtered = filtered.filter(alloc => alloc.project_id === selectedProject);
    }
    
    // Filter out past allocations unless toggle is on (only for non-weekly views)
    if (!showPastAllocations && viewMode !== 'weekly') {
      filtered = filtered.filter(alloc => {
        const endDate = alloc.end_date ? parseISO(alloc.end_date.split('T')[0]) : null;
        return !endDate || isAfter(endDate, today) || format(endDate, 'yyyy-MM-dd') === format(today, 'yyyy-MM-dd');
      });
    }
    
    return filtered;
  }, [allocations, filterDateRange, selectedProject, showPastAllocations, viewMode, today]);

  // Group allocations by resource
  const groupedByResource = useMemo(() => {
    if (!filteredAllocations) return [];

    const resourceMap = {};

    filteredAllocations.forEach(alloc => {
      const rid = alloc.resource_id;
      if (!resourceMap[rid]) {
        resourceMap[rid] = {
          id: rid,
          name: alloc.resource_name || 'Unknown Resource',
          role: alloc.resource_role || '',
          allocations: [],
        };
      }
      resourceMap[rid].allocations.push(alloc);
    });

    let grouped = Object.values(resourceMap);

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      grouped = grouped.filter(r => {
        const nameMatch = r.name?.toLowerCase().includes(q);
        const projectMatch = r.allocations.some(a =>
          (a.project_name || '').toLowerCase().includes(q)
        );
        return nameMatch || projectMatch;
      });
    }

    grouped.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    return grouped;
  }, [filteredAllocations, searchQuery]);

  // Group allocations by project
  const groupedByProject = useMemo(() => {
    if (!filteredAllocations) return [];

    const projectMap = {};

    filteredAllocations.forEach(alloc => {
      const pid = alloc.project_id;
      if (!projectMap[pid]) {
        const project = projects?.find(p => p.id === pid);
        projectMap[pid] = {
          id: pid,
          name: alloc.project_name || 'Unknown Project',
          client_name: alloc.client_name || project?.client_name || '',
          status: project?.status || 'Active',
          allocations: [],
        };
      }
      projectMap[pid].allocations.push(alloc);
    });

    let grouped = Object.values(projectMap);

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      grouped = grouped.filter(p => {
        const nameMatch = p.name?.toLowerCase().includes(q);
        const clientMatch = p.client_name?.toLowerCase().includes(q);
        const resourceMatch = p.allocations.some(a =>
          (a.resource_name || '').toLowerCase().includes(q)
        );
        return nameMatch || clientMatch || resourceMatch;
      });
    }

    grouped.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    return grouped;
  }, [filteredAllocations, searchQuery, projects]);

  // Timeline data
  const timelineData = useMemo(() => {
    if (!allocations || !resources) return { weeks: [], resources: [] };

    const weekStart = startOfWeek(addWeeks(today, weekOffset), { weekStartsOn: 1 });
    const weeks = [];
    for (let i = 0; i < timelineWeeks; i++) {
      const start = addWeeks(weekStart, i);
      const end = addDays(start, 4); // Friday (business days only)
      weeks.push({ start, end, label: format(start, 'MMM d') });
    }

    // Filter by project if selected
    let relevantAllocations = allocations;
    if (selectedProject !== 'all') {
      relevantAllocations = allocations.filter(a => a.project_id === selectedProject);
    }

    const resourceData = resources.filter(resource => resource.active !== false).map(resource => {
      const resourceAllocs = relevantAllocations.filter(a => a.resource_id === resource.id);
      const weeklyAllocations = weeks.map(week => {
        const activeAllocs = resourceAllocs.filter(alloc => {
          const allocStart = alloc.start_date ? parseISO(alloc.start_date.split('T')[0]) : null;
          const allocEnd = alloc.end_date ? parseISO(alloc.end_date.split('T')[0]) : null;
          if (!allocStart || !allocEnd) return false;
          return !(isAfter(allocStart, week.end) || isBefore(allocEnd, week.start));
        });
        const totalPct = activeAllocs.reduce((sum, a) => sum + (a.percentage || 0), 0);
        return { allocations: activeAllocs, totalPct };
      });
      return { ...resource, weeklyAllocations };
    });

    return { weeks, resources: resourceData };
  }, [allocations, resources, timelineWeeks, today, weekOffset, selectedProject]);

  // Auto-expand all on first load
  useMemo(() => {
    if (groupedByResource.length > 0 && Object.keys(expandedResources).length === 0) {
      const initial = {};
      groupedByResource.forEach(r => { initial[r.id] = true; });
      setExpandedResources(initial);
    }
  }, [groupedByResource.length]);

  useMemo(() => {
    if (groupedByProject.length > 0 && Object.keys(expandedProjects).length === 0) {
      const initial = {};
      groupedByProject.forEach(p => { initial[p.id] = true; });
      setExpandedProjects(initial);
    }
  }, [groupedByProject.length]);

  const toggleResource = (resourceId) => {
    setExpandedResources(prev => ({ ...prev, [resourceId]: !prev[resourceId] }));
  };

  const toggleProject = (projectId) => {
    setExpandedProjects(prev => ({ ...prev, [projectId]: !prev[projectId] }));
  };

  const expandAll = () => {
    if (viewMode === 'resource' || viewMode === 'weekly') {
      const all = {};
      groupedByResource.forEach(r => { all[r.id] = true; });
      setExpandedResources(all);
    } else if (viewMode === 'project') {
      const all = {};
      groupedByProject.forEach(p => { all[p.id] = true; });
      setExpandedProjects(all);
    }
  };

  const collapseAll = () => {
    if (viewMode === 'resource' || viewMode === 'weekly') setExpandedResources({});
    else if (viewMode === 'project') setExpandedProjects({});
  };

  const getProjectName = (alloc) => alloc.project_name || 'Unknown';
  const getProjectClient = (alloc) => alloc.client_name || '';

  const getTotalPercentage = (allocs) =>
    allocs.reduce((sum, a) => sum + (a.percentage || 0), 0);

  const getUtilColor = (total) => {
    if (total > 100) return 'text-[#EF4444]';
    if (total >= 80) return 'text-[#F4B740]';
    return 'text-[#16B364]';
  };

  const getUtilBadge = (total) => {
    if (total > 100) return { label: 'Over-allocated', className: 'bg-[#EF4444]/10 text-[#EF4444] border-[#EF4444]/30' };
    if (total >= 80) return { label: 'Near capacity', className: 'bg-[#F4B740]/10 text-[#F4B740] border-[#F4B740]/30' };
    if (total > 0) return { label: 'Available', className: 'bg-[#16B364]/10 text-[#16B364] border-[#16B364]/30' };
    return { label: 'Unallocated', className: 'bg-[#667085]/10 text-[#667085] border-[#667085]/30' };
  };

  const getTimelineBarColor = (pct) => {
    if (pct > 100) return 'bg-[#EF4444]';
    if (pct >= 80) return 'bg-[#F4B740]';
    if (pct > 0) return 'bg-[#1570EF]';
    return 'bg-[#E6E8EC]';
  };

  const isPastAllocation = (alloc) => {
    const endDate = alloc.end_date ? parseISO(alloc.end_date.split('T')[0]) : null;
    return endDate && isBefore(endDate, today);
  };

  // Navigation functions
  const goToPreviousWeek = () => setWeekOffset(prev => prev - 1);
  const goToNextWeek = () => setWeekOffset(prev => prev + 1);
  const goToToday = () => setWeekOffset(0);

  // Mutations
  const createMutation = useMutation({
    mutationFn: createAllocation,
    onSuccess: () => {
      queryClient.invalidateQueries(['allocations']);
      queryClient.invalidateQueries(['capacity']);
      queryClient.invalidateQueries(['projects']); // Cross-page: team count on Dashboard
      queryClient.invalidateQueries(['portfolioHealthScores']); // Cross-page: team score
      toast.success('Allocation created');
      setIsDialogOpen(false);
      resetForm();
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to create'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateAllocation(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['allocations']);
      queryClient.invalidateQueries(['capacity']);
      queryClient.invalidateQueries(['projects']); // Cross-page
      queryClient.invalidateQueries(['portfolioHealthScores']); // Cross-page
      toast.success('Allocation updated');
      setIsDialogOpen(false);
      resetForm();
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to update'),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteAllocation,
    onSuccess: () => {
      queryClient.invalidateQueries(['allocations']);
      queryClient.invalidateQueries(['capacity']);
      queryClient.invalidateQueries(['projects']); // Cross-page
      queryClient.invalidateQueries(['portfolioHealthScores']); // Cross-page
      toast.success('Allocation deleted');
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to delete'),
  });

  const resetForm = () => {
    setFormData({ resource_id: '', project_id: '', start_date: '', end_date: '', percentage: 50 });
    setEditingAllocation(null);
  };

  const handleOpenDialog = (allocation = null) => {
    if (allocation) {
      setEditingAllocation(allocation);
      setFormData({
        resource_id: allocation.resource_id,
        project_id: allocation.project_id,
        start_date: allocation.start_date?.split('T')[0] || '',
        end_date: allocation.end_date?.split('T')[0] || '',
        percentage: allocation.percentage,
      });
    } else {
      resetForm();
    }
    setIsDialogOpen(true);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (editingAllocation) {
      updateMutation.mutate({ id: editingAllocation.id, data: formData });
    } else {
      createMutation.mutate(formData);
    }
  };

  const handleDelete = (id) => {
    if (window.confirm('Delete this allocation?')) {
      deleteMutation.mutate(id);
    }
  };

  // Render allocation row
  const renderAllocationRow = (alloc, showResource = false, showProject = true) => {
    const isPast = isPastAllocation(alloc);
    // Get resource to access standard_capacity
    const resource = resources?.find(r => r.id === alloc.resource_id);
    const resourceCapacity = resource?.standard_capacity || 100;
    
    return (
      <div
        key={alloc.id}
        className={`flex items-center justify-between px-5 py-3 hover:bg-[#F9FAFB] border-b border-[#F2F3F5] last:border-b-0 ml-12 ${isPast ? 'opacity-50' : ''}`}
        data-testid={`allocation-row-${alloc.id}`}
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {showProject && <Briefcase size={14} className="text-[#98A2B3] shrink-0" />}
          {showResource && <Users size={14} className="text-[#98A2B3] shrink-0" />}
          <div className="min-w-0">
            <div className="font-medium text-sm text-[#0B1220] truncate flex items-center gap-2">
              {showProject ? getProjectName(alloc) : alloc.resource_name}
              {isPast && <Badge variant="outline" className="text-[10px] px-1.5 py-0 bg-[#667085]/10 text-[#667085]">Past</Badge>}
            </div>
            <div className="text-xs text-[#667085]">
              {showProject ? getProjectClient(alloc) : alloc.resource_role}
              {alloc.role && <span className="ml-2 text-[#1570EF]">{alloc.role}</span>}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-6 shrink-0">
          <div className="text-xs text-[#667085] hidden sm:block">
            {alloc.start_date && format(new Date(alloc.start_date), 'MMM d')}
            {' - '}
            {alloc.end_date && format(new Date(alloc.end_date), 'MMM d, yyyy')}
          </div>
          <div className="w-16 text-right">
            <span className="font-semibold text-sm">{formatAllocation(alloc.percentage, resourceCapacity)}</span>
          </div>
          {isAdmin && (
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                onClick={(e) => { e.stopPropagation(); handleOpenDialog(alloc); }}
                data-testid={`edit-allocation-${alloc.id}`}
              >
                <Edit size={13} />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0 text-[#EF4444] hover:text-[#EF4444]"
                onClick={(e) => { e.stopPropagation(); handleDelete(alloc.id); }}
                data-testid={`delete-allocation-${alloc.id}`}
              >
                <Trash2 size={13} />
              </Button>
            </div>
          )}
        </div>
      </div>
    );
  };

  // Render resource group (shared between weekly and resource views)
  const renderResourceGroup = (resource) => {
    const total = getTotalPercentage(resource.allocations);
    const utilBadge = getUtilBadge(total);
    const isExpanded = expandedResources[resource.id] ?? false;

    return (
      <Collapsible
        key={resource.id}
        open={isExpanded}
        onOpenChange={() => toggleResource(resource.id)}
      >
        <div
          className="bg-white border border-[#E6E8EC] rounded-lg overflow-hidden"
          data-testid={`resource-group-${resource.id}`}
        >
          <CollapsibleTrigger asChild>
            <button
              className="w-full flex items-center justify-between px-5 py-4 hover:bg-[#F9FAFB] transition-colors text-left"
              data-testid={`resource-toggle-${resource.id}`}
            >
              <div className="flex items-center gap-4">
                {isExpanded ? (
                  <ChevronDown size={18} className="text-[#98A2B3] shrink-0" />
                ) : (
                  <ChevronRight size={18} className="text-[#98A2B3] shrink-0" />
                )}
                <div className="w-9 h-9 rounded-full bg-[#1570EF]/10 flex items-center justify-center text-[#1570EF] font-semibold text-sm shrink-0">
                  {(resource.name || '?')[0].toUpperCase()}
                </div>
                <div>
                  <div className="font-semibold text-[#0B1220]">{resource.name}</div>
                  {resource.role && (
                    <div className="text-xs text-[#667085]">{resource.role}</div>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-4">
                <div className="text-right mr-2">
                  <div className="flex items-center gap-2">
                    <span className={`text-lg font-bold ${getUtilColor(total)}`}>{total}%</span>
                    <span className="text-xs text-[#667085]">of capacity</span>
                  </div>
                  <Progress
                    value={Math.min(total, 100)}
                    className="w-24 h-1.5 mt-1"
                  />
                </div>
                <Badge variant="outline" className={utilBadge.className}>
                  {utilBadge.label}
                </Badge>
                <span className="text-xs text-[#98A2B3]">
                  {resource.allocations.length} project{resource.allocations.length !== 1 ? 's' : ''}
                </span>
              </div>
            </button>
          </CollapsibleTrigger>

          <CollapsibleContent>
            <div className="border-t border-[#E6E8EC]">
              {resource.allocations.map((alloc) => renderAllocationRow(alloc, false, true))}
            </div>
          </CollapsibleContent>
        </div>
      </Collapsible>
    );
  };

  return (
    <div className="space-y-6" data-testid="allocations-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold flex items-center gap-3" style={{ fontFamily: 'Space Grotesk' }}>
            <Calendar size={28} />
            Allocations
          </h1>
          <p className="text-sm text-[#667085] mt-1">
            Resource capacity planning • Percentage = % of resource's weekly capacity
          </p>
        </div>
        {isAdmin && (
          <Button onClick={() => handleOpenDialog()} data-testid="add-allocation-button">
            <Plus size={16} className="mr-2" />
            Add Allocation
          </Button>
        )}
      </div>

      {/* View Mode Tabs */}
      <Tabs value={viewMode} onValueChange={(v) => { setViewMode(v); setWeekOffset(0); }} className="w-full">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <TabsList className="grid w-auto grid-cols-4">
            <TabsTrigger value="weekly" className="flex items-center gap-2" data-testid="view-weekly-tab">
              <Calendar size={14} />
              Weekly
            </TabsTrigger>
            <TabsTrigger value="resource" className="flex items-center gap-2" data-testid="view-resource-tab">
              <Users size={14} />
              By Resource
            </TabsTrigger>
            <TabsTrigger value="project" className="flex items-center gap-2" data-testid="view-project-tab">
              <Briefcase size={14} />
              By Project
            </TabsTrigger>
            <TabsTrigger value="timeline" className="flex items-center gap-2" data-testid="view-timeline-tab">
              <GanttChart size={14} />
              Timeline
            </TabsTrigger>
          </TabsList>

          <div className="flex items-center gap-4">
            {viewMode !== 'timeline' && (
              <div className="flex items-center gap-2">
                <Switch
                  id="show-past"
                  checked={showPastAllocations}
                  onCheckedChange={setShowPastAllocations}
                  data-testid="show-past-toggle"
                />
                <Label htmlFor="show-past" className="text-sm text-[#667085] cursor-pointer flex items-center gap-1">
                  {showPastAllocations ? <Eye size={14} /> : <EyeOff size={14} />}
                  Past
                </Label>
              </div>
            )}
          </div>
        </div>

        {/* Filters Row */}
        <div className="flex items-center gap-3 mt-4 flex-wrap">
          {/* Week Navigation (for weekly view) */}
          {(viewMode === 'weekly' || viewMode === 'timeline') && (
            <div className="flex items-center gap-2 bg-white border border-[#E6E8EC] rounded-lg p-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={goToPreviousWeek}
                data-testid="prev-week-btn"
              >
                <ChevronLeft size={16} />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 px-3 text-sm font-medium"
                onClick={goToToday}
                data-testid="today-btn"
              >
                Today
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={goToNextWeek}
                data-testid="next-week-btn"
              >
                <ChevronRight size={16} />
              </Button>
            </div>
          )}

          {/* Time Period Filter */}
          {viewMode === 'weekly' && (
            <div className="flex items-center gap-2 bg-[#1570EF]/5 border border-[#1570EF]/20 rounded-lg px-3 py-2">
              <Calendar size={14} className="text-[#1570EF]" />
              <span className="text-sm font-medium text-[#1570EF]">
                {filterDateRange.label}
              </span>
              <span className="text-xs text-[#667085]">
                ({format(filterDateRange.start, 'MMM d')} - {format(filterDateRange.end, 'MMM d')})
              </span>
            </div>
          )}

          {/* Project Filter */}
          <div className="flex items-center gap-2">
            <Filter size={14} className="text-[#667085]" />
            <Select value={selectedProject} onValueChange={setSelectedProject}>
              <SelectTrigger className="w-48 h-9" data-testid="project-filter">
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
            {selectedProject !== 'all' && (
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => setSelectedProject('all')}
              >
                <X size={14} />
              </Button>
            )}
          </div>

          {/* Search */}
          <div className="relative flex-1 max-w-sm">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#98A2B3]" />
            <Input
              placeholder="Search resources or projects..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 h-9"
              data-testid="allocation-search"
            />
          </div>

          {viewMode !== 'timeline' && (
            <>
              <Button variant="outline" size="sm" onClick={expandAll} className="h-9">
                Expand All
              </Button>
              <Button variant="outline" size="sm" onClick={collapseAll} className="h-9">
                Collapse All
              </Button>
            </>
          )}

          {viewMode === 'timeline' && (
            <Select value={String(timelineWeeks)} onValueChange={(v) => setTimelineWeeks(Number(v))}>
              <SelectTrigger className="w-28 h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="4">4 weeks</SelectItem>
                <SelectItem value="8">8 weeks</SelectItem>
                <SelectItem value="12">12 weeks</SelectItem>
                <SelectItem value="16">16 weeks</SelectItem>
              </SelectContent>
            </Select>
          )}
        </div>

        {/* Weekly View - Default, shows this week's allocations */}
        <TabsContent value="weekly" className="mt-4">
          {isLoading ? (
            <div className="text-center py-12 text-[#667085]">Loading allocations...</div>
          ) : groupedByResource.length === 0 ? (
            <div className="text-center py-16 bg-white border border-[#E6E8EC] rounded-lg">
              <Calendar size={48} className="mx-auto mb-4 text-[#98A2B3]" />
              <p className="text-[#667085] font-medium">No allocations for {filterDateRange.label.toLowerCase()}</p>
              <p className="text-sm text-[#98A2B3] mt-1">
                {selectedProject !== 'all' ? 'Try clearing the project filter or ' : ''}
                Use the navigation to view other weeks
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {/* Summary Card */}
              <div className="bg-[#F9FAFB] border border-[#E6E8EC] rounded-lg p-4 mb-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-[#0B1220]">{filterDateRange.label}</h3>
                    <p className="text-sm text-[#667085]">
                      {groupedByResource.length} resources • {filteredAllocations.length} allocations
                    </p>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-[#16B364]">
                        {groupedByResource.filter(r => getTotalPercentage(r.allocations) < 80).length}
                      </div>
                      <div className="text-xs text-[#667085]">Available</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-[#F4B740]">
                        {groupedByResource.filter(r => {
                          const t = getTotalPercentage(r.allocations);
                          return t >= 80 && t <= 100;
                        }).length}
                      </div>
                      <div className="text-xs text-[#667085]">At Capacity</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-[#EF4444]">
                        {groupedByResource.filter(r => getTotalPercentage(r.allocations) > 100).length}
                      </div>
                      <div className="text-xs text-[#667085]">Over</div>
                    </div>
                  </div>
                </div>
              </div>

              {groupedByResource.map(renderResourceGroup)}
            </div>
          )}
        </TabsContent>

        {/* Resource View */}
        <TabsContent value="resource" className="mt-4">
          {isLoading ? (
            <div className="text-center py-12 text-[#667085]">Loading allocations...</div>
          ) : groupedByResource.length === 0 ? (
            <div className="text-center py-16 bg-white border border-[#E6E8EC] rounded-lg">
              <Users size={48} className="mx-auto mb-4 text-[#98A2B3]" />
              <p className="text-[#667085]">{searchQuery ? 'No matching results' : 'No allocations yet'}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {groupedByResource.map(renderResourceGroup)}
            </div>
          )}
        </TabsContent>

        {/* Project View */}
        <TabsContent value="project" className="mt-4">
          {isLoading ? (
            <div className="text-center py-12 text-[#667085]">Loading allocations...</div>
          ) : groupedByProject.length === 0 ? (
            <div className="text-center py-16 bg-white border border-[#E6E8EC] rounded-lg">
              <Briefcase size={48} className="mx-auto mb-4 text-[#98A2B3]" />
              <p className="text-[#667085]">{searchQuery ? 'No matching results' : 'No project allocations yet'}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {groupedByProject.map((project) => {
                const total = getTotalPercentage(project.allocations);
                const isExpanded = expandedProjects[project.id] ?? false;
                const statusColor = project.status === 'Active' ? 'bg-[#16B364]' : project.status === 'Pipeline' ? 'bg-[#F4B740]' : 'bg-[#667085]';

                return (
                  <Collapsible
                    key={project.id}
                    open={isExpanded}
                    onOpenChange={() => toggleProject(project.id)}
                  >
                    <div
                      className="bg-white border border-[#E6E8EC] rounded-lg overflow-hidden"
                      data-testid={`project-group-${project.id}`}
                    >
                      <CollapsibleTrigger asChild>
                        <button
                          className="w-full flex items-center justify-between px-5 py-4 hover:bg-[#F9FAFB] transition-colors text-left"
                          data-testid={`project-toggle-${project.id}`}
                        >
                          <div className="flex items-center gap-4">
                            {isExpanded ? (
                              <ChevronDown size={18} className="text-[#98A2B3] shrink-0" />
                            ) : (
                              <ChevronRight size={18} className="text-[#98A2B3] shrink-0" />
                            )}
                            <div className={`w-2 h-9 rounded-full ${statusColor} shrink-0`} />
                            <div>
                              <div className="font-semibold text-[#0B1220]">{project.name}</div>
                              <div className="text-xs text-[#667085]">{project.client_name}</div>
                            </div>
                          </div>

                          <div className="flex items-center gap-4">
                            <Badge variant="outline" className="text-xs">
                              {project.status}
                            </Badge>
                            <div className="text-right">
                              <div className="text-lg font-bold text-[#0B1220]">{total}%</div>
                              <div className="text-xs text-[#667085]">total capacity</div>
                            </div>
                            <span className="text-xs text-[#98A2B3]">
                              {project.allocations.length} resource{project.allocations.length !== 1 ? 's' : ''}
                            </span>
                          </div>
                        </button>
                      </CollapsibleTrigger>

                      <CollapsibleContent>
                        <div className="border-t border-[#E6E8EC]">
                          {project.allocations.map((alloc) => renderAllocationRow(alloc, true, false))}
                        </div>
                      </CollapsibleContent>
                    </div>
                  </Collapsible>
                );
              })}
            </div>
          )}
        </TabsContent>

        {/* Timeline View */}
        <TabsContent value="timeline" className="mt-4">
          <div className="bg-white border border-[#E6E8EC] rounded-lg overflow-hidden">
            {/* Timeline Header */}
            <div className="flex border-b border-[#E6E8EC]">
              <div className="w-48 shrink-0 px-4 py-3 bg-[#F9FAFB] font-semibold text-sm text-[#667085] border-r border-[#E6E8EC]">
                Resource
              </div>
              <div className="flex-1 flex overflow-x-auto">
                {timelineData.weeks.map((week, i) => (
                  <div
                    key={i}
                    className={`flex-1 min-w-[80px] px-2 py-3 text-center text-xs font-medium border-r border-[#F2F3F5] last:border-r-0 ${
                      i === 0 && weekOffset === 0 ? 'bg-[#1570EF]/5 text-[#1570EF]' : 'bg-[#F9FAFB] text-[#667085]'
                    }`}
                  >
                    {week.label}
                    {i === 0 && weekOffset === 0 && <div className="text-[10px]">This Week</div>}
                  </div>
                ))}
              </div>
            </div>

            {/* Timeline Rows */}
            {timelineData.resources.length === 0 ? (
              <div className="text-center py-12 text-[#667085]">No resources found</div>
            ) : (
              timelineData.resources.map((resource) => (
                <div key={resource.id} className="flex border-b border-[#F2F3F5] last:border-b-0 hover:bg-[#F9FAFB]/50">
                  <div className="w-48 shrink-0 px-4 py-3 border-r border-[#E6E8EC]">
                    <div className="font-medium text-sm text-[#0B1220] truncate">{resource.name}</div>
                    <div className="text-xs text-[#667085]">{resource.role}</div>
                  </div>
                  <div className="flex-1 flex overflow-x-auto">
                    {resource.weeklyAllocations.map((week, i) => (
                      <div
                        key={i}
                        className="flex-1 min-w-[80px] px-1 py-2 border-r border-[#F2F3F5] last:border-r-0 flex items-center justify-center"
                        title={week.allocations.map(a => `${a.project_name}: ${formatAllocation(a.percentage, resource.standard_capacity)}`).join('\n')}
                      >
                        {week.totalPct > 0 ? (
                          <div className="w-full">
                            <div
                              className={`h-6 rounded ${getTimelineBarColor(week.totalPct)} flex items-center justify-center text-xs font-semibold text-white`}
                              style={{ opacity: Math.min(week.totalPct / 100, 1) * 0.5 + 0.5 }}
                            >
                              {week.totalPct}%
                            </div>
                            <div className="text-[10px] text-[#667085] text-center mt-0.5 truncate">
                              {week.allocations.length} proj
                            </div>
                          </div>
                        ) : (
                          <div className="w-full h-6 rounded bg-[#F2F3F5]" />
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Timeline Legend */}
          <div className="flex items-center gap-6 mt-4 text-xs text-[#667085]">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-[#1570EF]" />
              <span>Available (&lt;80%)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-[#F4B740]" />
              <span>Near capacity (80-100%)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-[#EF4444]" />
              <span>Over-allocated (&gt;100%)</span>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* Create/Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent data-testid="allocation-dialog">
          <DialogHeader>
            <DialogTitle>
              {editingAllocation ? 'Edit Allocation' : 'Add New Allocation'}
            </DialogTitle>
            <DialogDescription>
              {editingAllocation ? 'Update allocation details' : 'Assign a resource to a project'}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4 mt-4">
            <div>
              <Label htmlFor="resource">Resource</Label>
              <Select
                value={formData.resource_id}
                onValueChange={(value) => setFormData({ ...formData, resource_id: value })}
              >
                <SelectTrigger id="resource" data-testid="allocation-resource-select">
                  <SelectValue placeholder="Select a resource" />
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

            <div>
              <Label htmlFor="project">Project</Label>
              <Select
                value={formData.project_id}
                onValueChange={(value) => setFormData({ ...formData, project_id: value })}
              >
                <SelectTrigger id="project" data-testid="allocation-project-select">
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
                  required
                  data-testid="allocation-start-date-input"
                />
              </div>
              <div>
                <Label htmlFor="end_date">End Date</Label>
                <Input
                  id="end_date"
                  type="date"
                  value={formData.end_date}
                  onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                  required
                  data-testid="allocation-end-date-input"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="percentage">Capacity Percentage</Label>
              <p className="text-xs text-[#667085] mb-2">
                % of this resource's weekly capacity dedicated to this project
              </p>
              <Input
                id="percentage"
                type="number"
                min="0"
                max="200"
                value={formData.percentage}
                onChange={(e) => setFormData({ ...formData, percentage: parseInt(e.target.value) || 0 })}
                required
                data-testid="allocation-percentage-input"
              />
            </div>

            <div className="flex justify-end gap-2 mt-6">
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
                disabled={createMutation.isPending || updateMutation.isPending}
                data-testid="submit-allocation"
              >
                {createMutation.isPending || updateMutation.isPending
                  ? 'Saving...'
                  : editingAllocation ? 'Update' : 'Create'}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Allocations;
