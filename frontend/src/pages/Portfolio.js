import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Calendar, TrendingUp, TrendingDown, AlertCircle, Building2, Users, Clock, GanttChart, LayoutGrid, ListTree } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import api from '../api';
import PortfolioGantt from '../components/PortfolioGantt';

const Portfolio = () => {
  const [selectedMonths, setSelectedMonths] = useState(3);
  const [viewMode, setViewMode] = useState('gantt'); // 'gantt' | 'cards'
  const [statusFilter, setStatusFilter] = useState('all'); // 'all' | 'active' | 'pipeline'
  const [showAllPhases, setShowAllPhases] = useState(false);

  // Fetch portfolio data using the shared API client.
  // `api` is configured with a relative `/api` baseURL and an auth
  // interceptor, so it works in both preview and production without
  // depending on REACT_APP_BACKEND_URL.
  const { data: portfolioData, isLoading, error } = useQuery({
    queryKey: ['portfolio', selectedMonths],
    queryFn: async () => {
      const response = await api.get(`/portfolio?months=${selectedMonths}`);
      return response.data;
    },
    refetchOnWindowFocus: false
  });

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading portfolio data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <p className="text-red-600">Error loading portfolio: {error.message}</p>
        </div>
      </div>
    );
  }

  const allProjects = portfolioData?.projects || [];
  // Apply status filter (drives both Gantt and Card views)
  const projects = allProjects.filter((p) => {
    if (statusFilter === 'active') return !p.is_pipeline;
    if (statusFilter === 'pipeline') return p.is_pipeline;
    return true;
  });
  const pipelineProjects = projects.filter(p => p.is_pipeline);
  const activeProjects = projects.filter(p => !p.is_pipeline);

  // Calculate totals
  const totalBudgeted = projects.reduce((sum, p) => sum + (p.budgeted_hours || 0), 0);
  const totalBaseline = projects.reduce((sum, p) => sum + (p.baseline_hours || 0), 0);
  const totalActual = projects.reduce((sum, p) => sum + (p.actual_hours || 0), 0);

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

  const ProjectCard = ({ project }) => {
    const variance = project.actual_hours - project.baseline_hours;
    const variancePercent = project.baseline_hours > 0 
      ? ((variance / project.baseline_hours) * 100).toFixed(1) 
      : 0;
    const isOverBudget = variance > 0;

    return (
      <Card className="hover:shadow-lg transition-shadow mb-4">
        <CardHeader>
          <div className="flex justify-between items-start">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <CardTitle className="text-lg">{project.name}</CardTitle>
                {project.is_pipeline && (
                  <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-300">
                    Pipeline
                  </Badge>
                )}
              </div>
              <CardDescription className="flex items-center gap-2">
                <Building2 className="h-4 w-4" />
                {project.client_name || 'No client'}
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Badge className={getHealthColor(project.health)}>
                {project.health || 'N/A'}
              </Badge>
              <Badge className={getScheduleColor(project.schedule_status)}>
                {project.schedule_status || 'N/A'}
              </Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <p className="text-sm text-gray-600 flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                Start Date
              </p>
              <p className="font-medium">{formatDate(project.start_date)}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600 flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                End Date
              </p>
              <p className="font-medium">{formatDate(project.end_date)}</p>
            </div>
          </div>

          {project.project_lead_name && (
            <div className="mb-4">
              <p className="text-sm text-gray-600 flex items-center gap-1">
                <Users className="h-4 w-4" />
                Project Lead
              </p>
              <p className="font-medium">{project.project_lead_name}</p>
            </div>
          )}

          {/* Hours Analysis */}
          <div className="border-t pt-4">
            <p className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1">
              <Clock className="h-4 w-4" />
              Hours Analysis
            </p>
            <div className="grid grid-cols-3 gap-2 text-sm">
              <div>
                <p className="text-gray-600">Budgeted</p>
                <p className="font-medium">{project.budgeted_hours?.toFixed(1) || 'N/A'} hrs</p>
              </div>
              <div>
                <p className="text-gray-600">Baseline</p>
                <p className="font-medium">{project.baseline_hours.toFixed(1)} hrs</p>
              </div>
              <div>
                <p className="text-gray-600">Actual</p>
                <p className="font-medium">{project.actual_hours.toFixed(1)} hrs</p>
              </div>
            </div>
            
            {/* Variance Display */}
            <div className="mt-3 p-2 rounded-md bg-gray-50 flex items-center justify-between">
              <span className="text-sm font-medium">Baseline vs Actual Variance:</span>
              <span className={`flex items-center gap-1 font-semibold ${isOverBudget ? 'text-red-600' : 'text-green-600'}`}>
                {isOverBudget ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                {Math.abs(variance).toFixed(1)} hrs ({variancePercent}%)
              </span>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="mt-4">
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-600">Progress</span>
              <span className="font-medium">{project.actual_progress || 0}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all"
                style={{ width: `${Math.min(project.actual_progress || 0, 100)}%` }}
              />
            </div>
          </div>
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Portfolio Overview</h1>
          <p className="text-gray-600">Company-wide project portfolio with baseline vs actual hours tracking</p>
        </div>

        {/* Controls */}
        <div className="mb-6 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">Timeline:</label>
            <Select value={selectedMonths.toString()} onValueChange={(value) => setSelectedMonths(parseInt(value))}>
              <SelectTrigger className="w-32" data-testid="portfolio-timeline-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1">1 Month</SelectItem>
                <SelectItem value="3">3 Months</SelectItem>
                <SelectItem value="6">6 Months</SelectItem>
                <SelectItem value="12">12 Months</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">Status:</label>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-32" data-testid="portfolio-status-filter">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="pipeline">Pipeline</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="text-sm text-gray-600">
            {formatDate(portfolioData?.date_range?.start)} - {formatDate(portfolioData?.date_range?.end)}
          </div>

          {/* Right-aligned: phase toggle + view switch */}
          <div className="ml-auto flex items-center gap-3">
            {viewMode === 'gantt' && (
              <Button
                variant={showAllPhases ? 'default' : 'outline'}
                size="sm"
                onClick={() => setShowAllPhases((v) => !v)}
                data-testid="portfolio-toggle-phases"
              >
                <ListTree className="h-4 w-4 mr-1" />
                {showAllPhases ? 'Hide Phases' : 'Show Phases'}
              </Button>
            )}
            <div className="inline-flex rounded-md border border-gray-200 overflow-hidden">
              <button
                onClick={() => setViewMode('gantt')}
                className={`flex items-center gap-1 px-3 py-1.5 text-sm ${viewMode === 'gantt' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'}`}
                data-testid="portfolio-view-gantt"
              >
                <GanttChart className="h-4 w-4" /> Gantt
              </button>
              <button
                onClick={() => setViewMode('cards')}
                className={`flex items-center gap-1 px-3 py-1.5 text-sm border-l border-gray-200 ${viewMode === 'cards' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'}`}
                data-testid="portfolio-view-cards"
              >
                <LayoutGrid className="h-4 w-4" /> Cards
              </button>
            </div>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Total Projects</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-gray-900">{portfolioData?.total_projects || 0}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Active</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-green-600">{portfolioData?.active_count || 0}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Pipeline</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-blue-600">{portfolioData?.pipeline_count || 0}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Total Hours (Actual)</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-gray-900">{totalActual.toFixed(0)}</p>
              <p className="text-xs text-gray-500">vs {totalBaseline.toFixed(0)} baseline</p>
            </CardContent>
          </Card>
        </div>

        {/* Projects View */}
        {viewMode === 'gantt' ? (
          <PortfolioGantt
            projects={projects}
            dateRange={portfolioData?.date_range}
            showAllPhases={showAllPhases}
          />
        ) : (
          <div className="space-y-6">
            {/* Active Projects */}
            {activeProjects.length > 0 && (
              <div>
                <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <div className="h-1 w-8 bg-green-600 rounded"></div>
                  Active Projects ({activeProjects.length})
                </h2>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {activeProjects.map(project => (
                    <ProjectCard key={project.id} project={project} />
                  ))}
                </div>
              </div>
            )}

            {/* Pipeline Projects */}
            {pipelineProjects.length > 0 && (
              <div>
                <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <div className="h-1 w-8 bg-blue-600 rounded"></div>
                  Pipeline Projects ({pipelineProjects.length})
                </h2>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {pipelineProjects.map(project => (
                    <ProjectCard key={project.id} project={project} />
                  ))}
                </div>
              </div>
            )}

            {/* Empty State */}
            {projects.length === 0 && (
              <div className="text-center py-12">
                <Building2 className="h-16 w-16 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">No projects found</h3>
                <p className="text-gray-600">No projects found in the selected {selectedMonths}-month timeline.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Portfolio;
