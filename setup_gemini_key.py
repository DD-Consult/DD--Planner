#!/usr/bin/env python3
"""
Script to configure Gemini API key in the DD Planner database settings.
This will enable AI features (chatbot, command parser, budget analysis).
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
MONGO_DB_NAME = os.environ.get('DB_NAME') or os.environ.get('MONGO_DB_NAME', 'resource_planner')

async def setup_gemini_key():
    """Set up Gemini API key in database settings."""
    
    # Your Gemini API key
    GEMINI_API_KEY = "AIzaSyCWrc_BsY2kJgM706xsfnbu2kBHNJIIEjA"
    
    print(f"Connecting to MongoDB at: {MONGO_URL[:50]}...")
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[MONGO_DB_NAME]
    settings_collection = db.settings
    
    try:
        # Check if AI config already exists
        existing = await settings_collection.find_one({"type": "ai_config"})
        
        if existing:
            print(f"\n✓ Found existing AI config:")
            print(f"  Provider: {existing.get('ai_provider', 'N/A')}")
            masked_key = existing.get('ai_api_key', '')
            if masked_key:
                print(f"  API Key: {masked_key[:7]}...{masked_key[-4:]}")
            else:
                print(f"  API Key: Not set")
        
        # Update with Gemini key
        result = await settings_collection.update_one(
            {"type": "ai_config"},
            {
                "$set": {
                    "type": "ai_config",
                    "ai_provider": "gemini",
                    "ai_api_key": GEMINI_API_KEY
                }
            },
            upsert=True
        )
        
        if result.modified_count > 0 or result.upserted_id:
            print(f"\n✅ Successfully configured Gemini API key!")
            print(f"   Provider: gemini")
            print(f"   API Key: {GEMINI_API_KEY[:7]}...{GEMINI_API_KEY[-4:]}")
            print(f"\n🎉 AI features are now enabled:")
            print(f"   - AI Chatbot (DD Planner AI)")
            print(f"   - Natural language commands")
            print(f"   - Budget analysis")
            print(f"   - Portfolio insights")
        else:
            print(f"\n⚠️  No changes made (key already set)")
        
        # Verify the setting
        verify = await settings_collection.find_one({"type": "ai_config"})
        if verify and verify.get("ai_provider") == "gemini" and verify.get("ai_api_key"):
            print(f"\n✓ Verification: AI config is properly stored in database")
        else:
            print(f"\n⚠️  Warning: Could not verify AI config")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise
    finally:
        client.close()
        print(f"\n✓ Database connection closed")

if __name__ == "__main__":
    asyncio.run(setup_gemini_key())
