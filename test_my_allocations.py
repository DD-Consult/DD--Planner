#!/usr/bin/env python3
"""
Test script for the new /api/my-allocations endpoint
"""
import requests
import json

BASE_URL = "http://localhost:8001"

def test_endpoint():
    print("=" * 80)
    print("Testing GET /api/my-allocations endpoint")
    print("=" * 80)
    
    # Step 1: Login as admin
    print("\n1. Logging in as admin@test.com...")
    login_response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={
            "username": "admin@test.com",
            "password": "admin123"
        }
    )
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        print(login_response.text)
        return
    
    token_data = login_response.json()
    token = token_data["access_token"]
    print(f"✅ Login successful! Token: {token[:20]}...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Step 2: Test with period="month" (default)
    print("\n2. Testing with period='month' (default)...")
    response = requests.get(
        f"{BASE_URL}/api/my-allocations",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success! Status: {response.status_code}")
        print(f"\nResponse structure:")
        print(f"  - period: {data.get('period')}")
        print(f"  - period_start: {data.get('period_start')}")
        print(f"  - period_end: {data.get('period_end')}")
        print(f"  - resource: {data.get('resource')}")
        print(f"  - summary: {json.dumps(data.get('summary'), indent=4)}")
        print(f"  - allocations count: {len(data.get('allocations', []))}")
        if data.get('allocations'):
            print(f"\nFirst allocation:")
            print(json.dumps(data['allocations'][0], indent=4))
    else:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)
    
    # Step 3: Test with period="week"
    print("\n3. Testing with period='week'...")
    response = requests.get(
        f"{BASE_URL}/api/my-allocations?period=week",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success! Period: {data.get('period')}")
        print(f"   Date range: {data.get('period_start')} to {data.get('period_end')}")
        print(f"   Total allocations: {data.get('summary', {}).get('total_allocations')}")
    else:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)
    
    # Step 4: Test with period="3months"
    print("\n4. Testing with period='3months'...")
    response = requests.get(
        f"{BASE_URL}/api/my-allocations?period=3months",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success! Period: {data.get('period')}")
        print(f"   Date range: {data.get('period_start')} to {data.get('period_end')}")
        print(f"   Total period hours: {data.get('summary', {}).get('total_period_hours')}")
    else:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)
    
    # Step 5: Test with invalid period
    print("\n5. Testing with invalid period='invalid'...")
    response = requests.get(
        f"{BASE_URL}/api/my-allocations?period=invalid",
        headers=headers
    )
    
    if response.status_code == 400:
        print(f"✅ Correctly rejected invalid period! Status: {response.status_code}")
        print(f"   Error: {response.json().get('detail')}")
    else:
        print(f"❌ Unexpected response: {response.status_code}")
        print(response.text)
    
    # Step 6: Test as client user (should be rejected)
    print("\n6. Testing access as client user...")
    login_response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={
            "username": "client@test.com",
            "password": "client123"
        }
    )
    
    if login_response.status_code == 200:
        client_token = login_response.json()["access_token"]
        client_headers = {"Authorization": f"Bearer {client_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/my-allocations",
            headers=client_headers
        )
        
        if response.status_code == 403:
            print(f"✅ Correctly rejected client access! Status: {response.status_code}")
            print(f"   Error: {response.json().get('detail')}")
        else:
            print(f"❌ Client should not have access! Status: {response.status_code}")
            print(response.text)
    
    print("\n" + "=" * 80)
    print("Testing complete!")
    print("=" * 80)

if __name__ == "__main__":
    test_endpoint()
