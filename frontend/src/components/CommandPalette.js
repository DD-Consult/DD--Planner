import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Command, Search, Briefcase, Users, ClipboardList, AlertTriangle,
  MessageSquare, LayoutDashboard, ArrowRight, Mic, MicOff, Loader2,
  BarChart3, Calendar, CalendarOff, HelpCircle, Sparkles, Settings as SettingsIcon,
  FileText, X,
} from 'lucide-react';
import { globalSearch } from '../api';
import { toast } from 'sonner';

// Detect Mac for keyboard shortcut label
const IS_MAC = typeof navigator !== 'undefined' && /Mac|iPhone|iPod|iPad/.test(navigator.platform);
const CMD_KEY = IS_MAC ? '⌘' : 'Ctrl';

// ─── Static navigation targets (fuzzy-match top of palette) ──────────
const NAV_ITEMS = [
  { icon: LayoutDashboard, label: 'Dashboard',          href: '/',                keywords: 'home overview' },
  { icon: Briefcase,       label: 'Projects',           href: '/projects',        keywords: 'projects' },
  { icon: BarChart3,       label: 'Portfolio Gantt',    href: '/portfolio',       keywords: 'portfolio gantt timeline' },
  { icon: Users,           label: 'Resources',          href: '/resources',       keywords: 'resources team people' },
  { icon: Calendar,        label: 'Allocations',        href: '/allocations',     keywords: 'allocations capacity assign' },
  { icon: FileText,        label: 'My Timesheets',      href: '/my-timesheets',   keywords: 'timesheets time tracking hours' },
  { icon: ClipboardList,   label: 'Manage Timesheets',  href: '/manage-timesheets', keywords: 'admin timesheets manage' },
  { icon: CalendarOff,     label: 'Time Off / Leaves',  href: '/leaves',          keywords: 'leaves vacation time off' },
  { icon: Calendar,        label: 'Holidays',           href: '/holidays',        keywords: 'holidays company' },
  { icon: BarChart3,       label: 'Reports',            href: '/reports',         keywords: 'reports budget' },
  { icon: Sparkles,        label: 'AI Intelligence',    href: '/ai-intelligence', keywords: 'ai intelligence anomaly forecast retrospective' },
  { icon: SettingsIcon,    label: 'Settings',           href: '/settings',        keywords: 'settings integrations config' },
  { icon: HelpCircle,      label: 'Help & Guide',       href: '/help',            keywords: 'help guide how to' },
];

const TYPE_META = {
  project:       { icon: Briefcase,      color: 'text-blue-600',   label: 'Project' },
  resource:      { icon: Users,          color: 'text-emerald-600', label: 'Resource' },
  task:          { icon: ClipboardList,  color: 'text-purple-600', label: 'Task' },
  risk:          { icon: AlertTriangle,  color: 'text-orange-600', label: 'Risk' },
  status_update: { icon: MessageSquare,  color: 'text-cyan-600',   label: 'Status Update' },
  navigation:    { icon: ArrowRight,     color: 'text-[#667085]',  label: 'Navigate' },
};

// Fuzzy-match nav items
const filterNav = (query) => {
  const q = query.toLowerCase().trim();
  if (!q) return [];
  return NAV_ITEMS
    .filter(n => n.label.toLowerCase().includes(q) || n.keywords.includes(q))
    .slice(0, 6);
};

