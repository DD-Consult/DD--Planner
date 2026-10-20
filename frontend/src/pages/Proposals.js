import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { 
  getProposals, 
  createProposal, 
  deleteProposal, 
  sendProposal,
  confirmProposal 
} from '../api';
import { format, formatDistanceToNow } from 'date-fns';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '../components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../components/ui/tooltip';
import { 
  Plus, 
  Eye, 
  Copy, 
  CheckCircle2, 
  Trash2, 
  FileText 
} from 'lucide-react';
import { Card, CardContent } from '../components/ui/card';

const Proposals = () => {
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isConfirmDialogOpen, setIsConfirmDialogOpen] = useState(false);
  const [confirmingProposal, setConfirmingProposal] = useState(null);
  const [confirmResult, setConfirmResult] = useState(null);
  const [newProposal, setNewProposal] = useState({
    client_name: '',
    proposal_title: '',
  });
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Fetch proposals
  const { data: proposals = [], isLoading } = useQuery({
    queryKey: ['proposals'],
    queryFn: async () => {
      const response = await getProposals();
      return response.data;
    },
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: createProposal,
    onSuccess: (response) => {
      queryClient.invalidateQueries(['proposals']);
      setIsCreateDialogOpen(false);
      setNewProposal({ client_name: '', proposal_title: '' });
      toast.success('Proposal created');
      // Navigate to builder
      navigate(`/proposals/${response.data.id}/builder`);
    },
    onError: () => {
      toast.error('Failed to create proposal');
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: deleteProposal,
    onSuccess: () => {
      queryClient.invalidateQueries(['proposals']);
      toast.success('Proposal deleted');
    },
    onError: () => {
      toast.error('Failed to delete proposal');
    },
  });

  // Send/get link mutation
  const sendMutation = useMutation({
    mutationFn: sendProposal,
    onSuccess: (response) => {
      queryClient.invalidateQueries(['proposals']);
      const link = response.data.proposal_link;
      navigator.clipboard.writeText(link);
      toast.success(`Link copied to clipboard${response.data.email_sent ? ' and email sent!' : '!'}`);
    },
    onError: () => {
      toast.error('Failed to send proposal');
    },
  });

  // Confirm mutation
  const confirmMutation = useMutation({
    mutationFn: confirmProposal,
    onSuccess: (response) => {
      queryClient.invalidateQueries(['proposals']);
      setConfirmResult(response.data);
      setIsConfirmDialogOpen(true);
      toast.success('Proposal confirmed!');
    },
    onError: () => {
      toast.error('Failed to confirm proposal');
    },
  });

  const handleCreate = () => {
    createMutation.mutate(newProposal);
  };

  const handleDelete = (id) => {
    if (window.confirm('Delete this proposal? This cannot be undone.')) {
      deleteMutation.mutate(id);
    }
  };

  const handleCopyLink = (proposal) => {
    if (proposal.status === 'Draft') {
      // Send first to generate link
      sendMutation.mutate(proposal.id);
    } else {
      // Just copy existing link
      const link = `${window.location.origin}/proposal/${proposal.public_token}`;
      navigator.clipboard.writeText(link);
      toast.success('Link copied to clipboard');
    }
  };

  const handleConfirm = (proposal) => {
    setConfirmingProposal(proposal);
    confirmMutation.mutate(proposal.id);
  };

  const getStatusBadge = (status) => {
    const variants = {
      Draft: 'bg-slate-100 text-slate-700 hover:bg-slate-100',
      Sent: 'bg-blue-100 text-blue-700 hover:bg-blue-100',
      Viewed: 'bg-indigo-100 text-indigo-700 hover:bg-indigo-100',
      Accepted: 'bg-amber-100 text-amber-700 hover:bg-amber-100',
      Confirmed: 'bg-green-100 text-green-700 hover:bg-green-100',
      Declined: 'bg-red-100 text-red-700 hover:bg-red-100',
      Expired: 'bg-slate-100 text-slate-500 hover:bg-slate-100',
    };
    return (
      <Badge className={variants[status] || variants.Draft} data-testid={`status-badge-${status}`}>
        {status === 'Accepted' ? 'Accepted — awaiting confirmation' : status}
      </Badge>
    );
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
          <div>
            <h1 className="text-3xl font-bold text-[#0B1220]">Proposals</h1>
            <p className="text-[#667085] mt-1">Create and send AI-guided secure client proposals</p>
          </div>
          <Button
            onClick={() => setIsCreateDialogOpen(true)}
            className="bg-[#1570EF] hover:bg-[#1565D8] text-white"
            data-testid="new-proposal-button"
          >
            <Plus className="mr-2 h-4 w-4" />
            New Proposal
          </Button>
        </div>

        {/* Empty State */}
        {proposals.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-16">
              <FileText className="h-16 w-16 text-slate-300 mb-4" />
              <h3 className="text-xl font-semibold text-[#0B1220] mb-2">No proposals yet</h3>
              <p className="text-[#667085] text-center mb-6 max-w-md">
                Get started by creating your first AI-guided proposal. The assistant will help you draft compelling client proposals in minutes.
              </p>
              <Button
                onClick={() => setIsCreateDialogOpen(true)}
                className="bg-[#1570EF] hover:bg-[#1565D8] text-white"
                data-testid="empty-state-create-button"
              >
                <Plus className="mr-2 h-4 w-4" />
                Create First Proposal
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
                    <TableHead>Client</TableHead>
                    <TableHead>Proposal Title</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Path</TableHead>
                    <TableHead>Last Activity</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {proposals.map((proposal) => (
                    <TableRow key={proposal.id} data-testid={`proposal-row-${proposal.id}`}>
                      <TableCell className="font-medium">{proposal.client_name || '—'}</TableCell>
                      <TableCell>{proposal.proposal_title || 'Untitled'}</TableCell>
                      <TableCell>{getStatusBadge(proposal.status)}</TableCell>
                      <TableCell>
                        {proposal.accepted_path ? (
                          <span className="text-sm font-medium text-[#1570EF]">
                            Path {proposal.accepted_path.toUpperCase()}
                          </span>
                        ) : (
                          '—'
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-[#667085]">
                        {proposal.last_client_activity
                          ? formatDistanceToNow(new Date(proposal.last_client_activity), { addSuffix: true })
                          : '—'}
                      </TableCell>
                      <TableCell className="text-sm text-[#667085]">
                        {format(new Date(proposal.created_at), 'MMM d, yyyy')}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => navigate(`/proposals/${proposal.id}/builder`)}
                                data-testid={`open-builder-${proposal.id}`}
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Open builder</TooltipContent>
                          </Tooltip>

                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleCopyLink(proposal)}
                                data-testid={`copy-link-${proposal.id}`}
                              >
                                <Copy className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                              {proposal.status === 'Draft' ? 'Send & copy link' : 'Copy link'}
                            </TooltipContent>
                          </Tooltip>

                          {proposal.status === 'Accepted' && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleConfirm(proposal)}
                                  className="text-green-600 hover:text-green-700 hover:bg-green-50"
                                  data-testid={`confirm-${proposal.id}`}
                                >
                                  <CheckCircle2 className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Confirm & provision</TooltipContent>
                            </Tooltip>
                          )}

                          {proposal.status === 'Draft' && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleDelete(proposal.id)}
                                  className="text-red-600 hover:text-red-700 hover:bg-red-50"
                                  data-testid={`delete-${proposal.id}`}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Delete</TooltipContent>
                            </Tooltip>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}

        {/* Create Dialog */}
        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogContent data-testid="create-proposal-dialog">
            <DialogHeader>
              <DialogTitle>New Proposal</DialogTitle>
              <DialogDescription>
                Create a new client proposal. You can fill in more details in the builder.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="client_name">Client Name (optional)</Label>
                <Input
                  id="client_name"
                  value={newProposal.client_name}
                  onChange={(e) => setNewProposal({ ...newProposal, client_name: e.target.value })}
                  placeholder="Acme Corp"
                  data-testid="client-name-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="proposal_title">Proposal Title (optional)</Label>
                <Input
                  id="proposal_title"
                  value={newProposal.proposal_title}
                  onChange={(e) => setNewProposal({ ...newProposal, proposal_title: e.target.value })}
                  placeholder="Digital Transformation Initiative"
                  data-testid="proposal-title-input"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setIsCreateDialogOpen(false)}
                data-testid="cancel-create-button"
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreate}
                disabled={createMutation.isPending}
                className="bg-[#1570EF] hover:bg-[#1565D8] text-white"
                data-testid="create-submit-button"
              >
                {createMutation.isPending ? 'Creating...' : 'Create & Open Builder'}
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Confirm Success Dialog */}
        <Dialog open={isConfirmDialogOpen} onOpenChange={setIsConfirmDialogOpen}>
          <DialogContent data-testid="confirm-success-dialog">
            <DialogHeader>
              <DialogTitle className="text-green-600">Proposal Confirmed!</DialogTitle>
              <DialogDescription>
                The project has been created and the client login provisioned.
              </DialogDescription>
            </DialogHeader>
            {confirmResult && (
              <div className="space-y-4 py-4">
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <p className="text-sm text-green-800">
                    <strong>Project created:</strong> ID {confirmResult.project_id}
                  </p>
                  <p className="text-sm text-green-800 mt-1">
                    <strong>Client user:</strong> ID {confirmResult.client_user_id}
                  </p>
                  {confirmResult.magic_link_sent && (
                    <p className="text-sm text-green-800 mt-1">
                      ✓ Magic link email sent to client
                    </p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label>Client Report Link</Label>
                  <div className="flex gap-2">
                    <Input
                      value={confirmResult.report_link}
                      readOnly
                      className="font-mono text-xs"
                      data-testid="report-link-input"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        navigator.clipboard.writeText(confirmResult.report_link);
                        toast.success('Link copied');
                      }}
                      data-testid="copy-report-link-button"
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            )}
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setIsConfirmDialogOpen(false)}
                data-testid="close-confirm-dialog-button"
              >
                Close
              </Button>
              {confirmResult && (
                <Button
                  onClick={() => navigate(`/projects/${confirmResult.project_id}`)}
                  className="bg-[#1570EF] hover:bg-[#1565D8] text-white"
                  data-testid="open-project-button"
                >
                  Open Project
                </Button>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </TooltipProvider>
  );
};

export default Proposals;
