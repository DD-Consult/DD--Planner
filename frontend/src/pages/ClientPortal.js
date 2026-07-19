import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getProjects, getMe } from '../api';
import { format, differenceInDays } from 'date-fns';
import { Calendar, Building2, TrendingUp, FileText } from 'lucide-react';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';

const ClientPortal = () => {
  const navigate = useNavigate();
  const { data: user } = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const response = await getMe();
      return response.data;
    },
  });

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await getProjects();
      return response.data;
    },
  });

  const calculateProgress = (startDate, endDate) => {
    const start = new Date(startDate);
    const end = new Date(endDate);
    const today = new Date();
    
    const totalDays = differenceInDays(end, start);
    const elapsedDays = differenceInDays(today, start);
    
    const progress = Math.max(0, Math.min(100, (elapsedDays / totalDays) * 100));
    return Math.round(progress);
  };

  const getStatusColor = (status) => {
    const colors = {
      Active: 'bg-[#16B364] text-white',
      Pipeline: 'bg-[#F4B740] text-white',
      Completed: 'bg-[#667085] text-white',
    };
    return colors[status] || 'bg-[#667085] text-white';
  };

  const handleViewReport = (projectId) => {
    navigate(`/projects/${projectId}/report?period=whole-project`);
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/3 mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
        </div>
        <div className="text-center py-12 text-[#667085]">
          <p>Loading your projects...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-semibold" style={{ fontFamily: 'Space Grotesk' }}>
          Welcome to Your Projects
        </h1>
        <p className="text-sm text-[#667085] mt-1">
          {user?.email && `Logged in as: ${user.email}`}
          {user?.company_name && ` • ${user.company_name}`}
        </p>
      </div>

      {/* Projects Grid */}
      {!projects || projects.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <Building2 size={48} className="mx-auto mb-4 text-[#98A2B3]" />
            <h3 className="text-lg font-medium mb-2">No projects assigned</h3>
            <p className="text-[#667085]">
              No projects have been assigned to your account yet. Please contact your project manager for access.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {projects.map((project) => {
            const progress = calculateProgress(project.start_date, project.end_date);
            return (
              <Card
                key={project.id}
                className="hover:shadow-lg transition-all duration-200 border-[#E6E8EC]"
              >
                <CardContent className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <h3 className="text-xl font-semibold mb-2" style={{ fontFamily: 'Space Grotesk' }}>
                        {project.name}
                      </h3>
                      <p className="text-sm text-[#667085] mb-3">
                        Client: {project.client_name}
                      </p>
                    </div>
                    <Badge className={getStatusColor(project.status)}>
                      {project.status}
                    </Badge>
                  </div>

                  <div className="space-y-4">
                    {/* Timeline */}
                    <div className="flex items-center gap-2 text-sm text-[#667085]">
                      <Calendar size={16} />
                      <span>
                        {format(new Date(project.start_date), 'MMM d, yyyy')} -{' '}
                        {format(new Date(project.end_date), 'MMM d, yyyy')}
                      </span>
                    </div>

                    {/* Progress Bar */}
                    {project.status === 'Active' && (
                      <div>
                        <div className="flex items-center justify-between text-sm mb-2">
                          <span className="text-[#667085]">Timeline Progress</span>
                          <span className="font-medium text-[#1570EF]">{progress}%</span>
                        </div>
                        <div className="w-full bg-[#F1F3F4] rounded-full h-2">
                          <div
                            className="bg-[#1570EF] h-2 rounded-full transition-all duration-300"
                            style={{ width: `${progress}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {/* Action Button */}
                    <div className="pt-2">
                      <Button
                        onClick={() => handleViewReport(project.id)}
                        className="w-full bg-[#1570EF] hover:bg-[#0E5FD9] text-white"
                        data-testid={`view-report-btn-${project.id}`}
                      >
                        <FileText size={16} className="mr-2" />
                        View Project Report
                      </Button>
                    </div>

                    {/* Project Summary (if available) */}
                    {project.summary && (
                      <div className="pt-4 border-t border-[#E6E8EC]">
                        <p className="text-sm text-[#374151] leading-relaxed">
                          {project.summary.length > 150
                            ? `${project.summary.substring(0, 150)}...`
                            : project.summary
                          }
                        </p>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Summary Section */}
      {projects && projects.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="bg-gradient-to-r from-[#16B364] to-[#16B364]/80 text-white">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <TrendingUp size={24} />
                <div>
                  <div className="text-sm opacity-90">Active Projects</div>
                  <div className="text-2xl font-bold">
                    {projects.filter(p => p.status === 'Active').length}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-r from-[#F4B740] to-[#F4B740]/80 text-white">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <Calendar size={24} />
                <div>
                  <div className="text-sm opacity-90">In Pipeline</div>
                  <div className="text-2xl font-bold">
                    {projects.filter(p => p.status === 'Pipeline').length}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-r from-[#667085] to-[#667085]/80 text-white">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <Building2 size={24} />
                <div>
                  <div className="text-sm opacity-90">Completed</div>
                  <div className="text-2xl font-bold">
                    {projects.filter(p => p.status === 'Completed').length}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default ClientPortal;