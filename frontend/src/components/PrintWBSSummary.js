import React, { useMemo } from 'react';

/**
 * PrintWBSSummary — a COMPACT, phase-level roll-up of the Work Breakdown
 * Structure for the client report export (Phase 2 "summary" option).
 *
 * Instead of the full task table, it shows one row per project phase with:
 *   - Phase name
 *   - Task count (and how many are done)
 *   - Rolled-up % complete (average of task progress in that phase)
 *   - Rolled-up estimated hours for the phase
 *
 * Print-safe: fixed <colgroup> summing to 100% + table-layout:fixed so it
 * always fits the page. No interactive elements.
 */

const PrintWBSSummary = ({ tasks = [], phases = [] }) => {
  const rows = useMemo(() => {
    // Build the ordered list of phase names from the project's phase sequence,
    // plus an "Unassigned" bucket for tasks with no/unknown phase.
    const phaseNames = (phases || []).map((p) => (typeof p === 'string' ? p : p.name));
    const orderIndex = {};
    phaseNames.forEach((n, i) => { orderIndex[n] = i; });

    const buckets = {};
    (tasks || []).forEach((t) => {
      const key = t.phase_name || 'Unassigned';
      if (!buckets[key]) buckets[key] = [];
      buckets[key].push(t);
    });

    const keys = Object.keys(buckets).sort((a, b) => {
      const ia = orderIndex[a] ?? 998;
      const ib = orderIndex[b] ?? 998;
      if (a === 'Unassigned') return 1;
      if (b === 'Unassigned') return -1;
      return ia - ib;
    });

    return keys.map((name) => {
      const list = buckets[name];
      const count = list.length;
      const doneCount = list.filter((t) => t.status === 'done').length;
      const estHours = list.reduce((s, t) => s + (t.estimated_hours || 0), 0);
      const avgPct = count
        ? Math.round(list.reduce((s, t) => s + (t.progress_percentage || 0), 0) / count)
        : 0;
      return { name, count, doneCount, estHours, avgPct };
    });
  }, [tasks, phases]);

  const totals = useMemo(() => {
    const count = rows.reduce((s, r) => s + r.count, 0);
    const done = rows.reduce((s, r) => s + r.doneCount, 0);
    const est = rows.reduce((s, r) => s + r.estHours, 0);
    const avgPct = count
      ? Math.round(rows.reduce((s, r) => s + r.avgPct * r.count, 0) / count)
      : 0;
    return { count, done, est, avgPct };
  }, [rows]);

  if (!rows.length) {
    return (
      <div className="border border-gray-200 rounded-lg p-8 text-center text-gray-400 text-sm">
        No tasks have been created for this project yet.
      </div>
    );
  }

  const th = {
    padding: '8px 10px',
    fontSize: '9pt',
    fontWeight: 600,
    color: '#6B7280',
    textTransform: 'uppercase',
    letterSpacing: '0.03em',
    borderBottom: '1px solid #E5E7EB',
    wordBreak: 'break-word',
    overflowWrap: 'anywhere',
  };
  const td = {
    padding: '8px 10px',
    fontSize: '9pt',
    color: '#111827',
    borderBottom: '1px solid #F3F4F6',
    verticalAlign: 'top',
    wordBreak: 'break-word',
    overflowWrap: 'anywhere',
  };

  return (
    <div className="print-wbs-summary" style={{ width: '100%', maxWidth: '100%', overflow: 'hidden' }}>
      <table
        style={{
          width: '100%',
          maxWidth: '100%',
          tableLayout: 'fixed',
          borderCollapse: 'collapse',
          border: '1px solid #E5E7EB',
        }}
      >
        <colgroup>
          <col style={{ width: '40%' }} />{/* Phase */}
          <col style={{ width: '18%' }} />{/* Tasks */}
          <col style={{ width: '22%' }} />{/* Progress */}
          <col style={{ width: '20%' }} />{/* Est. Hours */}
        </colgroup>
        <thead>
          <tr style={{ backgroundColor: '#F9FAFB' }}>
            <th style={{ ...th, textAlign: 'left' }}>Phase</th>
            <th style={{ ...th, textAlign: 'right' }}>Tasks (Done)</th>
            <th style={{ ...th, textAlign: 'left' }}>Progress</th>
            <th style={{ ...th, textAlign: 'right' }}>Est. Hours</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} style={{ pageBreakInside: 'avoid', breakInside: 'avoid' }}>
              <td style={{ ...td, fontWeight: 500 }}>{r.name}</td>
              <td style={{ ...td, textAlign: 'right' }}>{r.doneCount} / {r.count}</td>
              <td style={td}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontWeight: 600, minWidth: '28px' }}>{r.avgPct}%</span>
                  <div style={{ flex: 1, height: '6px', background: '#E5E7EB', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ width: `${Math.min(100, r.avgPct)}%`, height: '100%', background: '#4A9CC7' }} />
                  </div>
                </div>
              </td>
              <td style={{ ...td, textAlign: 'right' }}>{r.estHours}h</td>
            </tr>
          ))}
          {/* Totals row */}
          <tr style={{ backgroundColor: '#F9FAFB', fontWeight: 600 }}>
            <td style={{ ...td, fontWeight: 700 }}>Total</td>
            <td style={{ ...td, textAlign: 'right', fontWeight: 700 }}>{totals.done} / {totals.count}</td>
            <td style={{ ...td, fontWeight: 700 }}>{totals.avgPct}%</td>
            <td style={{ ...td, textAlign: 'right', fontWeight: 700 }}>{totals.est}h</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
};

export default PrintWBSSummary;
