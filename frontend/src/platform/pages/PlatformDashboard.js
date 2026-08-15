import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getDashboardStats } from '../api';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui/table';
import { Building2, Users, Package, Activity } from 'lucide-react';
import { format, parseISO } from 'date-fns';

const PlatformDashboard = () => {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['platformDashboardStats'],
    queryFn: async () => {
      const response = await getDashboardStats();
      return response.data;
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-slate-400">Loading dashboard...</div>
      </div>
    );
  }

  const kpis = [
    {
      label: 'Total Tenants',
      value: stats?.tenants?.total || 0,
      icon: Building2,
      color: 'text-indigo-400',
      bgColor: 'bg-indigo-600/20',
    },
    {
      label: 'Active Tenants',
      value: stats?.tenants?.active || 0,
      icon: Activity,
      color: 'text-green-400',
      bgColor: 'bg-green-600/20',
    },
    {
      label: 'Suspended',
      value: stats?.tenants?.suspended || 0,
      icon: Building2,
      color: 'text-amber-400',
      bgColor: 'bg-amber-600/20',
    },
    {
      label: 'Platform Users',
      value: stats?.platform_users || 0,
      icon: Users,
      color: 'text-blue-400',
      bgColor: 'bg-blue-600/20',
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2" data-testid="dashboard-title">
          Platform Dashboard
        </h1>
        <p className="text-slate-400">Monitor and manage all tenants</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {kpis.map((kpi, idx) => (
          <Card key={idx} className="bg-slate-900 border-slate-800" data-testid={`kpi-${kpi.label.toLowerCase().replace(' ', '-')}`}>
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-slate-400 mb-1">{kpi.label}</p>
                  <p className="text-3xl font-bold text-white">{kpi.value}</p>
                </div>
                <div className={`p-3 rounded-lg ${kpi.bgColor}`}>
                  <kpi.icon className={`h-6 w-6 ${kpi.color}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Module Stats */}
      {stats?.modules && (
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Package className="h-5 w-5 text-indigo-400" />
              Module Usage
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {Object.entries(stats.modules).map(([key, counts]) => (
                <div key={key} className="p-4 bg-slate-800 rounded-lg">
                  <p className="text-sm text-slate-400 mb-2">{key.replace(/_/g, ' ')}</p>
                  <div className="flex items-baseline gap-2">
                    <span className="text-2xl font-bold text-green-400">{counts.enabled}</span>
                    <span className="text-sm text-slate-500">/ {counts.enabled + counts.disabled}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent Audit Log */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader>
          <CardTitle className="text-white">Recent Activity</CardTitle>
        </CardHeader>
        <CardContent>
          {stats?.recent_audit && stats.recent_audit.length > 0 ? (
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
                {stats.recent_audit.map((item, idx) => (
                  <TableRow key={idx} className="border-slate-800 hover:bg-slate-800/50">
                    <TableCell className="text-slate-300 text-sm">
                      {format(parseISO(item.created_at), 'MMM d, HH:mm')}
                    </TableCell>
                    <TableCell className="text-slate-300 text-sm">{item.actor_email}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="border-indigo-700 text-indigo-400 bg-indigo-900/20">
                        {item.action}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-slate-300 text-sm">{item.tenant_slug || '—'}</TableCell>
                    <TableCell className="text-slate-400 text-sm max-w-xs truncate">
                      {item.details ? JSON.stringify(item.details) : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-slate-500 text-center py-8">No recent activity</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default PlatformDashboard;
