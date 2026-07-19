#!/usr/bin/env python3
"""Test Gemini API directly to verify the key works."""
import httpx
import asyncio
import json

GEMINI_API_KEY = "AIzaSyBmWkO5MiwOFJqcf09JeNfTC4lO-nkNYkU"

async def test_gemini():
    """Test Gemini API with a simple request."""
    
    print("Testing Gemini API...")
    print(f"API Key: {GEMINI_API_KEY[:10]}...{GEMINI_API_KEY[-4:]}")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [{
                "text": "You are a helpful assistant. Respond with valid JSON: {\"message\": \"Hello from Gemini!\"}"
            }]
        }],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json"
        }
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print(f"\nSending request to: {url[:80]}...")
            response = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload
            )
            
            print(f"\nResponse Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n✅ SUCCESS! Gemini API is working!")
                print(f"\nResponse preview:")
                print(json.dumps(data, indent=2)[:500])
            else:
                print(f"\n❌ FAILED!")
                print(f"Error: {response.text[:500]}")
                
        except Exception as e:
            print(f"\n❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini())
