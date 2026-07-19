import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getProjectAIInstructions, 
  createAIInstruction, 
  updateAIInstruction, 
  deleteAIInstruction 
} from '../api';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Switch } from './ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from './ui/alert-dialog';
import { Sparkles, Plus, Edit2, Trash2, Loader2, Save, X } from 'lucide-react';
import { toast } from 'sonner';

/**
 * AIInstructionsPanel - Manage AI instructions for guiding AI features
 * 
 * Props:
 * - scope: 'global' | 'project'
 * - projectId: string (required if scope='project')
 * - projectName: string (optional, for display)
 */

// Category display labels
const CATEGORY_LABELS = {
  all: 'All AI Features',
  risk_polish: 'Risk Polishing',
  status_summary: 'Status Summaries',
  wbs_generation: 'WBS Generation',
  reschedule: 'AI Reschedule',
  chat: 'AI Chat',
};

// Category badge colors
const CATEGORY_COLORS = {
  all: 'bg-purple-50 text-purple-700 border-purple-200',
  risk_polish: 'bg-amber-50 text-amber-700 border-amber-200',
  status_summary: 'bg-blue-50 text-blue-700 border-blue-200',
  wbs_generation: 'bg-green-50 text-green-700 border-green-200',
  reschedule: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  chat: 'bg-pink-50 text-pink-700 border-pink-200',
};

