import React, { useMemo } from 'react';
import { format, isWithinInterval } from 'date-fns';
import { CheckCircle2, Circle, Diamond } from 'lucide-react';

const PhaseVisualizer = ({ phases = [], milestones = [] }) => {
  const currentPhase = useMemo(() => {
    const today = new Date();
    return phases.find(phase => {
      try {
        const start = new Date(phase.start_date);
        const end = new Date(phase.end_date);
        // Validate dates before using isWithinInterval
        if (isNaN(start.getTime()) || isNaN(end.getTime())) return false;
        if (start > end) return false; // Invalid interval
        return isWithinInterval(today, { start, end });
      } catch (e) {
        return false;
      }
    });
  }, [phases]);

  const getPhaseStatus = (phase) => {
    try {
      const today = new Date();
      const start = new Date(phase.start_date);
      const end = new Date(phase.end_date);
      
      // Validate dates
      if (isNaN(start.getTime()) || isNaN(end.getTime())) return 'pending';
      
      if (phase.status === 'Done') return 'done';
      if (today < start) return 'pending';
      if (start > end) return 'pending'; // Invalid interval - treat as pending
      if (isWithinInterval(today, { start, end })) return 'active';
      if (today > end) return 'done';
      return 'pending';
    } catch (e) {
      return 'pending';
    }
  };

  const formatDate = (dateStr) => {
    try {
      const date = new Date(dateStr);
      if (isNaN(date.getTime())) return 'N/A';
      return format(date, 'MMM d');
    } catch (e) {
      return 'N/A';
    }
  };

  const formatDateFull = (dateStr) => {
    try {
      const date = new Date(dateStr);
      if (isNaN(date.getTime())) return 'N/A';
      return format(date, 'MMM d, yyyy');
    } catch (e) {
      return 'N/A';
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      done: 'bg-[#16B364] border-[#16B364] text-white',
      active: 'bg-[#1570EF] border-[#1570EF] text-white',
      pending: 'bg-white border-[#E6E8EC] text-[#667085]',
    };
    return colors[status] || colors.pending;
  };

  if (!phases || phases.length === 0) {
    return null;
  }

  return (
    <div className="bg-white border border-[#E6E8EC] rounded-lg p-6" data-testid="phase-visualizer">
      <h3 className="text-lg font-semibold mb-4" style={{ fontFamily: 'Space Grotesk' }}>
        Project Phases
      </h3>
      
      {/* Chevron Progress Bar */}
      <div className="relative">
        <div className="flex items-center gap-2">
          {phases.map((phase, index) => {
            const status = getPhaseStatus(phase);
            const isActive = currentPhase?.name === phase.name;
            
            return (
              <React.Fragment key={index}>
                <div className="flex-1">
                  <div
                    className={`relative px-4 py-3 border-2 rounded-lg transition-all ${
                      getStatusColor(status)
                    } ${
                      isActive ? 'ring-2 ring-[#1570EF] ring-opacity-50 scale-105' : ''
                    }`}
                    data-testid={`phase-${index}`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="font-semibold text-sm">{phase.name}</div>
                      {status === 'done' && <CheckCircle2 size={16} />}
                      {status === 'active' && <Circle size={16} className="animate-pulse" />}
                    </div>
                    <div className="text-xs opacity-90">
                      {formatDate(phase.start_date)} -{' '}
                      {formatDateFull(phase.end_date)}
                    </div>
                    
                    {/* Milestones for this phase */}
                    {milestones
                      .filter(m => {
                        try {
                          if (!m.date) return false;
                          const mDate = new Date(m.date);
                          const pStart = new Date(phase.start_date);
                          const pEnd = new Date(phase.end_date);
                          // Validate all dates
                          if (isNaN(mDate.getTime()) || isNaN(pStart.getTime()) || isNaN(pEnd.getTime())) return false;
                          if (pStart > pEnd) return false; // Invalid interval
                          return isWithinInterval(mDate, { start: pStart, end: pEnd });
                        } catch (e) {
                          return false;
                        }
                      })
                      .map((milestone, mIndex) => (
                        <div key={mIndex} className="mt-2 flex items-center gap-2">
                          <Diamond
                            size={12}
                            className={milestone.status === 'Completed' ? 'fill-current' : ''}
                          />
                          <span className="text-xs">{milestone.name}</span>
                        </div>
                      ))}                    
                  </div>
                </div>
                
                {/* Chevron Arrow */}
                {index < phases.length - 1 && (
                  <div className="flex-shrink-0">
                    <svg
                      width="24"
                      height="40"
                      viewBox="0 0 24 40"
                      fill="none"
                      className="text-[#E6E8EC]"
                    >
                      <path
                        d="M2 2L20 20L2 38"
                        stroke="currentColor"
                        strokeWidth="3"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 mt-4 text-sm text-[#667085]">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[#16B364]"></div>
          <span>Completed</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[#1570EF]"></div>
          <span>Active</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full border-2 border-[#E6E8EC]"></div>
          <span>Pending</span>
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <Diamond size={14} />
          <span>Milestones</span>
        </div>
      </div>
    </div>
  );
};

export default PhaseVisualizer;
