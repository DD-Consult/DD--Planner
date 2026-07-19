import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getHolidays, createHoliday, deleteHoliday } from '../api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Calendar, Plus, Trash2, Loader2, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import { format } from 'date-fns';

const Holidays = () => {
  const queryClient = useQueryClient();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    date: '',
  });
  const [error, setError] = useState('');

  // Fetch holidays
  const { data: holidays, isLoading } = useQuery({
    queryKey: ['holidays'],
    queryFn: async () => {
      const response = await getHolidays();
      return response.data;
    },
  });

  // Create holiday mutation
  const createMutation = useMutation({
    mutationFn: createHoliday,
    onSuccess: () => {
      toast.success('Holiday added successfully');
      queryClient.invalidateQueries({ queryKey: ['holidays'] });
      queryClient.invalidateQueries({ queryKey: ['capacity'] });
      handleCloseDialog();
    },
    onError: (error) => {
      const message = error.response?.data?.detail || 'Failed to add holiday';
      setError(message);
      toast.error(message);
    },
  });

  // Delete holiday mutation
  const deleteMutation = useMutation({
    mutationFn: deleteHoliday,
    onSuccess: () => {
      toast.success('Holiday deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['holidays'] });
      queryClient.invalidateQueries({ queryKey: ['capacity'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to delete holiday');
    },
  });

  const handleCloseDialog = () => {
    setIsDialogOpen(false);
    setFormData({ name: '', date: '' });
    setError('');
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');

    if (!formData.name || !formData.date) {
      setError('Please fill in all fields');
      return;
    }

    createMutation.mutate(formData);
  };

  const handleDelete = (id) => {
    if (window.confirm('Are you sure you want to delete this holiday?')) {
      deleteMutation.mutate(id);
    }
  };

  return (
    <div className="space-y-6" data-testid="holidays-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold flex items-center gap-3" style={{ fontFamily: 'Space Grotesk' }}>
            <Calendar size={32} />
            Global Holidays
          </h1>
          <p className="text-sm text-[#667085] mt-1">
            Manage company-wide holidays that affect all resources
          </p>
        </div>
        <Button onClick={() => setIsDialogOpen(true)} data-testid="add-holiday-button">
          <Plus size={16} className="mr-2" />
          Add Holiday
        </Button>
      </div>

      {/* Holidays Table */}
      <div className="bg-white border border-[#E6E8EC] rounded-lg">
        {isLoading ? (
          <div className="p-8 text-center text-[#667085]">
            <Loader2 className="animate-spin mx-auto mb-2" size={24} />
            Loading holidays...
          </div>
        ) : holidays?.length === 0 ? (
          <div className="p-8 text-center">
            <Calendar size={48} className="mx-auto mb-4 text-[#98A2B3]" />
            <p className="text-[#667085] mb-4">No holidays configured yet</p>
            <Button variant="outline" onClick={() => setIsDialogOpen(true)}>
              <Plus size={16} className="mr-2" />
              Add Your First Holiday
            </Button>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Holiday Name</TableHead>
                <TableHead>Date</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {holidays?.map((holiday) => (
                <TableRow key={holiday.id} data-testid={`holiday-row-${holiday.id}`}>
                  <TableCell className="font-medium">{holiday.name}</TableCell>
                  <TableCell>
                    {format(new Date(holiday.date), 'MMMM d, yyyy')}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(holiday.id)}
                      disabled={deleteMutation.isLoading}
                      data-testid={`delete-holiday-${holiday.id}`}
                    >
                      <Trash2 size={16} className="text-[#EF4444]" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {/* Add Holiday Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={handleCloseDialog}>
        <DialogContent data-testid="add-holiday-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Calendar size={20} className="text-[#1570EF]" />
              Add Global Holiday
            </DialogTitle>
          </DialogHeader>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Holiday Name */}
            <div>
              <Label htmlFor="name">Holiday Name *</Label>
              <Input
                id="name"
                type="text"
                placeholder="e.g., Christmas Day"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                data-testid="holiday-name-input"
              />
            </div>

            {/* Date */}
            <div>
              <Label htmlFor="date">Date *</Label>
              <Input
                id="date"
                type="date"
                value={formData.date}
                onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                data-testid="holiday-date-input"
              />
            </div>

            {/* Error Message */}
            {error && (
              <Alert variant="destructive" data-testid="holiday-error">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {/* Actions */}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={handleCloseDialog}
                disabled={createMutation.isLoading}
                data-testid="holiday-cancel"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={createMutation.isLoading}
                data-testid="holiday-submit"
              >
                {createMutation.isLoading ? (
                  <>
                    <Loader2 size={16} className="mr-2 animate-spin" />
                    Adding...
                  </>
                ) : (
                  'Add Holiday'
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Holidays;
