import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getAuditLog } from '../api';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui/table';
import { Search } from 'lucide-react';
import { format, parseISO } from 'date-fns';

const PlatformAuditLog = () => {
  const [tenantFilter, setTenantFilter] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [limit] = useState(100);

  const { data: auditLog, isLoading } = useQuery({
    queryKey: ['platformAuditLog', { tenantFilter, actionFilter, limit }],
    queryFn: async () => {
      const params = { limit };
      if (tenantFilter) params.tenant_slug = tenantFilter;
      if (actionFilter) params.action = actionFilter;
      
      const response = await getAuditLog(params);
      return response.data;
    },
  });

  // Extract unique actions for filter dropdown
  const uniqueActions = React.useMemo(() => {
    if (!auditLog) return [];
    const actions = new Set(auditLog.map((entry) => entry.action));
    return Array.from(actions).sort();
  }, [auditLog]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2" data-testid="audit-log-title">
          Audit Log
        </h1>
        <p className="text-slate-400">Cross-tenant activity tracking</p>
      </div>

      {/* Filters */}
      <Card className="bg-slate-900 border-slate-800">
        <CardContent className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label className="text-slate-300 text-sm mb-2 block">Tenant Slug</Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-500" />
                <Input
                  placeholder="Filter by tenant slug..."
                  value={tenantFilter}
                  onChange={(e) => setTenantFilter(e.target.value)}
                  className="pl-10 bg-slate-800 border-slate-700 text-white placeholder:text-slate-500"
                  data-testid="audit-tenant-filter"
                />
              </div>
            </div>

            <div>
              <Label className="text-slate-300 text-sm mb-2 block">Action</Label>
              <Select value={actionFilter} onValueChange={setActionFilter}>
                <SelectTrigger className="bg-slate-800 border-slate-700 text-white" data-testid="audit-action-filter">
                  <SelectValue placeholder="All actions" />
                </SelectTrigger>
                <SelectContent className="bg-slate-800 border-slate-700">
                  <SelectItem value="">All actions</SelectItem>
                  {uniqueActions.map((action) => (
                    <SelectItem key={action} value={action} className="text-white">
                      {action}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Audit Table */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-white">Activity Log</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-slate-400">Loading audit log...</p>
            </div>
          ) : !auditLog || auditLog.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-slate-500">No audit entries found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-slate-800 hover:bg-slate-800/50">
                    <TableHead className="text-slate-400">Time</TableHead>
                    <TableHead className="text-slate-400">Actor</TableHead>
                    <TableHead className="text-slate-400">Action</TableHead>
                    <TableHead className="text-slate-400">Tenant</TableHead>
                    <TableHead className="text-slate-400">Details</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {auditLog.map((entry, idx) => (
                    <TableRow key={entry.id || idx} className="border-slate-800 hover:bg-slate-800/50">
                      <TableCell className="text-slate-300 text-sm whitespace-nowrap">
                        {format(parseISO(entry.created_at), 'MMM d, yyyy HH:mm:ss')}
                      </TableCell>
                      <TableCell className="text-slate-300 text-sm">{entry.actor_email}</TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={getActionBadgeClass(entry.action)}
                        >
                          {entry.action}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-slate-300 text-sm font-mono">
                        {entry.tenant_slug || '—'}
                      </TableCell>
                      <TableCell className="text-slate-400 text-sm max-w-md">
                        <div className="truncate" title={JSON.stringify(entry.details)}>
                          {entry.details ? JSON.stringify(entry.details) : '—'}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {auditLog && auditLog.length >= limit && (
        <p className="text-sm text-slate-500 text-center">
          Showing the most recent {limit} entries
        </p>
      )}
    </div>
  );
};

// Helper to get badge styling based on action type
const getActionBadgeClass = (action) => {
  if (action.includes('create')) {
    return 'border-green-700 text-green-400 bg-green-900/20';
  }
  if (action.includes('delete')) {
    return 'border-red-700 text-red-400 bg-red-900/20';
  }
  if (action.includes('update') || action.includes('toggle')) {
    return 'border-blue-700 text-blue-400 bg-blue-900/20';
  }
  if (action.includes('impersonate')) {
    return 'border-amber-700 text-amber-400 bg-amber-900/20';
  }
  return 'border-indigo-700 text-indigo-400 bg-indigo-900/20';
};

export default PlatformAuditLog;