const CommandPalette = () => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [debounced, setDebounced] = useState('');
  const [activeIdx, setActiveIdx] = useState(0);
  const [isListening, setIsListening] = useState(false);
  const inputRef = useRef(null);
  const recognitionRef = useRef(null);
  const navigate = useNavigate();

  // ⌘K / Ctrl+K shortcut + custom event trigger (used by sidebar button)
  useEffect(() => {
    const onKey = (e) => {
      const isCmdK = (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k';
      if (isCmdK) {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === 'Escape' && open) setOpen(false);
    };
    const onOpenEvent = () => setOpen(true);
    window.addEventListener('keydown', onKey);
    window.addEventListener('dd:open-command-palette', onOpenEvent);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('dd:open-command-palette', onOpenEvent);
    };
  }, [open]);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setQuery('');
      setDebounced('');
      setActiveIdx(0);
    }
  }, [open]);

  // Debounce query
  useEffect(() => {
    const id = setTimeout(() => setDebounced(query), 200);
    return () => clearTimeout(id);
  }, [query]);

  const { data, isFetching } = useQuery({
    queryKey: ['global-search', debounced],
    queryFn: () => globalSearch(debounced).then(r => r.data),
    enabled: debounced.trim().length >= 2,
    staleTime: 30000,
  });

  // Voice input (browser native Web Speech API)
  const startVoice = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      toast.error('Voice search is not supported in this browser. Try Chrome or Edge.');
      return;
    }
    if (isListening) {
      recognitionRef.current?.stop();
      return;
    }
    const rec = new SR();
    rec.lang = 'en-US';
    rec.continuous = false;
    rec.interimResults = false;
    rec.onstart = () => setIsListening(true);
    rec.onresult = (e) => {
      const text = e.results?.[0]?.[0]?.transcript || '';
      if (text) setQuery(text);
      setIsListening(false);
    };
    rec.onerror = (e) => {
      setIsListening(false);
      if (e.error === 'no-speech') toast.info('No speech detected');
      else toast.error(`Voice error: ${e.error}`);
    };
    rec.onend = () => setIsListening(false);
    recognitionRef.current = rec;
    rec.start();
  }, [isListening]);

  // Build combined result list
  const navMatches = filterNav(query).map(n => ({
    type: 'navigation', title: n.label, subtitle: 'Navigate', href: n.href, icon: n.icon,
  }));
  const results = data?.results || {};
  const searchMatches = [
    ...(results.projects || []),
    ...(results.tasks || []),
    ...(results.resources || []),
    ...(results.risks || []),
    ...(results.status_updates || []),
  ];
  const combined = [...navMatches, ...searchMatches];

  // Reset active idx when list changes
  useEffect(() => { setActiveIdx(0); }, [combined.length]);

  const executeSelection = (item) => {
    if (!item) return;
    setOpen(false);
    navigate(item.href);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, combined.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      executeSelection(combined[activeIdx]);
    }
  };

  return (
    <>
      {/* Overlay — the palette itself. The trigger button lives in the sidebar
          (Layout.js) so it no longer floats over Sign Out. Users can also press
          Cmd/Ctrl+K from anywhere. */}
      {open && (
        <div
          className="fixed inset-0 bg-black/40 z-50 flex items-start justify-center pt-[10vh] px-4"
          onClick={() => setOpen(false)}
          data-testid="command-palette-overlay"
        >
          <div
            className="w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-[#E6E8EC] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Search input */}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-[#E6E8EC]">
              {isFetching ? (
                <Loader2 size={18} className="text-[#1570EF] animate-spin flex-shrink-0" />
              ) : (
                <Search size={18} className="text-[#667085] flex-shrink-0" />
              )}
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Search projects, tasks, resources, risks… or say 'go to projects'"
                className="flex-1 bg-transparent border-none outline-none text-[15px] placeholder:text-[#98A2B3]"
                data-testid="command-palette-input"
              />
              <button
                onClick={startVoice}
                className={`p-1.5 rounded transition-colors ${isListening ? 'bg-red-100 text-red-600' : 'hover:bg-[#F2F3F5] text-[#667085]'}`}
                title="Voice search"
                data-testid="command-palette-mic-btn"
              >
                {isListening ? <MicOff size={16} /> : <Mic size={16} />}
              </button>
              <button
                onClick={() => setOpen(false)}
                className="p-1.5 rounded hover:bg-[#F2F3F5] text-[#667085]"
              >
                <X size={16} />
              </button>
            </div>

            {/* Results */}
            <div className="max-h-[60vh] overflow-y-auto">
              {query.trim().length < 2 && (
                <div className="p-8 text-center text-[#667085] text-sm" data-testid="command-palette-empty">
                  <Sparkles size={24} className="mx-auto mb-3 text-purple-400" />
                  <p className="mb-1">Start typing to search across your projects, tasks, and team.</p>
                  <p className="text-xs text-[#98A2B3]">
                    Or use the mic to say something like <i>&quot;go to projects&quot;</i>.
                  </p>
                </div>
              )}

              {query.trim().length >= 2 && combined.length === 0 && !isFetching && (
                <div className="p-8 text-center text-[#667085] text-sm">
                  No matches for &quot;<b>{query}</b>&quot;
                </div>
              )}

              {combined.length > 0 && (
                <ul className="py-1" data-testid="command-palette-results">
                  {combined.map((item, idx) => {
                    const meta = TYPE_META[item.type] || TYPE_META.navigation;
                    const Icon = item.icon || meta.icon;
                    return (
                      <li key={`${item.type}-${item.id || idx}`}>
                        <button
                          onClick={() => executeSelection(item)}
                          onMouseEnter={() => setActiveIdx(idx)}
                          className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                            idx === activeIdx ? 'bg-[#F2F3F5]' : 'hover:bg-[#F9FAFB]'
                          }`}
                          data-testid={`command-palette-result-${idx}`}
                        >
                          <Icon size={16} className={meta.color} />
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-[#0B1220] truncate">{item.title}</div>
                            {item.subtitle && (
                              <div className="text-xs text-[#667085] truncate">{item.subtitle}</div>
                            )}
                          </div>
                          <span className="text-[10px] uppercase text-[#98A2B3] tracking-wide">{meta.label}</span>
                          <ArrowRight size={12} className="text-[#94A3B8]" />
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* Footer */}
            <div className="px-4 py-2 border-t border-[#E6E8EC] bg-[#FAFAFB] text-[11px] text-[#667085] flex items-center gap-3">
              <span><kbd className="px-1 py-0.5 bg-white border rounded">↑↓</kbd> navigate</span>
              <span><kbd className="px-1 py-0.5 bg-white border rounded">↵</kbd> select</span>
              <span><kbd className="px-1 py-0.5 bg-white border rounded">{CMD_KEY}+K</kbd> toggle</span>
              <span><kbd className="px-1 py-0.5 bg-white border rounded">esc</kbd> close</span>
              <span className="ml-auto">Powered by DD Planner AI</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default CommandPalette;
