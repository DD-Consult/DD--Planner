#!/usr/bin/env python3
"""
Retry PDF export test multiple times to check if it's a transient issue
"""

import requests
import time

BASE_URL = "https://ddplan-502760053858.australia-southeast1.run.app"
EMAIL = "don@ddconsult.tech"
PASSWORD = "@Ddplanner2026"
PROJECT_ID = "6a81afb545f7c98ef63971fd"

# Authenticate
print("Authenticating...")
response = requests.post(
    f"{BASE_URL}/api/auth/login",
    data={"username": EMAIL, "password": PASSWORD},
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    timeout=30
)

if response.status_code != 200:
    print(f"❌ Authentication failed: {response.status_code}")
    exit(1)

token = response.json().get("access_token")
print(f"✅ Authenticated successfully\n")

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Retry PDF export 3 times
print("Testing PDF export endpoint (3 attempts with 10s delay between)...")
print("=" * 80)

for attempt in range(1, 4):
    print(f"\nAttempt {attempt}/3:")
    try:
        start_time = time.time()
        response = requests.get(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/export/pdf",
            headers=headers,
            timeout=90
        )
        elapsed = time.time() - start_time
        
        print(f"  Status Code: {response.status_code}")
        print(f"  Response Time: {elapsed:.2f}s")
        print(f"  Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        
        if response.status_code == 200:
            size_kb = len(response.content) / 1024
            print(f"  Content Size: {size_kb:.1f}KB")
            if response.content[:4] == b'%PDF':
                print(f"  ✅ Valid PDF received")
            else:
                print(f"  ❌ Invalid PDF content")
        else:
            print(f"  Response: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        print(f"  ❌ Request timeout (90s)")
    except Exception as e:
        print(f"  ❌ Exception: {str(e)}")
    
    if attempt < 3:
        print(f"  Waiting 10s before next attempt...")
        time.sleep(10)

print("\n" + "=" * 80)
