# Update Gemini API Key in GCP Cloud Run

## ✅ Issue Resolved Locally

The Gemini API key has been successfully updated in the local database and all AI features are now working:
- ✅ AI Chatbot (DD Planner AI)
- ✅ Natural language commands
- ✅ Budget analysis
- ✅ Portfolio insights

**New Gemini API Key:** `AIzaSyCWrc_BsY2kJgM706xsfnbu2kBHNJIIEjA`

---

## 🚀 Update the Key in GCP Cloud Run Deployment

To fix the 502 error in your GCP deployment, you have **two options**:

### Option 1: Store in Database (Recommended for Quick Fix)

This approach updates the AI settings directly in your MongoDB Atlas database, which is accessible by your Cloud Run deployment.

```bash
# Run this script to update the Gemini key in your Atlas database
python3 /app/setup_gemini_key.py
```

**OR** manually update via MongoDB Atlas UI:
1. Go to MongoDB Atlas: https://cloud.mongodb.com
2. Browse Collections → `resource_planner` database → `settings` collection
3. Find/Create document with `type: "ai_config"`
4. Set fields:
   ```json
   {
     "type": "ai_config",
     "ai_provider": "gemini",
     "ai_api_key": "AIzaSyCWrc_BsY2kJgM706xsfnbu2kBHNJIIEjA"
   }
   ```

**Pros:** No redeployment needed, instant update
**Cons:** API key stored in database (less secure than GCP Secret Manager)

---

### Option 2: Update GCP Secret Manager (Most Secure - Recommended for Production)

This stores the API key securely in GCP Secret Manager.

#### Step 1: Update the EMERGENT_LLM_KEY Secret

```bash
# Authenticate to GCP
gcloud auth login
gcloud config set project dd-planner-494404

# Update the secret with new Gemini key
echo -n "AIzaSyCWrc_BsY2kJgM706xsfnbu2kBHNJIIEjA" | \
  gcloud secrets versions add EMERGENT_LLM_KEY --data-file=-
```

#### Step 2: Update Cloud Run Environment

The app will automatically use the EMERGENT_LLM_KEY if no database AI config is set. To ensure it uses the secret:

1. **Clear the database AI config** (so it falls back to EMERGENT_LLM_KEY):
   ```bash
   # Connect to your Atlas database and run:
   db.settings.deleteOne({"type": "ai_config"})
   ```

2. **Restart Cloud Run** to pick up the new secret:
   ```bash
   gcloud run services update dd-planner \
     --region australia-southeast1
   ```

**Pros:** Most secure, follows best practices
**Cons:** Requires GCP access and redeployment

---

## 🔧 How the App Chooses API Keys (Priority Order)

1. **Database Settings** (`settings` collection with `type: "ai_config"`)
   - If `ai_provider` is set to "gemini" and `ai_api_key` exists → uses this

2. **Environment Variable Fallback**
   - If no database config → uses `EMERGENT_LLM_KEY` environment variable
   - In GCP, this is pulled from Secret Manager

3. **No Key Available**
   - Returns error: "No AI provider configured"

---

## 🧪 Test Your Deployment

After updating, test the AI endpoints:

```bash
# Get your Cloud Run URL
URL=$(gcloud run services describe dd-planner --region=australia-southeast1 --format="value(status.url)")

# Test login
TOKEN=$(curl -s -X POST "$URL/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=don@ddconsult.tech&password=@Ddplanner2026" | jq -r .access_token)

# Test AI command
curl -X POST "$URL/api/ai/command" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "Show me all active projects"}' | jq

# Test AI chat
curl -X POST "$URL/api/ai/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message": "What projects are currently active?", "session_id": null}' | jq .response
```

---

## 📋 Summary of Changes Made

1. ✅ **Updated Gemini API key** from `AIzaSyBmWkO5MiwOFJqcf09JeNfTC4lO-nkNYkU` (leaked/disabled) to `AIzaSyCWrc_BsY2kJgM706xsfnbu2kBHNJIIEjA` (active)
2. ✅ **Verified API key** works with Gemini API (model: gemini-2.5-flash)
3. ✅ **Updated local database** settings collection
4. ✅ **Tested all AI endpoints** - all working correctly
5. ✅ **Backend restarted** and confirmed healthy

---

## 🔐 Security Note

**IMPORTANT:** The old API key was reported as leaked. Make sure to:
- ✅ Keep the new key secure
- ✅ Never commit API keys to Git
- ✅ Use GCP Secret Manager for production
- ✅ Rotate keys regularly
- ✅ Monitor key usage in Google AI Studio: https://aistudio.google.com/apikey

---

## Need Help?

If you encounter issues:
1. Check Cloud Run logs: `gcloud run services logs dd-planner --region=australia-southeast1 --limit=100`
2. Verify MongoDB connection: `curl $URL/health`
3. Check AI settings: `curl $URL/api/settings/ai -H "Authorization: Bearer $TOKEN"`
