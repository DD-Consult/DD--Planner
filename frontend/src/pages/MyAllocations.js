import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getMyAllocations } from '../api';
import { format, parseISO } from 'date-fns';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Calendar, Clock, Briefcase, AlertTriangle, TrendingUp, User } from 'lucide-react';
import { formatAllocation } from '../utils/capacityHelpers';

const MyAllocations = () => {
  const [period, setPeriod] = useState('month');

  const { data, isLoading, error } = useQuery({
    queryKey: ['my-allocations', period],
    queryFn: async () => {
      const response = await getMyAllocations(period);
      return response.data;
    },
  });

  // Helper to format dates
  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      return format(parseISO(dateStr), 'MMM d');
    } catch {
      return dateStr;
    }
  };

  // Determine capacity color
  const getCapacityColor = (percentage) => {
    if (percentage < 80) return 'text-green-600 bg-green-50 border-green-200';
    if (percentage <= 100) return 'text-amber-600 bg-amber-50 border-amber-200';
    return 'text-red-600 bg-red-50 border-red-200';
  };

  // Project status badge colors
  const getStatusColor = (status) => {
    const statusMap = {
      'Active': 'bg-green-100 text-green-800',
      'Pipeline': 'bg-blue-100 text-blue-800',
      'On Hold': 'bg-amber-100 text-amber-800',
      'Completed': 'bg-gray-100 text-gray-800',
      'Cancelled': 'bg-red-100 text-red-800',
    };
    return statusMap[status] || 'bg-gray-100 text-gray-800';
  };

  // Confirmation status badge
  const getConfirmationBadge = (status) => {
    const statusMap = {
      'Confirmed': { color: 'bg-green-100 text-green-800', label: 'Confirmed' },
      'Tentative': { color: 'bg-amber-100 text-amber-800', label: 'Tentative' },
      'Declined': { color: 'bg-red-100 text-red-800', label: 'Declined' },
    };
    return statusMap[status] || { color: 'bg-gray-100 text-gray-800', label: status || 'Pending' };
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#1570EF] mx-auto mb-4"></div>
          <p className="text-[#667085]">Loading your allocations...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <p className="text-red-600">Failed to load allocations</p>
        </div>
      </div>
    );
  }

  const resource = data?.resource;
  const summary = data?.summary || {};
  const allocations = data?.allocations || [];
  const periodStart = data?.period_start;
  const periodEnd = data?.period_end;

  return (
    <div className="max-w-7xl mx-auto" data-testid="my-allocations-page">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-[#0B1220] mb-2">My Allocations</h1>
        {resource ? (
          <div className="flex items-center gap-2 text-[#667085]">
            <User size={18} />
            <span className="font-medium text-[#0B1220]">{resource.name}</span>
            <span>•</span>
            <span>{resource.role}</span>
            {resource.standard_capacity && (
              <>
                <span>•</span>
                <span>Standard Capacity: {resource.standard_capacity}%</span>
              </>
            )}
          </div>
        ) : (
          <p className="text-[#667085]">No resource profile linked to your account</p>
        )}
      </div>

      {/* Period Selector */}
      <div className="mb-6 flex gap-3" data-testid="period-selector">
        <Button
          variant={period === 'week' ? 'default' : 'outline'}
          onClick={() => setPeriod('week')}
          className={period === 'week' ? 'bg-[#1570EF] text-white' : ''}
          data-testid="period-button-week"
        >
          This & Next Week
        </Button>
        <Button
          variant={period === 'month' ? 'default' : 'outline'}
          onClick={() => setPeriod('month')}
          className={period === 'month' ? 'bg-[#1570EF] text-white' : ''}
          data-testid="period-button-month"
        >
          This Month
        </Button>
        <Button
          variant={period === '3months' ? 'default' : 'outline'}
          onClick={() => setPeriod('3months')}
          className={period === '3months' ? 'bg-[#1570EF] text-white' : ''}
          data-testid="period-button-3months"
        >
          Next 3 Months
        </Button>
      </div>

      {!resource ? (
        <div className="bg-white border border-[#E6E8EC] rounded-lg p-12 text-center">
          <User className="h-16 w-16 text-[#98A2B3] mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-[#0B1220] mb-2">No Resource Profile</h3>
          <p className="text-[#667085] max-w-md mx-auto">
            Your account is not linked to a resource profile. Please contact your administrator to set up your profile.
          </p>
        </div>
      ) : (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {/* Total Allocations */}
            <div className="bg-white border border-[#E6E8EC] rounded-lg p-5" data-testid="summary-total-allocations">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-[#667085]">Total Allocations</span>
                <Briefcase className="h-5 w-5 text-[#98A2B3]" />
              </div>
              <div className="text-3xl font-bold text-[#0B1220]">{summary.total_allocations || 0}</div>
            </div>

            {/* Capacity Used */}
            <div className={`border rounded-lg p-5 ${getCapacityColor(summary.capacity_used_percentage || 0)}`} data-testid="summary-capacity">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm">Capacity Used</span>
                <TrendingUp className="h-5 w-5" />
              </div>
              <div className="text-3xl font-bold">{summary.capacity_used_percentage || 0}%</div>
            </div>

            {/* Hours per Week */}
            <div className="bg-white border border-[#E6E8EC] rounded-lg p-5" data-testid="summary-hours-per-week">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-[#667085]">Hours / Week</span>
                <Clock className="h-5 w-5 text-[#98A2B3]" />
              </div>
              <div className="text-3xl font-bold text-[#0B1220]">{(summary.total_weekly_hours || 0).toFixed(1)}h</div>
            </div>

            {/* Period Range */}
            <div className="bg-white border border-[#E6E8EC] rounded-lg p-5" data-testid="summary-period-range">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-[#667085]">Period</span>
                <Calendar className="h-5 w-5 text-[#98A2B3]" />
              </div>
              <div className="text-sm font-medium text-[#0B1220]">
                {periodStart && periodEnd ? `${formatDate(periodStart)} → ${formatDate(periodEnd)}` : 'N/A'}
              </div>
            </div>
          </div>

          {/* Over-Capacity Warning */}
          {summary.is_over_capacity && (
            <div
              className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 flex items-start gap-3"
              data-testid="over-capacity-banner"
            >
              <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
              <div>
                <h4 className="font-semibold text-red-900 mb-1">⚠️ You are over-capacity this period</h4>
                <p className="text-sm text-red-700">
                  Current: <span className="font-semibold">{summary.capacity_used_percentage}%</span> of standard capacity{' '}
                  ({summary.standard_capacity || 100}%)
                </p>
              </div>
            </div>
          )}

          {/* Allocations List */}
          <div className="space-y-4">
            {allocations.length === 0 ? (
              <div className="bg-white border border-[#E6E8EC] rounded-lg p-12 text-center">
                <Briefcase className="h-16 w-16 text-[#98A2B3] mx-auto mb-4" />
                <h3 className="text-xl font-semibold text-[#0B1220] mb-2">No allocations in this period</h3>
                <p className="text-[#667085]">You don't have any project allocations during this time frame.</p>
              </div>
            ) : (
              allocations.map((alloc, idx) => {
                const confirmationBadge = getConfirmationBadge(alloc.confirmation_status);
                return (
                  <div
                    key={alloc.id}
                    className="bg-white border border-[#E6E8EC] rounded-lg p-6 hover:shadow-md transition-shadow"
                    data-testid={`allocation-card-${idx}`}
                  >
                    {/* Top Row: Project Name + Status */}
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1">
                        <Link
                          to={`/projects/${alloc.project_id}`}
                          className="text-xl font-bold text-[#0B1220] hover:text-[#1570EF] transition-colors"
                        >
                          {alloc.project_name}
                        </Link>
                        <div className="flex items-center gap-2 mt-1 text-sm text-[#667085]">
                          <span>{alloc.client_name}</span>
                          {alloc.role && (
                            <>
                              <span>•</span>
                              <span>{alloc.role}</span>
                            </>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge className={getStatusColor(alloc.project_status)}>{alloc.project_status}</Badge>
                        <Badge className={confirmationBadge.color}>{confirmationBadge.label}</Badge>
                      </div>
                    </div>

                    {/* Allocation Details (4-column grid) */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                      <div>
                        <div className="text-xs text-[#667085] mb-1">Allocation</div>
                        <div className="text-base font-semibold text-[#0B1220]">
                          {alloc.percentage !== null && alloc.percentage !== undefined ? formatAllocation(alloc.percentage, summary?.standard_capacity || 100) : 
                           alloc.hours !== null && alloc.hours !== undefined ? `${alloc.hours}h` : 'N/A'}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-[#667085] mb-1">Duration</div>
                        <div className="text-base font-semibold text-[#0B1220]">
                          {alloc.start_date && alloc.end_date
                            ? `${formatDate(alloc.start_date)} → ${formatDate(alloc.end_date)}`
                            : 'N/A'}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-[#667085] mb-1">Hours / Week</div>
                        <div className="text-base font-semibold text-[#0B1220]">
                          {alloc.weekly_hours !== null && alloc.weekly_hours !== undefined
                            ? `${alloc.weekly_hours.toFixed(1)}h`
                            : 'N/A'}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-[#667085] mb-1">Total in Period</div>
                        <div className="text-base font-semibold text-[#0B1220]">
                          {alloc.period_hours !== null && alloc.period_hours !== undefined
                            ? `${alloc.period_hours.toFixed(1)}h`
                            : 'N/A'}
                        </div>
                      </div>
                    </div>

                    {/* Phases */}
                    {alloc.phase_names && alloc.phase_names.length > 0 && (
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs text-[#667085]">Phases:</span>
                        {alloc.phase_names.map((phase, pidx) => (
                          <Badge
                            key={pidx}
                            variant="outline"
                            className="bg-[#F0F9FF] text-[#1570EF] border-[#1570EF]/20"
                          >
                            {phase}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default MyAllocations;
