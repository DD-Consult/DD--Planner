import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, Link } from 'react-router-dom';
import {
  format, parseISO, startOfWeek, endOfWeek, isWithinInterval,
  areIntervalsOverlapping, addDays, isFuture, isPast,
} from 'date-fns';
import { getMyAllocations, getMyTimesheetHistory, getLeaves, getActionItems } from '../api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Progress } from '../components/ui/progress';
import {
  Clock, Briefcase, Calendar, CheckCircle2, AlertTriangle,
  ChevronRight, TrendingUp, Bell, X, ChevronDown, ChevronUp,
  FileText, ClipboardList, Flag, Palmtree, ArrowRight,
} from 'lucide-react';

// ─── helpers ──────────────────────────────────────────────────────────────────

const today = new Date();
const weekStart = startOfWeek(today, { weekStartsOn: 1 }); // Monday
const weekEnd   = addDays(weekStart, 4);                    // Friday

function getAllocationsThisWeek(allocations = []) {
  return allocations.filter(a => {
    try {
      return areIntervalsOverlapping(
        { start: parseISO(a.start_date), end: parseISO(a.end_date) },
        { start: weekStart, end: weekEnd }
      );
    } catch { return false; }
  });
}

function timesheetStatusFromActionItems(actionItems = []) {
  const types = actionItems.map(i => i.type);
  if (types.includes('missing_timesheet')) return 'missing';
  if (types.includes('draft_timesheet'))   return 'draft';
  return 'ok';
}

const STATUS_CONFIG = {
  missing: { label: 'Not Submitted', color: 'bg-red-100 text-red-700 border-red-200' },
  draft:   { label: 'Draft',         color: 'bg-amber-100 text-amber-700 border-amber-200' },
  ok:      { label: 'Up to Date',    color: 'bg-green-100 text-green-700 border-green-200' },
};

const ACTION_ICON_MAP = {
  missing_timesheet:     { Icon: Clock,         color: '#EF4444' },
  draft_timesheet:       { Icon: FileText,       color: '#F59E0B' },
  status_update_due:     { Icon: ClipboardList,  color: '#1570EF' },
  budget_alert_critical: { Icon: AlertTriangle,  color: '#EF4444' },
  budget_alert_warning:  { Icon: AlertTriangle,  color: '#F59E0B' },
  allocation_ending:     { Icon: Calendar,       color: '#F97316' },
  overdue_milestone:     { Icon: Flag,           color: '#9333EA' },
};
const SEVERITY_STYLES = {
  high:   { bg: 'bg-red-50',   border: 'border-red-200',   badge: 'bg-red-100 text-red-800'   },
  medium: { bg: 'bg-amber-50', border: 'border-amber-200', badge: 'bg-amber-100 text-amber-800' },
  low:    { bg: 'bg-blue-50',  border: 'border-blue-200',  badge: 'bg-blue-100 text-blue-800'  },
};

// ─── sub-components ───────────────────────────────────────────────────────────

