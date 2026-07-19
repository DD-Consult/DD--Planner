#!/usr/bin/env python3
"""
Create a test resource user with allocations to test the endpoint with real data
"""
import requests
import json

BASE_URL = "http://localhost:8001"

def create_test_resource_user():
    print("Creating test resource user with allocations...")
    
    # Login as admin
    login_response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": "admin@test.com", "password": "admin123"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get first resource (Alice Johnson)
    resources_response = requests.get(f"{BASE_URL}/api/resources", headers=headers)
    resources = resources_response.json()
    
    if not resources:
        print("❌ No resources found!")
        return
    
    alice = resources[0]
    alice_id = alice["id"]
    print(f"✅ Found resource: {alice['name']} (ID: {alice_id})")
    
    # Create user account linked to Alice
    print("\nCreating user account for Alice...")
    create_user_response = requests.post(
        f"{BASE_URL}/api/admin/create-resource-user?resource_id={alice_id}&email=alice@test.com&password=alice123",
        headers=headers
    )
    
    if create_user_response.status_code == 200:
        print("✅ User account created successfully!")
    else:
        print(f"⚠️  User might already exist: {create_user_response.status_code}")
    
    # Login as Alice
    print("\nLogging in as Alice...")
    alice_login = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": "alice@test.com", "password": "alice123"}
    )
    
    if alice_login.status_code != 200:
        print(f"❌ Login failed: {alice_login.status_code}")
        print(alice_login.text)
        return
    
    alice_token = alice_login.json()["access_token"]
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    print(f"✅ Logged in as Alice!")
    
    # Test the endpoint
    print("\n" + "=" * 80)
    print("Testing /api/my-allocations as Alice (resource user)")
    print("=" * 80)
    
    for period in ["month", "week", "3months"]:
        print(f"\nPeriod: {period}")
        response = requests.get(
            f"{BASE_URL}/api/my-allocations?period={period}",
            headers=alice_headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success!")
            print(f"   Resource: {data['resource']['name']} ({data['resource']['role']})")
            print(f"   Period: {data['period_start']} to {data['period_end']}")
            print(f"   Total allocations: {data['summary']['total_allocations']}")
            print(f"   Capacity used: {data['summary']['capacity_used_percentage']}%")
            print(f"   Weekly hours: {data['summary']['total_weekly_hours']}h")
            print(f"   Period hours: {data['summary']['total_period_hours']}h")
            print(f"   Over capacity: {data['summary']['is_over_capacity']}")
            
            if data['allocations']:
                print(f"\n   Allocations:")
                for alloc in data['allocations']:
                    print(f"     - {alloc['project_name']} ({alloc['client_name']})")
                    print(f"       Role: {alloc['role']}, Percentage: {alloc['percentage']}%, Weekly: {alloc['weekly_hours']}h")
                    print(f"       Period hours: {alloc['period_hours']}h")
                    print(f"       Dates: {alloc['start_date']} to {alloc['end_date']}")
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
    
    print("\n" + "=" * 80)
    print("Sample response (month):")
    print("=" * 80)
    response = requests.get(
        f"{BASE_URL}/api/my-allocations?period=month",
        headers=alice_headers
    )
    print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    create_test_resource_user()
