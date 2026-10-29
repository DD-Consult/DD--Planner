import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { 
  getProposals, 
  createProposal, 
  createProposalFromProject,
  getProjects,
  deleteProposal, 
  sendProposal,
  confirmProposal,
  getProposalTemplates,
  createProposalFromTemplate,
  createProposalFromDocument,
  listDriveDocs,
  createProposalFromDrive,
  listHubspotDeals,
  createProposalFromDeal
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
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
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
  FileText,
  Loader2
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
  const [createMode, setCreateMode] = useState('blank'); // 'blank' | 'project' | 'template' | 'document' | 'drive' | 'hubspot'
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [uploadFile, setUploadFile] = useState(null);
  const [driveFiles, setDriveFiles] = useState([]);
  const [driveLoadingList, setDriveLoadingList] = useState(false);
  const [driveError, setDriveError] = useState('');
  const [selectedDriveDocId, setSelectedDriveDocId] = useState('');
  const [driveUrl, setDriveUrl] = useState('');
  const [hubspotDeals, setHubspotDeals] = useState([]);
  const [hubspotLoading, setHubspotLoading] = useState(false);
  const [hubspotError, setHubspotError] = useState('');
  const [selectedDealId, setSelectedDealId] = useState('');
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

  // Fetch projects (for "start from project" pre-fill)
  const { data: projects = [] } = useQuery({
    queryKey: ['projects', 'all'],
    queryFn: async () => {
      const response = await getProjects('all');
      return response.data;
    },
  });

  // Fetch templates (for "start from template" pre-fill)
  const { data: templates = [] } = useQuery({
    queryKey: ['proposalTemplates'],
    queryFn: async () => {
      const response = await getProposalTemplates();
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

  // Create-from-project mutation (Phase 2a pre-fill)
  const fromProjectMutation = useMutation({
    mutationFn: createProposalFromProject,
    onSuccess: (response) => {
      queryClient.invalidateQueries(['proposals']);
      setIsCreateDialogOpen(false);
      setSelectedProjectId('');
      toast.success(response.data?.assistant_message || 'Proposal pre-filled from project');
      navigate(`/proposals/${response.data.id}/builder`);
    },
    onError: (err) => {
      toast.error(err?.response?.data?.detail || 'Failed to create from project');
    },
  });

  // Create-from-template mutation (Phase 2b)
  const fromTemplateMutation = useMutation({
    mutationFn: createProposalFromTemplate,
    onSuccess: (response) => {
      queryClient.invalidateQueries(['proposals']);
      setIsCreateDialogOpen(false);
      setSelectedTemplateId('');
      setNewProposal({ client_name: '', proposal_title: '' });
      toast.success('Proposal created from template');
      navigate(`/proposals/${response.data.id}/builder`);
    },
    onError: (err) => {
      toast.error(err?.response?.data?.detail || 'Failed to create from template');
    },
  });

  // Create-from-document mutation (Phase 2c)
  const fromDocumentMutation = useMutation({
    mutationFn: createProposalFromDocument,
    onSuccess: (response) => {
      queryClient.invalidateQueries(['proposals']);
      setIsCreateDialogOpen(false);
      setUploadFile(null);
      toast.success(response.data?.assistant_message || 'Proposal drafted from document');
      navigate(`/proposals/${response.data.id}/builder`);
    },
    onError: (err) => {
      toast.error(err?.response?.data?.detail || 'Failed to create from document');
    },
  });

  // Create-from-drive mutation (Phase 2d)
  const fromDriveMutation = useMutation({
    mutationFn: createProposalFromDrive,
    onSuccess: (response) => {
      queryClient.invalidateQueries(['proposals']);
      setIsCreateDialogOpen(false);
      setSelectedDriveDocId('');
      setDriveUrl('');
      setDriveFiles([]);
      setDriveError('');
      toast.success(response.data?.assistant_message || 'Proposal imported from Drive');
      navigate(`/proposals/${response.data.id}/builder`);
    },
    onError: (err) => {
      toast.error(err?.response?.data?.detail || 'Failed to import from Drive');
    },
  });

  // Create-from-hubspot-deal mutation
  const fromHubspotMutation = useMutation({
    mutationFn: createProposalFromDeal,
    onSuccess: (response) => {
      queryClient.invalidateQueries(['proposals']);
      setIsCreateDialogOpen(false);
      setSelectedDealId('');
      setHubspotDeals([]);
      setHubspotError('');
      toast.success(response.data?.assistant_message || 'Proposal imported from HubSpot deal');
      navigate(`/proposals/${response.data.id}/builder`);
    },
    onError: (err) => {
      toast.error(err?.response?.data?.detail || 'Failed to import from HubSpot deal');
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
      // Honest status: say whether the email actually went out, or to share manually.
      if (response.data.email_sent) {
        toast.success(`Link copied — and emailed to ${response.data.recipient || 'the client'}.`);
      } else {
        toast.success('Link copied to clipboard.');
        if (response.data.email_message) {
          toast.info(response.data.email_message);
        }
      }
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
      if (response.data.magic_link_sent) {
        toast.success('Proposal confirmed — report link emailed to the client.');
      } else {
        toast.success('Proposal confirmed!');
        if (response.data.email_message) {
          toast.info(response.data.email_message);
        }
      }
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

  const handleLoadDriveDocs = async () => {
    setDriveLoadingList(true);
    setDriveError('');
    setDriveFiles([]);
    try {
      const response = await listDriveDocs();
      if (response.data.ok === false) {
        setDriveError(response.data.message || 'Failed to load Google Drive documents');
      } else {
        setDriveFiles(response.data.files || []);
      }
    } catch (err) {
      setDriveError(err?.response?.data?.detail || err?.response?.data?.message || 'Failed to load Google Drive documents');
    } finally {
      setDriveLoadingList(false);
    }
  };

  const handleLoadHubspotDeals = async () => {
    setHubspotLoading(true);
    setHubspotError('');
    setHubspotDeals([]);
    try {
      const response = await listHubspotDeals();
      if (response.data.ok === false) {
        setHubspotError(response.data.message || 'Failed to load HubSpot deals');
      } else {
        setHubspotDeals(response.data.deals || []);
      }
    } catch (err) {
      setHubspotError(err?.response?.data?.detail || err?.response?.data?.message || 'Failed to load HubSpot deals');
    } finally {
      setHubspotLoading(false);
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
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={() => navigate('/proposals/templates')}
              data-testid="manage-templates-btn"
            >
              Templates
            </Button>
            <Button
              onClick={() => setIsCreateDialogOpen(true)}
              className="bg-[#1570EF] hover:bg-[#1565D8] text-white"
              data-testid="new-proposal-button"
            >
              <Plus className="mr-2 h-4 w-4" />
              New Proposal
            </Button>
          </div>
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
        <Dialog open={isCreateDialogOpen} onOpenChange={(open) => {
          setIsCreateDialogOpen(open);
          if (!open) {
            // Reset all states when dialog closes
            setDriveFiles([]);
            setDriveLoadingList(false);
            setDriveError('');
            setSelectedDriveDocId('');
            setDriveUrl('');
            setHubspotDeals([]);
            setHubspotLoading(false);
            setHubspotError('');
            setSelectedDealId('');
          }
        }}>
          <DialogContent data-testid="create-proposal-dialog">
            <DialogHeader>
              <DialogTitle>New Proposal</DialogTitle>
              <DialogDescription>
                Start blank, or pre-fill from an existing project. You can refine everything in the builder.
              </DialogDescription>
            </DialogHeader>

            <Tabs value={createMode} onValueChange={setCreateMode} className="py-2">
              <TabsList className="grid w-full grid-cols-6">
                <TabsTrigger value="blank" data-testid="create-mode-blank">Blank</TabsTrigger>
                <TabsTrigger value="project" data-testid="create-mode-project">From a project</TabsTrigger>
                <TabsTrigger value="template" data-testid="create-mode-template">From template</TabsTrigger>
                <TabsTrigger value="document" data-testid="create-mode-document">Upload document</TabsTrigger>
                <TabsTrigger value="drive" data-testid="create-mode-drive">From Drive</TabsTrigger>
                <TabsTrigger value="hubspot" data-testid="create-mode-hubspot">From HubSpot</TabsTrigger>
              </TabsList>

              <TabsContent value="blank" className="space-y-4 pt-4">
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
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)} data-testid="cancel-create-button">
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
              </TabsContent>

              <TabsContent value="project" className="space-y-4 pt-4">
                <div className="space-y-2">
                  <Label>Source project</Label>
                  <Select value={selectedProjectId} onValueChange={setSelectedProjectId}>
                    <SelectTrigger data-testid="from-project-select">
                      <SelectValue placeholder="Choose a project to pre-fill from" />
                    </SelectTrigger>
                    <SelectContent>
                      {projects.map((p) => (
                        <SelectItem key={p.id} value={p.id}>
                          {p.name}{p.client_name ? ` — ${p.client_name}` : ''}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-[#667085]">
                    We&apos;ll pre-fill the client, title, timeline, team and pricing from this project, then the AI drafts on-brand proposal content for you to refine.
                  </p>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)} data-testid="cancel-from-project-button">
                    Cancel
                  </Button>
                  <Button
                    onClick={() => fromProjectMutation.mutate({ project_id: selectedProjectId, use_ai: true })}
                    disabled={!selectedProjectId || fromProjectMutation.isPending}
                    className="bg-[#1570EF] hover:bg-[#1565D8] text-white"
                    data-testid="create-from-project-submit"
                  >
                    {fromProjectMutation.isPending ? 'Pre-filling…' : 'Pre-fill & Open Builder'}
                  </Button>
                </div>
              </TabsContent>

              <TabsContent value="template" className="space-y-4 pt-4">
                <div className="space-y-2">
                  <Label>Choose a template</Label>
                  {templates.length === 0 ? (
                    <p className="text-sm text-[#667085] py-4 text-center">
                      No templates yet — save one from the builder.
                    </p>
                  ) : (
                    <>
                      <Select value={selectedTemplateId} onValueChange={setSelectedTemplateId}>
                        <SelectTrigger data-testid="from-template-select">
                          <SelectValue placeholder="Select a template" />
                        </SelectTrigger>
                        <SelectContent>
                          {templates.map((t) => (
                            <SelectItem key={t.id} value={t.id}>
                              {t.name}{t.description ? ` — ${t.description}` : ''}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <div className="space-y-2">
                        <Label htmlFor="template_client_name">Client Name (optional)</Label>
                        <Input
                          id="template_client_name"
                          value={newProposal.client_name}
                          onChange={(e) => setNewProposal({ ...newProposal, client_name: e.target.value })}
                          placeholder="Acme Corp"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="template_proposal_title">Proposal Title (optional)</Label>
                        <Input
                          id="template_proposal_title"
                          value={newProposal.proposal_title}
                          onChange={(e) => setNewProposal({ ...newProposal, proposal_title: e.target.value })}
                          placeholder="Digital Transformation Initiative"
                        />
                      </div>
                    </>
                  )}
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button
                    onClick={() => fromTemplateMutation.mutate({ 
                      template_id: selectedTemplateId,
                      client_name: newProposal.client_name || undefined,
                      proposal_title: newProposal.proposal_title || undefined
                    })}
                    disabled={!selectedTemplateId || fromTemplateMutation.isPending}
                    className="bg-[#1570EF] hover:bg-[#1565D8] text-white"
                    data-testid="create-from-template-submit"
                  >
                    {fromTemplateMutation.isPending ? 'Creating…' : 'Create from Template'}
                  </Button>
                </div>
              </TabsContent>

              <TabsContent value="document" className="space-y-4 pt-4">
                <div className="space-y-2">
                  <Label htmlFor="upload-doc">Upload a document</Label>
                  <Input
                    id="upload-doc"
                    type="file"
                    accept=".docx,.pdf,.txt,.md"
                    onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                    data-testid="upload-doc-input"
                  />
                  <p className="text-xs text-[#667085]">
                    We&apos;ll read the document and let AI draft the proposal — refine it after.
                  </p>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button
                    onClick={() => {
                      if (!uploadFile) return;
                      const fd = new FormData();
                      fd.append('file', uploadFile);
                      fd.append('use_ai', 'true');
                      fromDocumentMutation.mutate(fd);
                    }}
                    disabled={!uploadFile || fromDocumentMutation.isPending}
                    className="bg-[#1570EF] hover:bg-[#1565D8] text-white"
                    data-testid="create-from-document-submit"
                  >
                    {fromDocumentMutation.isPending ? 'Reading & drafting… this can take ~30–60s' : 'Upload & Draft'}
                  </Button>
                </div>
              </TabsContent>

              <TabsContent value="drive" className="space-y-4 pt-4">
                <div className="space-y-2">
                  <p className="text-sm text-[#667085]">
                    Import a finalized brief straight from Google Drive. (Requires a super admin to connect Google Drive in Settings → Integrations.)
                  </p>
                  
                  {!driveFiles.length && !driveError && (
                    <Button
                      onClick={handleLoadDriveDocs}
                      disabled={driveLoadingList}
                      variant="outline"
                      className="w-full"
                      data-testid="drive-load-btn"
                    >
                      {driveLoadingList && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                      {driveLoadingList ? 'Loading...' : 'Load my Google Docs'}
                    </Button>
                  )}

                  {driveError && (
                    <p className="text-sm text-red-600" data-testid="drive-error">
                      {driveError}
                    </p>
                  )}

                  {driveFiles.length > 0 && (
                    <div className="space-y-2">
                      <Label>Select a document</Label>
                      <Select value={selectedDriveDocId} onValueChange={setSelectedDriveDocId}>
                        <SelectTrigger data-testid="drive-doc-select">
                          <SelectValue placeholder="Choose a Google Doc" />
                        </SelectTrigger>
                        <SelectContent>
                          {driveFiles.map((file) => (
                            <SelectItem key={file.id} value={file.id}>
                              {file.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}

                  <div className="space-y-2">
                    <Label htmlFor="drive-doc-url-input">...or paste a Google Doc link</Label>
                    <Input
                      id="drive-doc-url-input"
                      value={driveUrl}
                      onChange={(e) => setDriveUrl(e.target.value)}
                      placeholder="https://docs.google.com/document/d/..."
                      data-testid="drive-doc-url-input"
                    />
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button
                    onClick={() => {
                      const docId = selectedDriveDocId || driveUrl;
                      if (!docId) return;
                      fromDriveMutation.mutate({ doc_id: docId, use_ai: true });
                    }}
                    disabled={(!selectedDriveDocId && !driveUrl) || fromDriveMutation.isPending}
                    className="bg-[#1570EF] hover:bg-[#1565D8] text-white"
                    data-testid="create-from-drive-submit"
                  >
                    {fromDriveMutation.isPending ? 'Importing… this can take ~30–60s' : 'Import & Open Builder'}
                  </Button>
                </div>
              </TabsContent>

              <TabsContent value="hubspot" className="space-y-4 pt-4">
                <div className="space-y-2">
                  <p className="text-sm text-[#667085]">
                    Create a proposal from a HubSpot deal. (Requires a super admin to connect HubSpot in Settings → Integrations.)
                  </p>
                  
                  {!hubspotDeals.length && !hubspotError && (
                    <Button
                      onClick={handleLoadHubspotDeals}
                      disabled={hubspotLoading}
                      variant="outline"
                      className="w-full"
                      data-testid="hubspot-load-btn"
                    >
                      {hubspotLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                      {hubspotLoading ? 'Loading...' : 'Load my deals'}
                    </Button>
                  )}

                  {hubspotError && (
                    <p className="text-sm text-red-600" data-testid="hubspot-error">
                      {hubspotError}
                    </p>
                  )}

                  {hubspotDeals.length > 0 && (
                    <div className="space-y-2">
                      <Label>Select a deal</Label>
                      <Select value={selectedDealId} onValueChange={setSelectedDealId}>
                        <SelectTrigger data-testid="hubspot-deal-select">
                          <SelectValue placeholder="Choose a HubSpot deal" />
                        </SelectTrigger>
                        <SelectContent>
                          {hubspotDeals.map((deal) => (
                            <SelectItem key={deal.id} value={deal.id}>
                              {deal.name} — {deal.stage}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button
                    onClick={() => {
                      if (!selectedDealId) return;
                      fromHubspotMutation.mutate({ deal_id: selectedDealId, use_ai: true });
                    }}
                    disabled={!selectedDealId || fromHubspotMutation.isPending}
                    className="bg-[#1570EF] hover:bg-[#1565D8] text-white"
                    data-testid="create-from-deal-submit"
                  >
                    {fromHubspotMutation.isPending ? 'Importing… this can take ~30–60s' : 'Import & Open Builder'}
                  </Button>
                </div>
              </TabsContent>
            </Tabs>
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
