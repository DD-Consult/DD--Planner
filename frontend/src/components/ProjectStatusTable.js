import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { format, parseISO, isWithinInterval } from 'date-fns';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from './ui/table';
import { Badge } from './ui/badge';
import { Avatar, AvatarImage, AvatarFallback } from './ui/avatar';
import { Progress } from './ui/progress';
import { Button } from './ui/button';
import { ChevronUp, ChevronDown, Crown, ExternalLink, Edit, Trash2, Bell } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from './ui/tooltip';

/**
 * Shared rich project row used by Dashboard + Projects page.
 * Columns: Project / Lead / Current Phase / Team / Health / Progress (+ Actions for admin)
 *
 * Use this to keep the two views identical.
 */
export const enrichProjects = (projects, allocations, resources) => {
  if (!projects) return [];
  const today = new Date();
  return projects.map(project => {
    const projectAllocations = (allocations || []).filter(a => a.project_id === project.id);
    const uniqueResourceIds = [...new Set(projectAllocations.map(a => a.resource_id))];
    const teamMembers = uniqueResourceIds
      .map(rid => (resources || []).find(r => r.id === rid))
      .filter(Boolean);

    let currentPhase = null;
    if (project.phases?.length > 0) {
      currentPhase = project.phases.find(phase => {
        try {
          return isWithinInterval(today, { start: parseISO(phase.start_date), end: parseISO(phase.end_date) });
        } catch { return false; }
      });
    }

    let timeBasedProgress = 0;
    try {
      const projectStart = parseISO(project.start_date);
      const projectEnd = parseISO(project.end_date);
      const totalDays = Math.max(1, Math.floor((projectEnd - projectStart) / (1000 * 60 * 60 * 24)));
      const elapsedDays = Math.max(0, Math.floor((today - projectStart) / (1000 * 60 * 60 * 24)));
      timeBasedProgress = Math.min(100, Math.max(0, Math.round((elapsedDays / totalDays) * 100)));
    } catch { /* noop */ }

    const progress = project.actual_progress != null ? project.actual_progress : timeBasedProgress;
    let health = project.health || 'Green';
    if (!project.health) {
      if (project.status === 'Pipeline') health = 'Amber';
      if (timeBasedProgress > 80 && project.status === 'Active') health = 'Amber';
    }

    return {
      ...project,
      teamMembers,
      currentPhase: currentPhase?.name || 'N/A',
      health,
      progress,
      scheduleStatus: project.schedule_status || null,
    };
  });
};

const getHealthColor = (health) => ({
  Green: 'bg-[#16B364] text-white',
  Amber: 'bg-[#F4B740] text-white',
  Red:   'bg-[#EF4444] text-white',
}[health] || 'bg-[#667085] text-white');

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


/**
 * The rich table — exactly the same on Dashboard and Projects pages.
 */
