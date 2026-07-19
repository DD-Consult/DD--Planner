# DD Planner - User Guide for New Features

## 🎯 Quick Reference Guide

This guide explains how to use the new features implemented in DD Planner.

---

## 1. Admin Editing Status Updates

### Who Can Use This?
- ✅ Administrators
- ✅ Super Administrators
- ❌ Regular users, resources, clients

### How to Use
1. Navigate to any project detail page
2. Scroll to "Recent Status Updates" section
3. Look for the **Edit** button (pencil icon) next to each status update
4. Click **Edit** to open the edit dialog
5. Modify any fields you need to change
6. Click **Save Changes**

### What You Can Edit
- Health Status (Green/Amber/Red)
- Schedule Status (On Track/Delayed/At Risk/Ahead)
- Progress percentage (or leave empty for auto-calculation)
- Accomplishments
- Blockers/Issues
- Next Steps
- Additional Notes

### Notes
- Original submitter information is preserved
- Your edit is tracked with your name and timestamp
- Changes are immediately visible across the app

---

## 2. Automatic Progress Calculation

### How It Works
Progress is now automatically calculated based on time elapsed:
```
Progress % = (Days Passed / Total Project Days) × 100
```

### Example
- Project starts: January 1
- Project ends: January 31 (31 days total)
- Today: January 16 (15 days passed)
- **Progress: 48%** (automatically calculated)

### When to Override
You can still provide an explicit progress value when creating/editing status updates. Use this when:
- Project is ahead/behind schedule
- Actual work completion differs from time elapsed
- Major milestones reached early or late

### Where to See It
- Project detail page progress bar
- Dashboard project cards
- Status update history

---

## 3. WBS Delay Tracking

### Visual Indicators

#### Delayed Task Badge
- **Red badge** appears on overdue tasks
- Shows format: "🔴 DELAYED Xd" (where X = days overdue)
- Only shown for tasks that are:
  - Past their end date
  - Not marked as "Done"

#### Header Metrics
- **Summary badge** shows total delays
- Format: "X delayed (Yd)"
  - X = number of delayed tasks
  - Y = total days delayed across all tasks

### Where to Find Delays
1. **Plan View** (recommended for delay tracking)
   - Each overdue task shows delay badge
   - Sort by dates to see critical delays first
   
2. **Header Summary**
   - Quick overview of total delays
   - Click badge to filter (future enhancement)

### What Counts as Delayed?
- Task end_date is in the past
- Task status is NOT "Done"
- System checks this in real-time

---

## 4. Bulk WBS Operations

### How to Use Bulk Actions

#### Step 1: Select Tasks
- Go to WBS Plan view
- Check the checkbox next to each task you want to update
- OR click the header checkbox to "Select All"

#### Step 2: Choose Action
Once tasks are selected, the bulk toolbar appears with options:

**Change Status**
- Dropdown shows: To Do, In Progress, Done, On Hold, Blocked
- Select a status to update all selected tasks

**Assign To**
- Dropdown shows all project resources
- Select a person to reassign all selected tasks

**Delete**
- Red button
- Requires confirmation
- Permanently deletes all selected tasks

**Clear**
- Removes current selection without making changes

#### Step 3: Confirm
- Action happens immediately (except Delete, which asks for confirmation)
- Toast notification shows success
- Selection automatically clears

### Best Practices
- Select related tasks for consistent updates
- Use for weekly status updates (mark multiple tasks as "Done")
- Bulk reassign when team members change
- Review selection before bulk delete (cannot undo)

### Limitations
- Maximum ~100 tasks per bulk operation recommended
- Operations run in parallel for speed
- All selected tasks must be visible (no hidden tasks)

---

## 5. WBS → Project Date Sync

### Purpose
Keeps your project end date aligned with your actual WBS plan.

### When to Use
- After extending task deadlines
- When project scope increases
- After adding new WBS tasks with later dates
- When WBS completion date differs from project end date

### How to Use
1. Go to any project's WBS tab
2. Look for **"Sync Dates from WBS"** button (refresh icon)
3. Click the button
4. System finds the latest WBS task end date
5. Updates project end date to match
6. Updates last phase end date to match
7. Shows toast with summary of changes

### Example
```
Before:
- Project End: Nov 30, 2025
- Latest WBS Task: Dec 31, 2025 (Final Deployment)

After Sync:
- Project End: Dec 31, 2025 ✓
- Last Phase End: Dec 31, 2025 ✓
```

### Notes
- **Manual operation** (not automatic)
- Only admins can sync dates
- Shows preview of changes
- Updates both project AND last phase
- Doesn't affect WBS tasks or allocations

---

## 6. AI WBS Generation (Enhanced)

### What's New
AI now only suggests team members **actually assigned to your project**.

### Before vs After
**Before**: AI suggested any resource in the system (200+ names)  
**After**: AI only suggests your project's 5-10 allocated team members

### How It Works
1. Click "Generate with AI" in WBS tab
2. System checks project allocations
3. AI receives only allocated resource names
4. Generated tasks only assign to your team
5. More accurate, less cleanup needed

### Fallback Behavior
If no resources are allocated yet (new project), AI will see all resources as before.

---

## 💡 Pro Tips

### For Admins
1. **Edit Status Updates Responsibly**
   - Your edits are tracked and visible
   - Add notes explaining major changes
   - Don't overwrite important historical data

2. **Use Bulk Operations Efficiently**
   - Select tasks by phase for organized updates
   - Bulk reassign during team transitions
   - Review before bulk delete

3. **Sync Dates Regularly**
   - Run sync after major WBS updates
   - Keeps reporting accurate
   - Prevents date discrepancies

### For Project Leads
1. **Monitor Delays**
   - Check WBS delay badge weekly
   - Address overdue tasks promptly
   - Update end dates or mark as done

2. **Accurate Progress Updates**
   - Let auto-calculation work for most projects
   - Override only when needed
   - Document significant variances

### For Team Members
1. **Update Task Status**
   - Mark tasks done as you complete them
   - Move to "In Progress" when starting
   - Use "Blocked" to flag issues

2. **Log Time Accurately**
   - Link timesheets to WBS tasks
   - Helps delay detection and reporting
   - Improves future estimates

---

## 🆘 Troubleshooting

### "Can't see Edit button on status updates"
- Only admins see this button
- Check your role (Settings → Users)
- Contact admin if you need access

### "Progress shows as 0%"
- Check if project has start/end dates
- If dates missing, add them in project settings
- Auto-calculation requires valid date range

### "Bulk actions not working"
- Ensure tasks are selected (checkboxes checked)
- Try with smaller selection (< 50 tasks)
- Check browser console for errors
- Refresh page and try again

### "Delayed badge not appearing"
- Task must have an end_date set
- Task status must NOT be "Done"
- Today's date must be past end_date
- Refresh page to see updated calculations

### "Sync dates button missing"
- Only admins see this button
- Must be in WBS tab
- Must have at least one WBS task with end_date

---

## 📊 Keyboard Shortcuts (Future)

Coming soon:
- `Ctrl/Cmd + A` - Select all tasks
- `Ctrl/Cmd + D` - Bulk mark as Done
- `Esc` - Clear selection
- `Ctrl/Cmd + E` - Edit selected

---

## 📞 Support

### Need Help?
1. Check this guide first
2. Review /app/PHASE_1_2_3_COMPLETE.md for technical details
3. Contact your system administrator
4. Submit feedback via project settings

### Found a Bug?
Report with:
- What you were trying to do
- What happened instead
- Screenshots if possible
- Your user role

---

**Last Updated**: 2025-05-28  
**Version**: 2.0
