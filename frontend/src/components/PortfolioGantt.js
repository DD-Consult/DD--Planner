import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronRight, ChevronDown, Building2, Diamond } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from './ui/tooltip';

/**
 * PortfolioGantt
 * -------------------------------------------------------------
 * Company-wide Gantt chart. Renders every project as a horizontal
 * bar across a shared time axis, grouped by Active vs Pipeline,
 * color-coded by health, with an optional per-project phase
 * breakdown (sub-bars) and click-through to the project detail.
 *
 * The axis auto-fits to encompass all supplied projects (and the
 * selected window) so bars are always fully visible.
 *
 * Props:
 *   projects   : portfolio project objects (from /api/portfolio)
 *   dateRange  : { start, end } ISO strings for the selected window
 *   showAllPhases : boolean — expand phase sub-bars for every project
 */

const MS_PER_DAY = 1000 * 60 * 60 * 24;

const toDate = (val) => {
  if (!val) return null;
  // Handles ISO ("2026-05-28T..."), space-separated ("2026-05-28 13:16:..")
  const d = new Date(typeof val === 'string' ? val.replace(' ', 'T') : val);
  return isNaN(d.getTime()) ? null : d;
};

const startOfMonth = (d) => new Date(d.getFullYear(), d.getMonth(), 1);
const addMonths = (d, n) => new Date(d.getFullYear(), d.getMonth() + n, 1);

const healthBar = (health) => {
  switch ((health || '').toLowerCase()) {
    case 'green':
      return { bar: 'bg-green-400', fill: 'bg-green-600', text: 'text-green-900' };
    case 'amber':
    case 'yellow':
      return { bar: 'bg-amber-300', fill: 'bg-amber-500', text: 'text-amber-900' };
    case 'red':
      return { bar: 'bg-red-300', fill: 'bg-red-600', text: 'text-red-900' };
    default:
      return { bar: 'bg-slate-300', fill: 'bg-slate-500', text: 'text-slate-900' };
  }
};

const fmt = (d) =>
  d
    ? d.toLocaleDateString('en-AU', { day: '2-digit', month: 'short', year: 'numeric' })
    : 'N/A';

