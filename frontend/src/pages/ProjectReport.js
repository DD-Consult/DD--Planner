import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getProject, getProjectRisks, getProjectAllocations, getResources, getProjectStatusUpdates, getProjectTimeReport, sendChatMessage, exportProjectPDF, exportProjectPPT, exportProjectWBSPDF, exportProjectWBSPPT, updateProjectSummary, getMe } from '../api';
import { format, differenceInDays, startOfWeek, endOfWeek, addDays, subDays, parseISO, isWithinInterval, isBefore, isAfter } from 'date-fns';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '../components/ui/dropdown-menu';
import { ArrowLeft, Printer, Calendar, TrendingUp, AlertTriangle, CheckCircle2, Clock, Sparkles, Bot, RefreshCw, Download, FileText, Presentation, Loader2, Target, ArrowRight, Edit2, Save, X, Mail, Copy, CheckCheck } from 'lucide-react';
import { Badge } from '../components/ui/badge';
import WBSView from '../components/WBSView';
import { toast } from 'sonner';
import '../styles/print.css';

// DD Consulting Brand Colours (from ddconsult.com.au)
const DD_NAVY   = '#1B2A47';  // deep navy — primary brand dark
const DD_BLUE   = '#4A9CC7';  // steel blue accent
const DD_GOLD   = '#C9A84C';  // gold/amber from compass logo  
const DD_WHITE  = '#FFFFFF';
const DD_LIGHT  = '#E8EDF2';  // light grey background
const DD_TEXT   = '#2D3748';  // dark text
const DD_MUTED  = '#718096';  // muted text

// DD Consulting Logo Component
const DDConsultingLogo = ({ className = "", showText = true, size = "md" }) => {
  const sizeClasses = {
    sm: "w-8 h-8",
    md: "w-12 h-12",
    lg: "w-16 h-16",
  };
  const textSizeClasses = {
    sm: "text-base",
    md: "text-xl",
    lg: "text-2xl",
  };
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <img
        src="/dd-consulting-logo.png"
        alt="DD Consulting"
        className={`${sizeClasses[size]} object-contain`}
        crossOrigin="anonymous"
      />
      {showText && (
        <div>
          <div className={`${textSizeClasses[size]} font-bold text-gray-900 tracking-tight`}>DD Consulting</div>
          <div className="text-xs text-gray-500 uppercase tracking-wider">Project Report</div>
        </div>
      )}
    </div>
  );
};

// Helper: Count business days (Monday-Friday only, excluding weekends)
const countBusinessDays = (startDate, endDate) => {
  if (!startDate || !endDate || startDate > endDate) return 0;
  
  let businessDays = 0;
  const current = new Date(startDate);
  const end = new Date(endDate);
  
  while (current <= end) {
    const dayOfWeek = current.getDay();
    // 0 = Sunday, 6 = Saturday
    if (dayOfWeek !== 0 && dayOfWeek !== 6) {
      businessDays++;
    }
    current.setDate(current.getDate() + 1);
  }
  
  return businessDays;
};

