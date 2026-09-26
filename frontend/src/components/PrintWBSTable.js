import React, { useMemo } from 'react';
import { format, differenceInBusinessDays } from 'date-fns';

/**
 * PrintWBSTable — a dedicated, print-first WBS table for the CLIENT REPORT
 * export (PDF/PPTX).
 *
 * WHY THIS EXISTS
 * ----------------
 * The interactive WBSView plan table is a screen-first component: it uses
 * `overflow-x-auto` + `min-w-max` and ~11 columns designed for a wide screen
 * with horizontal scrolling. A fixed-size export page cannot hold all of it, so
 * the right-most columns ("Actuals vs Est.", "Deps") were consistently clipped.
 * Four rounds of CSS/structural tweaks on the shared component each looked fixed
 * on light demo data but the real report still overflowed.
 *
 * This component stops reusing the screen component. It renders a print-safe
 * table with a fixed <colgroup> (widths sum to 100%) and `table-layout: fixed`,
 * so the table ALWAYS fits the page and long text wraps instead of overflowing —
 * regardless of how much data a project has.
 *
 * Essential columns (agreed in plan): Task, Phase, Start, End, Duration, Status,
 * % Complete, Actuals vs Est. The "Deps" column is intentionally dropped from the
 * client export.
 */

const STATUS_LABELS = {
  todo: 'To Do',
  in_progress: 'In Progress',
  done: 'Done',
  on_hold: 'On Hold',
  blocked: 'Blocked',
};

const STATUS_STYLES = {
  todo: { bg: '#F3F4F6', color: '#374151' },
  in_progress: { bg: '#DBEAFE', color: '#1D4ED8' },
  done: { bg: '#DCFCE7', color: '#15803D' },
  on_hold: { bg: '#FEF9C3', color: '#A16207' },
  blocked: { bg: '#FEE2E2', color: '#B91C1C' },
};

const fmtDate = (d) => {
  if (!d) return '—';
  try {
    return format(new Date(d), 'd MMM yyyy');
  } catch {
    return '—';
  }
};

const durationDays = (start, end) => {
  if (!start || !end) return '—';
  try {
    const days = differenceInBusinessDays(new Date(end), new Date(start)) + 1;
    return days > 0 ? `${days}d` : '—';
  } catch {
    return '—';
  }
};