const AIInstructionsPanel = ({ scope, projectId, projectName }) => {
  const queryClient = useQueryClient();
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);
  
  // Form state
  const [formData, setFormData] = useState({
    category: 'all',
    instructions: '',
  });

  // Fetch instructions
  const { data: instructions = [], isLoading } = useQuery({
    queryKey: ['aiInstructions', scope, projectId],
    queryFn: async () => {
      if (scope === 'project' && projectId) {
        const response = await getProjectAIInstructions(projectId);
        return response.data;
      }
      return [];
    },
    enabled: scope === 'project' && !!projectId,
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data) => createAIInstruction(data),
    onSuccess: () => {
      toast.success('Instruction added');
      queryClient.invalidateQueries(['aiInstructions', scope, projectId]);
      resetForm();
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to add instruction'),
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateAIInstruction(id, data),
    onSuccess: () => {
      toast.success('Instruction updated');
      queryClient.invalidateQueries(['aiInstructions', scope, projectId]);
      setEditingId(null);
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to update instruction'),
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id) => deleteAIInstruction(id),
    onSuccess: () => {
      toast.success('Instruction deleted');
      queryClient.invalidateQueries(['aiInstructions', scope, projectId]);
      setDeleteConfirmId(null);
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to delete instruction'),
  });

  const resetForm = () => {
    setShowAddForm(false);
    setFormData({ category: 'all', instructions: '' });
  };

  const handleAdd = () => {
    if (!formData.instructions.trim()) {
      toast.error('Please enter instructions');
      return;
    }

    createMutation.mutate({
      scope,
      project_id: scope === 'project' ? projectId : undefined,
      category: formData.category,
      instructions: formData.instructions.trim(),
    });
  };

  const handleUpdate = (instruction, updates) => {
    updateMutation.mutate({
      id: instruction.id,
      data: updates,
    });
  };

  const handleToggleActive = (instruction) => {
    handleUpdate(instruction, { is_active: !instruction.is_active });
  };

  const startEdit = (instruction) => {
    setEditingId(instruction.id);
    setFormData({
      category: instruction.category,
      instructions: instruction.instructions,
    });
  };

  const saveEdit = (instruction) => {
    if (!formData.instructions.trim()) {
      toast.error('Instructions cannot be empty');
      return;
    }
    handleUpdate(instruction, {
      category: formData.category,
      instructions: formData.instructions.trim(),
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setFormData({ category: 'all', instructions: '' });
  };

  if (isLoading) {
    return (
      <div className="bg-white border border-[#E6E8EC] rounded-lg p-6">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="animate-spin text-gray-400" size={24} />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-[#E6E8EC] rounded-lg p-6" data-testid="ai-instructions-panel">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold flex items-center gap-2" style={{ fontFamily: 'Space Grotesk' }}>
            <Sparkles size={20} className="text-purple-600" />
            AI Instructions {projectName && `for ${projectName}`}
          </h3>
          <p className="text-sm text-[#667085] mt-1">
            Guide how AI features behave for this project
          </p>
        </div>
        {!showAddForm && !editingId && (
          <Button
            size="sm"
            onClick={() => setShowAddForm(true)}
            className="gap-2 bg-purple-600 hover:bg-purple-700"
            data-testid="add-instruction-btn"
          >
            <Plus size={14} />
            Add Instruction
          </Button>
        )}
      </div>

      {/* Existing Instructions */}
      <div className="space-y-3 mb-4">
        {instructions.map((instruction) => (
          <div
            key={instruction.id}
            className={`border rounded-lg p-4 transition-colors ${
              instruction.is_active ? 'border-[#E6E8EC] bg-white' : 'border-gray-200 bg-gray-50 opacity-60'
            }`}
            data-testid={`instruction-card-${instruction.id}`}
          >
            {editingId === instruction.id ? (
              // Edit Mode
              <div className="space-y-3">
                <div>
                  <Label className="text-xs font-medium text-gray-700 mb-1 block">Category</Label>
                  <Select
                    value={formData.category}
                    onValueChange={(value) => setFormData({ ...formData, category: value })}
                    data-testid="edit-category-select"
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                        <SelectItem key={key} value={key}>
                          {label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs font-medium text-gray-700 mb-1 block">Instructions</Label>
                  <Textarea
                    value={formData.instructions}
                    onChange={(e) => setFormData({ ...formData, instructions: e.target.value })}
                    placeholder="Enter AI instructions..."
                    rows={4}
                    data-testid="edit-instructions-textarea"
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={() => saveEdit(instruction)}
                    disabled={updateMutation.isPending}
                    className="gap-1"
                    data-testid="save-edit-btn"
                  >
                    {updateMutation.isPending ? (
                      <><Loader2 size={14} className="animate-spin" /> Saving...</>
                    ) : (
                      <><Save size={14} /> Save</>
                    )}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={cancelEdit}
                    disabled={updateMutation.isPending}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              // View Mode
              <>
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge
                      variant="outline"
                      className={`text-xs font-medium ${CATEGORY_COLORS[instruction.category] || CATEGORY_COLORS.all}`}
                    >
                      {CATEGORY_LABELS[instruction.category] || instruction.category}
                    </Badge>
                    <div className="flex items-center gap-1.5">
                      <Switch
                        checked={instruction.is_active}
                        onCheckedChange={() => handleToggleActive(instruction)}
                        data-testid={`toggle-active-${instruction.id}`}
                      />
                      <span className="text-xs text-gray-600">
                        {instruction.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => startEdit(instruction)}
                      data-testid={`edit-instruction-${instruction.id}`}
                      title="Edit"
                    >
                      <Edit2 size={14} />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0 text-red-600 hover:bg-red-50 hover:text-red-700"
                      onClick={() => setDeleteConfirmId(instruction.id)}
                      data-testid={`delete-instruction-${instruction.id}`}
                      title="Delete"
                    >
                      <Trash2 size={14} />
                    </Button>
                  </div>
                </div>
                <p className="text-sm text-[#344054] whitespace-pre-wrap" data-testid="instruction-text">
                  {instruction.instructions}
                </p>
              </>
            )}
          </div>
        ))}

        {instructions.length === 0 && !showAddForm && (
          <div className="text-center py-8 text-gray-500">
            <Sparkles size={32} className="mx-auto mb-3 opacity-40" />
            <p className="text-sm">No AI instructions yet.</p>
            <p className="text-xs">Add instructions to guide AI behavior for this project.</p>
          </div>
        )}
      </div>

      {/* Add Form */}
      {showAddForm && (
        <div className="border border-purple-200 rounded-lg p-4 bg-purple-50" data-testid="add-instruction-form">
          <h4 className="text-sm font-semibold text-gray-900 mb-3">Add New Instruction</h4>
          <div className="space-y-3">
            <div>
              <Label className="text-xs font-medium text-gray-700 mb-1 block">Category</Label>
              <Select
                value={formData.category}
                onValueChange={(value) => setFormData({ ...formData, category: value })}
                data-testid="add-category-select"
              >
                <SelectTrigger className="w-full bg-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                    <SelectItem key={key} value={key}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs font-medium text-gray-700 mb-1 block">Instructions</Label>
              <Textarea
                value={formData.instructions}
                onChange={(e) => setFormData({ ...formData, instructions: e.target.value })}
                placeholder="e.g., We use Agile methodology with 2-week sprints. Always refer to phases as 'iterations'."
                rows={4}
                className="bg-white"
                data-testid="add-instructions-textarea"
              />
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={handleAdd}
                disabled={createMutation.isPending}
                className="gap-1 bg-purple-600 hover:bg-purple-700"
                data-testid="save-new-instruction-btn"
              >
                {createMutation.isPending ? (
                  <><Loader2 size={14} className="animate-spin" /> Saving...</>
                ) : (
                  <><Save size={14} /> Save</>
                )}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={resetForm}
                disabled={createMutation.isPending}
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!deleteConfirmId} onOpenChange={(open) => !open && setDeleteConfirmId(null)}>
        <AlertDialogContent data-testid="delete-instruction-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this instruction?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently remove this AI instruction. AI features will no longer use this guidance.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setDeleteConfirmId(null)}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMutation.mutate(deleteConfirmId)}
              className="bg-[#EF4444] hover:bg-[#EF4444]/90"
              data-testid="confirm-delete-instruction"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default AIInstructionsPanel;
