{
  "meta": {
    "app_name": "PlanFlux – Resource Planning & Capacity Heatmap",
    "version": "1.0",
    "audience": ["Project Managers", "Resource Managers", "Team Leads"],
    "success_actions": [
      "View 14-day timeline and instantly see red/yellow/green capacity",
      "Create/Edit allocations via dialog with optimistic updates",
      "Filter by team/role and date range",
      "Export or snapshot charts for reporting"
    ]
  },
  "brand_personality": ["modern", "precise", "trustworthy", "calm", "data-focused"],
  "design_style": {
    "fusion": [
      "Linear-like neutral chrome + crisp borders",
      "Swiss typographic hierarchy",
      "Bento grid for dashboard cards",
      "Subtle glass accents only for decorative surfaces"
    ],
    "layout_style": "Dashboard: Sidebar + Header + Main. Timeline Grid with sticky first column, scrollable days"
  },
  "color_system": {
    "neutrals": {
      "background": "#FCFCFD",
      "surface": "#FFFFFF",
      "elevated": "#F7F7F8",
      "panel": "#F2F3F5",
      "border_subtle": "#E6E8EC",
      "border_strong": "#D0D5DD",
      "text_primary": "#0B1220",
      "text_secondary": "#475467",
      "text_muted": "#667085",
      "muted_icon": "#98A2B3"
    },
    "functional": {
      "green_safe": "#16B364",
      "yellow_attention": "#F4B740",
      "red_critical": "#EF4444",
      "blue_action": "#1570EF",
      "cyan_info": "#06AED4"
    },
    "charts": {
      "chart_1": "#3B82F6",
      "chart_2": "#10B981",
      "chart_3": "#F59E0B",
      "chart_4": "#EF4444",
      "chart_5": "#06B6D4"
    },
    "semantic": {
      "success_bg": "#E9F9F1",
      "success_fg": "#065F46",
      "warning_bg": "#FFF8E5",
      "warning_fg": "#7A4E00",
      "error_bg": "#FEEBEC",
      "error_fg": "#7A1D1D",
      "info_bg": "#E6F7FB",
      "info_fg": "#0B5566"
    },
    "heatmap_scale": {
      "under_50": "#D1FAE5",
      "fifty_to_eighty": "#34D399",
      "eighty_to_hundred": "#FCD34D",
      "over_hundred": "#F87171"
    },
    "usage_notes": [
      "Use neutrals for all chrome: sidebars, headers, cards",
      "Use vibrant functional colors only for status/heatmap/badges",
      "Borders are always #E6E8EC (subtle) or #D0D5DD (strong)"
    ]
  },
  "gradients_and_texture": {
    "restriction_rule": "NEVER use dark/saturated gradient combos; never cover >20% viewport; avoid on text-heavy areas; no gradients on small UI elements <100px.",
    "allowed_usage": ["Hero stripe backgrounds", "Section separators", "Decorative overlays only"],
    "examples": [
      {
        "name": "Header Accent",
        "css": "background: linear-gradient(180deg, rgba(21,112,239,0.06) 0%, rgba(6,182,212,0.06) 100%);"
      },
      {
        "name": "Chart Card Accent",
        "css": "background: linear-gradient(135deg, rgba(22,179,100,0.04), rgba(244,183,64,0.04));"
      }
    ],
    "texture": "Optional 2% noise overlay on hero only (not on reading areas)"
  },
  "typography": {
    "fonts": {
      "heading": "Space Grotesk",
      "body": "Inter",
      "mono": "Roboto Mono"
    },
    "load_via": "Google Fonts",
    "scale": {
      "h1": "text-4xl sm:text-5xl lg:text-6xl",
      "h2": "text-base md:text-lg",
      "body": "text-sm md:text-base",
      "small": "text-xs"
    },
    "weights": { "heading": 600, "body": 400, "emphasis": 500 },
    "tracking": { "tight": "-0.01em", "normal": "0em" },
    "line_height": { "heading": 1.15, "body": 1.6 },
    "usage": [
      "Use Space Grotesk for page titles, section headings",
      "Inter for forms, tables, labels and body copy"
    ]
  },
  "spacing_radii_shadows": {
    "spacing_scale_px": [4, 8, 12, 16, 20, 24, 32, 40],
    "container_padding": "px-4 sm:px-6 lg:px-8",
    "radii": { "xs": 6, "sm": 8, "md": 10, "lg": 12 },
    "shadow_tokens": {
      "subtle": "0 1px 0 rgba(16,24,40,0.04), 0 1px 2px rgba(16,24,40,0.06)",
      "elevated": "0 2px 6px rgba(16,24,40,0.08)",
      "popover": "0 8px 30px rgba(0,0,0,0.12)"
    }
  },
  "css_tokens_for_index_css": {
    "instructions": "Update :root HSL tokens in /app/frontend/src/index.css to reflect palette. Keep Tailwind shadcn variables.",
    "root_vars": {
      "--background": "210 20% 99%",
      "--foreground": "220 14% 8%",
      "--card": "0 0% 100%",
      "--card-foreground": "220 14% 8%",
      "--popover": "0 0% 100%",
      "--popover-foreground": "220 14% 8%",
      "--primary": "217 91% 45%", 
      "--primary-foreground": "210 40% 98%",
      "--secondary": "220 9% 96%",
      "--secondary-foreground": "220 14% 8%",
      "--muted": "220 9% 96%",
      "--muted-foreground": "220 9% 46%",
      "--accent": "0 0% 100%",
      "--accent-foreground": "220 14% 8%",
      "--destructive": "0 84% 60%",
      "--destructive-foreground": "210 40% 98%",
      "--border": "220 14% 90%",
      "--input": "220 14% 90%",
      "--ring": "217 91% 45%",
      "--chart-1": "217 91% 60%",
      "--chart-2": "158 64% 52%",
      "--chart-3": "42 96% 56%",
      "--chart-4": "0 84% 65%",
      "--chart-5": "191 82% 46%",
      "--radius": "0.625rem"
    }
  },
  "buttons": {
    "brand": "Professional / Corporate",
    "tokens": {
      "--btn-radius": "8px",
      "--btn-shadow": "0 1px 2px rgba(16,24,40,0.06)",
      "--btn-motion": "150ms ease"
    },
    "variants": {
      "primary": {
        "class": "bg-[#1570EF] text-white hover:bg-[#175CD3] focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#1570EF] disabled:opacity-60 disabled:cursor-not-allowed",
        "data_testid": "primary-button"
      },
      "secondary": {
        "class": "bg-[#F2F3F5] text-[#0B1220] hover:bg-[#E9EAEC] border border-[#E6E8EC]",
        "data_testid": "secondary-button"
      },
      "ghost": {
        "class": "text-[#1570EF] hover:bg-[#F2F7FF]",
        "data_testid": "ghost-button"
      }
    },
    "sizes": {
      "sm": "h-9 px-3",
      "md": "h-10 px-4",
      "lg": "h-11 px-5"
    }
  },
  "legend_and_status": {
    "capacity_legend": [
      {"label": "< 80% (Safe)", "color": "#16B364"},
      {"label": "80–100% (At capacity)", "color": "#F4B740"},
      {"label": "> 100% (Over-allocated)", "color": "#EF4444"}
    ],
    "warning_icon": "lucide:alert-triangle"
  },
  "layouts": {
    "app_shell": {
      "structure": "Sidebar (sticky) + Header (sticky) + Main",
      "container_classes": "min-h-screen bg-[#FCFCFD] text-[#0B1220]",
      "content_grid": "grid grid-cols-1 lg:grid-cols-[260px_1fr]",
      "border_style": "border-r border-[#E6E8EC]"
    },
    "login_page": {
      "card": "max-w-md mx-auto mt-24 p-6 bg-white border border-[#E6E8EC] rounded-lg shadow-sm",
      "form_controls": "space-y-4",
      "notes": ["Include email/password inputs, remember me, sign-in button", "Show error with Alert component", "Use data-testid on all inputs and submit"]
    },
    "dashboard": {
      "header": "flex items-center justify-between px-6 py-4 border-b border-[#E6E8EC] bg-white",
      "grid": "px-4 sm:px-6 lg:px-8 py-6 space-y-6",
      "cards": "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6"
    }
  },
  "timeline_grid": {
    "spec": {
      "rows": "Resources (avatar, name, role)",
      "columns": "Days (default 14)",
      "cell": "Color block based on capacity percentage; tooltip on hover; click opens Allocation Dialog"
    },
    "styles": {
      "wrapper": "overflow-auto border border-[#E6E8EC] rounded-lg bg-white",
      "header_row": "sticky top-0 z-10 bg-[#F7F7F8] text-[#475467] text-xs border-b border-[#E6E8EC]",
      "resource_col": "sticky left-0 z-10 bg-white border-r border-[#E6E8EC] min-w-[220px]",
      "day_cell": "h-9 min-w-[44px] border-l border-[#F0F2F5] hover:ring-1 hover:ring-[#1570EF] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1570EF] transition-[background-color,box-shadow] duration-150 ease-out"
    },
    "color_logic": {
      "rule": "if pct < 0.8 -> green; 0.8 <= pct <= 1 -> yellow; pct > 1 -> red",
      "map": {
        "green": "#16B364",
        "yellow": "#F4B740",
        "red": "#EF4444"
      }
    },
    "interactive": [
      "Click cell -> open Dialog prefilled with resource/date",
      "Hover -> show Tooltip with percentage and total hours",
      "Keyboard -> arrow keys move focus; Enter opens dialog"
    ],
    "jsx_scaffold": {
      "file": "./components/TimelineGrid.jsx",
      "code": "import React from 'react';\nimport { Avatar, AvatarImage, AvatarFallback } from './components/ui/avatar';\nimport { Dialog, DialogContent, DialogHeader } from './components/ui/dialog';\nimport { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './components/ui/tooltip';\n\nexport const TimelineGrid = ({ resources = [], days = [], allocations = {}, onOpenAllocation }) => {\n  return (\n    <div className=\"overflow-auto border border-[$E6E8EC] rounded-lg bg-white\" data-testid=\"timeline-grid\">\n      <div className=\"min-w-max\">\n        <div className=\"grid\" style={{ gridTemplateColumns: `220px repeat(${days.length}, 48px)` }} role=\"table\" aria-label=\"Resource capacity timeline\">\n          <div className=\"contents\">\n            <div className=\"sticky left-0 z-10 bg-white px-3 py-2 text-xs font-medium border-r border-[#E6E8EC]\">Resource</div>\n            {days.map(d => (\n              <div key={d.key} className=\"sticky top-0 z-10 bg-[#F7F7F8] text-[#475467] text-xs px-2 py-2 border-b border-l border-[#E6E8EC] text-center\" aria-hidden>{d.label}</div>\n            ))}\n          </div>\n          {resources.map((r) => {\n            const rowKey = `row-${r.id}`;\n            return (\n              <React.Fragment key={rowKey}>\n                <div className=\"sticky left-0 z-10 bg-white border-t border-r border-[#E6E8EC] flex items-center gap-3 px-3 py-2 min-w-[220px]\">\n                  <Avatar className=\"h-7 w-7\"><AvatarImage src={r.avatar} alt=\"\" /><AvatarFallback>{r.initials}</AvatarFallback></Avatar>\n                  <div className=\"min-w-0\"><div className=\"text-sm font-medium text-[#0B1220] truncate\">{r.name}</div><div className=\"text-xs text-[#667085] truncate\">{r.role}</div></div>\n                </div>\n                {days.map((d) => {\n                  const key = `${r.id}-${d.key}`;\n                  const pct = allocations[key]?.pct ?? 0;\n                  const bg = pct > 1 ? '#EF4444' : pct >= 0.8 ? '#F4B740' : '#16B364';\n                  const title = `${Math.round(pct * 100)}%`;\n                  return (\n                    <TooltipProvider key={key}>\n                      <Tooltip delayDuration={150}>\n                        <TooltipTrigger asChild>\n                          <button\n                            style={{ backgroundColor: bg }}\n                            className=\"h-9 min-w-[48px] border-l border-[#F0F2F5] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1570EF]\"\n                            aria-label={\`Allocation ${title} for ${r.name} on ${d.label}\`}\n                            data-testid=\"timeline-cell-button\"\n                            onClick={() => onOpenAllocation?.({ resource: r, day: d })}\n                          />\n                        </TooltipTrigger>\n                        <TooltipContent side=\"top\">{r.name} • {d.label} • {title}</TooltipContent>\n                      </Tooltip>\n                    </TooltipProvider>\n                  );\n                })}\n              </React.Fragment>\n            );\n          })}\n        </div>\n      </div>\n    </div>\n  );\n};"
    }
  },
  "charts": {
    "library": "Recharts",
    "usage": ["StackedBarChart for capacity by role", "LineChart for trend"],
    "jsx_scaffold": "import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend } from 'recharts';\nexport const CapacityByRoleCard = ({ data }) => (\n  <div className=\"bg-white border border-[#E6E8EC] rounded-lg p-4\" data-testid=\"capacity-by-role-card\">\n    <div className=\"text-sm font-medium text-[#0B1220] mb-3\">Capacity by Role</div>\n    <ResponsiveContainer width=\"100%\" height={220}>\n      <BarChart data={data}>\n        <XAxis dataKey=\"role\" tickLine={false} axisLine={{ stroke: '#E6E8EC' }} />\n        <YAxis tickLine={false} axisLine={{ stroke: '#E6E8EC' }} />\n        <Tooltip cursor={{ fill: 'rgba(21,112,239,0.06)' }} />\n        <Legend />\n        <Bar dataKey=\"safe\" stackId=\"a\" fill=\"#16B364\" />\n        <Bar dataKey=\"atCapacity\" stackId=\"a\" fill=\"#F4B740\" />\n        <Bar dataKey=\"over\" stackId=\"a\" fill=\"#EF4444\" />\n      </BarChart>\n    </ResponsiveContainer>\n  </div>\n);"
  },
  "date_controls": {
    "components": ["button", "popover", "calendar"],
    "guidance": [
      "Provide Previous/Next week buttons",
      "Date range via shadcn Calendar inside Popover",
      "Always attach data-testid attributes"
    ],
    "jsx_scaffold": "import { Popover, PopoverTrigger, PopoverContent } from './components/ui/popover';\nimport { Calendar } from './components/ui/calendar';\nimport { Button } from './components/ui/button';\nimport { addDays, format } from 'date-fns';\nexport function DateRangeControls({ range, setRange }) {\n  return (\n    <div className=\"flex items-center gap-2\">\n      <Button data-testid=\"prev-range-button\" onClick={() => setRange(r => ({ start: addDays(r.start, -14), end: addDays(r.end, -14) }))}>Prev</Button>\n      <Popover>\n        <PopoverTrigger asChild>\n          <Button variant=\"secondary\" data-testid=\"open-date-picker-button\">{format(range.start, 'MMM d')} – {format(range.end, 'MMM d')}</Button>\n        </PopoverTrigger>\n        <PopoverContent className=\"w-auto p-0\">\n          <Calendar mode=\"range\" selected={range} onSelect={setRange} numberOfMonths={2} data-testid=\"date-range-calendar\" />\n        </PopoverContent>\n      </Popover>\n      <Button data-testid=\"next-range-button\" onClick={() => setRange(r => ({ start: addDays(r.start, 14), end: addDays(r.end, 14) }))}>Next</Button>\n    </div>\n  );\n}"
  },
  "forms_and_crud": {
    "components": ["form", "input", "select", "textarea", "dialog", "toast (sonner)", "alert"],
    "pattern": "Use shadcn Form for validation messages, inputs with dense spacing, labels above fields.",
    "loading_empty_error": [
      "Use Skeleton for list loading",
      "Empty state in cards with ghost buttons",
      "Error state via Alert component"
    ],
    "optimistic_updates": "Use TanStack Query useMutation with onMutate -> rollback cache onError -> invalidate onSettled.",
    "sample_mutation": "const mutation = useMutation({ mutationFn: createAllocation, onMutate: async (newAlloc) => { await queryClient.cancelQueries({ queryKey: ['allocations'] }); const prev = queryClient.getQueryData(['allocations']); queryClient.setQueryData(['allocations'], old => [...(old||[]), newAlloc]); return { prev }; }, onError: (_e, _v, ctx) => { queryClient.setQueryData(['allocations'], ctx.prev); }, onSettled: () => queryClient.invalidateQueries({ queryKey: ['allocations'] }) });"
  },
  "role_based_ui": {
    "admin_only": ["Edit/Delete allocation buttons", "Project/Resource CRUD"],
    "markers": { "badge": "Admin", "class": "bg-[#E6F7FB] text-[#0B5566] border border-[#B2E7F5]" },
    "testing": "Guard admin actions with data-testid ending in -admin-action"
  },
  "accessibility": {
    "contrast": "All text WCAG AA 4.5:1 minimum; verify greens/yellows with dark text in cells",
    "keyboard": ["Roving tabindex for grid cells", "Enter to open dialog", "Esc to close modal"],
    "aria": ["aria-labels on buttons and timeline cells", "role='table' for grid", "aria-describedby for error text"],
    "focus": "Use focus-visible ring-[#1570EF] with 2px and ring-offset 2"
  },
  "micro_interactions": {
    "principles": ["No transition: all; only specific properties", "Hover shade shifts; subtle scale for primary CTAs", "Sticky headers fade-in shadow on scroll"],
    "examples": {
      "button": "transition-colors duration-150 ease-out",
      "card_enter": "opacity-0 translate-y-2 -> opacity-100 translate-y-0 via Framer Motion",
      "timeline_cell_hover": "ring-1 ring-[#1570EF] ring-offset-0"
    }
  },
  "libraries": {
    "required": [
      { "name": "recharts", "install": "npm i recharts" },
      { "name": "@tanstack/react-query", "install": "npm i @tanstack/react-query" },
      { "name": "date-fns", "install": "npm i date-fns" },
      { "name": "framer-motion", "install": "npm i framer-motion" }
    ],
    "toasts": {
      "component_path": "./components/ui/sonner.jsx",
      "usage": "import { Toaster, toast } from './components/ui/sonner'; <Toaster />; toast.success('Saved');"
    }
  },
  "component_path": {
    "button": "./components/ui/button.jsx",
    "badge": "./components/ui/badge.jsx",
    "card": "./components/ui/card.jsx",
    "dialog": "./components/ui/dialog.jsx",
    "tooltip": "./components/ui/tooltip.jsx",
    "avatar": "./components/ui/avatar.jsx",
    "table": "./components/ui/table.jsx",
    "tabs": "./components/ui/tabs.jsx",
    "select": "./components/ui/select.jsx",
    "input": "./components/ui/input.jsx",
    "textarea": "./components/ui/textarea.jsx",
    "form": "./components/ui/form.jsx",
    "calendar": "./components/ui/calendar.jsx",
    "popover": "./components/ui/popover.jsx",
    "skeleton": "./components/ui/skeleton.jsx",
    "alert": "./components/ui/alert.jsx",
    "sonner": "./components/ui/sonner.jsx",
    "separator": "./components/ui/separator.jsx",
    "sheet": "./components/ui/sheet.jsx"
  },
  "component_guidelines": [
    {
      "name": "Sidebar",
      "structure": ["logo area", "nav items (Dashboard, Resources, Projects, Allocations)", "account switcher"],
      "class": "hidden lg:flex lg:w-[260px] flex-col gap-2 border-r border-[#E6E8EC] bg-white p-3",
      "nav_item": "flex items-center gap-2 rounded-md px-3 py-2 text-sm text-[#0B1220] hover:bg-[#F2F3F5]",
      "data_testid": "sidebar-nav-link"
    },
    {
      "name": "Header",
      "class": "sticky top-0 z-20 bg-white border-b border-[#E6E8EC] px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between",
      "elements": ["search", "date controls", "user menu"],
      "data_testid": "app-header"
    },
    {
      "name": "Allocation Dialog",
      "components": ["dialog", "form", "input", "select", "button"],
      "class": "bg-white border border-[#E6E8EC] rounded-lg",
      "states": ["loading with Skeleton", "error via Alert"],
      "data_testid": "allocation-dialog"
    },
    {
      "name": "Tables",
      "class": "bg-white border border-[#E6E8EC] rounded-lg",
      "row_states": ["hover:bg-[#F8FAFC]", "selected:bg-[#EEF2FF]"]
    }
  ],
  "testing_attributes": {
    "rule": "Every interactive or key informational element must include data-testid using kebab-case role-oriented names",
    "examples": [
      "data-testid=\"login-form\"",
      "data-testid=\"login-form-email-input\"",
      "data-testid=\"login-form-submit-button\"",
      "data-testid=\"timeline-grid\"",
      "data-testid=\"timeline-cell-button\"",
      "data-testid=\"allocation-dialog\"",
      "data-testid=\"capacity-by-role-card\""
    ]
  },
  "image_urls": [
    {
      "category": "decorative-hero-stripe",
      "description": "Wavy yellow/green light abstract usable as faint header texture (do not use behind text-heavy content)",
      "url": "https://images.unsplash.com/photo-1741705054352-b41c1529c4c3?crop=entropy&cs=srgb&fm=jpg&q=85"
    },
    {
      "category": "empty-state-bg",
      "description": "Subtle green-red texture; overlay at 4–6% opacity",
      "url": "https://images.unsplash.com/photo-1747940920030-199da656630c?crop=entropy&cs=srgb&fm=jpg&q=85"
    },
    {
      "category": "presentation-slide",
      "description": "Heatmap-like gradient for marketing slides only (not in-app UI)",
      "url": "https://images.unsplash.com/photo-1762166206312-bfa56b08d690?crop=entropy&cs=srgb&fm=jpg&q=85"
    }
  ],
  "instructions_to_main_agent": [
    "Mobile-first: stack cards; horizontal scroll for timeline; keep sticky resource column",
    "Install Recharts, date-fns, React Query, Framer Motion",
    "Wire TanStack Query Provider at app root",
    "Use shadcn components from ./components/ui only (no native HTML dropdowns/toasts)",
    "Apply classes and tokens from this file; do not apply transition: all",
    "Attach data-testid to every interactive and critical info element",
    "Use shadcn Calendar for date range",
    "Implement optimistic mutations with rollback",
    "Enforce gradient restriction rule strictly"
  ],
  "web_references": [
    {"topic": "Resource heatmap rationale", "url": "https://www.runn.io/blog/resource-heatmap"},
    {"topic": "Linear UI aesthetic", "url": "https://linear.app/now/how-we-redesigned-the-linear-ui"}
  ],
  "notes": [
    "All code examples are in .jsx/.js format (no .tsx)",
    "Avoid purple or saturated gradients; prefer clean neutrals with vibrant semantic colors",
    "Prefer card-based layouts with crisp borders and generous spacing"
  ],
  "general_ui_ux_guidelines": """
    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms
    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text
   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json

 **GRADIENT RESTRICTION RULE**
NEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc
NEVER use dark gradients for logo, testimonial, footer etc
NEVER let gradients cover more than 20% of the viewport.
NEVER apply gradients to text-heavy content or reading areas.
NEVER use gradients on small UI elements (<100px width).
NEVER stack multiple gradient layers in the same viewport.

**ENFORCEMENT RULE:**
    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors

**How and where to use:**
   • Section backgrounds (not content backgrounds)
   • Hero section header content. Eg: dark to light to dark color
   • Decorative overlays and accent elements only
   • Hero section with 2-3 mild color
   • Gradients creation can be done for any angle say horizontal, vertical or diagonal

- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**

</Font Guidelines>

- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. 
   
- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.

- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.
   
- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly
    Eg: - if it implies playful/energetic, choose a colorful scheme
           - if it implies monochrome/minimal, choose a black–white/neutral scheme

**Component Reuse:**
	- Prioritize using pre-existing components from src/components/ui when applicable
	- Create new components that match the style and conventions of existing components when needed
	- Examine existing components to understand the project's component patterns before creating new ones

**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component

**Best Practices:**
	- Use Shadcn/UI as the primary component library for consistency and accessibility
	- Import path: ./components/[component-name]

**Export Conventions:**
	- Components MUST use named exports (export const ComponentName = ...)
	- Pages MUST use default exports (export default function PageName() {...})

**Toasts:**
  - Use `sonner` for toasts" 
  - Sonner component are located in `/app/src/components/ui/sonner.tsx`

Use 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals."""
}
