import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { sendChatMessage, getChatSessions, getChatSession, deleteChatSession, executeChatAction, undoLastAction, executeActionPlan } from '../api';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import {
  Send,
  X,
  Loader2,
  Plus,
  Trash2,
  History,
  ChevronLeft,
  Sparkles,
  Bot,
  User,
  Check,
  XCircle,
  Zap,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Users,
  Briefcase,
  Calendar,
  Clock,
  DollarSign,
  Percent,
  ArrowRight,
  RotateCcw,
  ListChecks,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { toast } from 'sonner';

// Parse action blocks from AI response
const parseResponse = (text) => {
  const actionRegex = /```(?:action|json)?\s*\n?([\s\S]*?)```/;
  const match = text.match(actionRegex);
  if (match) {
    try {
      const jsonStr = match[1].trim();
      // Check if it's a valid action JSON
      if (jsonStr.includes('"action"')) {
        const action = JSON.parse(jsonStr);
        const narrative = text.replace(actionRegex, '').trim();
        return { narrative, action };
      }
    } catch {
      // Not valid JSON, treat as regular text
    }
  }
  return { narrative: text, action: null };
};

// Format AI response with rich formatting
const FormatResponse = ({ text }) => {
  // Split into paragraphs
  const lines = text.split('\n');
  const elements = [];
  let currentList = [];
  let listType = null;
  let inTable = false;
  let tableRows = [];

  const flushList = () => {
    if (currentList.length > 0) {
      elements.push(
        <ul key={`list-${elements.length}`} className="my-2 space-y-1.5">
          {currentList.map((item, i) => (
            <li key={i} className="flex items-start gap-2 text-sm">
              <span className="text-[#1570EF] mt-1.5">•</span>
              <span className="flex-1">{formatInlineText(item)}</span>
            </li>
          ))}
        </ul>
      );
      currentList = [];
      listType = null;
    }
  };

  const flushTable = () => {
    if (tableRows.length > 0) {
      elements.push(
        <div key={`table-${elements.length}`} className="my-3 overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <tbody>
              {tableRows.map((row, i) => (
                <tr key={i} className={i === 0 ? 'bg-[#F9FAFB] font-medium' : 'border-t border-[#E6E8EC]'}>
                  {row.map((cell, j) => (
                    <td key={j} className="px-2 py-1.5 text-left">{cell.trim()}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      tableRows = [];
      inTable = false;
    }
  };

  // Format inline text (bold, numbers, percentages)
  const formatInlineText = (text) => {
    // Split by **bold** markers and other patterns
    const parts = text.split(/(\*\*[^*]+\*\*|\d+%|\$[\d,]+|\d+\s*(?:hours?|hrs?|days?))/gi);
    
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="font-semibold text-[#0B1220]">{part.slice(2, -2)}</strong>;
      }
      if (/^\d+%$/.test(part)) {
        const num = parseInt(part);
        const color = num > 100 ? 'text-[#EF4444]' : num >= 80 ? 'text-[#F4B740]' : 'text-[#16B364]';
        return <span key={i} className={`font-semibold ${color}`}>{part}</span>;
      }
      if (/^\$[\d,]+$/.test(part)) {
        return <span key={i} className="font-semibold text-[#16B364]">{part}</span>;
      }
      if (/^\d+\s*(?:hours?|hrs?|days?)$/i.test(part)) {
        return <span key={i} className="font-medium text-[#1570EF]">{part}</span>;
      }
      return part;
    });
  };

  // Detect status indicators
  const getStatusIcon = (text) => {
    const lower = text.toLowerCase();
    if (lower.includes('over-utilized') || lower.includes('over-allocated') || lower.includes('exceeded') || lower.includes('risk')) {
      return <AlertTriangle size={14} className="text-[#EF4444]" />;
    }
    if (lower.includes('at capacity') || lower.includes('near capacity')) {
      return <TrendingUp size={14} className="text-[#F4B740]" />;
    }
    if (lower.includes('available') || lower.includes('on track') || lower.includes('completed')) {
      return <Check size={14} className="text-[#16B364]" />;
    }
    return null;
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();
    
    // Skip empty lines
    if (!trimmed) {
      flushList();
      flushTable();
      return;
    }

    // Handle table rows (lines with | separators)
    if (trimmed.includes('|') && trimmed.split('|').length >= 3) {
      flushList();
      const cells = trimmed.split('|').filter(c => c.trim() && !c.match(/^[-:]+$/));
      if (cells.length > 0) {
        inTable = true;
        tableRows.push(cells);
      }
      return;
    } else if (inTable) {
      flushTable();
    }

    // Handle bullet points
    if (trimmed.match(/^[-•*]\s+/)) {
      flushTable();
      currentList.push(trimmed.replace(/^[-•*]\s+/, ''));
      return;
    }

    // Handle numbered lists
    if (trimmed.match(/^\d+[.)]\s+/)) {
      flushTable();
      currentList.push(trimmed.replace(/^\d+[.)]\s+/, ''));
      return;
    }

    flushList();
    flushTable();

    // Handle headers (lines ending with :)
    if (trimmed.endsWith(':') && trimmed.length < 60 && !trimmed.includes('.')) {
      const icon = getStatusIcon(trimmed);
      elements.push(
        <div key={`h-${index}`} className="flex items-center gap-2 mt-3 mb-1.5">
          {icon}
          <h4 className="font-semibold text-sm text-[#0B1220]">{trimmed}</h4>
        </div>
      );
      return;
    }

    // Handle summary/insight cards
    if (trimmed.toLowerCase().startsWith('summary:') || trimmed.toLowerCase().startsWith('insight:') || trimmed.toLowerCase().startsWith('recommendation:')) {
      const [label, ...rest] = trimmed.split(':');
      elements.push(
        <div key={`card-${index}`} className="my-2 p-2.5 bg-[#1570EF]/5 border border-[#1570EF]/20 rounded-lg">
          <div className="flex items-center gap-1.5 mb-1">
            <Sparkles size={12} className="text-[#1570EF]" />
            <span className="text-xs font-semibold text-[#1570EF] uppercase">{label}</span>
          </div>
          <p className="text-sm text-[#344054]">{formatInlineText(rest.join(':').trim())}</p>
        </div>
      );
      return;
    }

    // Handle resource mentions (Name - XX%)
    if (trimmed.match(/^[A-Z][a-z]+(\s[A-Z][a-z]+)*\s*[-–]\s*\d+%/)) {
      const [name, ...rest] = trimmed.split(/[-–]/);
      elements.push(
        <div key={`res-${index}`} className="flex items-center justify-between py-1.5 border-b border-[#F2F3F5] last:border-b-0">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-[#1570EF]/10 flex items-center justify-center">
              <Users size={12} className="text-[#1570EF]" />
            </div>
            <span className="font-medium text-sm">{name.trim()}</span>
          </div>
          <span className="text-sm">{formatInlineText(rest.join('-').trim())}</span>
        </div>
      );
      return;
    }

    // Handle project mentions with arrow indicators
    if (trimmed.includes('→') || trimmed.includes('->')) {
      elements.push(
        <div key={`proj-${index}`} className="flex items-center gap-2 py-1 text-sm">
          <ArrowRight size={14} className="text-[#98A2B3]" />
          <span>{formatInlineText(trimmed.replace(/[→>-]+/g, '').trim())}</span>
        </div>
      );
      return;
    }

    // Regular paragraph
    elements.push(
      <p key={`p-${index}`} className="text-sm leading-relaxed text-[#344054] my-1.5">
        {formatInlineText(trimmed)}
      </p>
    );
  });

  flushList();
  flushTable();

  return <div className="space-y-0.5">{elements}</div>;
};

const ActionCard = ({ action, onConfirm, onDismiss, isExecuting, executed }) => {
  const actionLabels = {
    create_project: 'Create Project',
    create_allocation: 'Create Allocation',
    update_allocation: 'Update Allocation',
    remove_allocation: 'Remove Allocation',
    update_project_status: 'Update Project Status',
    update_project_dates: 'Update Project Dates',
    add_risk: 'Add Risk',
    update_risk: 'Update Risk',
    set_project_lead: 'Set Project Lead',
    bulk_set_project_lead: 'Bulk Set Project Lead',
    create_status_update: 'Submit Weekly Status Update',
  };

  const actionIcons = {
    create_project: Briefcase,
    create_allocation: Calendar,
    update_allocation: Clock,
    remove_allocation: XCircle,
    update_project_status: TrendingUp,
    update_project_dates: Calendar,
    add_risk: AlertTriangle,
    update_risk: AlertTriangle,
    set_project_lead: User,
    bulk_set_project_lead: Users,
    create_status_update: Sparkles,
  };

  const Icon = actionIcons[action.action] || Zap;

  if (executed) {
    return (
      <div className="mt-2 p-3 rounded-lg border border-[#16B364]/30 bg-[#16B364]/5">
        <div className="flex items-center gap-2 text-sm text-[#16B364] font-medium">
          <Check size={14} />
          Action completed: {action.description || actionLabels[action.action] || action.action}
        </div>
      </div>
    );
  }

  return (
    <div className="mt-2 p-3 rounded-lg border border-[#1570EF]/30 bg-[#1570EF]/5" data-testid="action-card">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={14} className="text-[#1570EF]" />
        <span className="text-xs font-semibold text-[#1570EF] uppercase tracking-wider">
          {actionLabels[action.action] || action.action}
        </span>
      </div>
      <p className="text-sm text-[#475467] mb-3">{action.description || action.summary || 'Execute this action?'}</p>
      <div className="flex gap-2">
        <Button
          size="sm"
          onClick={onConfirm}
          disabled={isExecuting}
          className="bg-[#1570EF] hover:bg-[#0F5DC9] text-xs h-8"
          data-testid="action-confirm-btn"
        >
          {isExecuting ? <Loader2 size={12} className="animate-spin mr-1" /> : <Check size={12} className="mr-1" />}
          Confirm
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={onDismiss}
          disabled={isExecuting}
          className="text-xs h-8"
          data-testid="action-dismiss-btn"
        >
          <XCircle size={12} className="mr-1" />
          Cancel
        </Button>
      </div>
    </div>
  );
};

// PlanCard — shows a multi-step action plan for user review before execution
const STEP_ACTION_LABELS = {
  create_project: 'Create project',
  create_allocation: 'Allocate resource',
  manage_phases: 'Set up phases',
  update_project: 'Update project',
  add_risk: 'Add risk',
  create_status_update: 'Add status update',
  generate_wbs: 'Generate WBS',
  create_wbs_task: 'Add WBS task',
  create_baseline: 'Save baseline',
  autofill_timesheets_week: 'Autofill timesheets',
};

const PlanCard = ({ plan, onExecute, isExecuting, results }) => {
  const [expanded, setExpanded] = useState(true);
  const steps = plan?.steps || [];
  const allDone = results && results.length === steps.length;
  const successCount = results ? results.filter((r) => r.success).length : 0;

  return (
    <div className="mt-2 rounded-xl border border-[#7F56D9]/30 bg-[#7F56D9]/5 overflow-hidden" data-testid="plan-card">
      {/* Header */}
      <div
        className="flex items-center justify-between px-3.5 py-2.5 cursor-pointer"
        onClick={() => setExpanded((e) => !e)}
      >
        <div className="flex items-center gap-2">
          <ListChecks size={14} className="text-[#7F56D9]" />
          <span className="text-xs font-semibold text-[#7F56D9] uppercase tracking-wider">
            {plan.title || 'Action Plan'} — {steps.length} steps
          </span>
        </div>
        {expanded ? <ChevronUp size={14} className="text-[#7F56D9]" /> : <ChevronDown size={14} className="text-[#7F56D9]" />}
      </div>

      {expanded && (
        <div className="px-3.5 pb-3">
          {plan.description && (
            <p className="text-xs text-[#475467] mb-2.5">{plan.description}</p>
          )}
          {/* Steps list */}
          <ol className="space-y-1.5 mb-3">
            {steps.map((step, i) => {
              const r = results && results[i];
              return (
                <li key={i} className="flex items-start gap-2">
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 text-[10px] font-bold
                    ${r ? (r.success ? 'bg-[#16B364] text-white' : 'bg-red-500 text-white') : 'bg-[#7F56D9]/20 text-[#7F56D9]'}`}>
                    {r ? (r.success ? <Check size={10} /> : <X size={10} />) : i + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-[#344054]">
                      {STEP_ACTION_LABELS[step.action] || step.action}
                    </p>
                    {step.description && (
                      <p className="text-xs text-[#667085] truncate">{step.description}</p>
                    )}
                    {r && !r.success && (
                      <p className="text-xs text-red-500 mt-0.5">{r.message}</p>
                    )}
                    {r && r.success && (
                      <p className="text-xs text-[#16B364] mt-0.5">{r.message}</p>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>

          {/* Action buttons */}
          {!allDone ? (
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={onExecute}
                disabled={isExecuting}
                className="bg-[#7F56D9] hover:bg-[#6941C6] text-xs h-8"
                data-testid="plan-execute-btn"
              >
                {isExecuting ? (
                  <><Loader2 size={12} className="animate-spin mr-1" /> Running...</>
                ) : (
                  <><Check size={12} className="mr-1" /> Execute All {steps.length} Steps</>
                )}
              </Button>
            </div>
          ) : (
            <div className={`text-xs font-medium ${successCount === steps.length ? 'text-[#16B364]' : 'text-amber-600'}`}>
              {successCount === steps.length
                ? `All ${steps.length} steps completed successfully`
                : `${successCount}/${steps.length} steps succeeded`}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const MessageBubble = ({ msg, onActionConfirm, onActionDismiss, executingAction, executedActions, onPlanExecute, executingPlan, planResults }) => {
  if (msg.role === 'user') {
    return (
      <div className="flex gap-2 justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md px-3.5 py-2.5 text-sm leading-relaxed bg-[#1570EF] text-white">
          {msg.content}
        </div>
        <div className="w-7 h-7 rounded-full bg-[#1570EF] flex items-center justify-center flex-shrink-0 mt-0.5">
          <User size={14} className="text-white" />
        </div>
      </div>
    );
  }

  if (msg.loading) {
    return (
      <div className="flex gap-2 justify-start">
        <div className="w-7 h-7 rounded-full bg-[#0B1220] flex items-center justify-center flex-shrink-0 mt-0.5">
          <Bot size={14} className="text-white" />
        </div>
        <div className="max-w-[85%] rounded-2xl rounded-bl-md px-3.5 py-2.5 bg-[#F7F7F8] border border-[#E6E8EC]">
          <div className="flex items-center gap-2 text-[#667085]">
            <Loader2 size={14} className="animate-spin" />
            <span className="text-xs">Analyzing data...</span>
          </div>
        </div>
      </div>
    );
  }

  const { narrative, action } = parseResponse(msg.content);
  const msgKey = msg.timestamp || '';
  const isExecuted = executedActions?.has(msgKey);
  const plan = msg.plan || null;
  const planResult = planResults?.get(msgKey) || null;

  return (
    <div className="flex gap-2 justify-start">
      <div className="w-7 h-7 rounded-full bg-[#0B1220] flex items-center justify-center flex-shrink-0 mt-0.5">
        <Bot size={14} className="text-white" />
      </div>
      <div className="max-w-[85%]">
        <div className="rounded-2xl rounded-bl-md px-3.5 py-2.5 bg-[#F7F7F8] text-[#0B1220] border border-[#E6E8EC]">
          <FormatResponse text={narrative} />
        </div>
        {plan && (
          <PlanCard
            plan={plan}
            onExecute={() => onPlanExecute(plan, msgKey)}
            isExecuting={executingPlan === msgKey}
            results={planResult}
          />
        )}
        {action && !plan && (
          <ActionCard
            action={action}
            onConfirm={() => onActionConfirm(action, msgKey)}
            onDismiss={() => onActionDismiss(msgKey)}
            isExecuting={executingAction === msgKey}
            executed={isExecuted}
          />
        )}
      </div>
    </div>
  );
};

const ChatPanel = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [executingAction, setExecutingAction] = useState(null);
  const [executedActions, setExecutedActions] = useState(new Set());
  const [canUndo, setCanUndo] = useState(false);
  const [undoLabel, setUndoLabel] = useState(null);
  const [executingPlan, setExecutingPlan] = useState(null);       // msgKey of plan being executed
  const [planResults, setPlanResults] = useState(new Map());      // msgKey → results array
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const queryClient = useQueryClient();

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Fetch chat sessions for history
  const { data: sessions } = useQuery({
    queryKey: ['chatSessions'],
    queryFn: async () => {
      const res = await getChatSessions();
      return res.data;
    },
    enabled: showHistory,
  });

  // Send message mutation
  const sendMutation = useMutation({
    mutationFn: async (msg) => {
      const res = await sendChatMessage(msg, sessionId);
      return res.data;
    },
    onSuccess: (data) => {
      setSessionId(data.session_id);
      const ts = new Date().toISOString();
      setMessages((prev) => {
        const filtered = prev.filter((m) => !m.loading);
        const newMsg = {
          role: 'assistant',
          content: data.response,
          timestamp: ts,
        };
        // Attach plan data to the message if the AI returned a plan
        if (data.has_plan && data.plan) {
          newMsg.plan = data.plan;
        }
        return [...filtered, newMsg];
      });
      // Track undo availability from auto-executed action
      setCanUndo(!!data.can_undo);
      setUndoLabel(data.undo_label || null);
      // Refresh relevant queries if an action was auto-executed
      if (data.auto_executed) {
        queryClient.invalidateQueries(['allocations']);
        queryClient.invalidateQueries(['projects']);
        queryClient.invalidateQueries(['resources']);
        queryClient.invalidateQueries(['projectRisks']);
        queryClient.invalidateQueries(['projectStatusUpdates']);
      }
    },
    onError: (err) => {
      setMessages((prev) => prev.filter((m) => !m.loading));
      toast.error(err.response?.data?.detail || 'Failed to send message');
    },
  });

  // Undo last action mutation
  const undoMutation = useMutation({
    mutationFn: () => undoLastAction(sessionId),
    onSuccess: (data) => {
      if (data.data.success) {
        toast.success(data.data.message || 'Undone');
        setCanUndo(false);
        setUndoLabel(null);
        // Append an undo note to the message thread
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `↩️ **Undo applied.** ${data.data.message || ''}`,
            timestamp: new Date().toISOString(),
          },
        ]);
        // Refresh data
        queryClient.invalidateQueries(['allocations']);
        queryClient.invalidateQueries(['projects']);
        queryClient.invalidateQueries(['resources']);
        queryClient.invalidateQueries(['projectRisks']);
        queryClient.invalidateQueries(['projectStatusUpdates']);
      } else {
        toast.error(data.data.message || 'Nothing to undo');
        setCanUndo(false);
        setUndoLabel(null);
      }
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || 'Undo failed');
    },
  });

  // Execute action mutation
  const executeMutation = useMutation({
    mutationFn: ({ action }) => executeChatAction(action),
    onSuccess: (data, variables) => {
      toast.success(data.data.message || 'Action completed');
      setExecutedActions((prev) => new Set([...prev, variables.msgKey]));
      queryClient.invalidateQueries(['allocations']);
      queryClient.invalidateQueries(['projects']);
      queryClient.invalidateQueries(['resources']);
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || 'Action failed');
    },
    onSettled: () => {
      setExecutingAction(null);
    },
  });

  // Execute multi-step action plan mutation
  const executePlanMutation = useMutation({
    mutationFn: ({ steps }) => executeActionPlan({ steps }),
    onSuccess: (data, variables) => {
      const { msgKey } = variables;
      const results = data.data?.results || [];
      setPlanResults((prev) => new Map([...prev, [msgKey, results]]));
      setExecutingPlan(null);
      const { success_count, total_steps } = data.data || {};
      if (success_count === total_steps) {
        toast.success(`Plan complete — all ${total_steps} steps succeeded`);
      } else {
        toast.warning(`Plan partially complete — ${success_count}/${total_steps} steps succeeded`);
      }
      queryClient.invalidateQueries(['allocations']);
      queryClient.invalidateQueries(['projects']);
      queryClient.invalidateQueries(['resources']);
      queryClient.invalidateQueries(['projectRisks']);
    },
    onError: (err) => {
      setExecutingPlan(null);
      toast.error(err.response?.data?.detail || 'Plan execution failed');
    },
  });

  // Load session mutation
  const loadSessionMutation = useMutation({
    mutationFn: getChatSession,
    onSuccess: (data) => {
      setSessionId(data.data.session_id);
      setMessages(
        data.data.messages.map((m, i) => ({
          ...m,
          timestamp: `loaded-${i}`,
        }))
      );
      setShowHistory(false);
      // Preserve undo capability from loaded session if present
      setCanUndo(!!data.data.last_undo);
      setUndoLabel(data.data.last_undo?.label || null);
    },
    onError: () => {
      toast.error('Failed to load session');
    },
  });

  // Delete session mutation
  const deleteSessionMutation = useMutation({
    mutationFn: deleteChatSession,
    onSuccess: () => {
      queryClient.invalidateQueries(['chatSessions']);
      toast.success('Session deleted');
    },
    onError: () => {
      toast.error('Failed to delete session');
    },
  });

  const handleSend = (e) => {
    e.preventDefault();
    if (!message.trim() || sendMutation.isPending) return;

    const userMsg = message.trim();
    setMessage('');
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: userMsg, timestamp: new Date().toISOString() },
      { role: 'assistant', content: '', loading: true },
    ]);

    sendMutation.mutate(userMsg);
  };

  const handleActionConfirm = (action, msgKey) => {
    setExecutingAction(msgKey);
    // Remove msgKey from the action before sending to API
    const { msgKey: _, ...actionData } = { ...action, msgKey };
    executeMutation.mutate({ action: actionData, msgKey });
  };

  const handleActionDismiss = (msgKey) => {
    setExecutedActions((prev) => new Set([...prev, msgKey]));
  };

  const handlePlanExecute = (plan, msgKey) => {
    if (executingPlan) return;
    setExecutingPlan(msgKey);
    executePlanMutation.mutate({ steps: plan.steps || [], msgKey });
  };

  const startNewSession = () => {
    setSessionId(null);
    setMessages([]);
    setExecutedActions(new Set());
    setCanUndo(false);
    setUndoLabel(null);
  };

  const quickPrompts = [
    { label: 'Team utilization', prompt: 'Give me a summary of team utilization this week' },
    { label: 'Projects at risk', prompt: 'Which projects are at risk or over budget?' },
    { label: 'Available resources', prompt: 'Who is available for new work this week?' },
    { label: 'Timesheet status', prompt: 'Show me the timesheet submission status for this week' },
  ];

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-4 right-4 w-12 h-12 bg-[#0B1220] hover:bg-[#1A2332] text-white rounded-full shadow-lg flex items-center justify-center transition-all hover:scale-105 z-50"
        data-testid="chat-toggle-btn"
      >
        <Sparkles size={20} />
      </button>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 w-[400px] h-[600px] bg-white rounded-2xl shadow-2xl border border-[#E6E8EC] flex flex-col overflow-hidden z-50" data-testid="chat-panel">
      {/* Header */}
      <div className="px-4 py-3 bg-[#0B1220] text-white flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          {showHistory ? (
            <button onClick={() => setShowHistory(false)} className="p-1 hover:bg-white/10 rounded">
              <ChevronLeft size={18} />
            </button>
          ) : (
            <Bot size={18} />
          )}
          <div>
            <h3 className="font-semibold text-sm">DD Planner AI</h3>
            <p className="text-[10px] text-[#94A3B8]">
              {showHistory ? 'Chat History' : sessionId ? 'Session active' : 'New conversation'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {!showHistory && canUndo && (
            <button
              onClick={() => undoMutation.mutate()}
              disabled={undoMutation.isPending}
              className="px-2 py-1 text-xs font-medium bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 rounded border border-amber-500/40 transition-colors flex items-center gap-1 disabled:opacity-50"
              title={undoLabel || 'Undo last action'}
              data-testid="chat-undo-btn"
            >
              <RotateCcw size={12} />
              {undoMutation.isPending ? 'Undoing…' : 'Undo'}
            </button>
          )}
          {!showHistory && (
            <>
              <button
                onClick={() => setShowHistory(true)}
                className="p-1.5 hover:bg-white/10 rounded transition-colors"
                title="Chat history"
              >
                <History size={16} />
              </button>
              <button
                onClick={startNewSession}
                className="p-1.5 hover:bg-white/10 rounded transition-colors"
                title="New chat"
              >
                <Plus size={16} />
              </button>
            </>
          )}
          <button
            onClick={() => setIsOpen(false)}
            className="p-1.5 hover:bg-white/10 rounded transition-colors"
            title="Close"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* History View */}
      {showHistory ? (
        <div className="flex-1 overflow-y-auto p-3">
          {!sessions || sessions.length === 0 ? (
            <div className="text-center py-8 text-[#667085] text-sm">No chat history yet</div>
          ) : (
            <div className="space-y-2">
              {sessions.map((session) => (
                <div
                  key={session.id}
                  className="p-3 bg-[#F9FAFB] rounded-lg hover:bg-[#F2F3F5] transition-colors cursor-pointer group"
                  onClick={() => loadSessionMutation.mutate(session.id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-[#0B1220] truncate">{session.preview || 'Chat session'}</p>
                      <p className="text-xs text-[#667085]">
                        {session.message_count} messages • {new Date(session.updated_at).toLocaleDateString()}
                      </p>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteSessionMutation.mutate(session.id);
                      }}
                      className="p-1.5 opacity-0 group-hover:opacity-100 hover:bg-[#EF4444]/10 rounded text-[#EF4444] transition-all"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center px-4">
                <div className="w-12 h-12 rounded-full bg-[#0B1220] flex items-center justify-center mb-3">
                  <Sparkles size={20} className="text-white" />
                </div>
                <h4 className="font-semibold text-[#0B1220] mb-1">DD Planner AI</h4>
                <p className="text-xs text-[#667085] mb-4">
                  Ask about projects, resources, utilization, or request actions
                </p>
                <div className="grid grid-cols-2 gap-2 w-full">
                  {quickPrompts.map((qp, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        setMessage(qp.prompt);
                        inputRef.current?.focus();
                      }}
                      className="p-2 text-xs text-left bg-[#F9FAFB] hover:bg-[#F2F3F5] rounded-lg border border-[#E6E8EC] transition-colors"
                    >
                      {qp.label}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg, i) => (
                <MessageBubble
                  key={i}
                  msg={msg}
                  onActionConfirm={handleActionConfirm}
                  onActionDismiss={handleActionDismiss}
                  executingAction={executingAction}
                  executedActions={executedActions}
                  onPlanExecute={handlePlanExecute}
                  executingPlan={executingPlan}
                  planResults={planResults}
                />
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <form onSubmit={handleSend} className="p-3 border-t border-[#E6E8EC] flex-shrink-0">
            <div className="flex gap-2">
              <Input
                ref={inputRef}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Ask or request an action..."
                className="flex-1 text-sm"
                disabled={sendMutation.isPending}
                data-testid="chat-input"
              />
              <Button
                type="submit"
                size="sm"
                disabled={sendMutation.isPending || !message.trim()}
                className="bg-[#0B1220] hover:bg-[#1A2332]"
                data-testid="chat-send-btn"
              >
                {sendMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              </Button>
            </div>
          </form>
        </>
      )}
    </div>
  );
};

export default ChatPanel;
