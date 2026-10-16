#!/usr/bin/env python3
"""Quick test to verify deadline_violated flag behavior."""

import requests

BACKEND_URL = "https://ddplanner-fixes.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"
PROJECT_ID = "6ab25bc82be78e05e89230f3"

# Login
response = requests.post(
    f"{BACKEND_URL}/auth/login",
    data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    headers={"Content-Type": "application/x-www-form-urlencoded"}
)
token = response.json()["access_token"]

# Create task with deadline violation
task_data = {
    "name": "Test Deadline Flag",
    "start_date": "2027-03-01",
    "end_date": "2027-03-20",
    "deadline": "2027-03-10"
}

response = requests.post(
    f"{BACKEND_URL}/projects/{PROJECT_ID}/wbs/tasks",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json=task_data
)

print("CREATE response:")
task = response.json()
task_id = task.get("id")
print(f"  deadline_violated: {task.get('deadline_violated')}")

# Fetch task via GET to see if flag is computed there
response = requests.get(
    f"{BACKEND_URL}/projects/{PROJECT_ID}/wbs",
    headers={"Authorization": f"Bearer {token}"}
)

tasks = response.json()
created_task = next((t for t in tasks if t.get("id") == task_id), None)

print("\nGET response:")
if created_task:
    print(f"  deadline_violated: {created_task.get('deadline_violated')}")
else:
    print("  Task not found in GET response")

# Cleanup
requests.delete(
    f"{BACKEND_URL}/wbs/tasks/{task_id}",
    headers={"Authorization": f"Bearer {token}"}
)
print(f"\nTask {task_id} deleted")

# Test duration_days calculation
print("\n" + "="*80)
print("Testing duration_days calculation")
print("="*80)

from datetime import datetime, timedelta

def snap_to_weekday(d):
    """Snap a date to the next weekday if it falls on a weekend."""
    if d.weekday() == 5:  # Saturday
        return d + timedelta(days=2)
    elif d.weekday() == 6:  # Sunday
        return d + timedelta(days=1)
    return d

def add_business_days(start, num_days):
    """Add `num_days` business days (Mon-Fri) to a date. Returns a date."""
    if isinstance(start, datetime):
        start = start.date()
    start = snap_to_weekday(start)
    current = start
    added = 0
    while added < num_days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current

# Test: Monday 2027-03-02 + 5 business days
start = datetime.strptime("2027-03-02", "%Y-%m-%d").date()
print(f"Start: {start} ({start.strftime('%A')})")

# Backend does: add_business_days(start, duration - 1)
# For duration=5, that's add_business_days(start, 4)
result = add_business_days(start, 4)
print(f"add_business_days(start, 4) = {result} ({result.strftime('%A')})")

# Let's trace through the logic:
print("\nTracing add_business_days(2027-03-02, 4):")
current = start
added = 0
print(f"  Start: {current} ({current.strftime('%A')}), added={added}")
while added < 4:
    current += timedelta(days=1)
    if current.weekday() < 5:
        added += 1
        print(f"  -> {current} ({current.strftime('%A')}), added={added}")
    else:
        print(f"  -> {current} ({current.strftime('%A')}) [weekend, skip]")

print(f"\nFinal result: {current}")
print(f"Expected: 2027-03-06 (Friday)")
