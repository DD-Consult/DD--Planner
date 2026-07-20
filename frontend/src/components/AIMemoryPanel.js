import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getProjectMemories, createAIMemory, updateAIMemory, deleteAIMemory } from '../api';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Brain, Plus, Trash2, Edit2, Check, X, Globe, FolderOpen } from 'lucide-react';
import { toast } from 'sonner';

const CATEGORIES = ['decision', 'preference', 'context', 'note'];
const CATEGORY_COLORS = {
  decision: 'bg-blue-100 text-blue-700',
  preference: 'bg-purple-100 text-purple-700',
  context: 'bg-green-100 text-green-700',
  note: 'bg-gray-100 text-gray-600',
};

const MemoryForm = ({ projectId, initial, onSave, onCancel }) => {
  const [title, setTitle] = useState(initial?.title || '');
  const [content, setContent] = useState(initial?.content || '');
  const [category, setCategory] = useState(initial?.category || 'note');
  const [scope, setScope] = useState(initial?.scope || 'project');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!title.trim() || !content.trim()) return toast.error('Title and content are required');
    onSave({ title: title.trim(), content: content.trim(), category, scope, project_id: scope === 'project' ? projectId : undefined });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3 p-4 bg-[#F7F8FA] rounded-xl border border-[#E4E7EC]">
      <div className="flex gap-2">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="text-xs px-2 py-1 rounded-lg border border-[#D0D5DD] bg-white"
        >
          {CATEGORIES.map((c) => <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
        </select>
        <select
          value={scope}
          onChange={(e) => setScope(e.target.value)}
          className="text-xs px-2 py-1 rounded-lg border border-[#D0D5DD] bg-white"
        >
          <option value="project">This project</option>
          <option value="global">Global (all projects)</option>
        </select>
      </div>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Title (e.g. Phase budget decision)"
        className="w-full text-sm px-3 py-2 rounded-lg border border-[#D0D5DD] bg-white focus:outline-none focus:ring-2 focus:ring-[#1570EF]/30"
      />
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="What should the AI remember? (e.g. Team agreed to 60/40 budget split for all future phases)"
        rows={3}
        className="w-full text-sm px-3 py-2 rounded-lg border border-[#D0D5DD] bg-white resize-none focus:outline-none focus:ring-2 focus:ring-[#1570EF]/30"
      />
      <div className="flex gap-2">
        <Button type="submit" size="sm" className="h-8 text-xs bg-[#1570EF] hover:bg-[#0F5DC9]">
          <Check size={12} className="mr-1" /> Save Memory
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onCancel} className="h-8 text-xs">
          <X size={12} className="mr-1" /> Cancel
        </Button>
      </div>
    </form>
  );
};

