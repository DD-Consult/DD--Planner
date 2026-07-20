import axios from 'axios';
import { toast } from 'sonner';

// Always use relative /api path - works in both preview and production
// because frontend and backend share the same domain via Kubernetes ingress
const api = axios.create({
  baseURL: '/api',
});

// Global error interceptor - show user-friendly error messages
// + surface X-Budget-Warnings header from successful responses as warning toasts
api.interceptors.response.use(
  (response) => {
    // Seamless budget hierarchy warnings — backend sets X-Budget-Warnings header
    // on successful PUT/POST calls when a save violates the budget hierarchy
    // (e.g. phase budgets exceed project budget).
    const warningsHeader = response.headers?.['x-budget-warnings'];
    if (warningsHeader && !response.config?.skipBudgetWarnings) {
      try {
        const warnings = JSON.parse(warningsHeader);
        if (Array.isArray(warnings) && warnings.length > 0) {
          // Show the first warning prominently; collapse rest into a hint
          const first = warnings[0];
          const extra = warnings.length > 1 ? ` (+${warnings.length - 1} more)` : '';
          toast.warning(`⚠️ ${first.message}${extra}`, {
            duration: 7000,
            description: warnings.length > 1
              ? warnings.slice(1).map(w => `• ${w.message}`).join('\n')
              : undefined,
          });
        }
      } catch (_e) { /* ignore malformed header */ }
    }
    
    // WBS Budget validation warnings — backend sets X-WBS-Budget-Status header
    // when WBS task creation/update causes total WBS hours to exceed project budget
    const wbsBudgetHeader = response.headers?.['x-wbs-budget-status'];
    if (wbsBudgetHeader && !response.config?.skipBudgetWarnings) {
      try {
        const budgetStatus = JSON.parse(wbsBudgetHeader);
        if (budgetStatus && !budgetStatus.is_valid && budgetStatus.warning) {
          toast.warning(`⚠️ ${budgetStatus.warning}`, {
            duration: 7000,
            description: `WBS Total: ${budgetStatus.total_wbs_hours}h / Budget: ${budgetStatus.project_budget}h`,
          });
        }
      } catch (_e) { /* ignore malformed header */ }
    }
    
    // Auto-cascade notification
    const cascaded = response.headers?.['x-cascade-updated'];
    if (cascaded && parseInt(cascaded) > 0 && !response.config?.skipBudgetWarnings) {
      toast.info(`🔗 Cascaded dates to ${cascaded} dependent task${cascaded === '1' ? '' : 's'}`, {
        duration: 4000,
      });
    }
    return response;
  },
  (error) => {
    // Extract error message
    let errorMessage = error.response?.data?.detail || 
                        error.response?.data?.message || 
                        error.message || 
                        'An unexpected error occurred';
    
    // Handle Pydantic validation errors (array of objects)
    if (typeof errorMessage === 'object') {
      if (Array.isArray(errorMessage)) {
        // It's a list of errors, take the first one or join them
        errorMessage = errorMessage.map(e => e.msg || JSON.stringify(e)).join(', ');
      } else {
        // It's a single object
        errorMessage = errorMessage.msg || JSON.stringify(errorMessage);
      }
    }
    
    // Don't show toast for auth errors (handled by login page)
    if (error.response?.status !== 401 && !error.config?.skipErrorToast) {
      toast.error(errorMessage, {
        duration: 5000,
      });
    }
    
    return Promise.reject(error);
  }
);

export const setAuthToken = (token) => {
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common['Authorization'];
  }
};

// Auth
export const login = (email, password) => {
  const formData = new FormData();
  formData.append('username', email);
  formData.append('password', password);
  return api.post('/auth/login', formData);
};

export const getMe = () => api.get('/auth/me');

export const changePassword = (oldPassword, newPassword) =>
  api.post('/auth/change-password', null, {
    params: { old_password: oldPassword, new_password: newPassword }
  });

export const getMyResource = () => api.get('/users/me/resource');

// Admin endpoints
export const createResourceUser = (resourceId, email, password) =>
  api.post('/admin/create-resource-user', null, {
    params: { resource_id: resourceId, email, password }
  });

export const getAllUsers = () => api.get('/admin/users');

