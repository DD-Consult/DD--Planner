import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { setAuthToken, getMe, getResources, getProjects, getNotifications, getUnreadCount, markNotificationRead, markAllNotificationsRead } from '../api';
import { LayoutDashboard, Users, Briefcase, Calendar, LogOut, Settings as SettingsIcon, CalendarOff, CalendarDays, FlaskConical, Clock, Sparkles, BarChart3, Bell, Check, X, User, Building2, Menu, ClipboardList, HelpCircle } from 'lucide-react';
import { Button } from './ui/button';
import { Switch } from './ui/switch';
import { Label } from './ui/label';
import ChatPanel from './ChatPanel';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from './ui/tooltip';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from './ui/popover';
import { ConfirmCommandDialog } from './ConfirmCommandDialog';
import { useSandbox } from '../contexts/SandboxContext';
import { format } from 'date-fns';

const Layout = ({ children, token, onLogout }) => {
  const location = useLocation();
  const queryClient = useQueryClient();
  const [user, setUser] = useState(null);
  const [parsedCommand, setParsedCommand] = useState(null);
  const [isConfirmDialogOpen, setIsConfirmDialogOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const { showDrafts, setShowDrafts } = useSandbox();

  useEffect(() => {
    if (token) {
      setAuthToken(token);
    }
  }, [token]);

  // Notification queries
  const { data: notifications = [] } = useQuery({
    queryKey: ['notifications'],
    queryFn: async () => { const r = await getNotifications(); return r.data; },
    enabled: !!token,
    refetchInterval: 60000, // Refetch every minute
  });

  const { data: unreadData } = useQuery({
    queryKey: ['unread-count'],
    queryFn: async () => { const r = await getUnreadCount(); return r.data; },
    enabled: !!token,
    refetchInterval: 30000, // Refetch every 30 seconds
  });

  const unreadCount = unreadData?.count || 0;

  const markReadMutation = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: () => {
      queryClient.invalidateQueries(['notifications']);
      queryClient.invalidateQueries(['unread-count']);
    },
  });

  const markAllReadMutation = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: () => {
      queryClient.invalidateQueries(['notifications']);
      queryClient.invalidateQueries(['unread-count']);
    },
  });

  // Close mobile menu when route changes
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);
  
  // Close mobile menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (isMobileMenuOpen && !e.target.closest('aside') && !e.target.closest('[data-testid="mobile-menu-toggle"]')) {
        setIsMobileMenuOpen(false);
      }
    };
    
    if (isMobileMenuOpen) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [isMobileMenuOpen]);

  const { data: userData } = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const response = await getMe();
      return response.data;
    },
    enabled: !!token,
  });

  // Fetch resources for AI command mapping
  const { data: resourcesData } = useQuery({
    queryKey: ['resources'],
    queryFn: async () => {
      const response = await getResources();
      return response.data;
    },
    enabled: !!token,
  });

  // Fetch projects for AI command mapping
  const { data: projectsData } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await getProjects();
      return response.data;
    },
    enabled: !!token,
  });

  useEffect(() => {
    if (userData) {
      setUser(userData);
    }
  }, [userData]);

  // Helper function to find resource by name (case-insensitive, partial match)
  const findResourceByName = (name) => {
    if (!resourcesData || !name) return null;
    const lowerName = name.toLowerCase();
    return resourcesData.find(r => 
      r.name.toLowerCase().includes(lowerName) || 
      lowerName.includes(r.name.toLowerCase())
    );
  };

  // Helper function to find project by name (case-insensitive, partial match)
  const findProjectByName = (name) => {
    if (!projectsData || !name) return null;
    const lowerName = name.toLowerCase();
    return projectsData.find(p => 
      p.name.toLowerCase().includes(lowerName) || 
      lowerName.includes(p.name.toLowerCase())
    );
  };

  // Transform AI response to ConfirmCommandDialog format
  const handleCommandParsed = (aiResponse) => {
    // Get current date for default dates - ALWAYS use real current date
    const today = new Date();
    const twoWeeksLater = new Date(today);
    twoWeeksLater.setDate(today.getDate() + 14);
    const formatDate = (d) => d.toISOString().split('T')[0];

    // Helper to validate and sanitize AI-returned dates
    // AI often returns outdated dates from training data, so we validate them
    const getValidDate = (aiDate, defaultDate) => {
      if (!aiDate) return formatDate(defaultDate);
      
      try {
        const parsedDate = new Date(aiDate);
        // If the date is invalid or in the past (more than 1 day ago), use default
        const oneDayAgo = new Date(today);
        oneDayAgo.setDate(today.getDate() - 1);
        
        if (isNaN(parsedDate.getTime()) || parsedDate < oneDayAgo) {
          return formatDate(defaultDate);
        }
        return aiDate;
      } catch {
        return formatDate(defaultDate);
      }
    };

    let transformedCommand = {
      original_query: aiResponse.natural_language || '',
      action: 'unknown',
      data: {},
    };

    // Handle ASSIGN_RESOURCE intent
    if (aiResponse.intent === 'ASSIGN_RESOURCE') {
      const resource = findResourceByName(aiResponse.entities?.resource_name);
      const project = findProjectByName(aiResponse.entities?.project_name);

      transformedCommand = {
        original_query: aiResponse.natural_language || '',
        action: 'create_allocation',
        data: {
          resource_id: resource?.id || null,
          resource_name: aiResponse.entities?.resource_name || 'Unknown',
          project_id: project?.id || null,
          project_name: aiResponse.entities?.project_name || 'Unknown',
          percentage: aiResponse.entities?.percentage || 50,
          start_date: getValidDate(aiResponse.entities?.start_date, today),
          end_date: getValidDate(aiResponse.entities?.end_date, twoWeeksLater),
        },
      };
    }
    // Handle CREATE_PROJECT_FULL intent - Create project with phases and allocations
    else if (aiResponse.intent === 'CREATE_PROJECT_FULL') {
      // Build allocations with resource IDs
      const allocations = (aiResponse.entities?.resource_names || []).map(name => {
        const resource = findResourceByName(name);
        return {
          resource_id: resource?.id || null,
          resource_name: name,
          percentage: aiResponse.entities?.percentage || 50,
        };
      });

      // If single resource mentioned
      if (aiResponse.entities?.resource_name && allocations.length === 0) {
        const resource = findResourceByName(aiResponse.entities.resource_name);
        allocations.push({
          resource_id: resource?.id || null,
          resource_name: aiResponse.entities.resource_name,
          percentage: aiResponse.entities?.percentage || 50,
        });
      }

      transformedCommand = {
        original_query: aiResponse.natural_language || '',
        action: 'create_project_full',
        data: {
          name: aiResponse.entities?.project_name || 'New Project',
          client_name: aiResponse.entities?.client_name || 'Unknown Client',
          status: 'Pipeline',
          phases: aiResponse.entities?.phases || [
            { name: 'Initiate', duration_weeks: 2 },
            { name: 'Plan', duration_weeks: 3 },
            { name: 'Execute', duration_weeks: 4 },
            { name: 'Close', duration_weeks: 1 },
          ],
          allocations: allocations,
        },
      };
    }
    // Handle RESCHEDULE_PROJECT intent
    else if (aiResponse.intent === 'RESCHEDULE_PROJECT') {
      const project = findProjectByName(aiResponse.entities?.project_name);
      transformedCommand = {
        original_query: aiResponse.natural_language || '',
        action: 'reschedule_project',
        data: {
          project_id: project?.id || null,
          project_name: aiResponse.entities?.project_name || 'Unknown',
          weeks_to_shift: aiResponse.entities?.weeks_to_shift || 2,
          shift_direction: aiResponse.entities?.shift_direction || 'forward',
        },
      };
    }
    // Handle MOVE_RESOURCE intent
    else if (aiResponse.intent === 'MOVE_RESOURCE') {
      const resource = findResourceByName(aiResponse.entities?.resource_name);
      const sourceProject = findProjectByName(aiResponse.entities?.source_project_name || aiResponse.entities?.project_name);
      const targetProject = findProjectByName(aiResponse.entities?.target_project_name);
      
      transformedCommand = {
        original_query: aiResponse.natural_language || '',
        action: 'move_resource',
        data: {
          resource_id: resource?.id || null,
          resource_name: aiResponse.entities?.resource_name || 'Unknown',
          source_project_id: sourceProject?.id || null,
          source_project_name: sourceProject?.name || aiResponse.entities?.source_project_name || 'Unknown',
          target_project_id: targetProject?.id || null,
          target_project_name: targetProject?.name || aiResponse.entities?.target_project_name || 'Unknown',
          new_percentage: aiResponse.entities?.percentage || null,
        },
      };
    }
    // Handle REMOVE_ALLOCATION intent
    else if (aiResponse.intent === 'REMOVE_ALLOCATION') {
      const resource = findResourceByName(aiResponse.entities?.resource_name);
      const project = findProjectByName(aiResponse.entities?.project_name);
      
      transformedCommand = {
        original_query: aiResponse.natural_language || '',
        action: 'remove_allocation',
        data: {
          resource_id: resource?.id || null,
          resource_name: aiResponse.entities?.resource_name || 'Unknown',
          project_id: project?.id || null,
          project_name: aiResponse.entities?.project_name || 'Unknown',
        },
      };
    }
    // Handle CREATE_RISK intent (supports multiple risks)
    else if (aiResponse.intent === 'CREATE_RISK') {
      const project = findProjectByName(aiResponse.entities?.project_name);
      
      // Support both single risk and multiple risks
      let risks = aiResponse.entities?.risks || [];
      if (risks.length === 0 && aiResponse.entities?.risk_description) {
        risks = [{
          description: aiResponse.entities.risk_description,
          impact: aiResponse.entities?.risk_impact || 'Medium',
          probability: aiResponse.entities?.risk_probability || 'Medium',
        }];
      }
      
      transformedCommand = {
        original_query: aiResponse.natural_language || '',
        action: 'create_risks',
        data: {
          project_id: project?.id || null,
          project_name: aiResponse.entities?.project_name || 'Unknown',
          risks: risks,
        },
      };
    }
    // Handle UPDATE_SUMMARY intent
    else if (aiResponse.intent === 'UPDATE_SUMMARY') {
      // Support both single and multiple projects
      const projectNames = aiResponse.entities?.project_names || [];
      if (aiResponse.entities?.project_name && projectNames.length === 0) {
        projectNames.push(aiResponse.entities.project_name);
      }
      
      const projectIds = projectNames.map(name => {
        const project = findProjectByName(name);
        return { id: project?.id, name: name };
      });
      
      transformedCommand = {
        original_query: aiResponse.natural_language || '',
        action: 'update_summaries',
        data: {
          projects: projectIds,
        },
      };
    }
    // Handle PROJECT_STATUS_UPDATE intent (Weekly check-in via AI)
    else if (aiResponse.intent === 'PROJECT_STATUS_UPDATE') {
      const project = findProjectByName(aiResponse.entities?.project_name);
      const statusUpdate = aiResponse.entities?.status_update || {};
      
      transformedCommand = {
        original_query: aiResponse.natural_language || '',
        action: 'project_status_update',
        data: {
          project_id: project?.id || null,
          project_name: aiResponse.entities?.project_name || 'Unknown',
          health: statusUpdate.health || 'Green',
          schedule_status: statusUpdate.schedule_status || 'On Track',
          actual_progress: statusUpdate.actual_progress, // Let backend calculate if null
          accomplishments: statusUpdate.accomplishments || '',
          blockers: statusUpdate.blockers || '',
          next_steps: statusUpdate.next_steps || '',
        },
      };
    }
    // Handle QUERY_CAPACITY intent
    else if (aiResponse.intent === 'QUERY_CAPACITY') {
      transformedCommand = {
        original_query: aiResponse.natural_language || '',
        action: 'query',
        answer: aiResponse.natural_language || 'No information available',
      };
    }
    // Handle legacy CREATE_PROJECT intent (simple project creation)
    else if (aiResponse.intent === 'CREATE_PROJECT') {
      transformedCommand = {
        original_query: aiResponse.natural_language || '',
        action: 'create_project',
        data: {
          name: aiResponse.entities?.project_name || 'New Project',
          client_name: aiResponse.entities?.client_name || 'Unknown Client',
          status: 'Pipeline',
          start_date: getValidDate(aiResponse.entities?.start_date, today),
          end_date: getValidDate(aiResponse.entities?.end_date, twoWeeksLater),
        },
      };
    }
    // Handle TIMESHEET_INSIGHTS intent - show insights as query response
    else if (aiResponse.intent === 'TIMESHEET_INSIGHTS') {
      transformedCommand = {
        original_query: aiResponse.natural_language || '',
        action: 'timesheet_insights',
        data: {
          project_name: aiResponse.entities?.project_name || null,
          resource_name: aiResponse.entities?.resource_name || null,
          time_period: aiResponse.entities?.time_period || null,
          analysis_type: aiResponse.entities?.analysis_type || 'patterns',
        },
      };
    }
    // Handle PLAN_FUTURE_ALLOCATION intent
    else if (aiResponse.intent === 'PLAN_FUTURE_ALLOCATION') {
      transformedCommand = {
        original_query: aiResponse.natural_language || '',
        action: 'plan_allocation',
        data: {
          start_date: aiResponse.entities?.start_date || null,
          end_date: aiResponse.entities?.end_date || null,
          required_count: aiResponse.entities?.resource_names?.length || 1,
        },
      };
    }
    // Handle MOVE_PROJECT_PHASE intent
    else if (aiResponse.intent === 'MOVE_PROJECT_PHASE') {
      const project = findProjectByName(aiResponse.entities?.project_name);
      transformedCommand = {
        original_query: aiResponse.natural_language || '',
        action: 'move_project_phase',
        data: {
          project_id: project?.id || null,
          project_name: aiResponse.entities?.project_name || 'Unknown',
          phase_name: aiResponse.entities?.phase_name || 'Unknown',
          days_to_shift: aiResponse.entities?.days_to_shift || 0,
          weeks_to_shift: aiResponse.entities?.weeks_to_shift || 0,
          shift_direction: aiResponse.entities?.shift_direction || 'forward',
        },
      };
    }
    // Handle BUDGET_ANALYSIS intent
    else if (aiResponse.intent === 'BUDGET_ANALYSIS') {
      const project = findProjectByName(aiResponse.entities?.project_name);
      transformedCommand = {
        original_query: aiResponse.natural_language || '',
        action: 'budget_analysis',
        data: {
          project_id: project?.id || null,
          project_name: aiResponse.entities?.project_name || null,
        },
      };
    }
    // Unknown intent - show as query response
    else {
      transformedCommand = {
        original_query: aiResponse.natural_language || '',
        action: 'query',
        answer: aiResponse.natural_language || 'Command not recognized. Please try a different phrasing.',
      };
    }

    setParsedCommand(transformedCommand);
    setIsCommandBarOpen(false);
    setIsConfirmDialogOpen(true);
  };

  const handleConfirmDialogClose = () => {
    setIsConfirmDialogOpen(false);
    setParsedCommand(null);
  };

  const navItems = [
    { path: '/', label: 'Dashboard', icon: LayoutDashboard, roles: ['admin', 'super_admin', 'resource'], tooltip: 'Command center with portfolio overview' },
    { path: '/portal', label: 'My Projects', icon: Briefcase, roles: ['client'], tooltip: 'View your assigned projects' },
    { path: '/resources', label: 'Resources', icon: Users, roles: ['admin', 'super_admin'], tooltip: 'Manage team members' },
    { path: '/projects', label: 'Projects', icon: Briefcase, roles: ['admin', 'super_admin', 'resource'], tooltip: 'View and manage all projects' },
    { path: '/portfolio', label: 'Portfolio', icon: Building2, roles: ['admin', 'super_admin'], tooltip: 'Company-wide portfolio view with timeline and hours analysis' },
    { path: '/my-allocations', label: 'My Allocations', icon: User, roles: ['resource', 'contractor'], tooltip: 'View your project allocations and capacity' },
    { path: '/allocations', label: 'Allocations', icon: Calendar, roles: ['admin', 'super_admin'], tooltip: 'Manage resource assignments' },
    { path: '/my-timesheets', label: 'My Timesheets', icon: ClipboardList, roles: ['resource', 'contractor'], tooltip: 'View your timesheet history and autofill current week' },
    { path: '/users', label: 'Users', icon: Users, roles: ['admin', 'super_admin'], tooltip: 'Manage user accounts and roles' },
    { path: '/manage-timesheets', label: 'Manage Timesheets', icon: Clock, roles: ['super_admin'], tooltip: 'View and edit all user timesheets' },
    { path: '/leaves', label: 'Time Off', icon: CalendarOff, roles: ['admin', 'super_admin', 'resource'], tooltip: 'Track vacations and holidays' },
    { path: '/holidays', label: 'Holidays', icon: CalendarDays, roles: ['admin', 'super_admin', 'resource'], tooltip: 'Manage company holidays' },
    { path: '/reports', label: 'Reports', icon: BarChart3, roles: ['admin', 'super_admin'], tooltip: 'Budget & actuals reporting' },
    { path: '/timesheets/reports', label: 'Timesheet Reports', icon: BarChart3, roles: ['admin', 'super_admin'], tooltip: 'Aggregated timesheet analysis with date ranges' },
    { path: '/settings', label: 'Settings', icon: SettingsIcon, roles: ['super_admin'], tooltip: 'Configure AI integrations' },
    { path: '/help', label: 'Help & Guide', icon: HelpCircle, roles: ['admin', 'super_admin', 'resource', 'contractor', 'client'], tooltip: 'How to use DD Planner' },
  ];

  const filteredNavItems = navItems.filter(item => 
    item.roles.includes(user?.role)
  );

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-[#F8FAFC]">
        {/* Mobile/Tablet Top Header — visible below lg breakpoint */}
        <div className="lg:hidden fixed top-0 left-0 right-0 h-16 bg-[#0B1120] border-b border-[#1A2332] z-50 flex items-center justify-between px-4" data-testid="mobile-header">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="p-2 rounded-lg text-[#94A3B8] hover:bg-[#1A2332] hover:text-white transition-colors"
              data-testid="mobile-menu-toggle"
              aria-label="Toggle menu"
            >
              {isMobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
            </button>
            <span className="text-white text-sm font-semibold" style={{ fontFamily: 'Space Grotesk' }}>DD Planner</span>
          </div>
          <div className="flex items-center gap-2">
            {/* Mobile Notification Bell */}
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="relative h-9 w-9 p-0 text-[#94A3B8] hover:text-white hover:bg-[#1A2332]"
                  data-testid="mobile-notification-bell"
                >
                  <Bell size={18} />
                  {unreadCount > 0 && (
                    <span className="absolute -top-1 -right-1 bg-[#EF4444] text-white text-[10px] font-bold rounded-full h-5 w-5 flex items-center justify-center">
                      {unreadCount > 9 ? '9+' : unreadCount}
                    </span>
                  )}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-80 p-0" align="end">
                <div className="flex items-center justify-between p-3 border-b">
                  <h4 className="font-semibold text-sm">Notifications</h4>
                  {unreadCount > 0 && (
                    <Button variant="ghost" size="sm" className="h-7 text-xs text-[#1570EF]" onClick={() => markAllReadMutation.mutate()}>
                      Mark all read
                    </Button>
                  )}
                </div>
                <div className="max-h-60 overflow-y-auto">
                  {notifications.length === 0 ? (
                    <div className="p-4 text-center text-sm text-[#667085]">No notifications</div>
                  ) : (
                    notifications.slice(0, 5).map((notif) => (
                      <div key={notif.id} className={`p-3 border-b last:border-b-0 ${!notif.read ? 'bg-[#1570EF]/5' : ''}`}
                        onClick={() => !notif.read && markReadMutation.mutate(notif.id)}>
                        <div className="font-medium text-sm">{notif.title}</div>
                        <div className="text-xs text-[#667085] mt-0.5 line-clamp-2">{notif.message}</div>
                      </div>
                    ))
                  )}
                </div>
              </PopoverContent>
            </Popover>
            {user && (
              <span className="text-xs text-[#64748B] hidden sm:inline">{user.email}</span>
            )}
          </div>
        </div>

        {/* Mobile Menu Backdrop — below the header */}
        {isMobileMenuOpen && (
          <div
            className="lg:hidden fixed top-16 left-0 right-0 bottom-0 bg-black bg-opacity-50 z-35"
            style={{ zIndex: 35 }}
            onClick={() => setIsMobileMenuOpen(false)}
          />
        )}

        <div className="min-h-screen">
          {/* Sidebar - Desktop always visible, Mobile slide-in below header */}
          <aside className={`
            fixed top-16 lg:top-0 left-0 h-[calc(100vh-4rem)] lg:h-screen w-[260px] bg-[#0B1120] border-r border-[#1A2332] z-40
            transition-transform duration-300 ease-in-out
            ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          `} data-testid="sidebar">
            <div className="text-white p-6 h-full flex flex-col overflow-hidden">
              {/* Logo */}
              <div className="mb-8">
              <img 
                src="https://customer-assets.emergentagent.com/job_resourcy/artifacts/tongpt22_Options%205-transparent%20background%20landscape%20copy%20%282%29.png"
                alt="DD Consulting"
                className="h-12 w-auto mb-2"
              />
              <div className="text-xs text-[#64748B] uppercase tracking-wider font-semibold" style={{ fontFamily: 'Space Grotesk' }}>
                DD Planner
              </div>
            </div>

            {/* Navigation — scrollable when many items */}
            <nav className="space-y-1 flex-1 overflow-y-auto min-h-0 pr-1 -mr-1 scrollbar-thin">
              {filteredNavItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path;
                return (
                  <Tooltip key={item.path}>
                    <TooltipTrigger asChild>
                      <Link
                        to={item.path}
                        className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                          isActive
                            ? 'bg-[#1570EF] text-white shadow-lg shadow-[#1570EF]/20'
                            : 'text-[#94A3B8] hover:bg-[#1A2332] hover:text-white'
                        }`}
                      >
                        <Icon size={20} />
                        <span>{item.label}</span>
                      </Link>
                    </TooltipTrigger>
                    <TooltipContent side="right">
                      <p>{item.tooltip}</p>
                    </TooltipContent>
                  </Tooltip>
                );
              })}
            </nav>

            {/* User Info & Logout */}
            <div className="pt-6 border-t border-[#1A2332]">
              {user && (
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-white">{user.email}</div>
                    <div className="text-xs text-[#64748B] capitalize">{user.role}</div>
                  </div>
                  {/* Notification Bell */}
                  <Popover open={isNotificationsOpen} onOpenChange={setIsNotificationsOpen}>
                    <PopoverTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="relative h-9 w-9 p-0 text-[#94A3B8] hover:text-white hover:bg-[#1A2332]"
                        data-testid="notification-bell"
                      >
                        <Bell size={18} />
                        {unreadCount > 0 && (
                          <span className="absolute -top-1 -right-1 bg-[#EF4444] text-white text-[10px] font-bold rounded-full h-5 w-5 flex items-center justify-center">
                            {unreadCount > 9 ? '9+' : unreadCount}
                          </span>
                        )}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-80 p-0" align="end" side="top">
                      <div className="flex items-center justify-between p-3 border-b">
                        <h4 className="font-semibold text-sm">Notifications</h4>
                        {unreadCount > 0 && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs text-[#1570EF]"
                            onClick={() => markAllReadMutation.mutate()}
                          >
                            Mark all read
                          </Button>
                        )}
                      </div>
                      <div className="max-h-80 overflow-y-auto">
                        {notifications.length === 0 ? (
                          <div className="p-6 text-center text-sm text-[#667085]">
                            No notifications
                          </div>
                        ) : (
                          notifications.slice(0, 10).map((notif) => (
                            <div
                              key={notif.id}
                              className={`p-3 border-b last:border-b-0 hover:bg-[#F9FAFB] cursor-pointer ${!notif.read ? 'bg-[#1570EF]/5' : ''}`}
                              onClick={() => !notif.read && markReadMutation.mutate(notif.id)}
                            >
                              <div className="flex items-start gap-2">
                                <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${
                                  notif.priority === 'high' ? 'bg-[#EF4444]' : 
                                  notif.type.includes('ending') ? 'bg-[#F4B740]' : 'bg-[#1570EF]'
                                }`} />
                                <div className="flex-1 min-w-0">
                                  <div className="font-medium text-sm text-[#0B1220]">{notif.title}</div>
                                  <div className="text-xs text-[#667085] mt-0.5 line-clamp-2">{notif.message}</div>
                                  <div className="text-[10px] text-[#98A2B3] mt-1">
                                    {notif.created_at ? format(new Date(notif.created_at), 'MMM d, h:mm a') : ''}
                                  </div>
                                </div>
                                {!notif.read && (
                                  <div className="w-2 h-2 rounded-full bg-[#1570EF] shrink-0" />
                                )}
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    </PopoverContent>
                  </Popover>
                </div>
              )}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    onClick={onLogout}
                    className="w-full bg-transparent border-[#1A2332] text-[#94A3B8] hover:bg-[#1A2332] hover:text-white"
                    data-testid="logout-button"
                  >
                    <LogOut size={16} className="mr-2" />
                    Sign Out
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="right">
                  <p>Sign out of your account</p>
                </TooltipContent>
              </Tooltip>
            </div>
            </div>
          </aside>

          {/* Main Content — offset for fixed sidebar on desktop */}
          <main className="min-h-screen pt-16 lg:pt-0 lg:ml-[260px]">
            {/* Sandbox Toggle Bar */}
            {(user?.role === 'admin' || user?.role === 'super_admin') && (
              <div className="bg-white border-b border-[#E6E8EC] px-4 sm:px-6 lg:px-8 py-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <FlaskConical size={18} className="text-[#F97316]" />
                    <Label htmlFor="sandbox-toggle" className="text-sm font-medium cursor-pointer">
                      Show Scenario/Drafts
                    </Label>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Switch
                          id="sandbox-toggle"
                          checked={showDrafts}
                          onCheckedChange={setShowDrafts}
                          data-testid="sandbox-toggle"
                        />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>Toggle to show/hide draft projects and scenarios</p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  {showDrafts && (
                    <div className="flex items-center gap-2 text-xs text-[#F97316] bg-[#FFF8E5] px-3 py-1 rounded-full">
                      <FlaskConical size={14} />
                      Scenario Mode Active
                    </div>
                  )}
                </div>
              </div>
            )}
            <div className={`px-4 sm:px-6 lg:px-8 py-6`}>{children}</div>
          </main>
        </div>

        {/* Confirm Command Dialog */}
        {(user?.role === 'admin' || user?.role === 'super_admin') && (
          <ConfirmCommandDialog
            isOpen={isConfirmDialogOpen}
            onClose={handleConfirmDialogClose}
            parsedCommand={parsedCommand}
          />
        )}

        {/* AI Chat Panel - accessible from every page */}
        <ChatPanel />
      </div>
    </TooltipProvider>
  );
};

export default Layout;
