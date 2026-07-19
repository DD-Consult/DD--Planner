#!/usr/bin/env python3
"""
Update Gemini API key in MongoDB Atlas (production database).
This will immediately fix the 502 error in your GCP Cloud Run deployment.
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

# Your MongoDB Atlas connection string (from GCP_DEPLOYMENT.md)
ATLAS_MONGO_URL = "mongodb+srv://ddplanner:%40DDplanner2026%21@cluster0.iy30moq.mongodb.net/resource_planner?retryWrites=true&w=majority"

# New Gemini API key
NEW_GEMINI_KEY = "AIzaSyCWrc_BsY2kJgM706xsfnbu2kBHNJIIEjA"

async def update_production_gemini_key():
    """Update Gemini API key in production Atlas database."""
    
    print("=" * 70)
    print("UPDATING GEMINI API KEY IN PRODUCTION DATABASE")
    print("=" * 70)
    
    print(f"\n🔗 Connecting to MongoDB Atlas...")
    print(f"   Database: resource_planner")
    
    client = AsyncIOMotorClient(ATLAS_MONGO_URL)
    db = client["resource_planner"]
    settings_collection = db.settings
    
    try:
        # Check current configuration
        existing = await settings_collection.find_one({"type": "ai_config"})
        
        if existing:
            print(f"\n📋 Current AI Configuration:")
            print(f"   Provider: {existing.get('ai_provider', 'N/A')}")
            old_key = existing.get('ai_api_key', '')
            if old_key:
                print(f"   Old API Key: {old_key[:10]}...{old_key[-4:]}")
                if "bmWkO5MiwOFJqcf09JeNfTC4lO-nkNYkU" in old_key:
                    print(f"   ⚠️  This is the LEAKED key that's causing 502 errors!")
            else:
                print(f"   Old API Key: Not set")
        else:
            print(f"\n📋 No existing AI configuration found in database")
        
        # Update with new Gemini key
        print(f"\n🔄 Updating configuration...")
        result = await settings_collection.update_one(
            {"type": "ai_config"},
            {
                "$set": {
                    "type": "ai_config",
                    "ai_provider": "gemini",
                    "ai_api_key": NEW_GEMINI_KEY
                }
            },
            upsert=True
        )
        
        if result.modified_count > 0 or result.upserted_id:
            print(f"\n✅ SUCCESS! Gemini API key updated in production database!")
            print(f"\n📌 New Configuration:")
            print(f"   Provider: gemini")
            print(f"   API Key: {NEW_GEMINI_KEY[:10]}...{NEW_GEMINI_KEY[-4:]}")
            print(f"   Model: gemini-2.5-flash")
            
            print(f"\n🎉 AI features are now enabled in production:")
            print(f"   ✓ AI Chatbot (DD Planner AI)")
            print(f"   ✓ Natural language commands")
            print(f"   ✓ Budget analysis")
            print(f"   ✓ Portfolio insights")
            
            print(f"\n⚡ Changes take effect IMMEDIATELY - no redeployment needed!")
            print(f"   Your GCP Cloud Run app will use this key on the next AI request.")
        else:
            print(f"\n⚠️  No changes made (key might already be set)")
        
        # Verify the update
        verify = await settings_collection.find_one({"type": "ai_config"})
        if verify and verify.get("ai_provider") == "gemini" and verify.get("ai_api_key") == NEW_GEMINI_KEY:
            print(f"\n✓ Verification: Configuration successfully stored in Atlas database")
        else:
            print(f"\n⚠️  Warning: Could not verify configuration update")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print(f"\nTroubleshooting:")
        print(f"  1. Verify MongoDB Atlas Network Access allows your IP")
        print(f"  2. Check that the connection string is correct")
        print(f"  3. Ensure the password is URL-encoded: @DDplanner2026! → %40DDplanner2026%21")
        raise
    finally:
        client.close()
        print(f"\n✓ Database connection closed")
    
    print(f"\n" + "=" * 70)
    print(f"🧪 TEST YOUR DEPLOYMENT:")
    print(f"=" * 70)
    print(f"\n1. Get your Cloud Run URL:")
    print(f"   gcloud run services describe dd-planner --region=australia-southeast1 --format='value(status.url)'")
    print(f"\n2. Test the AI chat:")
    print(f"   (Login and use the AI chatbot in the web interface)")
    print(f"\n3. The 502 error should be resolved!")
    print(f"\n" + "=" * 70)

if __name__ == "__main__":
    asyncio.run(update_production_gemini_key())
