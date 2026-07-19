import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getTaskComments, createTaskComment, updateTaskComment, deleteTaskComment } from '../api';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Loader2, Edit2, Trash2, MessageSquare } from 'lucide-react';
import { toast } from 'sonner';

const getInitials = (name) => {
  if (!name) return '?';
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
};

const getRelativeTime = (dateStr) => {
  if (!dateStr) return '';
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    if (diffDays === 1) return 'yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    return date.toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return dateStr;
  }
};

const WBSCommentSection = ({ taskId, projectId, currentUserEmail }) => {
  const queryClient = useQueryClient();
  const [newComment, setNewComment] = useState('');
  const [editingCommentId, setEditingCommentId] = useState(null);
  const [editedContent, setEditedContent] = useState('');

  // Fetch comments
  const { data: comments = [], isLoading } = useQuery({
    queryKey: ['taskComments', taskId],
    queryFn: async () => {
      const response = await getTaskComments(taskId);
      return response.data;
    },
    enabled: !!taskId,
  });

  // Create comment mutation
  const createMutation = useMutation({
    mutationFn: (data) => createTaskComment(taskId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['taskComments', taskId] });
      queryClient.invalidateQueries({ queryKey: ['projectCommentCounts', projectId] });
      setNewComment('');
      toast.success('Comment added');
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to add comment'),
  });

  // Update comment mutation
  const updateMutation = useMutation({
    mutationFn: ({ commentId, data }) => updateTaskComment(commentId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['taskComments', taskId] });
      setEditingCommentId(null);
      setEditedContent('');
      toast.success('Comment updated');
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to update comment'),
  });

  // Delete comment mutation
  const deleteMutation = useMutation({
    mutationFn: (commentId) => deleteTaskComment(commentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['taskComments', taskId] });
      queryClient.invalidateQueries({ queryKey: ['projectCommentCounts', projectId] });
      toast.success('Comment deleted');
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to delete comment'),
  });

  const handleSubmitComment = () => {
    if (!newComment.trim()) return;
    createMutation.mutate({
      content: newComment.trim(),
      mentions: [], // Future enhancement: parse @mentions
    });
  };

  const handleStartEdit = (comment) => {
    setEditingCommentId(comment.id);
    setEditedContent(comment.content);
  };

  const handleCancelEdit = () => {
    setEditingCommentId(null);
    setEditedContent('');
  };

  const handleSaveEdit = (commentId) => {
    if (!editedContent.trim()) return;
    updateMutation.mutate({
      commentId,
      data: { content: editedContent.trim() },
    });
  };

  const handleDelete = (commentId) => {
    if (window.confirm('Delete this comment?')) {
      deleteMutation.mutate(commentId);
    }
  };

  if (!taskId) return null;

  return (
    <div className="border-t border-gray-200 pt-4 mt-6">
      <div className="flex items-center gap-2 mb-4">
        <MessageSquare size={16} className="text-gray-500" />
        <h4 className="text-sm font-semibold text-gray-700">
          Comments {comments.length > 0 && <span className="text-gray-400">({comments.length})</span>}
        </h4>
      </div>

      {/* Comment List */}
      <div className="space-y-3 mb-4">
        {isLoading ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 size={16} className="animate-spin text-gray-400" />
          </div>
        ) : comments.length === 0 ? (
          <div className="text-center py-6 text-sm text-gray-400 bg-gray-50 rounded-md border border-gray-100">
            No comments yet. Start the conversation!
          </div>
        ) : (
          comments.map((comment) => {
            const isOwnComment = comment.author_email === currentUserEmail;
            const isEditing = editingCommentId === comment.id;

            return (
              <div
                key={comment.id}
                className="bg-gray-50 rounded-lg border border-gray-200 p-3 hover:border-gray-300 transition-colors"
                data-testid={`comment-${comment.id}`}
              >
                {/* Header */}
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-full bg-[#1570EF] text-white text-xs flex items-center justify-center font-medium">
                      {getInitials(comment.author_name)}
                    </div>
                    <div>
                      <div className="text-sm font-medium text-gray-900">{comment.author_name}</div>
                      <div className="text-xs text-gray-500 flex items-center gap-1.5">
                        {getRelativeTime(comment.created_at)}
                        {comment.is_edited && <span className="text-gray-400">(edited)</span>}
                      </div>
                    </div>
                  </div>
                  {isOwnComment && !isEditing && (
                    <div className="flex gap-1">
                      <button
                        onClick={() => handleStartEdit(comment)}
                        className="p-1.5 rounded hover:bg-gray-200 text-gray-500 hover:text-gray-700"
                        title="Edit comment"
                        data-testid={`edit-comment-${comment.id}`}
                      >
                        <Edit2 size={12} />
                      </button>
                      <button
                        onClick={() => handleDelete(comment.id)}
                        className="p-1.5 rounded hover:bg-red-100 text-gray-500 hover:text-red-600"
                        title="Delete comment"
                        data-testid={`delete-comment-${comment.id}`}
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  )}
                </div>

                {/* Content */}
                {isEditing ? (
                  <div className="space-y-2">
                    <Textarea
                      value={editedContent}
                      onChange={(e) => setEditedContent(e.target.value)}
                      className="text-sm min-h-20"
                      autoFocus
                      data-testid={`edit-textarea-${comment.id}`}
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => handleSaveEdit(comment.id)}
                        disabled={!editedContent.trim() || updateMutation.isPending}
                        className="h-7 text-xs bg-[#1570EF] hover:bg-[#1570EF]/90"
                        data-testid={`save-edit-${comment.id}`}
                      >
                        {updateMutation.isPending ? <Loader2 size={12} className="mr-1 animate-spin" /> : null}
                        Save
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handleCancelEdit}
                        className="h-7 text-xs"
                        data-testid={`cancel-edit-${comment.id}`}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="text-sm text-gray-700 whitespace-pre-wrap">{comment.content}</div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* New Comment Input */}
      <div className="border border-gray-200 rounded-lg p-3 bg-white" data-testid="new-comment-area">
        <Textarea
          value={newComment}
          onChange={(e) => setNewComment(e.target.value)}
          placeholder="Add a comment..."
          className="text-sm min-h-20 mb-2 border-gray-200"
          data-testid="new-comment-input"
        />
        <div className="flex justify-end">
          <Button
            size="sm"
            onClick={handleSubmitComment}
            disabled={!newComment.trim() || createMutation.isPending}
            className="bg-[#1570EF] hover:bg-[#1570EF]/90 text-white"
            data-testid="post-comment-button"
          >
            {createMutation.isPending ? <Loader2 size={14} className="mr-1.5 animate-spin" /> : null}
            Post Comment
          </Button>
        </div>
      </div>
    </div>
  );
};

export default WBSCommentSection;
