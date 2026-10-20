import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  getProposalTemplates,
  deleteProposalTemplate,
  createProposalFromTemplate,
} from '../api';
import { format } from 'date-fns';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { Card, CardContent } from '../components/ui/card';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../components/ui/tooltip';
import { ArrowLeft, FileText, Trash2, Plus } from 'lucide-react';

const ProposalTemplates = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Fetch templates
  const { data: templates = [], isLoading } = useQuery({
    queryKey: ['proposalTemplates'],
    queryFn: async () => {
      const response = await getProposalTemplates();
      return response.data;
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: deleteProposalTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries(['proposalTemplates']);
      toast.success('Template deleted');
    },
    onError: () => {
      toast.error('Failed to delete template');
    },
  });

  // Create proposal from template mutation
  const createFromTemplateMutation = useMutation({
    mutationFn: createProposalFromTemplate,
    onSuccess: (response) => {
      queryClient.invalidateQueries(['proposals']);
      toast.success('Proposal created from template');
      navigate(`/proposals/${response.data.id}/builder`);
    },
    onError: (err) => {
      toast.error(err?.response?.data?.detail || 'Failed to create proposal');
    },
  });

  const handleDelete = (id) => {
    if (window.confirm('Delete this template? This cannot be undone.')) {
      deleteMutation.mutate(id);
    }
  };

  const handleCreateFromTemplate = (templateId) => {
    createFromTemplateMutation.mutate({ template_id: templateId });
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-slate-200 rounded w-48"></div>
          <div className="h-64 bg-slate-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <TooltipProvider>
      <div className="p-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/proposals')}
              data-testid="back-to-proposals-btn"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Proposals
            </Button>
            <div>
              <h1 className="text-3xl font-bold text-[#0B1220]">Proposal Templates</h1>
              <p className="text-[#667085] mt-1">Reusable proposal templates for faster creation</p>
            </div>
          </div>
        </div>

        {/* Empty State */}
        {templates.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-16">
              <FileText className="h-16 w-16 text-slate-300 mb-4" />
              <h3 className="text-xl font-semibold text-[#0B1220] mb-2">No templates yet</h3>
              <p className="text-[#667085] text-center mb-6 max-w-md">
                Templates are created from existing proposals. Open a proposal in the builder and click &quot;Save as template&quot; to create one.
              </p>
              <Button
                onClick={() => navigate('/proposals')}
                className="bg-[#1570EF] hover:bg-[#1565D8] text-white"
              >
                Go to Proposals
              </Button>
            </CardContent>
          </Card>
        ) : (
          /* Table */
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Created By</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {templates.map((template) => (
                    <TableRow key={template.id} data-testid={`template-row-${template.id}`}>
                      <TableCell className="font-medium">{template.name}</TableCell>
                      <TableCell className="text-sm text-[#667085]">
                        {template.description || '—'}
                      </TableCell>
                      <TableCell className="text-sm">{template.created_by || '—'}</TableCell>
                      <TableCell className="text-sm text-[#667085]">
                        {format(new Date(template.created_at), 'MMM d, yyyy')}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleCreateFromTemplate(template.id)}
                                disabled={createFromTemplateMutation.isPending}
                                data-testid={`new-from-template-${template.id}`}
                              >
                                <Plus className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>New proposal from this</TooltipContent>
                          </Tooltip>

                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDelete(template.id)}
                                className="text-red-600 hover:text-red-700 hover:bg-red-50"
                                data-testid={`delete-template-${template.id}`}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Delete</TooltipContent>
                          </Tooltip>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>
    </TooltipProvider>
  );
};

export default ProposalTemplates;
