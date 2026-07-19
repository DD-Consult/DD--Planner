import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listBaselines, getVariance, createBaseline, patchBaseline,
  deleteBaseline, getChangeLog,
} from '../api';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter,
} from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import {
  Camera, Star, StarOff, Trash2, Edit3, History, RefreshCw,
  TrendingUp, TrendingDown, Minus, AlertCircle, Clock,
  CheckCircle2, Loader2, Plus, ChevronRight,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { toast } from 'sonner';

// ─────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────
const fmtDate = (d) => {
  if (!d) return '—';
  try { return format(parseISO(d.length > 10 ? d : `${d}T00:00:00`), 'MMM d, yyyy'); }
  catch { return d; }
};

const DeltaPill = ({ value, suffix = 'd', neutralLabel = 'On track' }) => {
  if (value === null || value === undefined) {
    return <span className="text-xs text-gray-400">—</span>;
  }
  const v = Number(value);
  if (v === 0) {
    return (
      <Badge variant="outline" className="text-[10px] bg-green-50 text-green-700 border-green-200">
        <Minus size={10} className="mr-1" />
        {neutralLabel}
      </Badge>
    );
  }
  const positive = v > 0;
  return (
    <Badge
      variant="outline"
      className={`text-[10px] ${positive ? 'bg-red-50 text-red-700 border-red-200' : 'bg-blue-50 text-blue-700 border-blue-200'}`}
    >
      {positive ? <TrendingUp size={10} className="mr-1" /> : <TrendingDown size={10} className="mr-1" />}
      {positive ? '+' : ''}{v}{suffix}
    </Badge>
  );
};

// ─────────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────────
const BaselinesView = ({ projectId, canEdit = true }) => {
  const queryClient = useQueryClient();
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showRenameDialog, setShowRenameDialog] = useState(null); // baseline object
  const [showDeleteDialog, setShowDeleteDialog] = useState(null); // baseline object
  const [showChangeLog, setShowChangeLog] = useState(false);
  const [createForm, setCreateForm] = useState({ name: '', description: '', set_current: true });

  // ── Data ──
  const { data: baselinesResp, isLoading } = useQuery({
    queryKey: ['baselines', projectId],
    queryFn: async () => (await listBaselines(projectId)).data,
    enabled: !!projectId,
  });
  const baselines = baselinesResp?.items || [];

  const { data: variance, isLoading: varLoading } = useQuery({
    queryKey: ['variance', projectId],
    queryFn: async () => (await getVariance(projectId)).data,
    enabled: !!projectId,
  });

  // ── Mutations ──
  const createMut = useMutation({
    mutationFn: (payload) => createBaseline(projectId, payload),
    onSuccess: () => {
      toast.success('Baseline created');
      queryClient.invalidateQueries({ queryKey: ['baselines', projectId] });
      queryClient.invalidateQueries({ queryKey: ['variance', projectId] });
      setShowCreateDialog(false);
      setCreateForm({ name: '', description: '', set_current: true });
    },
  });

  const patchMut = useMutation({
    mutationFn: ({ baselineId, payload }) => patchBaseline(projectId, baselineId, payload),
    onSuccess: () => {
      toast.success('Baseline updated');
      queryClient.invalidateQueries({ queryKey: ['baselines', projectId] });
      queryClient.invalidateQueries({ queryKey: ['variance', projectId] });
      setShowRenameDialog(null);
    },
  });

  const deleteMut = useMutation({
    mutationFn: (baselineId) => deleteBaseline(projectId, baselineId),
    onSuccess: () => {
      toast.success('Baseline deleted');
      queryClient.invalidateQueries({ queryKey: ['baselines', projectId] });
      setShowDeleteDialog(null);
    },
  });

  // ── Default name suggestion for the next baseline ──
  const suggestedName = useMemo(() => {
    if (baselines.length === 0) return 'Baseline v1';
    return `Re-baseline ${format(new Date(), 'MMM yyyy')}`;
  }, [baselines.length]);

  if (isLoading) {
    return <div className="text-center text-gray-500 py-8"><Loader2 className="animate-spin inline mr-2" size={16}/>Loading baselines…</div>;
  }

  const currentBaseline = baselines.find(b => b.is_current);

  return (
    <div className="space-y-6">
      {/* ── Header + Variance summary cards ── */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Baselines &amp; Variance</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Track changes against a locked-in plan. The <strong>current baseline</strong> is what variance is measured against.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowChangeLog(true)}
            data-testid="open-change-log-btn"
          >
            <History size={14} className="mr-1.5" />
            Change log
          </Button>
          {canEdit && (
            <Button
              size="sm"
              onClick={() => {
                setCreateForm({ name: suggestedName, description: '', set_current: true });
                setShowCreateDialog(true);
              }}
              data-testid="create-baseline-btn"
            >
              <Camera size={14} className="mr-1.5" />
              Snapshot baseline
            </Button>
          )}
        </div>
      </div>

      {/* Variance summary cards */}
      {varLoading ? (
        <div className="text-gray-400 text-sm">Calculating variance…</div>
      ) : variance?.note ? (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-2 text-sm text-amber-700">
          <AlertCircle size={16} /> {variance.note}
        </div>
      ) : variance?.baseline ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <VarianceCard
              label="Schedule slip"
              value={variance.summary?.schedule_slip_days}
              suffix=" days"
              hint="End-date drift vs baseline"
              icon={<Clock size={16} />}
            />
            <VarianceCard
              label="Scope delta"
              value={variance.summary?.scope_delta_hours}
              suffix="h"
              hint="Estimated-hours change across all tasks"
              icon={<TrendingUp size={16} />}
              formatVal={(v) => (v > 0 ? '+' : '') + Number(v).toFixed(1)}
            />
            <CountCard
              label="Tasks added"
              count={variance.summary?.tasks_added || 0}
              color="blue"
            />
            <CountCard
              label="Tasks removed"
              count={variance.summary?.tasks_removed || 0}
              color="red"
            />
          </div>

          <div className="p-3 bg-gray-50 rounded-lg border border-gray-200 text-xs text-gray-600">
            Comparing against <strong>{variance.baseline.name}</strong> (created {fmtDate(variance.baseline.created_at)} by {variance.baseline.created_by}).
          </div>
        </>
      ) : null}

      {/* ── Baselines list ── */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-3">All baselines</h3>
        <div className="space-y-2">
          {baselines.length === 0 && (
            <div className="text-center py-8 text-gray-500 text-sm border border-dashed rounded-lg">
              No baselines yet. {canEdit && 'Click "Snapshot baseline" to create one.'}
            </div>
          )}
          {baselines.map(b => (
            <div
              key={b.id}
              className={`p-3 border rounded-lg flex items-center gap-3 ${b.is_current ? 'bg-amber-50 border-amber-300' : 'bg-white border-gray-200'}`}
              data-testid={`baseline-row-${b.id}`}
            >
              <div className="shrink-0">
                {b.is_current
                  ? <Star size={18} className="text-amber-500 fill-amber-400" />
                  : <StarOff size={18} className="text-gray-300" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-900 truncate">{b.name}</span>
                  {b.is_current && <Badge className="bg-amber-200 text-amber-900 text-[10px]">Current</Badge>}
                </div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {fmtDate(b.created_at)} • by {b.created_by} • {b.phase_count} phase{b.phase_count !== 1 && 's'} • {b.task_count} task{b.task_count !== 1 && 's'}
                </div>
                {b.description && <div className="text-xs text-gray-400 mt-0.5 italic">{b.description}</div>}
              </div>
              {canEdit && (
                <div className="flex gap-1 shrink-0">
                  {!b.is_current && (
                    <Button
                      variant="ghost" size="sm"
                      onClick={() => patchMut.mutate({ baselineId: b.id, payload: { set_current: true } })}
                      title="Set as current baseline"
                      data-testid={`set-current-${b.id}`}
                    >
                      <Star size={14} />
                    </Button>
                  )}
                  <Button
                    variant="ghost" size="sm"
                    onClick={() => setShowRenameDialog(b)}
                    title="Rename"
                    data-testid={`rename-baseline-${b.id}`}
                  >
                    <Edit3 size={14} />
                  </Button>
                  <Button
                    variant="ghost" size="sm"
                    onClick={() => setShowDeleteDialog(b)}
                    disabled={b.is_current}
                    title={b.is_current ? "Can't delete the current baseline" : "Delete"}
                    data-testid={`delete-baseline-${b.id}`}
                  >
                    <Trash2 size={14} className={b.is_current ? 'text-gray-300' : 'text-red-500'} />
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── Phase variance table ── */}
      {variance?.phases?.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Phase variance</h3>
          <div className="overflow-hidden rounded-lg border border-gray-200">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-600 uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-2 text-left">Phase</th>
                  <th className="px-4 py-2 text-left">Baseline start</th>
                  <th className="px-4 py-2 text-left">Current start</th>
                  <th className="px-4 py-2 text-center">Δ Start</th>
                  <th className="px-4 py-2 text-left">Baseline end</th>
                  <th className="px-4 py-2 text-left">Current end</th>
                  <th className="px-4 py-2 text-center">Δ End</th>
                  <th className="px-4 py-2 text-left">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {variance.phases.map(p => (
                  <tr key={p.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 font-medium text-gray-900">{p.name}</td>
                    <td className="px-4 py-2 text-gray-500">{fmtDate(p.baseline_start)}</td>
                    <td className="px-4 py-2 text-gray-700">{fmtDate(p.current_start)}</td>
                    <td className="px-4 py-2 text-center"><DeltaPill value={p.start_var_days} /></td>
                    <td className="px-4 py-2 text-gray-500">{fmtDate(p.baseline_end)}</td>
                    <td className="px-4 py-2 text-gray-700">{fmtDate(p.current_end)}</td>
                    <td className="px-4 py-2 text-center"><DeltaPill value={p.end_var_days} /></td>
                    <td className="px-4 py-2 text-xs">
                      {!p.present_in_baseline && <Badge className="bg-blue-100 text-blue-700 text-[10px]">New</Badge>}
                      {!p.present_now && <Badge className="bg-red-100 text-red-700 text-[10px]">Removed</Badge>}
                      {p.present_in_baseline && p.present_now && <span className="text-gray-400">Tracked</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Task variance table (only show rows with non-zero variance) ── */}
      {variance?.tasks?.length > 0 && (() => {
        const changed = variance.tasks.filter(t =>
          !t.present_in_baseline || !t.present_now ||
          t.start_var_days || t.end_var_days || t.hours_var || t.deps_changed
        );
        return (
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-700">
                Task variance <span className="text-xs text-gray-400 ml-1">({changed.length} of {variance.tasks.length} with changes)</span>
              </h3>
            </div>
            {changed.length === 0 ? (
              <div className="text-sm text-gray-400 text-center py-4 border border-dashed rounded">
                <CheckCircle2 className="inline mr-1" size={14}/> All tasks match the baseline.
              </div>
            ) : (
              <div className="overflow-hidden rounded-lg border border-gray-200 max-h-96 overflow-y-auto">
                <table className="min-w-full text-xs">
                  <thead className="bg-gray-50 text-gray-600 uppercase tracking-wider sticky top-0">
                    <tr>
                      <th className="px-3 py-2 text-left">Task</th>
                      <th className="px-3 py-2 text-left">Phase</th>
                      <th className="px-3 py-2 text-center">Δ Start</th>
                      <th className="px-3 py-2 text-center">Δ End</th>
                      <th className="px-3 py-2 text-center">Δ Hours</th>
                      <th className="px-3 py-2 text-left">State</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white">
                    {changed.map(t => (
                      <tr key={t.id} className="hover:bg-gray-50">
                        <td className="px-3 py-1.5 font-medium text-gray-900 truncate max-w-[260px]" title={t.name}>{t.name}</td>
                        <td className="px-3 py-1.5 text-gray-500">{t.phase_name || '—'}</td>
                        <td className="px-3 py-1.5 text-center"><DeltaPill value={t.start_var_days} /></td>
                        <td className="px-3 py-1.5 text-center"><DeltaPill value={t.end_var_days} /></td>
                        <td className="px-3 py-1.5 text-center">
                          <DeltaPill value={t.hours_var !== null ? Number(t.hours_var).toFixed(1) : null} suffix="h" />
                        </td>
                        <td className="px-3 py-1.5">
                          {!t.present_in_baseline && <Badge className="bg-blue-100 text-blue-700 text-[10px]">New</Badge>}
                          {!t.present_now && <Badge className="bg-red-100 text-red-700 text-[10px]">Removed</Badge>}
                          {t.deps_changed && <Badge className="bg-purple-100 text-purple-700 text-[10px] ml-1">Deps changed</Badge>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })()}

      {/* ── Create baseline dialog ── */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Snapshot current state as baseline</DialogTitle>
            <DialogDescription>
              Captures project dates, phases, budgeted hours, and all {variance?.summary?.current_task_count ?? '—'} WBS tasks.
              Future variance will be measured against this snapshot if you set it as current.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <Label htmlFor="bl-name">Name</Label>
              <Input
                id="bl-name"
                value={createForm.name}
                onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                placeholder="e.g. Re-baseline Q4 2025"
              />
            </div>
            <div>
              <Label htmlFor="bl-desc">Description (optional)</Label>
              <Textarea
                id="bl-desc"
                value={createForm.description}
                onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                placeholder="e.g. After scope expansion, signed off by sponsor."
                rows={2}
              />
            </div>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={createForm.set_current}
                onChange={(e) => setCreateForm({ ...createForm, set_current: e.target.checked })}
              />
              Set as current baseline (replaces existing current)
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>Cancel</Button>
            <Button
              onClick={() => createMut.mutate(createForm)}
              disabled={!createForm.name.trim() || createMut.isPending}
              data-testid="confirm-create-baseline-btn"
            >
              {createMut.isPending ? <Loader2 className="animate-spin mr-1.5" size={14}/> : <Camera size={14} className="mr-1.5"/>}
              Create baseline
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Rename dialog ── */}
      <Dialog open={!!showRenameDialog} onOpenChange={() => setShowRenameDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename baseline</DialogTitle>
          </DialogHeader>
          {showRenameDialog && (
            <RenameForm
              baseline={showRenameDialog}
              onSubmit={(name, description) =>
                patchMut.mutate({
                  baselineId: showRenameDialog.id,
                  payload: { name, description },
                })
              }
              isLoading={patchMut.isPending}
            />
          )}
        </DialogContent>
      </Dialog>

      {/* ── Delete confirmation ── */}
      <Dialog open={!!showDeleteDialog} onOpenChange={() => setShowDeleteDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete baseline?</DialogTitle>
            <DialogDescription>
              This permanently removes <strong>{showDeleteDialog?.name}</strong>. Change-log entries are NOT deleted.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(null)}>Cancel</Button>
            <Button
              variant="destructive"
              onClick={() => deleteMut.mutate(showDeleteDialog.id)}
              disabled={deleteMut.isPending}
            >
              <Trash2 size={14} className="mr-1.5" />
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Change log drawer ── */}
      {showChangeLog && (
        <ChangeLogDrawer projectId={projectId} onClose={() => setShowChangeLog(false)} />
      )}
    </div>
  );
};


// ─────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────

function VarianceCard({ label, value, suffix, hint, icon, formatVal }) {
  const v = value;
  const num = Number(v);
  const isZero = !num || num === 0;
  const isPositive = num > 0;
  const display = formatVal ? formatVal(num) : `${isPositive && num !== 0 ? '+' : ''}${num}`;
  const color = isZero
    ? 'bg-green-50 border-green-200 text-green-900'
    : (isPositive ? 'bg-red-50 border-red-200 text-red-900' : 'bg-blue-50 border-blue-200 text-blue-900');
  return (
    <div className={`p-3 rounded-lg border ${color}`}>
      <div className="flex items-center gap-1.5 text-xs font-medium opacity-70 mb-1">
        {icon} {label}
      </div>
      <div className="text-xl font-bold">{display}{suffix}</div>
      {hint && <div className="text-[10px] opacity-60 mt-0.5">{hint}</div>}
    </div>
  );
}

function CountCard({ label, count, color }) {
  const palette = {
    blue: 'bg-blue-50 border-blue-200 text-blue-900',
    red: 'bg-red-50 border-red-200 text-red-900',
    green: 'bg-green-50 border-green-200 text-green-900',
  };
  return (
    <div className={`p-3 rounded-lg border ${palette[color] || palette.blue}`}>
      <div className="text-xs font-medium opacity-70 mb-1">{label}</div>
      <div className="text-xl font-bold">{count}</div>
    </div>
  );
}

function RenameForm({ baseline, onSubmit, isLoading }) {
  const [name, setName] = useState(baseline.name);
  const [description, setDescription] = useState(baseline.description || '');
  return (
    <>
      <div className="space-y-3 py-2">
        <div>
          <Label>Name</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <Label>Description</Label>
          <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
        </div>
      </div>
      <DialogFooter>
        <Button onClick={() => onSubmit(name, description)} disabled={!name.trim() || isLoading}>
          {isLoading ? <Loader2 className="animate-spin mr-1.5" size={14}/> : null}
          Save
        </Button>
      </DialogFooter>
    </>
  );
}

function ChangeLogDrawer({ projectId, onClose }) {
  const { data, isLoading } = useQuery({
    queryKey: ['changeLog', projectId],
    queryFn: async () => (await getChangeLog(projectId, { limit: 200 })).data,
  });
  const items = data?.items || [];

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <History size={18} /> Change log
            <Badge variant="outline" className="text-[10px] ml-2">{items.length} entries</Badge>
          </DialogTitle>
          <DialogDescription>
            All baselined-field edits to this project (newest first). Append-only — entries cannot be removed.
          </DialogDescription>
        </DialogHeader>
        {isLoading ? (
          <div className="text-center py-8 text-gray-500">
            <Loader2 className="animate-spin inline mr-2" size={16}/> Loading…
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-8 text-gray-400 text-sm">No changes recorded yet.</div>
        ) : (
          <div className="space-y-1.5 py-2">
            {items.map(e => (
              <div key={e.id} className="flex items-start gap-3 p-2 text-xs border border-gray-100 rounded hover:bg-gray-50">
                <ChevronRight size={12} className="mt-1 text-gray-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-gray-500">{format(parseISO(e.timestamp), 'MMM d, HH:mm')}</span>
                    <span className="text-gray-400">•</span>
                    <span className="font-medium text-gray-900">{e.user_email}</span>
                    <Badge variant="outline" className="text-[9px]">{e.entity_type}</Badge>
                    <Badge variant="outline" className={`text-[9px] ${
                      e.action === 'create' ? 'bg-green-50 text-green-700' :
                      e.action === 'delete' ? 'bg-red-50 text-red-700' :
                      'bg-blue-50 text-blue-700'
                    }`}>{e.action}</Badge>
                    {e.field && <span className="text-purple-700 font-mono text-[10px]">{e.field}</span>}
                  </div>
                  {(e.old_value !== null && e.old_value !== undefined) || (e.new_value !== null && e.new_value !== undefined) ? (
                    <div className="mt-1 text-gray-600 break-all">
                      {e.old_value !== null && e.old_value !== undefined && (
                        <span className="line-through text-red-500 mr-1">{JSON.stringify(e.old_value).slice(0, 80)}</span>
                      )}
                      {e.new_value !== null && e.new_value !== undefined && (
                        <span className="text-green-600">→ {JSON.stringify(e.new_value).slice(0, 80)}</span>
                      )}
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default BaselinesView;