const PrintWBSTable = ({ tasks = [], actuals = [], phases = [] }) => {
  // Map actuals by task id for quick lookup
  const actualsMap = useMemo(() => {
    const m = {};
    (actuals || []).forEach((a) => {
      if (a && a.task_id != null) m[a.task_id] = a;
    });
    return m;
  }, [actuals]);

  // Phase display order matching the project's phase sequence
  const phaseOrderMap = useMemo(() => {
    const map = {};
    (phases || []).forEach((p, idx) => {
      const name = typeof p === 'string' ? p : p.name;
      map[name] = idx;
    });
    return map;
  }, [phases]);

  // Sort by phase order first, then start date, then creation order
  const sortedTasks = useMemo(() => {
    const arr = [...(tasks || [])];
    arr.sort((a, b) => {
      const pa = phaseOrderMap[a.phase_name] ?? 999;
      const pb = phaseOrderMap[b.phase_name] ?? 999;
      if (pa !== pb) return pa - pb;
      const sa = a.start_date ? new Date(a.start_date).getTime() : Infinity;
      const sb = b.start_date ? new Date(b.start_date).getTime() : Infinity;
      if (sa !== sb) return sa - sb;
      return (a.order || 0) - (b.order || 0);
    });
    return arr;
  }, [tasks, phaseOrderMap]);

  if (!sortedTasks.length) {
    return (
      <div className="border border-gray-200 rounded-lg p-8 text-center text-gray-400 text-sm">
        No tasks have been created for this project yet.
      </div>
    );
  }

  const th = {
    padding: '6px 8px',
    fontSize: '8pt',
    fontWeight: 600,
    color: '#6B7280',
    textTransform: 'uppercase',
    letterSpacing: '0.03em',
    textAlign: 'left',
    borderBottom: '1px solid #E5E7EB',
    verticalAlign: 'bottom',
    wordBreak: 'break-word',
    overflowWrap: 'anywhere',
  };
  const td = {
    padding: '6px 8px',
    fontSize: '8pt',
    color: '#111827',
    borderBottom: '1px solid #F3F4F6',
    verticalAlign: 'top',
    wordBreak: 'break-word',
    overflowWrap: 'anywhere',
    whiteSpace: 'normal',
  };
  const tdRight = { ...td, textAlign: 'right' };

  return (
    <div className="print-wbs" style={{ width: '100%', maxWidth: '100%', overflow: 'hidden' }}>
      <table
        style={{
          width: '100%',
          maxWidth: '100%',
          tableLayout: 'fixed',
          borderCollapse: 'collapse',
          border: '1px solid #E5E7EB',
        }}
      >
        {/* Fixed column widths — sum to 100% so the table can never overflow. */}
        <colgroup>
          <col style={{ width: '24%' }} />{/* Task */}
          <col style={{ width: '14%' }} />{/* Phase */}
          <col style={{ width: '10%' }} />{/* Start */}
          <col style={{ width: '10%' }} />{/* End */}
          <col style={{ width: '8%' }} /> {/* Duration */}
          <col style={{ width: '12%' }} />{/* Status */}
          <col style={{ width: '10%' }} />{/* % Complete */}
          <col style={{ width: '12%' }} />{/* Actuals vs Est */}
        </colgroup>
        <thead>
          <tr style={{ backgroundColor: '#F9FAFB' }}>
            <th style={th}>Task</th>
            <th style={th}>Phase</th>
            <th style={th}>Start</th>
            <th style={th}>End</th>
            <th style={{ ...th, textAlign: 'right' }}>Duration</th>
            <th style={th}>Status</th>
            <th style={{ ...th, textAlign: 'right' }}>% Complete</th>
            <th style={th}>Actuals vs Est.</th>
          </tr>
        </thead>
        <tbody>
          {sortedTasks.map((task, idx) => {
            const a = actualsMap[task.id] || { actual_hours: 0 };
            const est = task.estimated_hours || 0;
            const act = a.actual_hours || 0;
            const over = est > 0 && act > est;
            const pct = task.progress_percentage != null ? Math.round(task.progress_percentage) : 0;
            const statusKey = task.status || 'todo';
            const stStyle = STATUS_STYLES[statusKey] || STATUS_STYLES.todo;
            const isMilestone = task.is_milestone;

            return (
              <tr key={task.id || idx} style={{ pageBreakInside: 'avoid', breakInside: 'avoid' }}>
                <td style={td}>
                  {isMilestone ? '◆ ' : ''}
                  {task.name || '(untitled)'}
                </td>
                <td style={{ ...td, color: '#6B7280' }}>{task.phase_name || '—'}</td>
                <td style={td}>{isMilestone ? fmtDate(task.milestone_date || task.start_date) : fmtDate(task.start_date)}</td>
                <td style={td}>{isMilestone ? '—' : fmtDate(task.end_date)}</td>
                <td style={tdRight}>{isMilestone ? '—' : durationDays(task.start_date, task.end_date)}</td>
                <td style={td}>
                  <span
                    style={{
                      display: 'inline-block',
                      padding: '1px 6px',
                      borderRadius: '4px',
                      fontSize: '7.5pt',
                      fontWeight: 600,
                      backgroundColor: stStyle.bg,
                      color: stStyle.color,
                    }}
                  >
                    {STATUS_LABELS[statusKey] || 'To Do'}
                  </span>
                </td>
                <td style={tdRight}>{isMilestone ? '—' : `${pct}%`}</td>
                <td style={td}>
                  {est > 0 ? (
                    <span style={{ color: over ? '#B91C1C' : act > 0 ? '#15803D' : '#9CA3AF', fontWeight: 500 }}>
                      {act}h / {est}h
                    </span>
                  ) : (
                    <span style={{ color: '#9CA3AF' }}>—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default PrintWBSTable;
