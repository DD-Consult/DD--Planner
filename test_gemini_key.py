#!/usr/bin/env python3
"""
Test Gemini API Key directly
"""

import sys
import requests

def test_gemini_key(api_key):
    """Test if Gemini API key works"""
    
    print("="*60)
    print("GEMINI API KEY TEST")
    print("="*60)
    print()
    
    # Test with a simple request
    print(f"Testing API key: {api_key[:10]}...{api_key[-4:]}")
    print()
    
    # Available Gemini models to try
    models = [
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-pro"
    ]
    
    for model in models:
        print(f"\nTrying model: {model}")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": "Say hello in JSON format with a 'message' field"
                }]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json"
            }
        }
        
        try:
            response = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=10
            )
            
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"  ✓ SUCCESS! Model {model} works!")
                result = response.json()
                print(f"  Response: {result}")
                return model
            else:
                print(f"  ✗ Error: {response.text[:200]}")
                
        except Exception as e:
            print(f"  ✗ Exception: {str(e)[:100]}")
    
    print("\n" + "="*60)
    print("NO WORKING MODEL FOUND")
    print("="*60)
    print()
    print("Possible issues:")
    print("1. API key is invalid or expired")
    print("2. API key doesn't have permission for Gemini API")
    print("3. Gemini API not enabled in Google Cloud Console")
    print("4. Billing not set up for the API key")
    print()
    print("To fix:")
    print("1. Go to: https://aistudio.google.com/app/apikey")
    print("2. Check if your key is valid")
    print("3. Make sure 'Generative Language API' is enabled")
    print("4. Check billing is set up")
    
    return None

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_gemini_key.py YOUR_API_KEY")
        sys.exit(1)
    
    api_key = sys.argv[1]
    working_model = test_gemini_key(api_key)
    
    if working_model:
        print(f"\n✓ Use model: {working_model}")
