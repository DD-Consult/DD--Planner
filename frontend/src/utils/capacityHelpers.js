/**
 * Capacity calculation helpers for resource allocation displays
 */

/**
 * Format allocation percentage with calculated hours (always 40h/week base, matching backend)
 * @param {number} percentage - Allocation percentage (0-100)
 * @returns {string} Formatted string like "50% (20.0h/wk)"
 */
export const formatAllocation = (percentage) => {
  if (percentage === null || percentage === undefined) {
    return 'N/A';
  }
  // Always 40h/week base to match backend allocation_weekly_hours() in utils.py
  const hours = (percentage / 100.0) * 40;
  return `${percentage}% (${hours.toFixed(1)}h/wk)`;
};

/**
 * Calculate weekly hours from percentage (always 40h/week base, matching backend)
 * @param {number} percentage - Allocation percentage (0-100)
 * @returns {number} Weekly hours
 */
export const calculateWeeklyHours = (percentage) => {
  if (percentage === null || percentage === undefined) {
    return 0;
  }
  return (percentage / 100.0) * 40;
};

/**
 * Calculate percentage from weekly hours
 * @param {number} hours - Weekly hours
 * @returns {number} Percentage (0-100)
 */
export const calculatePercentageFromHours = (hours) => {
  if (hours === null || hours === undefined) {
    return 0;
  }
  return (hours / 40.0) * 100;
};

/**
 * Format hours only (without percentage)
 * @param {number} hours - Hours to format
 * @returns {string} Formatted string like "20.0h"
 */
export const formatHours = (hours) => {
  if (hours === null || hours === undefined) {
    return '0h';
  }
  return `${hours.toFixed(1)}h`;
};
