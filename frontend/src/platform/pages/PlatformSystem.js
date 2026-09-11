import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getMigrationsStatus, runAllMigrations, runTenantMigrations } from '../api';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui/table';
import { Database, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

const PlatformSystem = () => {
  const queryClient = useQueryClient();
  const [runningTenants, setRunningTenants] = useState(new Set());

  // Fetch migrations status
  const { data: statusData, isLoading } = useQuery({
    queryKey: ['migrationsStatus'],
    queryFn: async () => {
      const response = await getMigrationsStatus();
      return response.data;
    },
  });

  // Mutation to run all migrations
  const runAllMutation = useMutation({
    mutationFn: runAllMigrations,
    onSuccess: (response) => {
      const data = response.data;
      const tenantCount = data.tenants?.length || 0;
      toast.success(`Applied migrations across ${tenantCount} tenant${tenantCount !== 1 ? 's' : ''}`);
      queryClient.invalidateQueries(['migrationsStatus']);
    },
  });

  // Mutation to run single tenant migrations
  const runTenantMutation = useMutation({
    mutationFn: ({ slug }) => runTenantMigrations(slug),
    onMutate: ({ slug }) => {
      setRunningTenants((prev) => new Set(prev).add(slug));
    },
    onSuccess: (response, { slug }) => {
      const data = response.data;
      const appliedCount = data.applied?.length || 0;
      toast.success(`Applied ${appliedCount} migration${appliedCount !== 1 ? 's' : ''} for ${slug}`);
      queryClient.invalidateQueries(['migrationsStatus']);
    },
    onError: (error, { slug }) => {
      // Error already shown by interceptor
    },
    onSettled: (data, error, { slug }) => {
      setRunningTenants((prev) => {
        const next = new Set(prev);
        next.delete(slug);
        return next;
      });
    },
  });

  const handleRunAll = () => {
    runAllMutation.mutate();
  };

  const handleRunTenant = (slug) => {
    runTenantMutation.mutate({ slug });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  const platformPending = statusData?.platform?.pending || [];
  const platformApplied = statusData?.platform?.applied || 0;
  const platformBehind = platformPending.length > 0;
  const latestVersion = statusData?.latest_version || 0;
  const tenants = statusData?.tenants || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">System & Migrations</h1>
        <p className="text-slate-400">
          Keep every tenant&apos;s database in sync with the latest app version.
        </p>
      </div>

      {/* Summary card */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Database className="h-5 w-5 text-indigo-500" />
            Migration Status
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-400">Latest Version</p>
              <p className="text-2xl font-bold text-white">v{latestVersion}</p>
            </div>
            <div>
              <p className="text-sm text-slate-400">Platform Applied</p>
              <div className="flex items-center gap-2">
                <p className="text-2xl font-bold text-white">v{platformApplied}</p>
                {platformBehind && (
                  <Badge variant="outline" className="border-amber-700 text-amber-400 bg-amber-900/20">
                    Platform behind
                  </Badge>
                )}
              </div>
            </div>
          </div>

          {platformBehind && (
            <div className="flex items-start gap-2 p-3 bg-amber-900/10 border border-amber-800/30 rounded-lg">
              <AlertCircle className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-amber-300">
                Platform has {platformPending.length} pending migration{platformPending.length !== 1 ? 's' : ''}.
                Run migrations to update.
              </p>
            </div>
          )}

          <Button
            onClick={handleRunAll}
            disabled={runAllMutation.isPending}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white"
            data-testid="run-all-migrations-button"
          >
            {runAllMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Running...
              </>
            ) : (
              'Run all migrations'
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Tenants table */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-white">Tenant Migrations</CardTitle>
        </CardHeader>
        <CardContent>
          {tenants.length === 0 ? (
            <div className="text-center py-8 text-slate-400">
              No tenants found
            </div>
          ) : (
            <Table data-testid="migrations-status-table">
              <TableHeader>
                <TableRow className="border-slate-800 hover:bg-slate-800/50">
                  <TableHead className="text-slate-300">Name</TableHead>
                  <TableHead className="text-slate-300">Slug</TableHead>
                  <TableHead className="text-slate-300">Applied Version</TableHead>
                  <TableHead className="text-slate-300">Status</TableHead>
                  <TableHead className="text-slate-300"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tenants.map((tenant) => {
                  const isRunning = runningTenants.has(tenant.slug);
                  const pendingCount = tenant.pending?.length || 0;
                  const hasError = tenant.status === 'error';
                  const isUpToDate = pendingCount === 0 && !hasError;

                  return (
                    <TableRow
                      key={tenant.slug}
                      className="border-slate-800 hover:bg-slate-800/50"
                    >
                      <TableCell className="text-slate-200 font-medium">
                        {tenant.name}
                      </TableCell>
                      <TableCell className="text-slate-400 font-mono text-sm">
                        {tenant.slug}
                      </TableCell>
                      <TableCell className="text-slate-200">
                        v{tenant.applied || 0}
                      </TableCell>
                      <TableCell>
                        {hasError ? (
                          <Badge variant="outline" className="border-red-700 text-red-400 bg-red-900/20">
                            Error
                          </Badge>
                        ) : isUpToDate ? (
                          <Badge variant="outline" className="border-green-700 text-green-400 bg-green-900/20">
                            <CheckCircle className="h-3 w-3 mr-1" />
                            Up to date
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="border-amber-700 text-amber-400 bg-amber-900/20">
                            {pendingCount} pending
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleRunTenant(tenant.slug)}
                          disabled={isRunning}
                          className="border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white"
                          data-testid={`run-tenant-migrations-${tenant.slug}`}
                        >
                          {isRunning ? (
                            <>
                              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                              Running
                            </>
                          ) : (
                            'Run'
                          )}
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default PlatformSystem;
