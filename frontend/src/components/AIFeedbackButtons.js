import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { submitAIFeedback } from '../api';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { ThumbsUp, ThumbsDown, Check } from 'lucide-react';
import { toast } from 'sonner';

/**
 * AIFeedbackButtons - Inline thumbs up/down feedback for AI outputs
 * 
 * Props:
 * - feature: string (e.g., "status_summary", "risk_polish", "reschedule")
 * - projectId: string
 * - inputSummary: string (optional, brief description of input context)
 * - outputSummary: string (optional, brief description of output)
 */
const AIFeedbackButtons = ({ feature, projectId, inputSummary = '', outputSummary = '' }) => {
  const [showFeedbackInput, setShowFeedbackInput] = useState(false);
  const [feedbackText, setFeedbackText] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [rating, setRating] = useState(null); // 'positive' or 'negative'

  const feedbackMutation = useMutation({
    mutationFn: (data) => submitAIFeedback(data),
    onSuccess: () => {
      setSubmitted(true);
      toast.success('Thanks for your feedback!');
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || 'Failed to submit feedback');
    },
  });

  const handleThumbClick = (thumbRating) => {
    setRating(thumbRating);
    setShowFeedbackInput(true);
  };

  const handleSubmit = () => {
    if (!rating) return;
    
    feedbackMutation.mutate({
      feature,
      project_id: projectId,
      rating,
      input_summary: inputSummary || undefined,
      output_summary: outputSummary || undefined,
      feedback_text: feedbackText.trim() || undefined,
    });
  };

  const handleSkip = () => {
    // Submit without feedback text
    if (!rating) return;
    
    feedbackMutation.mutate({
      feature,
      project_id: projectId,
      rating,
      input_summary: inputSummary || undefined,
      output_summary: outputSummary || undefined,
    });
  };

  if (submitted) {
    return (
      <div className="inline-flex items-center gap-1.5 text-xs text-green-600" data-testid="feedback-submitted">
        <Check size={14} />
        <span>Feedback submitted</span>
      </div>
    );
  }

  return (
    <div className="inline-flex items-center gap-2" data-testid="ai-feedback-buttons">
      {!showFeedbackInput ? (
        <>
          <span className="text-xs text-gray-500">Was this helpful?</span>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 hover:bg-green-50 hover:text-green-600"
            onClick={() => handleThumbClick('positive')}
            data-testid="feedback-thumbs-up"
            title="Helpful"
          >
            <ThumbsUp size={14} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 hover:bg-red-50 hover:text-red-600"
            onClick={() => handleThumbClick('negative')}
            data-testid="feedback-thumbs-down"
            title="Not helpful"
          >
            <ThumbsDown size={14} />
          </Button>
        </>
      ) : (
        <div className="flex flex-col gap-2 w-full max-w-md" data-testid="feedback-input-form">
          <div className="flex items-center gap-2">
            {rating === 'positive' ? (
              <ThumbsUp size={14} className="text-green-600" />
            ) : (
              <ThumbsDown size={14} className="text-red-600" />
            )}
            <span className="text-xs text-gray-600">Tell us more (optional):</span>
          </div>
          <Textarea
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
            placeholder="What did you like or dislike?"
            rows={2}
            className="text-sm"
            data-testid="feedback-text-input"
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={handleSubmit}
              disabled={feedbackMutation.isPending}
              className="bg-[#1570EF] hover:bg-[#1570EF]/90"
              data-testid="submit-feedback-btn"
            >
              {feedbackMutation.isPending ? 'Submitting...' : 'Submit'}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={handleSkip}
              disabled={feedbackMutation.isPending}
              data-testid="skip-feedback-btn"
            >
              Skip
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setShowFeedbackInput(false);
                setRating(null);
                setFeedbackText('');
              }}
              disabled={feedbackMutation.isPending}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default AIFeedbackButtons;