export const updateUserRole = (userId, newRole) =>
  api.put(`/admin/users/${userId}/role`, null, {
    params: { new_role: newRole }
  });

export const resetUserPassword = (userId) =>
  api.put(`/admin/users/${userId}/reset-password`);


// Resources
export const getResources = () => api.get('/resources');
export const createResource = (data) => api.post('/resources', data);
export const updateResource = (id, data) => api.put(`/resources/${id}`, data);
export const deleteResource = (id) => api.delete(`/resources/${id}`);
export const deactivateResource = (id) => api.post(`/resources/${id}/deactivate`);
export const reactivateResource = (id) => api.post(`/resources/${id}/reactivate`);
export const setUserStatus = (userId, disabled) =>
  api.put(`/admin/users/${userId}/status?disabled=${disabled}`);
export const deleteUser = (userId) => api.delete(`/admin/users/${userId}`);

// Projects
export const getProjects = () => api.get('/projects');
export const getProject = (id) => api.get(`/projects/${id}`);
export const getProjectRisks = (id) => api.get(`/projects/${id}/risks`);
export const getProjectAllocations = (id) => api.get(`/projects/${id}/allocations`);
export const createProject = (data) => api.post('/projects', data);
export const createProjectWizard = (data) => api.post('/projects/wizard', data);
export const updateProject = (id, data) => api.put(`/projects/${id}`, data);
export const deleteProject = (id) => api.delete(`/projects/${id}`);
// Risks (single CRUD)
export const createRisk = (projectId, data) => api.post(`/projects/${projectId}/risks`, data);
export const updateRisk = (riskId, data) => api.put(`/risks/${riskId}`, data);
export const deleteRisk = (riskId) => api.delete(`/risks/${riskId}`);
export const generateProjectSummary = (id) => api.post(`/projects/${id}/generate-summary`);
export const updateProjectSummary = (id, summary) => 
  api.patch(`/projects/${id}/summary`, null, { params: { summary } });

// Allocation Roles
export const getAllocationRoles = () => api.get('/allocation-roles');

// Allocations
export const getAllocations = () => api.get('/allocations');
export const createAllocation = (data) => api.post('/allocations', data);
export const updateAllocation = (id, data) => api.put(`/allocations/${id}`, data);
export const confirmAllocation = (id, data) => api.put(`/allocations/${id}/confirm`, data);
export const deleteAllocation = (id) => api.delete(`/allocations/${id}`);

// My Allocations (resource self-service)
export const getMyAllocations = (period = 'month') =>
  api.get('/my-allocations', { params: { period } });

// Budget Validation
export const getBudgetHealth = (projectId) => api.get(`/projects/${projectId}/budget-health`);
export const validateAllocation = (data) => api.post('/allocations/validate', data);

// Reports
export const getCapacityReport = (startDate, endDate) =>
  api.get('/reports/capacity', {
    params: { start_date: startDate, end_date: endDate },
  });

// Client Portal
export const getClientProjects = () => api.get('/client/projects');

// Allocations by cell (for interactive grid)
export const getAllocationsByCell = (resourceId, date) =>
  api.get('/allocations/by-cell', {
    params: { resource_id: resourceId, date: date },
  });

// Leaves
export const getLeaves = () => api.get('/leaves');
export const createLeave = (data) => api.post('/leaves', data);
export const deleteLeave = (id) => api.delete(`/leaves/${id}`);

// Holidays
export const getHolidays = () => api.get('/holidays');
export const createHoliday = (data) => api.post('/holidays', data);
export const deleteHoliday = (id) => api.delete(`/holidays/${id}`);

// AI Command
export const aiCommand = (query, provider, apiKey) => 
  api.post('/ai/command', { 
    query, 
    provider, 
    api_key: apiKey 
  });

// AI-Powered Bulk Operations
export const rescheduleProject = (projectId, weeksToShift, direction = 'forward') =>
  api.post(`/projects/${projectId}/reschedule`, {
    weeks_to_shift: weeksToShift,
    shift_direction: direction
  });

export const getSmartReschedule = (projectId) =>
  api.post(`/ai/smart-reschedule/${projectId}`);

export const moveResourceBetweenProjects = (resourceId, sourceProjectId, targetProjectId, newPercentage = null) =>
  api.post('/allocations/move-resource', {
    resource_id: resourceId,
    source_project_id: sourceProjectId,
    target_project_id: targetProjectId,
    new_percentage: newPercentage
  });

