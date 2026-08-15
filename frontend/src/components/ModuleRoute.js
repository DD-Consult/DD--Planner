/**
 * ModuleRoute — route guard that checks if a module is enabled for the tenant.
 *
 * Usage:
 *   <Route path="/timesheets" element={
 *     <ModuleRoute module="timesheets">
 *       <MyTimesheets />
 *     </ModuleRoute>
 *   } />
 *
 * If the module is disabled, renders a friendly "module not enabled" page
 * instead of redirecting (redirect can loop; a static page is safer).
 */
import React from 'react';
import { useEnabledModules } from '../hooks/useEnabledModules';
import { Link } from 'react-router-dom';
import { Ban, ArrowLeft } from 'lucide-react';

export default function ModuleRoute({ module, children }) {
  const { isEnabled, isLoading, tenantSlug } = useEnabledModules();

  if (isLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center text-slate-500 text-sm">
        Loading...
      </div>
    );
  }

  if (!isEnabled(module)) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center p-8" data-testid="module-disabled-page">
        <div className="max-w-md text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-amber-100 rounded-full mb-4">
            <Ban className="w-8 h-8 text-amber-600" />
          </div>
          <h1 className="text-2xl font-semibold text-slate-900 mb-2">
            Module Not Enabled
          </h1>
          <p className="text-slate-600 mb-6">
            The <span className="font-mono bg-slate-100 px-2 py-0.5 rounded text-sm">{module}</span> module
            is not enabled for {tenantSlug ? `the "${tenantSlug}" workspace` : 'this workspace'}.
            Please contact your administrator if you need access to this feature.
          </p>
          <Link
            to="/"
            className="inline-flex items-center gap-2 px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-800 transition"
            data-testid="module-disabled-back-btn"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  return children;
}
