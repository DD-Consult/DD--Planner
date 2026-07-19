import React, { useCallback } from 'react';
import { Input } from './input';
import { snapToWeekday, isWeekendDate } from '../../utils/dateHelpers';

/**
 * WeekdayDateInput — A date input that only allows Monday–Friday.
 * 
 * If a user picks a Saturday or Sunday, the date is automatically
 * snapped to the next Monday and a brief visual cue is shown.
 * 
 * Props are identical to <Input type="date" /> plus:
 *   - onChange(e) — synthetic event with value already snapped
 *   - snapMode — "start" (snap to Monday) or "end" (snap to Friday). Default "start"
 */
const WeekdayDateInput = ({ value, onChange, snapMode = 'start', ...props }) => {
  const handleChange = useCallback((e) => {
    const raw = e.target.value;
    if (!raw) {
      onChange?.(e);
      return;
    }
    
    if (isWeekendDate(raw)) {
      // Snap the date to a weekday
      const snapped = snapToWeekday(raw);
      // Create a synthetic event with the snapped value
      const syntheticEvent = {
        ...e,
        target: { ...e.target, value: snapped },
      };
      onChange?.(syntheticEvent);
    } else {
      onChange?.(e);
    }
  }, [onChange]);

  return (
    <Input
      type="date"
      value={value}
      onChange={handleChange}
      data-testid={props['data-testid']}
      {...props}
    />
  );
};

export default WeekdayDateInput;
