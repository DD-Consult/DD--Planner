import React, { useState, useEffect } from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import WeekdayDateInput from './ui/weekday-date-input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { Checkbox } from './ui/checkbox';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from './ui/select';
import { X, Loader2, Flag } from 'lucide-react';
import { setWBSTaskBaseline } from '../api';
import { toast } from 'sonner';
import WBSCommentSection from './WBSCommentSection';

const STATUS_OPTIONS = [
  { value: 'todo', label: 'To Do' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'done', label: 'Done' },
  { value: 'on_hold', label: 'On Hold' },
  { value: 'blocked', label: 'Blocked' },
];

const PRIORITY_OPTIONS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
];

const WBSTaskDialog = ({
  open,
  onClose,
  task,          // null = create, object = edit
  projectId,
  phases,        // array of {id, name} objects
  resources,     // array of {id, name}
  tasks,         // all tasks for parent/dep selects
  onSubmit,      // async fn(data) → void
  isLoading,
  onBaselineSet, // optional fn() → void, called after baseline is set
  currentUserEmail, // for comments section
}) => {
  const isEdit = !!task;
  const [baselineSaving, setBaselineSaving] = useState(false);

  const formatBaselineDate = (d) => {
    if (!d) return '—';
    try {
      return new Date(d).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' });
    } catch {
      return d;
    }
  };

  const handleSetBaseline = async () => {
    if (!task) return;
    const taskId = task.id || task._id;
    setBaselineSaving(true);
    try {
      await setWBSTaskBaseline(taskId);
      toast.success('Baseline set to current dates');
      if (onBaselineSet) onBaselineSet();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to set baseline');
    } finally {
      setBaselineSaving(false);
    }
  };

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    phase_name: '__none__',
    parent_id: '__none__',
    assigned_to: '__none__',
    status: 'todo',
    priority: 'medium',
    estimated_hours: '',
    start_date: '',
    end_date: '',
    order: 0,
    dependencies: [],
    labels: [],
    is_milestone: false,
    milestone_date: '',
  });

  const [depToAdd, setDepToAdd] = useState('__none__');
  const [labelInput, setLabelInput] = useState('');

  // Populate form when editing
  useEffect(() => {
    if (task) {
      setFormData({
        name: task.name || '',
        description: task.description || '',
        phase_name: task.phase_name || '__none__',
        parent_id: task.parent_id || '__none__',
        assigned_to: task.assigned_to || '__none__',
        status: task.status || 'todo',
        priority: task.priority || 'medium',
        estimated_hours: task.estimated_hours != null ? String(task.estimated_hours) : '',
        start_date: task.start_date || '',
        end_date: task.end_date || '',
        order: task.order ?? 0,
        dependencies: task.dependencies || [],
        labels: task.labels || [],
        is_milestone: task.is_milestone || false,
        milestone_date: task.milestone_date || '',
      });
    } else {
      setFormData({
        name: '',
        description: '',
        phase_name: '__none__',
        parent_id: '__none__',
        assigned_to: '__none__',
        status: 'todo',
        priority: 'medium',
        estimated_hours: '',
        start_date: '',
        end_date: '',
        order: 0,
        dependencies: [],
        labels: [],
        is_milestone: false,
        milestone_date: '',
      });
    }
    setDepToAdd('__none__');
    setLabelInput('');
  }, [task, open]);

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleAddDependency = () => {
    if (depToAdd && depToAdd !== '__none__' && !formData.dependencies.includes(depToAdd)) {
      setFormData(prev => ({
        ...prev,
        dependencies: [...prev.dependencies, depToAdd],
      }));
      setDepToAdd('__none__');
    }
  };

  const handleRemoveDependency = (depId) => {
    setFormData(prev => ({
      ...prev,
      dependencies: prev.dependencies.filter(d => d !== depId),
    }));
  };

  const handleAddLabel = (e) => {
    if (e.key === 'Enter' && labelInput.trim()) {
      e.preventDefault();
      if (!formData.labels.includes(labelInput.trim())) {
        setFormData(prev => ({ ...prev, labels: [...prev.labels, labelInput.trim()] }));
      }
      setLabelInput('');
    }
  };

  const handleRemoveLabel = (label) => {
    setFormData(prev => ({
      ...prev,
      labels: prev.labels.filter(l => l !== label),
    }));
  };

  const handleSubmit = async () => {
    if (!formData.name.trim()) return;

    const payload = {
      name: formData.name.trim(),
      description: formData.description.trim(),
      phase_name: formData.phase_name !== '__none__' ? formData.phase_name : null,
      parent_id: formData.parent_id !== '__none__' ? formData.parent_id : null,
      assigned_to: formData.assigned_to !== '__none__' ? formData.assigned_to : null,
      status: formData.status,
      priority: formData.priority,
      estimated_hours: formData.is_milestone ? 0 : (formData.estimated_hours !== '' ? parseFloat(formData.estimated_hours) || 0 : 0),
      start_date: formData.is_milestone ? formData.milestone_date : formData.start_date || null,
      end_date: formData.is_milestone ? formData.milestone_date : formData.end_date || null,
      order: formData.order || 0,
      dependencies: formData.dependencies,
      labels: formData.labels,
      is_milestone: formData.is_milestone,
      milestone_date: formData.is_milestone ? formData.milestone_date : null,
    };

    await onSubmit(payload);
  };

  // Eligible parent tasks (exclude self and own children)
  const eligibleParents = tasks ? tasks.filter(t => {
    if (isEdit && t.id === task?.id) return false;
    if (isEdit && t.parent_id === task?.id) return false;
    return true;
  }) : [];

  // Eligible dependencies (exclude self)
  const eligibleDeps = tasks ? tasks.filter(t => {
    if (isEdit && t.id === task?.id) return false;
    if (formData.dependencies.includes(t.id)) return false;
    return true;
  }) : [];

  const getTaskNameById = (id) => {
    const t = tasks?.find(t => t.id === id);
    return t ? t.name : id;
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit Task' : 'Add New Task'}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Name */}
          <div>
            <Label htmlFor="task-name">Task Name *</Label>
            <Input
              id="task-name"
              value={formData.name}
              onChange={e => handleChange('name', e.target.value)}
              placeholder="Enter task name..."
              className="mt-1"
            />
          </div>

          {/* Description */}
          <div>
            <Label htmlFor="task-desc">Description</Label>
            <Textarea
              id="task-desc"
              value={formData.description}
              onChange={e => handleChange('description', e.target.value)}
              placeholder="Optional task description..."
              className="mt-1"
              rows={2}
            />
          </div>

          {/* Milestone Checkbox */}
          <div className="flex items-center space-x-2 p-3 bg-purple-50 border border-purple-200 rounded-lg">
            <Checkbox
              id="is-milestone"
              checked={formData.is_milestone}
              onCheckedChange={v => handleChange('is_milestone', v)}
            />
            <div className="flex-1">
              <Label htmlFor="is-milestone" className="text-sm font-medium cursor-pointer">
                <Flag className="inline w-4 h-4 mr-1 text-purple-600" />
                This is a Milestone
              </Label>
              <p className="text-xs text-gray-500 mt-0.5">
                Milestones are 0-hour markers for key project events
              </p>
            </div>
          </div>

          {/* Milestone Date (shown only if is_milestone is true) */}
          {formData.is_milestone && (
            <div className="bg-purple-50 p-3 rounded-lg border border-purple-200">
              <Label htmlFor="milestone-date">Milestone Date *</Label>
              <WeekdayDateInput
                id="milestone-date"
                value={formData.milestone_date}
                onChange={e => handleChange('milestone_date', e.target.value)}
                className="mt-1"
              />
            </div>
          )}

          {/* Phase + Priority row */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Phase</Label>
              <Select value={formData.phase_name} onValueChange={v => handleChange('phase_name', v)}>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Select phase" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">No phase</SelectItem>
                  {phases && phases.map(phase => {
                    const phaseName = typeof phase === 'string' ? phase : phase.name;
                    return (
                      <SelectItem key={phaseName} value={phaseName}>{phaseName}</SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Priority</Label>
              <Select value={formData.priority} onValueChange={v => handleChange('priority', v)}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PRIORITY_OPTIONS.map(opt => (
                    <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Status + Assigned */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Status</Label>
              <Select value={formData.status} onValueChange={v => handleChange('status', v)}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map(opt => (
                    <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Assigned To</Label>
              <Select value={formData.assigned_to} onValueChange={v => handleChange('assigned_to', v)}>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Unassigned" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Unassigned</SelectItem>
                  {resources && resources.map(r => (
                    <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Parent Task */}
          <div>
            <Label>Parent Task (for sub-tasks)</Label>
            <Select value={formData.parent_id} onValueChange={v => handleChange('parent_id', v)}>
              <SelectTrigger className="mt-1">
                <SelectValue placeholder="No parent (top-level)" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">No parent (top-level)</SelectItem>
                {eligibleParents.map(t => (
                  <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Dates + Hours row (hidden for milestones) */}
          {!formData.is_milestone && (
          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label>Start Date</Label>
              <WeekdayDateInput
                value={formData.start_date}
                onChange={e => handleChange('start_date', e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <Label>End Date</Label>
              <WeekdayDateInput
                value={formData.end_date}
                onChange={e => handleChange('end_date', e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <Label>Est. Hours</Label>
              <Input
                type="number"
                min="0"
                step="0.5"
                value={formData.estimated_hours}
                onChange={e => handleChange('estimated_hours', e.target.value)}
                placeholder="0"
                className="mt-1"
              />
            </div>
          </div>
          )}

          {/* Baseline (planned schedule) — only when editing an existing task */}
          {isEdit && (
            <div className="rounded-md border border-gray-200 bg-gray-50 p-3 flex items-center justify-between gap-3">
              <div className="text-xs text-gray-600">
                <div className="font-medium text-gray-700 flex items-center gap-1">
                  <Flag size={12} /> Baseline (planned)
                </div>
                <div className="mt-0.5">
                  {task.baseline_start_date || task.baseline_end_date ? (
                    <span>
                      {formatBaselineDate(task.baseline_start_date)} → {formatBaselineDate(task.baseline_end_date)}
                    </span>
                  ) : (
                    <span className="text-gray-400">No baseline set yet</span>
                  )}
                </div>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleSetBaseline}
                disabled={baselineSaving}
                title="Snapshot the current start/end dates as the committed baseline"
              >
                {baselineSaving ? <Loader2 size={14} className="mr-1.5 animate-spin" /> : <Flag size={14} className="mr-1.5" />}
                {(task.baseline_start_date || task.baseline_end_date) ? 'Update Baseline' : 'Set Baseline'}
              </Button>
            </div>
          )}

          {/* Dependencies */}
          <div>
            <Label>Dependencies</Label>
            <div className="flex gap-2 mt-1">
              <Select value={depToAdd} onValueChange={setDepToAdd}>
                <SelectTrigger className="flex-1">
                  <SelectValue placeholder="Add dependency..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Select a task...</SelectItem>
                  {eligibleDeps.map(t => (
                    <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button type="button" variant="outline" onClick={handleAddDependency} size="sm">
                Add
              </Button>
            </div>
            {formData.dependencies.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {formData.dependencies.map(depId => (
                  <Badge
                    key={depId}
                    variant="secondary"
                    className="flex items-center gap-1 cursor-pointer hover:bg-red-100"
                    onClick={() => handleRemoveDependency(depId)}
                  >
                    {getTaskNameById(depId)}
                    <X size={10} />
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Labels */}
          <div>
            <Label>Labels</Label>
            <Input
              value={labelInput}
              onChange={e => setLabelInput(e.target.value)}
              onKeyDown={handleAddLabel}
              placeholder="Type a label and press Enter..."
              className="mt-1"
            />
            {formData.labels.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {formData.labels.map(label => (
                  <Badge
                    key={label}
                    variant="outline"
                    className="flex items-center gap-1 cursor-pointer hover:bg-red-100"
                    onClick={() => handleRemoveLabel(label)}
                  >
                    {label}
                    <X size={10} />
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Comments Section (only for existing tasks) */}
        {isEdit && (
          <WBSCommentSection
            taskId={task?.id || task?._id}
            projectId={projectId}
            currentUserEmail={currentUserEmail}
          />
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!formData.name.trim() || isLoading}
            className="bg-[#1570EF] hover:bg-[#1570EF]/90 text-white"
          >
            {isLoading ? <Loader2 size={14} className="mr-2 animate-spin" /> : null}
            {isEdit ? 'Save Changes' : 'Add Task'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default WBSTaskDialog;
