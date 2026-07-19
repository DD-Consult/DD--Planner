# AI API Configuration Guide - DD Planner

## 🔴 Current Issue: Gemini API Quota Exceeded

**Error:** "You exceeded your current quota, please check your plan and billing details"

**What's happening:**
- Your Gemini API free tier quota has been exhausted
- Free tier limits: 0 input tokens, 0 requests remaining
- The app is trying to use Emergent backup AI but needs proper configuration

---

## ✅ IMMEDIATE SOLUTION OPTIONS

### Option 1: Use Emergent LLM Key (RECOMMENDED - FREE)
The app has built-in fallback to Emergent's universal key for OpenAI/Gemini. This should work automatically but may need Settings verification.

**Steps:**
1. Go to **Settings** page
2. Select **Provider:** Gemini or OpenAI
3. Leave the API key field as-is (system will use Emergent key automatically)
4. Click **Save AI Settings**
5. Test AI command again

**Note:** Emergent LLM key provides free access to:
- OpenAI GPT models (text generation)
- Gemini models (text generation)  
- OpenAI image generation (gpt-image-1)
- Gemini image generation (Nano Banana)

---

### Option 2: Upgrade Gemini API Plan
If you need direct Gemini API access with your own key:

**Steps:**
1. Visit: https://ai.google.dev/gemini-api/docs/rate-limits
2. Log in to your Google AI account
3. Check current usage: https://ai.dev/rate-limit
4. Upgrade from free tier to paid plan
5. Update API key in DD Planner Settings

**Gemini Pricing:**
- **Free Tier:** 15 requests/minute, 1,500 requests/day
- **Pay-as-you-go:** $0.50 per 1M input tokens, $1.50 per 1M output tokens

---

### Option 3: Switch to OpenAI
If Gemini quota is exhausted, use OpenAI instead:

**Steps:**
1. Get OpenAI API key: https://platform.openai.com/api-keys
2. Go to DD Planner **Settings**
3. Select **Provider:** OpenAI
4. Paste your OpenAI API key
5. Click **Save AI Settings**

**OpenAI Pricing:**
- **GPT-4o-mini:** $0.15 per 1M input tokens, $0.60 per 1M output tokens
- **GPT-4o:** Higher cost but better quality

---

## 🔧 HOW DD PLANNER AI SYSTEM WORKS

### Architecture:
```
User Command → Primary Provider (OpenAI/Gemini with user's key)
                    ↓ (if fails)
              Emergent Fallback (free backup AI)
                    ↓ (if fails)
              User-friendly error message
```

### Provider Indicators:
When you use AI commands, you'll see:
- ✓ **Powered by Gemini** - Your Gemini key worked
- ✓ **Powered by OpenAI** - Your OpenAI key worked
- ⚡ **Using Emergent backup AI** - Your key failed, using fallback

---

## ⚠️ COMMON ERRORS & SOLUTIONS

### 1. "Quota exceeded" (429 Error)
**Cause:** API usage limit reached
**Solution:**
- Wait for quota reset (daily/monthly)
- Upgrade API plan
- Switch to Emergent fallback (automatic)

### 2. "Invalid API key" (401/403 Error)
**Cause:** Wrong or expired API key
**Solution:**
- Verify key at provider's dashboard
- Generate new key
- Update in Settings

### 3. "Request timeout" (408 Error)
**Cause:** API taking too long to respond
**Solution:**
- Try again
- System auto-retries with fallback

### 4. "Both primary and fallback failed"
**Cause:** All AI providers unreachable
**Solution:**
- Check internet connection
- Contact Emergent support
- Wait and retry

---

## 📊 MONITORING YOUR USAGE

### Gemini API:
- **Current usage:** https://ai.dev/rate-limit
- **Billing:** https://console.cloud.google.com/billing
- **Quota info:** https://ai.google.dev/gemini-api/docs/rate-limits

### OpenAI API:
- **Usage dashboard:** https://platform.openai.com/usage
- **Billing:** https://platform.openai.com/account/billing
- **API keys:** https://platform.openai.com/api-keys

---

## 💡 BEST PRACTICES

### 1. **Use Emergent LLM Key for Development/Testing**
- Free and automatically available
- No quota concerns for basic usage
- Good for learning the system

### 2. **Use Your Own Key for Production**
- Better control over costs
- Higher rate limits
- Direct billing management

### 3. **Monitor Usage Regularly**
- Set up billing alerts
- Check usage dashboards weekly
- Upgrade plan before hitting limits

### 4. **Optimize AI Commands**
- Be concise in commands
- Batch similar operations
- Use AI selectively (not for every action)

---

## 🆘 STILL HAVING ISSUES?

### If Emergent Fallback Isn't Working:

1. **Check Settings Page:**
   - Open Settings
   - Verify provider is selected
   - Ensure API key field shows some value (or leave empty for Emergent key)

2. **Check Browser Console:**
   - Open Developer Tools (F12)
   - Look for errors in Console tab
   - Share error messages with support

3. **Check Backend Logs:**
   - Error messages will show which step failed
   - Look for "Emergent fallback error" in logs

4. **Contact Support:**
   - Provide screenshot of error
   - Mention which provider you're using
   - Include any console errors

---

## 📝 QUICK REFERENCE

| Provider | Free Tier | Paid Starting | Best For |
|----------|-----------|---------------|----------|
| **Emergent LLM** | ✅ Yes (included) | N/A | Testing, demos, low usage |
| **Gemini** | 1,500 req/day | $0.50/1M tokens | Cost-effective production |
| **OpenAI** | No free tier | $0.15/1M tokens (mini) | High quality results |

---

## 🔐 API KEY SAFETY

**NEVER:**
- Share API keys publicly
- Commit keys to code repositories
- Use production keys for testing

**ALWAYS:**
- Keep keys in DD Planner Settings only
- Rotate keys regularly
- Set spending limits on provider dashboards
- Monitor for unusual usage

---

## ✅ RECOMMENDED SETUP FOR YOUR CASE

Based on your error, here's what I recommend:

1. **Immediate:** Use Emergent LLM key (should work automatically)
2. **Short-term:** Upgrade Gemini to paid plan if you need higher limits
3. **Long-term:** Set up billing alerts and usage monitoring

**Cost Estimate:**
If you process ~1,000 AI commands per day with average 500 tokens each:
- Gemini: ~$0.25/day = $7.50/month
- OpenAI (mini): ~$0.75/day = $22.50/month
- Emergent LLM: FREE (within reasonable limits)

---

**Last Updated:** Feb 9, 2026
**Support:** contact@ddplanner.com (replace with actual support contact)
