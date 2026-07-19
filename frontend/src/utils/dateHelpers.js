/**
 * Date Helper Utilities — Business Days Only
 * 
 * Ensures all project-related dates fall on Monday–Friday.
 * Provides helpers for snapping dates to weekdays and 
 * counting business days.
 */
import { differenceInBusinessDays, addBusinessDays, isWeekend, nextMonday, previousFriday, format, parseISO } from 'date-fns';

/**
 * Snap a date to the nearest weekday (Mon-Fri).
 * - Saturday → next Monday
 * - Sunday → next Monday
 * @param {string|Date} dateVal - ISO date string or Date object
 * @returns {string} ISO date string (yyyy-MM-dd) snapped to weekday, or original if invalid
 */
export function snapToWeekday(dateVal) {
  if (!dateVal) return dateVal;
  try {
    const d = typeof dateVal === 'string' ? parseISO(dateVal) : new Date(dateVal);
    if (isNaN(d.getTime())) return dateVal;
    if (!isWeekend(d)) return format(d, 'yyyy-MM-dd');
    // Snap to next Monday
    const snapped = nextMonday(d);
    return format(snapped, 'yyyy-MM-dd');
  } catch {
    return dateVal;
  }
}

/**
 * Snap a date to the previous weekday (for end dates).
 * - Saturday → previous Friday
 * - Sunday → previous Friday
 * @param {string|Date} dateVal
 * @returns {string} ISO date string snapped to weekday
 */
export function snapToWeekdayEnd(dateVal) {
  if (!dateVal) return dateVal;
  try {
    const d = typeof dateVal === 'string' ? parseISO(dateVal) : new Date(dateVal);
    if (isNaN(d.getTime())) return dateVal;
    if (!isWeekend(d)) return format(d, 'yyyy-MM-dd');
    // Snap to previous Friday
    const snapped = previousFriday(d);
    return format(snapped, 'yyyy-MM-dd');
  } catch {
    return dateVal;
  }
}

/**
 * Check if a date string falls on a weekend.
 * @param {string} dateStr - ISO date string
 * @returns {boolean}
 */
export function isWeekendDate(dateStr) {
  if (!dateStr) return false;
  try {
    const d = parseISO(dateStr);
    return isWeekend(d);
  } catch {
    return false;
  }
}

/**
 * Calculate business days between two dates (Mon-Fri only).
 * @param {string|Date} startDate
 * @param {string|Date} endDate
 * @returns {number} Number of business days (inclusive of start, exclusive of end by default)
 */
export function businessDaysBetween(startDate, endDate) {
  if (!startDate || !endDate) return 0;
  try {
    const s = typeof startDate === 'string' ? parseISO(startDate) : new Date(startDate);
    const e = typeof endDate === 'string' ? parseISO(endDate) : new Date(endDate);
    if (isNaN(s.getTime()) || isNaN(e.getTime())) return 0;
    // differenceInBusinessDays counts Mon-Fri only, add 1 to be inclusive
    return Math.abs(differenceInBusinessDays(e, s)) + 1;
  } catch {
    return 0;
  }
}

/**
 * Add business days to a date.
 * @param {string|Date} dateVal
 * @param {number} days - Number of business days to add
 * @returns {string} ISO date string
 */
export function addBizDays(dateVal, days) {
  if (!dateVal) return dateVal;
  try {
    const d = typeof dateVal === 'string' ? parseISO(dateVal) : new Date(dateVal);
    if (isNaN(d.getTime())) return dateVal;
    const result = addBusinessDays(d, days);
    return format(result, 'yyyy-MM-dd');
  } catch {
    return dateVal;
  }
}

export { isWeekend, differenceInBusinessDays, addBusinessDays };
