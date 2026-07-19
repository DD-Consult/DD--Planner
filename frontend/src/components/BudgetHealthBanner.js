import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getBudgetHealth } from '../api';
import { Progress } from './ui/progress';
import { AlertTriangle, AlertOctagon } from 'lucide-react';

const BudgetHealthBanner = ({ projectId, compact = false }) => {
  const { data, isLoading } = useQuery({
    queryKey: ['budget-health', projectId],
    queryFn: async () => {
      const response = await getBudgetHealth(projectId);
      return response.data;
    },
    enabled: !!projectId,
    staleTime: 30000, // 30 seconds
  });

  // Don't show banner if loading, no data, status is ok, or no budget
  if (isLoading || !data) return null;
  if (data.status === 'ok' || data.status === 'no_budget') return null;

  const isExceeded = data.status === 'exceeded';
  const isWarning = data.status === 'warning';

  // Color scheme based on status
  const bgColor = isExceeded ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200';
  const textColor = isExceeded ? 'text-red-900' : 'text-amber-900';
  const iconColor = isExceeded ? 'text-red-600' : 'text-amber-600';
  const progressColor = isExceeded ? 'bg-red-500' : 'bg-amber-500';

  const Icon = isExceeded ? AlertOctagon : AlertTriangle;

  const headline = isExceeded
    ? `Budget Exceeded: ${data.usage_percentage?.toFixed(1)}% of project hours allocated`
    : `Budget Warning: ${data.usage_percentage?.toFixed(1)}% of project hours allocated`;

  const subtext = `Budgeted: ${data.budgeted_hours?.toFixed(0) || 0}h • Allocated: ${data.allocated_hours?.toFixed(0) || 0}h • Remaining: ${data.remaining_hours?.toFixed(0) || 0}h`;

  if (compact) {
    return (
      <div 
        className={`flex items-center gap-2 px-3 py-2 rounded-md border ${bgColor}`}
        data-testid="budget-health-banner"
        data-status={data.status}
      >
        <Icon className={`w-4 h-4 flex-shrink-0 ${iconColor}`} />
        <span className={`text-xs font-medium ${textColor}`}>
          {data.usage_percentage?.toFixed(0)}% Budget Used
        </span>
      </div>
    );
  }

  return (
    <div 
      className={`rounded-lg border p-4 ${bgColor}`}
      data-testid="budget-health-banner"
      data-status={data.status}
    >
      <div className="flex gap-3">
        <Icon className={`w-5 h-5 flex-shrink-0 mt-0.5 ${iconColor}`} />
        
        <div className="flex-1 space-y-2">
          <div>
            <p className={`font-semibold text-sm ${textColor}`}>
              {headline}
            </p>
            <p className={`text-xs mt-1 ${textColor} opacity-80`}>
              {subtext}
            </p>
          </div>

          {/* Progress bar visualization */}
          <div className="space-y-1">
            <div className="relative">
              <Progress 
                value={Math.min(data.usage_percentage || 0, 100)} 
                className="h-2 bg-white/50"
              />
              <div 
                className={`absolute top-0 left-0 h-2 rounded-full transition-all ${progressColor}`}
                style={{ width: `${Math.min(data.usage_percentage || 0, 100)}%` }}
              />
            </div>
            <div className="flex justify-between text-xs opacity-75">
              <span className={textColor}>0h</span>
              <span className={textColor}>{data.budgeted_hours?.toFixed(0) || 0}h</span>
            </div>
          </div>

          {/* Phase breakdown if exceeded */}
          {isExceeded && data.phase_breakdown && data.phase_breakdown.length > 0 && (
            <details className="text-xs mt-2">
              <summary className={`cursor-pointer font-medium ${textColor} opacity-80`}>
                View phase breakdown
              </summary>
              <div className="mt-2 space-y-1 pl-2 border-l-2 border-red-300">
                {data.phase_breakdown.map((phase, idx) => (
                  <div key={idx} className="flex justify-between">
                    <span className={textColor}>{phase.phase_name}:</span>
                    <span className={`font-medium ${phase.status === 'exceeded' ? 'text-red-700' : textColor}`}>
                      {phase.allocated_hours?.toFixed(0)}h / {phase.budgeted_hours?.toFixed(0)}h
                      ({phase.usage_percentage?.toFixed(0)}%)
                    </span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      </div>
    </div>
  );
};

export default BudgetHealthBanner;
