import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import {
  getProposal,
  updateProposal,
  aiDraftProposal,
  previewProposal,
  sendProposal,
  confirmProposal,
  getProposalEvents,
  createProposalTemplate,
} from '../api';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../components/ui/collapsible';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '../components/ui/dialog';
import {
  ArrowLeft,
  Save,
  Send,
  RefreshCw,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Loader2,
  Copy,
  BarChart3,
  MessageSquare,
  FileEdit,
  Eye,
} from 'lucide-react';
import { ScrollArea } from '../components/ui/scroll-area';
import AIFeedbackButtons from '../components/AIFeedbackButtons';

const ProposalBuilder = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const chatEndRef = useRef(null);

  const [data, setData] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [previewHtml, setPreviewHtml] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isDraftingAI, setIsDraftingAI] = useState(false);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [isSendDialogOpen, setIsSendDialogOpen] = useState(false);
  const [sendResult, setSendResult] = useState(null);
  const [isConfirmDialogOpen, setIsConfirmDialogOpen] = useState(false);
  const [confirmResult, setConfirmResult] = useState(null);
  const [isSaveTemplateDialogOpen, setIsSaveTemplateDialogOpen] = useState(false);
  const [templateName, setTemplateName] = useState('');
  const [templateDescription, setTemplateDescription] = useState('');
  const [openSections, setOpenSections] = useState({
    cover: true,
    understanding: false,
    shift: false,
    options: false,
    plan: false,
    success: false,
    investment: false,
    why: false,
    nextSteps: false,
    appendix: false,
  });

  // Fetch proposal
  const { data: proposal, isLoading } = useQuery({
    queryKey: ['proposal', id],
    queryFn: async () => {
      const response = await getProposal(id);
      return response.data;
    },
    enabled: !!id,
  });

  // Fetch engagement events
  const { data: eventsData } = useQuery({
    queryKey: ['proposalEvents', id],
    queryFn: async () => {
      const response = await getProposalEvents(id);
      return response.data;
    },
    enabled: !!id && proposal?.status !== 'Draft',
    refetchInterval: 30000, // Refresh every 30s
  });

  // Initialize data when proposal loads
  useEffect(() => {
    if (proposal) {
      setData(proposal.data || {});
      // Welcome message
      if (chatMessages.length === 0) {
        setChatMessages([
          {
            role: 'assistant',
            content:
              "Hi! I'm your proposal assistant. You can paste notes, describe the client deal in plain English, or ask me to draft any section. I'll help you build a compelling proposal. Try: 'The client is Acme Corp, they need help with cloud migration' or 'Draft the understanding section focusing on scalability challenges'.",
          },
        ]);
      }
    }
  }, [proposal]);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: async () => {
      setIsSaving(true);
      await updateProposal(id, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['proposal', id]);
      setIsSaving(false);
      toast.success('Saved');
    },
    onError: () => {
      setIsSaving(false);
      toast.error('Failed to save');
    },
  });

  // AI draft mutation
  const aiDraftMutation = useMutation({
    mutationFn: async (message) => {
      setIsDraftingAI(true);
      const response = await aiDraftProposal(id, {
        message,
        current_data: data,
      });
      return response.data;
    },
    onSuccess: (result) => {
      setIsDraftingAI(false);
      // Add assistant message
      setChatMessages((prev) => [
        ...prev,
        { role: 'assistant', content: result.assistant_message },
      ]);
      // Update data
      setData(result.data);
      // Show warnings if any
      if (result.warnings && result.warnings.length > 0) {
        toast.warning(result.warnings.join(', '));
      }
    },
    onError: () => {
      setIsDraftingAI(false);
      setChatMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' },
      ]);
      toast.error('AI draft failed');
    },
  });

  // Preview mutation
  const previewMutation = useMutation({
    mutationFn: async () => {
      setIsPreviewLoading(true);
      // Save first
      await updateProposal(id, data);
      // Then preview
      const response = await previewProposal(id);
      return response.data;
    },
    onSuccess: (html) => {
      setIsPreviewLoading(false);
      setPreviewHtml(html);
      toast.success('Preview refreshed');
    },
    onError: () => {
      setIsPreviewLoading(false);
      toast.error('Failed to load preview');
    },
  });

  // Send mutation
  const sendMutation = useMutation({
    mutationFn: async () => {
      // Save first
      await updateProposal(id, data);
      // Then send
      const response = await sendProposal(id);
      return response.data;
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries(['proposal', id]);
      queryClient.invalidateQueries(['proposals']);
      setSendResult(result);
      setIsSendDialogOpen(true);
    },
    onError: () => {
      toast.error('Failed to send proposal');
    },
  });

  // Confirm mutation
  const confirmMutation = useMutation({
    mutationFn: confirmProposal,
    onSuccess: (response) => {
      queryClient.invalidateQueries(['proposal', id]);
      queryClient.invalidateQueries(['proposals']);
      setConfirmResult(response.data);
      setIsConfirmDialogOpen(true);
      toast.success('Proposal confirmed!');
    },
    onError: () => {
      toast.error('Failed to confirm proposal');
    },
  });

  // Save as template mutation
  const saveTemplateMutation = useMutation({
    mutationFn: async () => {
      await createProposalTemplate({
        name: templateName,
        description: templateDescription || undefined,
        from_proposal_id: id,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['proposalTemplates']);
      setIsSaveTemplateDialogOpen(false);
      setTemplateName('');
      setTemplateDescription('');
      toast.success('Template saved');
    },
    onError: () => {
      toast.error('Failed to save template');
    },
  });

  const handleSave = () => {
    saveMutation.mutate();
  };

  const handleSendChat = () => {
    if (!chatInput.trim()) return;
    // Add user message
    setChatMessages((prev) => [...prev, { role: 'user', content: chatInput }]);
    // Call AI
    aiDraftMutation.mutate(chatInput);
    setChatInput('');
  };

  const handleRefreshPreview = () => {
    previewMutation.mutate();
  };

  const handleSend = () => {
    sendMutation.mutate();
  };

  const handleConfirm = () => {
    confirmMutation.mutate(id);
  };

  const toggleSection = (section) => {
    setOpenSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  const getStatusBadge = (status) => {
    const variants = {
      Draft: 'bg-slate-100 text-slate-700',
      Sent: 'bg-blue-100 text-blue-700',
      Viewed: 'bg-indigo-100 text-indigo-700',
      Accepted: 'bg-amber-100 text-amber-700',
      Confirmed: 'bg-green-100 text-green-700',
      Declined: 'bg-red-100 text-red-700',
      Expired: 'bg-slate-100 text-slate-500',
    };
    return <Badge className={variants[status] || variants.Draft}>{status}</Badge>;
  };

  if (isLoading || !data) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-slate-200 rounded w-48"></div>
          <div className="h-96 bg-slate-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F8FAFC]">
      {/* Top Bar */}
      <div className="bg-white border-b border-slate-200 px-6 py-4 sticky top-0 z-10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/proposals')}
              data-testid="back-button"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
            <div>
              <h1 className="text-xl font-semibold text-[#0B1220]">
                {data.client_name || 'Untitled'} — {data.proposal_title || 'Proposal'}
              </h1>
            </div>
            {getStatusBadge(proposal.status)}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsSaveTemplateDialogOpen(true)}
              data-testid="save-as-template-btn"
            >
              Save as template
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleSave}
              disabled={isSaving}
              data-testid="save-button"
            >
              <Save className="mr-2 h-4 w-4" />
              {isSaving ? 'Saving...' : 'Save'}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleSend}
              disabled={sendMutation.isPending}
              data-testid="send-button"
            >
              <Send className="mr-2 h-4 w-4" />
              Send / Get Link
            </Button>
            {proposal.status === 'Accepted' && (
              <Button
                size="sm"
                onClick={handleConfirm}
                disabled={confirmMutation.isPending}
                className="bg-green-600 hover:bg-green-700 text-white"
                data-testid="confirm-button"
              >
                <CheckCircle2 className="mr-2 h-4 w-4" />
                Confirm & Provision
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Main Content - Responsive 3-pane layout */}
      <div className="hidden lg:flex h-[calc(100vh-73px)]">
        {/* Left: AI Chat */}
        <div className="w-80 border-r border-slate-200 bg-white flex flex-col">
          <div className="p-4 border-b border-slate-200">
            <h2 className="font-semibold text-[#0B1220] flex items-center">
              <MessageSquare className="mr-2 h-5 w-5 text-[#1570EF]" />
              AI Assistant
            </h2>
          </div>
          <ScrollArea className="flex-1 p-4">
            <div className="space-y-4">
              {chatMessages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`p-3 rounded-lg ${
                    msg.role === 'user'
                      ? 'bg-[#1570EF] text-white ml-4'
                      : 'bg-slate-100 text-[#0B1220] mr-4'
                  }`}
                  data-testid={`chat-message-${idx}`}
                >
                  <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
                </div>
              ))}
              {isDraftingAI && (
                <div className="bg-slate-100 text-[#0B1220] mr-4 p-3 rounded-lg flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm">Assistant is drafting...</span>
                </div>
              )}
              {chatMessages.length > 1 && chatMessages[chatMessages.length - 1]?.role === 'assistant' && (
                <div className="mr-4">
                  <AIFeedbackButtons
                    feature="proposal"
                    projectId={null}
                    outputSummary="Proposal AI draft"
                  />
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
          </ScrollArea>
          <div className="p-4 border-t border-slate-200">
            <div className="flex gap-2">
              <Textarea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendChat();
                  }
                }}
                placeholder="Describe the deal or ask me to draft..."
                className="min-h-[60px]"
                data-testid="chat-input"
              />
              <Button
                onClick={handleSendChat}
                disabled={!chatInput.trim() || isDraftingAI}
                className="bg-[#1570EF] hover:bg-[#1565D8] text-white"
                data-testid="chat-send-button"
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>

        {/* Center: Editable Form */}
        <div className="flex-1 overflow-y-auto">
          <ScrollArea className="h-full">
            <div className="p-6 max-w-4xl mx-auto space-y-4">
              <ProposalForm data={data} setData={setData} openSections={openSections} toggleSection={toggleSection} />
            </div>
          </ScrollArea>
        </div>

        {/* Right: Preview */}
        <div className="w-96 border-l border-slate-200 bg-white flex flex-col">
          <div className="p-4 border-b border-slate-200 flex items-center justify-between">
            <h2 className="font-semibold text-[#0B1220] flex items-center">
              <Eye className="mr-2 h-5 w-5 text-[#1570EF]" />
              Live Preview
            </h2>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefreshPreview}
              disabled={isPreviewLoading}
              data-testid="refresh-preview-button"
            >
              <RefreshCw className={`h-4 w-4 ${isPreviewLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
          <div className="flex-1 p-4 overflow-hidden">
            {previewHtml ? (
              <iframe
                srcDoc={previewHtml}
                className="w-full h-full border rounded"
                title="Proposal Preview"
                data-testid="preview-iframe"
              />
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center text-[#667085]">
                <Eye className="h-12 w-12 text-slate-300 mb-2" />
                <p className="text-sm">Click &quot;Refresh preview&quot; to see the saved version</p>
              </div>
            )}
          </div>
          {eventsData && eventsData.summary && (
            <div className="p-4 border-t border-slate-200">
              <h3 className="text-sm font-semibold text-[#0B1220] mb-2 flex items-center">
                <BarChart3 className="mr-2 h-4 w-4 text-[#1570EF]" />
                Engagement
              </h3>
              <div className="space-y-1 text-xs text-[#667085]">
                {eventsData.summary.opened && <div>✓ Opened</div>}
                {eventsData.summary.sections_viewed > 0 && (
                  <div>Sections viewed: {eventsData.summary.sections_viewed}</div>
                )}
                {eventsData.summary.interested_path && (
                  <div className="text-[#1570EF] font-medium">
                    Interested in: Path {eventsData.summary.interested_path.toUpperCase()}
                  </div>
                )}
                {eventsData.summary.accepted && (
                  <div className="text-green-600 font-medium">✓ Accepted</div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Mobile/Tablet: Tabs Layout */}
      <div className="lg:hidden p-4">
        <Tabs defaultValue="edit" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="assistant" data-testid="tab-assistant">
              <MessageSquare className="h-4 w-4 mr-2" />
              Assistant
            </TabsTrigger>
            <TabsTrigger value="edit" data-testid="tab-edit">
              <FileEdit className="h-4 w-4 mr-2" />
              Edit
            </TabsTrigger>
            <TabsTrigger value="preview" data-testid="tab-preview">
              <Eye className="h-4 w-4 mr-2" />
              Preview
            </TabsTrigger>
          </TabsList>

          <TabsContent value="assistant" className="mt-4">
            <Card>
              <CardContent className="p-4 space-y-4">
                <ScrollArea className="h-96">
                  <div className="space-y-4">
                    {chatMessages.map((msg, idx) => (
                      <div
                        key={idx}
                        className={`p-3 rounded-lg ${
                          msg.role === 'user'
                            ? 'bg-[#1570EF] text-white ml-4'
                            : 'bg-slate-100 text-[#0B1220] mr-4'
                        }`}
                      >
                        <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
                      </div>
                    ))}
                    {isDraftingAI && (
                      <div className="bg-slate-100 text-[#0B1220] mr-4 p-3 rounded-lg flex items-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span className="text-sm">Assistant is drafting...</span>
                      </div>
                    )}
                    {chatMessages.length > 1 && chatMessages[chatMessages.length - 1]?.role === 'assistant' && (
                      <div className="mr-4">
                        <AIFeedbackButtons
                          feature="proposal"
                          projectId={null}
                          outputSummary="Proposal AI draft"
                        />
                      </div>
                    )}
                    <div ref={chatEndRef} />
                  </div>
                </ScrollArea>
                <div className="flex gap-2">
                  <Textarea
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Describe the deal or ask me to draft..."
                    className="min-h-[60px]"
                  />
                  <Button
                    onClick={handleSendChat}
                    disabled={!chatInput.trim() || isDraftingAI}
                    className="bg-[#1570EF] hover:bg-[#1565D8] text-white"
                  >
                    <Send className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="edit" className="mt-4">
            <ProposalForm data={data} setData={setData} openSections={openSections} toggleSection={toggleSection} />
          </TabsContent>

          <TabsContent value="preview" className="mt-4">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Preview</CardTitle>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRefreshPreview}
                    disabled={isPreviewLoading}
                  >
                    <RefreshCw className={`h-4 w-4 ${isPreviewLoading ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {previewHtml ? (
                  <iframe
                    srcDoc={previewHtml}
                    className="w-full h-96 border rounded"
                    title="Proposal Preview"
                  />
                ) : (
                  <div className="flex flex-col items-center justify-center h-96 text-center text-[#667085]">
                    <Eye className="h-12 w-12 text-slate-300 mb-2" />
                    <p className="text-sm">Click refresh to see the saved version</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      {/* Send Dialog */}
      <Dialog open={isSendDialogOpen} onOpenChange={setIsSendDialogOpen}>
        <DialogContent data-testid="send-dialog">
          <DialogHeader>
            <DialogTitle>Proposal Sent!</DialogTitle>
            <DialogDescription>
              {sendResult?.email_sent
                ? 'The proposal link has been sent via email.'
                : 'Share the secure link with your client.'}
            </DialogDescription>
          </DialogHeader>
          {sendResult && (
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>Secure Proposal Link</Label>
                <div className="flex gap-2">
                  <Input
                    value={sendResult.proposal_link}
                    readOnly
                    className="font-mono text-xs"
                    data-testid="proposal-link-input"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      navigator.clipboard.writeText(sendResult.proposal_link);
                      toast.success('Link copied');
                    }}
                    data-testid="copy-link-button"
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          )}
          <div className="flex justify-end">
            <Button onClick={() => setIsSendDialogOpen(false)} data-testid="close-send-dialog-button">
              Close
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
                  <p className="text-sm text-green-800 mt-1">✓ Magic link email sent to client</p>
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
            <Button variant="outline" onClick={() => setIsConfirmDialogOpen(false)}>
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

      {/* Save Template Dialog */}
      <Dialog open={isSaveTemplateDialogOpen} onOpenChange={setIsSaveTemplateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save as Template</DialogTitle>
            <DialogDescription>
              This will snapshot the current proposal as a reusable template.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="template-name">Template Name *</Label>
              <Input
                id="template-name"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                placeholder="e.g., Standard Cloud Migration Proposal"
                data-testid="template-name-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="template-desc">Description (optional)</Label>
              <Input
                id="template-desc"
                value={templateDescription}
                onChange={(e) => setTemplateDescription(e.target.value)}
                placeholder="Brief description of when to use this template"
                data-testid="template-desc-input"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setIsSaveTemplateDialogOpen(false);
                setTemplateName('');
                setTemplateDescription('');
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={() => saveTemplateMutation.mutate()}
              disabled={!templateName.trim() || saveTemplateMutation.isPending}
              className="bg-[#1570EF] hover:bg-[#1565D8] text-white"
              data-testid="save-template-confirm"
            >
              {saveTemplateMutation.isPending ? 'Saving...' : 'Save Template'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

// Module-level collapsible section — defined OUTSIDE ProposalForm so React does
// not remount the whole subtree (and lose input focus) on every parent render.
const CollapsibleSection = ({ section, title, openSections, toggleSection, children }) => (
  <Card>
    <Collapsible open={openSections[section]} onOpenChange={() => toggleSection(section)}>
      <CollapsibleTrigger className="w-full" data-testid={`section-toggle-${section}`}>
        <CardHeader className="cursor-pointer hover:bg-slate-50 transition-colors">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">{title}</CardTitle>
            {openSections[section] ? (
              <ChevronDown className="h-5 w-5 text-[#667085]" />
            ) : (
              <ChevronRight className="h-5 w-5 text-[#667085]" />
            )}
          </div>
        </CardHeader>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <CardContent className="space-y-4">{children}</CardContent>
      </CollapsibleContent>
    </Collapsible>
  </Card>
);

// Separate form component for cleaner code
const ProposalForm = ({ data, setData, openSections, toggleSection }) => {
  const updateData = (path, value) => {
    setData((prev) => {
      const newData = { ...prev };
      const keys = path.split('.');
      let current = newData;
      for (let i = 0; i < keys.length - 1; i++) {
        if (!current[keys[i]]) current[keys[i]] = {};
        current = current[keys[i]];
      }
      current[keys[keys.length - 1]] = value;
      return newData;
    });
  };

  return (
    <div className="space-y-4">
      {/* Cover / Meta */}
      <CollapsibleSection section="cover" title="Cover & Metadata" openSections={openSections} toggleSection={toggleSection}>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label htmlFor="client_name">Client Name</Label>
            <Input
              id="client_name"
              value={data.client_name || ''}
              onChange={(e) => updateData('client_name', e.target.value)}
              data-testid="input-client-name"
            />
          </div>
          <div>
            <Label htmlFor="proposal_title">Proposal Title</Label>
            <Input
              id="proposal_title"
              value={data.proposal_title || ''}
              onChange={(e) => updateData('proposal_title', e.target.value)}
              data-testid="input-proposal-title"
            />
          </div>
          <div>
            <Label htmlFor="proposal_subtitle">Subtitle</Label>
            <Input
              id="proposal_subtitle"
              value={data.proposal_subtitle || ''}
              onChange={(e) => updateData('proposal_subtitle', e.target.value)}
              data-testid="input-proposal-subtitle"
            />
          </div>
          <div>
            <Label htmlFor="currency">Currency</Label>
            <Input
              id="currency"
              value={data.currency || 'USD'}
              onChange={(e) => updateData('currency', e.target.value)}
              data-testid="input-currency"
            />
          </div>
          <div>
            <Label htmlFor="prepared_by_name">Prepared By (Name)</Label>
            <Input
              id="prepared_by_name"
              value={data.prepared_by_name || ''}
              onChange={(e) => updateData('prepared_by_name', e.target.value)}
              data-testid="input-prepared-by-name"
            />
          </div>
          <div>
            <Label htmlFor="contact_email">Contact Email</Label>
            <Input
              id="contact_email"
              value={data.contact_email || ''}
              onChange={(e) => updateData('contact_email', e.target.value)}
              data-testid="input-contact-email"
            />
          </div>
        </div>
      </CollapsibleSection>

      {/* Understanding */}
      <CollapsibleSection section="understanding" title="01 Understanding" openSections={openSections} toggleSection={toggleSection}>
        <div>
          <Label htmlFor="understanding_paragraphs">Paragraphs (one per line)</Label>
          <Textarea
            id="understanding_paragraphs"
            value={(data.understanding?.paragraphs || []).join('\n')}
            onChange={(e) =>
              updateData(
                'understanding.paragraphs',
                e.target.value.split('\n').filter((p) => p.trim())
              )
            }
            rows={6}
            data-testid="input-understanding-paragraphs"
          />
        </div>
      </CollapsibleSection>

      {/* The Shift (Vision) */}
      <CollapsibleSection section="shift" title="02 The Shift (Vision)" openSections={openSections} toggleSection={toggleSection}>
        <div className="space-y-4">
          <div>
            <Label htmlFor="vision_headline">Headline</Label>
            <Input
              id="vision_headline"
              value={data.vision?.headline || ''}
              onChange={(e) => updateData('vision.headline', e.target.value)}
              data-testid="input-vision-headline"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="vision_from_title">From (Title)</Label>
              <Input
                id="vision_from_title"
                value={data.vision?.from_title || ''}
                onChange={(e) => updateData('vision.from_title', e.target.value)}
                data-testid="input-vision-from-title"
              />
              <Label className="mt-2">From (Points, one per line)</Label>
              <Textarea
                value={(data.vision?.from_points || []).join('\n')}
                onChange={(e) =>
                  updateData(
                    'vision.from_points',
                    e.target.value.split('\n').filter((p) => p.trim())
                  )
                }
                rows={4}
                data-testid="input-vision-from-points"
              />
            </div>
            <div>
              <Label htmlFor="vision_to_title">To (Title)</Label>
              <Input
                id="vision_to_title"
                value={data.vision?.to_title || ''}
                onChange={(e) => updateData('vision.to_title', e.target.value)}
                data-testid="input-vision-to-title"
              />
              <Label className="mt-2">To (Points, one per line)</Label>
              <Textarea
                value={(data.vision?.to_points || []).join('\n')}
                onChange={(e) =>
                  updateData(
                    'vision.to_points',
                    e.target.value.split('\n').filter((p) => p.trim())
                  )
                }
                rows={4}
                data-testid="input-vision-to-points"
              />
            </div>
          </div>
        </div>
      </CollapsibleSection>

      {/* Options */}
      <CollapsibleSection section="options" title="04 Options (3 Paths)" openSections={openSections} toggleSection={toggleSection}>
        <div className="space-y-4">
          <p className="text-sm text-[#667085]">
            Define three paths (a, b, c) here. For complex editing, use the AI assistant.
          </p>
          <div>
            <Label>Options Intro</Label>
            <Textarea
              value={data.options_intro || ''}
              onChange={(e) => updateData('options_intro', e.target.value)}
              rows={3}
              data-testid="input-options-intro"
            />
          </div>
        </div>
      </CollapsibleSection>

      {/* Plan */}
      <CollapsibleSection section="plan" title="05 Plan" openSections={openSections} toggleSection={toggleSection}>
        <div className="space-y-4">
          <div>
            <Label htmlFor="plan_headline">Headline</Label>
            <Input
              id="plan_headline"
              value={data.plan?.headline || ''}
              onChange={(e) => updateData('plan.headline', e.target.value)}
              data-testid="input-plan-headline"
            />
          </div>
          <div>
            <Label>Intro</Label>
            <Textarea
              value={data.plan?.intro || ''}
              onChange={(e) => updateData('plan.intro', e.target.value)}
              rows={3}
              data-testid="input-plan-intro"
            />
          </div>
        </div>
      </CollapsibleSection>

      {/* Success */}
      <CollapsibleSection section="success" title="06 Success (Outcomes & Gates)" openSections={openSections} toggleSection={toggleSection}>
        <div className="space-y-4">
          <div>
            <Label>Outcomes Caption</Label>
            <Input
              value={data.success?.outcomes_caption || ''}
              onChange={(e) => updateData('success.outcomes_caption', e.target.value)}
              data-testid="input-success-outcomes-caption"
            />
          </div>
        </div>
      </CollapsibleSection>

      {/* Investment (Pricing) */}
      <CollapsibleSection section="investment" title="07 Investment (Pricing)" openSections={openSections} toggleSection={toggleSection}>
        <div className="space-y-4">
          <div>
            <Label>Investment Note</Label>
            <Textarea
              value={data.investment_note || ''}
              onChange={(e) => updateData('investment_note', e.target.value)}
              rows={3}
              data-testid="input-investment-note"
            />
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <Label>Path A — Tier Fee</Label>
              <Input
                type="number"
                value={data.pricing_model?.path_a?.tier_fee || ''}
                onChange={(e) => updateData('pricing_model.path_a.tier_fee', parseFloat(e.target.value))}
                data-testid="input-pricing-path-a-fee"
              />
            </div>
            <div>
              <Label>Path B — Hourly Rate</Label>
              <Input
                type="number"
                value={data.pricing_model?.path_b?.hourly_rate || ''}
                onChange={(e) => updateData('pricing_model.path_b.hourly_rate', parseFloat(e.target.value))}
                data-testid="input-pricing-path-b-rate"
              />
            </div>
            <div>
              <Label>Path C — Hourly Rate</Label>
              <Input
                type="number"
                value={data.pricing_model?.path_c?.hourly_rate || ''}
                onChange={(e) => updateData('pricing_model.path_c.hourly_rate', parseFloat(e.target.value))}
                data-testid="input-pricing-path-c-rate"
              />
            </div>
          </div>
        </div>
      </CollapsibleSection>

      {/* Why DD / Team */}
      <CollapsibleSection section="why" title="08 Why DD / Team" openSections={openSections} toggleSection={toggleSection}>
        <div className="space-y-4">
          <p className="text-sm text-[#667085]">
            Team and case studies can be edited via AI assistant for complex arrays.
          </p>
        </div>
      </CollapsibleSection>

      {/* Next Steps */}
      <CollapsibleSection section="nextSteps" title="09 Next Steps" openSections={openSections} toggleSection={toggleSection}>
        <div>
          <Label>Next Steps Intro</Label>
          <Textarea
            value={data.next_steps_intro || ''}
            onChange={(e) => updateData('next_steps_intro', e.target.value)}
            rows={3}
            data-testid="input-next-steps-intro"
          />
        </div>
      </CollapsibleSection>

      {/* Appendix */}
      <CollapsibleSection section="appendix" title="Appendix" openSections={openSections} toggleSection={toggleSection}>
        <div className="space-y-4">
          <p className="text-sm text-[#667085]">
            Appendix tables (friction matrix, target state, AWS footprint) can be edited via AI assistant.
          </p>
        </div>
      </CollapsibleSection>
    </div>
  );
};

export default ProposalBuilder;