export const createBulkRisks = (projectId, risks) =>
  api.post('/risks/bulk', {
    project_id: projectId,
    risks: risks
  });

export const bulkGenerateSummaries = (projectIds) =>
  api.post('/projects/bulk-generate-summaries', {
    project_ids: projectIds
  });

export const createProjectFull = (data) =>
  api.post('/projects/create-full', data);

// Project Status Updates (Weekly Check-ins)
export const createStatusUpdate = (data) =>
  api.post('/status-updates', data);

export const editStatusUpdate = (updateId, data) =>
  api.put(`/status-updates/${updateId}`, data);

export const getProjectStatusUpdates = (projectId, limit = 10) =>
  api.get(`/status-updates/project/${projectId}?limit=${limit}`);

export const getLatestStatusUpdate = (projectId) =>
  api.get(`/status-updates/latest/${projectId}`);

export const getMyProjectsForStatus = () =>
  api.get('/status-updates/my-projects');

export const getStatusOptions = () =>
  api.get('/status-options');

// Timesheet restriction check
export const checkTimesheetUpdateAllowed = () =>
  api.get('/timesheet/can-update');

// Project phases for allocation
export const getProjectPhases = (projectId) =>
  api.get(`/projects/${projectId}/phases`);

// Avatar update
export const updateAvatar = (avatarUrl) =>
  api.put('/auth/avatar', { avatar_url: avatarUrl });

// =============================================================================
// Timesheet APIs (Planned vs Actual Time Tracking)
// =============================================================================

// Create a new timesheet entry
export const createTimesheet = (data) =>
  api.post('/timesheets', data);

// Get current user's timesheets for a specific week
export const getMyWeekTimesheets = (weekStart) =>
  api.get(`/timesheets/my-week?week_start=${weekStart}&view=personal`);

// Get all timesheets for a specific week (super admin only)
export const getTimesheets = (weekStart) =>
  api.get(`/timesheets/my-week?week_start=${weekStart}&view=all`);

// Update a timesheet entry
export const updateTimesheet = (id, data) =>
  api.put(`/timesheets/${id}`, data);

// Delete a timesheet entry
export const deleteTimesheet = (id) =>
  api.delete(`/timesheets/${id}`);

// Auto-fill timesheets for the week based on allocations
export const autoFillTimesheets = (weekStart) =>
  api.post(`/timesheets/auto-fill?week_start=${weekStart}`);

// Submit all draft timesheets for the week
export const submitWeekTimesheets = (weekStart) =>
  api.post(`/timesheets/submit-week?week_start=${weekStart}`);

// =============================================================================
// Reporting APIs
// =============================================================================

// Get planned vs actual report for a project
export const getProjectTimeReport = (projectId) =>
  api.get(`/reports/planned-vs-actual/project/${projectId}`);

// Get time tracking summary for dashboard
export const getTimeTrackingSummary = () =>
  api.get('/reports/time-tracking/summary');

// =============================================================================
// AI Analysis APIs
// =============================================================================

// Get timesheet insights
export const getTimesheetInsights = (params = {}) =>
  api.post('/ai/timesheet-insights', null, { params });

// Plan future allocation
export const getPlanAllocation = (params = {}) =>
  api.post('/ai/plan-allocation', null, { params });

// Move a project phase
export const moveProjectPhase = (projectId, phaseName, daysToShift = 0, weeksToShift = 0, direction = 'forward') =>
  api.post(`/projects/${projectId}/move-phase`, null, { 
    params: { phase_name: phaseName, days_to_shift: daysToShift, weeks_to_shift: weeksToShift, direction } 
  });

// Data Cleanup (Admin)
export const scanOrphanedData = () => api.get('/admin/data-cleanup/scan');
export const executeDataCleanup = () => api.post('/admin/data-cleanup/execute');

// AI Budget Analysis
export const getProjectBudgetAnalysis = (projectId) => api.get(`/ai/project-budget-analysis/${projectId}`);
export const getPlannedVsActualOverview = () => api.get('/reports/planned-vs-actual/overview');
export const getPortfolioBudgetAnalysis = () => api.get('/ai/portfolio-budget-analysis');