export const ProjectRichTable = ({ projects, isAdmin = false, onEdit, onDelete }) => {
  const navigate = useNavigate();
  const handleClick = (pid) => navigate(`/projects/${pid}`);
  return (
    <Table>
      <TableHeader>
        <TableRow className="bg-[#F8FAFC]">
          <TableHead className="font-semibold text-[#0B1220]">Project</TableHead>
          <TableHead className="font-semibold text-[#0B1220]">Lead</TableHead>
          <TableHead className="font-semibold text-[#0B1220]">Current Phase</TableHead>
          <TableHead className="font-semibold text-[#0B1220]">Team</TableHead>
          <TableHead className="font-semibold text-[#0B1220]">Health</TableHead>
          <TableHead className="font-semibold text-[#0B1220]">Progress</TableHead>
          {isAdmin && <TableHead className="text-right font-semibold text-[#0B1220]">Actions</TableHead>}
        </TableRow>
      </TableHeader>
      <TableBody>
        {projects.map((project) => (
          <TableRow
            key={project.id}
            onClick={() => handleClick(project.id)}
            className={`cursor-pointer hover:bg-[#F8FAFC] transition-colors border-b border-[#E6E8EC] ${
              project.is_draft
                ? 'border-dashed opacity-70 bg-[repeating-linear-gradient(45deg,transparent,transparent_10px,#FFF8E5_10px,#FFF8E5_20px)]'
                : ''
            }`}
            data-testid={`project-row-${project.id}`}
          >
            <TableCell>
              <div>
                <div className="font-medium text-[#0B1220] flex items-center gap-2">
                  {project.name}
                  {project.is_draft && (
                    <Badge variant="outline" className="text-xs border-[#F97316] text-[#F97316]">DRAFT</Badge>
                  )}
                  {project.google_drive_url && (
                    <a
                      href={project.google_drive_url}
                      target="_blank" rel="noopener noreferrer"
                      onClick={e => e.stopPropagation()}
                      className="text-[#667085] hover:text-[#1570EF]" title="Open Google Drive"
                    >
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
              <Badge className={getHealthColor(project.health)}>{project.health}</Badge>
            </TableCell>
            <TableCell>
              <div className="flex items-center gap-2">
                <Progress value={project.progress} className="flex-1 h-2" />
                <span className="text-sm font-medium min-w-[40px] text-right">{project.progress}%</span>
                {project.end_date && (
                  <span className="text-xs text-[#667085] whitespace-nowrap">
                    | Due: {(() => { try { return format(parseISO(project.end_date), 'MMM d'); } catch { return '—'; } })()}
                  </span>
                )}
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
            {isAdmin && (
              <TableCell className="text-right">
                <div className="flex items-center justify-end gap-1">
                  <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); onEdit && onEdit(project); }} data-testid={`edit-project-${project.id}`}>
                    <Edit size={14} />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); onDelete && onDelete(project.id); }} data-testid={`delete-project-${project.id}`}>
                    <Trash2 size={14} className="text-[#EF4444]" />
                  </Button>
                </div>
              </TableCell>
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};


/**
 * A collapsible status-group section. Default expanded states:
 *   Active    → expanded
 *   Pipeline  → collapsed
 *   Completed → collapsed
 *
 * Caller controls expanded state via props (so it persists across re-renders).
 */
export const ProjectStatusSection = ({
  title, projects, expanded, onToggle, color, testId, isAdmin, onEdit, onDelete,
}) => (
  <div className="border border-[#E6E8EC] rounded-lg overflow-hidden" data-testid={testId}>
    <div
      className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-[#F8FAFC] transition-colors"
      style={{ borderLeft: `4px solid ${color}` }}
      onClick={onToggle}
    >
      <div className="flex items-center gap-3">
        <h3 className="text-sm font-semibold text-[#0B1220]" style={{ fontFamily: 'Space Grotesk' }}>{title}</h3>
        <Badge variant="secondary" className="text-xs">{projects.length}</Badge>
      </div>
      {expanded ? <ChevronUp size={16} className="text-[#667085]" /> : <ChevronDown size={16} className="text-[#667085]" />}
    </div>
    {expanded && projects.length > 0 && (
      <div className="overflow-x-auto">
        <ProjectRichTable projects={projects} isAdmin={isAdmin} onEdit={onEdit} onDelete={onDelete} />
      </div>
    )}
    {expanded && projects.length === 0 && (
      <div className="text-center py-6 text-sm text-[#667085]">No {title.toLowerCase()} projects</div>
    )}
  </div>
);


/**
 * Convenience wrapper: groups enriched projects by status and renders 3
 * collapsible sections with consistent defaults (Active expanded, others
 * collapsed). Used by both Dashboard and Projects page.
 */
export const ProjectStatusGroups = ({ projects, isAdmin = false, onEdit, onDelete, defaultExpanded }) => {
  const expandedDefaults = {
    Active: true,
    Pipeline: false,
    Completed: false,
    ...(defaultExpanded || {}),
  };
  const [active, setActive]       = useState(expandedDefaults.Active);
  const [pipeline, setPipeline]   = useState(expandedDefaults.Pipeline);
  const [completed, setCompleted] = useState(expandedDefaults.Completed);

  const activeProjects    = useMemo(() => projects.filter(p => p.status === 'Active'),    [projects]);
  const pipelineProjects  = useMemo(() => projects.filter(p => p.status === 'Pipeline'),  [projects]);
  const completedProjects = useMemo(() => projects.filter(p => p.status === 'Completed'), [projects]);

  return (
    <div className="space-y-3">
      <ProjectStatusSection
        title="Active" testId="status-section-active"
        projects={activeProjects}
        expanded={active} onToggle={() => setActive(!active)}
        color="#16B364"
        isAdmin={isAdmin} onEdit={onEdit} onDelete={onDelete}
      />
      <ProjectStatusSection
        title="Pipeline" testId="status-section-pipeline"
        projects={pipelineProjects}
        expanded={pipeline} onToggle={() => setPipeline(!pipeline)}
        color="#F4B740"
        isAdmin={isAdmin} onEdit={onEdit} onDelete={onDelete}
      />
      <ProjectStatusSection
        title="Completed" testId="status-section-completed"
        projects={completedProjects}
        expanded={completed} onToggle={() => setCompleted(!completed)}
        color="#667085"
        isAdmin={isAdmin} onEdit={onEdit} onDelete={onDelete}
      />
    </div>
  );
};
