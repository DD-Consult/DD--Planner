import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getProjectHealthScore } from '../api';
import { TrendingUp, TrendingDown, Minus, Activity } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Progress } from './ui/progress';

const ProjectHealthScore = ({ projectId }) => {
  const { data: healthScore, isLoading } = useQuery({
    queryKey: ['projectHealthScore', projectId],
    queryFn: async () => {
      const response = await getProjectHealthScore(projectId);
      return response.data;
    },
    enabled: !!projectId,
    staleTime: 2 * 60 * 1000, // Cache for 2 minutes
  });

  if (isLoading) {
    return (
      <Card data-testid="project-health-score-loading">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2" style={{ fontFamily: 'Space Grotesk' }}>
            <Activity size={20} className="text-[#1570EF]" />
            Project Health Score
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <p className="text-sm text-[#667085]">Loading health score...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!healthScore) {
    return (
      <Card data-testid="project-health-score-error">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2" style={{ fontFamily: 'Space Grotesk' }}>
            <Activity size={20} className="text-[#1570EF]" />
            Project Health Score
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <p className="text-sm text-[#667085]">Health score unavailable</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Grade color mapping
  const getGradeColor = (grade) => {
    const colors = {
      A: { bg: 'bg-[#16B364]', text: 'text-white', border: 'border-[#16B364]', label: 'Excellent' },
      B: { bg: 'bg-[#1570EF]', text: 'text-white', border: 'border-[#1570EF]', label: 'Good' },
      C: { bg: 'bg-[#F4B740]', text: 'text-white', border: 'border-[#F4B740]', label: 'Fair' },
      D: { bg: 'bg-[#F97316]', text: 'text-white', border: 'border-[#F97316]', label: 'Poor' },
      F: { bg: 'bg-[#EF4444]', text: 'text-white', border: 'border-[#EF4444]', label: 'Critical' },
    };
    return colors[grade] || colors.C;
  };

  // Bar color based on score
  const getBarColor = (score) => {
    if (score >= 80) return 'bg-[#16B364]';
    if (score >= 60) return 'bg-[#1570EF]';
    if (score >= 40) return 'bg-[#F4B740]';
    return 'bg-[#EF4444]';
  };

  // Trend icon
  const getTrendIcon = (trend) => {
    if (trend === 'improving') return <TrendingUp size={16} className="text-[#16B364]" data-testid="trend-improving" />;
    if (trend === 'declining') return <TrendingDown size={16} className="text-[#EF4444]" data-testid="trend-declining" />;
    return <Minus size={16} className="text-[#667085]" data-testid="trend-stable" />;
  };

  const gradeStyle = getGradeColor(healthScore.grade);
  const dims = healthScore.dimensions || {};
  // Extract scores from dimension objects (each has {score, weight, detail})
  const dimensions = {
    schedule: dims.schedule?.score ?? 0,
    budget: dims.budget?.score ?? 0,
    risk: dims.risk?.score ?? 0,
    team: dims.team?.score ?? 0,
    wbs: dims.wbs?.score ?? 0,
  };
  const dimensionDetails = {
    schedule: dims.schedule?.detail || '',
    budget: dims.budget?.detail || '',
    risk: dims.risk?.detail || '',
    team: dims.team?.detail || '',
    wbs: dims.wbs?.detail || '',
  };

  return (
    <Card data-testid="project-health-score">
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2" style={{ fontFamily: 'Space Grotesk' }}>
          <Activity size={20} className="text-[#1570EF]" />
          Project Health Score
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Grade Circle + Score */}
        <div className="flex items-center gap-6">
          <div 
            className={`w-24 h-24 rounded-full ${gradeStyle.bg} ${gradeStyle.text} flex items-center justify-center border-4 ${gradeStyle.border} shadow-lg`}
            data-testid="health-grade-circle"
          >
            <div className="text-center">
              <div className="text-3xl font-bold" data-testid="health-grade">{healthScore.grade}</div>
              <div className="text-xs opacity-90">{gradeStyle.label}</div>
            </div>
          </div>
          
          <div className="flex-1">
            <div className="flex items-baseline gap-2 mb-1">
              <span className="text-4xl font-bold text-[#0B1220]" data-testid="health-score">
                {Math.round(healthScore.overall_score)}
              </span>
              <span className="text-lg text-[#667085]">/ 100</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-[#667085]">
              <span>Trend:</span>
              {getTrendIcon(healthScore.trend)}
              <span className="capitalize">{healthScore.trend || 'stable'}</span>
            </div>
          </div>
        </div>

        {/* Dimension Breakdown */}
        <div className="space-y-3 pt-2 border-t border-[#E6E8EC]">
          <h4 className="text-xs font-semibold text-[#475467] uppercase tracking-wide">Health Dimensions</h4>
          
          {/* Schedule */}
          <div className="space-y-1" data-testid="dimension-schedule">
            <div className="flex items-center justify-between text-sm">
              <span className="text-[#475467] font-medium">Schedule</span>
              <span className="font-semibold text-[#0B1220]">{Math.round(dimensions.schedule || 0)}%</span>
            </div>
            <div className="relative h-2 bg-[#F7F7F8] rounded-full overflow-hidden">
              <div 
                className={`h-full ${getBarColor(dimensions.schedule || 0)} transition-all duration-500`}
                style={{ width: `${Math.min(dimensions.schedule || 0, 100)}%` }}
              />
            </div>
          </div>

          {/* Budget */}
          <div className="space-y-1" data-testid="dimension-budget">
            <div className="flex items-center justify-between text-sm">
              <span className="text-[#475467] font-medium">Budget</span>
              <span className="font-semibold text-[#0B1220]">{Math.round(dimensions.budget || 0)}%</span>
            </div>
            <div className="relative h-2 bg-[#F7F7F8] rounded-full overflow-hidden">
              <div 
                className={`h-full ${getBarColor(dimensions.budget || 0)} transition-all duration-500`}
                style={{ width: `${Math.min(dimensions.budget || 0, 100)}%` }}
              />
            </div>
          </div>

          {/* Risk */}
          <div className="space-y-1" data-testid="dimension-risk">
            <div className="flex items-center justify-between text-sm">
              <span className="text-[#475467] font-medium">Risk</span>
              <span className="font-semibold text-[#0B1220]">{Math.round(dimensions.risk || 0)}%</span>
            </div>
            <div className="relative h-2 bg-[#F7F7F8] rounded-full overflow-hidden">
              <div 
                className={`h-full ${getBarColor(dimensions.risk || 0)} transition-all duration-500`}
                style={{ width: `${Math.min(dimensions.risk || 0, 100)}%` }}
              />
            </div>
          </div>

          {/* Team */}
          <div className="space-y-1" data-testid="dimension-team">
            <div className="flex items-center justify-between text-sm">
              <span className="text-[#475467] font-medium">Team</span>
              <span className="font-semibold text-[#0B1220]">{Math.round(dimensions.team || 0)}%</span>
            </div>
            <div className="relative h-2 bg-[#F7F7F8] rounded-full overflow-hidden">
              <div 
                className={`h-full ${getBarColor(dimensions.team || 0)} transition-all duration-500`}
                style={{ width: `${Math.min(dimensions.team || 0, 100)}%` }}
              />
            </div>
          </div>

          {/* WBS */}
          <div className="space-y-1" data-testid="dimension-wbs">
            <div className="flex items-center justify-between text-sm">
              <span className="text-[#475467] font-medium">WBS</span>
              <span className="font-semibold text-[#0B1220]">{Math.round(dimensions.wbs || 0)}%</span>
            </div>
            <div className="relative h-2 bg-[#F7F7F8] rounded-full overflow-hidden">
              <div 
                className={`h-full ${getBarColor(dimensions.wbs || 0)} transition-all duration-500`}
                style={{ width: `${Math.min(dimensions.wbs || 0, 100)}%` }}
              />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default ProjectHealthScore;
