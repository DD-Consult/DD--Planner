/**
 * Capacity calculation helpers for resource allocation displays
 */

/**
 * Format allocation percentage with calculated hours
 * @param {number} percentage - Allocation percentage (0-100)
 * @param {number} resourceCapacity - Resource's standard capacity percentage (default 100 for full-time)
 * @returns {string} Formatted string like "50% (20h)" or "100% (40h)"
 */
export const formatAllocation = (percentage, resourceCapacity = 100) => {
  if (percentage === null || percentage === undefined) {
    return 'N/A';
  }
  
  // Calculate base hours from resource capacity
  // Full capacity (100%) = 40 hours/week
  // Part-time (50%) = 20 hours/week base
  const baseHours = (resourceCapacity / 100.0) * 40;
  const hours = (percentage / 100.0) * baseHours;
  
  return `${percentage}% (${hours.toFixed(1)}h)`;
};

/**
 * Calculate weekly hours from percentage and resource capacity
 * @param {number} percentage - Allocation percentage (0-100)
 * @param {number} resourceCapacity - Resource's standard capacity percentage (default 100)
 * @returns {number} Weekly hours
 */
export const calculateWeeklyHours = (percentage, resourceCapacity = 100) => {
  if (percentage === null || percentage === undefined) {
    return 0;
  }
  const baseHours = (resourceCapacity / 100.0) * 40;
  return (percentage / 100.0) * baseHours;
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
