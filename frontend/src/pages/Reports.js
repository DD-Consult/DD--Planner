import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getPlannedVsActualOverview, getPortfolioBudgetAnalysis } from '../api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  BarChart3,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Search,
  Sparkles,
  Loader2,
  ArrowUpDown,
  ChevronRight,
  Target,
} from 'lucide-react';

const HealthBadge = ({ health }) => {
  const styles = {
    on_track: 'bg-[#16B364]/10 text-[#16B364] border-[#16B364]/30',
    at_risk: 'bg-[#F4B740]/10 text-[#F4B740] border-[#F4B740]/30',
    over_budget: 'bg-[#EF4444]/10 text-[#EF4444] border-[#EF4444]/30',
    no_budget: 'bg-[#667085]/10 text-[#667085] border-[#667085]/30',
  };
  const labels = { on_track: 'On Track', at_risk: 'At Risk', over_budget: 'Over Budget', no_budget: 'No Budget' };
  return <Badge variant="outline" className={styles[health] || styles.no_budget}>{labels[health] || health}</Badge>;
};

const SummaryCard = ({ icon: Icon, label, value, sub, color = 'text-[#0B1220]' }) => (
  <div className="bg-white border border-[#E6E8EC] rounded-lg p-5" data-testid={`summary-${label.toLowerCase().replace(/\s/g, '-')}`}>
    <div className="flex items-center gap-2 mb-2">
      <Icon size={16} className="text-[#98A2B3]" />
      <span className="text-xs text-[#667085] uppercase tracking-wider">{label}</span>
    </div>
    <div className={`text-2xl font-bold ${color}`}>{value}</div>
    {sub && <div className="text-xs text-[#98A2B3] mt-1">{sub}</div>}
  </div>
);