function KpiCard({ icon: Icon, iconColor, label, value, sub, testId }) {
  return (
    <Card data-testid={testId}>
      <CardContent className="p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="w-9 h-9 rounded-lg bg-[#F7F7F8] flex items-center justify-center">
            <Icon size={18} style={{ color: iconColor }} />
          </div>
        </div>
        <div className="text-xs text-[#667085] mb-1">{label}</div>
        <div className="text-2xl font-semibold text-[#0B1220]">{value}</div>
        {sub && <div className="text-xs text-[#98A2B3] mt-0.5">{sub}</div>}
      </CardContent>
    </Card>
  );
}

function WeekBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.ok;
  return (
    <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${cfg.color}`}>
      {cfg.label}
    </span>
  );
}

// ─── main component ───────────────────────────────────────────────────────────

export default function ResourceDashboard({ userData }) {
  const navigate = useNavigate();
  const [actionsDismissed, setActionsDismissed] = useState(false);
  const [actionsExpanded, setActionsExpanded] = useState(false);

  const { data: myAllocsData } = useQuery({
    queryKey: ['myAllocations', 'month'],
    queryFn: async () => { const r = await getMyAllocations('month'); return r.data; },
  });

  const { data: timesheetData } = useQuery({
    queryKey: ['myTimesheetHistory', 4],
    queryFn: async () => { const r = await getMyTimesheetHistory(4); return r.data; },
  });

  const { data: leavesData } = useQuery({
    queryKey: ['leaves'],
    queryFn: async () => { const r = await getLeaves(); return r.data; },
  });

  const { data: actionItemsData } = useQuery({
    queryKey: ['actionItems'],
    queryFn: async () => { const r = await getActionItems(); return r.data; },
    refetchInterval: 5 * 60 * 1000,
  });

  // ── derived ────────────────────────────────────────────────────────────────

  const resource  = myAllocsData?.resource || {};
  const allAllocs = useMemo(() => myAllocsData?.allocations || [], [myAllocsData]);

  const thisWeekAllocs = useMemo(() => getAllocationsThisWeek(allAllocs), [allAllocs]);
  const totalUtilPct   = useMemo(() => Math.min(100, thisWeekAllocs.reduce((s, a) => s + (a.percentage || 0), 0)), [thisWeekAllocs]);
  const totalHrsWeek   = useMemo(() => thisWeekAllocs.reduce((s, a) => s + (a.weekly_hours || 0), 0), [thisWeekAllocs]);

  const activeAllocs  = useMemo(() => allAllocs.filter(a => {
    try { return !isPast(parseISO(a.end_date)); } catch { return false; }
  }), [allAllocs]);

  const tsStatus = useMemo(
    () => timesheetStatusFromActionItems(actionItemsData?.action_items || []),
    [actionItemsData]
  );

  const recentWeeks = useMemo(() => {
    const weeks = timesheetData?.weeks || [];
    return weeks.slice(0, 4);
  }, [timesheetData]);

  const upcomingLeaves = useMemo(() => {
    if (!Array.isArray(leavesData)) return [];
    return leavesData
      .filter(l => {
        try { return !isPast(parseISO(l.end_date)); } catch { return false; }
      })
      .sort((a, b) => new Date(a.start_date) - new Date(b.start_date))
      .slice(0, 3);
  }, [leavesData]);

  const greetingHour = today.getHours();
  const greeting = greetingHour < 12 ? 'Good morning' : greetingHour < 17 ? 'Good afternoon' : 'Good evening';
  const displayName = resource.name || userData?.email?.split('@')[0] || 'there';

  // ── render ─────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">

      {/* ── Header ── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-semibold" style={{ fontFamily: 'Space Grotesk' }} data-testid="resource-dashboard-title">
            {greeting}, {displayName.split(' ')[0]}
          </h1>
          <p className="text-sm text-[#667085] mt-1">
            {resource.role ? `${resource.role} · ` : ''}{format(today, 'EEEE, MMMM d yyyy')}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => navigate('/my-timesheets')} data-testid="view-timesheets-btn">
          <FileText size={14} className="mr-1.5" /> My Timesheets
        </Button>
      </div>

      {/* ── Action Items Banner ── */}
      {actionItemsData?.summary?.total > 0 && !actionsDismissed && (
        <Card className="border-l-4 border-l-[#F97316] bg-gradient-to-r from-orange-50 to-white" data-testid="action-items-banner">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Bell className="w-5 h-5 text-[#F97316]" />
                <span className="font-semibold text-[#0B1220] text-sm">
                  {actionItemsData.summary.total} item{actionItemsData.summary.total !== 1 ? 's' : ''} need your attention
                </span>
                {actionItemsData.summary.high > 0 && (
                  <Badge className="bg-red-100 text-red-800 text-xs">
                    {actionItemsData.summary.high} high priority
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-1">
                <Button variant="ghost" size="sm" onClick={() => setActionsExpanded(!actionsExpanded)} className="text-[#1570EF] text-xs">
                  {actionsExpanded ? <><ChevronUp className="w-3.5 h-3.5 mr-1" />Hide</> : <><ChevronDown className="w-3.5 h-3.5 mr-1" />Show All</>}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setActionsDismissed(true)} className="text-[#667085]">
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {actionsExpanded && (
              <div className="space-y-2 mt-3 pt-3 border-t border-[#E6E8EC]">
                {actionItemsData.action_items.map(item => {
                  const { Icon, color } = ACTION_ICON_MAP[item.type] || { Icon: Bell, color: '#667085' };
                  const s = SEVERITY_STYLES[item.severity] || SEVERITY_STYLES.low;
                  return (
                    <div key={item.id} className={`flex items-center justify-between p-3 rounded-lg border ${s.border} ${s.bg}`} data-testid={`action-item-${item.id}`}>
                      <div className="flex items-center gap-3">
                        <Icon size={16} style={{ color }} />
                        <div>
                          <div className="text-sm font-medium text-[#0B1220]">{item.title}</div>
                          <div className="text-xs text-[#667085]">{item.message}</div>
                        </div>
                      </div>
                      <Link to={item.action_url} className="text-xs font-medium text-[#1570EF] hover:underline whitespace-nowrap ml-4" data-testid={`action-item-link-${item.id}`}>
                        Go →
                      </Link>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Timesheet Nudge (standalone if no action items banner) ── */}
      {tsStatus === 'missing' && actionsDismissed && (
        <Card className="border-l-4 border-l-[#EF4444] bg-red-50" data-testid="timesheet-nudge">
          <CardContent className="p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Clock className="w-5 h-5 text-[#EF4444]" />
              <div>
                <p className="font-semibold text-sm text-[#0B1220]">Timesheet not submitted</p>
                <p className="text-xs text-[#667085]">Week of {format(weekStart, 'MMM d')} – {format(weekEnd, 'MMM d')}</p>
              </div>
            </div>
            <Button size="sm" onClick={() => navigate('/my-timesheets')} className="bg-[#EF4444] hover:bg-red-600 text-white" data-testid="nudge-submit-btn">
              Submit Now
            </Button>
          </CardContent>
        </Card>
      )}

      {/* ── KPI Row ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" data-testid="resource-kpi-row">
        <KpiCard
          icon={TrendingUp}
          iconColor="#1570EF"
          label="My Utilization This Week"
          value={`${totalUtilPct}%`}
          sub={thisWeekAllocs.length ? `${thisWeekAllocs.length} project${thisWeekAllocs.length !== 1 ? 's' : ''}` : 'No active allocations'}
          testId="kpi-my-utilization"
        />
        <KpiCard
          icon={Clock}
          iconColor="#7839EE"
          label="My Hours This Week"
          value={`${totalHrsWeek.toFixed(0)}h`}
          sub="based on 40h/week"
          testId="kpi-my-hours"
        />
        <KpiCard
          icon={Briefcase}
          iconColor="#16B364"
          label="Active Projects"
          value={activeAllocs.length}
          sub={activeAllocs.length === 0 ? 'No current work' : 'allocated to you'}
          testId="kpi-active-projects"
        />
        <Card data-testid="kpi-timesheet-status">
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="w-9 h-9 rounded-lg bg-[#F7F7F8] flex items-center justify-center">
                {tsStatus === 'ok'
                  ? <CheckCircle2 size={18} style={{ color: '#16B364' }} />
                  : <AlertTriangle size={18} style={{ color: tsStatus === 'missing' ? '#EF4444' : '#F59E0B' }} />
                }
              </div>
            </div>
            <div className="text-xs text-[#667085] mb-1">Timesheet Status</div>
            <WeekBadge status={tsStatus} />
            <div className="text-xs text-[#98A2B3] mt-1">
              Week of {format(weekStart, 'MMM d')}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── Main two-column layout ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left: My Allocations (2/3 width) */}
        <div className="lg:col-span-2 space-y-4">
          <Card data-testid="my-allocations-card">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base" style={{ fontFamily: 'Space Grotesk' }}>My Allocations</CardTitle>
                <Link to="/my-allocations" className="text-xs font-medium text-[#1570EF] hover:underline flex items-center gap-1" data-testid="view-all-allocations-link">
                  View all <ArrowRight size={12} />
                </Link>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              {activeAllocs.length === 0 ? (
                <div className="text-center py-8 text-[#98A2B3]">
                  <Briefcase size={32} className="mx-auto mb-2 opacity-40" />
                  <p className="text-sm">No active allocations</p>
                  <p className="text-xs mt-1">Contact your admin to get assigned to a project</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {activeAllocs.map(alloc => {
                    const isActive = !isPast(parseISO(alloc.end_date)) && !isFuture(parseISO(alloc.start_date));
                    const isUpcoming = isFuture(parseISO(alloc.start_date));
                    return (
                      <div
                        key={alloc.id}
                        className="flex items-center justify-between p-3 rounded-lg border border-[#E6E8EC] hover:bg-[#F8FAFC] transition-colors"
                        data-testid={`alloc-row-${alloc.id}`}
                      >
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <div className="w-8 h-8 rounded-md bg-[#EEF4FF] flex items-center justify-center shrink-0">
                            <Briefcase size={14} className="text-[#1570EF]" />
                          </div>
                          <div className="min-w-0">
                            <div className="font-medium text-sm text-[#0B1220] truncate">{alloc.project_name}</div>
                            <div className="text-xs text-[#667085] truncate">{alloc.client_name} · {alloc.role || 'Team Member'}</div>
                          </div>
                        </div>
                        <div className="flex items-center gap-4 shrink-0 ml-3">
                          <div className="text-right hidden sm:block">
                            <div className="text-xs text-[#667085]">
                              {format(parseISO(alloc.start_date), 'MMM d')} – {format(parseISO(alloc.end_date), 'MMM d')}
                            </div>
                            <div className="text-xs text-[#98A2B3]">
                              {alloc.confirmation_status === 'Confirmed' ? '✓ Confirmed' : alloc.confirmation_status}
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-sm font-semibold text-[#0B1220]">{alloc.percentage}%</div>
                            <div className="text-xs text-[#667085]">{alloc.weekly_hours?.toFixed(0)}h/wk</div>
                          </div>
                          <div className="w-16">
                            <Progress value={alloc.percentage} className="h-1.5" />
                          </div>
                          <Badge
                            className={`text-xs shrink-0 ${
                              isUpcoming
                                ? 'bg-blue-100 text-blue-700'
                                : isActive
                                  ? 'bg-green-100 text-green-700'
                                  : 'bg-gray-100 text-gray-600'
                            }`}
                          >
                            {isUpcoming ? 'Upcoming' : isActive ? 'Active' : 'Ending'}
                          </Badge>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right sidebar: Timesheet history + Leaves */}
        <div className="space-y-4">

          {/* Recent Timesheets */}
          <Card data-testid="recent-timesheets-card">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base" style={{ fontFamily: 'Space Grotesk' }}>Recent Timesheets</CardTitle>
                <Link to="/my-timesheets" className="text-xs font-medium text-[#1570EF] hover:underline flex items-center gap-1" data-testid="view-timesheets-link">
                  History <ArrowRight size={12} />
                </Link>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              {recentWeeks.length === 0 ? (
                <div className="text-center py-6 text-[#98A2B3]">
                  <Clock size={28} className="mx-auto mb-2 opacity-40" />
                  <p className="text-xs">No timesheet history</p>
                  <Button size="sm" variant="outline" className="mt-3 text-xs" onClick={() => navigate('/my-timesheets')} data-testid="go-submit-timesheets-btn">
                    Submit your first timesheet
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  {recentWeeks.map(week => {
                    const submitted = week.entries?.some(e => e.status === 'submitted');
                    const hasDraft  = week.entries?.some(e => e.status === 'draft');
                    const weekStatus = submitted ? 'submitted' : hasDraft ? 'draft' : 'missing';
                    return (
                      <div key={week.week_start} className="flex items-center justify-between py-2 border-b border-[#F2F4F7] last:border-0" data-testid={`ts-week-${week.week_start}`}>
                        <div>
                          <div className="text-xs font-medium text-[#0B1220]">
                            {format(parseISO(week.week_start), 'MMM d')} – {format(addDays(parseISO(week.week_start), 4), 'MMM d')}
                          </div>
                          <div className="text-xs text-[#667085]">
                            {(week.entries || []).reduce((s, e) => s + (e.actual_hours || 0), 0).toFixed(0)}h logged
                          </div>
                        </div>
                        <WeekBadge status={weekStatus} />
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Upcoming Leaves */}
          <Card data-testid="upcoming-leaves-card">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base" style={{ fontFamily: 'Space Grotesk' }}>My Leaves</CardTitle>
                <Link to="/time-off" className="text-xs font-medium text-[#1570EF] hover:underline flex items-center gap-1" data-testid="manage-leaves-link">
                  Manage <ArrowRight size={12} />
                </Link>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              {upcomingLeaves.length === 0 ? (
                <div className="text-center py-6 text-[#98A2B3]">
                  <Palmtree size={28} className="mx-auto mb-2 opacity-40" />
                  <p className="text-xs">No upcoming leaves</p>
                  <Button size="sm" variant="outline" className="mt-3 text-xs" onClick={() => navigate('/time-off')} data-testid="add-leave-btn">
                    Add time off
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  {upcomingLeaves.map(leave => (
                    <div key={leave.id} className="flex items-center justify-between py-2 border-b border-[#F2F4F7] last:border-0" data-testid={`leave-row-${leave.id}`}>
                      <div>
                        <div className="text-xs font-medium text-[#0B1220] capitalize">{leave.type || 'Leave'}</div>
                        <div className="text-xs text-[#667085]">
                          {format(parseISO(leave.start_date), 'MMM d')} – {format(parseISO(leave.end_date), 'MMM d')}
                        </div>
                      </div>
                      <Badge className={`text-xs ${
                        leave.status === 'approved' ? 'bg-green-100 text-green-700' :
                        leave.status === 'rejected' ? 'bg-red-100 text-red-700' :
                        'bg-amber-100 text-amber-700'
                      }`}>
                        {leave.status || 'pending'}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

        </div>
      </div>

    </div>
  );
}
