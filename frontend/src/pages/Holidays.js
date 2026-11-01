import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getHolidays, createHoliday, deleteHoliday, getMe, getHolidayRegion, setHolidayRegion, refreshPublicHolidays, getLeaveTypes, createLeaveType, updateLeaveType, deleteLeaveType } from '../api';
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
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Calendar, Plus, Trash2, Loader2, AlertCircle, RefreshCw } from 'lucide-react';
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

  const { data: userData } = useQuery({
    queryKey: ['me'],
    queryFn: async () => { const r = await getMe(); return r.data; },
  });
  const isAdmin = userData?.role === 'admin' || userData?.role === 'super_admin';
  const isSuperAdmin = userData?.role === 'super_admin';

  // Fetch holidays
  const { data: holidays, isLoading } = useQuery({
    queryKey: ['holidays'],
    queryFn: async () => {
      const response = await getHolidays();
      return response.data;
    },
  });

  // Fetch holiday region (super_admin only)
  const { data: regionData } = useQuery({
    queryKey: ['holidayRegion'],
    queryFn: async () => {
      const response = await getHolidayRegion();
      return response.data;
    },
    enabled: isSuperAdmin,
  });

  // Fetch leave types (admin+)
  const { data: leaveTypes } = useQuery({
    queryKey: ['leaveTypes', true],
    queryFn: async () => {
      const response = await getLeaveTypes(true);
      return response.data;
    },
    enabled: isAdmin,
  });

  // Local state for region selector
  const [selectedRegion, setSelectedRegion] = useState('');
  const [newLeaveTypeName, setNewLeaveTypeName] = useState('');
  
  // Accrual config form for new leave type
  const [newLeaveTypeConfig, setNewLeaveTypeConfig] = useState({
    name: '',
    accrual_method: 'none',
    annual_allowance: '',
    accrual_rate: '',
    allow_negative: false,
  });
  
  // Editing existing type
  const [editingTypeId, setEditingTypeId] = useState(null);
  const [editTypeConfig, setEditTypeConfig] = useState({});

  // Update selected region when data loads
  React.useEffect(() => {
    if (regionData?.region) {
      setSelectedRegion(regionData.region);
    }
  }, [regionData]);

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

  // Set region mutation
  const setRegionMutation = useMutation({
    mutationFn: setHolidayRegion,
    onSuccess: (response) => {
      toast.success(response.data.message || 'Region updated and holidays loaded');
      queryClient.invalidateQueries({ queryKey: ['holidayRegion'] });
      queryClient.invalidateQueries({ queryKey: ['holidays'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to update region');
    },
  });

  // Refresh public holidays mutation
  const refreshMutation = useMutation({
    mutationFn: refreshPublicHolidays,
    onSuccess: (response) => {
      toast.success(response.data.message || 'Public holidays refreshed');
      queryClient.invalidateQueries({ queryKey: ['holidays'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to refresh holidays');
    },
  });

  // Create leave type mutation
  const createLeaveTypeMutation = useMutation({
    mutationFn: createLeaveType,
    onSuccess: () => {
      toast.success('Leave type added');
      queryClient.invalidateQueries({ queryKey: ['leaveTypes'] });
      setNewLeaveTypeConfig({
        name: '',
        accrual_method: 'none',
        annual_allowance: '',
        accrual_rate: '',
        allow_negative: false,
      });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to add leave type');
    },
  });

  // Update leave type mutation
  const updateLeaveTypeMutation = useMutation({
    mutationFn: ({ id, data }) => updateLeaveType(id, data),
    onSuccess: () => {
      toast.success('Leave type updated');
      queryClient.invalidateQueries({ queryKey: ['leaveTypes'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to update leave type');
    },
  });

  // Delete leave type mutation
  const deleteLeaveTypeMutation = useMutation({
    mutationFn: deleteLeaveType,
    onSuccess: () => {
      toast.success('Leave type deleted');
      queryClient.invalidateQueries({ queryKey: ['leaveTypes'] });
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to delete leave type');
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

  const handleSaveRegion = () => {
    if (selectedRegion) {
      setRegionMutation.mutate(selectedRegion);
    }
  };

  const handleRefreshHolidays = () => {
    refreshMutation.mutate();
  };

  const handleToggleLeaveType = (id, currentActive) => {
    updateLeaveTypeMutation.mutate({ id, data: { is_active: !currentActive } });
  };

  const handleDeleteLeaveType = (id) => {
    if (window.confirm('Are you sure you want to delete this leave type?')) {
      deleteLeaveTypeMutation.mutate(id);
    }
  };

  const handleAddLeaveType = () => {
    if (!newLeaveTypeConfig.name.trim()) {
      toast.error('Please enter a leave type name');
      return;
    }
    // Build payload with accrual config
    const payload = {
      name: newLeaveTypeConfig.name.trim(),
      accrual_method: newLeaveTypeConfig.accrual_method,
      allow_negative: newLeaveTypeConfig.allow_negative,
    };
    if (newLeaveTypeConfig.accrual_method === 'fixed_annual' && newLeaveTypeConfig.annual_allowance) {
      payload.annual_allowance = parseFloat(newLeaveTypeConfig.annual_allowance);
    }
    if (newLeaveTypeConfig.accrual_method === 'monthly_accrual' && newLeaveTypeConfig.accrual_rate) {
      payload.accrual_rate = parseFloat(newLeaveTypeConfig.accrual_rate);
    }
    createLeaveTypeMutation.mutate(payload);
  };
  
  const handleEditLeaveType = (type) => {
    setEditingTypeId(type.id);
    setEditTypeConfig({
      accrual_method: type.accrual_method || 'none',
      annual_allowance: type.annual_allowance || '',
      accrual_rate: type.accrual_rate || '',
      allow_negative: type.allow_negative || false,
    });
  };
  
  const handleSaveEditLeaveType = (id) => {
    const payload = {
      accrual_method: editTypeConfig.accrual_method,
      allow_negative: editTypeConfig.allow_negative,
    };
    if (editTypeConfig.accrual_method === 'fixed_annual' && editTypeConfig.annual_allowance) {
      payload.annual_allowance = parseFloat(editTypeConfig.annual_allowance);
    } else {
      payload.annual_allowance = null;
    }
    if (editTypeConfig.accrual_method === 'monthly_accrual' && editTypeConfig.accrual_rate) {
      payload.accrual_rate = parseFloat(editTypeConfig.accrual_rate);
    } else {
      payload.accrual_rate = null;
    }
    updateLeaveTypeMutation.mutate({ id, data: payload });
    setEditingTypeId(null);
  };
  
  const getAccrualSummary = (type) => {
    if (type.accrual_method === 'fixed_annual') {
      return `Fixed: ${type.annual_allowance || 0} days/yr`;
    }
    if (type.accrual_method === 'monthly_accrual') {
      return `Accrues ${type.accrual_rate || 0}/mo`;
    }
    return 'Not tracked';
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
        {isAdmin && (
          <Button onClick={() => setIsDialogOpen(true)} data-testid="add-holiday-button">
            <Plus size={16} className="mr-2" />
            Add Holiday
          </Button>
        )}
      </div>

      {/* Region Selector Card (super_admin only) */}
      {isSuperAdmin && (
        <Card data-testid="holiday-region-card" className="border-[#E6E8EC]">
          <CardHeader>
            <CardTitle className="text-lg" style={{ fontFamily: 'Space Grotesk' }}>
              Public Holiday Region
            </CardTitle>
            <CardDescription>
              Select your region to automatically load public holidays
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-end gap-3">
              <div className="flex-1">
                <Label htmlFor="region-select">Region</Label>
                <Select
                  value={selectedRegion}
                  onValueChange={setSelectedRegion}
                >
                  <SelectTrigger id="region-select" data-testid="holiday-region-select">
                    <SelectValue placeholder="Select a region" />
                  </SelectTrigger>
                  <SelectContent>
                    {regionData?.available?.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button
                onClick={handleSaveRegion}
                disabled={setRegionMutation.isPending || !selectedRegion}
                data-testid="save-region-btn"
                style={{ backgroundColor: '#1570EF' }}
              >
                {setRegionMutation.isPending ? (
                  <>
                    <Loader2 size={16} className="mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  'Save & Load Holidays'
                )}
              </Button>
              <Button
                onClick={handleRefreshHolidays}
                disabled={refreshMutation.isPending}
                variant="outline"
                data-testid="refresh-holidays-btn"
              >
                {refreshMutation.isPending ? (
                  <>
                    <Loader2 size={16} className="mr-2 animate-spin" />
                    Refreshing...
                  </>
                ) : (
                  <>
                    <RefreshCw size={16} className="mr-2" />
                    Refresh Public Holidays
                  </>
                )}
              </Button>
            </div>
            {regionData && (
              <div className="text-sm text-[#667085]">
                Current: <span className="font-medium text-[#0B1220]">{regionData.label}</span>
                {regionData.holidays_loaded !== undefined && (
                  <span className="ml-2">
                    ({regionData.holidays_loaded} holidays loaded for {regionData.year || 'current year'})
                  </span>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Leave Types Configuration (admin+) */}
      {isAdmin && (
        <Card data-testid="leave-types-card" className="border-[#E6E8EC]">
          <CardHeader>
            <CardTitle className="text-lg" style={{ fontFamily: 'Space Grotesk' }}>
              Leave Types
            </CardTitle>
            <CardDescription>
              Configure available leave types for time off requests
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Existing leave types */}
            <div className="space-y-2">
              {leaveTypes?.map((type) => (
                <div
                  key={type.id}
                  className="p-3 bg-[#F7F9FC] rounded-md border border-[#E6E8EC]"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3 flex-1">
                      <span className="font-medium text-[#0B1220]">{type.name}</span>
                      <Badge
                        variant="outline"
                        className={type.is_system ? 'bg-blue-50 text-blue-700 border-blue-200' : 'bg-purple-50 text-purple-700 border-purple-200'}
                      >
                        {type.is_system ? 'System' : 'Custom'}
                      </Badge>
                      {!type.is_active && (
                        <Badge variant="outline" className="bg-gray-100 text-gray-600 border-gray-300">
                          Inactive
                        </Badge>
                      )}
                      <span className="text-xs text-[#667085]">{getAccrualSummary(type)}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={type.is_active}
                        onCheckedChange={() => handleToggleLeaveType(type.id, type.is_active)}
                        disabled={updateLeaveTypeMutation.isPending}
                        data-testid={`leave-type-toggle-${type.id}`}
                      />
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleEditLeaveType(type)}
                        disabled={updateLeaveTypeMutation.isPending}
                        data-testid={`leave-type-edit-${type.id}`}
                        title="Edit accrual config"
                      >
                        <span className="text-[#1570EF]">✎</span>
                      </Button>
                      {!type.is_system && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteLeaveType(type.id)}
                          disabled={deleteLeaveTypeMutation.isPending}
                          data-testid={`leave-type-delete-${type.id}`}
                        >
                          <Trash2 size={16} className="text-[#EF4444]" />
                        </Button>
                      )}
                    </div>
                  </div>
                  
                  {/* Inline edit form */}
                  {editingTypeId === type.id && (
                    <div className="mt-2 p-3 bg-white rounded border border-[#E6E8EC] space-y-3">
                      <div>
                        <Label htmlFor={`accrual-method-${type.id}`} className="text-xs">Accrual Method</Label>
                        <Select
                          value={editTypeConfig.accrual_method}
                          onValueChange={(val) => setEditTypeConfig({...editTypeConfig, accrual_method: val})}
                        >
                          <SelectTrigger id={`accrual-method-${type.id}`} data-testid={`accrual-method-select-${type.id}`} className="h-8 text-sm">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="none">Not tracked</SelectItem>
                            <SelectItem value="fixed_annual">Fixed annual allowance</SelectItem>
                            <SelectItem value="monthly_accrual">Accrue monthly</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      
                      {editTypeConfig.accrual_method === 'fixed_annual' && (
                        <div>
                          <Label htmlFor={`annual-allowance-${type.id}`} className="text-xs">Annual Allowance (days)</Label>
                          <Input
                            id={`annual-allowance-${type.id}`}
                            type="number"
                            step="0.5"
                            value={editTypeConfig.annual_allowance}
                            onChange={(e) => setEditTypeConfig({...editTypeConfig, annual_allowance: e.target.value})}
                            data-testid={`annual-allowance-input-${type.id}`}
                            className="h-8 text-sm"
                          />
                        </div>
                      )}
                      
                      {editTypeConfig.accrual_method === 'monthly_accrual' && (
                        <div>
                          <Label htmlFor={`accrual-rate-${type.id}`} className="text-xs">Accrual Rate (days/month)</Label>
                          <Input
                            id={`accrual-rate-${type.id}`}
                            type="number"
                            step="0.1"
                            value={editTypeConfig.accrual_rate}
                            onChange={(e) => setEditTypeConfig({...editTypeConfig, accrual_rate: e.target.value})}
                            data-testid={`accrual-rate-input-${type.id}`}
                            className="h-8 text-sm"
                          />
                        </div>
                      )}
                      
                      <div className="flex items-center gap-2">
                        <Switch
                          id={`allow-negative-${type.id}`}
                          checked={editTypeConfig.allow_negative}
                          onCheckedChange={(val) => setEditTypeConfig({...editTypeConfig, allow_negative: val})}
                          data-testid={`allow-negative-toggle-${type.id}`}
                        />
                        <Label htmlFor={`allow-negative-${type.id}`} className="text-xs cursor-pointer">Allow negative balance</Label>
                      </div>
                      
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          onClick={() => handleSaveEditLeaveType(type.id)}
                          disabled={updateLeaveTypeMutation.isPending}
                          data-testid={`save-leave-type-btn-${type.id}`}
                          style={{ backgroundColor: '#1570EF' }}
                        >
                          {updateLeaveTypeMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : 'Save'}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setEditingTypeId(null)}
                          disabled={updateLeaveTypeMutation.isPending}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Add new leave type */}
            <div className="pt-2 border-t border-[#E6E8EC] space-y-3">
              <Input
                placeholder="New leave type name"
                value={newLeaveTypeConfig.name}
                onChange={(e) => setNewLeaveTypeConfig({...newLeaveTypeConfig, name: e.target.value})}
                data-testid="new-leave-type-input"
              />
              
              <div>
                <Label htmlFor="new-accrual-method" className="text-xs">Accrual Method</Label>
                <Select
                  value={newLeaveTypeConfig.accrual_method}
                  onValueChange={(val) => setNewLeaveTypeConfig({...newLeaveTypeConfig, accrual_method: val})}
                >
                  <SelectTrigger id="new-accrual-method" data-testid="new-accrual-method-select" className="h-9 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Not tracked</SelectItem>
                    <SelectItem value="fixed_annual">Fixed annual allowance</SelectItem>
                    <SelectItem value="monthly_accrual">Accrue monthly</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              {newLeaveTypeConfig.accrual_method === 'fixed_annual' && (
                <div>
                  <Label htmlFor="new-annual-allowance" className="text-xs">Annual Allowance (days)</Label>
                  <Input
                    id="new-annual-allowance"
                    type="number"
                    step="0.5"
                    value={newLeaveTypeConfig.annual_allowance}
                    onChange={(e) => setNewLeaveTypeConfig({...newLeaveTypeConfig, annual_allowance: e.target.value})}
                    data-testid="new-annual-allowance-input"
                    className="h-9 text-sm"
                  />
                </div>
              )}
              
              {newLeaveTypeConfig.accrual_method === 'monthly_accrual' && (
                <div>
                  <Label htmlFor="new-accrual-rate" className="text-xs">Accrual Rate (days/month)</Label>
                  <Input
                    id="new-accrual-rate"
                    type="number"
                    step="0.1"
                    value={newLeaveTypeConfig.accrual_rate}
                    onChange={(e) => setNewLeaveTypeConfig({...newLeaveTypeConfig, accrual_rate: e.target.value})}
                    data-testid="new-accrual-rate-input"
                    className="h-9 text-sm"
                  />
                </div>
              )}
              
              <div className="flex items-center gap-2">
                <Switch
                  id="new-allow-negative"
                  checked={newLeaveTypeConfig.allow_negative}
                  onCheckedChange={(val) => setNewLeaveTypeConfig({...newLeaveTypeConfig, allow_negative: val})}
                  data-testid="new-allow-negative-toggle"
                />
                <Label htmlFor="new-allow-negative" className="text-xs cursor-pointer">Allow negative balance</Label>
              </div>
              
              <Button
                onClick={handleAddLeaveType}
                disabled={createLeaveTypeMutation.isPending || !newLeaveTypeConfig.name.trim()}
                data-testid="add-leave-type-btn"
                className="w-full"
              >
                {createLeaveTypeMutation.isPending ? (
                  <Loader2 size={16} className="animate-spin mr-2" />
                ) : (
                  <Plus size={16} className="mr-2" />
                )}
                Add Leave Type
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

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
            {isAdmin && (
              <Button variant="outline" onClick={() => setIsDialogOpen(true)}>
                <Plus size={16} className="mr-2" />
                Add Your First Holiday
              </Button>
            )}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Holiday Name</TableHead>
                <TableHead>Date</TableHead>
                {isAdmin && <TableHead className="text-right">Actions</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {holidays?.map((holiday) => (
                <TableRow key={holiday.id} data-testid={`holiday-row-${holiday.id}`}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      {holiday.name}
                      {holiday.is_public_holiday && (
                        <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                          Public
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {format(new Date(holiday.date), 'MMMM d, yyyy')}
                      {holiday.source && (
                        <Badge variant="outline" className="text-xs">
                          {holiday.source === 'auto' ? 'Auto' : 'Manual'}
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  {isAdmin && (
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
                  )}
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
