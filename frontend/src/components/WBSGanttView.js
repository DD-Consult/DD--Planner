import React, { useState, useMemo, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { parseISO, differenceInCalendarDays, addDays, format, isValid } from 'date-fns';
import { getCriticalPath } from '../api';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Button } from './ui/button';
import { AlertTriangle } from 'lucide-react';

// ============================================================
// WBSGanttView Component
// ============================================================
const WBSGanttView = ({ projectId, tasks, resources, readOnly, onReschedule }) => {
  const [dragState, setDragState] = useState(null);
  const [showRescheduleDialog, setShowRescheduleDialog] = useState(false);
  const [rescheduleData, setRescheduleData] = useState(null);
  const timelineRef = useRef(null);

  // ---- Fetch critical path ----
  const { data: cp = { critical_task_ids: [], project_duration_days: 0, task_slack: {} } } = useQuery({
    queryKey: ['wbsCriticalPath', projectId],
    queryFn: async () => (await getCriticalPath(projectId)).data,
    enabled: !!projectId,
  });

  // ---- Filter dated tasks ----
  const datedTasks = useMemo(() => {
    return tasks.filter(t => {
      if (!t.start_date || !t.end_date) return false;
      const start = parseISO(t.start_date);
      const end = parseISO(t.end_date);
      return isValid(start) && isValid(end);
    });
  }, [tasks]);

  const undatedCount = tasks.length - datedTasks.length;

  // ---- Sort tasks by phase, then start_date ----
  const sortedTasks = useMemo(() => {
    const sorted = [...datedTasks];
    sorted.sort((a, b) => {
      // First by phase
      const phaseA = a.phase_name || 'Unassigned';
      const phaseB = b.phase_name || 'Unassigned';
      if (phaseA !== phaseB) return phaseA.localeCompare(phaseB);
      // Then by start_date
      const dateA = parseISO(a.start_date);
      const dateB = parseISO(b.start_date);
      return dateA - dateB;
    });
    return sorted;
  }, [datedTasks]);

  // ---- Calculate timeline window ----
  const { minDate, maxDate, pxPerDay, timelineWidthPx } = useMemo(() => {
    if (sortedTasks.length === 0) {
      return { minDate: new Date(), maxDate: new Date(), pxPerDay: 24, timelineWidthPx: 0 };
    }

    let min = parseISO(sortedTasks[0].start_date);
    let max = parseISO(sortedTasks[0].end_date);

    sortedTasks.forEach(t => {
      const start = parseISO(t.start_date);
      const end = parseISO(t.end_date);
      if (start < min) min = start;
      if (end > max) max = end;
    });

    // Pad a few days on each side
    min = addDays(min, -3);
    max = addDays(max, 3);

    const totalDays = differenceInCalendarDays(max, min);
    const px = 24; // pixels per day
    const width = totalDays * px;

    return { minDate: min, maxDate: max, pxPerDay: px, timelineWidthPx: width };
  }, [sortedTasks]);

  // ---- Calculate bar positions ----
  const taskBars = useMemo(() => {
    return sortedTasks.map((task, idx) => {
      const start = parseISO(task.start_date);
      const end = parseISO(task.end_date);
      const daysFromStart = differenceInCalendarDays(start, minDate);
      const duration = differenceInCalendarDays(end, start) + 1;
      const left = daysFromStart * pxPerDay;
      const width = Math.max(duration * pxPerDay, pxPerDay);
      const isCritical = cp.critical_task_ids.includes(task.id);
      return { task, idx, left, width, isCritical };
    });
  }, [sortedTasks, minDate, pxPerDay, cp.critical_task_ids]);

  // ---- Generate date ticks (weekly) ----
  const dateTicks = useMemo(() => {
    const ticks = [];
    let current = new Date(minDate);
    while (current <= maxDate) {
      const daysFromStart = differenceInCalendarDays(current, minDate);
      const left = daysFromStart * pxPerDay;
      ticks.push({ date: current, left, label: format(current, 'MMM d') });
      current = addDays(current, 7);
    }
    return ticks;
  }, [minDate, maxDate, pxPerDay]);

  // ---- Dependency arrows ----
  const arrows = useMemo(() => {
    const arrowList = [];
    const taskMap = {};
    taskBars.forEach(bar => { taskMap[bar.task.id] = bar; });

    taskBars.forEach(bar => {
      const deps = bar.task.dependencies || [];
      const depLinks = bar.task.dependency_links || [];
      const allPreds = [...deps];
      depLinks.forEach(link => {
        if (link.predecessor_id && !allPreds.includes(link.predecessor_id)) {
          allPreds.push(link.predecessor_id);
        }
      });

      allPreds.forEach(predId => {
        const predBar = taskMap[predId];
        if (!predBar) return; // Skip if predecessor not in dated set

        // Simple L-shaped arrow: from pred bar's right to task bar's left
        const x1 = predBar.left + predBar.width;
        const y1 = predBar.idx * 40 + 20; // center of bar (bar height ~40px including padding)
        const x2 = bar.left;
        const y2 = bar.idx * 40 + 20;

        arrowList.push({ x1, y1, x2, y2, key: `${predId}-${bar.task.id}` });
      });
    });

    return arrowList;
  }, [taskBars]);

  // ---- Drag handlers ----
  const handlePointerDown = (e, bar) => {
    if (readOnly) return;
    e.preventDefault();
    e.stopPropagation();
    const startX = e.clientX;
    const originalLeft = bar.left;
    setDragState({ bar, startX, originalLeft, currentDelta: 0 });
  };

  const handlePointerMove = (e) => {
    if (!dragState) return;
    const dx = e.clientX - dragState.startX;
    const dayDelta = Math.round(dx / pxPerDay);
    setDragState({ ...dragState, currentDelta: dayDelta });
  };

  const handlePointerUp = () => {
    if (!dragState) return;
    const { bar, currentDelta } = dragState;
    setDragState(null);

    if (currentDelta === 0) return;

    // Calculate new dates
    const oldStart = parseISO(bar.task.start_date);
    const oldEnd = parseISO(bar.task.end_date);
    const newStart = addDays(oldStart, currentDelta);
    const newEnd = addDays(oldEnd, currentDelta);

    // Show confirmation dialog
    setRescheduleData({
      task: bar.task,
      oldStart: format(oldStart, 'MMM d, yyyy'),
      oldEnd: format(oldEnd, 'MMM d, yyyy'),
      newStart: format(newStart, 'yyyy-MM-dd'),
      newEnd: format(newEnd, 'yyyy-MM-dd'),
      newStartDisplay: format(newStart, 'MMM d, yyyy'),
      newEndDisplay: format(newEnd, 'MMM d, yyyy'),
    });
    setShowRescheduleDialog(true);
  };

  const handleRescheduleConfirm = () => {
    if (!rescheduleData) return;
    onReschedule(rescheduleData.task, rescheduleData.newStart, rescheduleData.newEnd);
    setShowRescheduleDialog(false);
    setRescheduleData(null);
  };

  const handleRescheduleCancel = () => {
    setShowRescheduleDialog(false);
    setRescheduleData(null);
  };

  // ---- Handle pointer events globally when dragging ----
  React.useEffect(() => {
    if (dragState) {
      document.addEventListener('pointermove', handlePointerMove);
      document.addEventListener('pointerup', handlePointerUp);
      return () => {
        document.removeEventListener('pointermove', handlePointerMove);
        document.removeEventListener('pointerup', handlePointerUp);
      };
    }
  }, [dragState]);

  // ============================================================
  // Render
  // ============================================================
  if (sortedTasks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 px-4 text-gray-500">
        <AlertTriangle className="w-12 h-12 mb-4 text-gray-400" />
        <p className="text-sm">No scheduled tasks to display on the Gantt.</p>
        <p className="text-xs mt-1">Add start/end dates to see the timeline.</p>
      </div>
    );
  }

  const rowHeight = 40;
  const svgHeight = taskBars.length * rowHeight;

  return (
    <div className="flex flex-col gap-4 py-4">
      {/* Header */}
      <div className="flex items-center justify-between px-4">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-red-500" />
            <span className="text-xs text-gray-600">Critical path</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-[#1570EF]" />
            <span className="text-xs text-gray-600">On track</span>
          </div>
        </div>
        {cp.project_duration_days > 0 && (
          <div className="text-xs text-gray-600">
            <span className="font-medium" data-testid="gantt-project-duration">
              Project duration: {cp.project_duration_days} business days
            </span>
          </div>
        )}
      </div>

      {undatedCount > 0 && (
        <div className="px-4">
          <p className="text-xs text-yellow-600">
            {undatedCount} task{undatedCount > 1 ? 's have' : ' has'} no dates and {undatedCount > 1 ? 'are' : 'is'} hidden from the Gantt view.
          </p>
        </div>
      )}

      {/* Gantt Chart */}
      <div className="flex border border-gray-200 rounded-lg overflow-hidden">
        {/* Left column: Task names */}
        <div className="flex-shrink-0 w-64 bg-gray-50 border-r border-gray-200 overflow-y-auto">
          <div className="sticky top-0 bg-gray-100 border-b border-gray-200 px-3 py-2 text-xs font-semibold text-gray-700">
            Task
          </div>
          {taskBars.map(bar => (
            <div
              key={bar.task.id}
              className="px-3 py-2 border-b border-gray-200 text-xs truncate"
              style={{ height: rowHeight }}
              title={`${bar.task.name} (${bar.task.phase_name || 'Unassigned'})`}
            >
              <div className="font-medium text-gray-800 truncate">{bar.task.name}</div>
              <div className="text-gray-500 text-[10px] truncate">{bar.task.phase_name || 'Unassigned'}</div>
            </div>
          ))}
        </div>

        {/* Timeline area */}
        <div className="flex-1 overflow-x-auto" ref={timelineRef}>
          <div style={{ width: timelineWidthPx, minWidth: '100%' }}>
            {/* Date header */}
            <div className="sticky top-0 bg-gray-100 border-b border-gray-200 relative" style={{ height: 40 }}>
              {dateTicks.map((tick, i) => (
                <div
                  key={i}
                  className="absolute top-0 bottom-0 border-l border-gray-300 px-2 py-2 text-xs text-gray-600 font-medium"
                  style={{ left: tick.left }}
                >
                  {tick.label}
                </div>
              ))}
            </div>

            {/* Bars and Arrows */}
            <div className="relative" style={{ height: svgHeight }}>
              {/* SVG for dependency arrows */}
              <svg
                className="absolute inset-0 pointer-events-none"
                style={{ width: '100%', height: '100%' }}
              >
                <defs>
                  <marker
                    id="arrowhead"
                    markerWidth="10"
                    markerHeight="10"
                    refX="8"
                    refY="3"
                    orient="auto"
                  >
                    <polygon points="0 0, 10 3, 0 6" fill="#9CA3AF" />
                  </marker>
                </defs>
                {arrows.map(arrow => {
                  // Draw L-shaped path
                  const midX = (arrow.x1 + arrow.x2) / 2;
                  return (
                    <path
                      key={arrow.key}
                      d={`M ${arrow.x1} ${arrow.y1} L ${midX} ${arrow.y1} L ${midX} ${arrow.y2} L ${arrow.x2} ${arrow.y2}`}
                      stroke="#9CA3AF"
                      strokeWidth="1.5"
                      fill="none"
                      markerEnd="url(#arrowhead)"
                    />
                  );
                })}
              </svg>

              {/* Task bars */}
              {taskBars.map(bar => {
                const isDragging = dragState && dragState.bar.task.id === bar.task.id;
                const displayLeft = isDragging
                  ? bar.left + dragState.currentDelta * pxPerDay
                  : bar.left;

                const barColor = bar.isCritical ? 'bg-red-500' : 'bg-[#1570EF]';
                const hoverClass = readOnly ? '' : 'hover:opacity-80 cursor-move';

                return (
                  <div
                    key={bar.task.id}
                    data-testid={`gantt-bar-${bar.task.id}`}
                    className={`absolute rounded px-2 py-1 text-white text-[10px] font-medium ${barColor} ${hoverClass} ${isDragging ? 'opacity-70 ring-2 ring-blue-400' : ''}`}
                    style={{
                      left: displayLeft,
                      width: bar.width,
                      top: bar.idx * rowHeight + 8,
                      height: 24,
                      display: 'flex',
                      alignItems: 'center',
                      overflow: 'hidden',
                      whiteSpace: 'nowrap',
                    }}
                    onPointerDown={(e) => handlePointerDown(e, bar)}
                    title={`${bar.task.name}: ${format(parseISO(bar.task.start_date), 'MMM d')} - ${format(parseISO(bar.task.end_date), 'MMM d')}`}
                  >
                    <span className="truncate">{bar.task.name}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Reschedule confirmation dialog */}
      {rescheduleData && (
        <Dialog open={showRescheduleDialog} onOpenChange={setShowRescheduleDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Reschedule Task</DialogTitle>
              <DialogDescription>
                Confirm rescheduling &quot;{rescheduleData.task.name}&quot;
              </DialogDescription>
            </DialogHeader>
            <div className="py-4 space-y-2 text-sm">
              <div>
                <span className="font-medium">Original:</span>{' '}
                {rescheduleData.oldStart} → {rescheduleData.oldEnd}
              </div>
              <div>
                <span className="font-medium">New:</span>{' '}
                {rescheduleData.newStartDisplay} → {rescheduleData.newEndDisplay}
              </div>
              <p className="text-xs text-gray-500 mt-2">
                Dependent tasks will auto-shift.
              </p>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={handleRescheduleCancel}
                data-testid="gantt-reschedule-cancel"
              >
                Cancel
              </Button>
              <Button
                onClick={handleRescheduleConfirm}
                data-testid="gantt-reschedule-confirm"
              >
                Confirm
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};

export default WBSGanttView;