// AI Settings (app-wide, super_admin only)
export const getAiSettings = () => api.get('/settings/ai');
export const updateAiSettings = (provider, apiKey) =>
  api.put('/settings/ai', null, { params: { provider, api_key: apiKey } });
export const clearAiSettings = () => api.delete('/settings/ai');

// AI Chat Agent
export const sendChatMessage = (message, sessionId) =>
  api.post('/ai/chat', { message, session_id: sessionId });
export const getChatSessions = () => api.get('/ai/chat/sessions');
export const getChatSession = (sessionId) => api.get(`/ai/chat/sessions/${sessionId}`);
export const deleteChatSession = (sessionId) => api.delete(`/ai/chat/sessions/${sessionId}`);
export const executeChatAction = (action) => api.post('/ai/chat/execute-action', action);
export const undoLastAction = (sessionId) => api.post('/ai/chat/undo', { session_id: sessionId });

// Notifications
export const getNotifications = () => api.get('/notifications');
export const getUnreadCount = () => api.get('/notifications/unread-count');
export const markNotificationRead = (id) => api.put(`/notifications/${id}/read`);
export const markAllNotificationsRead = () => api.put('/notifications/read-all');
export const deleteNotification = (id) => api.delete(`/notifications/${id}`);

// Reminders (Admin only)
export const checkTimesheetReminders = () => api.post('/reminders/check-timesheets');
export const checkAllocationReminders = () => api.post('/reminders/check-allocations');
export const getReminderStatus = () => api.get('/reminders/status');

// Client user management (admin only)
export const createClientUser = (data) =>
  api.post('/admin/clients', data);

export const getClientUsers = () => api.get('/admin/clients');

export const updateClientUser = (userId, data) =>
  api.put(`/admin/clients/${userId}`, data);

export const deleteClientUser = (userId) =>
  api.delete(`/admin/clients/${userId}`);

// ============================================================
// WBS APIs
// ============================================================

export const getProjectWBS = (projectId) =>
  api.get(`/projects/${projectId}/wbs`);

export const createWBSTask = (projectId, data) =>
  api.post(`/projects/${projectId}/wbs/tasks`, data);

export const updateWBSTask = (taskId, data) =>
  api.put(`/wbs/tasks/${taskId}`, data);

export const deleteWBSTask = (taskId) =>
  api.delete(`/wbs/tasks/${taskId}`);

export const cascadeTaskDates = (taskId, newEndDate) =>
  api.post(`/wbs/tasks/${taskId}/cascade-dates`, null, {
    params: newEndDate ? { new_end_date: newEndDate } : {}
  });

// WBS Baseline — snapshot current dates as the committed (planned) schedule
export const setWBSTaskBaseline = (taskId) =>
  api.post(`/wbs/tasks/${taskId}/set-baseline`);

export const setProjectWBSBaseline = (projectId) =>
  api.post(`/projects/${projectId}/wbs/set-baseline`);

export const aiGenerateWBS = (data) =>
  api.post('/ai/generate-wbs', data);

export const saveGeneratedWBS = (data) =>
  api.post('/ai/generate-wbs/save', data);

// WBS Timesheet Integration
export const getWBSActuals = (projectId) =>
  api.get(`/projects/${projectId}/wbs/actuals`);

export const getWBSTasksForTimesheet = (projectId, phaseId = null) =>
  api.get(`/projects/${projectId}/wbs/tasks-for-timesheet`,
    { params: phaseId ? { phase_id: phaseId } : {} }
  );

export const syncProjectDatesFromWBS = (projectId) =>
  api.post(`/projects/${projectId}/sync-dates-from-wbs`);

// Timesheet Range Reports (admin only)
export const getTimesheetRangeReport = (params) =>
  api.get('/reports/timesheets/range', { params });

export const getResourceUtilization = (params) =>
  api.get('/reports/resource-utilization', { params });

// Server-side Exports — DD-branded report (single mode)
export const exportProjectPDF = (projectId) =>
  api.get(`/projects/${projectId}/export/pdf`, { responseType: 'blob' });

export const exportProjectPPT = (projectId) =>
  api.get(`/projects/${projectId}/export/ppt`, { responseType: 'blob' });

