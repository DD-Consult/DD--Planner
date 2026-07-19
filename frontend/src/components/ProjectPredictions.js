import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getProjectPredictions } from '../api';
import { Sparkles, Calendar, TrendingUp, DollarSign, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { format, parseISO } from 'date-fns';

const ProjectPredictions = ({ projectId }) => {
  const { data: predictions, isLoading } = useQuery({
    queryKey: ['projectPredictions', projectId],
    queryFn: async () => {
      const response = await getProjectPredictions(projectId);
      return response.data;
    },
    enabled: !!projectId,
    staleTime: 2 * 60 * 1000, // Cache for 2 minutes
  });

  if (isLoading) {
    return (
      <Card data-testid="project-predictions-loading">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2" style={{ fontFamily: 'Space Grotesk' }}>
            <Sparkles size={20} className="text-[#9333EA]" />
            Predictions & Forecasts
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <p className="text-sm text-[#667085]">Loading predictions...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!predictions) {
    return (
      <Card data-testid="project-predictions-error">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2" style={{ fontFamily: 'Space Grotesk' }}>
            <Sparkles size={20} className="text-[#9333EA]" />
            Predictions & Forecasts
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <p className="text-sm text-[#667085]">Predictions unavailable</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Safe date formatting
  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    try {
      return format(parseISO(dateStr), 'MMM d, yyyy');
    } catch {
      return dateStr;
    }
  };

  // Status badge styling
  const getStatusStyle = (status) => {
    const styles = {
      'On Track': { bg: 'bg-[#16B364]', text: 'text-white', icon: CheckCircle2 },
      'At Risk': { bg: 'bg-[#F4B740]', text: 'text-white', icon: AlertTriangle },
      'Critical': { bg: 'bg-[#EF4444]', text: 'text-white', icon: AlertTriangle },
    };
    return styles[status] || styles['At Risk'];
  };

  const statusStyle = getStatusStyle(predictions.status);
  const StatusIcon = statusStyle.icon;

  const velocity = predictions.velocity || {};
  const budgetPred = predictions.budget_prediction || {};

  return (
    <Card data-testid="project-predictions">
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2" style={{ fontFamily: 'Space Grotesk' }}>
          <Sparkles size={20} className="text-[#9333EA]" />
          Predictions & Forecasts
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Completion Date Prediction */}
        <div className="space-y-2" data-testid="completion-prediction">
          <div className="flex items-center gap-2 text-sm font-semibold text-[#475467]">
            <Calendar size={16} />
            <span>Completion</span>
          </div>
          <div className="pl-6 space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="text-[#667085]">Planned:</span>
              <span className="font-medium text-[#0B1220]">{formatDate(predictions.planned_end_date)}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-[#667085]">Predicted:</span>
              <span className="font-medium text-[#0B1220]">{formatDate(predictions.predicted_end_date)}</span>
            </div>
            
            {predictions.variance_days !== undefined && predictions.variance_days !== 0 && (
              <div className="flex items-center justify-between pt-2 border-t border-[#E6E8EC]">
                <div className="flex items-center gap-2">
                  {predictions.variance_days > 0 ? (
                    <AlertTriangle size={16} className="text-[#F97316]" />
                  ) : (
                    <CheckCircle2 size={16} className="text-[#16B364]" />
                  )}
                  <span className={`text-sm font-semibold ${predictions.variance_days > 0 ? 'text-[#F97316]' : 'text-[#16B364]'}`}>
                    {Math.abs(predictions.variance_days)} day{Math.abs(predictions.variance_days) !== 1 ? 's' : ''} {predictions.variance_days > 0 ? 'late' : 'early'}
                  </span>
                </div>
                <Badge className={`${statusStyle.bg} ${statusStyle.text}`} data-testid="prediction-status-badge">
                  <StatusIcon size={12} className="mr-1" />
                  {predictions.status}
                </Badge>
              </div>
            )}
          </div>
        </div>

        {/* Velocity Metrics */}
        {velocity && (Object.keys(velocity).length > 0) && (
          <div className="space-y-2 pt-2 border-t border-[#E6E8EC]" data-testid="velocity-metrics">
            <div className="flex items-center gap-2 text-sm font-semibold text-[#475467]">
              <TrendingUp size={16} />
              <span>Velocity</span>
            </div>
            <div className="pl-6 space-y-1">
              {velocity.progress_per_day != null && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-[#667085]">Progress per day:</span>
                  <span className="font-medium text-[#1570EF]">{(velocity.progress_per_day || 0).toFixed(1)}%</span>
                </div>
              )}
              {velocity.tasks_per_week != null && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-[#667085]">Tasks per week:</span>
                  <span className="font-medium text-[#1570EF]">{(velocity.tasks_per_week || 0).toFixed(1)}</span>
                </div>
              )}
              {velocity.hours_per_week != null && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-[#667085]">Hours per week:</span>
                  <span className="font-medium text-[#1570EF]">{(velocity.hours_per_week || 0).toFixed(1)}h</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Budget Forecast */}
        {budgetPred && (Object.keys(budgetPred).length > 0) && (
          <div className="space-y-2 pt-2 border-t border-[#E6E8EC]" data-testid="budget-forecast">
            <div className="flex items-center gap-2 text-sm font-semibold text-[#475467]">
              <DollarSign size={16} />
              <span>Budget</span>
            </div>
            <div className="pl-6 space-y-1">
              {budgetPred.burn_rate != null && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-[#667085]">Burn rate:</span>
                  <span className="font-medium text-[#0B1220]">{(budgetPred.burn_rate || 0).toFixed(1)}h/week</span>
                </div>
              )}
              {budgetPred.predicted_total != null && budgetPred.budgeted_hours != null && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-[#667085]">Predicted total:</span>
                  <span className={`font-medium ${(budgetPred.predicted_total || 0) > (budgetPred.budgeted_hours || 0) ? 'text-[#EF4444]' : 'text-[#16B364]'}`}>
                    {(budgetPred.predicted_total || 0).toFixed(0)}h / {(budgetPred.budgeted_hours || 0).toFixed(0)}h
                  </span>
                </div>
              )}
              {budgetPred.weeks_until_exhausted != null && budgetPred.weeks_until_exhausted > 0 && (
                <div className="flex items-center gap-2 pt-2 border-t border-[#E6E8EC]">
                  <span className="text-xs text-[#667085]">⏳ Budget exhausted in:</span>
                  <span className="text-sm font-semibold text-[#F97316]">
                    {(budgetPred.weeks_until_exhausted || 0).toFixed(1)} weeks
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Empty state if no detailed predictions */}
        {(!velocity || Object.keys(velocity).length === 0) && (!budgetPred || Object.keys(budgetPred).length === 0) && (
          <div className="text-center py-4 text-sm text-[#667085]">
            <Sparkles size={24} className="mx-auto mb-2 opacity-40" />
            <p>More predictions will appear as project data accumulates</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ProjectPredictions;
