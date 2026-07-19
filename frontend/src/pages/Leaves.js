import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getLeaves, deleteLeave, getResources } from '../api';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { CalendarOff, Plus, Trash2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { format } from 'date-fns';
import { AddLeaveDialog } from '../components/AddLeaveDialog';

const Leaves = () => {
  const queryClient = useQueryClient();
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  // Fetch leaves
  const { data: leaves, isLoading: leavesLoading } = useQuery({
    queryKey: ['leaves'],
    queryFn: async () => {
      const response = await getLeaves();
      return response.data;
    },
  });

  // Fetch resources for the dialog
  const { data: resources } = useQuery({
    queryKey: ['resources'],
    queryFn: async () => {
      const response = await getResources();
      return response.data;
    },
  });

  // Delete leave mutation
  const deleteMutation = useMutation({
    mutationFn: deleteLeave,
    onSuccess: () => {
      toast.success('Leave deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['leaves'] });
      queryClient.invalidateQueries({ queryKey: ['capacity'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to delete leave');
    },
  });

  const handleDelete = (id) => {
    if (window.confirm('Are you sure you want to delete this leave entry?')) {
      deleteMutation.mutate(id);
    }
  };

  const getLeaveTypeColor = (type) => {
    const colors = {
      vacation: 'bg-[#E6F7FB] text-[#0B5566] border-[#B2E7F5]',
      sick: 'bg-[#FFF8E5] text-[#7A4E00] border-[#FCD34D]',
      personal: 'bg-[#F0F2F5] text-[#475467] border-[#D0D5DD]',
      other: 'bg-[#F7F7F8] text-[#667085] border-[#E6E8EC]',
    };
    return colors[type] || colors.other;
  };

  const getResourceName = (resourceId) => {
    const resource = resources?.find((r) => r.id === resourceId);
    return resource ? `${resource.name} (${resource.role})` : resourceId;
  };

  return (
    <div className="space-y-6" data-testid="leaves-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold flex items-center gap-3" style={{ fontFamily: 'Space Grotesk' }}>
            <CalendarOff size={32} />
            Time Off Management
          </h1>
          <p className="text-sm text-[#667085] mt-1">
            Manage vacation, sick leave, and other time off for resources
          </p>
        </div>
        <Button onClick={() => setIsDialogOpen(true)} data-testid="add-leave-button">
          <Plus size={16} className="mr-2" />
          Add Time Off
        </Button>
      </div>

      {/* Leaves Table */}
      <div className="bg-white border border-[#E6E8EC] rounded-lg">
        {leavesLoading ? (
          <div className="p-8 text-center text-[#667085]">
            <Loader2 className="animate-spin mx-auto mb-2" size={24} />
            Loading leaves...
          </div>
        ) : leaves?.length === 0 ? (
          <div className="p-8 text-center">
            <CalendarOff size={48} className="mx-auto mb-4 text-[#98A2B3]" />
            <p className="text-[#667085] mb-4">No time off entries yet</p>
            <Button variant="outline" onClick={() => setIsDialogOpen(true)}>
              <Plus size={16} className="mr-2" />
              Add First Time Off
            </Button>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Resource</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Start Date</TableHead>
                <TableHead>End Date</TableHead>
                <TableHead>Notes</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {leaves?.map((leave) => (
                <TableRow key={leave._id} data-testid={`leave-row-${leave._id}`}>
                  <TableCell className="font-medium">
                    {getResourceName(leave.resource_id)}
                  </TableCell>
                  <TableCell>
                    <Badge className={getLeaveTypeColor(leave.type)}>
                      {leave.type}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {format(new Date(leave.start_date), 'MMM d, yyyy')}
                  </TableCell>
                  <TableCell>
                    {format(new Date(leave.end_date), 'MMM d, yyyy')}
                  </TableCell>
                  <TableCell className="text-[#667085] text-sm">
                    {leave.notes || '—'}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(leave._id)}
                      disabled={deleteMutation.isLoading}
                      data-testid={`delete-leave-${leave._id}`}
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

      {/* Add Leave Dialog */}
      <AddLeaveDialog
        isOpen={isDialogOpen}
        onClose={() => setIsDialogOpen(false)}
        resources={resources}
      />
    </div>
  );
};

export default Leaves;
