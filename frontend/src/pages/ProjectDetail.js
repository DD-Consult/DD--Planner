import React, { useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getProject, getProjectRisks, getProjectAllocations, getResources, generateProjectSummary, updateProjectSummary, getProjectStatusUpdates, getProjectTimeReport, getProjectBudgetAnalysis, createRisk, updateRisk, deleteRisk, updateProject, polishAllRisks, editStatusUpdate, syncProjectDatesFromWBS, getMe, getStatusOptions, createStatusUpdate, createAllocation, updateAllocation, deleteAllocation, getBudgetHealth } from '../api';
import { format, differenceInDays, differenceInBusinessDays } from 'date-fns';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Textarea } from '../components/ui/textarea';
import { Input } from '../components/ui/input';
import WeekdayDateInput from '../components/ui/weekday-date-input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../components/ui/alert-dialog';
import { Label } from '../components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import PhaseVisualizer from '../components/PhaseVisualizer';
import BudgetHealthBanner from '../components/BudgetHealthBanner';
import PhaseAllocationEditor from '../components/PhaseAllocationEditor';
import AIRescheduleDialog from '../components/AIRescheduleDialog';
import { formatAllocation } from '../utils/capacityHelpers';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../components/ui/tooltip';
import {
  ArrowLeft, 
  Calendar, 
  Users, 
  AlertTriangle, 
  CheckCircle2, 
  Printer,
  TrendingUp,
  Target,
  Shield,
  Clock,
  FileText,
  UserCircle,
  Settings as SettingsIcon,
  Sparkles,
  Save,
  Loader2,
  Crown,
  ExternalLink,
  Plus,
  Edit2,
  Trash2,
  ShieldAlert,
  ListTodo,
  GitCompare,
  Info,
  Mail,
  Phone,
  Building2
} from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { Avatar, AvatarImage, AvatarFallback } from '../components/ui/avatar';
import { toast } from 'sonner';
import WBSView from '../components/WBSView';
import BaselinesView from '../components/BaselinesView';
import BudgetReconciliation from '../components/BudgetReconciliation';
import EditStatusUpdateDialog from '../components/EditStatusUpdateDialog';
import AIInstructionsPanel from '../components/AIInstructionsPanel';
import AIFeedbackButtons from '../components/AIFeedbackButtons';
import ProjectHealthScore from '../components/ProjectHealthScore';
import ProjectPredictions from '../components/ProjectPredictions';
import AIMemoryPanel from '../components/AIMemoryPanel';

// Safe date formatting helper
const safeFormatDate = (dateStr, formatStr = 'MMM d, yyyy') => {
  try {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return 'N/A';
    return format(date, formatStr);
  } catch (e) {
    return 'N/A';
  }
};

// Safe difference in business days helper (Mon-Fri only)
const safeDifferenceInDays = (date1, date2) => {
  try {
    const d1 = new Date(date1);
    const d2 = new Date(date2);
    if (isNaN(d1.getTime()) || isNaN(d2.getTime())) return 1;
    const diff = differenceInBusinessDays(d1, d2);
    return Math.abs(diff) || 1;
  } catch (e) {
    return 1;
  }
};

const ProjectDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('overview');
  const [editedSummary, setEditedSummary] = useState('');
  const [isEditingSummary, setIsEditingSummary] = useState(false);
  
  // FIX #5: Project edit state
  const [isEditingProject, setIsEditingProject] = useState(false);
  const [editedProject, setEditedProject] = useState({});
  const [phaseToDelete, setPhaseToDelete] = useState(null);
  
  // CHANGE 2: Separate phase editing state (Settings tab)
  const [isEditingPhases, setIsEditingPhases] = useState(false);
  const [editedPhases, setEditedPhases] = useState([]);
  
  // Admin edit status update state
  const [showEditStatusDialog, setShowEditStatusDialog] = useState(false);
  const [editingStatusUpdate, setEditingStatusUpdate] = useState(null);
  const [showAIReschedule, setShowAIReschedule] = useState(false);
  
  // CHANGE 1: Add status update dialog state
  const [showAddStatusDialog, setShowAddStatusDialog] = useState(false);
  const [statusForm, setStatusForm] = useState({
    health: 'Green',
    schedule_status: 'On Track',
    actual_progress: '',
    accomplishments: '',
    blockers: '',
    next_steps: '',
    notes: '',
  });
  
  // Risk dialog state
  const [showRiskDialog, setShowRiskDialog] = useState(false);
  const [editingRisk, setEditingRisk] = useState(null); // null = create mode, object = edit mode
  const [riskForm, setRiskForm] = useState({
    description: '',
    impact: 'Medium',
    probability: 'Medium',
    mitigation: '',
    status: 'Active',
    category: 'Risk',
  });
  
  // Allocation dialog state
  const [showAllocDialog, setShowAllocDialog] = useState(false);
  const [editingAlloc, setEditingAlloc] = useState(null); // null = create, object = edit
  const [allocForm, setAllocForm] = useState({
    resource_id: '',
    start_date: '',
    end_date: '',
    percentage: 50,
    role: '',
    allocation_type: 'percentage', // 'percentage' | 'hours'
    hours: '',
  });
  const [allocToDelete, setAllocToDelete] = useState(null);
  
  const queryClient = useQueryClient();

  // Fetch project data
  const { data: project, isLoading: projectLoading } = useQuery({
    queryKey: ['project', id],
    queryFn: async () => {
      const response = await getProject(id);
      return response.data;
    },
  });

  const { data: risks } = useQuery({
    queryKey: ['projectRisks', id],
    queryFn: async () => {
      const response = await getProjectRisks(id);
      return response.data;
    },
    enabled: !!id,
  });

  const { data: allocations } = useQuery({
    queryKey: ['projectAllocations', id],
    queryFn: async () => {
      const response = await getProjectAllocations(id);
      return response.data;
    },
    enabled: !!id,
  });

  const { data: resources } = useQuery({
    queryKey: ['resources'],
    queryFn: async () => {
      const response = await getResources();
      return response.data;
    },
  });

  // Fetch budget health for allocation validation
  const { data: budgetHealth } = useQuery({
    queryKey: ['budgetHealth', id],
    queryFn: async () => {
      const response = await getBudgetHealth(id);
      return response.data;
    },
    enabled: !!id,
  });

  // Fetch status updates for this project
  const { data: statusUpdates = [] } = useQuery({
    queryKey: ['projectStatusUpdates', id],
    queryFn: async () => {
      const response = await getProjectStatusUpdates(id, 5); // Get last 5 updates
      return response.data;
    },
    enabled: !!id,
  });

  // Fetch current user for admin check
  const { data: currentUser } = useQuery({
    queryKey: ['currentUser'],
    queryFn: async () => {
      const response = await getMe();
      return response.data;
    },
  });

  // Fetch status options for edit dialog
  const { data: statusOptions } = useQuery({
    queryKey: ['statusOptions'],
    queryFn: async () => {
      const response = await getStatusOptions();
      return response.data;
    },
  });

  const isAdmin = currentUser?.role === 'admin' || currentUser?.role === 'super_admin';
  const isLead = !!(currentUser?.resource_id && project?.project_lead_id && currentUser.resource_id === project.project_lead_id);

  // Risk mutations
  const createRiskMutation = useMutation({
    mutationFn: (data) => createRisk(id, data),
    onSuccess: () => {
      toast.success('Risk added');
      queryClient.invalidateQueries(['projectRisks', id]);
      queryClient.invalidateQueries(['portfolioHealthScores']); // Cross-page: risk affects health
      resetRiskDialog();
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to add risk'),
  });
  const updateRiskMutation = useMutation({
    mutationFn: ({ riskId, data }) => updateRisk(riskId, data),
    onSuccess: () => {
      toast.success('Risk updated');
      queryClient.invalidateQueries(['projectRisks', id]);
      queryClient.invalidateQueries(['portfolioHealthScores']); // Cross-page: risk affects health
      resetRiskDialog();
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to update risk'),
  });
  const deleteRiskMutation = useMutation({
    mutationFn: (riskId) => deleteRisk(riskId),
    onSuccess: () => {
      toast.success('Risk removed');
      queryClient.invalidateQueries(['projectRisks', id]);
      queryClient.invalidateQueries(['portfolioHealthScores']); // Cross-page: risk affects health
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to delete risk'),
  });

  const resetRiskDialog = () => {
    setShowRiskDialog(false);
    setEditingRisk(null);
    setRiskForm({
      description: '',
      impact: 'Medium',
      probability: 'Medium',
      mitigation: '',
      status: 'Active',
      category: 'Risk',
    });
  };
  const openCreateRiskDialog = () => {
    setEditingRisk(null);
    setRiskForm({
      description: '',
      impact: 'Medium',
      probability: 'Medium',
      mitigation: '',
      status: 'Active',
      category: 'Risk',
    });
    setShowRiskDialog(true);
  };
  const openEditRiskDialog = (risk) => {
    setEditingRisk(risk);
    setRiskForm({
      description: risk.description || '',
      impact: risk.impact || 'Medium',
      probability: risk.probability || 'Medium',
      mitigation: risk.mitigation || '',
      status: risk.status || 'Active',
      category: risk.category || 'Risk',
    });
    setShowRiskDialog(true);
  };
  const submitRiskDialog = () => {
    if (!riskForm.description.trim()) {
      toast.error('Please enter a description');
      return;
    }
    if (editingRisk) {
      updateRiskMutation.mutate({ riskId: editingRisk.id, data: riskForm });
    } else {
      createRiskMutation.mutate(riskForm);
    }
  };
  const quickChangeStatus = (risk, newStatus) => {
    updateRiskMutation.mutate({ riskId: risk.id, data: { status: newStatus } });
  };

  // Allocation mutations
  const createAllocationMutation = useMutation({
    mutationFn: (data) => createAllocation(data),
    onSuccess: () => {
      toast.success('Allocation added');
      queryClient.invalidateQueries(['projectAllocations', id]);
      queryClient.invalidateQueries(['allocations']);
      queryClient.invalidateQueries(['budgetReconciliation', id]);
      queryClient.invalidateQueries(['project', id]);
      queryClient.invalidateQueries(['budgetHealth', id]);
      queryClient.invalidateQueries(['portfolioHealthScores']);
      resetAllocDialog();
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to add allocation'),
  });

  const updateAllocationMutation = useMutation({
    mutationFn: ({ allocId, data }) => updateAllocation(allocId, data),
    onSuccess: () => {
      toast.success('Allocation updated');
      queryClient.invalidateQueries(['projectAllocations', id]);
      queryClient.invalidateQueries(['allocations']);
      queryClient.invalidateQueries(['budgetReconciliation', id]);
      queryClient.invalidateQueries(['project', id]);
      queryClient.invalidateQueries(['budgetHealth', id]);
      queryClient.invalidateQueries(['portfolioHealthScores']);
      resetAllocDialog();
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to update allocation'),
  });

  const deleteAllocationMutation = useMutation({
    mutationFn: (allocId) => deleteAllocation(allocId),
    onSuccess: () => {
      toast.success('Allocation removed');
      queryClient.invalidateQueries(['projectAllocations', id]);
      queryClient.invalidateQueries(['allocations']);
      queryClient.invalidateQueries(['budgetReconciliation', id]);
      queryClient.invalidateQueries(['project', id]);
      queryClient.invalidateQueries(['budgetHealth', id]);
      queryClient.invalidateQueries(['portfolioHealthScores']);
      setAllocToDelete(null);
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to delete allocation'),
  });

  // Allocation dialog handlers
  const resetAllocDialog = () => {
    setShowAllocDialog(false);
    setEditingAlloc(null);
    setAllocForm({
      resource_id: '',
      start_date: '',
      end_date: '',
      percentage: 50,
      role: '',
      allocation_type: 'percentage',
      hours: '',
    });
  };

  const openCreateAllocDialog = () => {
    setEditingAlloc(null);
    setAllocForm({
      resource_id: '',
      start_date: project?.start_date ? format(new Date(project.start_date), 'yyyy-MM-dd') : '',
      end_date: project?.end_date ? format(new Date(project.end_date), 'yyyy-MM-dd') : '',
      percentage: 50,
      role: '',
      allocation_type: 'percentage',
      hours: '',
    });
    setShowAllocDialog(true);
  };

  const openEditAllocDialog = (alloc) => {
    setEditingAlloc(alloc);
    const isHours = alloc.allocation_type === 'hours';
    setAllocForm({
      resource_id: alloc.resource_id,
      start_date: format(new Date(alloc.start_date), 'yyyy-MM-dd'),
      end_date: format(new Date(alloc.end_date), 'yyyy-MM-dd'),
      percentage: alloc.percentage,
      role: alloc.role || '',
      allocation_type: isHours ? 'hours' : 'percentage',
      hours: isHours ? (alloc.hours || '') : '',
    });
    setShowAllocDialog(true);
  };

  const submitAllocDialog = () => {
    if (!allocForm.resource_id) {
      toast.error('Please select a resource');
      return;
    }
    if (!allocForm.start_date || !allocForm.end_date) {
      toast.error('Please select start and end dates');
      return;
    }

    const isHours = allocForm.allocation_type === 'hours';

    if (isHours) {
      const h = parseFloat(allocForm.hours);
      if (!h || h <= 0) {
        toast.error('Please enter the total hours');
        return;
      }
    } else {
      if (allocForm.percentage <= 0 || allocForm.percentage > 200) {
        toast.error('Allocation percentage must be between 1 and 200');
        return;
      }
    }

    const dataToSend = {
      project_id: id,
      resource_id: allocForm.resource_id,
      start_date: allocForm.start_date,
      end_date: allocForm.end_date,
      allocation_type: allocForm.allocation_type,
      percentage: isHours ? 0 : parseFloat(allocForm.percentage),
      hours: isHours ? parseFloat(allocForm.hours) : null,
      role: allocForm.role || null,
    };

    if (editingAlloc) {
      updateAllocationMutation.mutate({ allocId: editingAlloc.id, data: dataToSend });
    } else {
      createAllocationMutation.mutate(dataToSend);
    }
  };

  const confirmDeleteAlloc = () => {
    if (allocToDelete) {
      deleteAllocationMutation.mutate(allocToDelete.id);
    }
  };

  // Fetch time tracking report for this project
  const { data: timeReport, isLoading: timeReportLoading } = useQuery({
    queryKey: ['projectTimeReport', id],
    queryFn: async () => {
      const response = await getProjectTimeReport(id);
      return response.data;
    },
    enabled: !!id,
  });

  // AI Budget Analysis - auto-loads
  const { data: budgetAnalysis, isLoading: analysisLoading, refetch: refetchAnalysis } = useQuery({
    queryKey: ['projectBudgetAnalysis', id],
    queryFn: async () => {
      const response = await getProjectBudgetAnalysis(id);
      return response.data;
    },
    enabled: !!id,
    staleTime: 60 * 1000, // Cache for 1 minute (AI analysis is expensive)
    retry: 1,
  });

  // AI Summary mutations
  const generateSummaryMutation = useMutation({
    mutationFn: () => generateProjectSummary(id),
    onSuccess: (response) => {
      queryClient.invalidateQueries(['project', id]);
      queryClient.invalidateQueries(['projects']); // Cross-page: Dashboard project list
      setEditedSummary(response.data.summary);
      toast.success('Summary generated successfully');
    },
    onError: (error) => {
      toast.error('Failed to generate summary');
      console.error('Generate summary error:', error);
    },
  });

  const updateSummaryMutation = useMutation({
    mutationFn: (summary) => updateProjectSummary(id, summary),
    onSuccess: () => {
      queryClient.invalidateQueries(['project', id]);
      setIsEditingSummary(false);
      toast.success('Summary saved');
    },
    onError: (error) => {
      toast.error('Failed to save summary');
      console.error('Update summary error:', error);
    },
  });

  // FIX #5: Project update mutation
  const updateProjectMutation = useMutation({
    mutationFn: (data) => updateProject(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['project', id]);
      queryClient.invalidateQueries(['project-allocations', id]);
      queryClient.invalidateQueries(['projects']); // Cross-page: Dashboard & Projects list
      queryClient.invalidateQueries(['portfolioHealthScores']); // Cross-page: Dashboard health badges
      queryClient.invalidateQueries(['actionItems']); // Cross-page: Dashboard action items
      setIsEditingProject(false);
      toast.success('Project updated successfully');
    },
    onError: (error) => {
      toast.error('Failed to update project');
      console.error('Update project error:', error);
    },
  });

  // CHANGE 1: Create status update mutation
  const createStatusUpdateMutation = useMutation({
    mutationFn: (data) => createStatusUpdate(data),
    onSuccess: () => {
      queryClient.invalidateQueries(['projectStatusUpdates', id]);
      queryClient.invalidateQueries(['project', id]);
      queryClient.invalidateQueries(['projects']); // Cross-page: Dashboard
      queryClient.invalidateQueries(['portfolioHealthScores']); // Cross-page: Dashboard health
      queryClient.invalidateQueries(['actionItems']); // Cross-page: Dashboard action items
      setShowAddStatusDialog(false);
      setStatusForm({
        health: 'Green',
        schedule_status: 'On Track',
        actual_progress: '',
        accomplishments: '',
        blockers: '',
        next_steps: '',
        notes: '',
      });
      toast.success('Status update added successfully');
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to add status update');
      console.error('Create status update error:', error);
    },
  });

  // CHANGE 2: Update phases only mutation
  const updatePhasesMutation = useMutation({
    mutationFn: (phases) => updateProject(id, { phases }),
    onSuccess: () => {
      queryClient.invalidateQueries(['project', id]);
      queryClient.invalidateQueries(['projects']); // Cross-page: Dashboard & Projects list
      setIsEditingPhases(false);
      toast.success('Phases updated successfully');
    },
    onError: (error) => {
      toast.error('Failed to update phases');
      console.error('Update phases error:', error);
    },
  });

  const handleGenerateSummary = () => {
    generateSummaryMutation.mutate();
  };

  const handleSaveSummary = () => {
    updateSummaryMutation.mutate(editedSummary);
  };

  const handleEditSummary = () => {
    setEditedSummary(project?.status_summary || '');
    setIsEditingSummary(true);
  };

  // FIX #5: Project edit handlers
  const handleEditProject = () => {
    setEditedProject({
      name: project?.name || '',
      client_name: project?.client_name || '',
      status: project?.status || 'Active',
      start_date: project?.start_date ? format(new Date(project.start_date), 'yyyy-MM-dd') : '',
      end_date: project?.end_date ? format(new Date(project.end_date), 'yyyy-MM-dd') : '',
      project_lead_id: project?.project_lead_id || '',
      google_drive_url: project?.google_drive_url || '',
      project_objective: project?.project_objective || '',
      budgeted_hours: project?.budgeted_hours || '',
      main_contact_name: project?.main_contact_name || '',
      main_contact_email: project?.main_contact_email || '',
      main_contact_phone: project?.main_contact_phone || '',
      main_contact_role: project?.main_contact_role || '',
      phases: project?.phases ? JSON.parse(JSON.stringify(project.phases)) : [], // Deep copy
    });
    setIsEditingProject(true);
  };

  const handleSaveProject = () => {
    // Convert empty strings to null for optional fields
    const dataToSend = {
      ...editedProject,
      project_lead_id: editedProject.project_lead_id || null,
      google_drive_url: editedProject.google_drive_url || null,
      project_objective: editedProject.project_objective || null,
      budgeted_hours: editedProject.budgeted_hours ? parseFloat(editedProject.budgeted_hours) : null,
      phases: editedProject.phases?.map(p => ({
        ...p,
        budgeted_hours: p.budgeted_hours === '' || p.budgeted_hours === null ? null : parseFloat(p.budgeted_hours)
      })) || [],
    };
    
    // Validate phase dates against project dates
    const projectStart = new Date(dataToSend.start_date);
    const projectEnd = new Date(dataToSend.end_date);
    let hasDateWarning = false;
    
    dataToSend.phases.forEach(phase => {
      const phaseStart = new Date(phase.start_date);
      const phaseEnd = new Date(phase.end_date);
      if (phaseStart < projectStart || phaseEnd > projectEnd) {
        hasDateWarning = true;
      }
    });
    
    if (hasDateWarning) {
      toast.warning('Some phase dates fall outside project timeline');
    }
    
    updateProjectMutation.mutate(dataToSend);
  };

  const handleCancelEditProject = () => {
    setIsEditingProject(false);
    setEditedProject({});
  };

  // Phase management handlers
  const handleAddPhase = () => {
    const newPhase = {
      id: crypto.randomUUID(),
      name: '',
      start_date: editedProject.start_date || '',
      end_date: editedProject.end_date || '',
      status: 'Not Started',
      budgeted_hours: '',
    };
    setEditedProject({
      ...editedProject,
      phases: [...(editedProject.phases || []), newPhase],
    });
  };

  const handleUpdatePhase = (index, field, value) => {
    const updatedPhases = [...editedProject.phases];
    updatedPhases[index] = { ...updatedPhases[index], [field]: value };
    setEditedProject({ ...editedProject, phases: updatedPhases });
  };

  const handleDeletePhase = (index) => {
    setPhaseToDelete(index);
  };

  const confirmDeletePhase = () => {
    if (phaseToDelete !== null) {
      const updatedPhases = editedProject.phases.filter((_, i) => i !== phaseToDelete);
      setEditedProject({ ...editedProject, phases: updatedPhases });
      setPhaseToDelete(null);
      toast.success('Phase removed');
    }
  };

  const cancelDeletePhase = () => {
    setPhaseToDelete(null);
  };

  // CHANGE 1: Status update dialog handlers
  const handleOpenAddStatusDialog = () => {
    setStatusForm({
      health: project?.health || 'Green',
      schedule_status: project?.schedule_status || 'On Track',
      actual_progress: project?.actual_progress || '',
      accomplishments: '',
      blockers: '',
      next_steps: '',
      notes: '',
    });
    setShowAddStatusDialog(true);
  };

  const handleSubmitStatusUpdate = () => {
    if (!statusForm.accomplishments.trim() && !statusForm.blockers.trim() && !statusForm.next_steps.trim()) {
      toast.error('Please provide at least one update (accomplishments, blockers, or next steps)');
      return;
    }

    const dataToSend = {
      project_id: id,
      health: statusForm.health,
      schedule_status: statusForm.schedule_status,
      actual_progress: statusForm.actual_progress ? parseInt(statusForm.actual_progress) : null,
      accomplishments: statusForm.accomplishments.trim() || null,
      blockers: statusForm.blockers.trim() || null,
      next_steps: statusForm.next_steps.trim() || null,
      notes: statusForm.notes.trim() || null,
      new_risks: [], // No new risks for now
    };

    createStatusUpdateMutation.mutate(dataToSend);
  };

  // CHANGE 2: Phase-only editing handlers (Settings tab)
  const handleEditPhases = () => {
    setEditedPhases(project?.phases ? JSON.parse(JSON.stringify(project.phases)) : []);
    setIsEditingPhases(true);
  };

  const handleSavePhases = () => {
    // Validate phase dates against project dates
    const projectStart = new Date(project.start_date);
    const projectEnd = new Date(project.end_date);
    let hasDateWarning = false;
    
    const phasesToSave = editedPhases.map(p => ({
      ...p,
      budgeted_hours: p.budgeted_hours === '' || p.budgeted_hours === null ? null : parseFloat(p.budgeted_hours)
    }));
    
    phasesToSave.forEach(phase => {
      const phaseStart = new Date(phase.start_date);
      const phaseEnd = new Date(phase.end_date);
      if (phaseStart < projectStart || phaseEnd > projectEnd) {
        hasDateWarning = true;
      }
    });
    
    if (hasDateWarning) {
      toast.warning('Some phase dates fall outside project timeline');
    }
    
    updatePhasesMutation.mutate(phasesToSave);
  };

  const handleCancelEditPhases = () => {
    setIsEditingPhases(false);
    setEditedPhases([]);
  };

  const handleUpdatePhaseInSettings = (index, field, value) => {
    const updatedPhases = [...editedPhases];
    updatedPhases[index] = { ...updatedPhases[index], [field]: value };
    setEditedPhases(updatedPhases);
  };

  const handleAddPhaseInSettings = () => {
    const newPhase = {
      id: crypto.randomUUID(),
      name: '',
      start_date: project.start_date || '',
      end_date: project.end_date || '',
      status: 'Not Started',
      budgeted_hours: '',
    };
    setEditedPhases([...editedPhases, newPhase]);
  };

  const handleDeletePhaseInSettings = (index) => {
    const updatedPhases = editedPhases.filter((_, i) => i !== index);
    setEditedPhases(updatedPhases);
    toast.success('Phase removed');
  };


  // COMPUTED METRIC 1: Schedule Health - uses backend-computed field from latest status update
  const scheduleHealth = useMemo(() => {
    // Use health from project document (set by status update endpoint)
    if (project?.health) return project.health;
    
    // Fallback: compute from project status and time-based progress (same logic as Dashboard)
    if (project?.status === 'Pipeline') return 'Amber';
    if (project?.status === 'Active') {
      try {
        const start = new Date(project.start_date);
        const end = new Date(project.end_date);
        const today = new Date();
        const totalDays = Math.max(1, (end - start) / (1000 * 60 * 60 * 24));
        const elapsedDays = Math.max(0, (today - start) / (1000 * 60 * 60 * 24));
        const timeBasedProgress = Math.min(100, Math.round((elapsedDays / totalDays) * 100));
        if (timeBasedProgress > 80) return 'Amber';
      } catch {
        // Ignore date parsing errors
      }
      return 'Green';
    }
    return 'Green';
  }, [project]);

  // COMPUTED METRIC 2: Average Team Member Load - FIXED
  const resourceLoad = useMemo(() => {
    if (!allocations || allocations.length === 0) return 0;
    
    // Get unique resources on this project
    const uniqueResourceIds = [...new Set(allocations.map(a => a.resource_id))];
    const numResources = uniqueResourceIds.length;
    
    if (numResources === 0) return 0;
    
    // Calculate total allocation per resource on this project
    const resourceLoads = uniqueResourceIds.map(resourceId => {
      const resourceAllocs = allocations.filter(a => a.resource_id === resourceId);
      // Sum their allocations on this project (they might have multiple time periods)
      return resourceAllocs.reduce((sum, a) => sum + (a.percentage || 0), 0);
    });
    
    // Average load per team member
    const avgLoad = resourceLoads.reduce((sum, load) => sum + load, 0) / numResources;
    return Math.round(avgLoad);
  }, [allocations]);

  // COMPUTED METRIC 3: Risk Profile
  const riskProfile = useMemo(() => {
    if (!risks) return { critical: 0, high: 0, total: 0 };
    
    const critical = risks.filter(r => r.impact === 'Critical').length;
    const high = risks.filter(r => r.impact === 'High').length;
    
    return {
      critical,
      high,
      total: risks.length,
    };
  }, [risks]);

  // COMPUTED METRIC 4: Milestones
  const milestones = useMemo(() => {
    // Check milestones array if exists (future field)
    const projectMilestones = project?.milestones || [];
    const completed = projectMilestones.filter(m => m.status === 'Completed').length;
    const total = projectMilestones.length;
    
    return { completed, total };
  }, [project]);

  // COMPUTED: Total Effort (Hours) — business days only, consistent with backend
  const totalEffort = useMemo(() => {
    if (!allocations) return 0;
    
    let total = 0;
    allocations.forEach(alloc => {
      const days = Math.abs(differenceInBusinessDays(new Date(alloc.end_date), new Date(alloc.start_date))) + 1;
      
      // Formula: (Allocation % / 100) * Business Days * 8 hours per day
      const hours = (alloc.percentage / 100) * days * 8;
      total += hours;
    });
    
    return Math.round(total);
  }, [allocations]);

  // Calculate effort for individual allocation
  const calculateAllocationEffort = (allocation) => {
    const res = resources?.find(r => r.id === allocation.resource_id);
    const cap = res?.standard_capacity && res.standard_capacity > 0 ? res.standard_capacity : 100;
    const days = Math.abs(differenceInBusinessDays(new Date(allocation.end_date), new Date(allocation.start_date))) + 1;
    return Math.round((allocation.percentage / 100) * (cap / 100) * days * 8);
  };

  // Compute hours for allocation form (for budget validation)
  const computeAllocationHours = (startDate, endDate, percentage, stdCap = 100) => {
    if (!startDate || !endDate || !percentage) return 0;
    try {
      const cap = stdCap && stdCap > 0 ? stdCap : 100;
      const businessDays = differenceInBusinessDays(new Date(endDate), new Date(startDate)) + 1;
      return Math.round((percentage / 100) * (cap / 100) * businessDays * 8);
    } catch {
      return 0;
    }
  };

  // COMPUTED: Progress
  const progress = useMemo(() => {
    if (!project) return 0;
    
    // Use actual_progress from project document (set by status update endpoint)
    if (project.actual_progress !== undefined && project.actual_progress !== null) {
      return project.actual_progress;
    }
    
    // Fallback to date-based calculation if no status updates
    try {
      const start = new Date(project.start_date);
      const end = new Date(project.end_date);
      const today = new Date();
      
      if (isNaN(start.getTime()) || isNaN(end.getTime())) return 0;
      
      const totalDays = safeDifferenceInDays(end, start);
      const elapsedDays = safeDifferenceInDays(today, start);
      
      return Math.max(0, Math.min(100, Math.round((elapsedDays / totalDays) * 100)));
    } catch (e) {
      return 0;
    }
  }, [project]);

  const getResourceName = (resourceId) => {
    return resources?.find(r => r.id === resourceId)?.name || 'Unknown';
  };

  const getStatusColor = (status) => {
    const colors = {
      Active: 'bg-[#16B364] text-white',
      Pipeline: 'bg-[#F4B740] text-white',
      Completed: 'bg-[#667085] text-white',
    };
    return colors[status] || 'bg-[#667085] text-white';
  };

  const getHealthColor = (health) => {
    const colors = {
      Green: 'bg-[#16B364]',
      Amber: 'bg-[#F4B740]',
      Red: 'bg-[#EF4444]',
    };
    return colors[health] || 'bg-[#667085]';
  };

  const getImpactColor = (impact) => {
    const colors = {
      Low: 'bg-[#16B364]',
      Medium: 'bg-[#F4B740]',
      High: 'bg-[#EF4444]',
      Critical: 'bg-[#B42318]',
    };
    return colors[impact] || 'bg-[#667085]';
  };

  if (projectLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-[#667085]">Loading project...</p>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-[#667085]">Project not found</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="project-detail">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/projects')}
            data-testid="back-button"
          >
            <ArrowLeft size={16} className="mr-2" />
            Back to Projects
          </Button>
        </div>
        <Button
          onClick={() => navigate(`/projects/${id}/report`)}
          variant="outline"
          data-testid="generate-report"
        >
          <Printer size={16} className="mr-2" />
          Generate Report
        </Button>
      </div>

      {/* PHASE VISUALIZER - At the very top */}
      {project.phases && project.phases.length > 0 && (
        <PhaseVisualizer 
          phases={project.phases} 
          milestones={project.milestones || []} 
        />
      )}

      {/* Project Header */}
      <div className="bg-white border border-[#E6E8EC] rounded-lg p-6">
        {isEditingProject ? (
          /* EDIT MODE (FIX #5) */
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">Edit Project Details</h2>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleCancelEditProject}
                  disabled={updateProjectMutation.isPending}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleSaveProject}
                  disabled={updateProjectMutation.isPending}
                  className="bg-[#1570EF] hover:bg-[#1570EF]/90"
                >
                  {updateProjectMutation.isPending ? (
                    <><Loader2 size={14} className="mr-2 animate-spin" />Saving...</>
                  ) : (
                    <><Save size={14} className="mr-2" />Save Changes</>
                  )}
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-gray-700 mb-1 block">Project Name *</label>
                <Input
                  value={editedProject.name}
                  onChange={(e) => setEditedProject({ ...editedProject, name: e.target.value })}
                  placeholder="Project name"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 mb-1 block">Client Name *</label>
                <Input
                  value={editedProject.client_name}
                  onChange={(e) => setEditedProject({ ...editedProject, client_name: e.target.value })}
                  placeholder="Client name"
                />
              </div>
            </div>

            {/* Customer Contact Section */}
            <div className="border-t border-gray-200 pt-4 mt-2">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Customer Contact (Optional)</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-1 block flex items-center gap-1">
                    <Users size={14} />
                    Contact Name
                  </label>
                  <Input
                    value={editedProject.main_contact_name}
                    onChange={(e) => setEditedProject({ ...editedProject, main_contact_name: e.target.value })}
                    placeholder="e.g., John Doe"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-1 block flex items-center gap-1">
                    <Building2 size={14} />
                    Role / Title
                  </label>
                  <Input
                    value={editedProject.main_contact_role}
                    onChange={(e) => setEditedProject({ ...editedProject, main_contact_role: e.target.value })}
                    placeholder="e.g., Project Manager"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-1 block flex items-center gap-1">
                    <Mail size={14} />
                    Email
                  </label>
                  <Input
                    type="email"
                    value={editedProject.main_contact_email}
                    onChange={(e) => setEditedProject({ ...editedProject, main_contact_email: e.target.value })}
                    placeholder="e.g., john@client.com"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-1 block flex items-center gap-1">
                    <Phone size={14} />
                    Phone
                  </label>
                  <Input
                    type="tel"
                    value={editedProject.main_contact_phone}
                    onChange={(e) => setEditedProject({ ...editedProject, main_contact_phone: e.target.value })}
                    placeholder="e.g., +1 (555) 123-4567"
                  />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="text-sm font-medium text-gray-700 mb-1 block">Status *</label>
                <Select
                  value={editedProject.status}
                  onValueChange={(value) => setEditedProject({ ...editedProject, status: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Active">Active</SelectItem>
                    <SelectItem value="Pipeline">Pipeline</SelectItem>
                    <SelectItem value="Completed">Completed</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 mb-1 block">Start Date *</label>
                <WeekdayDateInput
                  value={editedProject.start_date}
                  onChange={(e) => setEditedProject({ ...editedProject, start_date: e.target.value })}
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 mb-1 block">End Date *</label>
                <WeekdayDateInput
                  value={editedProject.end_date}
                  onChange={(e) => setEditedProject({ ...editedProject, end_date: e.target.value })}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-gray-700 mb-1 block">Project Lead</label>
                <Select
                  value={editedProject.project_lead_id || 'none'}
                  onValueChange={(value) => setEditedProject({ ...editedProject, project_lead_id: value === 'none' ? '' : value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select project lead" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No lead assigned</SelectItem>
                    {resources?.filter((resource) => resource.active !== false).map((resource) => (
                      <SelectItem key={resource.id} value={resource.id}>
                        {resource.name} — {resource.role}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 mb-1 block">Budgeted Hours</label>
                <Input
                  type="number"
                  value={editedProject.budgeted_hours}
                  onChange={(e) => setEditedProject({ ...editedProject, budgeted_hours: e.target.value })}
                  placeholder="e.g., 100"
                />
              </div>
            </div>

            <div>
              <label className="text-sm font-medium text-gray-700 mb-1 block">Google Drive URL</label>
              <Input
                value={editedProject.google_drive_url}
                onChange={(e) => setEditedProject({ ...editedProject, google_drive_url: e.target.value })}
                placeholder="https://drive.google.com/..."
              />
            </div>

            <div>
              <label className="text-sm font-medium text-gray-700 mb-1 block">Project Objective</label>
              <Textarea
                value={editedProject.project_objective}
                onChange={(e) => setEditedProject({ ...editedProject, project_objective: e.target.value })}
                placeholder="Describe the project objective..."
                rows={3}
              />
            </div>
          </div>
        ) : (
          /* VIEW MODE */
          <div>
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <h1 className="text-3xl font-semibold mb-2" style={{ fontFamily: 'Space Grotesk' }}>
                  {project.name}
                </h1>
                <p className="text-[#667085]">Client: {project.client_name}</p>
                
                {/* Main Contact Info Display */}
                {(project.main_contact_name || project.main_contact_email || project.main_contact_phone) && (
                  <div className="mt-2 text-sm text-[#667085] space-y-1">
                    {project.main_contact_name && (
                      <div className="flex items-center gap-1.5">
                        <Users size={14} className="text-[#94A3B8]" />
                        <span>
                          Contact: <strong className="text-[#475467]">{project.main_contact_name}</strong>
                          {project.main_contact_role && (
                            <span className="text-[#667085]"> ({project.main_contact_role})</span>
                          )}
                        </span>
                      </div>
                    )}
                    <div className="flex items-center gap-3 ml-5">
                      {project.main_contact_email && (
                        <a 
                          href={`mailto:${project.main_contact_email}`}
                          className="flex items-center gap-1 text-[#1570EF] hover:underline"
                        >
                          <Mail size={13} />
                          {project.main_contact_email}
                        </a>
                      )}
                      {project.main_contact_phone && (
                        <a 
                          href={`tel:${project.main_contact_phone}`}
                          className="flex items-center gap-1 text-[#1570EF] hover:underline"
                        >
                          <Phone size={13} />
                          {project.main_contact_phone}
                        </a>
                      )}
                    </div>
                  </div>
                )}
                
                <div className="flex items-center gap-4 mt-1">
                  {project.project_lead_name && (
                    <span className="flex items-center gap-1 text-sm text-[#475467]">
                      <Crown size={14} className="text-[#F4B740]" />
                      Lead: <strong>{project.project_lead_name}</strong>
                    </span>
                  )}
                  {!project.project_lead_name && (
                    <span className="flex items-center gap-1 text-sm text-[#EF4444]">
                      <Crown size={14} />
                      No lead assigned
                    </span>
                  )}
                  {project.google_drive_url && (
                    <a href={project.google_drive_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-sm text-[#1570EF] hover:underline">
                      <ExternalLink size={14} />
                      Google Drive
                    </a>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge className={getStatusColor(project.status)}>
                  {project.status}
                </Badge>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleEditProject}
                  className="ml-2"
                  data-testid="edit-project-btn"
                >
                  <Edit2 size={14} className="mr-2" />
                  Edit Project
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowAIReschedule(true)}
                  className="ml-2 text-purple-700 border-purple-200 hover:bg-purple-50"
                  data-testid="ai-reschedule-btn"
                >
                  <Sparkles size={14} className="mr-2 text-purple-600" />
                  AI Reschedule
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Show dates and progress only in view mode */}
        {!isEditingProject && (
          <>
            <div className="flex items-center gap-6 text-sm text-[#667085]">
              <div className="flex items-center gap-2">
                <Calendar size={16} />
                <span>
                  {safeFormatDate(project.start_date)} -{' '}
                  {safeFormatDate(project.end_date)}
                </span>
              </div>
            </div>

            <div className="mt-4">
              <div className="flex items-center justify-between text-sm mb-2">
                <span className="text-[#667085]">Project Progress</span>
                <span className="font-medium">{progress}%</span>
              </div>
              <Progress value={progress} className="h-2" />
            </div>
          </>
        )}
      </div>

      {/* DASHBOARD WIDGETS - Computed Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* 1. Schedule Health */}
        <div className="bg-white border border-[#E6E8EC] rounded-lg p-6" data-testid="metric-schedule">
          <div className="flex items-center justify-between mb-4">
            <div className="w-10 h-10 rounded-lg bg-[#F7F7F8] flex items-center justify-center">
              <TrendingUp size={20} className="text-[#1570EF]" />
            </div>
            <div className={`w-3 h-3 rounded-full ${getHealthColor(scheduleHealth)}`} />
          </div>
          <div className="text-sm text-[#667085] mb-1">Schedule Health</div>
          <div className="text-2xl font-semibold capitalize">{scheduleHealth}</div>
        </div>

        {/* 2. Avg Team Member Load */}
        <div className="bg-white border border-[#E6E8EC] rounded-lg p-6" data-testid="metric-load">
          <div className="flex items-center justify-between mb-4">
            <div className="w-10 h-10 rounded-lg bg-[#F7F7F8] flex items-center justify-center">
              <Users size={20} className="text-[#1570EF]" />
            </div>
          </div>
          <div className="text-sm text-[#667085] mb-1">Avg Team Load</div>
          <div className="text-2xl font-semibold">{resourceLoad}%</div>
          <div className="text-xs text-[#667085] mt-1">
            {allocations?.length || 0} allocations
          </div>
        </div>

        {/* 3. Risk Profile */}
        <div className="bg-white border border-[#E6E8EC] rounded-lg p-6" data-testid="metric-risks">
          <div className="flex items-center justify-between mb-4">
            <div className="w-10 h-10 rounded-lg bg-[#F7F7F8] flex items-center justify-center">
              <Shield size={20} className="text-[#EF4444]" />
            </div>
          </div>
          <div className="text-sm text-[#667085] mb-1">Risk Profile</div>
          <div className="text-2xl font-semibold">
            {riskProfile.critical + riskProfile.high}
          </div>
          <div className="text-xs text-[#667085] mt-1">
            {riskProfile.critical > 0 && `${riskProfile.critical} Critical, `}
            {riskProfile.high} High Impact
          </div>
        </div>

        {/* 4. Total Effort */}
        <div className="bg-white border border-[#E6E8EC] rounded-lg p-6" data-testid="metric-effort">
          <div className="flex items-center justify-between mb-4">
            <div className="w-10 h-10 rounded-lg bg-[#F7F7F8] flex items-center justify-center">
              <Clock size={20} className="text-[#1570EF]" />
            </div>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button type="button" className="text-[#94A3B8] hover:text-[#667085]" data-testid="effort-info-tooltip">
                    <Info size={14} />
                  </button>
                </TooltipTrigger>
                <TooltipContent className="max-w-xs">
                  <p className="text-xs">
                    <strong>Allocation-Based Estimate</strong> — total hours implied by the resource staffing plan
                    (percentage × hours/week × weeks). This is NOT the approved budget or actual hours logged.
                  </p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
          <div className="text-sm text-[#667085] mb-1">Allocation-Based Estimate</div>
          <div className="text-2xl font-semibold">{totalEffort.toLocaleString()}</div>
          <div className="text-xs text-[#667085] mt-1">Based on team allocations</div>
        </div>
      </div>

      {/* TABBED CONTENT AREA */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-7 lg:w-auto">
          <TabsTrigger value="overview" data-testid="tab-overview">
            <FileText size={16} className="mr-2" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="team" data-testid="tab-team">
            <UserCircle size={16} className="mr-2" />
            Team
          </TabsTrigger>
          <TabsTrigger value="risks" data-testid="tab-risks">
            <Shield size={16} className="mr-2" />
            Risks
          </TabsTrigger>
          <TabsTrigger value="wbs" data-testid="tab-wbs">
            <ListTodo size={16} className="mr-2" />
            WBS &amp; Plan
          </TabsTrigger>
          <TabsTrigger value="baselines" data-testid="tab-baselines">
            <GitCompare size={16} className="mr-2" />
            Baselines
          </TabsTrigger>
          <TabsTrigger value="time-tracking" data-testid="tab-time-tracking">
            <Clock size={16} className="mr-2" />
            Time Tracking
          </TabsTrigger>
          <TabsTrigger value="settings" data-testid="tab-settings">
            <SettingsIcon size={16} className="mr-2" />
            Settings
          </TabsTrigger>
        </TabsList>

        {/* TAB 1: OVERVIEW */}
        <TabsContent value="overview" className="space-y-6">
          {/* AI Insights — Health Score + Predictions */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ProjectHealthScore projectId={id} />
            <ProjectPredictions projectId={id} />
          </div>

          {/* Budget Reconciliation — at-a-glance 4-number alignment */}
          <div className="bg-white border border-[#E6E8EC] rounded-lg p-6">
            <BudgetReconciliation projectId={id} canEdit={true} />
          </div>

          <div className="bg-white border border-[#E6E8EC] rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4" style={{ fontFamily: 'Space Grotesk' }}>
              Project Status
            </h3>
            <div className="space-y-4">
              <div>
                <div className="text-sm text-[#667085] mb-2">Current Status</div>
                <Badge className={getStatusColor(project.status)}>
                  {project.status}
                </Badge>
              </div>
              <div>
                <div className="text-sm text-[#667085] mb-2">Schedule Health</div>
                <div className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded-full ${getHealthColor(scheduleHealth)}`} />
                  <span className="font-medium capitalize">{scheduleHealth}</span>
                </div>
              </div>
              <div>
                <div className="text-sm text-[#667085] mb-2">Overall Progress</div>
                <div className="flex items-center gap-3">
                  <Progress value={progress} className="flex-1 h-2" />
                  <span className="font-semibold">{progress}%</span>
                </div>
              </div>
            </div>
          </div>

          {/* AI-Generated Status Summary */}
          <div className="bg-white border border-[#E6E8EC] rounded-lg p-6" data-testid="ai-summary-section">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold flex items-center gap-2" style={{ fontFamily: 'Space Grotesk' }}>
                <Sparkles size={20} className="text-[#1570EF]" />
                AI Status Summary
              </h3>
              <div className="flex gap-2">
                {!isEditingSummary && (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleGenerateSummary}
                      disabled={generateSummaryMutation.isPending}
                      data-testid="generate-summary-btn"
                    >
                      {generateSummaryMutation.isPending ? (
                        <>
                          <Loader2 size={14} className="mr-1 animate-spin" />
                          Generating...
                        </>
                      ) : (
                        <>
                          <Sparkles size={14} className="mr-1" />
                          {project?.status_summary ? 'Regenerate' : 'Generate Summary'}
                        </>
                      )}
                    </Button>
                    {project?.status_summary && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleEditSummary}
                        data-testid="edit-summary-btn"
                      >
                        Edit
                      </Button>
                    )}
                  </>
                )}
                {isEditingSummary && (
                  <>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setIsEditingSummary(false)}
                    >
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      onClick={handleSaveSummary}
                      disabled={updateSummaryMutation.isPending}
                      data-testid="save-summary-btn"
                    >
                      {updateSummaryMutation.isPending ? (
                        <Loader2 size={14} className="mr-1 animate-spin" />
                      ) : (
                        <Save size={14} className="mr-1" />
                      )}
                      Save
                    </Button>
                  </>
                )}
              </div>
            </div>

            {isEditingSummary ? (
              <Textarea
                value={editedSummary}
                onChange={(e) => setEditedSummary(e.target.value)}
                rows={8}
                className="w-full"
                placeholder="Enter project status summary..."
                data-testid="summary-textarea"
              />
            ) : project?.status_summary ? (
              <div className="space-y-3">
                <div className="prose prose-sm max-w-none text-[#344054] whitespace-pre-wrap" data-testid="summary-content">
                  {project.status_summary}
                </div>
                {project.status_summary_updated_at && (
                  <div className="text-xs text-[#667085] flex items-center gap-1">
                    <Clock size={12} />
                    Last updated: {safeFormatDate(project.status_summary_updated_at, 'MMM d, yyyy h:mm a')}
                  </div>
                )}
                <AIFeedbackButtons
                  feature="status_summary"
                  projectId={id}
                  inputSummary="Project status summary generation"
                  outputSummary={project.status_summary?.substring(0, 100)}
                />
              </div>
            ) : (
              <div className="text-center py-8 text-[#667085]">
                <Sparkles size={32} className="mx-auto mb-3 opacity-40" />
                <p>No summary generated yet.</p>
                <p className="text-sm">Click &ldquo;Generate Summary&rdquo; to create an AI-powered project update.</p>
              </div>
            )}
          </div>

          {/* Recent Status Updates */}
          <div className="bg-white border border-[#E6E8EC] rounded-lg p-6" data-testid="status-updates-section">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold" style={{ fontFamily: 'Space Grotesk' }}>
                Recent Status Updates
              </h3>
              <Button
                onClick={handleOpenAddStatusDialog}
                size="sm"
                className="bg-[#1570EF] hover:bg-[#1570EF]/90"
                data-testid="add-status-update-btn"
              >
                <Plus size={14} className="mr-2" />
                Add Status Update
              </Button>
            </div>
            
            {statusUpdates && statusUpdates.length > 0 ? (
              <div className="space-y-4">
                {statusUpdates.map((update, index) => (
                  <div 
                    key={update.id || index} 
                    className="border-l-4 pl-4 py-2 hover:bg-gray-50 transition-colors"
                    style={{ 
                      borderLeftColor: 
                        update.health === 'Green' ? '#10B981' : 
                        update.health === 'Amber' ? '#F59E0B' : 
                        update.health === 'Red' ? '#EF4444' : '#94A3B8' 
                    }}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <div className={`w-2.5 h-2.5 rounded-full ${
                          update.health === 'Green' ? 'bg-[#10B981]' : 
                          update.health === 'Amber' ? 'bg-[#F59E0B]' : 
                          update.health === 'Red' ? 'bg-[#EF4444]' : 'bg-[#94A3B8]'
                        }`} />
                        <span className="font-semibold text-sm text-[#0B1220]">
                          {update.health || 'N/A'}
                        </span>
                        <span className="text-xs text-[#667085]">•</span>
                        <span className="text-sm text-[#667085]">
                          {update.schedule_status || 'N/A'}
                        </span>
                        {update.actual_progress !== undefined && update.actual_progress !== null && (
                          <>
                            <span className="text-xs text-[#667085]">•</span>
                            <span className="text-sm font-medium text-[#475467]">
                              {update.actual_progress}% Complete
                            </span>
                          </>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-[#667085]">
                          {safeFormatDate(update.week_start_date, 'MMM d, yyyy')}
                        </span>
                        {(isAdmin || isLead) && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 px-2"
                            onClick={() => {
                              setEditingStatusUpdate(update);
                              setShowEditStatusDialog(true);
                            }}
                            title="Edit status update"
                          >
                            <Edit2 size={12} />
                          </Button>
                        )}
                      </div>
                    </div>
                    
                    {update.accomplishments && (
                      <div className="mb-2">
                        <p className="text-xs font-medium text-[#475467] mb-1">Accomplishments:</p>
                        <p className="text-sm text-[#667085]">{update.accomplishments}</p>
                      </div>
                    )}
                    
                    {update.blockers && (
                      <div className="mb-2">
                        <p className="text-xs font-medium text-[#475467] mb-1">Blockers:</p>
                        <p className="text-sm text-[#667085]">{update.blockers}</p>
                      </div>
                    )}
                    
                    {update.next_steps && (
                      <div>
                        <p className="text-xs font-medium text-[#475467] mb-1">Next Steps:</p>
                        <p className="text-sm text-[#667085]">{update.next_steps}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-[#667085]">
                <FileText size={32} className="mx-auto mb-3 opacity-40" />
                <p>No status updates yet.</p>
                <p className="text-sm">Status updates will appear here once project leads submit weekly check-ins.</p>
              </div>
            )}
          </div>
        </TabsContent>

        {/* TAB 2: TEAM (Resource Allocations) */}
        <TabsContent value="team" className="space-y-6">
          {/* Budget Health Banner */}
          <BudgetHealthBanner projectId={id} />
          
          {allocations && allocations.length > 0 ? (
            <>
              <div className="bg-white border border-[#E6E8EC] rounded-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold" style={{ fontFamily: 'Space Grotesk' }}>
                    Resource Allocations
                  </h3>
                  {isAdmin && (
                    <Button
                      onClick={openCreateAllocDialog}
                      size="sm"
                      className="bg-[#1570EF] hover:bg-[#1570EF]/90"
                      data-testid="allocate-resource-btn"
                    >
                      <Plus size={14} className="mr-2" />
                      Allocate Resource
                    </Button>
                  )}
                </div>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Resource</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Start Date</TableHead>
                      <TableHead>End Date</TableHead>
                      <TableHead className="text-right">Allocation</TableHead>
                      <TableHead className="text-right">Est. Hours</TableHead>
                      {isAdmin && <TableHead className="text-right">Actions</TableHead>}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {allocations.map((alloc) => {
                      const resource = resources?.find(r => r.id === alloc.resource_id);
                      const effortHours = calculateAllocationEffort(alloc);
                      return (
                        <TableRow key={alloc.id}>
                          <TableCell>
                            <div className="flex items-center gap-3">
                              <Avatar className="w-8 h-8">
                                <AvatarImage src={resource?.avatar_url} />
                                <AvatarFallback>{resource?.name?.charAt(0)}</AvatarFallback>
                              </Avatar>
                              <span className="font-medium">{getResourceName(alloc.resource_id)}</span>
                            </div>
                          </TableCell>
                          <TableCell>
                            {alloc.role ? (
                              <Badge variant="outline" className="text-xs">
                                {alloc.role}
                              </Badge>
                            ) : (
                              <span className="text-[#98A2B3]">-</span>
                            )}
                          </TableCell>
                          <TableCell>{safeFormatDate(alloc.start_date)}</TableCell>
                          <TableCell>{safeFormatDate(alloc.end_date)}</TableCell>
                          <TableCell className="text-right">
                            <span className="font-semibold">{formatAllocation(alloc.percentage, resource?.standard_capacity || 100)}</span>
                          </TableCell>
                          <TableCell className="text-right">
                            <span className="font-semibold text-[#1570EF]">{effortHours}h</span>
                          </TableCell>
                          {isAdmin && (
                            <TableCell className="text-right">
                              <div className="flex items-center justify-end gap-2">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => openEditAllocDialog(alloc)}
                                  data-testid={`edit-alloc-${alloc.id}`}
                                  title="Edit allocation"
                                >
                                  <Edit2 size={14} />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setAllocToDelete(alloc)}
                                  data-testid={`delete-alloc-${alloc.id}`}
                                  className="text-[#EF4444] hover:text-[#EF4444] hover:bg-red-50"
                                  title="Delete allocation"
                                >
                                  <Trash2 size={14} />
                                </Button>
                              </div>
                            </TableCell>
                          )}
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>

              {/* Phase-Based Allocations Editor */}
              <PhaseAllocationEditor projectId={id} />
            </>
          ) : (
            <div className="bg-white border border-[#E6E8EC] rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold" style={{ fontFamily: 'Space Grotesk' }}>
                  Resource Allocations
                </h3>
                {isAdmin && (
                  <Button
                    onClick={openCreateAllocDialog}
                    size="sm"
                    className="bg-[#1570EF] hover:bg-[#1570EF]/90"
                    data-testid="allocate-resource-btn-empty"
                  >
                    <Plus size={14} className="mr-2" />
                    Allocate Resource
                  </Button>
                )}
              </div>
              <div className="p-12 text-center">
                <Users size={48} className="mx-auto mb-4 text-[#98A2B3]" />
                <p className="text-[#667085]">No team members allocated yet</p>
              </div>
            </div>
          )}
        </TabsContent>

        {/* TAB 3: RISKS */}
        <TabsContent value="risks" className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold" style={{ fontFamily: 'Space Grotesk' }}>
                Risk & Issue Register
              </h3>
              <p className="text-sm text-[#667085] mt-0.5">
                Track risks (potential problems) and issues (current blockers) with mitigation plans and lifecycle status.
              </p>
            </div>
            <div className="flex items-center gap-2">
              {/* Bulk-polish button — always visible; label changes based on polish state */}
              {risks && risks.length > 0 && (
                <Button
                  variant="outline"
                  className="gap-2"
                  onClick={async () => {
                    try {
                      const r = await polishAllRisks(id);
                      toast.success(r.data.message || 'Polishing complete');
                      queryClient.invalidateQueries({ queryKey: ['projectRisks', id] });
                    } catch (e) {
                      toast.error(e.response?.data?.detail || 'Polish failed');
                    }
                  }}
                  data-testid="polish-all-risks-btn"
                  title="Run AI polish on all risks to improve descriptions and infer impact areas"
                >
                  {risks.some(r => !r.ai_polished)
                    ? `✨ Polish all (${risks.filter(r => !r.ai_polished).length})`
                    : '✨ Re-polish all'
                  }
                </Button>
              )}
              <Button onClick={openCreateRiskDialog} data-testid="add-risk-btn" className="gap-2">
                <Plus size={16} />
                Add Risk / Issue
              </Button>
            </div>
          </div>

          {risks && risks.length > 0 ? (
            <div className="bg-white border border-[#E6E8EC] rounded-lg overflow-hidden">
              <div className="divide-y divide-[#E6E8EC]">
                {(() => {
                  // SMART SORTING: Status (Active→Mitigated→Accepted→Closed) then Impact (Critical→High→Medium→Low)
                  const statusOrder = { Active: 0, Mitigated: 1, Accepted: 2, Closed: 3 };
                  const impactOrder = { Critical: 0, High: 1, Medium: 2, Low: 3 };
                  const sortedRisks = [...risks].sort((a, b) => {
                    const statusA = statusOrder[a.status || 'Active'] ?? 4;
                    const statusB = statusOrder[b.status || 'Active'] ?? 4;
                    if (statusA !== statusB) return statusA - statusB;
                    const impactA = impactOrder[a.impact || 'Medium'] ?? 4;
                    const impactB = impactOrder[b.impact || 'Medium'] ?? 4;
                    return impactA - impactB;
                  });
                  
                  return sortedRisks.map((risk) => {
                    const riskStatus = risk.status || 'Active';
                    const category = risk.category || 'Risk';
                    
                    // Status styling: larger badges, prominent colors, status icons
                    const statusConfig = {
                      Active: { 
                        bg: 'bg-red-50', 
                        text: 'text-red-700', 
                        border: 'border-red-300',
                        borderLeft: 'border-l-4 border-l-red-500',
                        icon: '🔴'
                      },
                      Mitigated: { 
                        bg: 'bg-amber-50', 
                        text: 'text-amber-700', 
                        border: 'border-amber-300',
                        borderLeft: 'border-l-4 border-l-amber-500',
                        icon: '🟡'
                      },
                      Accepted: { 
                        bg: 'bg-blue-50', 
                        text: 'text-blue-700', 
                        border: 'border-blue-300',
                        borderLeft: 'border-l-4 border-l-blue-500',
                        icon: '🔵'
                      },
                      Closed: { 
                        bg: 'bg-gray-100', 
                        text: 'text-gray-500', 
                        border: 'border-gray-300',
                        borderLeft: 'border-l-4 border-l-gray-400',
                        icon: '⚪'
                      },
                    };
                    const statusStyle = statusConfig[riskStatus] || statusConfig.Closed;
                    
                    return (
                      <div
                        key={risk.id}
                        className={`p-4 hover:bg-[#FAFBFC] transition-colors ${statusStyle.borderLeft}`}
                        data-testid={`risk-row-${risk.id}`}
                      >
                        <div className="flex items-start gap-3">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-start justify-between gap-3">
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap mb-2">
                                  {/* STATUS BADGE - Larger and more prominent */}
                                  <Badge variant="outline" className={`text-sm font-bold px-3 py-1 border-2 ${statusStyle.bg} ${statusStyle.text} ${statusStyle.border}`}>
                                    <span className="mr-1.5">{statusStyle.icon}</span>
                                    {riskStatus.toUpperCase()}
                                  </Badge>
                                  <Badge variant="outline" className={`text-xs font-semibold ${category === 'Issue' ? 'bg-red-50 text-red-700 border-red-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
                                    {category.toUpperCase()}
                                  </Badge>
                                  <Badge className={`${getImpactColor(risk.impact)} text-white text-xs`}>
                                    {risk.impact} Impact
                                  </Badge>
                                  <Badge variant="outline" className="text-xs">
                                    {risk.probability} Probability
                                  </Badge>
                                {risk.source_status_update_id && (
                                  <Badge variant="outline" className="text-[10px] bg-purple-50 text-purple-700 border-purple-200">
                                    From Status Update
                                  </Badge>
                                )}
                                {risk.ai_polished && (
                                  <Badge variant="outline" className="text-[10px] bg-violet-50 text-violet-700 border-violet-200" title="Rewritten by AI">
                                    ✨ AI polished
                                  </Badge>
                                )}
                              </div>
                              {/* Impact areas badges */}
                              {Array.isArray(risk.impact_areas) && risk.impact_areas.length > 0 && (
                                <div className="flex items-center gap-1 flex-wrap mb-1.5">
                                  <span className="text-[10px] text-gray-500 font-medium">Impacts:</span>
                                  {risk.impact_areas.map((area) => (
                                    <Badge
                                      key={area}
                                      variant="outline"
                                      className={`text-[10px] ${
                                        area === 'Scope' ? 'bg-blue-50 text-blue-700 border-blue-200' :
                                        area === 'Budget' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                                        area === 'Timeline' ? 'bg-orange-50 text-orange-700 border-orange-200' :
                                        area === 'Quality' ? 'bg-purple-50 text-purple-700 border-purple-200' :
                                        area === 'Resources' ? 'bg-pink-50 text-pink-700 border-pink-200' :
                                        'bg-indigo-50 text-indigo-700 border-indigo-200'
                                      }`}
                                    >
                                      {area}
                                    </Badge>
                                  ))}
                                </div>
                              )}
                              <p className="text-sm text-[#0B1220] font-medium break-words">{risk.description}</p>
                              {risk.mitigation && (
                                <div className="mt-2 p-2 rounded bg-[#F8FAFC] border border-[#E6E8EC] text-xs text-[#475467]">
                                  <span className="font-semibold text-[#0B1220]">Mitigation:</span> {risk.mitigation}
                                </div>
                              )}
                            </div>
                            <div className="flex items-center gap-1 shrink-0">
                              <Select
                                value={riskStatus}
                                onValueChange={(v) => quickChangeStatus(risk, v)}
                              >
                                <SelectTrigger className="h-8 w-32 text-xs" data-testid={`risk-status-select-${risk.id}`}>
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="Active">Active</SelectItem>
                                  <SelectItem value="Mitigated">Mitigated</SelectItem>
                                  <SelectItem value="Accepted">Accepted</SelectItem>
                                  <SelectItem value="Closed">Closed</SelectItem>
                                </SelectContent>
                              </Select>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={() => openEditRiskDialog(risk)}
                                data-testid={`edit-risk-${risk.id}`}
                              >
                                <Edit2 size={14} />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-red-600 hover:text-red-700 hover:bg-red-50"
                                onClick={() => {
                                  if (window.confirm('Delete this risk/issue?')) {
                                    deleteRiskMutation.mutate(risk.id);
                                  }
                                }}
                                data-testid={`delete-risk-${risk.id}`}
                              >
                                <Trash2 size={14} />
                              </Button>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                    );
                  })
                })()}
              </div>
            </div>
          ) : (
            <div className="bg-white border border-[#E6E8EC] rounded-lg p-12 text-center">
              <CheckCircle2 size={48} className="mx-auto mb-4 text-[#16B364]" />
              <p className="text-[#667085] mb-4">No risks or issues recorded yet</p>
              <Button onClick={openCreateRiskDialog} variant="outline" className="gap-2" data-testid="add-first-risk-btn">
                <Plus size={16} />
                Add first risk
              </Button>
            </div>
          )}

          {/* Risk Create/Edit Dialog */}
          <Dialog open={showRiskDialog} onOpenChange={(v) => { if (!v) resetRiskDialog(); }}>
            <DialogContent data-testid="risk-dialog">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <ShieldAlert size={18} className="text-amber-600" />
                  {editingRisk ? 'Edit Risk / Issue' : 'Add Risk / Issue'}
                </DialogTitle>
                <DialogDescription>
                  Capture a potential risk or current issue with a mitigation plan. ✨ Your description will be auto-polished by AI for clarity, and impact areas (Scope / Budget / Timeline / Quality / Resources / Stakeholder) will be inferred.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-3 py-2">
                <div>
                  <label className="text-sm font-medium text-[#0B1220] mb-1.5 block">Description</label>
                  <Textarea
                    value={riskForm.description}
                    onChange={(e) => setRiskForm(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Describe the risk or issue…"
                    rows={2}
                    data-testid="risk-dialog-description"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm font-medium text-[#0B1220] mb-1.5 block">Type</label>
                    <Select value={riskForm.category} onValueChange={(v) => setRiskForm(prev => ({ ...prev, category: v }))}>
                      <SelectTrigger data-testid="risk-dialog-category"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Risk">Risk (potential)</SelectItem>
                        <SelectItem value="Issue">Issue (current)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-[#0B1220] mb-1.5 block">Status</label>
                    <Select value={riskForm.status} onValueChange={(v) => setRiskForm(prev => ({ ...prev, status: v }))}>
                      <SelectTrigger data-testid="risk-dialog-status"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Active">Active</SelectItem>
                        <SelectItem value="Mitigated">Mitigated</SelectItem>
                        <SelectItem value="Accepted">Accepted</SelectItem>
                        <SelectItem value="Closed">Closed</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-[#0B1220] mb-1.5 block">Impact</label>
                    <Select value={riskForm.impact} onValueChange={(v) => setRiskForm(prev => ({ ...prev, impact: v }))}>
                      <SelectTrigger data-testid="risk-dialog-impact"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Low">Low</SelectItem>
                        <SelectItem value="Medium">Medium</SelectItem>
                        <SelectItem value="High">High</SelectItem>
                        <SelectItem value="Critical">Critical</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-[#0B1220] mb-1.5 block">Probability</label>
                    <Select value={riskForm.probability} onValueChange={(v) => setRiskForm(prev => ({ ...prev, probability: v }))}>
                      <SelectTrigger data-testid="risk-dialog-probability"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Low">Low</SelectItem>
                        <SelectItem value="Medium">Medium</SelectItem>
                        <SelectItem value="High">High</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium text-[#0B1220] mb-1.5 block">Mitigation plan</label>
                  <Textarea
                    value={riskForm.mitigation}
                    onChange={(e) => setRiskForm(prev => ({ ...prev, mitigation: e.target.value }))}
                    placeholder="How will this be addressed or avoided?"
                    rows={2}
                    data-testid="risk-dialog-mitigation"
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={resetRiskDialog}>Cancel</Button>
                <Button
                  onClick={submitRiskDialog}
                  disabled={createRiskMutation.isPending || updateRiskMutation.isPending}
                  data-testid="risk-dialog-submit"
                >
                  {(createRiskMutation.isPending || updateRiskMutation.isPending) && (
                    <Loader2 size={14} className="mr-2 animate-spin" />
                  )}
                  {editingRisk ? 'Save changes' : 'Add to register'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </TabsContent>

        {/* TAB 4: WBS & PLAN */}
        <TabsContent value="wbs" className="space-y-4">
          <WBSView
            projectId={id}
            project={project}
            phases={project?.phases || []}
            resources={resources || []}
            currentUserEmail={currentUser?.email}
          />
        </TabsContent>

        {/* TAB 5: BASELINES & VARIANCE */}
        <TabsContent value="baselines" className="space-y-4">
          <BaselinesView projectId={id} canEdit={true} />
        </TabsContent>

        {/* TAB 6: TIME TRACKING */}
        <TabsContent value="time-tracking" className="space-y-6">
          {/* Hour Metrics Legend */}
          <div className="bg-[#F5F8FF] border border-[#D1E0FF] rounded-lg p-4" data-testid="hour-metrics-info">
            <div className="flex items-start gap-3">
              <Info size={18} className="text-[#1570EF] flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <div className="text-sm font-semibold text-[#0B1220] mb-2" style={{ fontFamily: 'Space Grotesk' }}>
                  Understanding Hour Metrics
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2 text-xs text-[#475467]">
                  <div><strong className="text-[#0B1220]">Budget:</strong> Approved hours target for this project (top-down).</div>
                  <div><strong className="text-[#0B1220]">Estimated:</strong> Sum of WBS task estimates (bottom-up rollup).</div>
                  <div><strong className="text-[#0B1220]">Allocated:</strong> Resource commitment (allocation % × duration × 8h).</div>
                  <div><strong className="text-[#0B1220]">Actual:</strong> Hours actually worked and logged by the team.</div>
                </div>
                <div className="text-[11px] text-gray-500 mt-2 italic">
                  Hierarchy: Budget caps phase budgets, which cap WBS estimates. Allocations and actuals reconcile against all three.
                  See the <strong>Budget Reconciliation</strong> panel on the Overview tab for live drift.
                </div>
              </div>
            </div>
          </div>

          {timeReportLoading ? (
            <div className="text-center py-12">
              <Clock className="w-12 h-12 mx-auto mb-3 opacity-40 animate-spin" />
              <p className="text-gray-500">Loading time tracking data...</p>
            </div>
          ) : timeReport ? (
            <>
              {/* Summary Cards */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-white border border-[#E6E8EC] rounded-lg p-4">
                  <div className="text-sm text-gray-600 mb-1">
                    {timeReport.project?.budgeted_hours ? 'Total Budget' : 'Total Allocated'}
                  </div>
                  <div className="text-2xl font-bold">
                    {timeReport.project?.budgeted_hours ? timeReport.project.budgeted_hours : (timeReport.project?.planned_hours || 0)}h
                  </div>
                  {timeReport.project?.budgeted_hours && (
                    <div className="text-xs text-gray-500 mt-1">
                      Allocated: {timeReport.project?.planned_hours}h
                    </div>
                  )}
                </div>
                <div className="bg-white border border-[#E6E8EC] rounded-lg p-4">
                  <div className="text-sm text-gray-600 mb-1">Total Actual</div>
                  <div className="text-2xl font-bold">{timeReport.project?.actual_hours || 0}h</div>
                </div>
                <div className="bg-white border border-[#E6E8EC] rounded-lg p-4">
                  <div className="text-sm text-gray-600 mb-1">
                    {timeReport.project?.budgeted_hours ? 'Budget Variance' : 'Schedule Variance'}
                  </div>
                  <div className={`text-2xl font-bold ${
                    (timeReport.project?.budgeted_hours ? timeReport.project?.budget_variance : timeReport.project?.variance_hours) > 0 ? 'text-amber-600' : 
                    (timeReport.project?.budgeted_hours ? timeReport.project?.budget_variance : timeReport.project?.variance_hours) < 0 ? 'text-emerald-600' : 
                    'text-gray-600'
                  }`}>
                    {(timeReport.project?.budgeted_hours ? timeReport.project?.budget_variance : timeReport.project?.variance_hours) > 0 ? '+' : ''}
                    {timeReport.project?.budgeted_hours ? (timeReport.project?.budget_variance || 0) : (timeReport.project?.variance_hours || 0)}h
                  </div>
                </div>
                <div className="bg-white border border-[#E6E8EC] rounded-lg p-4">
                  <div className="text-sm text-gray-600 mb-1">
                    {timeReport.project?.budgeted_hours ? 'Budget Used' : 'Completion Rate'}
                  </div>
                  <div className="text-2xl font-bold">
                    {timeReport.project?.budgeted_hours ? (timeReport.project?.budget_used_percentage || 0) : (timeReport.project?.completion_rate || 0)}%
                  </div>
                </div>
              </div>

              {/* AI Budget Analysis */}
              <div className="bg-white border border-[#E6E8EC] rounded-lg p-6" data-testid="ai-budget-analysis">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold flex items-center gap-2" style={{ fontFamily: 'Space Grotesk' }}>
                    <Sparkles size={20} className="text-[#1570EF]" />
                    AI Budget Analysis
                  </h3>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => refetchAnalysis()}
                    disabled={analysisLoading}
                    data-testid="refresh-analysis-btn"
                  >
                    {analysisLoading ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                    <span className="ml-1 text-xs">{analysisLoading ? 'Analyzing...' : 'Refresh'}</span>
                  </Button>
                </div>

                {analysisLoading ? (
                  <div className="flex items-center gap-3 py-6 justify-center text-[#667085]">
                    <Loader2 size={20} className="animate-spin" />
                    <span className="text-sm">AI is analyzing budget data...</span>
                  </div>
                ) : budgetAnalysis ? (
                  <div className="space-y-4">
                    {/* Narrative */}
                    <div className="bg-[#F5F8FF] border border-[#D1E0FF] rounded-lg p-4">
                      <p className="text-sm text-[#0B1220] leading-relaxed" data-testid="ai-narrative">
                        {budgetAnalysis.narrative}
                      </p>
                    </div>

                    {/* Burn Rate */}
                    {budgetAnalysis.burn_rate && budgetAnalysis.burn_rate.current_weekly > 0 && (
                      <div className="grid grid-cols-3 gap-3">
                        <div className="bg-[#F9FAFB] rounded-lg p-3 text-center">
                          <div className="text-xs text-[#667085]">Weekly Burn</div>
                          <div className="text-lg font-bold text-[#0B1220]">{budgetAnalysis.burn_rate.current_weekly}h</div>
                        </div>
                        <div className="bg-[#F9FAFB] rounded-lg p-3 text-center">
                          <div className="text-xs text-[#667085]">Projected Total</div>
                          <div className="text-lg font-bold text-[#0B1220]">{budgetAnalysis.burn_rate.projected_total}h</div>
                        </div>
                        <div className="bg-[#F9FAFB] rounded-lg p-3 text-center">
                          <div className="text-xs text-[#667085]">Weeks at Rate</div>
                          <div className={`text-lg font-bold ${budgetAnalysis.burn_rate.on_track ? 'text-[#16B364]' : 'text-[#EF4444]'}`}>
                            {budgetAnalysis.burn_rate.weeks_remaining_at_rate || '—'}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Alerts */}
                    {budgetAnalysis.alerts && budgetAnalysis.alerts.length > 0 && (
                      <div className="space-y-2">
                        <div className="text-xs font-semibold text-[#667085] uppercase tracking-wider">Alerts</div>
                        {budgetAnalysis.alerts.map((alert, i) => (
                          <div
                            key={i}
                            className={`flex items-start gap-3 p-3 rounded-lg border text-sm ${
                              alert.severity === 'critical' ? 'bg-red-50 border-red-200 text-red-800' :
                              alert.severity === 'warning' ? 'bg-amber-50 border-amber-200 text-amber-800' :
                              'bg-blue-50 border-blue-200 text-blue-800'
                            }`}
                            data-testid={`ai-alert-${i}`}
                          >
                            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                            <div>
                              <div className="font-medium">{alert.title}</div>
                              <div className="text-xs mt-0.5 opacity-80">{alert.message}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Recommendations */}
                    {budgetAnalysis.recommendations && budgetAnalysis.recommendations.length > 0 && (
                      <div className="space-y-2">
                        <div className="text-xs font-semibold text-[#667085] uppercase tracking-wider">Recommendations</div>
                        {budgetAnalysis.recommendations.map((rec, i) => (
                          <div key={i} className="flex items-start gap-3 p-3 bg-[#F9FAFB] rounded-lg border border-[#E6E8EC] text-sm" data-testid={`ai-rec-${i}`}>
                            <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${
                              rec.priority === 'high' ? 'bg-[#EF4444]' :
                              rec.priority === 'medium' ? 'bg-[#F4B740]' :
                              'bg-[#16B364]'
                            }`} />
                            <div>
                              <div className="font-medium text-[#0B1220]">{rec.title}</div>
                              <div className="text-xs text-[#667085] mt-0.5">{rec.action}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Phase Insights */}
                    {budgetAnalysis.phase_insights && budgetAnalysis.phase_insights.length > 0 && (
                      <div className="space-y-2">
                        <div className="text-xs font-semibold text-[#667085] uppercase tracking-wider">Phase Insights</div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {budgetAnalysis.phase_insights.map((pi, i) => (
                            <div key={i} className="flex items-center gap-2 p-2 bg-[#F9FAFB] rounded border border-[#E6E8EC] text-sm">
                              <span className={`w-2 h-2 rounded-full shrink-0 ${
                                pi.status === 'over_budget' ? 'bg-[#EF4444]' :
                                pi.status === 'at_risk' ? 'bg-[#F4B740]' :
                                pi.status === 'under_utilized' ? 'bg-[#98A2B3]' :
                                'bg-[#16B364]'
                              }`} />
                              <span className="font-medium text-[#0B1220]">{pi.phase}:</span>
                              <span className="text-[#667085] truncate">{pi.insight}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-4 text-[#667085] text-sm">
                    Unable to generate analysis. Click Refresh to try again.
                  </div>
                )}
              </div>

              {/* Phase Breakdown */}
              <div className="bg-white border border-[#E6E8EC] rounded-lg p-6">
                <h3 className="text-lg font-semibold mb-4" style={{ fontFamily: 'Space Grotesk' }}>
                  Phase Breakdown
                </h3>
                
                {timeReport.phases && timeReport.phases.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="text-left p-3 text-sm font-medium text-gray-700">Phase</th>
                          <th className="text-right p-3 text-sm font-medium text-gray-700">Budget</th>
                          <th className="text-right p-3 text-sm font-medium text-gray-700">Allocated</th>
                          <th className="text-right p-3 text-sm font-medium text-gray-700">Actual</th>
                          <th className="text-right p-3 text-sm font-medium text-gray-700">Variance</th>
                          <th className="text-right p-3 text-sm font-medium text-gray-700">Progress</th>
                          <th className="text-center p-3 text-sm font-medium text-gray-700">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {timeReport.phases.map((phase, index) => (
                          <tr key={index} className="border-t border-gray-100">
                            <td className="p-3 font-medium">{phase.phase_name}</td>
                            <td className="p-3 text-right text-gray-600">{phase.budgeted_hours || '-'}h</td>
                            <td className="p-3 text-right text-gray-600">{phase.planned_hours}h</td>
                            <td className="p-3 text-right font-medium">{phase.actual_hours}h</td>
                            <td className={`p-3 text-right font-medium ${
                              (phase.budgeted_hours ? phase.budget_variance : phase.variance_hours) > 0 ? 'text-amber-600' : 
                              (phase.budgeted_hours ? phase.budget_variance : phase.variance_hours) < 0 ? 'text-emerald-600' : 
                              'text-gray-600'
                            }`}>
                              {(phase.budgeted_hours ? phase.budget_variance : phase.variance_hours) > 0 ? '+' : ''}
                              {phase.budgeted_hours ? phase.budget_variance : phase.variance_hours}h
                            </td>
                            <td className="p-3 text-right">
                              <div className="flex items-center justify-end gap-2">
                                <span className="text-sm">{phase.budgeted_hours ? phase.budget_used_percentage : phase.completion_rate}%</span>
                                <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                                  <div 
                                    className={`h-full transition-all ${
                                      (phase.budgeted_hours ? phase.budget_used_percentage : phase.completion_rate) > 100 ? 'bg-red-500' : 'bg-blue-500'
                                    }`}
                                    style={{ width: `${Math.min((phase.budgeted_hours ? phase.budget_used_percentage : phase.completion_rate), 100)}%` }}
                                  />
                                </div>
                              </div>
                            </td>
                            <td className="p-3 text-center">
                              <Badge variant="outline">{phase.status}</Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot className="bg-gray-50 font-bold">
                        <tr className="border-t-2 border-gray-300">
                          <td className="p-3">Total</td>
                          <td className="p-3 text-right">{timeReport.project?.planned_hours || 0}h</td>
                          <td className="p-3 text-right">{timeReport.project?.actual_hours || 0}h</td>
                          <td className={`p-3 text-right ${
                            (timeReport.project?.variance_hours || 0) > 0 ? 'text-amber-600' : 
                            (timeReport.project?.variance_hours || 0) < 0 ? 'text-emerald-600' : 
                            'text-gray-600'
                          }`}>
                            {(timeReport.project?.variance_hours || 0) > 0 ? '+' : ''}{timeReport.project?.variance_hours || 0}h
                          </td>
                          <td className="p-3 text-right" colSpan="2"></td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <Clock className="w-12 h-12 mx-auto mb-3 opacity-40" />
                    <p>No phase time tracking data available yet.</p>
                    <p className="text-sm mt-1">Time will be tracked as team members submit timesheets.</p>
                  </div>
                )}
              </div>

              {/* Resource Breakdown */}
              <div className="bg-white border border-[#E6E8EC] rounded-lg p-6">
                <h3 className="text-lg font-semibold mb-4" style={{ fontFamily: 'Space Grotesk' }}>
                  Resource Breakdown
                </h3>
                
                {timeReport.resources && timeReport.resources.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="text-left p-3 text-sm font-medium text-gray-700">Resource</th>
                          <th className="text-right p-3 text-sm font-medium text-gray-700">Allocated</th>
                          <th className="text-right p-3 text-sm font-medium text-gray-700">Actual</th>
                          <th className="text-right p-3 text-sm font-medium text-gray-700">Variance</th>
                          <th className="text-right p-3 text-sm font-medium text-gray-700">Utilization</th>
                        </tr>
                      </thead>
                      <tbody>
                        {timeReport.resources.map((resource, index) => (
                          <tr key={index} className="border-t border-gray-100">
                            <td className="p-3 font-medium">{resource.resource_name}</td>
                            <td className="p-3 text-right text-gray-600">{resource.planned_hours}h</td>
                            <td className="p-3 text-right font-medium">{resource.actual_hours}h</td>
                            <td className={`p-3 text-right font-medium ${
                              resource.variance_hours > 0 ? 'text-amber-600' : 
                              resource.variance_hours < 0 ? 'text-emerald-600' : 
                              'text-gray-600'
                            }`}>
                              {resource.variance_hours > 0 ? '+' : ''}{resource.variance_hours}h
                            </td>
                            <td className="p-3 text-right">
                              <div className="flex items-center justify-end gap-2">
                                <span className={`text-sm font-medium ${
                                  resource.utilization_rate < 50 ? 'text-red-600' : 
                                  resource.utilization_rate >= 80 ? 'text-emerald-600' : 
                                  'text-gray-600'
                                }`}>
                                  {resource.utilization_rate}%
                                </span>
                                {resource.utilization_rate < 50 && (
                                  <Badge variant="outline" className="bg-red-50 text-red-700 text-xs">
                                    Under-utilized
                                  </Badge>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <UserCircle className="w-12 h-12 mx-auto mb-3 opacity-40" />
                    <p>No resource time tracking data available yet.</p>
                    <p className="text-sm mt-1">Time will be tracked as team members submit timesheets.</p>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <AlertTriangle className="w-12 h-12 mx-auto mb-3 opacity-40" />
              <p>Failed to load time tracking data.</p>
            </div>
          )}
        </TabsContent>

        {/* TAB 5: SETTINGS */}
        <TabsContent value="settings" className="space-y-6">
          {/* Project Metadata */}
          <div className="bg-white border border-[#E6E8EC] rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4" style={{ fontFamily: 'Space Grotesk' }}>
              Project Information
            </h3>
            <div className="space-y-4">
              <div>
                <div className="text-sm font-medium text-[#0B1220] mb-1">Project ID</div>
                <div className="text-sm text-[#667085] font-mono">{project.id}</div>
              </div>
              <div>
                <div className="text-sm font-medium text-[#0B1220] mb-1">Created</div>
                <div className="text-sm text-[#667085]">
                  {safeFormatDate(project.created_at)}
                </div>
              </div>
              <div className="text-sm text-[#667085] pt-2 border-t border-[#E6E8EC]">
                <span className="font-medium text-[#0B1220]">Tip:</span> To edit project name, client, status, dates, or budget — click the <strong>Edit Project</strong> button at the top of this page.
              </div>
            </div>
          </div>

          {/* Phase Management */}
          <div className="bg-white border border-[#E6E8EC] rounded-lg p-6" data-testid="phase-manager-card">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold" style={{ fontFamily: 'Space Grotesk' }}>
                  Project Phases
                </h3>
                <p className="text-sm text-[#667085] mt-1">
                  Add, edit, or remove phases. Each phase can have its own budget and dates.
                </p>
              </div>
              {!isEditingPhases && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleEditPhases}
                  data-testid="edit-phases-button"
                >
                  <Edit2 size={14} className="mr-2" />
                  Edit Phases
                </Button>
              )}
              {isEditingPhases && (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCancelEditPhases}
                    disabled={updatePhasesMutation.isPending}
                    data-testid="cancel-phase-edits-button"
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleSavePhases}
                    disabled={updatePhasesMutation.isPending}
                    className="bg-[#1570EF] hover:bg-[#1570EF]/90"
                    data-testid="save-phase-edits-button"
                  >
                    {updatePhasesMutation.isPending ? (
                      <><Loader2 size={14} className="mr-2 animate-spin" />Saving...</>
                    ) : (
                      <><Save size={14} className="mr-2" />Save Phases</>
                    )}
                  </Button>
                </div>
              )}
            </div>

            {/* Phase List */}
            {!isEditingPhases ? (
              <div className="space-y-2">
                {(project.phases || []).length === 0 ? (
                  <p className="text-sm text-[#667085] italic py-4 text-center">
                    No phases defined. Click &ldquo;Edit Phases&rdquo; to add some.
                  </p>
                ) : (
                  (project.phases || []).map((phase, idx) => (
                    <div
                      key={phase.id || idx}
                      className="flex items-center justify-between p-3 border border-[#E6E8EC] rounded-md bg-[#F8FAFC]"
                      data-testid={`phase-view-row-${idx}`}
                    >
                      <div className="flex-1 grid grid-cols-4 gap-4">
                        <div>
                          <div className="text-xs text-[#667085] uppercase tracking-wide">Name</div>
                          <div className="text-sm font-medium text-[#0B1220]">{phase.name || '—'}</div>
                        </div>
                        <div>
                          <div className="text-xs text-[#667085] uppercase tracking-wide">Start</div>
                          <div className="text-sm text-[#475467]">{safeFormatDate(phase.start_date)}</div>
                        </div>
                        <div>
                          <div className="text-xs text-[#667085] uppercase tracking-wide">End</div>
                          <div className="text-sm text-[#475467]">{safeFormatDate(phase.end_date)}</div>
                        </div>
                        <div>
                          <div className="text-xs text-[#667085] uppercase tracking-wide">Budgeted Hours</div>
                          <div className="text-sm text-[#475467]">{phase.budgeted_hours ?? '—'}</div>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            ) : (
              <div className="space-y-3">
                {(editedPhases || []).map((phase, idx) => (
                  <div
                    key={phase.id || idx}
                    className="p-4 border border-[#E6E8EC] rounded-md bg-white"
                    data-testid={`phase-edit-row-${idx}`}
                  >
                    <div className="grid grid-cols-12 gap-3 items-end">
                      <div className="col-span-4">
                        <Label className="text-xs text-[#667085] uppercase tracking-wide mb-1 block">Phase Name</Label>
                        <Input
                          value={phase.name || ''}
                          onChange={(e) => handleUpdatePhaseInSettings(idx, 'name', e.target.value)}
                          placeholder="e.g., Discovery"
                          data-testid={`phase-name-input-${idx}`}
                        />
                      </div>
                      <div className="col-span-3">
                        <Label className="text-xs text-[#667085] uppercase tracking-wide mb-1 block">Start Date</Label>
                        <WeekdayDateInput
                          value={phase.start_date ? String(phase.start_date).slice(0, 10) : ''}
                          onChange={(e) => handleUpdatePhaseInSettings(idx, 'start_date', e.target.value)}
                          data-testid={`phase-start-input-${idx}`}
                        />
                      </div>
                      <div className="col-span-3">
                        <Label className="text-xs text-[#667085] uppercase tracking-wide mb-1 block">End Date</Label>
                        <WeekdayDateInput
                          value={phase.end_date ? String(phase.end_date).slice(0, 10) : ''}
                          onChange={(e) => handleUpdatePhaseInSettings(idx, 'end_date', e.target.value)}
                          data-testid={`phase-end-input-${idx}`}
                        />
                      </div>
                      <div className="col-span-1">
                        <Label className="text-xs text-[#667085] uppercase tracking-wide mb-1 block">Hours</Label>
                        <Input
                          type="number"
                          min="0"
                          step="1"
                          value={phase.budgeted_hours ?? ''}
                          onChange={(e) => handleUpdatePhaseInSettings(idx, 'budgeted_hours', e.target.value)}
                          placeholder="0"
                          data-testid={`phase-hours-input-${idx}`}
                        />
                      </div>
                      <div className="col-span-1 flex justify-end">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-[#EF4444] hover:bg-red-50 hover:text-[#EF4444]"
                          onClick={() => handleDeletePhaseInSettings(idx)}
                          data-testid={`delete-phase-${idx}`}
                        >
                          <Trash2 size={16} />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}

                <Button
                  variant="outline"
                  onClick={handleAddPhaseInSettings}
                  className="w-full border-dashed"
                  data-testid="add-phase-button"
                >
                  <Plus size={14} className="mr-2" />
                  Add Phase
                </Button>
              </div>
            )}
          </div>

          {/* AI Instructions Panel */}
          <AIInstructionsPanel 
            scope="project" 
            projectId={id} 
            projectName={project?.name}
          />

          {/* Agent Memory Panel */}
          <div className="mt-6">
            <AIMemoryPanel projectId={id} />
          </div>

          {/* Phase Delete Confirmation Dialog */}
          <AlertDialog open={phaseToDelete !== null} onOpenChange={(open) => !open && cancelDeletePhase()}>
            <AlertDialogContent data-testid="delete-phase-dialog">
              <AlertDialogHeader>
                <AlertDialogTitle>Delete this phase?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will remove the phase from the project. Any allocations or timesheets that reference this phase will lose their phase link but won&apos;t be deleted. This action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel onClick={cancelDeletePhase} data-testid="cancel-delete-phase">Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={confirmDeletePhase}
                  className="bg-[#EF4444] hover:bg-[#EF4444]/90"
                  data-testid="confirm-delete-phase"
                >
                  Delete Phase
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </TabsContent>
      </Tabs>

      {/* Edit Status Update Dialog (Admin only) */}
      <EditStatusUpdateDialog
        open={showEditStatusDialog}
        onClose={() => {
          setShowEditStatusDialog(false);
          setEditingStatusUpdate(null);
        }}
        statusUpdate={editingStatusUpdate}
        projectId={id}
        statusOptions={statusOptions}
      />

      {/* Add Status Update Dialog */}
      <Dialog open={showAddStatusDialog} onOpenChange={setShowAddStatusDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="add-status-update-dialog">
          <DialogHeader>
            <DialogTitle>Add Status Update</DialogTitle>
            <DialogDescription>
              Record a new status update for {project?.name}. This will update the project health and progress metrics.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* Health Status */}
            <div>
              <Label htmlFor="health" className="text-sm font-medium">
                Health Status *
              </Label>
              <Select
                value={statusForm.health}
                onValueChange={(value) => setStatusForm({ ...statusForm, health: value })}
              >
                <SelectTrigger data-testid="status-health-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(statusOptions?.health_options || ['Green', 'Amber', 'Red']).map(option => (
                    <SelectItem key={option} value={option}>
                      {option}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Schedule Status */}
            <div>
              <Label htmlFor="schedule" className="text-sm font-medium">
                Schedule Status *
              </Label>
              <Select
                value={statusForm.schedule_status}
                onValueChange={(value) => setStatusForm({ ...statusForm, schedule_status: value })}
              >
                <SelectTrigger data-testid="status-schedule-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(statusOptions?.schedule_options || ['On Track', 'Delayed', 'Ahead of Schedule', 'At Risk']).map(option => (
                    <SelectItem key={option} value={option}>
                      {option}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Actual Progress */}
            <div>
              <Label htmlFor="progress" className="text-sm font-medium">
                Actual Progress (0-100)
              </Label>
              <Input
                type="number"
                min="0"
                max="100"
                value={statusForm.actual_progress}
                onChange={(e) => setStatusForm({ ...statusForm, actual_progress: e.target.value })}
                placeholder="e.g., 45"
                data-testid="status-progress-input"
              />
            </div>

            {/* Accomplishments */}
            <div>
              <Label htmlFor="accomplishments" className="text-sm font-medium">
                Accomplishments This Period
              </Label>
              <Textarea
                value={statusForm.accomplishments}
                onChange={(e) => setStatusForm({ ...statusForm, accomplishments: e.target.value })}
                placeholder="What did the team accomplish?"
                rows={3}
                data-testid="status-accomplishments-input"
              />
            </div>

            {/* Blockers */}
            <div>
              <Label htmlFor="blockers" className="text-sm font-medium">
                Blockers & Challenges
              </Label>
              <Textarea
                value={statusForm.blockers}
                onChange={(e) => setStatusForm({ ...statusForm, blockers: e.target.value })}
                placeholder="What is blocking progress?"
                rows={3}
                data-testid="status-blockers-input"
              />
            </div>

            {/* Next Steps */}
            <div>
              <Label htmlFor="next-steps" className="text-sm font-medium">
                Next Steps
              </Label>
              <Textarea
                value={statusForm.next_steps}
                onChange={(e) => setStatusForm({ ...statusForm, next_steps: e.target.value })}
                placeholder="What are the next priorities?"
                rows={3}
                data-testid="status-next-steps-input"
              />
            </div>

            {/* Notes */}
            <div>
              <Label htmlFor="notes" className="text-sm font-medium">
                Additional Notes (Optional)
              </Label>
              <Textarea
                value={statusForm.notes}
                onChange={(e) => setStatusForm({ ...statusForm, notes: e.target.value })}
                placeholder="Any other important information..."
                rows={2}
                data-testid="status-notes-input"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowAddStatusDialog(false)}
              disabled={createStatusUpdateMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSubmitStatusUpdate}
              disabled={createStatusUpdateMutation.isPending}
              className="bg-[#1570EF] hover:bg-[#1570EF]/90"
              data-testid="submit-status-update-btn"
            >
              {createStatusUpdateMutation.isPending ? (
                <>
                  <Loader2 size={14} className="mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                'Submit Update'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Allocation Dialog (Add/Edit) */}
      <Dialog open={showAllocDialog} onOpenChange={setShowAllocDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="allocation-dialog">
          <DialogHeader>
            <DialogTitle>{editingAlloc ? 'Edit Allocation' : 'Allocate Resource'}</DialogTitle>
            <DialogDescription>
              {editingAlloc ? 'Update the resource allocation details below.' : 'Add a new resource to this project.'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* Resource Selection */}
            <div>
              <Label className="text-sm font-medium mb-2 block">Resource *</Label>
              <Select
                value={allocForm.resource_id}
                onValueChange={(value) => setAllocForm({ ...allocForm, resource_id: value })}
                disabled={!!editingAlloc}
              >
                <SelectTrigger data-testid="alloc-resource-select">
                  <SelectValue placeholder="Select a resource" />
                </SelectTrigger>
                <SelectContent>
                  {resources?.filter((resource) => resource.active !== false).map((resource) => {
                    const capacityInfo = resource.standard_capacity ? ` (${resource.standard_capacity}% capacity)` : '';
                    return (
                      <SelectItem key={resource.id} value={resource.id}>
                        {resource.name} — {resource.role}{capacityInfo}
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>

            {/* Dates */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-sm font-medium mb-2 block">Start Date *</Label>
                <WeekdayDateInput
                  value={allocForm.start_date}
                  onChange={(e) => setAllocForm({ ...allocForm, start_date: e.target.value })}
                  data-testid="alloc-start-date"
                />
              </div>
              <div>
                <Label className="text-sm font-medium mb-2 block">End Date *</Label>
                <WeekdayDateInput
                  value={allocForm.end_date}
                  onChange={(e) => setAllocForm({ ...allocForm, end_date: e.target.value })}
                  data-testid="alloc-end-date"
                />
              </div>
            </div>

            {/* Allocation Mode Toggle */}
            <div>
              <Label className="text-sm font-medium mb-2 block">Allocation Mode</Label>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant={allocForm.allocation_type === 'percentage' ? 'default' : 'outline'}
                  size="sm"
                  className={allocForm.allocation_type === 'percentage' ? 'bg-[#1570EF] text-white' : ''}
                  onClick={() => setAllocForm({ ...allocForm, allocation_type: 'percentage' })}
                  data-testid="alloc-mode-percentage"
                >
                  Percentage
                </Button>
                <Button
                  type="button"
                  variant={allocForm.allocation_type === 'hours' ? 'default' : 'outline'}
                  size="sm"
                  className={allocForm.allocation_type === 'hours' ? 'bg-[#1570EF] text-white' : ''}
                  onClick={() => setAllocForm({ ...allocForm, allocation_type: 'hours' })}
                  data-testid="alloc-mode-hours"
                >
                  Total Hours
                </Button>
              </div>
            </div>

            {/* Percentage or Hours input */}
            {allocForm.allocation_type === 'percentage' ? (
              <div>
                <Label className="text-sm font-medium mb-2 block">Allocation Percentage (0-200) *</Label>
                {(() => {
                  const selectedRes = resources?.find(r => r.id === allocForm.resource_id);
                  const cap = selectedRes?.standard_capacity || 100;
                  const hrsWk = (allocForm.percentage / 100) * (cap / 100) * 40;
                  return (
                    <div className="space-y-2">
                      <Input
                        type="number"
                        min="0"
                        max="200"
                        step="5"
                        value={allocForm.percentage}
                        onChange={(e) => setAllocForm({ ...allocForm, percentage: parseFloat(e.target.value) || 0 })}
                        data-testid="alloc-percentage"
                      />
                      <input
                        type="range"
                        min="0"
                        max="200"
                        step="5"
                        value={allocForm.percentage}
                        onChange={(e) => setAllocForm({ ...allocForm, percentage: parseFloat(e.target.value) })}
                        className="w-full"
                        data-testid="alloc-percentage-slider"
                      />
                      <div className="text-xs text-[#667085] text-right">
                        {allocForm.percentage}% = {hrsWk.toFixed(1)}h/wk
                        {cap < 100 && <span className="ml-1">(resource at {cap}% capacity)</span>}
                      </div>
                    </div>
                  );
                })()}
              </div>
            ) : (
              <div>
                <Label className="text-sm font-medium mb-2 block">Total Hours for Period *</Label>
                <Input
                  type="number"
                  min="1"
                  step="1"
                  value={allocForm.hours}
                  onChange={(e) => setAllocForm({ ...allocForm, hours: e.target.value })}
                  placeholder="e.g., 40"
                  data-testid="alloc-hours-input"
                />
                <p className="text-xs text-[#667085] mt-1">
                  Total hours this person should work on this project over the allocation period.
                </p>
              </div>
            )}

            {/* Role (Optional) */}
            <div>
              <Label className="text-sm font-medium mb-2 block">Role (Optional)</Label>
              <Input
                value={allocForm.role}
                onChange={(e) => setAllocForm({ ...allocForm, role: e.target.value })}
                placeholder="e.g., Frontend Developer"
                data-testid="alloc-role"
              />
            </div>

            {/* Budget Section */}
            {budgetHealth && (
              <div className="border-t border-[#E6E8EC] pt-4 mt-4">
                <h4 className="text-sm font-semibold text-[#0B1220] mb-3">Budget Impact</h4>
                {(() => {
                  const selectedRes = resources?.find(r => r.id === allocForm.resource_id);
                  const resCap = selectedRes?.standard_capacity || 100;
                  const budgetedHours = budgetHealth.budgeted_hours || 0;
                  const currentAllocated = budgetHealth.allocated_hours || 0;
                  const isHoursMode = allocForm.allocation_type === 'hours';
                  const newHours = isHoursMode
                    ? (parseFloat(allocForm.hours) || 0)
                    : computeAllocationHours(allocForm.start_date, allocForm.end_date, allocForm.percentage, resCap);
                  const oldHours = editingAlloc ? computeAllocationHours(
                    format(new Date(editingAlloc.start_date), 'yyyy-MM-dd'),
                    format(new Date(editingAlloc.end_date), 'yyyy-MM-dd'),
                    editingAlloc.percentage,
                    resCap
                  ) : 0;
                  const totalAfter = currentAllocated - oldHours + newHours;
                  const remaining = budgetedHours - totalAfter;
                  const wouldExceed = budgetedHours > 0 && totalAfter > budgetedHours;

                  return (
                    <div className="space-y-2 text-sm">
                      {budgetedHours > 0 ? (
                        <>
                          <div className="flex justify-between">
                            <span className="text-[#667085]">Project Budget:</span>
                            <span className="font-medium">{budgetedHours}h</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-[#667085]">Currently Allocated:</span>
                            <span className="font-medium">{currentAllocated}h</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-[#667085]">This allocation {editingAlloc ? 'changes by' : 'adds'}:</span>
                            <span className="font-medium text-[#1570EF]">
                              {editingAlloc && oldHours !== newHours ? (
                                `${newHours > oldHours ? '+' : ''}${newHours - oldHours}h`
                              ) : (
                                `${newHours}h`
                              )}
                            </span>
                          </div>
                          <div className="flex justify-between border-t border-[#E6E8EC] pt-2">
                            <span className="text-[#667085] font-medium">Remaining after this:</span>
                            <span className={`font-semibold ${wouldExceed ? 'text-[#EF4444]' : remaining < budgetedHours * 0.2 ? 'text-[#F4B740]' : 'text-[#16B364]'}`}>
                              {remaining}h
                            </span>
                          </div>
                          {wouldExceed && (
                            <div className="bg-red-50 border border-red-200 rounded p-3 flex items-start gap-2 mt-2">
                              <AlertTriangle size={16} className="text-red-600 mt-0.5 shrink-0" />
                              <div className="text-xs text-red-800">
                                <strong>Budget Exceeded:</strong> This would exceed the project budget by {Math.abs(remaining)}h. Please adjust the allocation or increase the project budget.
                              </div>
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="bg-blue-50 border border-blue-200 rounded p-3 flex items-start gap-2">
                          <Info size={16} className="text-blue-600 mt-0.5 shrink-0" />
                          <div className="text-xs text-blue-800">
                            No budget set for this project. This allocation will add <strong>{newHours}h</strong>.
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={resetAllocDialog}
              disabled={createAllocationMutation.isPending || updateAllocationMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={submitAllocDialog}
              disabled={
                createAllocationMutation.isPending || 
                updateAllocationMutation.isPending ||
                (() => {
                  // Disable if would exceed budget
                  if (!budgetHealth) return false;
                  const budgetedHours = budgetHealth.budgeted_hours || 0;
                  if (budgetedHours <= 0) return false;
                  const selectedRes = resources?.find(r => r.id === allocForm.resource_id);
                  const resCap = selectedRes?.standard_capacity || 100;
                  const currentAllocated = budgetHealth.allocated_hours || 0;
                  const isHoursMode = allocForm.allocation_type === 'hours';
                  const newHours = isHoursMode
                    ? (parseFloat(allocForm.hours) || 0)
                    : computeAllocationHours(allocForm.start_date, allocForm.end_date, allocForm.percentage, resCap);
                  const oldHours = editingAlloc ? computeAllocationHours(
                    format(new Date(editingAlloc.start_date), 'yyyy-MM-dd'),
                    format(new Date(editingAlloc.end_date), 'yyyy-MM-dd'),
                    editingAlloc.percentage,
                    resCap
                  ) : 0;
                  const totalAfter = currentAllocated - oldHours + newHours;
                  return totalAfter > budgetedHours;
                })()
              }
              className="bg-[#1570EF] hover:bg-[#1570EF]/90"
              data-testid="submit-alloc-btn"
            >
              {(createAllocationMutation.isPending || updateAllocationMutation.isPending) ? (
                <>
                  <Loader2 size={14} className="mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                editingAlloc ? 'Save Changes' : 'Add Allocation'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Allocation Confirmation */}
      <AlertDialog open={!!allocToDelete} onOpenChange={(open) => !open && setAllocToDelete(null)}>
        <AlertDialogContent data-testid="delete-alloc-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this allocation?</AlertDialogTitle>
            <AlertDialogDescription>
              This will remove {allocToDelete ? getResourceName(allocToDelete.resource_id) : 'this resource'} from the project team. 
              Any associated timesheets will remain but will lose their allocation link. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setAllocToDelete(null)} data-testid="cancel-delete-alloc">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDeleteAlloc}
              className="bg-[#EF4444] hover:bg-[#EF4444]/90"
              data-testid="confirm-delete-alloc"
            >
              Delete Allocation
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* AI Smart Reschedule Dialog */}
      <AIRescheduleDialog
        isOpen={showAIReschedule}
        onClose={() => setShowAIReschedule(false)}
        projectId={id}
        projectName={project?.name}
      />
    </div>
  );
};

export default ProjectDetail;
