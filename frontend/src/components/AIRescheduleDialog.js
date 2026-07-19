import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { getSmartReschedule, rescheduleProject } from '../api';
import AIFeedbackButtons from './AIFeedbackButtons';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './ui/dialog';
import { 
  Sparkles, Loader2, CalendarClock, ArrowRight, 
  AlertTriangle, CheckCircle2, Clock, BarChart3,
  ChevronRight, Zap
} from 'lucide-react';
import { toast } from 'sonner';

const AIRescheduleDialog = ({ isOpen, onClose, projectId, projectName }) => {
  const queryClient = useQueryClient();
  const [analysis, setAnalysis] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [applied, setApplied] = useState(false);

  const handleAnalyze = async () => {
    setIsAnalyzing(true);
    setAnalysis(null);
    setApplied(false);
    try {
      const response = await getSmartReschedule(projectId);
      setAnalysis(response.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to analyze project schedule');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleApply = async () => {
    if (!analysis?.analysis?.recommended_weeks) return;
    setIsApplying(true);
    try {
      await rescheduleProject(
        projectId,
        analysis.analysis.recommended_weeks,
        analysis.analysis.direction || 'forward'
      );
      setApplied(true);
      toast.success(`Project rescheduled ${analysis.analysis.recommended_weeks} weeks ${analysis.analysis.direction || 'forward'}`);
      queryClient.invalidateQueries(['project', projectId]);
      queryClient.invalidateQueries(['wbs', projectId]);
      queryClient.invalidateQueries(['allocations']);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to apply reschedule');
    } finally {
      setIsApplying(false);
    }
  };

  const handleClose = () => {
    setAnalysis(null);
    setApplied(false);
    onClose();
  };

  const a = analysis?.analysis;
  const preview = analysis?.preview;
  const metrics = analysis?.metrics;

  return (
    <Dialog open={isOpen} onOpenChange={(v) => { if (!v) handleClose(); }}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="ai-reschedule-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles size={20} className="text-purple-600" />
            AI Smart Reschedule
          </DialogTitle>
          <DialogDescription>
            Analyze <strong>{projectName}</strong> schedule health and get AI-powered rescheduling recommendations.
          </DialogDescription>
        </DialogHeader>

        {/* Initial State — Analyze Button */}
        {!analysis && !isAnalyzing && (
          <div className="py-8 text-center">
            <CalendarClock size={48} className="mx-auto mb-4 text-purple-400" />
            <p className="text-gray-600 mb-6">
              AI will analyze project progress, WBS tasks, milestones, and team allocations
              to recommend optimal schedule adjustments.
            </p>
            <Button onClick={handleAnalyze} className="gap-2 bg-purple-600 hover:bg-purple-700" data-testid="analyze-schedule-btn">
              <Sparkles size={16} />
              Analyze Schedule
            </Button>
          </div>
        )}

        {/* Loading State */}
        {isAnalyzing && (
          <div className="py-12 text-center">
            <Loader2 size={40} className="mx-auto mb-4 text-purple-600 animate-spin" />
            <p className="text-gray-600 font-medium">Analyzing project schedule...</p>
            <p className="text-gray-400 text-sm mt-1">Examining progress, tasks, milestones & allocations</p>
          </div>
        )}

        {/* Results */}
        {analysis && !isAnalyzing && (
          <div className="space-y-5">

            {/* Metrics Bar */}
            {metrics && (
              <div className="grid grid-cols-4 gap-3">
                <div className="bg-gray-50 rounded-lg p-3 text-center">
                  <Clock size={16} className="mx-auto mb-1 text-blue-500" />
                  <div className="text-lg font-bold text-gray-900">{metrics.time_progress}%</div>
                  <div className="text-xs text-gray-500">Time Elapsed</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3 text-center">
                  <BarChart3 size={16} className="mx-auto mb-1 text-green-500" />
                  <div className="text-lg font-bold text-gray-900">{metrics.actual_progress}%</div>
                  <div className="text-xs text-gray-500">Actual Progress</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3 text-center">
                  <CheckCircle2 size={16} className="mx-auto mb-1 text-emerald-500" />
                  <div className="text-lg font-bold text-gray-900">{metrics.completed_tasks}/{metrics.total_tasks}</div>
                  <div className="text-xs text-gray-500">Tasks Done</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3 text-center">
                  <AlertTriangle size={16} className="mx-auto mb-1 text-red-500" />
                  <div className="text-lg font-bold text-gray-900">{metrics.overdue_tasks}</div>
                  <div className="text-xs text-gray-500">Overdue</div>
                </div>
              </div>
            )}

            {/* AI Analysis */}
            <div className={`rounded-lg p-4 border ${a?.should_reschedule ? 'bg-amber-50 border-amber-200' : 'bg-green-50 border-green-200'}`}>
              <div className="flex items-start gap-3">
                {a?.should_reschedule ? (
                  <AlertTriangle size={20} className="text-amber-600 mt-0.5 shrink-0" />
                ) : (
                  <CheckCircle2 size={20} className="text-green-600 mt-0.5 shrink-0" />
                )}
                <div>
                  <div className="font-semibold text-gray-900 mb-1">
                    {a?.should_reschedule 
                      ? `Recommend: Shift ${a?.recommended_weeks} week${a?.recommended_weeks > 1 ? 's' : ''} ${a?.direction || 'forward'}`
                      : 'Project is on track — no rescheduling needed'
                    }
                  </div>
                  <p className="text-sm text-gray-700">{a?.analysis}</p>
                  {a?.confidence && (
                    <Badge variant="outline" className="mt-2 text-xs">
                      AI Confidence: {Math.round(a.confidence * 100)}%
                    </Badge>
                  )}
                </div>
              </div>
            </div>

            {/* Reasons */}
            {a?.reasons && a.reasons.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-gray-800 mb-2">Key Factors</h4>
                <ul className="space-y-1.5">
                  {a.reasons.map((reason, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                      <ChevronRight size={14} className="text-purple-500 mt-0.5 shrink-0" />
                      {reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Risk Warning */}
            {a?.risk_if_not_rescheduled && a?.should_reschedule && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                <div className="text-sm font-medium text-red-800 mb-1">⚠️ Risk if not rescheduled</div>
                <p className="text-sm text-red-700">{a.risk_if_not_rescheduled}</p>
              </div>
            )}

            {/* AI Feedback */}
            <AIFeedbackButtons
              feature="reschedule"
              projectId={projectId}
              inputSummary={`Reschedule analysis for ${projectName}`}
              outputSummary={a?.analysis?.substring(0, 100)}
            />

            {/* Preview */}
            {a?.should_reschedule && preview && (
              <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                <div className="bg-gray-50 px-4 py-2 border-b">
                  <h4 className="text-sm font-semibold text-gray-800">Preview of Changes</h4>
                </div>
                <div className="p-4 space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Project Dates</span>
                    <div className="flex items-center gap-2">
                      <span className="text-gray-500">{preview.project?.current_start} → {preview.project?.current_end}</span>
                      <ArrowRight size={14} className="text-purple-500" />
                      <span className="font-medium text-purple-700">{preview.project?.new_start} → {preview.project?.new_end}</span>
                    </div>
                  </div>
                  <div className="border-t pt-3 grid grid-cols-2 gap-3 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-500">Phases affected</span>
                      <span className="font-medium">{preview.phases_count}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Allocations affected</span>
                      <span className="font-medium">{preview.allocations_count}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">WBS tasks to shift</span>
                      <span className="font-medium">{preview.wbs_tasks_count}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Milestones to shift</span>
                      <span className="font-medium">{preview.milestones_count}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Applied Success */}
            {applied && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
                <CheckCircle2 size={24} className="mx-auto mb-2 text-green-600" />
                <p className="font-medium text-green-800">Reschedule applied successfully!</p>
                <p className="text-sm text-green-600 mt-1">
                  All dates shifted {a?.recommended_weeks} week{a?.recommended_weeks > 1 ? 's' : ''} {a?.direction || 'forward'}
                </p>
              </div>
            )}
          </div>
        )}

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={handleClose}>
            {applied ? 'Done' : 'Cancel'}
          </Button>
          {analysis && a?.should_reschedule && !applied && (
            <Button 
              onClick={handleApply}
              disabled={isApplying}
              className="gap-2 bg-purple-600 hover:bg-purple-700"
              data-testid="apply-reschedule-btn"
            >
              {isApplying ? (
                <><Loader2 size={16} className="animate-spin" /> Applying...</>
              ) : (
                <><Zap size={16} /> Apply Reschedule</>
              )}
            </Button>
          )}
          {analysis && !applied && (
            <Button variant="outline" onClick={handleAnalyze} disabled={isAnalyzing} className="gap-2">
              <Sparkles size={14} />
              Re-analyze
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default AIRescheduleDialog;
