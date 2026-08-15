/**
 * useEnabledModules — React hook exposing the current tenant's module toggles.
 *
 * Fetches `GET /api/tenant/modules` once per session, caches with React Query,
 * and returns:
 *   {
 *     modules: { projects: true, wbs: false, ... },
 *     isEnabled: (key) => bool,       // convenience checker (missing key -> true fallback)
 *     tenantSlug: 'ddconsult',
 *     isMultiTenant: false,
 *     isLoading: boolean,
 *   }
 *
 * When flag=off (backward compat), everything is enabled.
 * When a module is not in the map (e.g., freshly-added module), we default to
 * enabled to avoid accidentally hiding features on legacy tenants.
 */
import { useQuery } from '@tanstack/react-query';
import { getMyTenantModules } from '../api';

export function useEnabledModules() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['tenant-modules'],
    queryFn: async () => {
      try {
        const r = await getMyTenantModules();
        return r.data;
      } catch (e) {
        // If endpoint fails (e.g. not deployed yet), fail open — everything enabled.
        console.warn('[useEnabledModules] Failed to fetch modules; failing open', e);
        return { modules: {}, multi_tenant_enabled: false, tenant_slug: null };
      }
    },
    staleTime: 5 * 60 * 1000,  // 5 minutes
    refetchOnWindowFocus: false,
    retry: 1,
  });

  const modules = data?.modules || {};

  const isEnabled = (key) => {
    // Default: if key not present in map, treat as enabled (backward-compat safe).
    if (!(key in modules)) return true;
    return !!modules[key];
  };

  return {
    modules,
    isEnabled,
    tenantSlug: data?.tenant_slug || null,
    isMultiTenant: !!data?.multi_tenant_enabled,
    isLoading,
    error,
  };
}

/**
 * Module → route path mapping (for sidebar & route-guard filtering).
 * Keep in sync with backend `MODULES_CATALOG` in /app/backend/platform_db.py.
 */
export const MODULE_TO_ROUTES = {
  projects: ['/projects', '/projects/:id'],
  resources: ['/resources'],
  allocations: ['/allocations', '/my-allocations'],
  timesheets: ['/my-timesheets', '/manage-timesheets', '/timesheets/reports'],
  wbs: [],  // Nested inside ProjectDetail tab — gated at tab level, not route
  milestones: [],  // Nested inside WBS
  risks: [],  // Nested inside ProjectDetail
  status_updates: [],  // Nested inside ProjectDetail
  baselines: [],  // Nested inside ProjectDetail
  reports: ['/reports', '/projects/:id/report'],
  client_portal: ['/portal', '/portal/:token'],
  ai_copilot: [],  // Floating chat panel — gated at component level
  ai_intelligence: ['/ai-intelligence'],
  ai_productivity: [],  // Nested (Kickoff wizard button on Projects page)
  knowledge_base: [],  // Nested (AI Chat KB integration)
  hubspot_integration: [],  // Settings integrations tab
  mcp_server: [],  // Settings integrations tab
  portfolio: ['/portfolio'],  // Portfolio is a top-level view — mapped to projects module
};

/**
 * Sidebar item → module key mapping.
 * Used by Layout.js to filter navigation items.
 * Keep in sync with the modules catalog.
 *
 * `null` module means "always visible" (e.g. Dashboard, Help, Users management).
 */
export const NAV_ITEM_TO_MODULE = {
  '/': null,                   // Dashboard — always visible
  '/resources': 'resources',
  '/projects': 'projects',
  '/portfolio': 'projects',    // Portfolio depends on Projects module
  '/allocations': 'allocations',
  '/my-allocations': 'allocations',
  '/my-timesheets': 'timesheets',
  '/manage-timesheets': 'timesheets',
  '/timesheets/reports': 'timesheets',
  '/reports': 'reports',
  '/leaves': null,             // Leaves is a core people-management feature, always on
  '/holidays': null,           // Holidays is core, always on
  '/users': null,              // User management is core admin function
  '/settings': null,           // Settings always visible to super_admin
  '/help': null,               // Help always visible
  '/ai-intelligence': 'ai_intelligence',
};