// Server-side WBS Exports — standalone Work Breakdown Structure
export const exportProjectWBSPDF = (projectId) =>
  api.get(`/projects/${projectId}/export/wbs/pdf`, { responseType: 'blob' });

export const exportProjectWBSPPT = (projectId) =>
  api.get(`/projects/${projectId}/export/wbs/ppt`, { responseType: 'blob' });

// ─────────────────────────────────────────────────────────────
// Baselines & Change Log (PMBOK-style baseline tracking)
// ─────────────────────────────────────────────────────────────
export const listBaselines = (projectId) =>
  api.get(`/projects/${projectId}/baselines`);

export const getCurrentBaseline = (projectId) =>
  api.get(`/projects/${projectId}/baselines/current`);

export const getBaseline = (projectId, baselineId) =>
  api.get(`/projects/${projectId}/baselines/${baselineId}`);

export const createBaseline = (projectId, payload) =>
  api.post(`/projects/${projectId}/baselines`, payload);

export const patchBaseline = (projectId, baselineId, payload) =>
  api.patch(`/projects/${projectId}/baselines/${baselineId}`, payload);

export const deleteBaseline = (projectId, baselineId) =>
  api.delete(`/projects/${projectId}/baselines/${baselineId}`);

export const getVariance = (projectId, baselineId = null) =>
  baselineId
    ? api.get(`/projects/${projectId}/variance/${baselineId}`)
    : api.get(`/projects/${projectId}/variance`);

export const getChangeLog = (projectId, params = {}) =>
  api.get(`/projects/${projectId}/change-log`, { params });

// Bulk AI-polish all un-polished risks for a project
export const polishAllRisks = (projectId) =>
  api.post(`/projects/${projectId}/risks/polish-all`);

// ─────────────────────────────────────────────────────────────
// Budget Reconciliation (Budget / Estimated / Allocated / Actual)
// ─────────────────────────────────────────────────────────────
export const getBudgetReconciliation = (projectId) =>
  api.get(`/projects/${projectId}/budget-reconciliation`);

export const syncPhaseToWBS = (projectId, phaseId) =>
  api.post(`/projects/${projectId}/phases/${phaseId}/sync-to-wbs`);

// Milestone endpoints
export const completeMilestone = (taskId, completed = true) =>
  api.patch(`/wbs/tasks/${taskId}/complete-milestone`, null, { params: { completed } });

// WBS Task Comments
export const getTaskComments = (taskId) => api.get(`/wbs/tasks/${taskId}/comments`);
export const createTaskComment = (taskId, data) => api.post(`/wbs/tasks/${taskId}/comments`, data);
export const updateTaskComment = (commentId, data) => api.put(`/wbs/comments/${commentId}`, data);
export const deleteTaskComment = (commentId) => api.delete(`/wbs/comments/${commentId}`);
export const getTaskCommentCount = (taskId) => api.get(`/wbs/tasks/${taskId}/comments/count`);
export const getProjectCommentCounts = (projectId) => api.get(`/projects/${projectId}/wbs/comments/counts`);

// Dashboard Action Items
export const getActionItems = () => api.get('/dashboard/action-items');
export const generateNotifications = () => api.post('/notifications/generate');

// AI Instructions & Feedback
export const getAIInstructions = (params) => api.get('/ai/instructions', { params });
export const getProjectAIInstructions = (projectId) => api.get(`/ai/instructions/project/${projectId}`);
export const createAIInstruction = (data) => api.post('/ai/instructions', data);
export const updateAIInstruction = (id, data) => api.put(`/ai/instructions/${id}`, data);
export const deleteAIInstruction = (id) => api.delete(`/ai/instructions/${id}`);
export const submitAIFeedback = (data) => api.post('/ai/feedback', data);
export const getAIFeedbackStats = () => api.get('/ai/feedback/stats');

// AI Insights
export const getProjectHealthScore = (projectId) => api.get(`/insights/project/${projectId}/health-score`);
export const getPortfolioHealthScores = () => api.get('/insights/portfolio/health-scores');
export const getProjectPredictions = (projectId) => api.get(`/insights/project/${projectId}/predictions`);
export const getWeeklyDigest = () => api.get('/insights/weekly-digest');
export const getPortfolioTrends = () => api.get('/insights/portfolio/trends');

export default api;
