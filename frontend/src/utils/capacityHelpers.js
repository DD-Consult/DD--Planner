/**
 * Capacity calculation helpers for resource allocation displays.
 * All calculations respect the resource's standard_capacity.
 */

/**
 * Format allocation percentage with calculated hours (respects standard_capacity)
 * @param {number} percentage - Allocation percentage (0-200)
 * @param {number} standardCapacity - Resource standard capacity (default 100)
 * @returns {string} Formatted string like "50% (10.0h/wk)"
 */
export const formatAllocation = (percentage, standardCapacity = 100) => {
  if (percentage === null || percentage === undefined) {
    return 'N/A';
  }
  const cap = standardCapacity && standardCapacity > 0 ? standardCapacity : 100;
  const hours = (percentage / 100.0) * (cap / 100.0) * 40;
  return `${percentage}%\n(${hours.toFixed(1)}h/wk)`;
};

/**
 * Calculate weekly hours from percentage (respects standard_capacity)
 * @param {number} percentage - Allocation percentage (0-200)
 * @param {number} standardCapacity - Resource standard capacity (default 100)
 * @returns {number} Weekly hours
 */
export const calculateWeeklyHours = (percentage, standardCapacity = 100) => {
  if (percentage === null || percentage === undefined) {
    return 0;
  }
  const cap = standardCapacity && standardCapacity > 0 ? standardCapacity : 100;
  return (percentage / 100.0) * (cap / 100.0) * 40;
};

/**
 * Calculate percentage from weekly hours
 * @param {number} hours - Weekly hours
 * @param {number} standardCapacity - Resource standard capacity (default 100)
 * @returns {number} Percentage (0-200)
 */
export const calculatePercentageFromHours = (hours, standardCapacity = 100) => {
  if (hours === null || hours === undefined) {
    return 0;
  }
  const cap = standardCapacity && standardCapacity > 0 ? standardCapacity : 100;
  const availablePerWeek = (cap / 100.0) * 40;
  return (hours / availablePerWeek) * 100;
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