// Project Gantt Chart Component
const ProjectGanttChart = ({ project, phases }) => {
  const today = new Date();
  
  // Calculate project timeline
  const projectStart = project?.start_date ? parseISO(project.start_date.split('T')[0]) : null;
  const projectEnd = project?.end_date ? parseISO(project.end_date.split('T')[0]) : null;
  
  if (!projectStart || !projectEnd) {
    return (
      <div className="p-6 bg-gray-50 rounded-lg border border-gray-200 text-center text-gray-500">
        Project dates not set
      </div>
    );
  }
  
  // Use BUSINESS DAYS for calculations
  const totalBusinessDays = countBusinessDays(projectStart, projectEnd) || 1;
  const elapsedBusinessDays = countBusinessDays(projectStart, today > projectEnd ? projectEnd : today);
  const todayPosition = Math.max(0, Math.min(100, (elapsedBusinessDays / totalBusinessDays) * 100));
  const isPastProject = isAfter(today, projectEnd);
  const isBeforeProject = isBefore(today, projectStart);
  
  // Sort phases by start date
  const sortedPhases = [...(phases || [])].sort((a, b) => {
    const aStart = a.start_date ? parseISO(a.start_date.split('T')[0]) : projectStart;
    const bStart = b.start_date ? parseISO(b.start_date.split('T')[0]) : projectStart;
    return aStart - bStart;
  });

  // Generate month markers (use calendar days for positioning months on timeline)
  const months = [];
  let currentMonth = new Date(projectStart);
  const totalCalendarDays = differenceInDays(projectEnd, projectStart) || 1;
  while (currentMonth <= projectEnd) {
    const monthPosition = (differenceInDays(currentMonth, projectStart) / totalCalendarDays) * 100;
    if (monthPosition >= 0 && monthPosition <= 100) {
      months.push({
        label: format(currentMonth, 'MMM yyyy'),
        position: monthPosition,
      });
    }
    currentMonth = new Date(currentMonth.setMonth(currentMonth.getMonth() + 1));
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Project Timeline</h3>
          <div className="flex items-center gap-4 text-xs text-gray-500">
            <span>{format(projectStart, 'MMM d, yyyy')}</span>
            <span>→</span>
            <span>{format(projectEnd, 'MMM d, yyyy')}</span>
            <span className="text-gray-400">({totalBusinessDays} business days)</span>
          </div>
        </div>
      </div>

      {/* Month Headers - aligned to bar area via flex mirror of row structure */}
      <div className="relative h-8 bg-gray-100 border-b border-gray-200">
        <div className="absolute inset-0 flex items-center gap-3 px-4 pointer-events-none">
          <div className="w-28 shrink-0" aria-hidden />
          <div className="flex-1 relative h-full">
            {months.map((month, i) => (
              <div
                key={i}
                className="absolute top-0 h-full flex items-center border-l border-gray-300"
                style={{ left: `${month.position}%` }}
              >
                <span className="text-[10px] text-gray-500 px-1 whitespace-nowrap">{month.label}</span>
              </div>
            ))}
          </div>
          <div className="w-20 shrink-0" aria-hidden />
        </div>
      </div>

      {/* Gantt Bars */}
      <div className="relative px-4 py-4">
        {/* Today Line — overlay uses the SAME flex layout as the rows below
            so it perfectly inherits the bar-area position regardless of label width. */}
        {!isPastProject && !isBeforeProject && (
          <div className="absolute inset-x-4 inset-y-4 pointer-events-none flex items-stretch gap-3 z-20">
            <div className="w-28 shrink-0" aria-hidden />
            <div className="flex-1 relative">
              <div
                className="absolute top-0 bottom-0 w-0.5 bg-red-500"
                style={{ left: `${todayPosition}%` }}
              >
                <div className="absolute -top-1 left-1/2 -translate-x-1/2 bg-red-500 text-white text-[9px] px-1.5 py-0.5 rounded whitespace-nowrap">
                  Today
                </div>
              </div>
            </div>
            <div className="w-20 shrink-0" aria-hidden />
          </div>
        )}

        {/* Project Bar (full width background) */}
        <div className="mb-4">
          <div className="flex items-center gap-3 mb-1">
            <span className="text-xs font-medium text-gray-700 w-28 shrink-0">Full Project</span>
            <div className="flex-1 h-6 bg-[#E8EDF2] rounded relative overflow-hidden">
              <div
                className="absolute inset-y-0 left-0 bg-[#4A9CC7] rounded"
                style={{ width: `${Math.min(100, todayPosition)}%` }}
              />
              <div className="absolute inset-0 flex items-center justify-center text-[10px] font-medium text-[#1B2A47]">
                {format(projectStart, 'MMM d')} - {format(projectEnd, 'MMM d, yyyy')}
              </div>
            </div>
            {/* Invisible placeholder to match badge column width on phase rows */}
            <div className="shrink-0 w-20" aria-hidden />
          </div>
        </div>

        {/* Phase Bars */}
        {sortedPhases.length > 0 ? (
          <div className="space-y-3">
            {sortedPhases.map((phase, idx) => {
              const phaseStart = phase.start_date ? parseISO(phase.start_date.split('T')[0]) : projectStart;
              const phaseEnd = phase.end_date ? parseISO(phase.end_date.split('T')[0]) : projectEnd;
              
              const startPct = Math.max(0, (differenceInDays(phaseStart, projectStart) / totalCalendarDays) * 100);
              const widthPct = Math.min(100 - startPct, (differenceInDays(phaseEnd, phaseStart) / totalCalendarDays) * 100);
              
              // Determine phase status
              const isComplete = phase.status === 'Completed' || isAfter(today, phaseEnd);
              const isActive = !isComplete && isBefore(phaseStart, today) && isAfter(phaseEnd, today);
              const isFuture = isBefore(today, phaseStart);
              
              const barColor = isComplete ? 'bg-green-500' : isActive ? 'bg-blue-500' : 'bg-gray-300';
              const bgColor = isComplete ? 'bg-green-100' : isActive ? 'bg-blue-100' : 'bg-gray-100';

              return (
                <div key={idx} className="flex items-center gap-3">
                  <span className="text-xs font-medium text-gray-700 w-28 shrink-0 truncate" title={phase.name}>
                    {phase.name}
                  </span>
                  <div className="flex-1 h-5 bg-gray-50 rounded relative">
                    <div
                      className={`absolute h-full ${bgColor} rounded`}
                      style={{ left: `${startPct}%`, width: `${widthPct}%` }}
                    >
                      <div className={`h-full ${barColor} rounded`} style={{ width: isComplete ? '100%' : isActive ? `${((differenceInDays(today, phaseStart) / differenceInDays(phaseEnd, phaseStart)) * 100)}%` : '0%' }} />
                    </div>
                    {/* Phase label */}
                    <div
                      className="absolute h-full flex items-center text-[9px] font-medium text-gray-600 px-1"
                      style={{ left: `${startPct}%`, width: `${widthPct}%` }}
                    >
                      <span className="truncate">{format(phaseStart, 'MMM d')} - {format(phaseEnd, 'MMM d')}</span>
                    </div>
                  </div>
                  <Badge variant="outline" className={`text-[10px] shrink-0 w-20 justify-center ${isComplete ? 'bg-green-50 text-green-700' : isActive ? 'bg-blue-50 text-blue-700' : 'bg-gray-50 text-gray-500'}`}>
                    {isComplete ? 'Done' : isActive ? 'Active' : 'Upcoming'}
                  </Badge>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-center text-gray-500 text-sm py-4">No phases defined</div>
        )}

        {/* Legend */}
        <div className="mt-6 pt-4 border-t border-gray-100 flex items-center gap-6 text-xs text-gray-500">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 bg-green-500 rounded" />
            <span>Completed</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 bg-blue-500 rounded" />
            <span>In Progress</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 bg-gray-300 rounded" />
            <span>Upcoming</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-0.5 h-3 bg-red-500" />
            <span>Today</span>
          </div>
        </div>
      </div>
    </div>
  );
};

// Client-facing Status Summary with 4 structured sections
const AIStatusSummary = ({ project, periodInfo, statusUpdates = [], risks = [] }) => {
  const [sections, setSections] = useState(null); // { executive_summary, project_objective, achievements, next_period_focus }
  const [rawFallback, setRawFallback] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editedSummary, setEditedSummary] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Fetch current user to check permissions
  const { data: currentUser } = useQuery({
    queryKey: ['currentUser'],
    queryFn: async () => {
      const response = await getMe();
      return response.data;
    },
  });

  const isAdmin = currentUser?.role?.toLowerCase() === 'admin' || currentUser?.role?.toLowerCase() === 'project lead';

  const generateSummary = async () => {
    setIsLoading(true);
    setError(null);
    setRawFallback(null);
    try {
      const periodLabel = periodInfo?.label || 'the project to date';
      
      // Build comprehensive context from status updates
      let contextStr = '';
      if (statusUpdates && statusUpdates.length > 0) {
        contextStr = '\n\nCONTEXT FROM STATUS UPDATES:\n';
        statusUpdates.forEach((update, idx) => {
          contextStr += `\nUpdate ${idx + 1} (Week of ${update.week_start_date}):\n`;
          if (update.health) contextStr += `- Health: ${update.health}\n`;
          if (update.schedule_status) contextStr += `- Schedule Status: ${update.schedule_status}\n`;
          if (update.budget_status) contextStr += `- Budget Status: ${update.budget_status}\n`;
          if (update.accomplishments) contextStr += `- Accomplishments: ${update.accomplishments}\n`;
          if (update.upcoming_work) contextStr += `- Upcoming Work: ${update.upcoming_work}\n`;
          if (update.risks_issues) contextStr += `- Risks/Issues: ${update.risks_issues}\n`;
          if (update.milestones) contextStr += `- Milestones: ${update.milestones}\n`;
          if (update.notes) contextStr += `- Notes: ${update.notes}\n`;
        });
      }
      
      // Build risk context for AI
      let riskContextStr = '';
      if (risks && risks.length > 0) {
        const activeRisks = risks.filter(r => (r.status || 'Active') !== 'Closed');
        const mitigatedRisks = risks.filter(r => r.status === 'Mitigated');
        const closedRisks = risks.filter(r => r.status === 'Closed');
        const highImpactActive = activeRisks.filter(r => r.impact === 'High' || r.impact === 'Critical');
        
        riskContextStr = `\n\nRISK REGISTER SUMMARY:
- Total risks/issues: ${risks.length}
- Active: ${activeRisks.length}${highImpactActive.length > 0 ? ` (${highImpactActive.length} high/critical impact)` : ''}
- Being mitigated: ${mitigatedRisks.length}
- Closed/resolved: ${closedRisks.length}
${activeRisks.slice(0, 3).map(r => `- [${r.status}] ${r.impact} impact: ${(r.description || '').substring(0, 80)}`).join('\n')}`;
      }
      
      const prompt = `You are generating a CLIENT-FACING project status report for the project "${project?.name}" (client: ${project?.client_name || 'N/A'}). Reporting period: ${periodLabel}.
${contextStr}${riskContextStr}

Return ONLY a valid JSON object (no code fences, no prose before or after) with EXACTLY these four string keys:
{
  "executive_summary": "2-3 sentences. Professional, confident tone. Overall health, progress, and any headline decision the client should know. USE THE CONTEXT FROM STATUS UPDATES ABOVE. IMPORTANT: Include a brief, seamless mention of the risk posture — e.g. how many risks are being actively mitigated or monitored. Do NOT list individual risks, just a concise summary like 'X risks are being actively managed' woven naturally into the narrative.",
  "project_objective": "1-2 sentences. What this project is designed to deliver in business terms. No jargon.",
  "achievements": "Markdown bullet list (use '- ') of concrete accomplishments during ${periodLabel}. Outputs, milestones hit, risks closed. Keep to 3-6 bullets. REFERENCE THE ACCOMPLISHMENTS AND MILESTONES FROM STATUS UPDATES ABOVE.",
  "next_period_focus": "Markdown bullet list (use '- ') of what will be worked on next. Keep to 3-5 bullets. Client-relevant only. USE THE UPCOMING WORK FROM STATUS UPDATES ABOVE."
}

Rules:
- Write for the CLIENT, not the internal team. No mention of utilization %, internal staffing, or individual resource names unless critical.
- Be specific, not generic. Reference actual deliverables when available.
- IMPORTANT: Use all the context provided from status updates to make this summary comprehensive and accurate.
- The executive_summary MUST naturally weave in a brief risk posture mention (e.g. "X risks are under active mitigation" or "no outstanding risks"). Keep it subtle and professional.
- Do NOT include any action JSON blocks.`;

      const response = await sendChatMessage(prompt, null);
      const text = (response.data.response || '').trim();

      // Try to extract JSON (strip code fences if AI included them despite instruction)
      let jsonStr = text;
      const fenceMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/);
      if (fenceMatch) jsonStr = fenceMatch[1].trim();

      // Find first { ... last } in case there's stray prose
      const firstBrace = jsonStr.indexOf('{');
      const lastBrace = jsonStr.lastIndexOf('}');
      if (firstBrace !== -1 && lastBrace > firstBrace) {
        jsonStr = jsonStr.slice(firstBrace, lastBrace + 1);
      }

      try {
        const parsed = JSON.parse(jsonStr);
        if (parsed.executive_summary && parsed.project_objective) {
          setSections(parsed);
          setRawFallback(null);
        } else {
          throw new Error('Missing required fields');
        }
      } catch {
        // Fallback: show raw text if JSON parse fails
        setRawFallback(text);
        setSections(null);
      }
    } catch (err) {
      setError('Failed to generate status summary');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  // Auto-generate on mount and when period changes
  useEffect(() => {
    if (project?.id) {
      generateSummary();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id, periodInfo?.label]);

  const handleSaveSummary = async () => {
    if (!editedSummary.trim()) {
      toast.error('Summary cannot be empty');
      return;
    }

    setIsSaving(true);
    try {
      await updateProjectSummary(project.id, editedSummary);
      toast.success('Summary updated successfully');
      setIsEditing(false);
      // Update the sections state with the edited content
      try {
        const parsed = JSON.parse(editedSummary);
        if (parsed.executive_summary && parsed.project_objective) {
          setSections(parsed);
        }
      } catch {
        // If not JSON, treat as raw text
        setRawFallback(editedSummary);
        setSections(null);
      }
    } catch (err) {
      console.error('Failed to save summary:', err);
      toast.error('Failed to save summary');
    } finally {
      setIsSaving(false);
    }
  };

  const handleStartEdit = () => {
    // Convert current sections to editable JSON string
    if (sections) {
      setEditedSummary(JSON.stringify(sections, null, 2));
    } else if (rawFallback) {
      setEditedSummary(rawFallback);
    } else {
      setEditedSummary('');
    }
    setIsEditing(true);
  };

  const renderMarkdownBullets = (text) => {
    if (!text) return null;
    const lines = String(text).split('\n').map(l => l.trim()).filter(Boolean);
    const bullets = [];
    const paragraphs = [];
    lines.forEach((line) => {
      if (/^[-*•]\s+/.test(line)) {
        bullets.push(line.replace(/^[-*•]\s+/, ''));
      } else {
        paragraphs.push(line);
      }
    });
    return (
      <>
        {paragraphs.length > 0 && (
          <p className="text-sm text-gray-700 leading-relaxed">{paragraphs.join(' ')}</p>
        )}
        {bullets.length > 0 && (
          <ul className="list-none space-y-1.5 text-sm text-gray-700">
            {bullets.map((b, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-current opacity-60 mt-1.5 shrink-0">•</span>
                <span className="flex-1 leading-relaxed">{b.replace(/\*\*(.*?)\*\*/g, '$1')}</span>
              </li>
            ))}
          </ul>
        )}
      </>
    );
  };

  const SectionBox = ({ icon: Icon, title, colorClasses, children }) => (
    <div className={`rounded-lg border ${colorClasses.border} ${colorClasses.bg} overflow-hidden flex flex-col`}>
      <div className={`px-4 py-2.5 border-b ${colorClasses.border} ${colorClasses.headerBg} flex items-center gap-2`}>
        <Icon className={`w-4 h-4 ${colorClasses.icon}`} />
        <h4 className={`text-sm font-bold ${colorClasses.title} uppercase tracking-wide`}>{title}</h4>
      </div>
      <div className="p-4 flex-1">{children}</div>
    </div>
  );

  // Render loading / error / empty states at the top-level wrapper
  const wrapperClass = "bg-white rounded-lg border border-gray-200 p-4";

  if (error) {
    return (
      <div className={wrapperClass}>
        <div className="flex items-center justify-between mb-3">
          <div className="text-red-600 text-sm">{error}</div>
          <Button variant="outline" size="sm" onClick={generateSummary} disabled={isLoading}>
            <RefreshCw className={`w-4 h-4 mr-1 ${isLoading ? 'animate-spin' : ''}`} />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  if (isLoading && !sections && !rawFallback) {
    return (
      <div className={wrapperClass}>
        <div className="flex items-center gap-2 text-indigo-600 py-8 justify-center">
          <Bot className="w-5 h-5 animate-pulse" />
          <span className="text-sm font-medium">Generating client status summary…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Report Period Dates - Prominent Display */}
      {periodInfo?.start && periodInfo?.end && (
        <div className="bg-gradient-to-r from-[#1B2A47] to-[#4A9CC7] text-white px-6 py-3 rounded-lg">
          <div className="text-sm font-medium opacity-90">Report Period</div>
          <div className="text-lg font-bold">
            {format(periodInfo.start, 'MMM d, yyyy')} - {format(periodInfo.end, 'MMM d, yyyy')}
          </div>
        </div>
      )}

      {/* Edit Mode */}
      {isEditing ? (
        <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-gray-900">Edit AI Summary</h4>
            <div className="flex gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsEditing(false)}
                disabled={isSaving}
                className="text-gray-600 hover:text-gray-900"
                data-testid="cancel-edit-summary"
              >
                <X className="w-4 h-4 mr-1" />
                Cancel
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handleSaveSummary}
                disabled={isSaving}
                className="bg-[#4A9CC7] hover:bg-[#3a8cb7] text-white"
                data-testid="save-summary"
              >
                <Save className={`w-4 h-4 mr-1 ${isSaving ? 'animate-pulse' : ''}`} />
                {isSaving ? 'Saving...' : 'Save'}
              </Button>
            </div>
          </div>
          <Textarea
            value={editedSummary}
            onChange={(e) => setEditedSummary(e.target.value)}
            className="min-h-[300px] font-mono text-xs"
            placeholder="Edit summary as JSON or plain text..."
            data-testid="edit-summary-textarea"
          />
          <p className="text-xs text-gray-500">
            💡 Tip: Keep the JSON structure for best display, or use plain text for simple summaries.
          </p>
        </div>
      ) : (
        <>
          {/* Refresh and Edit controls */}
          <div className="flex items-center justify-between">
            <div className="text-xs text-gray-500">
              Reporting period: <span className="font-medium text-gray-700">{periodInfo?.label || '—'}</span>
            </div>
            <div className="flex gap-2 no-print">
              {isAdmin && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleStartEdit}
                  className="text-amber-600 hover:text-amber-700 hover:bg-amber-50"
                  data-testid="edit-summary-btn"
                >
                  <Edit2 className="w-4 h-4 mr-1" />
                  Edit
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={generateSummary}
                disabled={isLoading}
                className="text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50"
                data-testid="refresh-summary-btn"
              >
                <RefreshCw className={`w-4 h-4 mr-1 ${isLoading ? 'animate-spin' : ''}`} />
                {isLoading ? 'Refreshing…' : 'Refresh'}
              </Button>
            </div>
          </div>

          {rawFallback && !sections ? (
            <div className={wrapperClass}>
              <p className="text-xs text-amber-600 mb-2">Could not parse structured summary — showing raw response:</p>
              <div className="text-sm text-gray-700 whitespace-pre-wrap">{rawFallback}</div>
            </div>
          ) : sections ? (
            <div className="space-y-3">
              {/* Executive Summary — full width */}
              <SectionBox
                icon={Sparkles}
                title="Executive Summary"
                colorClasses={{
                  border: 'border-[#4A9CC7]/30',
                  bg: 'bg-[#F0F4F8]',
                  headerBg: 'bg-[#1B2A47]',
                  icon: 'text-[#4A9CC7]',
                  title: 'text-white',
                }}
              >
                {renderMarkdownBullets(sections.executive_summary)}
              </SectionBox>

              {/* Project Objective — full width */}
              <SectionBox
                icon={Target}
                title="Project Objective"
                colorClasses={{
                  border: 'border-[#C9A84C]/40',
                  bg: 'bg-[#FDFBF5]',
                  headerBg: 'bg-[#C9A84C]/20',
                  icon: 'text-[#C9A84C]',
                  title: 'text-[#1B2A47]',
                }}
              >
                {renderMarkdownBullets(sections.project_objective)}
              </SectionBox>

              {/* Achievements + Focus of Next Period — side by side */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <SectionBox
                  icon={CheckCircle2}
                  title="Achievements This Period"
                  colorClasses={{
                    border: 'border-emerald-200',
                    bg: 'bg-emerald-50/40',
                    headerBg: 'bg-emerald-100/70',
                    icon: 'text-emerald-600',
                    title: 'text-emerald-900',
                  }}
                >
                  {renderMarkdownBullets(sections.achievements)}
                </SectionBox>

                <SectionBox
                  icon={ArrowRight}
                  title="Focus of Next Period"
                  colorClasses={{
                    border: 'border-amber-200',
                    bg: 'bg-amber-50/40',
                    headerBg: 'bg-amber-100/70',
                    icon: 'text-amber-600',
                    title: 'text-amber-900',
                  }}
                >
                  {renderMarkdownBullets(sections.next_period_focus)}
                </SectionBox>
              </div>
            </div>
          ) : null}

          <div className="text-[10px] text-gray-400 text-right">
            Generated by DD Planner AI • {format(new Date(), 'MMM d, yyyy h:mm a')}
          </div>
        </>
      )}
    </div>
  );
};

const ProjectReport = ({ printMode: printModeProp = false, wbsOnly: wbsOnlyProp = false } = {}) => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [showFilterDialog, setShowFilterDialog] = useState(false);
  // In print mode default to whole-project (no dialog)
  const [reportPeriod, setReportPeriod] = useState(
    searchParams.get('period') || (printModeProp ? 'whole-project' : 'whole-project')
  );
  const [exporting, setExporting] = useState(null); // 'pdf' | 'pptx' | null
  const [showMagicLinkDialog, setShowMagicLinkDialog] = useState(false);
  const [magicLinkEmail, setMagicLinkEmail] = useState('');
  const [magicLinkLoading, setMagicLinkLoading] = useState(false);
  const [generatedLink, setGeneratedLink] = useState(null);
  const [linkCopied, setLinkCopied] = useState(false);
  const isClientMode = searchParams.get('client') === 'true';
  // Print/export mode flags — also read from URL so the component works when used
  // directly under a route that doesn't pass props.
  const printMode = printModeProp || searchParams.get('print') === '1';
  const wbsOnly = wbsOnlyProp || searchParams.get('view') === 'wbs';

  // Show filter dialog on mount if no period is set (NOT in print mode)
  useEffect(() => {
    if (!printMode && !searchParams.get('period')) {
      setShowFilterDialog(true);
    }
  }, [searchParams, printMode]);

  // Fetch project data
  const { data: project, isLoading } = useQuery({
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

  const { data: statusUpdates } = useQuery({
    queryKey: ['projectStatusUpdates', id],
    queryFn: async () => {
      const response = await getProjectStatusUpdates(id, 5);
      return response.data;
    },
    enabled: !!id,
  });

  const { data: timeReport } = useQuery({
    queryKey: ['projectTimeReport', id],
    queryFn: async () => {
      const response = await getProjectTimeReport(id);
      return response.data;
    },
    enabled: !!id,
  });

  // Calculate period dates
  const periodInfo = useMemo(() => {
    if (!project) return null;
    const today = new Date();
    
    switch (reportPeriod) {
      case 'this-week':
        return {
          label: 'This Week',
          start: startOfWeek(today, { weekStartsOn: 1 }),
          end: addDays(startOfWeek(today, { weekStartsOn: 1 }), 4), // Friday (business days only)
        };
      case 'last-fortnight':
        return {
          label: 'Last Fortnight',
          start: subDays(today, 14),
          end: today,
        };
      case 'current-phase': {
        const currentPhase = project.phases?.find(p => p.status === 'In Progress');
        if (currentPhase) {
          return {
            label: `Current Phase: ${currentPhase.name}`,
            start: currentPhase.start_date ? parseISO(currentPhase.start_date) : null,
            end: currentPhase.end_date ? parseISO(currentPhase.end_date) : null,
          };
        }
        return {
          label: 'No Active Phase',
          start: null,
          end: null,
        };
      }
      case 'whole-project':
      default:
        return {
          label: 'Whole Project',
          start: project.start_date ? parseISO(project.start_date) : null,
          end: project.end_date ? parseISO(project.end_date) : null,
        };
    }
  }, [project, reportPeriod]);

  // Filter status updates for the selected period
  const periodStatusUpdates = useMemo(() => {
    if (!statusUpdates || !periodInfo?.start || !periodInfo?.end) return statusUpdates || [];
    
    return statusUpdates.filter(update => {
      const updateDate = parseISO(update.week_start_date);
      return isWithinInterval(updateDate, { start: periodInfo.start, end: periodInfo.end });
    });
  }, [statusUpdates, periodInfo]);

  // Get latest status update
  const latestStatusUpdate = statusUpdates?.[0];

  // Calculate progress using BUSINESS DAYS
  const progress = useMemo(() => {
    if (!project?.start_date || !project?.end_date) return 0;
    const start = parseISO(project.start_date);
    const end = parseISO(project.end_date);
    const today = new Date();
    
    if (today < start) return 0;
    if (today > end) return 100;
    
    // Use business days for progress calculation
    const totalBusinessDays = countBusinessDays(start, end);
    const elapsedBusinessDays = countBusinessDays(start, today);
    return Math.round((elapsedBusinessDays / totalBusinessDays) * 100);
  }, [project]);

  const handleApplyFilter = () => {
    setShowFilterDialog(false);
    navigate(`/projects/${id}/report?period=${reportPeriod}`, { replace: true });
  };

  const handlePrint = () => {
    window.print();
  };

  const safeFileName = () => {
    const name = (project?.name || 'project').replace(/[^a-z0-9-]+/gi, '-').replace(/^-|-$/g, '');
    return `${name}-Report-${format(new Date(), 'yyyy-MM-dd')}`;
  };

  const downloadBlob = (blob, filename) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const exportToPDF = async () => {
    setExporting('pdf');
    try {
      const res = await exportProjectPDF(id);
      const filename = `${safeFileName()}.pdf`;
      downloadBlob(res.data, filename);
      toast.success('PDF exported successfully');
    } catch (err) {
      console.error('PDF export failed:', err);
      toast.error(`PDF export failed: ${err?.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setExporting(null);
    }
  };

  const exportToPPTX = async () => {
    setExporting('pptx');
    try {
      const res = await exportProjectPPT(id);
      const filename = `${safeFileName()}.pptx`;
      downloadBlob(res.data, filename);
      toast.success('PPTX exported — 2 slides');
    } catch (err) {
      console.error('PPTX export failed:', err);
      toast.error(`PPTX export failed: ${err?.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setExporting(null);
    }
  };

  const exportWBSToPDF = async () => {
    setExporting('wbs-pdf');
    try {
      const res = await exportProjectWBSPDF(id);
      const filename = `${safeFileName()}-WBS.pdf`;
      downloadBlob(res.data, filename);
      toast.success('WBS PDF exported successfully');
    } catch (err) {
      console.error('WBS PDF export failed:', err);
      toast.error(`WBS PDF export failed: ${err?.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setExporting(null);
    }
  };

  const exportWBSToPPTX = async () => {
    setExporting('wbs-pptx');
    try {
      const res = await exportProjectWBSPPT(id);
      const filename = `${safeFileName()}-WBS.pptx`;
      downloadBlob(res.data, filename);
      toast.success('WBS PPTX exported successfully');
    } catch (err) {
      console.error('WBS PPTX export failed:', err);
      toast.error(`WBS PPTX export failed: ${err?.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setExporting(null);
    }
  };

  const handleGenerateMagicLink = async () => {
    if (!magicLinkEmail || !magicLinkEmail.includes('@')) {
      toast.error('Please enter a valid email address');
      return;
    }

    setMagicLinkLoading(true);
    try {
      const response = await fetch('/api/reports/magic-link', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          project_id: id,
          recipient_email: magicLinkEmail,
          report_type: 'project_status',
          report_period: reportPeriod
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to generate link');
      }

      const data = await response.json();
      setGeneratedLink(data.magic_link);
      toast.success(`Magic link sent to ${magicLinkEmail}`);
    } catch (err) {
      console.error('Magic link generation failed:', err);
      toast.error(err.message || 'Failed to generate magic link');
    } finally {
      setMagicLinkLoading(false);
    }
  };

  const handleCopyLink = () => {
    if (generatedLink) {
      navigator.clipboard.writeText(generatedLink);
      setLinkCopied(true);
      toast.success('Link copied to clipboard!');
      setTimeout(() => setLinkCopied(false), 2000);
    }
  };

  const handleCloseMagicLinkDialog = () => {
    setShowMagicLinkDialog(false);
    setMagicLinkEmail('');
    setGeneratedLink(null);
    setLinkCopied(false);
  };


  if (isLoading || !project || !periodInfo) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="text-lg font-medium text-gray-600">Loading report...</div>
        </div>
      </div>
    );
  }

  const getHealthColor = (health) => {
    switch (health?.toLowerCase()) {
      case 'green': return 'bg-emerald-500';
      case 'amber': return 'bg-amber-500';
      case 'red': return 'bg-red-500';
      default: return 'bg-gray-400';
    }
  };

  const getHealthTextColor = (health) => {
    switch (health?.toLowerCase()) {
      case 'green': return 'text-emerald-600';
      case 'amber': return 'text-amber-600';
      case 'red': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  // Signal to Playwright that all data is ready & rendered
  // Only true once project + (timeReport OR no time tracking) + risks + allocations are all settled
  const isExportReady = !isLoading && !!project && !!periodInfo && (timeReport !== undefined) && (risks !== undefined) && (allocations !== undefined);

  // ============================================================
  // WBS-only render path (used by /print routes for WBS exports)
  // ============================================================
  if (wbsOnly) {
    if (isLoading || !project) {
      return (
        <div className="flex items-center justify-center min-h-screen bg-white">
          <div className="text-lg font-medium text-gray-600">Loading WBS...</div>
        </div>
      );
    }
    return (
      <div
        className={printMode ? "bg-white" : "min-h-screen bg-gray-50"}
        data-export-ready={isExportReady ? "true" : "false"}
      >
        <div className="max-w-[1600px] mx-auto px-6 py-6 bg-white">
          {/* Header */}
          <div className="border-b-4 border-[#1B2A47] pb-4 mb-6">
            <div className="flex items-start justify-between">
              <DDConsultingLogo />
              <div className="text-right text-sm text-gray-500">
                <div>Generated: {format(new Date(), 'MMM d, yyyy')}</div>
                <div className="font-medium text-gray-700">Work Breakdown Structure</div>
              </div>
            </div>
            <div className="mt-4">
              <h1 className="text-3xl font-bold text-gray-900">{project.name}</h1>
              <div className="text-sm text-gray-600 mt-1">
                <span className="font-medium">Client:</span> {project.client_name}
                <span className="mx-2">•</span>
                <span className="font-medium">Status:</span> {project.status}
              </div>
            </div>
          </div>

          {/* WBS body */}
          <div data-export-section="wbs">
            <WBSView projectId={id} project={project} phases={project.phases} resources={[]} readOnly={printMode} defaultView="plan" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={printMode ? "bg-white" : "min-h-screen bg-gray-50"}
      data-export-ready={isExportReady ? "true" : "false"}
    >
      {/* Filter Dialog */}
      <Dialog open={showFilterDialog && !printMode} onOpenChange={setShowFilterDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Select Report Period</DialogTitle>
            <DialogDescription>
              Choose the time period for this project report
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <RadioGroup value={reportPeriod} onValueChange={setReportPeriod}>
              <div className="flex items-center space-x-2 p-3 rounded-lg border hover:bg-gray-50 cursor-pointer">
                <RadioGroupItem value="whole-project" id="whole" />
                <Label htmlFor="whole" className="cursor-pointer flex-1">
                  <div className="font-medium">Whole Project</div>
                  <div className="text-sm text-gray-500">Complete project overview</div>
                </Label>
              </div>
              
              <div className="flex items-center space-x-2 p-3 rounded-lg border hover:bg-gray-50 cursor-pointer">
                <RadioGroupItem value="current-phase" id="phase" />
                <Label htmlFor="phase" className="cursor-pointer flex-1">
                  <div className="font-medium">Current Phase</div>
                  <div className="text-sm text-gray-500">Focus on active phase only</div>
                </Label>
              </div>
              
              <div className="flex items-center space-x-2 p-3 rounded-lg border hover:bg-gray-50 cursor-pointer">
                <RadioGroupItem value="last-fortnight" id="fortnight" />
                <Label htmlFor="fortnight" className="cursor-pointer flex-1">
                  <div className="font-medium">Last Fortnight</div>
                  <div className="text-sm text-gray-500">Last 14 days of activity</div>
                </Label>
              </div>
              
              <div className="flex items-center space-x-2 p-3 rounded-lg border hover:bg-gray-50 cursor-pointer">
                <RadioGroupItem value="this-week" id="week" />
                <Label htmlFor="week" className="cursor-pointer flex-1">
                  <div className="font-medium">This Week</div>
                  <div className="text-sm text-gray-500">Current week only</div>
                </Label>
              </div>
            </RadioGroup>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => navigate(-1)}>Cancel</Button>
            <Button onClick={handleApplyFilter}>Generate Report</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Action Bar - Hidden on print */}
      {!printMode && (
      <div className="no-print bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <Button 
              variant="ghost" 
              onClick={() => navigate(-1)}
              className="gap-2"
            >
              <ArrowLeft size={16} />
              Back to Project
            </Button>
            <div className="flex gap-2">
              <Button 
                variant="outline" 
                onClick={() => setShowFilterDialog(true)}
                className="gap-2"
                data-testid="change-period-btn"
              >
                <Calendar size={16} />
                Change Period
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button className="gap-2" disabled={!!exporting} data-testid="export-report-btn">
                    {exporting ? (
                      <>
                        <Loader2 size={16} className="animate-spin" />
                        Exporting {exporting.replace('wbs-', 'WBS ').toUpperCase()}...
                      </>
                    ) : (
                      <>
                        <Download size={16} />
                        Export
                      </>
                    )}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-60">
                  <DropdownMenuItem onClick={exportToPDF} disabled={!!exporting} data-testid="export-pdf-item">
                    <FileText size={16} className="mr-2 text-red-600" />
                    <div className="flex flex-col">
                      <span className="font-medium">Export as PDF</span>
                      <span className="text-xs text-gray-500">DD-branded • landscape A4 • 1 page</span>
                    </div>
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={exportToPPTX} disabled={!!exporting} data-testid="export-pptx-item">
                    <Presentation size={16} className="mr-2 text-orange-600" />
                    <div className="flex flex-col">
                      <span className="font-medium">Export as PPTX</span>
                      <span className="text-xs text-gray-500">DD-branded • 2 slides • 16:9</span>
                    </div>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={exportWBSToPDF} disabled={!!exporting} data-testid="export-wbs-pdf-item">
                    <FileText size={16} className="mr-2 text-blue-600" />
                    <div className="flex flex-col">
                      <span className="font-medium">Export WBS as PDF</span>
                      <span className="text-xs text-gray-500">Work Breakdown Structure • hierarchy</span>
                    </div>
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={exportWBSToPPTX} disabled={!!exporting} data-testid="export-wbs-pptx-item">
                    <Presentation size={16} className="mr-2 text-blue-600" />
                    <div className="flex flex-col">
                      <span className="font-medium">Export WBS as PPTX</span>
                      <span className="text-xs text-gray-500">Work Breakdown Structure • 16:9</span>
                    </div>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => setShowMagicLinkDialog(true)} disabled={!!exporting} data-testid="generate-magic-link-item">
                    <Mail size={16} className="mr-2 text-purple-600" />
                    <div className="flex flex-col">
                      <span className="font-medium">Generate Magic Link</span>
                      <span className="text-xs text-gray-500">Secure 30-day client access</span>
                    </div>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handlePrint} disabled={!!exporting} data-testid="print-report-item">
                    <Printer size={16} className="mr-2 text-gray-600" />
                    <span className="font-medium">Print</span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </div>
      </div>
      )}

      {/* Report Content */}
      <div id="report-root" className={`mx-auto px-6 py-8 bg-white ${printMode ? 'max-w-[1600px] my-0 shadow-none' : 'max-w-7xl my-8 shadow-sm rounded-lg'} print:shadow-none print:my-0`}>
        {/* Header with Logo */}
        <div id="report-header" className="border-b-4 border-[#1B2A47] pb-6 mb-8">
          <div className="flex items-start justify-between mb-6">
            <DDConsultingLogo />
            <div className="text-right text-sm text-gray-500">
              <div>Generated: {format(new Date(), 'MMM d, yyyy')}</div>
              <div>Period: {periodInfo.label}</div>
            </div>
          </div>
          <div className="flex items-start justify-between mt-6">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <h1 className="text-4xl font-bold text-gray-900">{project.name}</h1>
                {isClientMode && (
                  <Badge className="bg-[#4A9CC7] text-white" data-testid="client-view-badge">
                    Client View
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <span className="font-medium">Client: {project.client_name}</span>
                <span>•</span>
                <span>Status: <Badge variant="outline">{project.status}</Badge></span>
              </div>
            </div>
            {latestStatusUpdate && (
              <div className="text-right">
                <div className="flex items-center justify-end gap-2 mb-1">
                  <span className="text-sm text-gray-600">Health Status:</span>
                  <div className={`w-3 h-3 rounded-full ${getHealthColor(latestStatusUpdate.health)}`} />
                  <span className={`font-bold text-lg ${getHealthTextColor(latestStatusUpdate.health)}`}>
                    {latestStatusUpdate.health}
                  </span>
                </div>
                <Badge variant="outline" className="text-xs">
                  {latestStatusUpdate.schedule_status}
                </Badge>
              </div>
            )}
          </div>
        </div>

        {/* Client Status Summary — shown FIRST */}
        <div id="report-body">
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-4 flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-[#4A9CC7]" />
            Status Summary
          </h2>
          <AIStatusSummary 
            project={project} 
            periodInfo={periodInfo}
            statusUpdates={periodStatusUpdates}
            risks={risks}
          />
        </div>

        {/* Project Gantt Chart — shown SECOND */}
        <div id="report-gantt" className="mb-8" data-export-section="timeline">
          <h2 className="text-2xl font-bold text-gray-900 mb-4 flex items-center gap-2">
            <Calendar className="h-6 w-6 text-[#4A9CC7]" />
            Project Timeline & Phases
          </h2>
          <div id="report-gantt-inner">
            <ProjectGanttChart project={project} phases={project.phases} />
          </div>
        </div>

        {/* Project Overview */}
        <div className="mb-8" data-export-section="overview">
          <h2 className="text-2xl font-bold text-gray-900 mb-4 flex items-center gap-2">
            <TrendingUp className="h-6 w-6 text-gray-600" />
            Project Overview
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-[#E8EDF2] rounded-lg border border-[#4A9CC7]/30">
              <div className="text-sm text-[#4A9CC7] font-medium mb-1">Status</div>
              <div className="text-xl font-bold text-[#1B2A47]">{project.status}</div>
            </div>
            <div className="p-4 bg-green-50 rounded-lg border border-green-200">
              <div className="text-sm text-green-600 font-medium mb-1">Progress</div>
              <div className="text-xl font-bold text-green-900">{progress}%</div>
            </div>
            <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
              <div className="text-sm text-purple-600 font-medium mb-1">Start Date</div>
              <div className="text-xl font-bold text-purple-900">
                {project.start_date ? format(parseISO(project.start_date), 'MMM d, yyyy') : 'TBD'}
              </div>
            </div>
            <div className="p-4 bg-orange-50 rounded-lg border border-orange-200">
              <div className="text-sm text-orange-600 font-medium mb-1">End Date</div>
              <div className="text-xl font-bold text-orange-900">
                {project.end_date ? format(parseISO(project.end_date), 'MMM d, yyyy') : 'TBD'}
              </div>
            </div>
          </div>
        </div>

        {/* Budget & Time Tracking */}
        {timeReport && (
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-gray-900 mb-4 flex items-center gap-2">
              <Clock className="h-6 w-6 text-gray-600" />
              Budget & Time Tracking
            </h2>
            
            {/* Summary Cards */}
            <div className={`grid ${isClientMode ? 'grid-cols-2' : 'grid-cols-4'} gap-4 mb-6`}>
              <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                <div className="text-sm text-gray-600 font-medium mb-1">Budgeted Hours</div>
                <div className="text-2xl font-bold text-gray-900">
                  {timeReport.project?.budgeted_hours || '-'}h
                </div>
              </div>
              {!isClientMode && (
                <div className="p-4 bg-[#E8EDF2] rounded-lg border border-[#4A9CC7]/30">
                  <div className="text-sm text-[#4A9CC7] font-medium mb-1">Allocated Hours</div>
                  <div className="text-xl font-bold text-[#1B2A47]">{timeReport.project?.planned_hours}h</div>
                </div>
              )}
              <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                <div className="text-sm text-green-600 font-medium mb-1">Actual Hours</div>
                <div className="text-2xl font-bold text-green-900">{timeReport.project?.actual_hours}h</div>
              </div>
              {!isClientMode && (
              <div className={`p-4 rounded-lg border ${
                (timeReport.project?.budgeted_hours ? timeReport.project?.budget_variance : timeReport.project?.variance_hours) > 0 
                  ? 'bg-red-50 border-red-200' 
                  : 'bg-green-50 border-green-200'
              }`}>
                <div className={`text-sm font-medium mb-1 ${
                  (timeReport.project?.budgeted_hours ? timeReport.project?.budget_variance : timeReport.project?.variance_hours) > 0 
                    ? 'text-red-600' 
                    : 'text-green-600'
                }`}>Variance</div>
                <div className={`text-2xl font-bold ${
                  (timeReport.project?.budgeted_hours ? timeReport.project?.budget_variance : timeReport.project?.variance_hours) > 0 
                    ? 'text-red-900' 
                    : 'text-green-900'
                }`}>
                  {(timeReport.project?.budgeted_hours ? timeReport.project?.budget_variance : timeReport.project?.variance_hours) > 0 ? '+' : ''}
                  {timeReport.project?.budgeted_hours ? timeReport.project?.budget_variance : timeReport.project?.variance_hours}h
                </div>
              </div>
              )}
            </div>

            {/* Phase Breakdown removed — see Budget Reconciliation panel on the Overview tab */}
          </div>
        )}

        {/* Risks & Issues Section — Enhanced visual matching Project Detail */}
        {risks && risks.filter(r => (r.status || 'Active') !== 'Closed').length > 0 && (
          <div className="mb-8" data-print-section="risks">
            <h2 className="text-2xl font-bold text-gray-900 mb-4 flex items-center gap-2">
              <AlertTriangle className="h-6 w-6 text-amber-600" />
              Risks & Issues
            </h2>
            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden divide-y divide-gray-100">
              {(() => {
                const statusOrder = { Active: 0, Mitigated: 1, Accepted: 2, Closed: 3 };
                const impactOrder = { Critical: 0, High: 1, Medium: 2, Low: 3 };
                return [...risks]
                  .filter(r => (r.status || 'Active') !== 'Closed')
                  .sort((a, b) => {
                    const sA = statusOrder[a.status || 'Active'] ?? 4;
                    const sB = statusOrder[b.status || 'Active'] ?? 4;
                    if (sA !== sB) return sA - sB;
                    return (impactOrder[a.impact || 'Medium'] ?? 4) - (impactOrder[b.impact || 'Medium'] ?? 4);
                  })
                  .map((risk, idx) => {
                    const status = risk.status || 'Active';
                    const category = risk.category || 'Risk';
                    const statusConfig = {
                      Active: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-300', borderLeft: 'border-l-4 border-l-red-500', icon: '🔴' },
                      Mitigated: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-300', borderLeft: 'border-l-4 border-l-amber-500', icon: '🟡' },
                      Accepted: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-300', borderLeft: 'border-l-4 border-l-blue-500', icon: '🔵' },
                      Closed: { bg: 'bg-gray-100', text: 'text-gray-500', border: 'border-gray-300', borderLeft: 'border-l-4 border-l-gray-400', icon: '⚪' },
                    };
                    const sc = statusConfig[status] || statusConfig.Closed;
                    const impactColor = risk.impact === 'Critical' ? 'bg-red-600' : risk.impact === 'High' ? 'bg-orange-500' : risk.impact === 'Medium' ? 'bg-amber-500' : 'bg-yellow-400';
                    
                    return (
                      <div key={idx} data-print-keep className={`p-4 ${sc.borderLeft}`}>
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1 min-w-0">
                            {/* Badges row */}
                            <div className="flex items-center gap-2 flex-wrap mb-2">
                              <Badge variant="outline" className={`text-xs font-bold px-2.5 py-0.5 border-2 ${sc.bg} ${sc.text} ${sc.border}`}>
                                <span className="mr-1">{sc.icon}</span>
                                {status.toUpperCase()}
                              </Badge>
                              <Badge variant="outline" className={`text-xs font-semibold px-2 py-0.5 ${category === 'Issue' ? 'bg-red-50 text-red-700 border-red-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
                                {category.toUpperCase()}
                              </Badge>
                              <Badge className={`${impactColor} text-white text-xs px-2 py-0.5`}>
                                {risk.impact} Impact
                              </Badge>
                              <Badge variant="outline" className="text-xs px-2 py-0.5">
                                {risk.probability} Prob.
                              </Badge>
                              {Array.isArray(risk.impact_areas) && risk.impact_areas.map((area) => (
                                <Badge
                                  key={area}
                                  variant="outline"
                                  className={`text-[10px] px-1.5 py-0 ${
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
                            {/* Description */}
                            <p className="text-sm font-medium text-gray-900 leading-snug">{risk.description}</p>
                            {/* Mitigation */}
                            {risk.mitigation && (
                              <div className="mt-2 p-2 rounded bg-gray-50 border border-gray-200 text-xs text-gray-600">
                                <span className="font-semibold text-gray-800">Mitigation:</span> {risk.mitigation}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  });
              })()}
            </div>
          </div>
        )}

        {/* Team Allocations section removed per user request — see Team tab on Project Detail for staffing info */}

        {/* Footer */}
        <div className="report-footer mt-12 pt-6 border-t border-gray-200 text-center text-sm text-gray-500">
          <DDConsultingLogo className="justify-center mb-4" />
          <p>This report was generated by DD Planner on {format(new Date(), 'MMMM d, yyyy \'at\' h:mm a')}</p>
          <p className="text-xs mt-1">Confidential - For internal use only</p>
        </div>
        </div>{/* end #report-body */}
      </div>

      {/* Magic Link Dialog */}
      <Dialog open={showMagicLinkDialog} onOpenChange={handleCloseMagicLinkDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Mail className="w-5 h-5 text-purple-600" />
              Generate Magic Link
            </DialogTitle>
            <DialogDescription>
              Create a secure, time-limited link for client access to this report.
            </DialogDescription>
          </DialogHeader>
          
          {!generatedLink ? (
            <div className="space-y-4 py-4">
              <div>
                <Label htmlFor="recipient-email">Recipient Email Address</Label>
                <Input
                  id="recipient-email"
                  type="email"
                  placeholder="client@example.com"
                  value={magicLinkEmail}
                  onChange={(e) => setMagicLinkEmail(e.target.value)}
                  className="mt-2"
                  autoFocus
                />
              </div>
              
              <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                <div className="flex items-start gap-2 text-sm text-blue-900">
                  <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
                  <div>
                    <p className="font-medium mb-1">Secure Access</p>
                    <ul className="text-xs space-y-1 text-blue-700">
                      <li>• Valid for 30 days</li>
                      <li>• Requires email verification (6-digit code)</li>
                      <li>• View count tracking</li>
                      <li>• Can be revoked anytime</li>
                    </ul>
                  </div>
                </div>
              </div>

              <Button 
                onClick={handleGenerateMagicLink}
                disabled={magicLinkLoading || !magicLinkEmail}
                className="w-full"
              >
                {magicLinkLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Generating Link...
                  </>
                ) : (
                  <>
                    <Mail className="w-4 h-4 mr-2" />
                    Generate & Send Link
                  </>
                )}
              </Button>
            </div>
          ) : (
            <div className="space-y-4 py-4">
              <div className="bg-green-50 p-4 rounded-lg border border-green-200">
                <div className="flex items-center gap-2 text-sm text-green-900 mb-3">
                  <CheckCheck className="w-5 h-5" />
                  <span className="font-medium">Link Generated Successfully!</span>
                </div>
                <p className="text-xs text-green-700">
                  A verification code and magic link have been sent to <strong>{magicLinkEmail}</strong>
                </p>
              </div>

              <div>
                <Label>Secure Link</Label>
                <div className="flex gap-2 mt-2">
                  <Input
                    value={generatedLink}
                    readOnly
                    className="font-mono text-xs"
                  />
                  <Button
                    onClick={handleCopyLink}
                    variant="outline"
                    size="icon"
                    className="shrink-0"
                  >
                    {linkCopied ? (
                      <CheckCheck className="w-4 h-4 text-green-600" />
                    ) : (
                      <Copy className="w-4 h-4" />
                    )}
                  </Button>
                </div>
              </div>

              <Button onClick={handleCloseMagicLinkDialog} className="w-full" variant="outline">
                Close
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ProjectReport;
