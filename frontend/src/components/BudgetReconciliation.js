import React, { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getBudgetReconciliation, syncPhaseToWBS } from '../api';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import {
  Target, Calculator, Users, Clock, AlertTriangle, RefreshCw,
  TrendingUp, TrendingDown, Calendar, ArrowRight, Loader2, CheckCircle2,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { toast } from 'sonner';

const fmtH = (v) => v === null || v === undefined ? '—' : `${Number(v).toFixed(1)}h`;
const fmtDate = (d) => {
  if (!d) return '—';
  try { return format(parseISO(d), 'MMM d'); }
  catch { return d; }
};

const NumberCard = ({ icon, label, value, suffix = 'h', subtitle, accent, hint, drift }) => {
  const palette = {
    blue:   'bg-blue-50 border-blue-200',
    emerald:'bg-emerald-50 border-emerald-200',
    amber:  'bg-amber-50 border-amber-200',
    purple: 'bg-purple-50 border-purple-200',
    gray:   'bg-gray-50 border-gray-200',
  };
  const text = {
    blue: 'text-blue-700', emerald: 'text-emerald-700', amber: 'text-amber-700',
    purple: 'text-purple-700', gray: 'text-gray-700',
  };
  return (
    <div className={`p-4 rounded-lg border ${palette[accent] || palette.gray}`}>
      <div className={`flex items-center gap-1.5 text-xs font-medium ${text[accent] || text.gray} mb-1`}>
        {icon} {label}
      </div>
      <div className="text-2xl font-bold text-gray-900">
        {value === null || value === undefined ? '—' : `${Number(value).toFixed(1)}${suffix}`}
      </div>
      {subtitle && <div className="text-xs text-gray-600 mt-1">{subtitle}</div>}
      {drift !== undefined && drift !== null && (
        <div className={`text-xs mt-1 flex items-center gap-1 ${drift > 0 ? 'text-red-600' : drift < 0 ? 'text-emerald-600' : 'text-gray-500'}`}>
          {drift > 0 ? <TrendingUp size={11} /> : drift < 0 ? <TrendingDown size={11} /> : null}
          {drift > 0 ? '+' : ''}{Number(drift).toFixed(1)}h vs budget
        </div>
      )}
      {hint && <div className="text-[10px] text-gray-500 mt-0.5 italic">{hint}</div>}
    </div>
  );
};


const BudgetReconciliation = ({ projectId, canEdit = true }) => {
  const queryClient = useQueryClient();
  const [syncingPhaseId, setSyncingPhaseId] = useState(null);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['budgetReconciliation', projectId],
    queryFn: async () => (await getBudgetReconciliation(projectId)).data,
    enabled: !!projectId,
    refetchOnWindowFocus: false,
  });

  const syncMut = useMutation({
    mutationFn: async (phaseId) => {
      setSyncingPhaseId(phaseId);
      try {
        return (await syncPhaseToWBS(projectId, phaseId)).data;
      } finally {
        setSyncingPhaseId(null);
      }
    },
    onSuccess: (data) => {
      toast.success(`Phase synced: ${fmtDate(data.new_start_date)} → ${fmtDate(data.new_end_date)} (${data.task_count} tasks)`);
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      queryClient.invalidateQueries({ queryKey: ['budgetReconciliation', projectId] });
    },
  });

  if (isLoading) {
    return (
      <div className="p-8 text-center text-gray-400">
        <Loader2 className="animate-spin inline mr-2" size={16}/> Loading reconciliation…
      </div>
    );
  }
  if (!data || !data.totals) {
    return null;
  }
  const t = data.totals;
  const phases = data.phases || [];
  const warnings = data.warnings || [];
  const refLabel = t.reference_label || 'budget';
  const refValue = refLabel === 'budget' ? t.budget : t.estimated;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-gray-900 flex items-center gap-2">
            <Calculator size={16} className="text-[#1B2A47]" />
            Budget Reconciliation
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            How the four parallel numbers compare against {refLabel === 'budget' ? 'the project budget' : 'WBS estimates'}.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => refetch()} title="Refresh">
          <RefreshCw size={14} />
        </Button>
      </div>

      {/* 4-number summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <NumberCard
          icon={<Target size={14} />}
          label="Budget"
          value={t.budget}
          subtitle={t.phase_budgets_sum > 0 ? `Phase sum: ${fmtH(t.phase_budgets_sum)}` : 'Top-down target'}
          accent="blue"
        />
        <NumberCard
          icon={<Calculator size={14} />}
          label="Estimated"
          value={t.estimated}
          subtitle={t.estimated_pct !== null ? `${t.estimated_pct}% of ${refLabel}` : 'WBS rollup'}
          accent="purple"
          drift={t.estimated_vs_budget}
        />
        <NumberCard
          icon={<Users size={14} />}
          label="Allocated"
          value={t.allocated}
          subtitle={t.allocated_pct !== null ? `${t.allocated_pct}% of ${refLabel}` : 'Resource commitment'}
          accent="amber"
          drift={t.allocated_vs_budget}
        />
        <NumberCard
          icon={<Clock size={14} />}
          label="Actual"
          value={t.actual}
          subtitle={t.actual_pct !== null ? `${t.actual_pct}% of ${refLabel}` : 'Logged hours'}
          accent="emerald"
          drift={t.actual_vs_budget}
        />
      </div>

      {/* Hierarchy warnings */}
      {warnings.length > 0 && (
        <div className="p-3 rounded-lg border border-amber-200 bg-amber-50">
          <div className="flex items-start gap-2">
            <AlertTriangle size={16} className="text-amber-600 mt-0.5 shrink-0" />
            <div className="flex-1 text-sm">
              <div className="font-semibold text-amber-900 mb-1">
                {warnings.length} hierarchy issue{warnings.length === 1 ? '' : 's'} detected
              </div>
              <ul className="space-y-1 text-amber-800">
                {warnings.map((w, i) => (
                  <li key={i} className="text-xs flex items-start gap-1">
                    <span className="text-amber-500 shrink-0">•</span>
                    <span>{w.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Per-phase breakdown */}
      {phases.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-gray-200">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-600 uppercase tracking-wider">
              <tr>
                <th className="px-3 py-2 text-left">Phase</th>
                <th className="px-3 py-2 text-right">Budget</th>
                <th className="px-3 py-2 text-right">Estimated</th>
                <th className="px-3 py-2 text-right">Allocated</th>
                <th className="px-3 py-2 text-right">Actual</th>
                <th className="px-3 py-2 text-left">Dates</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {phases.map(p => {
                const hasDrift = !!p.date_drift;
                const overBudget = p.budget > 0 && (p.estimated > p.budget || p.actual > p.budget);
                return (
                  <tr key={p.id} className={overBudget ? 'bg-red-50/30' : ''}>
                    <td className="px-3 py-2 font-medium text-gray-900">
                      <div>{p.name}</div>
                      <div className="text-[10px] text-gray-400">{p.task_count} task{p.task_count !== 1 && 's'}</div>
                    </td>
                    <td className="px-3 py-2 text-right text-gray-700">{fmtH(p.budget)}</td>
                    <td className={`px-3 py-2 text-right ${p.budget > 0 && p.estimated > p.budget ? 'text-red-600 font-semibold' : 'text-gray-700'}`}>
                      {fmtH(p.estimated)}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-700">{fmtH(p.allocated)}</td>
                    <td className={`px-3 py-2 text-right ${p.budget > 0 && p.actual > p.budget ? 'text-red-600 font-semibold' : 'text-gray-700'}`}>
                      {fmtH(p.actual)}
                    </td>
                    <td className="px-3 py-2 text-xs">
                      <div className="text-gray-700 flex items-center gap-1">
                        <Calendar size={11} />
                        {fmtDate(p.manual_start)} → {fmtDate(p.manual_end)}
                      </div>
                      {hasDrift && p.derived_start && p.derived_end && (
                        <div className="text-amber-600 mt-0.5 flex items-center gap-1" title="WBS dates differ from phase dates">
                          <ArrowRight size={11} />
                          WBS: {fmtDate(p.derived_start)} → {fmtDate(p.derived_end)}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {hasDrift && canEdit && (
                        <Button
                          variant="outline" size="sm"
                          onClick={() => syncMut.mutate(p.id)}
                          disabled={syncingPhaseId === p.id}
                          className="text-xs gap-1"
                          data-testid={`sync-phase-${p.id}`}
                          title="Sync phase dates to MIN/MAX of WBS task dates"
                        >
                          {syncingPhaseId === p.id ? <Loader2 className="animate-spin" size={11} /> : <RefreshCw size={11} />}
                          Sync to WBS
                        </Button>
                      )}
                      {!hasDrift && p.task_count > 0 && (
                        <span className="text-[10px] text-emerald-600 flex items-center justify-end gap-1">
                          <CheckCircle2 size={11} /> In sync
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Legend */}
      <div className="text-[11px] text-gray-500 bg-gray-50 p-2 rounded border border-gray-100">
        <strong>Legend:</strong>{' '}
        <span className="text-blue-700">Budget</span> = target (top-down) •{' '}
        <span className="text-purple-700">Estimated</span> = sum of WBS task estimates (bottom-up) •{' '}
        <span className="text-amber-700">Allocated</span> = resource commitment (allocation % × duration × 8h) •{' '}
        <span className="text-emerald-700">Actual</span> = logged timesheet hours.
      </div>
    </div>
  );
};

export default BudgetReconciliation;
