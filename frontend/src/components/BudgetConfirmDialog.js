import React from 'react';
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
import { Progress } from './ui/progress';
import { AlertTriangle, TrendingUp } from 'lucide-react';

const BudgetConfirmDialog = ({ 
  open, 
  onOpenChange, 
  validation, 
  onConfirm, 
  onCancel 
}) => {
  if (!validation) return null;

  const { 
    status, 
    current_allocated_hours, 
    new_allocation_hours, 
    projected_allocated_hours, 
    budgeted_hours,
    remaining_after,
    current_usage_percentage,
    projected_usage_percentage,
    message 
  } = validation;

  // Determine styling based on status
  const isExceeded = status === 'exceeded';
  const isWarning = status === 'warning';
  
  const titleIcon = isExceeded ? '🚫' : '⚠️';
  const titleText = isExceeded ? 'Budget Exceeded' : 'Budget Warning';
  
  const progressColor = isExceeded 
    ? 'bg-red-500' 
    : isWarning 
    ? 'bg-amber-500' 
    : 'bg-blue-500';
  
  const buttonVariant = isExceeded ? 'destructive' : 'default';
  const buttonClass = isExceeded 
    ? 'bg-red-600 hover:bg-red-700' 
    : 'bg-amber-600 hover:bg-amber-700';

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            {titleIcon} {titleText}
          </AlertDialogTitle>
          <AlertDialogDescription className="text-left space-y-4 pt-2">
            <p className="text-sm text-slate-700">{message}</p>
            
            {/* Budget Breakdown */}
            <div className="bg-slate-50 rounded-lg p-4 space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-600">Budgeted Hours:</span>
                <span className="font-semibold text-slate-900">{budgeted_hours?.toFixed(0) || 0}h</span>
              </div>
              
              <div className="flex justify-between">
                <span className="text-slate-600">Currently Allocated:</span>
                <span className="font-semibold">
                  {current_allocated_hours?.toFixed(0) || 0}h 
                  <span className="text-slate-500 ml-1">
                    ({current_usage_percentage?.toFixed(1) || 0}%)
                  </span>
                </span>
              </div>
              
              <div className="flex justify-between items-center">
                <span className="text-slate-600 flex items-center gap-1">
                  <TrendingUp className="w-3 h-3" />
                  This Allocation:
                </span>
                <span className="font-semibold text-blue-600">
                  +{new_allocation_hours?.toFixed(0) || 0}h
                </span>
              </div>
              
              <div className="border-t border-slate-200 pt-3">
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-slate-700">Projected Total:</span>
                  <span className={`font-bold text-lg ${
                    projected_usage_percentage > 100 
                      ? 'text-red-600' 
                      : projected_usage_percentage >= 90 
                      ? 'text-amber-600' 
                      : 'text-slate-900'
                  }`}>
                    {projected_allocated_hours?.toFixed(0) || 0}h
                    <span className="text-sm ml-1">
                      ({projected_usage_percentage?.toFixed(1) || 0}%)
                    </span>
                  </span>
                </div>
              </div>
              
              <div className="flex justify-between">
                <span className="text-slate-600">Remaining After:</span>
                <span className={`font-semibold ${
                  remaining_after < 0 ? 'text-red-600' : 'text-green-600'
                }`}>
                  {remaining_after?.toFixed(0) || 0}h
                </span>
              </div>
            </div>

            {/* Visual Progress Bar */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs text-slate-600">
                <span>Budget Usage</span>
                <span>{projected_usage_percentage?.toFixed(1) || 0}%</span>
              </div>
              <div className="relative">
                <Progress 
                  value={Math.min(projected_usage_percentage || 0, 100)} 
                  className="h-3"
                />
                <div 
                  className={`absolute top-0 left-0 h-3 rounded-full transition-all ${progressColor}`}
                  style={{ width: `${Math.min(projected_usage_percentage || 0, 100)}%` }}
                />
              </div>
              {projected_usage_percentage > 100 && (
                <p className="text-xs text-red-600 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />
                  This allocation exceeds the project budget by {(projected_usage_percentage - 100).toFixed(1)}%
                </p>
              )}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onCancel}>
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className={buttonClass}
            data-testid="confirm-budget-warning"
          >
            Proceed Anyway
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};

export default BudgetConfirmDialog;
