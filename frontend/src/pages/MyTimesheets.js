import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getMyTimesheetHistory, autoFillTimesheets, submitWeekTimesheets } from '../api';
import { format, startOfWeek, addWeeks } from 'date-fns';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { Clock, AlertCircle, ChevronDown, ChevronRight, Zap, Send, CheckCircle } from 'lucide-react';
import { toast } from 'sonner';

const getCurrentWeekStart = () => {
  const monday = startOfWeek(new Date(), { weekStartsOn: 1 });
  return format(monday, 'yyyy-MM-dd');
};

const STATUS_COLORS = {
  Submitted: 'bg-green-100 text-green-700 border-green-200',
  Draft: 'bg-amber-100 text-amber-700 border-amber-200',
  Approved: 'bg-blue-100 text-blue-700 border-blue-200',
};

const WeekBlock = ({ week, isCurrentWeek, onAutofill, onSubmit, autofilling, submitting }) => {
  const [expanded, setExpanded] = useState(isCurrentWeek);
  const entries = week.entries || [];
  const allSubmitted = entries.length > 0 && entries.every((e) => e.status === 'Submitted');

  let weekLabel;
  try {
    weekLabel = `Week of ${format(new Date(week.week_start + 'T00:00:00'), 'MMM d, yyyy')}`;
  } catch {
    weekLabel = week.week_start;
  }

  return (
    <div
      className={`border rounded-xl overflow-hidden transition-all ${isCurrentWeek ? 'border-[#1570EF]/40 shadow-sm' : 'border-[#E4E7EC]'}`}
      data-testid={`week-block-${week.week_start}`}
    >
      {/* Week header row */}
      <div
        className={`flex items-center justify-between px-4 py-3 cursor-pointer select-none ${isCurrentWeek ? 'bg-[#1570EF]/5' : 'bg-[#F9FAFB]'}`}
        onClick={() => setExpanded((e) => !e)}
      >
        <div className="flex items-center gap-3">
          {expanded ? <ChevronDown size={16} className="text-[#667085]" /> : <ChevronRight size={16} className="text-[#667085]" />}
          <div>
            <span className="text-sm font-semibold text-[#101828]">{weekLabel}</span>
            {isCurrentWeek && (
              <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-[#1570EF] text-white font-medium">Current week</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-4">
          {entries.length > 0 ? (
            <>
              <span className="text-xs text-[#667085]">
                {week.total_actual?.toFixed(1)}h actual / {week.total_planned?.toFixed(1)}h planned
              </span>
              {allSubmitted ? (
                <CheckCircle size={16} className="text-green-600" />
              ) : (
                <span className="text-xs text-amber-600 font-medium">
                  {entries.filter((e) => e.status === 'Draft').length} draft
                </span>
              )}
            </>
          ) : (
            <span className="text-xs text-[#98A2B3]">No entries</span>
          )}
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-4">
          {/* Current week actions */}
          {isCurrentWeek && (
            <div className="flex gap-2 pt-3 pb-2">
              <Button
                size="sm"
                variant="outline"
                onClick={onAutofill}
                disabled={autofilling}
                className="h-8 text-xs gap-1.5"
                data-testid="autofill-btn"
              >
                <Zap size={13} className="text-[#1570EF]" />
                {autofilling ? 'Autofilling...' : 'Autofill from allocations'}
              </Button>
              {entries.some((e) => e.status === 'Draft') && (
                <Button
                  size="sm"
                  onClick={onSubmit}
                  disabled={submitting}
                  className="h-8 text-xs gap-1.5 bg-[#1570EF] hover:bg-[#0F5DC9]"
                  data-testid="submit-week-btn"
                >
                  <Send size={13} />
                  {submitting ? 'Submitting...' : 'Submit week'}
                </Button>
              )}
            </div>
          )}

          {entries.length === 0 ? (
            <p className="text-xs text-[#98A2B3] py-2">No timesheet entries for this week.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">Project</TableHead>
                  <TableHead className="text-xs">Phase</TableHead>
                  <TableHead className="text-xs text-right">Planned h</TableHead>
                  <TableHead className="text-xs text-right">Actual h</TableHead>
                  <TableHead className="text-xs">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.map((entry) => (
                  <TableRow key={entry.id} data-testid={`ts-row-${entry.id}`}>
                    <TableCell className="text-sm font-medium">{entry.project_name}</TableCell>
                    <TableCell className="text-xs text-[#667085]">{entry.phase_name}</TableCell>
                    <TableCell className="text-sm text-right">{entry.planned_hours?.toFixed(1)}</TableCell>
                    <TableCell className="text-sm text-right font-medium">{entry.actual_hours?.toFixed(1)}</TableCell>
                    <TableCell>
                      <Badge className={`text-xs border ${STATUS_COLORS[entry.status] || 'bg-gray-100 text-gray-600'}`}>
                        {entry.status || 'Draft'}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      )}
    </div>
  );
};

const MyTimesheets = () => {
  const queryClient = useQueryClient();
  const currentWeekStart = getCurrentWeekStart();
  const [weeksToLoad, setWeeksToLoad] = useState(12);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['myTimesheetHistory', weeksToLoad],
    queryFn: async () => {
      const res = await getMyTimesheetHistory(weeksToLoad);
      return res.data;
    },
  });

  const autofillMutation = useMutation({
    mutationFn: () => autoFillTimesheets(currentWeekStart),
    onSuccess: (res) => {
      const count = res.data?.created || res.data?.entries_created || 0;
      toast.success(`Autofilled ${count} timesheet entry(s) from your allocations`);
      queryClient.invalidateQueries(['myTimesheetHistory']);
      refetch();
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Autofill failed'),
  });

  const submitMutation = useMutation({
    mutationFn: () => submitWeekTimesheets(currentWeekStart),
    onSuccess: (res) => {
      toast.success(`Submitted ${res.data?.submitted_count || 0} timesheet entry(s)`);
      queryClient.invalidateQueries(['myTimesheetHistory']);
      refetch();
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Submission failed'),
  });

  const resource = data?.resource;
  const weeks = data?.weeks || [];

  return (
    <div className="max-w-4xl mx-auto space-y-6" data-testid="my-timesheets-page">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-[#0B1220]">My Timesheets</h1>
        {resource && (
          <p className="text-sm text-[#667085] mt-1">
            {resource.name} · {resource.role}
          </p>
        )}
      </div>

      {/* Read-only warning banner */}
      <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-50 border border-amber-200" data-testid="readonly-banner">
        <AlertCircle size={18} className="text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-amber-800">Timesheet history is read-only</p>
          <p className="text-xs text-amber-700 mt-0.5">
            To correct or edit past entries, please contact your admin. You can autofill and submit the <strong>current week</strong> below.
          </p>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="text-center py-12 text-[#667085]">
          <Clock className="animate-pulse mx-auto mb-3" size={32} />
          Loading your timesheet history...
        </div>
      ) : !resource ? (
        <div className="text-center py-12 border border-dashed border-[#D0D5DD] rounded-xl">
          <Clock size={32} className="text-[#D0D5DD] mx-auto mb-3" />
          <p className="text-[#667085]">No resource profile linked to your account.</p>
          <p className="text-xs text-[#98A2B3] mt-1">Contact your admin to set up your profile.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {/* Ensure current week always appears first even if no entries */}
          {!weeks.find((w) => w.week_start === currentWeekStart) && (
            <WeekBlock
              key="current-empty"
              week={{ week_start: currentWeekStart, entries: [], total_planned: 0, total_actual: 0 }}
              isCurrentWeek
              onAutofill={() => autofillMutation.mutate()}
              onSubmit={() => submitMutation.mutate()}
              autofilling={autofillMutation.isPending}
              submitting={submitMutation.isPending}
            />
          )}
          {weeks.map((week) => (
            <WeekBlock
              key={week.week_start}
              week={week}
              isCurrentWeek={week.week_start === currentWeekStart}
              onAutofill={() => autofillMutation.mutate()}
              onSubmit={() => submitMutation.mutate()}
              autofilling={autofillMutation.isPending}
              submitting={submitMutation.isPending}
            />
          ))}

          {/* Load more */}
          {weeks.length >= weeksToLoad && (
            <div className="text-center pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setWeeksToLoad((n) => n + 12)}
                className="text-xs"
              >
                Load older weeks
              </Button>
            </div>
          )}

          {weeks.length === 0 && (
            <div className="text-center py-8 text-[#98A2B3] text-sm">
              No timesheet entries found in the last {weeksToLoad} weeks.
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default MyTimesheets;