const MemoryCard = ({ memory, onEdit, onDelete }) => {
  const isGlobal = memory.scope === 'global';
  return (
    <div
      data-testid={`memory-card-${memory.id}`}
      className="p-3 rounded-xl border border-[#E4E7EC] bg-white hover:border-[#1570EF]/30 transition-colors group"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${CATEGORY_COLORS[memory.category] || CATEGORY_COLORS.note}`}>
            {memory.category}
          </span>
          {isGlobal ? (
            <span className="text-xs flex items-center gap-1 text-[#667085]">
              <Globe size={10} /> Global
            </span>
          ) : (
            <span className="text-xs flex items-center gap-1 text-[#667085]">
              <FolderOpen size={10} /> This project
            </span>
          )}
        </div>
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button onClick={() => onEdit(memory)} className="p-1 rounded hover:bg-[#F2F3F5] text-[#667085]">
            <Edit2 size={12} />
          </button>
          <button onClick={() => onDelete(memory.id)} className="p-1 rounded hover:bg-red-50 text-red-400">
            <Trash2 size={12} />
          </button>
        </div>
      </div>
      <p className="text-sm font-medium text-[#101828] mt-1.5">{memory.title}</p>
      <p className="text-xs text-[#475467] mt-0.5 leading-relaxed">{memory.content}</p>
      <p className="text-xs text-[#98A2B3] mt-1.5">
        Saved by {memory.created_by} · {new Date(memory.created_at).toLocaleDateString()}
      </p>
    </div>
  );
};

export const AIMemoryPanel = ({ projectId }) => {
  const [showForm, setShowForm] = useState(false);
  const [editingMemory, setEditingMemory] = useState(null);
  const queryClient = useQueryClient();

  const { data: memories = [], isLoading } = useQuery({
    queryKey: ['aiMemories', projectId],
    queryFn: async () => {
      const res = await getProjectMemories(projectId);
      return res.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: (data) => createAIMemory(data),
    onSuccess: () => {
      queryClient.invalidateQueries(['aiMemories', projectId]);
      setShowForm(false);
      toast.success('Memory saved — AI will use this in future sessions');
    },
    onError: () => toast.error('Failed to save memory'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateAIMemory(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['aiMemories', projectId]);
      setEditingMemory(null);
      toast.success('Memory updated');
    },
    onError: () => toast.error('Failed to update memory'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => deleteAIMemory(id),
    onSuccess: () => {
      queryClient.invalidateQueries(['aiMemories', projectId]);
      toast.success('Memory removed');
    },
    onError: () => toast.error('Failed to remove memory'),
  });

  const handleSave = (data) => {
    if (editingMemory) {
      updateMutation.mutate({ id: editingMemory.id, data });
    } else {
      createMutation.mutate(data);
    }
  };

  const handleEdit = (memory) => {
    setEditingMemory(memory);
    setShowForm(false);
  };

  const projectMemories = memories.filter((m) => m.scope === 'project');
  const globalMemories = memories.filter((m) => m.scope === 'global');

  return (
    <div className="space-y-4" data-testid="ai-memory-panel">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-[#1570EF]/10 flex items-center justify-center">
            <Brain size={16} className="text-[#1570EF]" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[#101828]">Agent Memory</h3>
            <p className="text-xs text-[#667085]">Key decisions and context the AI remembers in every session</p>
          </div>
        </div>
        <Button
          size="sm"
          onClick={() => { setShowForm(true); setEditingMemory(null); }}
          className="h-8 text-xs bg-[#1570EF] hover:bg-[#0F5DC9]"
          data-testid="add-memory-btn"
        >
          <Plus size={12} className="mr-1" /> Add Memory
        </Button>
      </div>

      {(showForm && !editingMemory) && (
        <MemoryForm
          projectId={projectId}
          onSave={handleSave}
          onCancel={() => setShowForm(false)}
        />
      )}

      {isLoading ? (
        <p className="text-xs text-[#667085] py-2">Loading memories...</p>
      ) : memories.length === 0 && !showForm ? (
        <div className="text-center py-8 border border-dashed border-[#D0D5DD] rounded-xl">
          <Brain size={24} className="text-[#D0D5DD] mx-auto mb-2" />
          <p className="text-sm text-[#667085]">No memories yet</p>
          <p className="text-xs text-[#98A2B3] mt-1">Save key decisions so the AI remembers them automatically</p>
        </div>
      ) : (
        <div className="space-y-3">
          {projectMemories.length > 0 && (
            <div>
              <p className="text-xs font-medium text-[#344054] mb-2 flex items-center gap-1">
                <FolderOpen size={11} /> Project-specific ({projectMemories.length})
              </p>
              <div className="space-y-2">
                {projectMemories.map((m) => (
                  editingMemory?.id === m.id ? (
                    <MemoryForm
                      key={m.id}
                      projectId={projectId}
                      initial={m}
                      onSave={handleSave}
                      onCancel={() => setEditingMemory(null)}
                    />
                  ) : (
                    <MemoryCard
                      key={m.id}
                      memory={m}
                      onEdit={handleEdit}
                      onDelete={(id) => deleteMutation.mutate(id)}
                    />
                  )
                ))}
              </div>
            </div>
          )}
          {globalMemories.length > 0 && (
            <div>
              <p className="text-xs font-medium text-[#344054] mb-2 flex items-center gap-1">
                <Globe size={11} /> Global memories ({globalMemories.length})
              </p>
              <div className="space-y-2">
                {globalMemories.map((m) => (
                  editingMemory?.id === m.id ? (
                    <MemoryForm
                      key={m.id}
                      projectId={projectId}
                      initial={m}
                      onSave={handleSave}
                      onCancel={() => setEditingMemory(null)}
                    />
                  ) : (
                    <MemoryCard
                      key={m.id}
                      memory={m}
                      onEdit={handleEdit}
                      onDelete={(id) => deleteMutation.mutate(id)}
                    />
                  )
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default AIMemoryPanel;
