import React, { useState, useEffect } from 'react';
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query';
import { createLeave, getLeaveTypes, getHolidays, addLeaveAttachment } from '../api';
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
import { Calendar, Loader2, AlertCircle, X, Paperclip } from 'lucide-react';
import { toast } from 'sonner';
import { format, parseISO } from 'date-fns';

export const AddLeaveDialog = ({ isOpen, onClose, resources, preselectedResourceId }) => {
  const queryClient = useQueryClient();
  const isPreselected = !!preselectedResourceId;

  // Fetch active leave types
  const { data: leaveTypes } = useQuery({
    queryKey: ['leaveTypes'],
    queryFn: async () => {
      const response = await getLeaveTypes(false); // active only
      return response.data;
    },
    enabled: isOpen,
  });

  // Fetch upcoming public holidays
  const { data: holidays } = useQuery({
    queryKey: ['holidays'],
    queryFn: async () => {
      const response = await getHolidays();
      return response.data;
    },
    enabled: isOpen,
  });

  const [mode, setMode] = useState('timeoff'); // 'timeoff' | 'work_holiday'
  const [formData, setFormData] = useState({
    resource_id: preselectedResourceId || undefined,
    start_date: '',
    end_date: '',
    type: '',
    notes: '',
    day_portion: 'full',
    holiday_date: '',
    replacement_date: '',
  });
  const [error, setError] = useState('');
  const [selectedFiles, setSelectedFiles] = useState([]); // Array of File objects
  const [uploadingAttachments, setUploadingAttachments] = useState(false);
  
  // Filter upcoming public holidays (date >= today, is_public_holiday)
  const upcomingPublicHolidays = holidays?.filter((h) => {
    if (!h.is_public_holiday) return false;
    const holidayDate = new Date(h.date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return holidayDate >= today;
  }) || [];

  // Auto-set default type when leave types load
  useEffect(() => {
    if (leaveTypes && leaveTypes.length > 0 && !formData.type) {
      setFormData((prev) => ({ ...prev, type: leaveTypes[0].name }));
    }
  }, [leaveTypes, formData.type]);
  
  // Reset form when dialog opens/closes — keep preselected resource
  useEffect(() => {
    if (!isOpen) {
      setMode('timeoff');
      setFormData({
        resource_id: preselectedResourceId || undefined,
        start_date: '',
        end_date: '',
        type: leaveTypes?.[0]?.name || '',
        notes: '',
        day_portion: 'full',
        holiday_date: '',
        replacement_date: '',
      });
      setError('');
    }
  }, [isOpen, preselectedResourceId, leaveTypes]);

  // Auto-select when preselectedResourceId changes while open
  useEffect(() => {
    if (preselectedResourceId) {
      setFormData((prev) => ({ ...prev, resource_id: preselectedResourceId }));
    }
  }, [preselectedResourceId]);

  const createMutation = useMutation({
    mutationFn: createLeave,
    onSuccess: async (response) => {
      const createdLeave = response.data;
      const leaveId = createdLeave._id || createdLeave.id;
      
      // Upload attachments if any
      if (selectedFiles.length > 0 && leaveId) {
        setUploadingAttachments(true);
        try {
          for (const file of selectedFiles) {
            // Read file as base64
            const base64 = await readFileAsBase64(file);
            await addLeaveAttachment(leaveId, {
              filename: file.name,
              content_type: file.type,
              data_base64: base64,
            });
          }
          toast.success('Time off and attachments added successfully');
        } catch (error) {
          toast.error('Time off added but attachment upload failed');
        } finally {
          setUploadingAttachments(false);
        }
      } else {
        toast.success('Time off added successfully');
      }
      
      queryClient.invalidateQueries({ queryKey: ['leaves'] });
      queryClient.invalidateQueries({ queryKey: ['capacity'] });
      queryClient.invalidateQueries({ queryKey: ['leaveCalendar'] });
      queryClient.invalidateQueries({ queryKey: ['whosOut'] });
      handleClose();
    },
    onError: (error) => {
      const message = error.response?.data?.detail || 'Failed to add time off';
      setError(message);
      toast.error(message);
    },
  });
  
  // Helper to read file as base64 (strip prefix)
  const readFileAsBase64 = (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const dataUrl = e.target.result;
        const base64 = dataUrl.split(',')[1]; // Strip "data:<mime>;base64," prefix
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };

  const handleClose = () => {
    setMode('timeoff');
    setFormData({
      resource_id: undefined,
      start_date: '',
      end_date: '',
      type: leaveTypes?.[0]?.name || '',
      notes: '',
      day_portion: 'full',
      holiday_date: '',
      replacement_date: '',
    });
    setError('');
    setSelectedFiles([]);
    setUploadingAttachments(false);
    onClose();
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');

    // Validation
    const effectiveResourceId = formData.resource_id || preselectedResourceId;
    if (!effectiveResourceId) {
      setError('Please select a resource');
      return;
    }

    if (mode === 'work_holiday') {
      // Work holiday mode validation — the replacement day is OPTIONAL. Staff may
      // either nominate a day off in lieu (a swap) OR simply work the holiday with no swap.
      if (!formData.holiday_date) {
        setError('Please select a public holiday');
        return;
      }

      const hasSwap = !!formData.replacement_date;
      // Submit work-holiday request. When a replacement day is given the leave spans
      // that day off; otherwise the backend records the worked holiday date itself.
      createMutation.mutate({
        resource_id: effectiveResourceId,
        worked_holiday: true,
        holiday_date: formData.holiday_date,
        replacement_date: formData.replacement_date || undefined,
        type: formData.type || (hasSwap ? 'Public holiday (worked)' : 'Public holiday (worked, no swap)'),
        notes: formData.notes || undefined,
        start_date: hasSwap ? formData.replacement_date : formData.holiday_date,
        end_date: hasSwap ? formData.replacement_date : formData.holiday_date,
      });
    } else {
      // Time off mode validation
      if (!formData.start_date || !formData.end_date) {
        setError('Please fill in all required fields');
        return;
      }

      if (new Date(formData.start_date) > new Date(formData.end_date)) {
        setError('End date must be after start date');
        return;
      }

      // Submit time-off request
      createMutation.mutate({
        resource_id: effectiveResourceId,
        start_date: formData.start_date,
        end_date: formData.end_date,
        type: formData.type,
        notes: formData.notes || undefined,
        day_portion: formData.day_portion,
      });
    }
  };

  // Auto-set end date to start date when half-day is selected
  const handleDayPortionChange = (value) => {
    setFormData((prev) => {
      const updated = { ...prev, day_portion: value };
      if ((value === 'am' || value === 'pm') && prev.start_date && !prev.end_date) {
        updated.end_date = prev.start_date;
      }
      return updated;
    });
  };
  
  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files || []);
    
    // Validate files
    const maxSize = 5 * 1024 * 1024; // 5MB
    const allowedTypes = ['application/pdf', 'image/png', 'image/jpeg'];
    const valid = [];
    
    for (const file of files) {
      if (selectedFiles.length + valid.length >= 3) {
        toast.error('Maximum 3 attachments allowed');
        break;
      }
      if (file.size > maxSize) {
        toast.error(`${file.name} is too large (max 5MB)`);
        continue;
      }
      if (!allowedTypes.includes(file.type)) {
        toast.error(`${file.name} has invalid type (only PDF, PNG, JPEG)`);
        continue;
      }
      valid.push(file);
    }
    
    setSelectedFiles([...selectedFiles, ...valid]);
  };
  
  const handleRemoveFile = (index) => {
    setSelectedFiles(selectedFiles.filter((_, i) => i !== index));
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose} modal={true}>
      <DialogContent data-testid="add-leave-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Calendar size={20} className="text-[#1570EF]" />
            {mode === 'work_holiday' ? 'Work a Public Holiday' : 'Request Time Off'}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Mode Toggle */}
          <div>
            <Label htmlFor="mode">Request Type</Label>
            <Select
              value={mode}
              onValueChange={setMode}
            >
              <SelectTrigger id="mode" data-testid="leave-mode-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="timeoff">Time Off</SelectItem>
                <SelectItem value="work_holiday">Work a Public Holiday</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {mode === 'work_holiday' ? (
            <>
              {/* Work Holiday Mode */}
              <div>
                <Label htmlFor="holiday">Public Holiday *</Label>
                <Select
                  value={formData.holiday_date}
                  onValueChange={(value) => setFormData({ ...formData, holiday_date: value })}
                >
                  <SelectTrigger id="holiday" data-testid="work-holiday-select">
                    <SelectValue placeholder="Select a public holiday" />
                  </SelectTrigger>
                  <SelectContent>
                    {upcomingPublicHolidays.length === 0 ? (
                      <SelectItem value="none" disabled>No upcoming public holidays</SelectItem>
                    ) : (
                      upcomingPublicHolidays.map((holiday) => (
                        <SelectItem key={holiday.id} value={holiday.date}>
                          {holiday.name} — {format(parseISO(holiday.date), 'MMM d, yyyy')}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="replacement-date">Replacement Date (Optional)</Label>
                <Input
                  id="replacement-date"
                  type="date"
                  value={formData.replacement_date}
                  onChange={(e) => setFormData({ ...formData, replacement_date: e.target.value })}
                  data-testid="replacement-date-input"
                />
                <p className="text-xs text-[#667085] mt-1">
                  Optional — the day you&apos;ll take off instead. Leave blank to simply work the holiday with no swap.
                </p>
              </div>

              {/* Leave Type (optional for work holiday) */}
              <div>
                <Label htmlFor="type-wh">Leave Type (Optional)</Label>
                <Select
                  value={formData.type || 'Public holiday (worked)'}
                  onValueChange={(value) => setFormData({ ...formData, type: value })}
                >
                  <SelectTrigger id="type-wh" data-testid="leave-type-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Public holiday (worked)">Public holiday (worked)</SelectItem>
                    {leaveTypes?.map((type) => (
                      <SelectItem key={type.id} value={type.name}>
                        {type.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </>
          ) : (
            <>
              {/* Time Off Mode */}
              {/* Resource Selection — hidden for resource users (auto-assigned) */}
              {!isPreselected && (
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
                      {resources?.filter((resource) => resource.active !== false).map((resource) => (
                        <SelectItem key={resource.id} value={resource.id}>
                          {resource.name} - {resource.role}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* Leave Type */}
              <div>
                <Label htmlFor="type">Leave Type *</Label>
                <Select
                  value={formData.type}
                  onValueChange={(value) => setFormData({ ...formData, type: value })}
                >
                  <SelectTrigger id="type" data-testid="leave-type-select">
                    <SelectValue placeholder="Select leave type" />
                  </SelectTrigger>
                  <SelectContent>
                    {leaveTypes?.map((type) => (
                      <SelectItem key={type.id} value={type.name}>
                        {type.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Half Day Control */}
              <div>
                <Label htmlFor="day-portion">Duration</Label>
                <Select
                  value={formData.day_portion}
                  onValueChange={handleDayPortionChange}
                >
                  <SelectTrigger id="day-portion" data-testid="leave-day-portion-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="full">Full Day</SelectItem>
                    <SelectItem value="am">Morning (Half Day)</SelectItem>
                    <SelectItem value="pm">Afternoon (Half Day)</SelectItem>
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
            </>
          )}

          {/* Notes (common to both modes) */}
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

          {/* Attachments (optional) — e.g. medical certificate for sick leave */}
          <div>
            <Label htmlFor="leave-attachments" className="flex items-center gap-1.5">
              <Paperclip className="h-3.5 w-3.5" />
              Attachments (optional — e.g. medical certificate)
            </Label>
            <input
              id="leave-attachments"
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg"
              onChange={handleFileSelect}
              data-testid="attachment-file-input"
              className="mt-1 block w-full text-sm text-[#667085] file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border file:border-[#E6E8EC] file:text-sm file:bg-[#F9FAFB] file:cursor-pointer hover:file:bg-[#F2F4F7]"
            />
            <p className="text-xs text-[#98A2B3] mt-1">Up to 3 files, 5MB each. PDF, PNG or JPEG.</p>
            {selectedFiles.length > 0 && (
              <div className="mt-2 space-y-1.5" data-testid="selected-attachments">
                {selectedFiles.map((file, idx) => (
                  <div
                    key={`${file.name}-${idx}`}
                    className="flex items-center justify-between text-xs bg-[#F9FAFB] border border-[#E6E8EC] rounded-md px-2 py-1.5"
                  >
                    <span className="flex items-center gap-1.5 truncate">
                      <Paperclip className="h-3 w-3 text-[#667085]" />
                      <span className="truncate">{file.name}</span>
                      <span className="text-[#98A2B3]">({(file.size / 1024).toFixed(0)} KB)</span>
                    </span>
                    <button
                      type="button"
                      onClick={() => handleRemoveFile(idx)}
                      data-testid={`remove-attachment-${idx}`}
                      className="text-[#667085] hover:text-red-600 ml-2 shrink-0"
                      aria-label="Remove attachment"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
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
              disabled={createMutation.isLoading || uploadingAttachments}
              data-testid="leave-submit"
            >
              {createMutation.isLoading || uploadingAttachments ? (
                <>
                  <Loader2 size={16} className="mr-2 animate-spin" />
                  {uploadingAttachments ? 'Uploading...' : 'Adding...'}
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