const Reports = () => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [healthFilter, setHealthFilter] = useState('all');
  const [sortBy, setSortBy] = useState('budget_used_pct');
  const [sortDir, setSortDir] = useState('desc');

  const { data: overview, isLoading } = useQuery({
    queryKey: ['plannedVsActualOverview'],
    queryFn: async () => { const r = await getPlannedVsActualOverview(); return r.data; },
  });

  const { data: aiAnalysis, isLoading: aiLoading, refetch: refetchAi } = useQuery({
    queryKey: ['portfolioBudgetAnalysis'],
    queryFn: async () => { const r = await getPortfolioBudgetAnalysis(); return r.data; },
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  const summary = overview?.summary || {};
  const projects = overview?.projects || [];

  // Filter and sort
  const filtered = projects
    .filter(p => {
      if (healthFilter !== 'all' && p.health !== healthFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return p.project_name.toLowerCase().includes(q) || p.client_name.toLowerCase().includes(q);
      }
      return true;
    })
    .sort((a, b) => {
      const mul = sortDir === 'desc' ? -1 : 1;
      return (a[sortBy] - b[sortBy]) * mul;
    });

  const toggleSort = (field) => {
    if (sortBy === field) setSortDir(d => d === 'desc' ? 'asc' : 'desc');
    else { setSortBy(field); setSortDir('desc'); }
  };

  const SortHeader = ({ field, children }) => (
    <th
      className="px-4 py-3 text-left text-xs font-medium text-[#667085] uppercase tracking-wider cursor-pointer hover:text-[#0B1220] select-none"
      onClick={() => toggleSort(field)}
    >
      <span className="flex items-center gap-1">
        {children}
        {sortBy === field && <ArrowUpDown size={12} className="text-[#1570EF]" />}
      </span>
    </th>
  );

  return (
    <div className="space-y-6" data-testid="reports-page">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-semibold flex items-center gap-3" style={{ fontFamily: 'Space Grotesk' }}>
          <BarChart3 size={28} />
          Planned vs. Actuals
        </h1>
        <p className="text-sm text-[#667085] mt-1">Cross-project budget health and time tracking overview</p>
      </div>

      {/* Summary Cards */}
      {isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1,2,3,4].map(i => <div key={i} className="bg-white border border-[#E6E8EC] rounded-lg p-5 h-24 animate-pulse" />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <SummaryCard icon={Target} label="Total Budget" value={`${summary.total_budget || 0}h`} sub={`${summary.total_projects || 0} projects`} />
          <SummaryCard icon={Clock} label="Total Actual" value={`${summary.total_actual || 0}h`} sub={`${summary.overall_pct_used || 0}% of budget`} />
          <SummaryCard
            icon={TrendingUp}
            label="Variance"
            value={`${summary.overall_variance > 0 ? '+' : ''}${summary.overall_variance || 0}h`}
            color={summary.overall_variance > 0 ? 'text-[#EF4444]' : 'text-[#16B364]'}
            sub={summary.overall_variance > 0 ? 'Over budget' : 'Under budget'}
          />
          <SummaryCard
            icon={AlertTriangle}
            label="At Risk"
            value={`${(summary.projects_at_risk || 0) + (summary.projects_over_budget || 0)}`}
            color={(summary.projects_at_risk || 0) + (summary.projects_over_budget || 0) > 0 ? 'text-[#F4B740]' : 'text-[#16B364]'}
            sub={`${summary.projects_on_track || 0} on track`}
          />
        </div>
      )}

      {/* AI Portfolio Analysis */}
      <div className="bg-white border border-[#E6E8EC] rounded-lg p-6" data-testid="ai-portfolio-analysis">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold flex items-center gap-2" style={{ fontFamily: 'Space Grotesk' }}>
            <Sparkles size={20} className="text-[#1570EF]" />
            AI Portfolio Insights
          </h2>
          <Button variant="ghost" size="sm" onClick={() => refetchAi()} disabled={aiLoading} data-testid="refresh-portfolio-ai">
            {aiLoading ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
            <span className="ml-1 text-xs">{aiLoading ? 'Analyzing...' : 'Refresh'}</span>
          </Button>
        </div>

        {aiLoading ? (
          <div className="flex items-center gap-3 py-6 justify-center text-[#667085]">
            <Loader2 size={20} className="animate-spin" />
            <span className="text-sm">AI is analyzing portfolio data...</span>
          </div>
        ) : aiAnalysis ? (
          <div className="space-y-4">
            <div className="bg-[#F5F8FF] border border-[#D1E0FF] rounded-lg p-4">
              <p className="text-sm text-[#0B1220] leading-relaxed" data-testid="portfolio-narrative">{aiAnalysis.narrative}</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Alerts */}
              {aiAnalysis.alerts?.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-[#667085] uppercase tracking-wider">Alerts</div>
                  {aiAnalysis.alerts.map((alert, i) => (
                    <div
                      key={i}
                      className={`flex items-start gap-2 p-3 rounded-lg border text-sm ${
                        alert.severity === 'critical' ? 'bg-red-50 border-red-200 text-red-800' :
                        alert.severity === 'warning' ? 'bg-amber-50 border-amber-200 text-amber-800' :
                        'bg-blue-50 border-blue-200 text-blue-800'
                      }`}
                    >
                      <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                      <div>
                        <div className="font-medium">{alert.title}</div>
                        <div className="text-xs mt-0.5 opacity-80">{alert.message}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Recommendations */}
              {aiAnalysis.recommendations?.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-[#667085] uppercase tracking-wider">Recommendations</div>
                  {aiAnalysis.recommendations.map((rec, i) => (
                    <div key={i} className="flex items-start gap-2 p-3 bg-[#F9FAFB] rounded-lg border border-[#E6E8EC] text-sm">
                      <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${
                        rec.priority === 'high' ? 'bg-[#EF4444]' : rec.priority === 'medium' ? 'bg-[#F4B740]' : 'bg-[#16B364]'
                      }`} />
                      <div>
                        <div className="font-medium text-[#0B1220]">{rec.title}</div>
                        <div className="text-xs text-[#667085] mt-0.5">{rec.action}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Project Highlights */}
            {aiAnalysis.project_highlights?.length > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-semibold text-[#667085] uppercase tracking-wider">Project Highlights</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                  {aiAnalysis.project_highlights.map((ph, i) => (
                    <div key={i} className="flex items-center gap-2 p-2 bg-[#F9FAFB] rounded border border-[#E6E8EC] text-sm">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${
                        ph.status === 'over_budget' ? 'bg-[#EF4444]' : ph.status === 'at_risk' ? 'bg-[#F4B740]' : 'bg-[#16B364]'
                      }`} />
                      <span className="font-medium text-[#0B1220] truncate">{ph.project}:</span>
                      <span className="text-[#667085] truncate">{ph.note}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-4 text-[#667085] text-sm">Unable to load AI analysis. Click Refresh to try again.</div>
        )}
      </div>

      {/* Project Comparison Table */}
      <div className="bg-white border border-[#E6E8EC] rounded-lg overflow-hidden" data-testid="project-comparison-table">
        <div className="px-5 py-4 border-b border-[#E6E8EC] flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#98A2B3]" />
            <Input
              placeholder="Search projects..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
              data-testid="reports-search"
            />
          </div>
          <Select value={healthFilter} onValueChange={setHealthFilter}>
            <SelectTrigger className="w-[160px]" data-testid="health-filter">
              <SelectValue placeholder="All Health" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Projects</SelectItem>
              <SelectItem value="on_track">On Track</SelectItem>
              <SelectItem value="at_risk">At Risk</SelectItem>
              <SelectItem value="over_budget">Over Budget</SelectItem>
              <SelectItem value="no_budget">No Budget</SelectItem>
            </SelectContent>
          </Select>
          <span className="text-xs text-[#98A2B3]">{filtered.length} projects</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[#F9FAFB] border-b border-[#E6E8EC]">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-[#667085] uppercase tracking-wider">Project</th>
                <SortHeader field="budgeted_hours">Budget</SortHeader>
                <SortHeader field="actual_hours">Actual</SortHeader>
                <SortHeader field="variance_hours">Variance</SortHeader>
                <SortHeader field="budget_used_pct">% Used</SortHeader>
                <th className="px-4 py-3 text-left text-xs font-medium text-[#667085] uppercase tracking-wider">Health</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F2F3F5]">
              {filtered.map((p) => (
                <tr
                  key={p.project_id}
                  className="hover:bg-[#F9FAFB] transition-colors cursor-pointer"
                  onClick={() => navigate(`/projects/${p.project_id}`)}
                  data-testid={`project-row-${p.project_id}`}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-sm text-[#0B1220]">{p.project_name}</div>
                    <div className="text-xs text-[#667085]">{p.client_name}</div>
                  </td>
                  <td className="px-4 py-3 text-sm">{p.budgeted_hours > 0 ? `${p.budgeted_hours}h` : '—'}</td>
                  <td className="px-4 py-3 text-sm font-medium">{p.actual_hours}h</td>
                  <td className={`px-4 py-3 text-sm font-medium ${
                    p.variance_hours > 0 ? 'text-[#EF4444]' : p.variance_hours < 0 ? 'text-[#16B364]' : ''
                  }`}>
                    {p.budgeted_hours > 0 ? `${p.variance_hours > 0 ? '+' : ''}${p.variance_hours}h` : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {p.budgeted_hours > 0 ? (
                      <div className="flex items-center gap-2">
                        <Progress value={Math.min(p.budget_used_pct, 100)} className="w-16 h-1.5" />
                        <span className={`text-xs font-medium ${
                          p.budget_used_pct > 100 ? 'text-[#EF4444]' : p.budget_used_pct > 80 ? 'text-[#F4B740]' : 'text-[#16B364]'
                        }`}>{p.budget_used_pct}%</span>
                      </div>
                    ) : <span className="text-xs text-[#98A2B3]">—</span>}
                  </td>
                  <td className="px-4 py-3"><HealthBadge health={p.health} /></td>
                  <td className="px-4 py-3"><ChevronRight size={16} className="text-[#98A2B3]" /></td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-[#667085] text-sm">No projects match your filters</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Reports;
