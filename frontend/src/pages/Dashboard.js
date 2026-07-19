import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, Link } from 'react-router-dom';
import { format, addDays, parseISO, isWithinInterval, startOfWeek, endOfWeek, areIntervalsOverlapping } from 'date-fns';
import { getCapacityReport, getResources, getProjects, getAllocations, getMe, getActionItems, getPortfolioHealthScores } from '../api';
import InteractiveTimelineGrid from '../components/InteractiveTimelineGrid';
import AllocationEditor from '../components/AllocationEditor';
import TimesheetWeeklyCheckin from '../components/TimesheetWeeklyCheckin';
import ProjectStatusCheckin from '../components/ProjectStatusCheckin';
import { useSandbox } from '../contexts/SandboxContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Progress } from '../components/ui/progress';
import { Badge } from '../components/ui/badge';
import { Avatar, AvatarImage, AvatarFallback } from '../components/ui/avatar';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../components/ui/tooltip';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { 
  ChevronLeft, 
  ChevronRight, 
  Search, 
  Filter,
  Briefcase,
  Users,
  AlertTriangle,
  UserCheck,
  TrendingUp,
  ChevronDown,
  ChevronUp,
  Crown,
  ExternalLink,
  Bell,
  Clock,
  FileText,
  ClipboardList,
  Calendar,
  Flag,
  X,
} from 'lucide-react';

