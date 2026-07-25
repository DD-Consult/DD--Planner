import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  Sparkles, TrendingDown, AlertTriangle, ClipboardList, RefreshCw,
  ChevronRight, Zap, Activity, Timer, Award,
} from 'lucide-react';
import {
  runAnomalyScan, getLatestAnomalyReport,
  getPortfolioForecast, generateProjectRetrospective,
  listProjectRetrospectives, getRetrospective, deleteRetrospective,
  getProjects,
} from '../api';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';

const sevColor = {
  critical: 'bg-red-100 text-red-800 border-red-300',
  high: 'bg-orange-100 text-orange-800 border-orange-300',
  medium: 'bg-amber-100 text-amber-800 border-amber-300',
  low: 'bg-blue-100 text-blue-800 border-blue-300',
};

const riskColor = {
  Critical: 'bg-red-100 text-red-800 border-red-300',
  High: 'bg-orange-100 text-orange-800 border-orange-300',
  Medium: 'bg-amber-100 text-amber-800 border-amber-300',
  Low: 'bg-emerald-100 text-emerald-800 border-emerald-300',
};

// ─── Anomaly Detection Panel ───────────────────────────────────────────
const AnomalyPanel = () => {
  const qc = useQueryClient();
  const { data: report, isLoading } = useQuery({
    queryKey: ['anomaly-latest'],
    queryFn: () => getLatestAnomalyReport().then(r => r.data),
    staleTime: 60000,
  });
  const scanMutation = useMutation({
    mutationFn: runAnomalyScan,
    onSuccess: () => {
      toast.success('Anomaly scan complete');
      qc.invalidateQueries({ queryKey: ['anomaly-latest'] });
    },
    onError: (e) => toast.error(`Scan failed: ${e?.response?.data?.detail || e?.message || 'Unknown'}`),
  });

  const findings = report?.findings || [];
  const summary = report?.summary || {};

  return (
    <div className="bg-white rounded-xl border border-[#E6E8EC] p-6" data-testid="anomaly-panel">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-[#0B1220] flex items-center gap-2">
            <Zap size={18} className="text-amber-500" />
            Anomaly Detection
          </h3>
          <p className="text-sm text-[#667085] mt-1">
            Statistical scan for unusual patterns across timesheets, burn rates, and capacity
          </p>
        </div>
        <Button
          onClick={() => scanMutation.mutate()}
          disabled={scanMutation.isPending}
          size="sm"
          data-testid="anomaly-scan-btn"
        >
          <RefreshCw size={14} className={`mr-2 ${scanMutation.isPending ? 'animate-spin' : ''}`} />
          {scanMutation.isPending ? 'Scanning…' : 'Run scan'}
        </Button>
      </div>

      {isLoading ? (
        <div className="py-8 text-center text-[#667085] text-sm">Loading…</div>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-3 mb-4">
            <div className="p-3 bg-red-50 rounded-lg border border-red-200">
              <div className="text-2xl font-bold text-red-800">{summary.critical || 0}</div>
              <div className="text-xs text-red-700">Critical</div>
            </div>
            <div className="p-3 bg-orange-50 rounded-lg border border-orange-200">
              <div className="text-2xl font-bold text-orange-800">{summary.high || 0}</div>
              <div className="text-xs text-orange-700">High</div>
            </div>
            <div className="p-3 bg-amber-50 rounded-lg border border-amber-200">
              <div className="text-2xl font-bold text-amber-800">{summary.medium || 0}</div>
              <div className="text-xs text-amber-700">Medium</div>
            </div>
            <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
              <div className="text-2xl font-bold text-blue-800">{summary.low || 0}</div>
              <div className="text-xs text-blue-700">Low</div>
            </div>
          </div>

          {findings.length === 0 ? (
            <div className="py-6 text-center text-sm text-[#667085] bg-emerald-50 rounded-lg border border-emerald-200">
              ✓ No anomalies detected. {!report?.created_at && 'Run a scan to get started.'}
            </div>
          ) : (
            <div className="space-y-2" data-testid="anomaly-findings-list">
              {findings.map((f, i) => (
                <div key={i} className="p-3 border border-[#E6E8EC] rounded-lg hover:bg-[#F9FAFB]">
                  <div className="flex items-start gap-2">
                    <Badge className={`${sevColor[f.severity] || sevColor.low} text-xs px-2 border`}>
                      {f.severity}
                    </Badge>
                    <div className="flex-1">
                      <div className="text-sm text-[#0B1220] font-medium">{f.message}</div>
                      {f.suggested_action && (
                        <div className="text-xs text-[#475467] mt-1 italic">💡 {f.suggested_action}</div>
                      )}
                      {(f.baseline !== null && f.baseline !== undefined) && (
                        <div className="text-xs text-[#667085] mt-1">
                          baseline: {f.baseline} → current: {f.current}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
};

// ─── Forecasting Panel ─────────────────────────────────────────────────
const ForecastPanel = () => {
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['portfolio-forecast'],
    queryFn: () => getPortfolioForecast().then(r => r.data),
    staleTime: 5 * 60 * 1000,
  });

  const forecasts = data?.forecasts || [];
  const summary = data?.summary || {};

  return (
    <div className="bg-white rounded-xl border border-[#E6E8EC] p-6" data-testid="forecast-panel">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-[#0B1220] flex items-center gap-2">
            <TrendingDown size={18} className="text-purple-500" />
            Portfolio Forecast
          </h3>
          <p className="text-sm text-[#667085] mt-1">
            Slip-risk score per active project — velocity, WBS completion, and time buffer signals
          </p>
        </div>
        <Button
          onClick={() => refetch()}
          disabled={isFetching}
          size="sm"
          variant="outline"
          data-testid="forecast-refresh-btn"
        >
          <RefreshCw size={14} className={`mr-2 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {isLoading ? (
        <div className="py-8 text-center text-[#667085] text-sm">Analysing…</div>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-3 mb-4">
            <div className="p-3 bg-red-50 rounded-lg border border-red-200">
              <div className="text-2xl font-bold text-red-800">{summary.critical || 0}</div>
              <div className="text-xs text-red-700">Critical risk</div>
            </div>
            <div className="p-3 bg-orange-50 rounded-lg border border-orange-200">
              <div className="text-2xl font-bold text-orange-800">{summary.high || 0}</div>
              <div className="text-xs text-orange-700">High risk</div>
            </div>
            <div className="p-3 bg-amber-50 rounded-lg border border-amber-200">
              <div className="text-2xl font-bold text-amber-800">{summary.medium || 0}</div>
              <div className="text-xs text-amber-700">Medium</div>
            </div>
            <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-200">
              <div className="text-2xl font-bold text-emerald-800">{summary.low || 0}</div>
              <div className="text-xs text-emerald-700">On track</div>
            </div>
          </div>

          {forecasts.length === 0 ? (
            <div className="py-6 text-center text-sm text-[#667085]">
              No active projects to forecast yet.
            </div>
          ) : (
            <div className="space-y-2" data-testid="forecast-list">
              {forecasts.map((f) => (
                <div key={f.project_id} className="p-4 border border-[#E6E8EC] rounded-lg">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-[#0B1220]">{f.project_name}</span>
                        <Badge className={`${riskColor[f.slip_risk_label] || riskColor.Low} text-xs px-2 border`}>
                          {f.slip_risk_label} ({f.slip_risk_score})
                        </Badge>
                      </div>
                      <div className="text-xs text-[#475467] flex flex-wrap gap-x-4 gap-y-1">
                        <span><Timer size={11} className="inline mr-1" />Planned: {f.planned_end_date}</span>
                        {f.projected_end_date && f.projected_end_date !== f.planned_end_date && (
                          <span className="text-orange-700">Projected: {f.projected_end_date}</span>
                        )}
                        <span>{f.actual_hours}h / {f.planned_hours}h</span>
                        <span>{f.elapsed_pct}% elapsed</span>
                        {f.recent_weekly_burn > 0 && <span>{f.recent_weekly_burn}h/wk avg</span>}
                      </div>
                      {f.top_factors && f.top_factors.length > 0 && (
                        <ul className="mt-2 text-xs text-[#475467] space-y-1">
                          {f.top_factors.map((tf, i) => (
                            <li key={i} className="flex items-start gap-1">
                              <span className="text-red-500 mt-0.5">•</span>
                              <span>{tf.narrative}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
};

// ─── Retrospective Panel ───────────────────────────────────────────────
const RetrospectivePanel = () => {
  const { data: projects } = useQuery({
    queryKey: ['projects'],
    queryFn: () => getProjects().then(r => r.data),
  });
  const [projectId, setProjectId] = useState('');
  const [openRetro, setOpenRetro] = useState(null);
  const qc = useQueryClient();

  const { data: retroList, refetch: refetchList } = useQuery({
    queryKey: ['retros', projectId],
    queryFn: () => listProjectRetrospectives(projectId).then(r => r.data.items),
    enabled: !!projectId,
  });

  const generateMutation = useMutation({
    mutationFn: () => generateProjectRetrospective(projectId),
    onSuccess: (res) => {
      toast.success('Retrospective generated');
      setOpenRetro(res.data);
      qc.invalidateQueries({ queryKey: ['retros', projectId] });
    },
    onError: (e) => toast.error(`Generation failed: ${e?.response?.data?.detail || e?.message}`),
  });

  const deleteMutation = useMutation({
    mutationFn: (retroId) => deleteRetrospective(retroId),
    onSuccess: () => {
      toast.success('Retrospective deleted');
      refetchList();
    },
  });

  return (
    <div className="bg-white rounded-xl border border-[#E6E8EC] p-6" data-testid="retrospective-panel">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-[#0B1220] flex items-center gap-2">
          <ClipboardList size={18} className="text-emerald-600" />
          Project Retrospectives
        </h3>
        <p className="text-sm text-[#667085] mt-1">
          AI-generated post-project analysis: what went well, lessons learned, and recommendations
        </p>
      </div>

      <div className="flex items-end gap-3 mb-4">
        <div className="flex-1">
          <label className="block text-xs font-medium text-[#475467] mb-1">Project</label>
          <Select value={projectId} onValueChange={setProjectId}>
            <SelectTrigger data-testid="retro-project-select"><SelectValue placeholder="Choose a project…" /></SelectTrigger>
            <SelectContent>
              {(projects || []).map(p => (
                <SelectItem key={p.id} value={p.id}>{p.name} ({p.status})</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button
          onClick={() => generateMutation.mutate()}
          disabled={!projectId || generateMutation.isPending}
          data-testid="retro-generate-btn"
        >
          <Sparkles size={14} className={`mr-2 ${generateMutation.isPending ? 'animate-pulse' : ''}`} />
          {generateMutation.isPending ? 'Generating…' : 'Generate'}
        </Button>
      </div>

      {projectId && (
        <div className="space-y-2">
          {(retroList || []).length === 0 && (
            <div className="text-sm text-[#667085] italic py-4 text-center border rounded-lg border-dashed">
              No retrospectives yet for this project. Click Generate to create the first one.
            </div>
          )}
          {(retroList || []).map((r) => {
            const retro = r.retrospective || {};
            return (
              <div key={r._id} className="p-3 border border-[#E6E8EC] rounded-lg hover:bg-[#F9FAFB] cursor-pointer group" onClick={() => setOpenRetro(r)}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <Badge className="text-xs px-2 bg-[#0B1220] text-white">Grade {retro.grade || '?'}</Badge>
                      <span className="text-xs text-[#667085]">{new Date(r.generated_at).toLocaleString()}</span>
                    </div>
                    <div className="text-sm text-[#475467] line-clamp-2">{retro.summary}</div>
                  </div>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100">
                    <button
                      onClick={(e) => { e.stopPropagation(); if (window.confirm('Delete this retrospective?')) deleteMutation.mutate(r._id); }}
                      className="p-1.5 hover:bg-red-50 rounded text-red-600 text-xs"
                    >
                      Delete
                    </button>
                    <ChevronRight size={16} className="text-[#667085]" />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <RetroDetailDialog retro={openRetro} onClose={() => setOpenRetro(null)} />
    </div>
  );
};

const Section = ({ title, items, colorClass = 'text-[#0B1220]', icon }) => {
  if (!items || items.length === 0) return null;
  return (
    <div className="mb-4">
      <h4 className={`text-sm font-semibold mb-2 ${colorClass} flex items-center gap-2`}>
        {icon}
        {title}
      </h4>
      <ul className="space-y-1.5 text-sm">
        {items.map((x, i) => (
          <li key={i} className="flex items-start gap-2">
            <span className="text-[#94A3B8] mt-1">•</span>
            <span className="text-[#334155] flex-1">{x}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

const RetroDetailDialog = ({ retro, onClose }) => {
  if (!retro) return null;
  const r = retro.retrospective || {};
  return (
    <Dialog open={!!retro} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto" data-testid="retro-detail-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Award size={18} className="text-emerald-600" />
            {retro.project_name} — Retrospective
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="p-4 bg-gradient-to-br from-emerald-50 to-blue-50 rounded-lg border border-emerald-200">
            <div className="flex items-center gap-3">
              <div className="text-4xl font-bold text-[#0B1220]">{r.grade || '?'}</div>
              <div>
                <div className="text-sm text-[#475467]">{r.grade_reasoning}</div>
              </div>
            </div>
            <div className="mt-3 text-sm text-[#334155]">{r.summary}</div>
            {r.kpi_highlights && (
              <div className="mt-3 flex gap-4 text-xs">
                <span>
                  <b>On time:</b>{' '}
                  {r.kpi_highlights.delivered_on_time === true ? '✅' : r.kpi_highlights.delivered_on_time === false ? '❌' : '—'}
                </span>
                <span>
                  <b>On budget:</b>{' '}
                  {r.kpi_highlights.delivered_on_budget === true ? '✅' : r.kpi_highlights.delivered_on_budget === false ? '❌' : '—'}
                </span>
                <span><b>Quality:</b> {r.kpi_highlights.quality_indicator || 'unknown'}</span>
              </div>
            )}
          </div>

          <Section title="What went well" items={r.what_went_well} colorClass="text-emerald-700" icon={<Activity size={14} />} />
          <Section title="What didn't go well" items={r.what_didnt_go_well} colorClass="text-orange-700" icon={<AlertTriangle size={14} />} />
          <Section title="Root causes" items={r.root_causes} colorClass="text-[#0B1220]" />
          <Section title="Lessons learned" items={r.lessons_learned} colorClass="text-blue-700" />
          <Section title="Recommendations" items={r.recommendations} colorClass="text-purple-700" />

          <div className="text-xs text-[#667085] pt-3 border-t">
            Generated by {retro.generated_by} · {new Date(retro.generated_at).toLocaleString()}
            {retro.provider && ` · via ${retro.provider}`}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// ─── Main Page ─────────────────────────────────────────────────────────
const AIIntelligence = () => {
  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6" data-testid="ai-intelligence-page">
      <div>
        <h1 className="text-2xl font-semibold text-[#0B1220] flex items-center gap-2">
          <Sparkles className="text-purple-500" />
          AI Intelligence
        </h1>
        <p className="text-sm text-[#667085] mt-1">
          Portfolio-level intelligence: anomaly detection, delivery forecasts, and retrospectives
        </p>
      </div>

      <AnomalyPanel />
      <ForecastPanel />
      <RetrospectivePanel />
    </div>
  );
};

export default AIIntelligence;
