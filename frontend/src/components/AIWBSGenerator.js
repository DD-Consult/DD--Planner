import React, { useState, useMemo } from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from './ui/select';
import { Loader2, Sparkles, CheckCircle2, AlertTriangle, RefreshCw, Settings } from 'lucide-react';
import { toast } from 'sonner';
import { aiGenerateWBS, saveGeneratedWBS } from '../api';

const COMPLEXITY_OPTIONS = [
  { value: 'simple', label: 'Simple (5–8 tasks)' },
  { value: 'standard', label: 'Standard (8–15 tasks)' },
  { value: 'detailed', label: 'Detailed (15–25 tasks)' },
];

const STATUS_COLORS = {
  todo: 'bg-gray-100 text-gray-700',
  in_progress: 'bg-blue-100 text-blue-700',
  done: 'bg-green-100 text-green-700',
  on_hold: 'bg-yellow-100 text-yellow-700',
  blocked: 'bg-red-100 text-red-700',
};

const PRIORITY_COLORS = {
  low: 'bg-gray-100 text-gray-600',
  medium: 'bg-blue-100 text-blue-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
};

const AIWBSGenerator = ({
  open,
  onClose,
  projectId,
  project,
  phases,
  resources,
  onSuccess,
}) => {
  const [step, setStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [generatedData, setGeneratedData] = useState(null);

  const [formData, setFormData] = useState({
    additional_context: '',
    primary_deliverables: '',
    complexity: 'standard',
    start_date: '',
    include_subtasks: true,
  });

  // Check for personal AI key in localStorage
  const hasAIKey = useMemo(() => {
    try {
      const saved = localStorage.getItem('ai_settings');
      if (!saved) return false;
      const parsed = JSON.parse(saved);
      return !!(parsed.apiKey || parsed.api_key);
    } catch {
      return false;
    }
  }, []);

  const getAICredentials = () => {
    try {
      const saved = localStorage.getItem('ai_settings');
      if (!saved) return { provider: null, apiKey: null };
      const parsed = JSON.parse(saved);
      return {
        provider: parsed.provider || null,
        apiKey: parsed.apiKey || parsed.api_key || null,
      };
    } catch {
      return { provider: null, apiKey: null };
    }
  };

  const handleGenerate = async () => {
    setStep(2);
    setIsLoading(true);
    try {
      const { provider, apiKey } = getAICredentials();
      const payload = {
        project_id: projectId,
        additional_context: formData.additional_context,
        primary_deliverables: formData.primary_deliverables,
        complexity: formData.complexity,
        start_date: formData.start_date || null,
        include_subtasks: formData.include_subtasks,
        provider: provider || null,
        api_key: apiKey || null,
      };

      const response = await aiGenerateWBS(payload);
      setGeneratedData(response.data);
      setStep(3);
    } catch (err) {
      const msg = err.response?.data?.detail || 'AI generation failed. Please check settings.';
      toast.error(msg);
      setStep(1);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    if (!generatedData?.tasks?.length) return;
    setIsLoading(true);
    try {
      await saveGeneratedWBS({
        project_id: projectId,
        tasks: generatedData.tasks,
        start_date: formData.start_date || project?.start_date || null,
      });
      toast.success(`Saved ${generatedData.tasks.length} WBS tasks successfully!`);
      onSuccess?.();
      handleClose();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to save tasks.';
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegenerate = () => {
    setStep(1);
    setGeneratedData(null);
  };

  const handleClose = () => {
    setStep(1);
    setGeneratedData(null);
    setFormData({
      additional_context: '',
      primary_deliverables: '',
      complexity: 'standard',
      start_date: '',
      include_subtasks: true,
    });
    onClose();
  };

  // Group preview tasks by phase
  const tasksByPhase = useMemo(() => {
    if (!generatedData?.tasks) return {};
    const grouped = {};
    generatedData.tasks.forEach(task => {
      if (!task.parent_temp_id) {
        const key = task.phase_name || 'Unassigned';
        if (!grouped[key]) grouped[key] = [];
        grouped[key].push(task);
      }
    });
    return grouped;
  }, [generatedData]);

  const totalEstHours = useMemo(() => {
    if (!generatedData?.tasks) return 0;
    return generatedData.tasks.reduce((sum, t) => sum + (t.estimated_hours || 0), 0);
  }, [generatedData]);

  const rootTaskCount = useMemo(() => {
    if (!generatedData?.tasks) return 0;
    return generatedData.tasks.filter(t => !t.parent_temp_id).length;
  }, [generatedData]);

  const subTaskCount = useMemo(() => {
    if (!generatedData?.tasks) return 0;
    return generatedData.tasks.filter(t => !!t.parent_temp_id).length;
  }, [generatedData]);

  const phaseNames = phases?.map(p => typeof p === 'string' ? p : p.name) || [];

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles size={18} className="text-[#1570EF]" />
            AI WBS Generator
            <Badge variant="outline" className="text-xs ml-2">
              Step {step} of 3
            </Badge>
          </DialogTitle>
        </DialogHeader>

        {/* Step 1: Context */}
        {step === 1 && (
          <div className="space-y-4">
            {/* AI Key Warning */}
            {!hasAIKey && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2">
                <AlertTriangle size={16} className="text-amber-600 mt-0.5 shrink-0" />
                <div className="text-sm text-amber-700">
                  <strong>No personal AI key configured.</strong> The app will use the shared AI service.
                  To use your own key, save it via{' '}
                  <button
                    className="underline font-medium"
                    onClick={() => {
                      const key = prompt('Enter your API key (OpenAI or Gemini):');
                      const prov = prompt('Provider? (openai or gemini):') || 'openai';
                      if (key) {
                        localStorage.setItem('ai_settings', JSON.stringify({ provider: prov, apiKey: key }));
                        toast.success('AI key saved to browser. Reopen the generator to use it.');
                      }
                    }}
                  >
                    Configure Key
                  </button>
                  .
                </div>
              </div>
            )}

            {/* Project Context Summary */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
              <div className="text-xs font-medium text-gray-500 mb-2 uppercase tracking-wide">Project Context</div>
              <div className="space-y-1 text-sm">
                <div><span className="text-gray-500">Project:</span> <strong>{project?.name}</strong></div>
                <div><span className="text-gray-500">Client:</span> {project?.client_name}</div>
                <div>
                  <span className="text-gray-500">Phases:</span>{' '}
                  {phaseNames.length > 0
                    ? phaseNames.map((p, i) => (
                        <Badge key={i} variant="outline" className="mr-1 text-xs">{p}</Badge>
                      ))
                    : <span className="text-gray-400">None defined</span>
                  }
                </div>
                <div>
                  <span className="text-gray-500">Team ({resources?.length || 0}):</span>{' '}
                  {resources?.slice(0, 5).map(r => r.name).join(', ')}
                  {resources?.length > 5 ? ` +${resources.length - 5} more` : ''}
                </div>
              </div>
            </div>

            {/* Context Inputs */}
            <div>
              <Label>Primary Deliverables</Label>
              <Textarea
                value={formData.primary_deliverables}
                onChange={e => setFormData(prev => ({ ...prev, primary_deliverables: e.target.value }))}
                placeholder="e.g. Mobile app, API integration, Data migration, UAT sign-off..."
                className="mt-1"
                rows={2}
              />
            </div>

            <div>
              <Label>Additional Context</Label>
              <Textarea
                value={formData.additional_context}
                onChange={e => setFormData(prev => ({ ...prev, additional_context: e.target.value }))}
                placeholder="Any specific constraints, methodology (Agile/Waterfall), tech stack, or notes for the AI..."
                className="mt-1"
                rows={2}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Complexity Level</Label>
                <Select
                  value={formData.complexity}
                  onValueChange={v => setFormData(prev => ({ ...prev, complexity: v }))}
                >
                  <SelectTrigger className="mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {COMPLEXITY_OPTIONS.map(opt => (
                      <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Plan Start Date (optional)</Label>
                <Input
                  type="date"
                  value={formData.start_date}
                  onChange={e => setFormData(prev => ({ ...prev, start_date: e.target.value }))}
                  className="mt-1"
                />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="include-subtasks"
                checked={formData.include_subtasks}
                onChange={e => setFormData(prev => ({ ...prev, include_subtasks: e.target.checked }))}
                className="w-4 h-4"
              />
              <Label htmlFor="include-subtasks" className="cursor-pointer">
                Include sub-tasks
              </Label>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={handleClose}>Cancel</Button>
              <Button
                onClick={handleGenerate}
                className="bg-[#1570EF] hover:bg-[#1570EF]/90 text-white"
              >
                <Sparkles size={14} className="mr-2" />
                Generate WBS
              </Button>
            </div>
          </div>
        )}

        {/* Step 2: Loading */}
        {step === 2 && (
          <div className="flex flex-col items-center justify-center py-16 space-y-4">
            <Loader2 size={40} className="text-[#1570EF] animate-spin" />
            <div className="text-center">
              <div className="text-lg font-semibold">Generating your WBS...</div>
              <div className="text-sm text-gray-500 mt-1">
                AI is analyzing project context and creating a structured breakdown.
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Preview */}
        {step === 3 && generatedData && (
          <div className="space-y-4">
            {/* Summary Stats */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-blue-700">{rootTaskCount}</div>
                <div className="text-xs text-blue-600">Main Tasks</div>
              </div>
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-purple-700">{subTaskCount}</div>
                <div className="text-xs text-purple-600">Sub-tasks</div>
              </div>
              <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-green-700">{totalEstHours}h</div>
                <div className="text-xs text-green-600">Est. Hours</div>
              </div>
            </div>

            {/* Task Preview grouped by phase */}
            <div className="space-y-4 max-h-80 overflow-y-auto pr-1">
              {Object.entries(tasksByPhase).map(([phaseName, phaseTasks]) => (
                <div key={phaseName}>
                  <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 pb-1 border-b">
                    {phaseName}
                  </div>
                  <div className="space-y-2">
                    {phaseTasks.map(task => {
                      const subTasks = generatedData.tasks.filter(
                        t => t.parent_temp_id === task.temp_id
                      );
                      return (
                        <div key={task.temp_id} className="border rounded-lg p-2.5 bg-white hover:bg-gray-50">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="font-medium text-sm truncate">{task.name}</div>
                              {task.description && (
                                <div className="text-xs text-gray-500 mt-0.5 line-clamp-2">{task.description}</div>
                              )}
                              {subTasks.length > 0 && (
                                <div className="mt-1.5 space-y-1 pl-3 border-l-2 border-gray-200">
                                  {subTasks.map(sub => (
                                    <div key={sub.temp_id} className="text-xs text-gray-600 flex items-center gap-1">
                                      <span className="w-1.5 h-1.5 rounded-full bg-gray-400 shrink-0" />
                                      {sub.name}
                                      {sub.estimated_hours > 0 && (
                                        <span className="text-gray-400 ml-1">({sub.estimated_hours}h)</span>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                            <div className="flex flex-col items-end gap-1 shrink-0">
                              <Badge className={`text-xs ${PRIORITY_COLORS[task.priority] || 'bg-gray-100'}`}>
                                {task.priority}
                              </Badge>
                              {task.estimated_hours > 0 && (
                                <span className="text-xs text-gray-500">{task.estimated_hours}h</span>
                              )}
                              {task.assigned_to && (
                                <span className="text-xs text-blue-600">{task.assigned_to}</span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>

            <div className="bg-amber-50 border border-amber-200 rounded-lg p-2.5 text-xs text-amber-700">
              <strong>Review before saving:</strong> Task assignments and phases can be edited after saving.
            </div>

            <div className="flex justify-between gap-2 pt-2">
              <Button variant="outline" onClick={handleRegenerate} disabled={isLoading}>
                <RefreshCw size={14} className="mr-2" />
                Regenerate
              </Button>
              <div className="flex gap-2">
                <Button variant="outline" onClick={handleClose} disabled={isLoading}>
                  Cancel
                </Button>
                <Button
                  onClick={handleSave}
                  disabled={isLoading}
                  className="bg-[#1570EF] hover:bg-[#1570EF]/90 text-white"
                >
                  {isLoading ? <Loader2 size={14} className="mr-2 animate-spin" /> : <CheckCircle2 size={14} className="mr-2" />}
                  Confirm & Save {generatedData.tasks.length} Tasks
                </Button>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default AIWBSGenerator;