const PortfolioGantt = ({ projects = [], dateRange, showAllPhases = false }) => {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState({});

  // ---- Build the shared time axis (auto-fit) ----
  const axis = useMemo(() => {
    const dates = [];
    const windowStart = toDate(dateRange?.start);
    const windowEnd = toDate(dateRange?.end);
    if (windowStart) dates.push(windowStart);
    if (windowEnd) dates.push(windowEnd);

    projects.forEach((p) => {
      const s = toDate(p.start_date);
      const e = toDate(p.end_date);
      if (s) dates.push(s);
      if (e) dates.push(e);
    });

    if (dates.length === 0) {
      const now = new Date();
      return { min: startOfMonth(now), max: addMonths(startOfMonth(now), 3), months: [] };
    }

    let min = new Date(Math.min(...dates.map((d) => d.getTime())));
    let max = new Date(Math.max(...dates.map((d) => d.getTime())));

    // Snap to month boundaries and pad by a month on each side for breathing room
    min = addMonths(startOfMonth(min), -0);
    max = addMonths(startOfMonth(max), 1); // include the end month fully

    // Build month gridline labels
    const months = [];
    let cur = new Date(min);
    while (cur < max) {
      months.push(new Date(cur));
      cur = addMonths(cur, 1);
    }
    return { min, max, months };
  }, [projects, dateRange]);

  const totalMs = axis.max.getTime() - axis.min.getTime() || 1;

  const pct = (d) => {
    const dt = toDate(d);
    if (!dt) return null;
    const clamped = Math.min(Math.max(dt.getTime(), axis.min.getTime()), axis.max.getTime());
    return ((clamped - axis.min.getTime()) / totalMs) * 100;
  };

  const barGeometry = (start, end) => {
    const left = pct(start);
    const right = pct(end);
    if (left === null || right === null) return null;
    const width = Math.max(right - left, 0.5); // min visible width
    return { left, width };
  };

  const today = new Date();
  const todayPct =
    today >= axis.min && today <= axis.max
      ? ((today.getTime() - axis.min.getTime()) / totalMs) * 100
      : null;

  const active = projects.filter((p) => !p.is_pipeline);
  const pipeline = projects.filter((p) => p.is_pipeline);

  const toggle = (id) => setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));

  const ProjectRow = ({ project }) => {
    const colors = healthBar(project.health);
    const geo = barGeometry(project.start_date, project.end_date);
    const isOpen = showAllPhases || expanded[project.id];
    const phases = Array.isArray(project.phases) ? project.phases : [];
    const milestones = Array.isArray(project.milestones) ? project.milestones : [];
    const progress = Math.min(Math.max(project.actual_progress || 0, 0), 100);

    return (
      <div className="border-b border-gray-100" data-testid={`gantt-row-${project.id}`}>
        <div className="flex items-stretch">
          {/* Left label column */}
          <div className="w-56 flex-shrink-0 px-3 py-2 flex items-center gap-1 border-r border-gray-100">
            {phases.length > 0 ? (
              <button
                onClick={() => toggle(project.id)}
                className="text-gray-400 hover:text-gray-700 flex-shrink-0"
                data-testid={`gantt-expand-${project.id}`}
                aria-label="Toggle phases"
              >
                {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
            ) : (
              <span className="w-4 flex-shrink-0" />
            )}
            <button
              onClick={() => navigate(`/projects/${project.id}`)}
              className="text-left min-w-0 group"
              data-testid={`gantt-project-link-${project.id}`}
            >
              <div className="text-sm font-medium text-gray-900 truncate group-hover:text-blue-600">
                {project.name}
              </div>
              <div className="text-xs text-gray-500 truncate">
                {project.client_name || 'No client'}
              </div>
            </button>
          </div>

          {/* Timeline track */}
          <div className="relative flex-1 py-3" style={{ minHeight: '2.75rem' }}>
            {/* Month gridlines */}
            {axis.months.map((m, i) => {
              const lpct = ((m.getTime() - axis.min.getTime()) / totalMs) * 100;
              return (
                <div
                  key={i}
                  className="absolute top-0 bottom-0 border-l border-gray-100"
                  style={{ left: `${lpct}%` }}
                />
              );
            })}
            {/* Today marker */}
            {todayPct !== null && (
              <div
                className="absolute top-0 bottom-0 border-l-2 border-blue-400 z-10"
                style={{ left: `${todayPct}%` }}
                title="Today"
              />
            )}

            {/* Project bar */}
            {geo && (
              <TooltipProvider delayDuration={150}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div
                      className={`absolute h-6 rounded-md cursor-pointer ${colors.bar} shadow-sm hover:ring-2 hover:ring-blue-300 transition`}
                      style={{ left: `${geo.left}%`, width: `${geo.width}%`, top: '0.5rem' }}
                      onClick={() => navigate(`/projects/${project.id}`)}
                      data-testid={`gantt-bar-${project.id}`}
                    >
                      {/* Progress fill */}
                      <div
                        className={`h-full rounded-md ${colors.fill}`}
                        style={{ width: `${progress}%` }}
                      />
                      <span className="absolute inset-0 flex items-center px-2 text-[11px] font-medium text-gray-800 truncate">
                        {progress > 0 ? `${progress}%` : ''}
                      </span>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <div className="space-y-1 text-xs">
                      <div className="font-semibold text-sm">{project.name}</div>
                      <div>{project.client_name || 'No client'}</div>
                      <div>
                        {fmt(toDate(project.start_date))} → {fmt(toDate(project.end_date))}
                      </div>
                      <div>Health: {project.health || 'N/A'} · {project.schedule_status || 'N/A'}</div>
                      <div>
                        Baseline {Number(project.baseline_hours || 0).toFixed(0)}h · Actual{' '}
                        {Number(project.actual_hours || 0).toFixed(0)}h
                      </div>
                      {project.project_lead_name && <div>Lead: {project.project_lead_name}</div>}
                    </div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
            {/* Milestone diamonds */}
            {milestones.map((m, mIdx) => {
              const mPct = pct(m.date);
              if (mPct === null) return null;
              return (
                <TooltipProvider key={`ms-${mIdx}`} delayDuration={150}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div
                        className="absolute z-20 flex items-center justify-center"
                        style={{ left: `${mPct}%`, top: '0.25rem', transform: 'translateX(-50%)' }}
                      >
                        <Diamond 
                          size={14} 
                          className={`${m.status === 'Completed' ? 'text-green-600 fill-green-600' : 'text-purple-500 fill-purple-200'} drop-shadow-sm`} 
                        />
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>
                      <div className="text-xs">
                        <div className="font-medium">{m.name}</div>
                        <div>{fmt(toDate(m.date))}</div>
                        <div className={m.status === 'Completed' ? 'text-green-600' : 'text-purple-600'}>{m.status}</div>
                      </div>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              );
            })}
          </div>
        </div>

        {/* Phase sub-bars */}
        {isOpen &&
          phases.map((phase, idx) => {
            const pgeo = barGeometry(phase.start_date, phase.end_date);
            return (
              <div key={phase.id || idx} className="flex items-stretch bg-gray-50/60">
                <div className="w-56 flex-shrink-0 pl-10 pr-3 py-1.5 border-r border-gray-100">
                  <div className="text-xs text-gray-600 truncate">{phase.name || `Phase ${idx + 1}`}</div>
                </div>
                <div className="relative flex-1 py-2" style={{ minHeight: '1.75rem' }}>
                  {todayPct !== null && (
                    <div
                      className="absolute top-0 bottom-0 border-l border-blue-200"
                      style={{ left: `${todayPct}%` }}
                    />
                  )}
                  {pgeo && (
                    <TooltipProvider delayDuration={150}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div
                            className="absolute h-3 rounded bg-indigo-300 hover:bg-indigo-400 cursor-default"
                            style={{ left: `${pgeo.left}%`, width: `${pgeo.width}%`, top: '0.4rem' }}
                            data-testid={`gantt-phase-${project.id}-${idx}`}
                          />
                        </TooltipTrigger>
                        <TooltipContent>
                          <div className="text-xs">
                            <div className="font-medium">{phase.name || `Phase ${idx + 1}`}</div>
                            <div>
                              {fmt(toDate(phase.start_date))} → {fmt(toDate(phase.end_date))}
                            </div>
                            {phase.status && <div>Status: {phase.status}</div>}
                          </div>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )}
                </div>
              </div>
            );
          })}
      </div>
    );
  };

  const GroupSection = ({ label, color, items }) => {
    if (items.length === 0) return null;
    return (
      <div className="mb-4">
        <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border-b border-gray-200">
          <div className={`h-1 w-8 rounded ${color}`} />
          <span className="text-sm font-semibold text-gray-800">
            {label} ({items.length})
          </span>
        </div>
        {items.map((p) => (
          <ProjectRow key={p.id} project={p} />
        ))}
      </div>
    );
  };

  if (projects.length === 0) {
    return (
      <div className="text-center py-12 bg-white rounded-lg border">
        <Building2 className="h-16 w-16 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">No projects in this view</h3>
        <p className="text-gray-600">Try a longer time range or adjust the status filter.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border overflow-hidden" data-testid="portfolio-gantt">
      {/* Month header axis */}
      <div className="flex items-stretch border-b border-gray-200 bg-white sticky top-0 z-20">
        <div className="w-56 flex-shrink-0 px-3 py-2 border-r border-gray-100 text-xs font-semibold text-gray-500">
          Project
        </div>
        <div className="relative flex-1 h-8">
          {axis.months.map((m, i) => {
            const lpct = ((m.getTime() - axis.min.getTime()) / totalMs) * 100;
            return (
              <div
                key={i}
                className="absolute top-0 bottom-0 flex items-center border-l border-gray-100 pl-1"
                style={{ left: `${lpct}%` }}
              >
                <span className="text-[10px] font-medium text-gray-500 whitespace-nowrap">
                  {m.toLocaleDateString('en-AU', { month: 'short', year: '2-digit' })}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="overflow-x-auto">
        <GroupSection label="Active Projects" color="bg-green-600" items={active} />
        <GroupSection label="Pipeline Projects" color="bg-blue-600" items={pipeline} />
      </div>
      {/* Legend */}
      <div className="flex items-center gap-4 px-3 py-2 border-t border-gray-100 text-xs text-gray-500">
        <div className="flex items-center gap-1.5"><div className="h-1 w-6 rounded bg-green-600" /> Active</div>
        <div className="flex items-center gap-1.5"><div className="h-1 w-6 rounded bg-blue-600" /> Pipeline</div>
        <div className="flex items-center gap-1.5"><Diamond size={12} className="text-purple-500 fill-purple-200" /> Milestone</div>
        <div className="flex items-center gap-1.5"><Diamond size={12} className="text-green-600 fill-green-600" /> Completed</div>
      </div>
    </div>
  );
};

export default PortfolioGantt;
