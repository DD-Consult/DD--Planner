import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { format } from 'date-fns';
import {
  getProjectWBS, createWBSTask, updateWBSTask, deleteWBSTask,
  getWBSActuals, cascadeTaskDates, syncProjectDatesFromWBS,
  setProjectWBSBaseline, setWBSTaskBaseline, getProjectCommentCounts,
} from '../api';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import {
  LayoutGrid, List, CalendarDays, Plus, Sparkles, Loader2,
  Edit2, Trash2, ChevronRight, ChevronDown, AlertTriangle,
  Clock, Users, ArrowRight, RefreshCw, TrendingUp, Flag, Diamond, MessageSquare,
} from 'lucide-react';
import { toast } from 'sonner';
import WBSTaskDialog from './WBSTaskDialog';
import AIWBSGenerator from './AIWBSGenerator';

// ============================================================
// Constants
// ============================================================
const STATUS_CONFIG = {
  todo: { label: 'To Do', className: 'bg-gray-100 text-gray-700 border-gray-200' },
  in_progress: { label: 'In Progress', className: 'bg-blue-100 text-blue-700 border-blue-200' },
  done: { label: 'Done', className: 'bg-green-100 text-green-700 border-green-200' },
  on_hold: { label: 'On Hold', className: 'bg-yellow-100 text-yellow-700 border-yellow-200' },
  blocked: { label: 'Blocked', className: 'bg-red-100 text-red-700 border-red-200' },
};

const PRIORITY_CONFIG = {
  low: { label: 'Low', className: 'bg-gray-100 text-gray-500' },
  medium: { label: 'Medium', className: 'bg-blue-100 text-blue-600' },
  high: { label: 'High', className: 'bg-orange-100 text-orange-600' },
  critical: { label: 'Critical', className: 'bg-red-100 text-red-700' },
};

const getActualsStatus = (estimated, actual) => {
  if (!actual || actual === 0) return 'none';
  if (!estimated || estimated === 0) return 'none';
  const ratio = actual / estimated;
  if (ratio > 1.0) return 'over';
  if (ratio > 0.8) return 'risk';
  return 'ok';
};

