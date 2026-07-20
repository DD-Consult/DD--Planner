import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  startOfWeek, 
  endOfWeek, 
  startOfMonth, 
  endOfMonth, 
  startOfQuarter, 
  endOfQuarter, 
  subWeeks, 
  subMonths, 
  addDays,
  format 
} from 'date-fns';
import { getTimesheetRangeReport, getResources, getProjects, getResourceUtilization } from '../api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
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
  Calendar,
  Filter,
  Download,
  BarChart3,
  Loader2,
  ChevronDown,
  ChevronRight,
  Users,
} from 'lucide-react';
import { toast } from 'sonner';

const SummaryCard = ({ icon: Icon, label, value, sub, color = 'text-[#0B1220]', testId }) => (
  <div className="bg-white border border-[#E6E8EC] rounded-lg p-5" data-testid={testId}>
    <div className="flex items-center gap-2 mb-2">
      <Icon size={16} className="text-[#98A2B3]" />
      <span className="text-xs text-[#667085] uppercase tracking-wider">{label}</span>
    </div>
    <div className={`text-2xl font-bold ${color}`}>{value}</div>
    {sub && <div className="text-xs text-[#98A2B3] mt-1">{sub}</div>}
  </div>
);

const TimesheetReports = () => {
  // Default to "This Month"
  const thisMonthStart = format(startOfMonth(new Date()), 'yyyy-MM-dd');
  const thisMonthEnd = format(endOfMonth(new Date()), 'yyyy-MM-dd');

  const [startDate, setStartDate] = useState(thisMonthStart);
  const [endDate, setEndDate] = useState(thisMonthEnd);
  const [groupBy, setGroupBy] = useState('resource');
  
  // View mode state
  const [viewMode, setViewMode] = useState('timesheets'); // 'timesheets' | 'utilization'
  const [expandedResources, setExpandedResources] = useState({});
  
  // Advanced filters
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [resourceId, setResourceId] = useState('all');
  const [projectId, setProjectId] = useState('all');
  const [clientName, setClientName] = useState('');
  const [status, setStatus] = useState('all');

  // Applied filters (trigger fetch only on Apply)
  const [appliedFilters, setAppliedFilters] = useState({
    start_date: thisMonthStart,
    end_date: thisMonthEnd,
    group_by: 'resource',
    resource_id: '',
    project_id: '',
    client_name: '',
    status: '',
  });

  const [showDetails, setShowDetails] = useState(false);

  // Fetch resources and projects for filters
  const { data: resourcesData } = useQuery({
    queryKey: ['resources'],
    queryFn: async () => { const r = await getResources(); return r.data; },
  });

  const { data: projectsData } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => { const r = await getProjects(); return r.data; },
  });

  const resources = resourcesData || [];
  const projects = projectsData || [];

  // Fetch report data
  const { data: reportData, isLoading } = useQuery({
    queryKey: ['timesheetRangeReport', appliedFilters],
    queryFn: async () => {
      // Build params, excluding empty values
      const params = {};
      Object.keys(appliedFilters).forEach(key => {
        if (appliedFilters[key]) params[key] = appliedFilters[key];
      });
      const r = await getTimesheetRangeReport(params);
      return r.data;
    },
  });

  // Fetch utilization data
  const { data: utilizationData, isLoading: isUtilLoading } = useQuery({
    queryKey: ['resource-utilization', appliedFilters.start_date, appliedFilters.end_date],
    queryFn: async () => {
      const r = await getResourceUtilization({
        start_date: appliedFilters.start_date,
        end_date: appliedFilters.end_date,
      });
      return r.data;
    },
    enabled: viewMode === 'utilization',
  });

  const summary = reportData?.summary || {};
  const groups = reportData?.groups || [];
  const entries = reportData?.entries || [];

  const handleApply = () => {
    setAppliedFilters({
      start_date: startDate,
      end_date: endDate,
      group_by: groupBy,
      resource_id: resourceId === 'all' ? '' : resourceId,
      project_id: projectId === 'all' ? '' : projectId,
      client_name: clientName.trim(),
      status: status === 'all' ? '' : status,
    });
  };

  const setQuickRange = (rangeType) => {
    const now = new Date();
    let start, end;
    switch (rangeType) {
      case 'this_week':
        start = startOfWeek(now, { weekStartsOn: 1 });
        end = addDays(start, 4); // Friday (business days only)
        break;
      case 'last_week':
        start = startOfWeek(subWeeks(now, 1), { weekStartsOn: 1 });
        end = addDays(start, 4); // Friday (business days only)
        break;
      case 'this_month':
        start = startOfMonth(now);
        end = endOfMonth(now);
        break;
      case 'last_month':
        start = startOfMonth(subMonths(now, 1));
        end = endOfMonth(subMonths(now, 1));
        break;
      case 'this_quarter':
        start = startOfQuarter(now);
        end = endOfQuarter(now);
        break;
      default:
        return;
    }
    setStartDate(format(start, 'yyyy-MM-dd'));
    setEndDate(format(end, 'yyyy-MM-dd'));
  };

  const exportCSV = () => {
    if (!entries || entries.length === 0) {
      toast.error('No data to export');
      return;
    }

    // CSV Header
    const headers = [
      'Resource',
      'Project',
      'Client',
      'Week Start',
      'Week End',
      'Planned Hours',
      'Actual Hours',
      'Variance',
      'Status',
      'Task',
    ];

    // Escape CSV field (wrap in quotes if contains comma or quote, double-escape quotes)
    const escapeCSV = (field) => {
      if (field == null) return '';
      const str = String(field);
      if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    };

    const rows = entries.map(e => [
      escapeCSV(e.resource_name || ''),
      escapeCSV(e.project_name || ''),
      escapeCSV(e.client_name || ''),
      escapeCSV(e.week_start_date || ''),
      escapeCSV(e.week_end_date || ''),
      escapeCSV(e.planned_hours || 0),
      escapeCSV(e.actual_hours || 0),
      escapeCSV(e.variance_hours || 0),
      escapeCSV(e.status || ''),
      escapeCSV(e.task_name || ''),
    ].join(','));

    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `timesheet-report-${appliedFilters.start_date}-to-${appliedFilters.end_date}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success('CSV exported successfully');
  };

  const varianceColor = (variance) => {
    if (variance == null) return 'text-[#667085]';
    if (variance < 0) return 'text-[#16B364]'; // under budget = good
    if (variance > 0) return 'text-[#EF4444]'; // over budget = bad
    return 'text-[#667085]';
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-[#0B1220]">Timesheet Reports</h1>
        <p className="text-sm text-[#667085] mt-1">
          Analyze planned vs actual time across any date range
        </p>
      </div>

      {/* Filters Card */}
      <div className="bg-white border border-[#E6E8EC] rounded-lg p-6 space-y-4">
        <div className="flex items-center gap-2 mb-2">
          <Filter size={18} className="text-[#667085]" />
          <span className="text-sm font-semibold text-[#0B1220]">Filters</span>
        </div>

        {/* Date Range */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-medium text-[#667085] uppercase tracking-wider block mb-2">
              Start Date
            </label>
            <Input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              data-testid="trr-start-date"
              className="w-full"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-[#667085] uppercase tracking-wider block mb-2">
              End Date
            </label>
            <Input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              data-testid="trr-end-date"
              className="w-full"
            />
          </div>
        </div>

        {/* Quick Filters */}
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setQuickRange('this_week')}
            className="text-xs"
          >
            This Week
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setQuickRange('last_week')}
            className="text-xs"
          >
            Last Week
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setQuickRange('this_month')}
            className="text-xs"
          >
            This Month
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setQuickRange('last_month')}
            className="text-xs"
          >
            Last Month
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setQuickRange('this_quarter')}
            className="text-xs"
          >
            This Quarter
          </Button>
        </div>

        {/* Group By */}
        <div>
          <label className="text-xs font-medium text-[#667085] uppercase tracking-wider block mb-2">
            Group By
          </label>
          <Select value={groupBy} onValueChange={setGroupBy}>
            <SelectTrigger data-testid="trr-group-by" className="w-full md:w-64">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="resource">Resource</SelectItem>
              <SelectItem value="project">Project</SelectItem>
              <SelectItem value="client">Client</SelectItem>
              <SelectItem value="week">Week</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Advanced Filters */}
        <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="text-xs text-[#667085] hover:text-[#0B1220]">
              {showAdvanced ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              <span className="ml-1">Advanced Filters</span>
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-[#667085] uppercase tracking-wider block mb-2">
                  Resource
                </label>
                <Select value={resourceId} onValueChange={setResourceId}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="All Resources" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Resources</SelectItem>
                    {resources.filter((r) => r.active !== false).map((r) => (
                      <SelectItem key={r.id} value={r.id}>
                        {r.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs font-medium text-[#667085] uppercase tracking-wider block mb-2">
                  Project
                </label>
                <Select value={projectId} onValueChange={setProjectId}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="All Projects" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Projects</SelectItem>
                    {projects.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.project_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs font-medium text-[#667085] uppercase tracking-wider block mb-2">
                  Client
                </label>
                <Input
                  type="text"
                  placeholder="Filter by client name"
                  value={clientName}
                  onChange={(e) => setClientName(e.target.value)}
                  className="w-full"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-[#667085] uppercase tracking-wider block mb-2">
                  Status
                </label>
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="All Statuses" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Statuses</SelectItem>
                    <SelectItem value="Draft">Draft</SelectItem>
                    <SelectItem value="Submitted">Submitted</SelectItem>
                    <SelectItem value="Approved">Approved</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* View Mode Toggle */}
        <div className="flex items-center gap-2 pt-4 border-t border-[#E6E8EC]">
          <span className="text-xs text-[#667085] font-medium uppercase tracking-wider">View:</span>
          <Button
            variant={viewMode === 'timesheets' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setViewMode('timesheets')}
            className="gap-1.5"
          >
            <BarChart3 size={14} />
            Timesheet Data
          </Button>
          <Button
            variant={viewMode === 'utilization' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setViewMode('utilization')}
            className="gap-1.5"
            data-testid="view-utilization-btn"
          >
            <Users size={14} />
            Resource Utilization
          </Button>
        </div>

        {/* Apply Button */}
        <div className="flex items-center gap-2 pt-2">
          <Button onClick={handleApply} data-testid="trr-apply" className="w-full md:w-auto">
            {isLoading ? <Loader2 size={16} className="animate-spin mr-2" /> : null}
            Apply Filters
          </Button>
          <Button
            variant="outline"
            onClick={exportCSV}
            disabled={!entries || entries.length === 0}
            data-testid="trr-export-csv"
            className="w-full md:w-auto"
          >
            <Download size={16} className="mr-2" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 size={32} className="animate-spin text-[#667085]" />
        </div>
      )}

      {/* Summary Cards */}
      {!isLoading && reportData && viewMode === 'timesheets' && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <SummaryCard
              icon={BarChart3}
              label="Total Entries"
              value={summary.total_entries || 0}
              testId="trr-summary-total-entries"
            />
            <SummaryCard
              icon={Calendar}
              label="Total Planned Hours"
              value={(summary.total_planned_hours || 0).toFixed(1)}
              sub={`${summary.unique_resources || 0} resources`}
              testId="trr-summary-total-planned"
            />
            <SummaryCard
              icon={Calendar}
              label="Total Actual Hours"
              value={(summary.total_actual_hours || 0).toFixed(1)}
              sub={`${summary.unique_projects || 0} projects`}
              testId="trr-summary-total-actual"
            />
            <SummaryCard
              icon={BarChart3}
              label="Variance Hours"
              value={
                summary.total_variance_hours != null
                  ? (summary.total_variance_hours > 0 ? '+' : '') +
                    summary.total_variance_hours.toFixed(1)
                  : '0.0'
              }
              color={varianceColor(summary.total_variance_hours)}
              sub={
                summary.total_variance_hours < 0
                  ? 'Under budget'
                  : summary.total_variance_hours > 0
                  ? 'Over budget'
                  : 'On track'
              }
              testId="trr-summary-variance"
            />
          </div>

          {/* Grouped Results Table */}
          {groups.length > 0 ? (
            <div className="bg-white border border-[#E6E8EC] rounded-lg overflow-hidden">
              <div className="p-4 border-b border-[#E6E8EC]">
                <h2 className="text-lg font-semibold text-[#0B1220]">
                  Grouped by {groupBy.charAt(0).toUpperCase() + groupBy.slice(1)}
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-[#F9FAFB]">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-[#667085] uppercase tracking-wider">
                        {groupBy === 'resource'
                          ? 'Resource'
                          : groupBy === 'project'
                          ? 'Project'
                          : groupBy === 'client'
                          ? 'Client'
                          : 'Week'}
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-[#667085] uppercase tracking-wider">
                        Planned
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-[#667085] uppercase tracking-wider">
                        Actual
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-[#667085] uppercase tracking-wider">
                        Variance
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-[#667085] uppercase tracking-wider">
                        Entries
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E6E8EC]">
                    {groups.map((g, idx) => (
                      <tr key={g.group_id || idx} className="hover:bg-[#F9FAFB]">
                        <td className="px-4 py-3">
                          <div className="font-medium text-[#0B1220]">{g.label || g.key}</div>
                          {g.subtitle && (
                            <div className="text-xs text-[#667085]">{g.subtitle}</div>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right text-sm text-[#0B1220]">
                          {(g.planned_hours || 0).toFixed(1)}h
                        </td>
                        <td className="px-4 py-3 text-right text-sm text-[#0B1220]">
                          {(g.actual_hours || 0).toFixed(1)}h
                        </td>
                        <td
                          className={`px-4 py-3 text-right text-sm font-medium ${varianceColor(
                            g.variance_hours
                          )}`}
                        >
                          {g.variance_hours != null
                            ? (g.variance_hours > 0 ? '+' : '') + g.variance_hours.toFixed(1) + 'h'
                            : '0.0h'}
                        </td>
                        <td className="px-4 py-3 text-right text-sm text-[#667085]">
                          {g.entries_count || 0}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="bg-white border border-[#E6E8EC] rounded-lg p-12 text-center">
              <BarChart3 size={48} className="mx-auto text-[#98A2B3] mb-4" />
              <h3 className="text-lg font-semibold text-[#0B1220] mb-2">No Data</h3>
              <p className="text-sm text-[#667085]">
                No timesheet data found for the selected filters.
              </p>
            </div>
          )}

          {/* Detailed Entries Table (Collapsible) */}
          {entries.length > 0 && (
            <Collapsible open={showDetails} onOpenChange={setShowDetails}>
              <div className="bg-white border border-[#E6E8EC] rounded-lg overflow-hidden">
                <CollapsibleTrigger asChild>
                  <button className="w-full p-4 flex items-center justify-between hover:bg-[#F9FAFB] transition-colors">
                    <h2 className="text-lg font-semibold text-[#0B1220]">
                      Detailed Entries ({entries.length})
                    </h2>
                    {showDetails ? (
                      <ChevronDown size={20} className="text-[#667085]" />
                    ) : (
                      <ChevronRight size={20} className="text-[#667085]" />
                    )}
                  </button>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-[#F9FAFB]">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium text-[#667085] uppercase tracking-wider">
                            Resource
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-[#667085] uppercase tracking-wider">
                            Project
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-[#667085] uppercase tracking-wider">
                            Client
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-[#667085] uppercase tracking-wider">
                            Week
                          </th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-[#667085] uppercase tracking-wider">
                            Planned
                          </th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-[#667085] uppercase tracking-wider">
                            Actual
                          </th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-[#667085] uppercase tracking-wider">
                            Variance
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-[#667085] uppercase tracking-wider">
                            Status
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#E6E8EC]">
                        {entries.map((e, idx) => (
                          <tr key={e.id || idx} className="hover:bg-[#F9FAFB]">
                            <td className="px-4 py-3 text-sm text-[#0B1220]">
                              {e.resource_name || '-'}
                            </td>
                            <td className="px-4 py-3">
                              <div className="text-sm font-medium text-[#0B1220]">
                                {e.project_name || '-'}
                              </div>
                              {e.task_name && (
                                <div className="text-xs text-[#667085]">{e.task_name}</div>
                              )}
                            </td>
                            <td className="px-4 py-3 text-sm text-[#667085]">
                              {e.client_name || '-'}
                            </td>
                            <td className="px-4 py-3 text-sm text-[#667085]">
                              {e.week_start_date && e.week_end_date
                                ? `${format(new Date(e.week_start_date), 'MMM d')} - ${format(
                                    new Date(e.week_end_date),
                                    'MMM d'
                                  )}`
                                : '-'}
                            </td>
                            <td className="px-4 py-3 text-right text-sm text-[#0B1220]">
                              {(e.planned_hours || 0).toFixed(1)}h
                            </td>
                            <td className="px-4 py-3 text-right text-sm text-[#0B1220]">
                              {(e.actual_hours || 0).toFixed(1)}h
                            </td>
                            <td
                              className={`px-4 py-3 text-right text-sm font-medium ${varianceColor(
                                e.variance_hours
                              )}`}
                            >
                              {e.variance_hours != null
                                ? (e.variance_hours > 0 ? '+' : '') +
                                  e.variance_hours.toFixed(1) +
                                  'h'
                                : '0.0h'}
                            </td>
                            <td className="px-4 py-3">
                              <span
                                className={`inline-flex px-2 py-1 text-xs font-medium rounded ${
                                  e.status === 'Approved'
                                    ? 'bg-[#16B364]/10 text-[#16B364]'
                                    : e.status === 'Submitted'
                                    ? 'bg-[#F4B740]/10 text-[#F4B740]'
                                    : 'bg-[#667085]/10 text-[#667085]'
                                }`}
                              >
                                {e.status || 'Draft'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CollapsibleContent>
              </div>
            </Collapsible>
          )}
        </>
      )}

      {/* Resource Utilization View */}
      {viewMode === 'utilization' && (
        <>
          {isUtilLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={32} className="animate-spin text-[#667085]" />
            </div>
          ) : utilizationData ? (
            <>
              {/* Summary Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <SummaryCard icon={Users} label="Resources" value={utilizationData.summary?.total_resources || 0} testId="util-resources" />
                <SummaryCard icon={Calendar} label="Total Allocated" value={`${(utilizationData.summary?.total_allocated_hours || 0).toFixed(1)}h`} testId="util-allocated" />
                <SummaryCard icon={Calendar} label="Total Actual" value={`${(utilizationData.summary?.total_actual_hours || 0).toFixed(1)}h`} testId="util-actual" />
                <SummaryCard
                  icon={BarChart3}
                  label="Overall Utilization"
                  value={`${utilizationData.summary?.overall_utilization_pct || 0}%`}
                  color={utilizationData.summary?.overall_utilization_pct > 100 ? 'text-red-600' : utilizationData.summary?.overall_utilization_pct > 80 ? 'text-green-600' : 'text-amber-600'}
                  sub={`${(utilizationData.summary?.total_variance || 0) > 0 ? '+' : ''}${(utilizationData.summary?.total_variance || 0).toFixed(1)}h variance`}
                  testId="util-pct"
                />
              </div>

              {/* Resource Table */}
              <div className="bg-white border border-[#E6E8EC] rounded-lg overflow-hidden">
                <div className="p-4 border-b border-[#E6E8EC]">
                  <h2 className="text-lg font-semibold text-[#0B1220]">
                    Allocated vs Actual Hours by Resource
                  </h2>
                  <p className="text-sm text-[#667085] mt-0.5">Click a resource to see project breakdown</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-[#F9FAFB]">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-[#667085] uppercase tracking-wider">Resource</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-[#667085] uppercase tracking-wider">Allocated</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-[#667085] uppercase tracking-wider">Actual</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-[#667085] uppercase tracking-wider">Variance</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-[#667085] uppercase tracking-wider">Utilization</th>
                        <th className="px-4 py-3 w-20"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E6E8EC]">
                      {(utilizationData.resources || []).map((res) => {
                        const isExpanded = expandedResources[res.resource_id];
                        return (
                          <React.Fragment key={res.resource_id}>
                            <tr
                              className="hover:bg-[#F9FAFB] cursor-pointer"
                              onClick={() => setExpandedResources(prev => ({
                                ...prev,
                                [res.resource_id]: !prev[res.resource_id]
                              }))}
                            >
                              <td className="px-4 py-3">
                                <div className="flex items-center gap-3">
                                  <div className="w-8 h-8 rounded-full bg-[#1570EF] text-white text-sm flex items-center justify-center font-medium">
                                    {res.resource_name?.charAt(0) || '?'}
                                  </div>
                                  <div>
                                    <div className="font-medium text-[#0B1220]">{res.resource_name}</div>
                                    {res.resource_role && <div className="text-xs text-[#667085]">{res.resource_role}</div>}
                                  </div>
                                </div>
                              </td>
                              <td className="px-4 py-3 text-right text-sm font-medium text-[#0B1220]">{res.total_allocated_hours}h</td>
                              <td className="px-4 py-3 text-right text-sm font-medium text-[#0B1220]">{res.total_actual_hours}h</td>
                              <td className={`px-4 py-3 text-right text-sm font-semibold ${res.variance > 0 ? 'text-red-600' : res.variance < 0 ? 'text-amber-600' : 'text-green-600'}`}>
                                {res.variance > 0 ? '+' : ''}{res.variance}h
                              </td>
                              <td className="px-4 py-3 text-right">
                                <div className="flex items-center justify-end gap-2">
                                  <div className="w-20 bg-gray-200 rounded-full h-2">
                                    <div
                                      className={`h-2 rounded-full ${res.utilization_pct > 100 ? 'bg-red-500' : res.utilization_pct > 80 ? 'bg-green-500' : 'bg-amber-400'}`}
                                      style={{ width: `${Math.min(res.utilization_pct, 100)}%` }}
                                    />
                                  </div>
                                  <span className={`text-sm font-semibold min-w-[40px] text-right ${res.utilization_pct > 100 ? 'text-red-600' : res.utilization_pct > 80 ? 'text-green-600' : 'text-amber-600'}`}>
                                    {res.utilization_pct}%
                                  </span>
                                </div>
                              </td>
                              <td className="px-4 py-3 text-center">
                                {isExpanded ? <ChevronDown size={16} className="text-[#667085]" /> : <ChevronRight size={16} className="text-[#667085]" />}
                              </td>
                            </tr>
                            {/* Expanded Project Breakdown */}
                            {isExpanded && res.projects && res.projects.map((prj, pi) => (
                              <tr key={`${res.resource_id}-${prj.project_id || pi}`} className="bg-[#F9FAFB]">
                                <td className="px-4 py-2 pl-16">
                                  <div className="text-sm text-[#667085]">{prj.project_name}</div>
                                  {prj.client_name && <div className="text-xs text-[#98A2B3]">{prj.client_name}</div>}
                                </td>
                                <td className="px-4 py-2 text-right text-sm text-[#667085]">{prj.allocated_hours}h</td>
                                <td className="px-4 py-2 text-right text-sm text-[#667085]">{prj.actual_hours}h</td>
                                <td className={`px-4 py-2 text-right text-sm ${prj.variance > 0 ? 'text-red-500' : prj.variance < 0 ? 'text-amber-500' : 'text-green-500'}`}>
                                  {prj.variance > 0 ? '+' : ''}{prj.variance}h
                                </td>
                                <td className="px-4 py-2" colSpan={2}></td>
                              </tr>
                            ))}
                          </React.Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Empty state */}
              {(!utilizationData.resources || utilizationData.resources.length === 0) && (
                <div className="bg-white border border-[#E6E8EC] rounded-lg p-12 text-center">
                  <Users size={48} className="mx-auto text-[#98A2B3] mb-4" />
                  <h3 className="text-lg font-semibold text-[#0B1220] mb-2">No Utilization Data</h3>
                  <p className="text-sm text-[#667085]">No allocations found for the selected date range.</p>
                </div>
              )}
            </>
          ) : null}
        </>
      )}
    </div>
  );
};

export default TimesheetReports;
