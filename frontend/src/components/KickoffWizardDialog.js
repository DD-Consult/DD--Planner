import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Sparkles, ArrowRight, ArrowLeft, Loader2, CheckCircle } from 'lucide-react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from './ui/select';
import { aiKickoffSuggest, createProjectFull } from '../api';

/**
 * AI Kickoff Wizard
 * Step 1: capture goal + budget + complexity
 * Step 2: show AI suggestions (phases, WBS, roles) and let user review/edit
 * Step 3: create project + phases + optional WBS
 */
const KickoffWizardDialog = ({ open, onOpenChange }) => {
  const qc = useQueryClient();
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    name: '', goal: '', client: '', budget_hours: '', complexity: 'standard',
    start_date: new Date().toISOString().slice(0, 10),
  });
  const [suggestion, setSuggestion] = useState(null);

  const reset = () => {
    setStep(1);
    setForm({ name: '', goal: '', client: '', budget_hours: '', complexity: 'standard',
              start_date: new Date().toISOString().slice(0, 10) });
    setSuggestion(null);
  };

  const suggestMutation = useMutation({
    mutationFn: () => aiKickoffSuggest({
      ...form,
      budget_hours: form.budget_hours ? Number(form.budget_hours) : null,
    }),
    onSuccess: (res) => {
      setSuggestion(res.data);
      setStep(2);
    },
    onError: (e) => toast.error(`Kickoff failed: ${e?.response?.data?.detail || e?.message}`),
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      // Convert AI suggestion → createProjectFull payload
      const phases = (suggestion.phases || []).map((p, i) => {
        // Compute phase dates by cumulative durations
        const startBase = new Date(form.start_date);
        const priorWeeks = (suggestion.phases || []).slice(0, i)
          .reduce((sum, x) => sum + (Number(x.duration_weeks) || 0), 0);
        const ps = new Date(startBase);
        ps.setDate(ps.getDate() + priorWeeks * 7);
        const pe = new Date(ps);
        pe.setDate(pe.getDate() + (Number(p.duration_weeks) || 1) * 7 - 1);
        return {
          name: p.name,
          start_date: ps.toISOString().slice(0, 10),
          end_date: pe.toISOString().slice(0, 10),
          status: 'Active',
        };
      });

      const totalWeeks = phases.length
        ? (suggestion.phases || []).reduce((s, x) => s + (Number(x.duration_weeks) || 0), 0)
        : 8;
      const endDate = new Date(form.start_date);
      endDate.setDate(endDate.getDate() + totalWeeks * 7);

      const payload = {
        name: form.name,
        client_name: form.client || 'TBD',
        start_date: form.start_date,
        end_date: endDate.toISOString().slice(0, 10),
        budgeted_hours: form.budget_hours ? Number(form.budget_hours) :
          (suggestion.budget_breakdown?.total_estimated_hours || null),
        status: 'Pipeline',
        phases,
      };
      return createProjectFull(payload);
    },
    onSuccess: () => {
      toast.success('Project created from AI kickoff plan');
      qc.invalidateQueries({ queryKey: ['projects'] });
      onOpenChange(false);
      setTimeout(reset, 300);
    },
    onError: (e) => toast.error(`Create failed: ${e?.response?.data?.detail || e?.message}`),
  });

  return (
    <Dialog open={open} onOpenChange={(v) => { onOpenChange(v); if (!v) setTimeout(reset, 300); }}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="kickoff-wizard">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="text-purple-500" size={18} />
            AI Kickoff Wizard
          </DialogTitle>
          <DialogDescription>
            Describe the project — AI will suggest phases, WBS, roles, and budget from similar past projects.
          </DialogDescription>
        </DialogHeader>

        {step === 1 && (
          <div className="space-y-4 py-2" data-testid="kickoff-step-1">
            <div>
              <Label>Project name *</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                     placeholder="e.g. Customer Portal Rebuild" data-testid="kickoff-name-input" />
            </div>
            <div>
              <Label>Goal / description *</Label>
              <Textarea rows={3} value={form.goal} onChange={(e) => setForm({ ...form, goal: e.target.value })}
                        placeholder="What are we building and why?" data-testid="kickoff-goal-input" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Client (optional)</Label>
                <Input value={form.client} onChange={(e) => setForm({ ...form, client: e.target.value })} />
              </div>
              <div>
                <Label>Budget (hours, optional)</Label>
                <Input type="number" value={form.budget_hours} onChange={(e) => setForm({ ...form, budget_hours: e.target.value })}
                       placeholder="e.g. 500" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Start date</Label>
                <Input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
              </div>
              <div>
                <Label>Complexity</Label>
                <Select value={form.complexity} onValueChange={(v) => setForm({ ...form, complexity: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="simple">Simple (2-3 phases)</SelectItem>
                    <SelectItem value="standard">Standard (3-4 phases)</SelectItem>
                    <SelectItem value="detailed">Detailed (4-6 phases)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        )}

        {step === 2 && suggestion && (
          <div className="space-y-4 py-2" data-testid="kickoff-step-2">
            {suggestion.notes && (
              <div className="p-3 bg-purple-50 rounded-lg border border-purple-200 text-sm text-purple-900 italic">
                💡 {suggestion.notes}
              </div>
            )}

            <div>
              <h4 className="text-sm font-semibold text-[#0B1220] mb-2">
                Phases ({suggestion.phases?.length || 0})
              </h4>
              <div className="space-y-2">
                {(suggestion.phases || []).map((p, i) => (
                  <div key={i} className="p-3 border border-[#E6E8EC] rounded-lg">
                    <div className="flex items-center justify-between">
                      <div className="font-medium text-sm">{p.name}</div>
                      <div className="text-xs text-[#667085]">{p.duration_weeks} weeks</div>
                    </div>
                    {p.description && <div className="text-xs text-[#475467] mt-1">{p.description}</div>}
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h4 className="text-sm font-semibold text-[#0B1220] mb-2">
                Team roles ({suggestion.team_roles?.length || 0})
              </h4>
              <div className="grid grid-cols-2 gap-2">
                {(suggestion.team_roles || []).map((r, i) => (
                  <div key={i} className="p-2 bg-[#F9FAFB] rounded text-xs">
                    <div className="font-medium">{r.role}</div>
                    <div className="text-[#667085]">{r.allocation_pct}% allocation</div>
                    {r.why && <div className="text-[#94A3B8] mt-1 italic">{r.why}</div>}
                  </div>
                ))}
              </div>
            </div>

            {suggestion.budget_breakdown && (
              <div>
                <h4 className="text-sm font-semibold text-[#0B1220] mb-2">
                  Budget: {suggestion.budget_breakdown.total_estimated_hours}h total
                </h4>
                <div className="text-xs text-[#475467] flex flex-wrap gap-2">
                  {(suggestion.budget_breakdown.by_phase || []).map((b, i) => (
                    <span key={i} className="px-2 py-1 bg-[#F2F3F5] rounded">
                      {b.phase}: {b.hours}h
                    </span>
                  ))}
                </div>
              </div>
            )}

            {suggestion.risks_to_watch && suggestion.risks_to_watch.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-orange-700 mb-2">Risks to watch</h4>
                <ul className="text-xs text-[#475467] space-y-1">
                  {suggestion.risks_to_watch.map((r, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-orange-500">•</span><span>{r}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {suggestion.kickoff_checklist && (
              <div>
                <h4 className="text-sm font-semibold text-emerald-700 mb-2">Kickoff checklist</h4>
                <ul className="text-xs text-[#475467] space-y-1">
                  {suggestion.kickoff_checklist.map((c, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <CheckCircle size={12} className="text-emerald-500 mt-0.5 flex-shrink-0" />
                      <span>{c}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <DialogFooter className="gap-2">
          {step === 2 && (
            <Button variant="outline" onClick={() => setStep(1)}>
              <ArrowLeft size={14} className="mr-1" /> Back
            </Button>
          )}
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          {step === 1 && (
            <Button
              onClick={() => suggestMutation.mutate()}
              disabled={!form.name || !form.goal || suggestMutation.isPending}
              data-testid="kickoff-suggest-btn"
            >
              {suggestMutation.isPending ? <Loader2 size={14} className="mr-1 animate-spin" /> : <Sparkles size={14} className="mr-1" />}
              {suggestMutation.isPending ? 'Thinking…' : 'Suggest plan'}
            </Button>
          )}
          {step === 2 && (
            <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending}
                    data-testid="kickoff-create-btn">
              {createMutation.isPending ? <Loader2 size={14} className="mr-1 animate-spin" /> : <ArrowRight size={14} className="mr-1" />}
              {createMutation.isPending ? 'Creating…' : 'Create project with these phases'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default KickoffWizardDialog;