const isTaskDelayed = (task) => {
  if (!task.end_date) return false;
  if (task.status === 'done') return false;
  
  try {
    const endDate = new Date(task.end_date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    endDate.setHours(0, 0, 0, 0);
    return today > endDate;
  } catch {
    return false;
  }
};

const getDaysDelayed = (task) => {
  if (!isTaskDelayed(task)) return 0;
  
  try {
    const endDate = new Date(task.end_date);
    const today = new Date();
    const diffTime = Math.abs(today - endDate);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  } catch {
    return 0;
  }
};

// ---- Late-to-start (feature c) ----
// A task is "late to start" when it should already have begun (today is past
// its start_date) but it has not started yet (still in To Do).
const isLateToStart = (task) => {
  if (!task.start_date) return false;
  if (task.status === 'done' || task.status === 'in_progress') return false;
  if (task.status !== 'todo') return false; // exclude on_hold/blocked from "late start"
  try {
    const startDate = new Date(task.start_date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    startDate.setHours(0, 0, 0, 0);
    return today > startDate;
  } catch {
    return false;
  }
};

const getDaysLateToStart = (task) => {
  if (!isLateToStart(task)) return 0;
  try {
    const startDate = new Date(task.start_date);
    const today = new Date();
    const diffTime = Math.abs(today - startDate);
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  } catch {
    return 0;
  }
};

// ---- Baseline vs revised schedule (feature b) ----
const hasBaseline = (task) => Boolean(task.baseline_end_date || task.baseline_start_date);

// Slip in days between revised end_date and baseline_end_date.
// Positive = slipped later than plan; negative = pulled earlier (ahead).
const getScheduleSlipDays = (task) => {
  if (!task.end_date || !task.baseline_end_date) return 0;
  try {
    const end = new Date(task.end_date);
    const base = new Date(task.baseline_end_date);
    end.setHours(0, 0, 0, 0);
    base.setHours(0, 0, 0, 0);
    return Math.round((end - base) / (1000 * 60 * 60 * 24));
  } catch {
    return 0;
  }
};

const formatDate = (dateStr) => {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' });
  } catch {
    return dateStr;
  }
};

const getInitials = (name) => {
  if (!name) return '?';
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
};

// ============================================================
// TaskCard sub-component (Board view)
// ============================================================
const TaskCard = ({
  task,
  resources,
  onEdit,
  onDelete,
  getSubTasks,
  getTaskDependencies,
  commentCount = 0,
}) => {
  const subTasks = getSubTasks(task.id);
  const deps = getTaskDependencies(task);
  const assignee = task.assigned_to_name || (resources?.find(r => r.id === task.assigned_to)?.name);
  const statusCfg = STATUS_CONFIG[task.status] || STATUS_CONFIG.todo;
  const priorityCfg = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.medium;
  const hasActuals = task.actualHours > 0;
  const isMilestone = task.is_milestone;

  return (
    <div className={`border rounded-lg p-3 shadow-sm hover:shadow-md transition-shadow group ${isMilestone ? 'bg-purple-50 border-purple-200' : 'bg-white border-gray-200'}`}>
      {/* Priority + Status */}
      <div className="flex items-center justify-between mb-2">
        {isMilestone ? (
          <Badge className="text-xs border bg-purple-100 text-purple-700 border-purple-300 flex items-center gap-1">
            <Diamond size={10} className="fill-purple-500" />
            MILESTONE
          </Badge>
        ) : (
          <Badge className={`text-xs border ${priorityCfg.className}`}>{priorityCfg.label}</Badge>
        )}
        {isMilestone ? (
          <Badge className={`text-xs border ${task.milestone_completed ? 'bg-green-100 text-green-700 border-green-300' : 'bg-amber-100 text-amber-700 border-amber-300'}`}>
            {task.milestone_completed ? '✓ Complete' : '◯ Pending'}
          </Badge>
        ) : (
          <Badge className={`text-xs border ${statusCfg.className}`}>{statusCfg.label}</Badge>
        )}
      </div>

      {/* Task name */}
      <div className={`font-medium text-sm mb-1 line-clamp-2 ${isMilestone ? 'text-purple-900' : 'text-gray-900'}`}>{task.name}</div>

      {/* Description */}
      {task.description && (
        <div className="text-xs text-gray-500 mb-2 line-clamp-2">{task.description}</div>
      )}

      {/* Dates */}
      {isMilestone && task.milestone_date ? (
        <div className="flex items-center gap-1 text-xs text-purple-600 font-medium mb-2">
          <Diamond size={11} className="fill-purple-400" />
          <span>{formatDate(task.milestone_date)}</span>
        </div>
      ) : (task.start_date || task.end_date) && (
        <div className="flex items-center gap-1 text-xs text-gray-500 mb-2">
          <CalendarDays size={11} />
          <span>{formatDate(task.start_date)}</span>
          {task.end_date && <><ArrowRight size={10} /><span>{formatDate(task.end_date)}</span></>}
        </div>
      )}

      {/* Hours */}
      {(task.estimated_hours > 0 || hasActuals) && (
        <div className="text-xs text-gray-500 mb-2 flex items-center gap-1">
          <Clock size={11} />
          {hasActuals ? (
            <span className={task.actualHours > task.estimated_hours ? 'text-red-600 font-medium' : 'text-gray-500'}>
              {task.actualHours}h / {task.estimated_hours}h
            </span>
          ) : (
            <span>{task.estimated_hours}h estimated</span>
          )}
        </div>
      )}

      {/* Footer: assignee + meta */}
      <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-100">
        <div className="flex items-center gap-2">
          {assignee ? (
            <div className="w-6 h-6 rounded-full bg-[#1570EF] text-white text-xs flex items-center justify-center font-medium">
              {getInitials(assignee)}
            </div>
          ) : (
            <div className="w-6 h-6 rounded-full bg-gray-200 text-gray-500 text-xs flex items-center justify-center">
              ?
            </div>
          )}
          <span className="text-xs text-gray-500 truncate max-w-20">{assignee || 'Unassigned'}</span>
        </div>
        <div className="flex items-center gap-2">
          {commentCount > 0 && (
            <span className="text-xs text-blue-500 flex items-center gap-0.5" data-testid="comment-count-badge">
              <MessageSquare size={11} />
              {commentCount}
            </span>
          )}
          {deps.length > 0 && (
            <span className="text-xs text-gray-400">{deps.length} dep{deps.length !== 1 ? 's' : ''}</span>
          )}
          {subTasks.length > 0 && (
            <span className="text-xs text-gray-400">{subTasks.length} sub</span>
          )}
          {/* Edit/Delete (shown on hover) */}
          <div className="opacity-0 group-hover:opacity-100 flex gap-1">
            <button
              onClick={() => onEdit(task)}
              className="p-1 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700"
            >
              <Edit2 size={12} />
            </button>
            <button
              onClick={() => onDelete(task)}
              className="p-1 rounded hover:bg-red-50 text-gray-500 hover:text-red-600"
            >
              <Trash2 size={12} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================================
// Main WBSView component
// ============================================================
const WBSView = ({ projectId, project, phases, resources, readOnly = false, defaultView = 'board', currentUserEmail }) => {
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState(defaultView); // 'board' | 'list' | 'plan'
  const [showTaskDialog, setShowTaskDialog] = useState(false);
  const [editingTask, setEditingTask] = useState(null);
  const [showAIGenerator, setShowAIGenerator] = useState(false);
  const [expandedTasks, setExpandedTasks] = useState({});
  const [defaultPhase, setDefaultPhase] = useState(null);
  const [selectedTasks, setSelectedTasks] = useState([]); // For bulk operations
  const [showBulkActions, setShowBulkActions] = useState(false);

  // ---- Data fetching ----
  const { data: wbsData = [], isLoading } = useQuery({
    queryKey: ['wbs', projectId],
    queryFn: async () => {
      const response = await getProjectWBS(projectId);
      return response.data;
    },
    enabled: !!projectId,
  });

  const { data: wbsActuals = [] } = useQuery({
    queryKey: ['wbsActuals', projectId],
    queryFn: async () => {
      const response = await getWBSActuals(projectId);
      return response.data;
    },
    enabled: !!projectId,
  });

  // Fetch comment counts for all tasks
  const { data: commentCounts = {} } = useQuery({
    queryKey: ['projectCommentCounts', projectId],
    queryFn: async () => {
      const response = await getProjectCommentCounts(projectId);
      return response.data;
    },
    enabled: !!projectId,
  });

  // Normalize tasks array
  const tasks = useMemo(() =>
    Array.isArray(wbsData) ? wbsData : (wbsData?.tasks || []),
    [wbsData]
  );

  // Actuals map: task_id → actuals object
  const actualsMap = useMemo(() => {
    const map = {};
    wbsActuals.forEach(a => { map[a.task_id] = a; });
    return map;
  }, [wbsActuals]);

  // Tasks grouped by phase (for Board view) — MUST be at component level
  const tasksByPhase = useMemo(() => {
    const phaseNames = [
      ...(phases || []).map(p => typeof p === 'string' ? p : p.name),
      'Unassigned',
    ];
    const grouped = {};
    phaseNames.forEach(phaseName => { grouped[phaseName] = []; });
    const rootTasks = tasks.filter(t => !t.parent_id);
    rootTasks.forEach(task => {
      const key = task.phase_name || 'Unassigned';
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(task);
    });
    return grouped;
  }, [tasks, phases]);

  // Date-sorted tasks (for Plan view) — MUST be at component level
  const sortedTasksByDate = useMemo(() => {
    return [...tasks].sort((a, b) => {
      if (!a.start_date && !b.start_date) return (a.order || 0) - (b.order || 0);
      if (!a.start_date) return 1;
      if (!b.start_date) return -1;
      return new Date(a.start_date) - new Date(b.start_date);
    });
  }, [tasks]);

  // Delay metrics calculation — MUST be at component level
  const delayMetrics = useMemo(() => {
    const delayedTasks = tasks.filter(isTaskDelayed);
    const totalDaysDelayed = delayedTasks.reduce((sum, task) => sum + getDaysDelayed(task), 0);
    
    // Group by phase
    const byPhase = {};
    delayedTasks.forEach(task => {
      const phaseName = task.phase_name || 'Unassigned';
      if (!byPhase[phaseName]) {
        byPhase[phaseName] = { count: 0, totalDays: 0 };
      }
      byPhase[phaseName].count += 1;
      byPhase[phaseName].totalDays += getDaysDelayed(task);
    });

    // Late-to-start + baseline slip aggregates
    const lateStartTasks = tasks.filter(isLateToStart);
    const slippedTasks = tasks.filter(t => hasBaseline(t) && getScheduleSlipDays(t) > 0);
    const totalSlipDays = slippedTasks.reduce((sum, t) => sum + getScheduleSlipDays(t), 0);

    return {
      count: delayedTasks.length,
      totalDays: totalDaysDelayed,
      byPhase,
      tasks: delayedTasks,
      lateStartCount: lateStartTasks.length,
      lateStartDays: lateStartTasks.reduce((sum, t) => sum + getDaysLateToStart(t), 0),
      slippedCount: slippedTasks.length,
      slippedDays: totalSlipDays,
    };
  }, [tasks]);

  // ---- Helper functions ----
  const getSubTasks = (taskId) => tasks.filter(t => t.parent_id === taskId);
  const getTaskDependencies = (task) =>
    (task.dependencies || []).map(depId => tasks.find(t => t.id === depId)).filter(Boolean);
  const getTaskActuals = (taskId) => actualsMap[taskId] || { actual_hours: 0, timesheet_count: 0 };

  const toggleExpand = (taskId) => {
    setExpandedTasks(prev => ({ ...prev, [taskId]: !prev[taskId] }));
  };

  // Bulk selection handlers
  const toggleTaskSelection = (taskId) => {
    setSelectedTasks(prev => 
      prev.includes(taskId) ? prev.filter(id => id !== taskId) : [...prev, taskId]
    );
  };

  const selectAll = () => {
    setSelectedTasks(tasks.map(t => t.id));
  };

  const clearSelection = () => {
    setSelectedTasks([]);
  };

  // ---- Mutations ----
  const createMutation = useMutation({
    mutationFn: (data) => createWBSTask(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wbs', projectId] });
      toast.success('Task created');
      setShowTaskDialog(false);
      setEditingTask(null);
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to create task'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ taskId, data }) => updateWBSTask(taskId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wbs', projectId] });
      toast.success('Task updated');
      setShowTaskDialog(false);
      setEditingTask(null);
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to update task'),
  });

  const deleteMutation = useMutation({
    mutationFn: (taskId) => deleteWBSTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wbs', projectId] });
      toast.success('Task deleted');
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to delete task'),
  });

  const cascadeMutation = useMutation({
    mutationFn: ({ taskId, endDate }) => cascadeTaskDates(taskId, endDate),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['wbs', projectId] });
      toast.success(data.data?.message || 'Dates cascaded');
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to cascade dates'),
  });

  const syncDatesMutation = useMutation({
    mutationFn: () => syncProjectDatesFromWBS(projectId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      const changes = data.data?.changes || [];
      if (changes.length > 0) {
        toast.success(`${data.data?.message || 'Dates synced'}\nLatest WBS end: ${data.data?.latest_wbs_end_date}`, {
          duration: 5000,
        });
      } else {
        toast.info(data.data?.message || 'Dates already in sync');
      }
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to sync dates'),
  });

  const setBaselineMutation = useMutation({
    mutationFn: () => setProjectWBSBaseline(projectId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['wbs', projectId] });
      toast.success(data.data?.message || 'Baseline set for all tasks', { duration: 4000 });
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to set baseline'),
  });

  const handleSetBaselineAll = () => {
    if (!window.confirm(
      'Snapshot the current start/end dates of ALL WBS tasks as their baseline (planned) schedule?\n\n' +
      'This becomes the committed plan. Future date changes will be measured against it as "slip".'
    )) return;
    setBaselineMutation.mutate();
  };

  // Bulk operations
  const handleBulkStatusChange = async (newStatus) => {
    try {
      const promises = selectedTasks.map(taskId =>
        updateWBSTask(taskId, { status: newStatus })
      );
      await Promise.all(promises);
      queryClient.invalidateQueries({ queryKey: ['wbs', projectId] });
      toast.success(`Updated ${selectedTasks.length} task(s) to ${newStatus}`);
      clearSelection();
      setShowBulkActions(false);
    } catch (err) {
      toast.error('Failed to update tasks');
    }
  };

  const handleBulkDelete = async () => {
    if (!window.confirm(`Delete ${selectedTasks.length} selected task(s)? This action cannot be undone.`)) {
      return;
    }
    
    try {
      const promises = selectedTasks.map(taskId => deleteWBSTask(taskId));
      await Promise.all(promises);
      queryClient.invalidateQueries({ queryKey: ['wbs', projectId] });
      toast.success(`Deleted ${selectedTasks.length} task(s)`);
      clearSelection();
      setShowBulkActions(false);
    } catch (err) {
      toast.error('Failed to delete tasks');
    }
  };

  const handleBulkAssign = async (resourceId) => {
    try {
      const promises = selectedTasks.map(taskId =>
        updateWBSTask(taskId, { assigned_to: resourceId })
      );
      await Promise.all(promises);
      queryClient.invalidateQueries({ queryKey: ['wbs', projectId] });
      const resource = resources?.find(r => r.id === resourceId);
      toast.success(`Assigned ${selectedTasks.length} task(s) to ${resource?.name || 'resource'}`);
      clearSelection();
      setShowBulkActions(false);
    } catch (err) {
      toast.error('Failed to assign tasks');
    }
  };

  const handleTaskSubmit = async (data) => {
    if (editingTask) {
      updateMutation.mutate({ taskId: editingTask.id, data });
    } else {
      createMutation.mutate(data);
    }
  };

  const handleEdit = (task) => {
    setEditingTask(task);
    setShowTaskDialog(true);
  };

  const handleDelete = (task) => {
    if (window.confirm(`Delete "${task.name}"${getSubTasks(task.id).length > 0 ? ' and all its sub-tasks' : ''}?`)) {
      deleteMutation.mutate(task.id);
    }
  };

  const handleAddInPhase = (phaseName) => {
    setDefaultPhase(phaseName);
    setEditingTask(null);
    setShowTaskDialog(true);
  };

  // ============================================================
  // Board View
  // ============================================================
  const renderBoardView = () => {
    const columns = [
      ...(phases || []).map(p => ({ name: typeof p === 'string' ? p : p.name })),
      { name: 'Unassigned' },
    ];

    return (
      <div className="flex gap-4 overflow-x-auto pb-4">
        {columns.map(col => {
          const colTasks = tasksByPhase[col.name] || [];
          return (
            <div key={col.name} className="flex-shrink-0 w-72">
              {/* Column header */}
              <div className="flex items-center justify-between mb-3 px-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm text-gray-700">{col.name}</span>
                  <Badge variant="outline" className="text-xs">{colTasks.length}</Badge>
                </div>
                <button
                  onClick={() => handleAddInPhase(col.name === 'Unassigned' ? null : col.name)}
                  className={`p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 ${readOnly ? 'hidden' : ''}`}
                >
                  <Plus size={14} />
                </button>
              </div>

              {/* Cards */}
              <div className="space-y-2 min-h-16">
                {colTasks.map(task => (
                  <TaskCard
                    key={task.id}
                    task={{ ...task, actualHours: getTaskActuals(task.id).actual_hours }}
                    resources={resources}
                    onEdit={handleEdit}
                    onDelete={handleDelete}
                    getSubTasks={getSubTasks}
                    getTaskDependencies={getTaskDependencies}
                    commentCount={commentCounts[task.id] || 0}
                  />
                ))}
                {colTasks.length === 0 && (
                  <div className="border-2 border-dashed border-gray-200 rounded-lg p-4 text-center text-xs text-gray-400">
                    No tasks
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  // ============================================================
  // List View (tree table)
  // ============================================================
  const renderTaskRows = (taskList, level = 0) => {
    return taskList.map(task => {
      const subTasks = getSubTasks(task.id);
      const isExpanded = expandedTasks[task.id];
      const hasChildren = subTasks.length > 0;
      const statusCfg = STATUS_CONFIG[task.status] || STATUS_CONFIG.todo;
      const priorityCfg = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.medium;
      const assignee = task.assigned_to_name || resources?.find(r => r.id === task.assigned_to)?.name;
      const isMilestone = task.is_milestone;

      return (
        <React.Fragment key={task.id}>
          <tr className={`border-b border-gray-100 hover:bg-gray-50 group ${isMilestone ? 'bg-purple-50/30' : ''}`}>
            <td className="py-2.5 px-4">
              <div className="flex items-center gap-2" style={{ paddingLeft: level * 20 }}>
                {isMilestone && (
                  <Flag size={16} className="text-purple-600 shrink-0" />
                )}
                {!isMilestone && hasChildren ? (
                  <button
                    onClick={() => toggleExpand(task.id)}
                    className="mr-1.5 p-0.5 rounded hover:bg-gray-200 text-gray-500"
                  >
                    {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  </button>
                ) : !isMilestone ? (
                  <span className="mr-1.5 w-5" />
                ) : null}
                <span className={`text-sm ${isMilestone ? 'font-semibold text-purple-900' : level > 0 ? 'text-gray-600' : 'font-medium text-gray-900'}`}>
                  {task.name}
                </span>
                {isMilestone && (
                  <Badge variant="outline" className="text-xs bg-purple-100 text-purple-700 border-purple-300">
                    MILESTONE
                  </Badge>
                )}
                {hasChildren && !isMilestone && (
                  <span className="ml-2 text-xs text-gray-400">({subTasks.length})</span>
                )}
                {(commentCounts[task.id] || 0) > 0 && (
                  <span className="ml-2 text-xs text-blue-500 flex items-center gap-0.5" data-testid="list-comment-badge">
                    <MessageSquare size={11} />
                    {commentCounts[task.id]}
                  </span>
                )}
              </div>
            </td>
            <td className="py-2.5 px-3 text-xs text-gray-500">
              {task.phase_name || '—'}
            </td>
            <td className="py-2.5 px-3">
              {isMilestone ? (
                <span className="text-xs text-purple-600 font-medium">
                  {task.milestone_date ? format(new Date(task.milestone_date), 'MMM d, yyyy') : '—'}
                </span>
              ) : assignee ? (
                <div className="flex items-center gap-1.5">
                  <div className="w-5 h-5 rounded-full bg-[#1570EF] text-white text-xs flex items-center justify-center font-medium">
                    {getInitials(assignee)}
                  </div>
                  <span className="text-xs text-gray-600">{assignee}</span>
                </div>
              ) : (
                <span className="text-xs text-gray-400">Unassigned</span>
              )}
            </td>
            <td className="py-2.5 px-3">
              {isMilestone ? (
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={task.milestone_completed || false}
                    onChange={async () => {
                      try {
                        await fetch(`/api/wbs/tasks/${task.id}/complete-milestone?completed=${!task.milestone_completed}`, {
                          method: 'PATCH',
                          headers: {
                            'Authorization': `Bearer ${localStorage.getItem('token')}`
                          }
                        });
                        queryClient.invalidateQueries(['wbs', projectId]);
                        toast.success(task.milestone_completed ? 'Milestone reopened' : 'Milestone completed!');
                      } catch (err) {
                        toast.error('Failed to update milestone');
                      }
                    }}
                    className="w-4 h-4 text-purple-600 rounded border-purple-300 focus:ring-purple-500"
                  />
                  <span className="text-xs text-gray-600">
                    {task.milestone_completed ? 'Complete' : 'Pending'}
                  </span>
                </label>
              ) : (
                <Badge className={`text-xs border ${statusCfg.className}`}>{statusCfg.label}</Badge>
              )}
            </td>
            <td className="py-2.5 px-3">
              {!isMilestone && (
                <Badge className={`text-xs ${priorityCfg.className}`}>{priorityCfg.label}</Badge>
              )}
            </td>
            <td className="py-2.5 px-3 text-xs text-gray-600 text-right">
              {isMilestone ? (
                <span className="text-purple-600 font-medium">◆ 0h</span>
              ) : task.estimated_hours > 0 ? (
                `${task.estimated_hours}h`
              ) : (
                '—'
              )}
            </td>
            <td className="py-2.5 px-3">
              <div className="opacity-0 group-hover:opacity-100 flex gap-1.5">
                <button
                  onClick={() => handleEdit(task)}
                  className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700"
                >
                  <Edit2 size={12} />
                </button>
                <button
                  onClick={() => handleDelete(task)}
                  className="p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-600"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </td>
          </tr>
          {hasChildren && isExpanded && renderTaskRows(subTasks, level + 1)}
        </React.Fragment>
      );
    });
  };

  const renderListView = () => {
    const rootTasks = tasks.filter(t => !t.parent_id);
    return (
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full text-left">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="py-2.5 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">Task Name</th>
              <th className="py-2.5 px-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Phase</th>
              <th className="py-2.5 px-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Assigned To</th>
              <th className="py-2.5 px-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Status</th>
              <th className="py-2.5 px-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Priority</th>
              <th className="py-2.5 px-3 text-xs font-medium text-gray-500 uppercase tracking-wide text-right">Est. Hours</th>
              <th className="py-2.5 px-3 w-20"></th>
            </tr>
          </thead>
          <tbody>
            {rootTasks.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-12 text-center text-gray-400 text-sm">
                  No tasks yet
                </td>
              </tr>
            ) : (
              renderTaskRows(rootTasks)
            )}
          </tbody>
        </table>
      </div>
    );
  };

  // ============================================================
  // Plan View (date-sorted table with actuals)
  // ============================================================
  const renderPlanView = () => {
    return (
      <div className="border border-gray-200 rounded-lg overflow-hidden overflow-x-auto">
        <table className="w-full text-left min-w-max">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {!readOnly && (
                <th className="py-2.5 px-3 w-10">
                  <input
                    type="checkbox"
                    checked={selectedTasks.length === tasks.length && tasks.length > 0}
                    onChange={(e) => e.target.checked ? selectAll() : clearSelection()}
                    className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                  />
                </th>
              )}
              <th className="py-2.5 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide min-w-48">Task</th>
              <th className="py-2.5 px-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Phase</th>
              <th className="py-2.5 px-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Assignee</th>
              <th className="py-2.5 px-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Start</th>
              <th className="py-2.5 px-3 text-xs font-medium text-gray-500 uppercase tracking-wide">End</th>
              <th className="py-2.5 px-3 text-xs font-medium text-gray-500 uppercase tracking-wide text-right">Duration</th>
              <th className="py-2.5 px-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Status</th>
              <th className="py-2.5 px-3 text-xs font-medium text-gray-500 uppercase tracking-wide min-w-40">Actuals vs Est.</th>
              <th className="py-2.5 px-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Deps</th>
              <th className="py-2.5 px-3 w-24"></th>
            </tr>
          </thead>
          <tbody>
            {sortedTasksByDate.length === 0 ? (
              <tr>
                <td colSpan={readOnly ? 10 : 11} className="py-12 text-center text-gray-400 text-sm">
                  No tasks yet
                </td>
              </tr>
            ) : (
              sortedTasksByDate.map(task => {
                const actuals = getTaskActuals(task.id);
                const actualsStatus = getActualsStatus(task.estimated_hours, actuals.actual_hours);
                const assignee = task.assigned_to_name || resources?.find(r => r.id === task.assigned_to)?.name;
                const statusCfg = STATUS_CONFIG[task.status] || STATUS_CONFIG.todo;
                const isSubTask = !!task.parent_id;

                const durationDays = task.start_date && task.end_date
                  ? Math.round((new Date(task.end_date) - new Date(task.start_date)) / (1000 * 60 * 60 * 24)) + 1
                  : null;

                const deps = getTaskDependencies(task);
                const hasDependents = tasks.some(t => (t.dependencies || []).includes(task.id));

                // Progress bar
                const progressPct = task.estimated_hours > 0
                  ? Math.min(100, Math.round((actuals.actual_hours / task.estimated_hours) * 100))
                  : 0;
                const progressColor = actualsStatus === 'over' ? 'bg-red-500'
                  : actualsStatus === 'risk' ? 'bg-yellow-500' : 'bg-green-500';

                return (
                  <tr
                    key={task.id}
                    className={`border-b border-gray-100 hover:bg-gray-50 group ${isSubTask ? 'bg-gray-50/50' : ''}`}
                  >
                    {!readOnly && (
                      <td className="py-2.5 px-3">
                        <input
                          type="checkbox"
                          checked={selectedTasks.includes(task.id)}
                          onChange={() => toggleTaskSelection(task.id)}
                          className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                        />
                      </td>
                    )}
                    <td className="py-2.5 px-4">
                      <div className="flex items-center gap-2">
                        {isSubTask && <span className="text-gray-300 text-xs pl-2">↳</span>}
                        <span className={`text-sm ${isSubTask ? 'text-gray-600' : 'font-medium text-gray-900'}`}>
                          {task.name}
                        </span>
                        {isTaskDelayed(task) && (
                          <Badge className="bg-red-100 text-red-700 border-red-200 text-xs flex items-center gap-1 ml-2">
                            <AlertTriangle size={10} />
                            DELAYED {getDaysDelayed(task)}d
                          </Badge>
                        )}
                        {isLateToStart(task) && (
                          <Badge className="bg-amber-100 text-amber-700 border-amber-200 text-xs flex items-center gap-1 ml-2">
                            <Clock size={10} />
                            LATE START {getDaysLateToStart(task)}d
                          </Badge>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-xs text-gray-500">{task.phase_name || '—'}</td>
                    <td className="py-2.5 px-3">
                      {assignee ? (
                        <div className="flex items-center gap-1">
                          <div className="w-5 h-5 rounded-full bg-[#1570EF] text-white text-xs flex items-center justify-center">
                            {getInitials(assignee)}
                          </div>
                          <span className="text-xs text-gray-600 max-w-20 truncate">{assignee}</span>
                        </div>
                      ) : (
                        <span className="text-xs text-gray-400">—</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-xs text-gray-600">{formatDate(task.start_date)}</td>
                    <td className="py-2.5 px-3 text-xs text-gray-600">
                      <div className="flex flex-col">
                        <span>{formatDate(task.end_date)}</span>
                        {hasBaseline(task) && getScheduleSlipDays(task) !== 0 && (
                          <span className="flex items-center gap-1 text-[10px] mt-0.5">
                            <span className="text-gray-400 line-through">{formatDate(task.baseline_end_date)}</span>
                            {getScheduleSlipDays(task) > 0 ? (
                              <span className="text-red-600 font-medium">+{getScheduleSlipDays(task)}d slip</span>
                            ) : (
                              <span className="text-green-600 font-medium">{getScheduleSlipDays(task)}d ahead</span>
                            )}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-xs text-gray-600 text-right">
                      {durationDays ? `${durationDays}d` : '—'}
                    </td>
                    <td className="py-2.5 px-3">
                      <Badge className={`text-xs border ${statusCfg.className}`}>{statusCfg.label}</Badge>
                    </td>
                    <td className="py-2.5 px-3">
                      {task.estimated_hours > 0 ? (
                        <div className="space-y-1 min-w-36">
                          <div className="flex items-center justify-between">
                            <span className={`text-xs font-medium ${
                              actualsStatus === 'over' ? 'text-red-600' :
                              actualsStatus === 'risk' ? 'text-yellow-600' :
                              actuals.actual_hours > 0 ? 'text-green-600' : 'text-gray-400'
                            }`}>
                              {actuals.actual_hours}h / {task.estimated_hours}h
                            </span>
                            {actualsStatus === 'over' && (
                              <span className="text-xs font-medium text-red-600">🔴 Over</span>
                            )}
                            {actualsStatus === 'risk' && (
                              <span className="text-xs font-medium text-yellow-600">🟡 At Risk</span>
                            )}
                            {actualsStatus === 'ok' && (
                              <span className="text-xs font-medium text-green-600">🟢 OK</span>
                            )}
                          </div>
                          {actuals.actual_hours > 0 && (
                            <div className="w-full bg-gray-200 rounded-full h-1.5">
                              <div
                                className={`h-1.5 rounded-full ${progressColor} transition-all`}
                                style={{ width: `${Math.min(progressPct, 100)}%` }}
                              />
                            </div>
                          )}
                          {actuals.timesheet_count > 0 && (
                            <div className="text-xs text-gray-400">
                              {actuals.timesheet_count} timesheet{actuals.timesheet_count !== 1 ? 's' : ''}
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs text-gray-400">—</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3">
                      {deps.length > 0 ? (
                        <div className="text-xs text-gray-500">
                          {deps.length} dep{deps.length !== 1 ? 's' : ''}
                        </div>
                      ) : <span className="text-xs text-gray-300">—</span>}
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-1">
                        {hasDependents && task.end_date && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-6 px-2 text-xs"
                            disabled={cascadeMutation.isPending}
                            onClick={() => cascadeMutation.mutate({ taskId: task.id, endDate: task.end_date })}
                          >
                            Cascade
                          </Button>
                        )}
                        <div className="opacity-0 group-hover:opacity-100 flex gap-1">
                          <button onClick={() => handleEdit(task)} className="p-1 rounded hover:bg-gray-100 text-gray-400">
                            <Edit2 size={11} />
                          </button>
                          <button onClick={() => handleDelete(task)} className="p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-600">
                            <Trash2 size={11} />
                          </button>
                        </div>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    );
  };

  // ============================================================
  // Main render
  // ============================================================
  const isDialogLoading = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold">Work Breakdown Structure</h3>
          {tasks.length > 0 && (
            <Badge variant="outline" className="text-xs">{tasks.length} tasks</Badge>
          )}
          {delayMetrics.count > 0 && (
            <Badge className="bg-red-100 text-red-700 border-red-200 text-xs flex items-center gap-1">
              <AlertTriangle size={12} />
              {delayMetrics.count} delayed ({delayMetrics.totalDays}d)
            </Badge>
          )}
          {delayMetrics.lateStartCount > 0 && (
            <Badge className="bg-amber-100 text-amber-700 border-amber-200 text-xs flex items-center gap-1">
              <Clock size={12} />
              {delayMetrics.lateStartCount} late to start ({delayMetrics.lateStartDays}d)
            </Badge>
          )}
          {delayMetrics.slippedCount > 0 && (
            <Badge className="bg-orange-100 text-orange-700 border-orange-200 text-xs flex items-center gap-1">
              <TrendingUp size={12} />
              {delayMetrics.slippedCount} slipped ({delayMetrics.slippedDays}d)
            </Badge>
          )}
          {selectedTasks.length > 0 && (
            <Badge className="bg-blue-100 text-blue-700 border-blue-200 text-xs">
              {selectedTasks.length} selected
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* View Switcher */}
          {!readOnly && (
          <div className="flex items-center border border-gray-200 rounded-lg p-0.5" data-testid="view-switcher">
            <button
              data-testid="view-mode-board"
              onClick={() => setViewMode('board')}
              className={`px-3 py-1.5 rounded text-xs font-medium flex items-center gap-1 transition-colors ${viewMode === 'board' ? 'bg-[#1570EF] text-white' : 'text-gray-500 hover:text-gray-700'}`}
              title="Board view"
            >
              <LayoutGrid size={13} />
              <span className="hidden sm:inline">Board</span>
            </button>
            <button
              data-testid="view-mode-list"
              onClick={() => setViewMode('list')}
              className={`px-3 py-1.5 rounded text-xs font-medium flex items-center gap-1 transition-colors ${viewMode === 'list' ? 'bg-[#1570EF] text-white' : 'text-gray-500 hover:text-gray-700'}`}
              title="List view"
            >
              <List size={13} />
              <span className="hidden sm:inline">List</span>
            </button>
            <button
              data-testid="view-mode-plan"
              onClick={() => setViewMode('plan')}
              className={`px-3 py-1.5 rounded text-xs font-medium flex items-center gap-1 transition-colors ${viewMode === 'plan' ? 'bg-[#1570EF] text-white' : 'text-gray-500 hover:text-gray-700'}`}
              title="Plan view"
            >
              <CalendarDays size={13} />
              <span className="hidden sm:inline">Plan</span>
            </button>
          </div>
          )}

          {/* Bulk Actions */}
          {!readOnly && selectedTasks.length > 0 && (
            <>
              <div className="h-6 w-px bg-gray-300" />
              <div className="flex items-center gap-2">
                <Select onValueChange={handleBulkStatusChange}>
                  <SelectTrigger className="h-8 text-xs w-32">
                    <SelectValue placeholder="Change Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="todo">To Do</SelectItem>
                    <SelectItem value="in_progress">In Progress</SelectItem>
                    <SelectItem value="done">Done</SelectItem>
                    <SelectItem value="on_hold">On Hold</SelectItem>
                    <SelectItem value="blocked">Blocked</SelectItem>
                  </SelectContent>
                </Select>
                
                <Select onValueChange={handleBulkAssign}>
                  <SelectTrigger className="h-8 text-xs w-32">
                    <SelectValue placeholder="Assign To" />
                  </SelectTrigger>
                  <SelectContent>
                    {resources?.map(resource => (
                      <SelectItem key={resource.id} value={resource.id}>
                        {resource.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                
                <Button
                  onClick={handleBulkDelete}
                  size="sm"
                  variant="outline"
                  className="h-8 text-xs text-red-600 border-red-200 hover:bg-red-50"
                >
                  <Trash2 size={12} className="mr-1" />
                  Delete
                </Button>
                
                <Button
                  onClick={clearSelection}
                  size="sm"
                  variant="ghost"
                  className="h-8 text-xs"
                >
                  Clear
                </Button>
              </div>
              <div className="h-6 w-px bg-gray-300" />
            </>
          )}

          {!readOnly && tasks.length > 0 && (
          <Button
            onClick={() => syncDatesMutation.mutate()}
            size="sm"
            variant="outline"
            disabled={syncDatesMutation.isPending}
            className="text-sm"
            title="Sync project end date from latest WBS task"
          >
            {syncDatesMutation.isPending ? (
              <Loader2 size={14} className="mr-1.5 animate-spin" />
            ) : (
              <RefreshCw size={14} className="mr-1.5" />
            )}
            Sync Dates from WBS
          </Button>
          )}

          {!readOnly && tasks.length > 0 && (
          <Button
            onClick={handleSetBaselineAll}
            size="sm"
            variant="outline"
            disabled={setBaselineMutation.isPending}
            className="text-sm"
            title="Snapshot current dates of all tasks as the committed baseline"
          >
            {setBaselineMutation.isPending ? (
              <Loader2 size={14} className="mr-1.5 animate-spin" />
            ) : (
              <Flag size={14} className="mr-1.5" />
            )}
            Set Baseline
          </Button>
          )}
          
          {!readOnly && (
          <Button
            onClick={() => { setEditingTask(null); setDefaultPhase(null); setShowTaskDialog(true); }}
            size="sm"
            variant="outline"
            className="text-sm"
          >
            <Plus size={14} className="mr-1.5" />
            Add Task
          </Button>
          )}
          {!readOnly && (
          <Button
            onClick={() => setShowAIGenerator(true)}
            size="sm"
            className="bg-[#1570EF] hover:bg-[#1570EF]/90 text-white text-sm"
          >
            <Sparkles size={14} className="mr-1.5" />
            Generate with AI
          </Button>
          )}
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 size={24} className="animate-spin text-[#1570EF]" />
        </div>
      )}

      {/* Empty State */}
      {!isLoading && tasks.length === 0 && (
        <div className="border-2 border-dashed border-gray-200 rounded-lg p-12 text-center">
          <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
            <List size={24} className="text-gray-400" />
          </div>
          <h4 className="font-medium text-gray-700 mb-1">No tasks yet</h4>
          <p className="text-sm text-gray-500 mb-6">
            Start building your Work Breakdown Structure manually or use AI to generate one.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Button
              variant="outline"
              onClick={() => { setEditingTask(null); setShowTaskDialog(true); }}
            >
              <Plus size={14} className="mr-2" />
              Add Task manually
            </Button>
            <Button
              onClick={() => setShowAIGenerator(true)}
              className="bg-[#1570EF] hover:bg-[#1570EF]/90 text-white"
            >
              <Sparkles size={14} className="mr-2" />
              Generate with AI
            </Button>
          </div>
        </div>
      )}

      {/* Views */}
      {!isLoading && tasks.length > 0 && (
        <>
          {viewMode === 'board' && <div data-testid="wbs-board-view">{renderBoardView()}</div>}
          {viewMode === 'list' && <div data-testid="wbs-list-view">{renderListView()}</div>}
          {viewMode === 'plan' && <div data-testid="wbs-plan-view">{renderPlanView()}</div>}
        </>
      )}

      {/* Task Dialog */}
      <WBSTaskDialog
        open={showTaskDialog}
        onClose={() => { setShowTaskDialog(false); setEditingTask(null); }}
        task={editingTask}
        projectId={projectId}
        phases={phases}
        resources={resources}
        tasks={tasks}
        onSubmit={handleTaskSubmit}
        isLoading={isDialogLoading}
        onBaselineSet={() => queryClient.invalidateQueries({ queryKey: ['wbs', projectId] })}
        currentUserEmail={currentUserEmail}
      />

      {/* AI Generator */}
      <AIWBSGenerator
        open={showAIGenerator}
        onClose={() => setShowAIGenerator(false)}
        projectId={projectId}
        project={project}
        phases={phases}
        resources={resources}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ['wbs', projectId] });
        }}
      />
    </div>
  );
};

export default WBSView;
