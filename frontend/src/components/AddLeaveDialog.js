import React, { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createLeave } from '../api';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from './ui/dialog';
import { Alert, AlertDescription } from './ui/alert';
import { Calendar, Loader2, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

export const AddLeaveDialog = ({ isOpen, onClose, resources }) => {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    resource_id: undefined,
    start_date: '',
    end_date: '',
    type: 'vacation',
    notes: '',
  });
  const [error, setError] = useState('');
  
  // Reset form when dialog opens/closes
  useEffect(() => {
    if (!isOpen) {
      setFormData({
        resource_id: undefined,
        start_date: '',
        end_date: '',
        type: 'vacation',
        notes: '',
      });
      setError('');
    }
  }, [isOpen]);

  const createMutation = useMutation({
    mutationFn: createLeave,
    onSuccess: () => {
      toast.success('Time off added successfully');
      queryClient.invalidateQueries({ queryKey: ['leaves'] });
      queryClient.invalidateQueries({ queryKey: ['capacity'] });
      handleClose();
    },
    onError: (error) => {
      const message = error.response?.data?.detail || 'Failed to add time off';
      setError(message);
      toast.error(message);
    },
  });

  const handleClose = () => {
    setFormData({
      resource_id: undefined,
      start_date: '',
      end_date: '',
      type: 'vacation',
      notes: '',
    });
    setError('');
    onClose();
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');

    // Validation
    if (formData.resource_id === undefined || formData.resource_id === '' || !formData.start_date || !formData.end_date) {
      setError('Please fill in all required fields');
      return;
    }

    if (new Date(formData.start_date) > new Date(formData.end_date)) {
      setError('End date must be after start date');
      return;
    }

    createMutation.mutate(formData);
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose} modal={true}>
      <DialogContent data-testid="add-leave-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Calendar size={20} className="text-[#1570EF]" />
            Add Time Off
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Resource Selection */}
          <div>
            <Label htmlFor="resource">Resource *</Label>
            <Select
              value={formData.resource_id || ''}
              onValueChange={(value) => {
                setFormData({ ...formData, resource_id: value });
              }}
            >
              <SelectTrigger id="resource" data-testid="leave-resource-select">
                <SelectValue placeholder="Select a resource" />
              </SelectTrigger>
              <SelectContent>
                {resources?.map((resource) => (
                  <SelectItem key={resource.id} value={resource.id}>
                    {resource.name} - {resource.role}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Leave Type */}
          <div>
            <Label htmlFor="type">Leave Type *</Label>
            <Select
              value={formData.type}
              onValueChange={(value) => setFormData({ ...formData, type: value })}
            >
              <SelectTrigger id="type" data-testid="leave-type-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="vacation">Vacation</SelectItem>
                <SelectItem value="sick">Sick Leave</SelectItem>
                <SelectItem value="personal">Personal Day</SelectItem>
                <SelectItem value="other">Other</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Start Date */}
          <div>
            <Label htmlFor="start-date">Start Date *</Label>
            <Input
              id="start-date"
              type="date"
              value={formData.start_date}
              onChange={(e) =>
                setFormData({ ...formData, start_date: e.target.value })
              }
              data-testid="leave-start-date"
            />
          </div>

          {/* End Date */}
          <div>
            <Label htmlFor="end-date">End Date *</Label>
            <Input
              id="end-date"
              type="date"
              value={formData.end_date}
              onChange={(e) =>
                setFormData({ ...formData, end_date: e.target.value })
              }
              data-testid="leave-end-date"
            />
          </div>

          {/* Notes */}
          <div>
            <Label htmlFor="notes">Notes (Optional)</Label>
            <Input
              id="notes"
              type="text"
              placeholder="Add any additional notes"
              value={formData.notes}
              onChange={(e) =>
                setFormData({ ...formData, notes: e.target.value })
              }
              data-testid="leave-notes"
            />
          </div>

          {/* Error Message */}
          {error && (
            <Alert variant="destructive" data-testid="leave-error">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Actions */}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={createMutation.isLoading}
              data-testid="leave-cancel"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={createMutation.isLoading}
              data-testid="leave-submit"
            >
              {createMutation.isLoading ? (
                <>
                  <Loader2 size={16} className="mr-2 animate-spin" />
                  Adding...
                </>
              ) : (
                'Add Time Off'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
