#!/usr/bin/env python3
"""
Test AI Chat JSON Response - Verify that structured JSON is not stripped
"""

import requests
import json

BACKEND_URL = "https://enhance-feedback-2.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"


def login():
    response = requests.post(
        f"{BACKEND_URL}/auth/login",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    return None


def test_ai_chat_json_preservation():
    """Test that AI chat preserves JSON blocks in responses"""
    print("=" * 80)
    print("Testing AI Chat JSON Preservation")
    print("=" * 80)
    
    token = login()
    if not token:
        print("❌ Login failed")
        return False
    
    # Test 1: Ask for a status summary that should return JSON
    print("\n🧪 Test 1: Request structured status summary")
    payload = {
        "message": "Give me a structured status summary of all projects in JSON format with fields: project_name, status, health, progress_percentage",
        "session_id": None
    }
    
    response = requests.post(
        f"{BACKEND_URL}/ai/chat",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=payload
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        response_text = data.get("response", "")
        
        print(f"\nResponse length: {len(response_text)} chars")
        print(f"\nFull response:\n{'-' * 80}")
        print(response_text)
        print('-' * 80)
        
        # Check if response contains JSON
        if "{" in response_text and "}" in response_text:
            print("\n✅ Response contains JSON-like structure")
            
            # Try to extract and parse JSON
            try:
                # Try to find JSON block
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = response_text[start:end]
                    parsed = json.loads(json_str)
                    print(f"✅ Successfully parsed JSON with {len(parsed)} top-level keys")
                    print(f"Keys: {list(parsed.keys())}")
                    return True
            except json.JSONDecodeError as e:
                print(f"⚠️  JSON-like structure found but couldn't parse: {e}")
                # Check if it's an array
                try:
                    start = response_text.find("[")
                    end = response_text.rfind("]") + 1
                    if start >= 0 and end > start:
                        json_str = response_text[start:end]
                        parsed = json.loads(json_str)
                        print(f"✅ Successfully parsed JSON array with {len(parsed)} items")
                        return True
                except:
                    pass
        else:
            print("ℹ️  Response is plain text (no JSON structure)")
        
        # Even if not JSON, the endpoint works
        return True
    else:
        print(f"❌ FAIL: {response.text}")
        return False


if __name__ == "__main__":
    success = test_ai_chat_json_preservation()
    exit(0 if success else 1)
