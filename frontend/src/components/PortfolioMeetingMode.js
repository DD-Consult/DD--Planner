import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { X, ChevronLeft, ChevronRight, Building2, Users, Calendar, Clock, AlertTriangle, Target } from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { getProject, getProjectRisks } from '../api';

const PortfolioMeetingMode = ({ projects, open, onClose, initialIndex = 0 }) => {
  const [currentIndex, setCurrentIndex] = useState(initialIndex);

  // Reset index when projects change
  useEffect(() => {
    if (open && initialIndex !== currentIndex) {
      setCurrentIndex(initialIndex);
    }
  }, [open, initialIndex]);

  // Keyboard navigation
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      } else if (e.key === 'ArrowRight' && currentIndex < projects.length - 1) {
        setCurrentIndex((prev) => prev + 1);
      } else if (e.key === 'ArrowLeft' && currentIndex > 0) {
        setCurrentIndex((prev) => prev - 1);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, currentIndex, projects.length, onClose]);

  if (!open) return null;

  if (projects.length === 0) {
    return (
      <div className="fixed inset-0 bg-white z-50 flex items-center justify-center">
        <div className="text-center">
          <Building2 className="h-16 w-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-4">No projects to present</h3>
          <Button onClick={onClose} data-testid="meeting-mode-close">
            Close
          </Button>
        </div>
      </div>
    );
  }

  const currentProject = projects[currentIndex];

  return (
    <div className="fixed inset-0 bg-white z-50 overflow-auto">
      {/* Sticky Top Bar */}
      <div className="sticky top-0 bg-white border-b border-gray-200 shadow-sm z-10">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Left: Title + Position */}
            <div className="flex items-center gap-4">
              <h2 className="text-xl font-semibold text-gray-900">Meeting Mode</h2>
              <span className="text-sm text-gray-600" data-testid="meeting-mode-position">
                Project {currentIndex + 1} of {projects.length}
              </span>
            </div>

            {/* Center: Jump to Project */}
            <div className="flex-1 max-w-xs mx-8">
              <Select
                value={currentIndex.toString()}
                onValueChange={(value) => setCurrentIndex(parseInt(value))}
              >
                <SelectTrigger data-testid="meeting-mode-jump">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {projects.map((project, idx) => (
                    <SelectItem key={project.id} value={idx.toString()}>
                      {project.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Right: Navigation Controls */}
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentIndex((prev) => prev - 1)}
                disabled={currentIndex === 0}
                data-testid="meeting-prev"
              >
                <ChevronLeft className="h-4 w-4 mr-1" />
                Prev
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentIndex((prev) => prev + 1)}
                disabled={currentIndex === projects.length - 1}
                data-testid="meeting-next"
              >
                Next
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={onClose}
                data-testid="meeting-mode-close"
              >
                <X className="h-4 w-4 mr-1" />
                Close
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Project Content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        <ProjectSlide project={currentProject} />
      </div>
    </div>
  );
};

