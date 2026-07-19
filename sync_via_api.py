#!/usr/bin/env python3
"""
Sync production data via API endpoint
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
    
    # Try form data format (username/password)
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
        print(response.text)
        return None

def export_production_data(token):
    """Export all data from production"""
    print("\nExporting production data (this may take 30-60 seconds)...")
    
    response = requests.get(
        f"{PROD_URL}/api/admin/export-database",
        headers={"Authorization": f"Bearer {token}"},
        timeout=180
    )
    
    if response.status_code == 200:
        data = response.json()
        
        # Show summary
        print("\n✓ Export successful!")
        print("\nCollections exported:")
        total_docs = 0
        for coll, docs in data.get('collections', {}).items():
            count = len(docs)
            total_docs += count
            print(f"  {coll}: {count} documents")
        
        print(f"\nTotal: {total_docs} documents")
        
        # Save to file
        filename = "production_export_via_api.json"
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        import os
        size_mb = os.path.getsize(filename) / (1024 * 1024)
        print(f"\n✓ Saved to: {filename} ({size_mb:.2f} MB)")
        return filename
    else:
        print(f"✗ Export failed: {response.status_code}")
        print(response.text)
        return None

def main():
    print("="*80)
    print("PRODUCTION DATA SYNC VIA API")
    print("="*80)
    print()
    
    # Step 1: Login
    token = login_and_get_token()
    if not token:
        sys.exit(1)
    
    # Step 2: Export
    filename = export_production_data(token)
    if not filename:
        sys.exit(1)
    
    # Step 3: Show next steps
    print("\n" + "="*80)
    print("NEXT STEP: Import to local database")
    print("="*80)
    print()
    print("Run this command to import:")
    print(f"  python data_sync.py --import-file {filename} --no-dry-run")
    print()

if __name__ == '__main__':
    main()
