#!/usr/bin/env python3
"""
Export production data using existing API endpoints
"""

import requests
import json
import sys

PROD_URL = "https://smartplanning.emergent.host"
ADMIN_EMAIL = "don@ddconsult.tech"
ADMIN_PASSWORD = "@Ddplanner2026"

def login_and_get_token():
    """Login to production and get auth token"""
    print(f"Logging in to {PROD_URL}...")
    
    response = requests.post(
        f"{PROD_URL}/api/auth/login",
        data={
            "username": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        },
        timeout=30
    )
    
    if response.status_code == 200:
        data = response.json()
        token = data.get('access_token')
        print("✓ Login successful")
        return token
    else:
        print(f"✗ Login failed: {response.status_code}")
        return None

def export_collection(token, endpoint, name):
    """Export a single collection"""
    print(f"  Fetching {name}...")
    
    response = requests.get(
        f"{PROD_URL}{endpoint}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60
    )
    
    if response.status_code == 200:
        data = response.json()
        count = len(data) if isinstance(data, list) else 1
        print(f"    ✓ {count} documents")
        return data
    else:
        print(f"    ✗ Failed: {response.status_code}")
        return []

def main():
    print("="*80)
    print("PRODUCTION DATA EXPORT")
    print("="*80)
    print()
    
    # Login
    token = login_and_get_token()
    if not token:
        sys.exit(1)
    
    print("\nExporting data from production...")
    
    # Export each collection using existing endpoints
    export_data = {
        "export_metadata": {
            "source": "production",
            "url": PROD_URL
        },
        "collections": {}
    }
    
    # Map of collection names to API endpoints
    endpoints = {
        "users": "/api/users",
        "resources": "/api/resources", 
        "projects": "/api/projects",
        "allocations": "/api/allocations",
        "allocation_roles": "/api/allocation-roles",
        "timesheets": "/api/timesheets/all-timesheets",  # Try this
        "status_updates": "/api/status-updates/all",  # Try this
        "risks": "/api/risks/all",  # Try this
    }
    
    for coll_name, endpoint in endpoints.items():
        data = export_collection(token, endpoint, coll_name)
        export_data["collections"][coll_name] = data
    
    # Save to file
    filename = "production_export.json"
    with open(filename, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    import os
    size_mb = os.path.getsize(filename) / (1024 * 1024)
    
    print(f"\n✓ Export complete!")
    print(f"  File: {filename}")
    print(f"  Size: {size_mb:.2f} MB")
    
    # Show summary
    total = sum(len(v) if isinstance(v, list) else 0 for v in export_data["collections"].values())
    print(f"\nTotal documents: {total}")
    
    print("\n" + "="*80)
    print("NEXT: Import to preview")
    print("="*80)
    print(f"\npython data_sync.py --import-file {filename} --no-dry-run")

if __name__ == '__main__':
    main()