const ProjectSlide = ({ project }) => {
  // Fetch full project details including status_summary
  const { data: projectDetails, isLoading: loadingProject } = useQuery({
    queryKey: ['project', project.id],
    queryFn: async () => {
      const response = await getProject(project.id);
      return response.data;
    },
    enabled: !!project.id,
  });

  // Fetch project risks
  const { data: risks = [], isLoading: loadingRisks } = useQuery({
    queryKey: ['projectRisks', project.id],
    queryFn: async () => {
      const response = await getProjectRisks(project.id);
      return response.data;
    },
    enabled: !!project.id,
  });

  const getHealthColor = (health) => {
    switch (health?.toLowerCase()) {
      case 'green': return 'bg-green-100 text-green-800 border-green-300';
      case 'amber': case 'yellow': return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      case 'red': return 'bg-red-100 text-red-800 border-red-300';
      default: return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  const getScheduleColor = (schedule) => {
    switch (schedule?.toLowerCase()) {
      case 'on track': return 'bg-green-100 text-green-800';
      case 'at risk': return 'bg-yellow-100 text-yellow-800';
      case 'delayed': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-AU', { 
      day: '2-digit', 
      month: 'short', 
      year: 'numeric' 
    });
  };

  // Filter for open risks
  const openRisks = risks.filter(
    (risk) => !['mitigated', 'closed', 'resolved'].includes(risk.status?.toLowerCase())
  );

  // Filter for upcoming milestones
  const upcomingMilestones = (project.milestones || [])
    .filter((m) => m.status?.toLowerCase() !== 'completed')
    .slice(0, 5); // Show max 5 upcoming

  const variance = project.actual_hours - project.baseline_hours;
  const isOverBudget = variance > 0;

  return (
    <div className="space-y-8">
      {/* Header Section */}
      <div className="border-b border-gray-200 pb-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1">
            <h1 className="text-4xl font-bold text-gray-900 mb-2">{project.name}</h1>
            <div className="flex items-center gap-3 text-lg text-gray-600">
              <Building2 className="h-5 w-5" />
              <span>{project.client_name || 'No client'}</span>
            </div>
          </div>
          <div className="flex flex-col gap-2 items-end">
            <div className="flex gap-2">
              <Badge className={`${getHealthColor(project.health)} text-sm px-3 py-1`}>
                Health: {project.health || 'N/A'}
              </Badge>
              <Badge className={`${getScheduleColor(project.schedule_status)} text-sm px-3 py-1`}>
                {project.schedule_status || 'N/A'}
              </Badge>
            </div>
            <div className="flex gap-2 text-sm">
              {project.is_pipeline ? (
                <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-300">
                  Pipeline
                </Badge>
              ) : (
                <Badge variant="outline" className="bg-green-50 text-green-700 border-green-300">
                  Active
                </Badge>
              )}
              {project.project_lead_name && (
                <div className="flex items-center gap-1 text-gray-700 bg-gray-100 px-3 py-1 rounded-full">
                  <Users className="h-4 w-4" />
                  <span>Lead: {project.project_lead_name}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-8">
        {/* Left Column */}
        <div className="space-y-6">
          {/* Schedule & Progress */}
          <div className="bg-gray-50 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Calendar className="h-5 w-5 text-blue-600" />
              Schedule & Progress
            </h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Start Date:</span>
                <span className="font-medium text-lg">{formatDate(project.start_date)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">End Date:</span>
                <span className="font-medium text-lg">{formatDate(project.end_date)}</span>
              </div>
              <div className="pt-4 border-t border-gray-200">
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-gray-600 font-medium">Project Progress</span>
                  <span className="font-semibold text-lg">{project.actual_progress || 0}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-4">
                  <div 
                    className="bg-blue-600 h-4 rounded-full transition-all"
                    style={{ width: `${Math.min(project.actual_progress || 0, 100)}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Budget vs Actual */}
          <div className="bg-gray-50 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Clock className="h-5 w-5 text-purple-600" />
              Budget vs Actual
            </h3>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="text-center">
                <p className="text-sm text-gray-600 mb-1">Budgeted</p>
                <p className="text-2xl font-bold text-gray-900">
                  {project.budgeted_hours?.toFixed(0) || 'N/A'}
                </p>
                <p className="text-xs text-gray-500">hours</p>
              </div>
              <div className="text-center">
                <p className="text-sm text-gray-600 mb-1">Baseline</p>
                <p className="text-2xl font-bold text-gray-900">
                  {project.baseline_hours?.toFixed(0) || 0}
                </p>
                <p className="text-xs text-gray-500">hours</p>
              </div>
              <div className="text-center">
                <p className="text-sm text-gray-600 mb-1">Actual</p>
                <p className="text-2xl font-bold text-gray-900">
                  {project.actual_hours?.toFixed(0) || 0}
                </p>
                <p className="text-xs text-gray-500">hours</p>
              </div>
            </div>
            <div className={`p-4 rounded-lg ${isOverBudget ? 'bg-red-50 border border-red-200' : 'bg-green-50 border border-green-200'}`}>
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-700">Variance (vs Baseline):</span>
                <span className={`text-xl font-bold ${isOverBudget ? 'text-red-600' : 'text-green-600'}`}>
                  {isOverBudget ? '+' : ''}{Math.abs(variance).toFixed(0)} hrs
                </span>
              </div>
              <div className="text-sm text-gray-600 mt-1">
                {project.variance_percentage ? `${project.variance_percentage}%` : '0%'} 
                {isOverBudget ? ' over budget' : ' under budget'}
              </div>
            </div>
          </div>

          {/* Upcoming Milestones */}
          <div className="bg-gray-50 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Target className="h-5 w-5 text-green-600" />
              Upcoming Milestones
              {upcomingMilestones.length > 0 && (
                <Badge variant="outline" className="ml-2">{upcomingMilestones.length}</Badge>
              )}
            </h3>
            {upcomingMilestones.length > 0 ? (
              <div className="space-y-3">
                {upcomingMilestones.map((milestone, idx) => (
                  <div key={idx} className="flex items-start gap-3 p-3 bg-white rounded border border-gray-200">
                    <div className="flex-1">
                      <p className="font-medium text-gray-900">{milestone.name}</p>
                      <p className="text-sm text-gray-600">{formatDate(milestone.date)}</p>
                    </div>
                    <Badge variant="outline" className="bg-blue-50 text-blue-700 text-xs">
                      {milestone.status || 'Pending'}
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 italic">No upcoming milestones</p>
            )}
          </div>
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          {/* Status Summary */}
          <div className="bg-gray-50 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Status Summary</h3>
            {loadingProject ? (
              <div className="flex items-center justify-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : (
              <div className="bg-white rounded p-4 border border-gray-200 min-h-[200px]">
                {projectDetails?.status_summary ? (
                  <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">
                    {projectDetails.status_summary}
                  </p>
                ) : (
                  <p className="text-gray-500 italic">No status summary yet.</p>
                )}
              </div>
            )}
          </div>

          {/* Open Risks */}
          <div className="bg-gray-50 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-orange-600" />
              Open Risks
              {openRisks.length > 0 && (
                <Badge variant="outline" className="ml-2 bg-orange-50 text-orange-700 border-orange-300">
                  {openRisks.length}
                </Badge>
              )}
            </h3>
            {loadingRisks ? (
              <div className="flex items-center justify-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : openRisks.length > 0 ? (
              <div className="space-y-3 max-h-[600px] overflow-y-auto">
                {openRisks.map((risk) => (
                  <div key={risk.id} className="bg-white rounded p-4 border border-gray-200">
                    <div className="flex items-start justify-between mb-2">
                      <h4 className="font-medium text-gray-900 flex-1">{risk.title}</h4>
                      <div className="flex gap-1 ml-2">
                        <Badge variant="outline" className="text-xs bg-red-50 text-red-700 border-red-300">
                          Impact: {risk.impact || 'N/A'}
                        </Badge>
                        <Badge variant="outline" className="text-xs bg-yellow-50 text-yellow-700 border-yellow-300">
                          Prob: {risk.probability || 'N/A'}
                        </Badge>
                      </div>
                    </div>
                    {risk.description && (
                      <p className="text-sm text-gray-600 mb-2">{risk.description}</p>
                    )}
                    {risk.mitigation && (
                      <div className="mt-2 pt-2 border-t border-gray-100">
                        <p className="text-xs font-medium text-gray-700 mb-1">Mitigation:</p>
                        <p className="text-sm text-gray-600">{risk.mitigation}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 italic">No open risks.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PortfolioMeetingMode;