const Dashboard = ({ token }) => {
  const navigate = useNavigate();
  const { showDrafts } = useSandbox();
  const [dateRange, setDateRange] = useState({
    start: format(new Date(), 'yyyy-MM-dd'),
    end: format(addDays(new Date(), 13), 'yyyy-MM-dd'),
  });
  
  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [timesheetExpanded, setTimesheetExpanded] = useState(false);
  const [statusCheckinExpanded, setStatusCheckinExpanded] = useState(false);
  const [actionItemsExpanded, setActionItemsExpanded] = useState(false);
  const [actionItemsDismissed, setActionItemsDismissed] = useState(false);
  
  // Status group collapse state — Active expanded by default, Pipeline + Completed collapsed
  const [activeExpanded, setActiveExpanded] = useState(true);
  const [pipelineExpanded, setPipelineExpanded] = useState(false);
  const [completedExpanded, setCompletedExpanded] = useState(false);

  const { data: userData } = useQuery({
    queryKey: ['me'],
    queryFn: async () => { const r = await getMe(); return r.data; },
  });

  const { data: actionItemsData } = useQuery({
    queryKey: ['actionItems'],
    queryFn: async () => { const r = await getActionItems(); return r.data; },
    refetchInterval: 5 * 60 * 1000, // Refetch every 5 minutes
  });

  const { data: capacityData, isLoading: capacityLoading } = useQuery({
    queryKey: ['capacity', dateRange.start, dateRange.end],
    queryFn: async () => { const r = await getCapacityReport(dateRange.start, dateRange.end); return r.data; },
  });

  const { data: resources } = useQuery({
    queryKey: ['resources'],
    queryFn: async () => { const r = await getResources(); return r.data; },
  });

  const { data: projects } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => { const r = await getProjects(); return r.data; },
  });

  const { data: allocations } = useQuery({
    queryKey: ['allocations'],
    queryFn: async () => { const r = await getAllocations(); return r.data; },
  });

  // Fetch portfolio health scores
  const { data: portfolioHealthData } = useQuery({
    queryKey: ['portfolioHealthScores'],
    queryFn: async () => { const r = await getPortfolioHealthScores(); return r.data; },
    staleTime: 2 * 60 * 1000, // Cache for 2 minutes
  });

  const isAdmin = userData?.role === 'admin' || userData?.role === 'super_admin';

  const filteredProjects = useMemo(() => {
    if (!projects) return [];
    if (showDrafts) return projects;
    return projects.filter(p => !p.is_draft);
  }, [projects, showDrafts]);

  const filteredAllocations = useMemo(() => {
    if (!allocations || !projects) return [];
    if (showDrafts) return allocations;
    const nonDraftProjectIds = projects.filter(p => !p.is_draft).map(p => p.id);
    return allocations.filter(a => nonDraftProjectIds.includes(a.project_id));
  }, [allocations, projects, showDrafts]);

  // KPIs
  const activeProjectsCount = useMemo(() => {
    return filteredProjects?.filter(p => p.status === 'Active').length || 0;
  }, [filteredProjects]);

  const teamUtilization = useMemo(() => {
    if (!filteredAllocations || !resources || resources.length === 0) return 0;
    const today = new Date();
    const weekStart = startOfWeek(today, { weekStartsOn: 1 });
    const weekEnd = addDays(weekStart, 4); // Friday (business days Mon-Fri)
    let totalUtilization = 0;
    resources.forEach(resource => {
      const activeAllocs = filteredAllocations.filter(alloc => {
        if (alloc.resource_id !== resource.id) return false;
        try {
          return areIntervalsOverlapping(
            { start: parseISO(alloc.start_date), end: parseISO(alloc.end_date) },
            { start: weekStart, end: weekEnd }
          );
        } catch { return false; }
      });
      const resourceUtil = activeAllocs.reduce((sum, a) => sum + (a.percentage || 0), 0);
      totalUtilization += Math.min(resourceUtil, 100);
    });
    return Math.round(totalUtilization / resources.length);
  }, [filteredAllocations, resources]);

  const overAllocatedCount = useMemo(() => {
    if (!capacityData) return 0;
    return capacityData.resources?.filter(r => r.days.some(d => d.color === 'red')).length || 0;
  }, [capacityData]);

  const onTheBenchCount = useMemo(() => {
    if (!filteredAllocations || !resources) return 0;
    const resourceAllocations = resources.map(resource => {
      const resourceAllocs = filteredAllocations.filter(alloc => 
        alloc.resource_id === resource.id &&
        isWithinInterval(new Date(), { start: parseISO(alloc.start_date), end: parseISO(alloc.end_date) })
      );
      return resourceAllocs.reduce((sum, alloc) => sum + (alloc.percentage || 0), 0);
    });
    return resourceAllocations.filter(a => a < 50).length;
  }, [filteredAllocations, resources]);

  // Enrich ALL projects with computed data
  const enrichedProjects = useMemo(() => {
    if (!filteredProjects || !filteredAllocations || !resources) return [];
    
    // Create health score map from portfolio data
    const healthScoreMap = {};
    if (portfolioHealthData?.projects) {
      portfolioHealthData.projects.forEach(projectHealth => {
        healthScoreMap[projectHealth.project_id] = {
          score: projectHealth.overall_score,
          grade: projectHealth.grade,
        };
      });
    }
    
    return filteredProjects.map(project => {
      const projectAllocations = filteredAllocations.filter(alloc => alloc.project_id === project.id);
      const uniqueResourceIds = [...new Set(projectAllocations.map(alloc => alloc.resource_id))];
      const projectResources = uniqueResourceIds.map(rid => resources.find(r => r.id === rid)).filter(Boolean);
      
      const today = new Date();
      let currentPhase = null;
      if (project.phases?.length > 0) {
        currentPhase = project.phases.find(phase => {
          try {
            return isWithinInterval(today, { start: parseISO(phase.start_date), end: parseISO(phase.end_date) });
          } catch { return false; }
        });
      }
      
      const projectStart = parseISO(project.start_date);
      const projectEnd = parseISO(project.end_date);
      const totalDays = Math.max(1, Math.floor((projectEnd - projectStart) / (1000 * 60 * 60 * 24)));
      const elapsedDays = Math.max(0, Math.floor((today - projectStart) / (1000 * 60 * 60 * 24)));
      const timeBasedProgress = Math.min(100, Math.max(0, Math.round((elapsedDays / totalDays) * 100)));
      
      const progress = project.actual_progress != null ? project.actual_progress : timeBasedProgress;
      let health = project.health || 'Green';
      if (!project.health) {
        if (project.status === 'Pipeline') health = 'Amber';
        if (timeBasedProgress > 80 && project.status === 'Active') health = 'Amber';
      }
      
      // Add AI health score if available
      const aiHealthScore = healthScoreMap[project.id];
      
      return {
        ...project,
        teamMembers: projectResources,
        currentPhase: currentPhase?.name || 'N/A',
        health,
        progress,
        scheduleStatus: project.schedule_status || null,
        aiHealthScore, // { score, grade } or undefined
      };
    });
  }, [filteredProjects, filteredAllocations, resources, portfolioHealthData]);

  // Group by status
  const activeProjects = useMemo(() => enrichedProjects.filter(p => p.status === 'Active'), [enrichedProjects]);
  const pipelineProjects = useMemo(() => enrichedProjects.filter(p => p.status === 'Pipeline'), [enrichedProjects]);
  const completedProjects = useMemo(() => enrichedProjects.filter(p => p.status === 'Completed'), [enrichedProjects]);

  const handlePreviousWeek = () => setDateRange({ start: format(addDays(new Date(dateRange.start), -7), 'yyyy-MM-dd'), end: format(addDays(new Date(dateRange.end), -7), 'yyyy-MM-dd') });
  const handleNextWeek = () => setDateRange({ start: format(addDays(new Date(dateRange.start), 7), 'yyyy-MM-dd'), end: format(addDays(new Date(dateRange.end), 7), 'yyyy-MM-dd') });
  const handleToday = () => setDateRange({ start: format(new Date(), 'yyyy-MM-dd'), end: format(addDays(new Date(), 13), 'yyyy-MM-dd') });
  const uniqueRoles = [...new Set(resources?.map(r => r.role) || [])];
  const filteredCapacityData = capacityData ? { ...capacityData, resources: capacityData.resources.filter(r => r.name.toLowerCase().includes(searchTerm.toLowerCase()) && (roleFilter === 'all' || r.role === roleFilter)) } : null;
  const filteredResources = resources?.filter(r => r.name.toLowerCase().includes(searchTerm.toLowerCase()) && (roleFilter === 'all' || r.role === roleFilter));

  const getHealthColor = (health) => ({ Green: 'bg-[#16B364] text-white', Amber: 'bg-[#F4B740] text-white', Red: 'bg-[#EF4444] text-white' }[health] || 'bg-[#667085] text-white');
  const handleProjectClick = (projectId) => navigate(`/projects/${projectId}`);

  // Helper function to check if project is in its last week (5 business days or less remaining)
  const isInLastWeek = (endDate) => {
    if (!endDate) return false;
    try {
      const end = parseISO(endDate);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      end.setHours(0, 0, 0, 0);
      
      // Calculate business days remaining (Mon-Fri only)
      let businessDaysLeft = 0;
      const current = new Date(today);
      while (current <= end) {
        const dayOfWeek = current.getDay();
        if (dayOfWeek !== 0 && dayOfWeek !== 6) {
          businessDaysLeft++;
        }
        current.setDate(current.getDate() + 1);
      }
      
      return businessDaysLeft > 0 && businessDaysLeft <= 5;
    } catch {
      return false;
    }
  };

  // Helper function to get action item icon and color
  const getActionItemIcon = (type) => {
    const iconMap = {
      missing_timesheet: { Icon: Clock, color: '#EF4444' },
      draft_timesheet: { Icon: FileText, color: '#F59E0B' },
      status_update_due: { Icon: ClipboardList, color: '#1570EF' },
      budget_alert_critical: { Icon: AlertTriangle, color: '#EF4444' },
      budget_alert_warning: { Icon: AlertTriangle, color: '#F59E0B' },
      allocation_ending: { Icon: Calendar, color: '#F97316' },
      overdue_milestone: { Icon: Flag, color: '#9333EA' },
    };
    return iconMap[type] || { Icon: Bell, color: '#667085' };
  };

  // Helper function to get severity styles
  const getSeverityStyles = (severity) => {
    const severityMap = {
      high: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700', badge: 'bg-red-100 text-red-800' },
      medium: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700', badge: 'bg-amber-100 text-amber-800' },
      low: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700', badge: 'bg-blue-100 text-blue-800' },
    };
    return severityMap[severity] || severityMap.low;
  };

  const ProjectTable = ({ projects: tableProjects }) => (
    <Table>
      <TableHeader>
        <TableRow className="bg-[#F8FAFC]">
          <TableHead className="font-semibold text-[#0B1220]">Project</TableHead>
          <TableHead className="font-semibold text-[#0B1220]">Lead</TableHead>
          <TableHead className="font-semibold text-[#0B1220]">Current Phase</TableHead>
          <TableHead className="font-semibold text-[#0B1220]">Team</TableHead>
          <TableHead className="font-semibold text-[#0B1220]">Health</TableHead>
          <TableHead className="font-semibold text-[#0B1220]">Progress</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {tableProjects.map((project) => (
          <TableRow
            key={project.id}
            onClick={() => handleProjectClick(project.id)}
            className={`cursor-pointer hover:bg-[#F8FAFC] transition-colors border-b border-[#E6E8EC] ${project.is_draft ? 'border-dashed opacity-70 bg-[repeating-linear-gradient(45deg,transparent,transparent_10px,#FFF8E5_10px,#FFF8E5_20px)]' : ''}`}
            data-testid={`project-row-${project.id}`}
          >
            <TableCell>
              <div>
                <div className="font-medium text-[#0B1220] flex items-center gap-2">
                  {project.name}
                  {project.is_draft && <Badge variant="outline" className="text-xs border-[#F97316] text-[#F97316]">DRAFT</Badge>}
                  {project.google_drive_url && (
                    <a href={project.google_drive_url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()} className="text-[#667085] hover:text-[#1570EF]" title="Open Google Drive">
                      <ExternalLink size={14} />
                    </a>
                  )}
                </div>
                <div className="text-sm text-[#667085]">{project.client_name}</div>
              </div>
            </TableCell>
            <TableCell>
              {project.project_lead_name ? (
                <div className="flex items-center gap-2">
                  <Crown size={14} className="text-[#F4B740]" />
                  <span className="text-sm font-medium text-[#0B1220]">{project.project_lead_name}</span>
                </div>
              ) : (
                <span className="text-xs text-[#EF4444] font-medium">No lead</span>
              )}
            </TableCell>
            <TableCell>
              <span className="text-sm text-[#475467]">{project.currentPhase}</span>
            </TableCell>
            <TableCell>
              <div className="flex items-center gap-1">
                {project.teamMembers.slice(0, 3).map((member, idx) => (
                  <Avatar key={member.id} className="w-8 h-8 border-2 border-white" style={{ marginLeft: idx > 0 ? '-8px' : '0' }}>
                    <AvatarImage src={member.avatar_url} />
                    <AvatarFallback>{member.name?.charAt(0)}</AvatarFallback>
                  </Avatar>
                ))}
                {project.teamMembers.length > 3 && (
                  <div className="w-8 h-8 rounded-full bg-[#F7F7F8] border-2 border-white flex items-center justify-center text-xs font-medium text-[#667085]" style={{ marginLeft: '-8px' }}>
                    +{project.teamMembers.length - 3}
                  </div>
                )}
                {project.teamMembers.length === 0 && <span className="text-sm text-[#667085]">No team</span>}
              </div>
            </TableCell>
            <TableCell>
              <div className="flex items-center gap-2" data-testid={`project-health-${project.id}`}>
                <Badge className={getHealthColor(project.health)}>{project.health}</Badge>
                {project.aiHealthScore && (
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Badge 
                          variant="outline" 
                          className={`text-xs font-bold border-2 ${
                            project.aiHealthScore.grade === 'A' ? 'bg-[#16B364] text-white border-[#16B364]' :
                            project.aiHealthScore.grade === 'B' ? 'bg-[#1570EF] text-white border-[#1570EF]' :
                            project.aiHealthScore.grade === 'C' ? 'bg-[#F4B740] text-white border-[#F4B740]' :
                            project.aiHealthScore.grade === 'D' ? 'bg-[#F97316] text-white border-[#F97316]' :
                            'bg-[#EF4444] text-white border-[#EF4444]'
                          }`}
                          data-testid={`ai-health-grade-${project.id}`}
                        >
                          {project.aiHealthScore.grade}
                        </Badge>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>AI Health Score: {Math.round(project.aiHealthScore.score)}/100</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                )}
              </div>
            </TableCell>
            <TableCell>
              <div className="flex items-center gap-2">
                <Progress value={project.progress} className="flex-1 h-2" />
                <span className="text-sm font-medium min-w-[40px] text-right">{project.progress}%</span>
                <span className="text-xs text-[#667085] whitespace-nowrap">
                  | Due: {format(parseISO(project.end_date), 'MMM d')}
                </span>
                {isInLastWeek(project.end_date) && project.status === 'Active' && (
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <Bell className="w-4 h-4 text-[#F97316] animate-pulse" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>Project ending within 5 business days</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                )}
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );

  const StatusSection = ({ title, projects: sectionProjects, expanded, onToggle, color, testId }) => (
    <div className="border border-[#E6E8EC] rounded-lg overflow-hidden" data-testid={testId}>
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-[#F8FAFC] transition-colors"
        style={{ borderLeft: `4px solid ${color}` }}
        onClick={onToggle}
      >
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-[#0B1220]" style={{ fontFamily: 'Space Grotesk' }}>{title}</h3>
          <Badge variant="secondary" className="text-xs">{sectionProjects.length}</Badge>
        </div>
        {expanded ? <ChevronUp size={16} className="text-[#667085]" /> : <ChevronDown size={16} className="text-[#667085]" />}
      </div>
      {expanded && sectionProjects.length > 0 && <ProjectTable projects={sectionProjects} />}
      {expanded && sectionProjects.length === 0 && (
        <div className="text-center py-6 text-sm text-[#667085]">No {title.toLowerCase()} projects</div>
      )}
    </div>
  );

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-semibold" style={{ fontFamily: 'Space Grotesk' }} data-testid="dashboard-title">Command Center</h1>
            <p className="text-sm text-[#667085] mt-1">Real-time portfolio overview and resource capacity</p>
          </div>
        </div>

        {/* ACTION ITEMS BANNER */}
        {actionItemsData?.summary?.total > 0 && !actionItemsDismissed && (
          <Card className="border-l-4 border-l-[#F97316] bg-gradient-to-r from-orange-50 to-white" data-testid="action-items-banner">
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <Bell className="w-5 h-5 text-[#F97316]" />
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-[#0B1220]">
                      ⚡ {actionItemsData.summary.total} item{actionItemsData.summary.total !== 1 ? 's' : ''} need your attention
                    </span>
                    {actionItemsData.summary.high > 0 && (
                      <Badge className="bg-red-100 text-red-800 text-xs">
                        🔴 {actionItemsData.summary.high} high priority
                      </Badge>
                    )}
                    {actionItemsData.summary.medium > 0 && (
                      <Badge className="bg-amber-100 text-amber-800 text-xs">
                        🟡 {actionItemsData.summary.medium} medium
                      </Badge>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setActionItemsExpanded(!actionItemsExpanded)}
                    data-testid="action-items-toggle"
                    className="text-[#1570EF]"
                  >
                    {actionItemsExpanded ? (
                      <>
                        <ChevronUp className="w-4 h-4 mr-1" />
                        Hide All
                      </>
                    ) : (
                      <>
                        <ChevronDown className="w-4 h-4 mr-1" />
                        Show All
                      </>
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setActionItemsDismissed(true)}
                    data-testid="action-items-dismiss"
                    className="text-[#667085] hover:text-[#0B1220]"
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              {actionItemsExpanded && (
                <div className="space-y-2 mt-4 border-t border-[#E6E8EC] pt-4">
                  {actionItemsData.action_items.map((item) => {
                    const { Icon, color } = getActionItemIcon(item.type);
                    const severityStyles = getSeverityStyles(item.severity);
                    
                    return (
                      <div
                        key={item.id}
                        className={`flex items-center justify-between p-3 rounded-lg border ${severityStyles.border} ${severityStyles.bg}`}
                        data-testid={`action-item-${item.id}`}
                      >
                        <div className="flex items-start gap-3 flex-1">
                          <div className="mt-0.5">
                            <Icon className="w-5 h-5" style={{ color }} />
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-semibold text-sm text-[#0B1220]">{item.title}</span>
                              <Badge className={`text-xs ${severityStyles.badge}`}>
                                {item.severity}
                              </Badge>
                            </div>
                            <p className="text-sm text-[#667085]">{item.message}</p>
                          </div>
                        </div>
                        <Link
                          to={item.action_url}
                          className="flex items-center gap-1 text-sm font-medium text-[#1570EF] hover:text-[#0B4A99] whitespace-nowrap ml-4"
                          data-testid={`action-item-link-${item.id}`}
                        >
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

        {/* KPI CARDS */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Tooltip>
            <TooltipTrigger asChild>
              <Card data-testid="kpi-active-projects" className="cursor-help">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-10 h-10 rounded-lg bg-[#F7F7F8] flex items-center justify-center"><Briefcase size={20} className="text-[#1570EF]" /></div>
                  </div>
                  <div className="text-sm text-[#667085] mb-1">Active Projects</div>
                  <div className="text-2xl font-semibold">{activeProjectsCount}</div>
                </CardContent>
              </Card>
            </TooltipTrigger>
            <TooltipContent><p>Number of projects not yet completed</p></TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Card data-testid="kpi-team-utilization" className="cursor-help">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-10 h-10 rounded-lg bg-[#F7F7F8] flex items-center justify-center"><TrendingUp size={20} className="text-[#1570EF]" /></div>
                  </div>
                  <div className="text-sm text-[#667085] mb-1">Team Utilization</div>
                  <div className="text-2xl font-semibold">{teamUtilization}%</div>
                </CardContent>
              </Card>
            </TooltipTrigger>
            <TooltipContent><p>Overall team allocation percentage across all projects</p></TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Card data-testid="kpi-over-allocated" className="cursor-help">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-10 h-10 rounded-lg bg-[#F7F7F8] flex items-center justify-center"><AlertTriangle size={20} className="text-[#EF4444]" /></div>
                  </div>
                  <div className="text-sm text-[#667085] mb-1">Over-Allocated</div>
                  <div className="text-2xl font-semibold text-[#EF4444]">{overAllocatedCount}</div>
                  <div className="text-xs text-[#667085] mt-1">resources</div>
                </CardContent>
              </Card>
            </TooltipTrigger>
            <TooltipContent><p>Resources allocated above 100% capacity</p></TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Card data-testid="kpi-on-bench" className="cursor-help">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-10 h-10 rounded-lg bg-[#F7F7F8] flex items-center justify-center"><UserCheck size={20} className="text-[#16B364]" /></div>
                  </div>
                  <div className="text-sm text-[#667085] mb-1">On The Bench</div>
                  <div className="text-2xl font-semibold">{onTheBenchCount}</div>
                  <div className="text-xs text-[#667085] mt-1">&lt;50% allocated</div>
                </CardContent>
              </Card>
            </TooltipTrigger>
            <TooltipContent><p>Resources available for new assignments (&lt;50% allocated)</p></TooltipContent>
          </Tooltip>
        </div>

        {/* TIMESHEET WIDGET */}
        <Card>
          <CardHeader className="cursor-pointer hover:bg-gray-50 transition-colors" onClick={() => setTimesheetExpanded(!timesheetExpanded)} data-testid="timesheet-header">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">My Weekly Timesheet</CardTitle>
              {timesheetExpanded ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
            </div>
          </CardHeader>
          {timesheetExpanded && <CardContent><TimesheetWeeklyCheckin /></CardContent>}
        </Card>

        {/* STATUS CHECK-IN WIDGET */}
        {userData?.role !== 'contractor' && (
          <Card>
            <CardHeader className="cursor-pointer hover:bg-gray-50 transition-colors" onClick={() => setStatusCheckinExpanded(!statusCheckinExpanded)} data-testid="status-checkin-header">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">Project Status Check-in</CardTitle>
                {statusCheckinExpanded ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
              </div>
            </CardHeader>
            {statusCheckinExpanded && <CardContent><ProjectStatusCheckin /></CardContent>}
          </Card>
        )}

        {/* PROJECT PORTFOLIO — Grouped by Status */}
        <Card data-testid="project-portfolio">
          <CardHeader>
            <CardTitle style={{ fontFamily: 'Space Grotesk' }}>Project Portfolio</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {enrichedProjects.length === 0 ? (
              <div className="text-center py-12 text-[#667085]">
                <Briefcase size={48} className="mx-auto mb-4 text-[#98A2B3]" />
                <p>No projects to display</p>
              </div>
            ) : (
              <>
                <StatusSection
                  title="Active"
                  projects={activeProjects}
                  expanded={activeExpanded}
                  onToggle={() => setActiveExpanded(!activeExpanded)}
                  color="#16B364"
                  testId="status-group-active"
                />
                <StatusSection
                  title="Pipeline"
                  projects={pipelineProjects}
                  expanded={pipelineExpanded}
                  onToggle={() => setPipelineExpanded(!pipelineExpanded)}
                  color="#F4B740"
                  testId="status-group-pipeline"
                />
                <StatusSection
                  title="Completed"
                  projects={completedProjects}
                  expanded={completedExpanded}
                  onToggle={() => setCompletedExpanded(!completedExpanded)}
                  color="#667085"
                  testId="status-group-completed"
                />
              </>
            )}
          </CardContent>
        </Card>

        {/* RESOURCE AVAILABILITY MATRIX */}
        {isAdmin && (
          <Card data-testid="resource-matrix">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle style={{ fontFamily: 'Space Grotesk' }}>Resource Availability Matrix</CardTitle>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={handlePreviousWeek} data-testid="prev-week-button"><ChevronLeft size={16} /></Button>
                  <Button variant="outline" size="sm" onClick={handleToday} data-testid="today-button">Today</Button>
                  <Button variant="outline" size="sm" onClick={handleNextWeek} data-testid="next-week-button"><ChevronRight size={16} /></Button>
                  <div className="text-sm text-[#475467] ml-2">
                    {format(new Date(dateRange.start), 'MMM d')} - {format(new Date(dateRange.end), 'MMM d, yyyy')}
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="bg-[#F7F7F8] border border-[#E6E8EC] rounded-lg p-4 mb-4">
                <div className="flex items-center gap-4 flex-wrap">
                  <div className="flex items-center gap-2 text-sm font-medium text-[#475467]"><Filter size={16} />Filters:</div>
                  <div className="flex-1 min-w-[200px] max-w-xs">
                    <div className="relative">
                      <Search size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-[#667085]" />
                      <Input placeholder="Search resources..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="pl-9" data-testid="resource-search" />
                    </div>
                  </div>
                  <div className="min-w-[180px]">
                    <Select value={roleFilter} onValueChange={setRoleFilter}>
                      <SelectTrigger data-testid="role-filter"><SelectValue placeholder="Filter by role" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Roles</SelectItem>
                        {uniqueRoles.map(role => <SelectItem key={role} value={role}>{role}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  {(searchTerm || roleFilter !== 'all') && (
                    <Button variant="ghost" size="sm" onClick={() => { setSearchTerm(''); setRoleFilter('all'); }} data-testid="clear-filters">Clear Filters</Button>
                  )}
                </div>
                {filteredCapacityData && (
                  <div className="mt-3 text-xs text-[#667085]">Showing {filteredCapacityData.resources.length} of {capacityData.resources.length} resources</div>
                )}
              </div>
              {capacityLoading ? (
                <div className="text-center py-12 text-[#667085]"><p>Loading capacity data...</p></div>
              ) : (
                <InteractiveTimelineGrid
                  capacityData={filteredCapacityData}
                  resources={filteredResources}
                  projects={projects?.filter(p => isAdmin || userData?.allowed_project_ids?.includes(p.id))}
                  onDateChange={setDateRange}
                />
              )}
            </CardContent>
          </Card>
        )}

        {isAdmin && (
          <div className="mt-6">
            <AllocationEditor standaloneMode={true} />
          </div>
        )}
      </div>
    </TooltipProvider>
  );
};

export default Dashboard;
