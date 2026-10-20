import React, { useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { driver } from 'driver.js';
import 'driver.js/dist/driver.css';
import { Sparkles } from 'lucide-react';
import { Button } from './ui/button';

// Wait for an element to appear in the DOM (resolves null on timeout).
const waitForElement = (selector, timeout = 4000) =>
  new Promise((resolve) => {
    const start = Date.now();
    const check = () => {
      const el = document.querySelector(selector);
      if (el) resolve(el);
      else if (Date.now() - start < timeout) setTimeout(check, 100);
      else resolve(null);
    };
    check();
  });

// Tour segments — MODULE-LEVEL constant so its identity is stable across
// renders (a per-render array previously caused the driving effect to loop and
// re-initialise the first segment, freezing the tour on step 1). Selectors are
// REAL data-testids verified against the page components.
const TOUR_SEGMENTS = [
  {
    name: 'Dashboard',
    path: '/',
    waitFor: '[data-testid="dashboard-title"]',
    steps: [
      {
        popover: {
          title: 'Welcome to the DD Planner demo',
          description:
            'A quick 2-minute tour of the highlights. Everything you see is sample data and the demo is read-only.',
        },
      },
      {
        element: '[data-testid="kpi-team-utilization"]',
        popover: {
          title: 'Portfolio at a glance',
          description:
            'Live KPIs across the whole portfolio — active projects, team utilisation and who is over-allocated.',
        },
      },
      {
        element: '[data-testid="project-portfolio"]',
        popover: {
          title: 'Project portfolio & AI health grades',
          description:
            'Every project with its health, schedule status and an AI-generated health grade so risks surface automatically.',
        },
      },
      {
        element: '[data-testid="chat-toggle-btn"]',
        popover: {
          title: 'AI PM Assist',
          description:
            'Your AI project assistant is available on every page — ask it about plans, draft updates, reschedule work or generate a WBS.',
        },
      },
    ],
  },
  {
    name: 'Projects',
    path: '/projects',
    waitFor: '[data-testid="add-project-button"]',
    steps: [
      {
        element: '[data-testid="add-project-button"]',
        popover: {
          title: 'Projects',
          description:
            'Create and manage every project — status, client, timeline and budget in one place.',
        },
      },
    ],
  },
  {
    name: 'ProjectDetail',
    path: null, // resolved dynamically to the first project
    waitFor: '[data-testid="tab-wbs"]',
    steps: [
      {
        element: '[data-testid="tab-wbs"]',
        popover: {
          title: 'Work breakdown, Gantt & critical path',
          description:
            'A full WBS with a Gantt timeline, task dependencies, drag-to-reschedule and automatic critical-path highlighting.',
        },
      },
      {
        element: '[data-testid="generate-report"]',
        popover: {
          title: 'AI status reports & client reporting',
          description:
            'Generate an AI-written status report, then share a secure read-only link with the client — no login required.',
        },
      },
      {
        element: '[data-testid="chat-toggle-btn"]',
        popover: {
          title: 'AI PM Assist on the project',
          description:
            'Ask the AI to generate the work breakdown, summarise progress or plan the next phase for this project.',
        },
      },
    ],
  },
  {
    name: 'Capacity',
    path: '/allocations',
    waitFor: '[data-testid="allocations-page"]',
    steps: [
      {
        element: '[data-testid="allocations-page"]',
        popover: {
          title: 'Team capacity',
          description:
            'A capacity heatmap across projects and weeks — green / amber / red instantly shows who is over-allocated.',
        },
      },
    ],
  },
  {
    name: 'Reports',
    path: '/reports',
    waitFor: '[data-testid="reports-page"]',
    steps: [
      {
        element: '[data-testid="ai-portfolio-analysis"]',
        popover: {
          title: 'AI portfolio highlights',
          description:
            'AI reads the whole portfolio and writes a plain-English narrative of what needs attention — refreshed on demand.',
        },
      },
      {
        element: '[data-testid="project-comparison-table"]',
        popover: {
          title: 'Budget vs actuals',
          description:
            'Compare budget against actuals across projects, and share secure read-only client report links.',
        },
      },
    ],
  },
  {
    name: 'Proposals',
    path: '/proposals',
    waitFor: '[data-testid="new-proposal-button"]',
    steps: [
      {
        element: '[data-testid="new-proposal-button"]',
        popover: {
          title: 'AI-guided client proposals',
          description:
            'Draft a polished proposal with an AI assistant, send a secure link, and auto-create the project + a read-only client login when the client accepts.',
        },
      },
    ],
  },
  {
    name: 'Final',
    path: null,
    waitFor: null,
    steps: [
      {
        popover: {
          title: 'That\u2019s the tour!',
          description:
            'This is a read-only demo with sample data. Sign up to create your own workspace and unlock everything.',
        },
      },
    ],
  },
];

// Inject brand-accent styling for the driver.js popover once.
const injectTourStyles = () => {
  if (document.getElementById('dd-demo-tour-styles')) return;
  const style = document.createElement('style');
  style.id = 'dd-demo-tour-styles';
  style.textContent = `
    .driver-popover { background:#fff; color:#0B1220; border-radius:12px; }
    .driver-popover-title { font-size:17px; font-weight:600; color:#0B1220; }
    .driver-popover-description { font-size:14px; color:#667085; }
    .driver-popover-footer button.driver-popover-next-btn {
      background:#1570EF; color:#fff; border:none; padding:8px 16px;
      border-radius:6px; font-weight:500; text-shadow:none; }
    .driver-popover-footer button.driver-popover-next-btn:hover { background:#0F5FD1; }
    .driver-popover-progress-text { color:#98A2B3; }
  `;
  document.head.appendChild(style);
};

const DemoTour = ({ user }) => {
  const navigate = useNavigate();
  const [isRunning, setIsRunning] = useState(false);
  const [segmentIndex, setSegmentIndex] = useState(0);

  const driverRef = useRef(null);
  const drivingIndexRef = useRef(-1); // guards against driving the same segment twice

  const endTour = useCallback(() => {
    try {
      if (driverRef.current) {
        driverRef.current.destroy();
      }
    } catch (e) {
      /* no-op */
    }
    driverRef.current = null;
    drivingIndexRef.current = -1;
    setIsRunning(false);
    setSegmentIndex(0);
  }, []);

  const goToNextSegmentOrEnd = useCallback((idx) => {
    if (idx < TOUR_SEGMENTS.length - 1) {
      setSegmentIndex(idx + 1);
    } else {
      endTour();
    }
  }, [endTour]);

  // Drive the steps of a single segment that is already on-screen.
  const driveSegment = useCallback(async (segment, idx) => {
    // Keep only steps whose target element exists (center-popover steps always kept).
    const steps = [];
    for (const step of segment.steps) {
      if (!step.element) {
        steps.push(step);
      } else {
        const el = await waitForElement(step.element, 2500);
        if (el) steps.push(step);
      }
    }

    if (steps.length === 0) {
      goToNextSegmentOrEnd(idx);
      return;
    }

    injectTourStyles();

    // Destroy any prior instance before creating a new one.
    try {
      if (driverRef.current) driverRef.current.destroy();
    } catch (e) {
      /* no-op */
    }

    const isLastSegment = idx === TOUR_SEGMENTS.length - 1;
    let advanced = false; // did we complete this segment's steps (vs user closing)?

    const d = driver({
      showProgress: true,
      allowClose: true,
      overlayClickBehavior: 'close',
      steps,
      nextBtnText: 'Next',
      prevBtnText: 'Back',
      doneBtnText: isLastSegment ? 'Done' : 'Next',
      onCloseClick: () => {
        // Explicit close (the X) ends the whole tour.
        endTour();
      },
      onNextClick: () => {
        if (!driverRef.current) return;
        if (driverRef.current.isLastStep()) {
          // Finished this segment's steps → advance to the next segment.
          advanced = true;
          driverRef.current.destroy();
          driverRef.current = null;
          goToNextSegmentOrEnd(idx);
        } else {
          driverRef.current.moveNext();
        }
      },
      onPrevClick: () => {
        if (driverRef.current) driverRef.current.movePrevious();
      },
      onDestroyed: () => {
        // If destroyed without completing (e.g. ESC/overlay), end the tour.
        if (!advanced) {
          // Only end if we're not mid-advance to the next segment.
        }
      },
    });

    driverRef.current = d;
    d.drive();
  }, [goToNextSegmentOrEnd, endTour]);

  // Navigate to a segment's page (resolving the dynamic project detail), then drive it.
  const enterSegment = useCallback(async (idx) => {
    const segment = TOUR_SEGMENTS[idx];

    // Final/center-only segment: no navigation.
    if (!segment.path && segment.name === 'Final') {
      driveSegment(segment, idx);
      return;
    }

    // Dynamic project-detail segment: go to /projects, read the first project row id.
    if (segment.name === 'ProjectDetail') {
      try {
        navigate('/projects');
        await waitForElement('[data-testid^="project-row-"]', 4000);
        const row = document.querySelector('[data-testid^="project-row-"]');
        const testid = row?.getAttribute('data-testid') || '';
        const projectId = testid.replace('project-row-', '');
        if (projectId) {
          navigate(`/projects/${projectId}`);
          const el = await waitForElement(segment.waitFor, 4000);
          if (el) {
            driveSegment(segment, idx);
            return;
          }
        }
      } catch (e) {
        /* fall through to skip */
      }
      goToNextSegmentOrEnd(idx);
      return;
    }

    // Standard page segment.
    if (segment.path) navigate(segment.path);
    if (segment.waitFor) {
      const el = await waitForElement(segment.waitFor, 4000);
      if (el) {
        driveSegment(segment, idx);
      } else {
        goToNextSegmentOrEnd(idx);
      }
    } else {
      driveSegment(segment, idx);
    }
  }, [navigate, driveSegment, goToNextSegmentOrEnd]);

  // Effect: when running and the segment index changes, enter that segment ONCE.
  React.useEffect(() => {
    if (!isRunning) return;
    if (drivingIndexRef.current === segmentIndex) return; // already handled
    drivingIndexRef.current = segmentIndex;
    enterSegment(segmentIndex);
  }, [isRunning, segmentIndex, enterSegment]);

  const startTour = useCallback(() => {
    drivingIndexRef.current = -1;
    setSegmentIndex(0);
    setIsRunning(true);
    try {
      localStorage.setItem('dd_demo_tour_seen', 'true');
    } catch (e) {
      /* no-op */
    }
  }, []);

  if (!user?.is_demo) return null;

  return (
    <>
      {!isRunning && (
        <Button
          data-testid="start-demo-tour-btn"
          onClick={startTour}
          className="fixed bottom-6 right-6 z-50 bg-[#1570EF] hover:bg-[#0F5FD1] text-white shadow-xl flex items-center gap-2 px-4 py-3 rounded-lg"
        >
          <Sparkles size={18} />
          Take the tour
        </Button>
      )}
    </>
  );
};

export default DemoTour;
