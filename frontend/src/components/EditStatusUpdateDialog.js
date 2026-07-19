import React, { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { editStatusUpdate } from '../api';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import { toast } from 'sonner';
import { Edit2, X } from 'lucide-react';

const EditStatusUpdateDialog = ({ open, onClose, statusUpdate, projectId, statusOptions }) => {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    health: '',
    schedule_status: '',
    actual_progress: '',
    accomplishments: '',
    blockers: '',
    next_steps: '',
    notes: '',
  });

  // Initialize form when dialog opens
  useEffect(() => {
    if (statusUpdate && open) {
      setFormData({
        health: statusUpdate.health || 'Green',
        schedule_status: statusUpdate.schedule_status || 'On Track',
        actual_progress: statusUpdate.actual_progress?.toString() || '',
        accomplishments: statusUpdate.accomplishments || statusUpdate.progress_summary || '',
        blockers: Array.isArray(statusUpdate.blockers) 
          ? statusUpdate.blockers.join(', ') 
          : (statusUpdate.blockers || ''),
        next_steps: statusUpdate.next_steps || statusUpdate.next_week_plan || '',
        notes: statusUpdate.notes || '',
      });
    }
  }, [statusUpdate, open]);

  const editMutation = useMutation({
    mutationFn: (data) => editStatusUpdate(statusUpdate.id, data),
    onSuccess: () => {
      toast.success('Status update edited successfully');
      queryClient.invalidateQueries(['projectStatusUpdates', projectId]);
      queryClient.invalidateQueries(['project', projectId]);
      queryClient.invalidateQueries(['projects']);
      onClose();
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to edit status update');
    },
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    
    const submitData = {
      health: formData.health,
      schedule_status: formData.schedule_status,
      actual_progress: formData.actual_progress ? parseInt(formData.actual_progress) : null,
      accomplishments: formData.accomplishments || null,
      blockers: formData.blockers || null,
      next_steps: formData.next_steps || null,
      notes: formData.notes || null,
    };
    
    editMutation.mutate(submitData);
  };

  const healthOptions = statusOptions?.health_options || ['Green', 'Amber', 'Red'];
  const scheduleOptions = statusOptions?.schedule_options || ['On Track', 'Ahead of Schedule', 'Delayed', 'At Risk'];

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Edit2 size={20} className="text-blue-600" />
            Edit Status Update
          </DialogTitle>
          <DialogDescription>
            Edit this project status update. Changes will be tracked with your username and timestamp.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Show original submitter info */}
          {statusUpdate && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-gray-600">Originally submitted by:</span>{' '}
                  <span className="font-medium">{statusUpdate.updated_by_name || statusUpdate.updated_by}</span>
                </div>
                <div className="text-xs text-gray-500">
                  {new Date(statusUpdate.created_at).toLocaleDateString('en-AU', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </div>
              </div>
              {statusUpdate.edited_by && (
                <div className="mt-1 text-xs text-gray-500">
                  Last edited by {statusUpdate.edited_by} on {new Date(statusUpdate.edited_at).toLocaleDateString()}
                </div>
              )}
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            {/* Health Status */}
            <div>
              <Label htmlFor="health">Health Status</Label>
              <Select value={formData.health} onValueChange={(value) => setFormData(prev => ({ ...prev, health: value }))}>
                <SelectTrigger>
                  <SelectValue placeholder="Select health" />
                </SelectTrigger>
                <SelectContent>
                  {healthOptions.map(option => (
                    <SelectItem key={option} value={option}>{option}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Schedule Status */}
            <div>
              <Label htmlFor="schedule_status">Schedule Status</Label>
              <Select value={formData.schedule_status} onValueChange={(value) => setFormData(prev => ({ ...prev, schedule_status: value }))}>
                <SelectTrigger>
                  <SelectValue placeholder="Select schedule" />
                </SelectTrigger>
                <SelectContent>
                  {scheduleOptions.map(option => (
                    <SelectItem key={option} value={option}>{option}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Progress */}
          <div>
            <Label htmlFor="actual_progress">
              Progress (%)
              <span className="ml-2 text-xs text-gray-500 font-normal">
                Leave empty to auto-calculate based on time elapsed
              </span>
            </Label>
            <Input
              id="actual_progress"
              type="number"
              min="0"
              max="100"
              value={formData.actual_progress}
              onChange={(e) => setFormData(prev => ({ ...prev, actual_progress: e.target.value }))}
              placeholder="Auto-calculated if empty"
            />
          </div>

          {/* Accomplishments */}
          <div>
            <Label htmlFor="accomplishments">Accomplishments</Label>
            <Textarea
              id="accomplishments"
              value={formData.accomplishments}
              onChange={(e) => setFormData(prev => ({ ...prev, accomplishments: e.target.value }))}
              placeholder="What was accomplished this week?"
              rows={3}
            />
          </div>

          {/* Blockers */}
          <div>
            <Label htmlFor="blockers">Blockers / Issues</Label>
            <Textarea
              id="blockers"
              value={formData.blockers}
              onChange={(e) => setFormData(prev => ({ ...prev, blockers: e.target.value }))}
              placeholder="Any blockers or issues? (comma or newline separated)"
              rows={2}
            />
          </div>

          {/* Next Steps */}
          <div>
            <Label htmlFor="next_steps">Next Steps</Label>
            <Textarea
              id="next_steps"
              value={formData.next_steps}
              onChange={(e) => setFormData(prev => ({ ...prev, next_steps: e.target.value }))}
              placeholder="What's planned for next week?"
              rows={3}
            />
          </div>

          {/* Notes */}
          <div>
            <Label htmlFor="notes">Additional Notes (Optional)</Label>
            <Textarea
              id="notes"
              value={formData.notes}
              onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
              placeholder="Any additional context or notes"
              rows={2}
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              <X size={14} className="mr-2" />
              Cancel
            </Button>
            <Button type="submit" disabled={editMutation.isPending}>
              {editMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default EditStatusUpdateDialog;
