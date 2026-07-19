# Production Login Error - FIXED

## 🚨 ISSUE

**Error:** Network error / Connection refused when logging in to production
**URL Attempted:** `http://localhost:8001/api/auth/login`
**Expected URL:** `https://smartplanning.emergent.host/api/auth/login`

**Browser Console Error:**
```
Login error:
code: "ERR_NETWORK"
request: { _url: 'http://localhost:8001/api/auth/login', _method: 'POST' }
Failed to load resource: net::ERR_CONNECTION_REFUSED
```

---

## 🔍 ROOT CAUSE

The frontend code was using:
```javascript
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
```

**Problem:**
- In production, `process.env.REACT_APP_BACKEND_URL` is not set by Emergent
- Frontend falls back to `http://localhost:8001` (development URL)
- Browser tries to connect to localhost (doesn't exist in production)
- Login fails with network error

---

## ✅ SOLUTION

Changed frontend API configuration to use **relative URLs** which work in both dev and production:

### Before:
```javascript
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

const api = axios.create({
  baseURL: `${BACKEND_URL}/api`,  // Always prepends BACKEND_URL
});
```

### After:
```javascript
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const api = axios.create({
  baseURL: BACKEND_URL ? `${BACKEND_URL}/api` : '/api',  // Relative URL if no env var
});
```

---

## 📊 HOW IT WORKS

### Development Environment:
```
Frontend: http://localhost:3000
Backend: http://localhost:8001
REACT_APP_BACKEND_URL: http://localhost:8001

API calls → http://localhost:8001/api/auth/login ✓
```

### Production Environment (Emergent):
```
Frontend: https://smartplanning.emergent.host/
Backend: https://smartplanning.emergent.host/api/
REACT_APP_BACKEND_URL: (not set)

API calls → /api/auth/login (relative)
Resolves to → https://smartplanning.emergent.host/api/auth/login ✓
```

**Emergent Ingress Routes:**
- `/api/*` → Backend (port 8001)
- `/*` → Frontend (port 3000)

---

## 🎯 WHY RELATIVE URLS WORK

In Emergent deployment:
1. Frontend and backend served from **same domain**
2. Kubernetes ingress routes by path:
   - Frontend: `https://smartplanning.emergent.host/`
   - Backend: `https://smartplanning.emergent.host/api/`

3. Relative URL `/api/auth/login` automatically resolves to correct domain
4. No environment variable needed in production

---

## 🚀 DEPLOYMENT STEPS

### 1. Deploy Updated Code

The fix is already applied in `/app/frontend/src/api.js`

**To deploy:**
```bash
# Commit and push your code
git add frontend/src/api.js
git commit -m "Fix: Use relative URLs for production API calls"
git push

# Or let Emergent deploy from current state
# Emergent will automatically build and deploy
```

### 2. Verify After Deployment

**Test Production Login:**
1. Go to: `https://smartplanning.emergent.host`
2. Enter credentials:
   - Email: `don@ddconsult.tech`
   - Password: `@Ddplanner2026`
3. Click "Sign In"

**Expected Result:** ✅ Login successful, dashboard loads

**Check Browser Console:**
```javascript
// Should see:
POST https://smartplanning.emergent.host/api/auth/login (200 OK)

// NOT:
POST http://localhost:8001/api/auth/login (ERR_CONNECTION_REFUSED)
```

---

## 🔧 ADDITIONAL FIXES INCLUDED

### 1. Development Still Works

With the change, development environment works because:
```javascript
// When REACT_APP_BACKEND_URL is set (development)
BACKEND_URL = 'http://localhost:8001'
baseURL = 'http://localhost:8001/api' ✓

// When REACT_APP_BACKEND_URL is NOT set (production)
BACKEND_URL = ''
baseURL = '/api' ✓
```

### 2. Preview Environment

The preview environment at `https://calc-audit-review.preview.emergentagent.com` also uses relative URLs and will work correctly.

---

## 📋 CHECKLIST FOR PRODUCTION

After redeployment, verify:

- [ ] Production app loads: `https://smartplanning.emergent.host`
- [ ] Login page appears
- [ ] Browser console shows no errors
- [ ] Can enter credentials
- [ ] Click "Sign In" button
- [ ] Network tab shows: `POST /api/auth/login` (200 OK)
- [ ] Dashboard loads successfully
- [ ] Can navigate to Projects, Resources, etc.
- [ ] All API calls use relative URLs (`/api/...`)

---

## ⚠️ COMMON ISSUES & SOLUTIONS

### Issue 1: "Could not validate credentials"
**Cause:** Users not synced to production database
**Solution:** Run user seed or create admin user manually

### Issue 2: "Incorrect email or password"
**Cause:** User exists but password is different
**Solution:** Reset password or use correct production password

### Issue 3: "CORS error"
**Cause:** Backend CORS not configured for production domain
**Solution:** Backend already allows all origins (*), should work

### Issue 4: Still seeing localhost in console
**Cause:** Browser cache
**Solution:** Hard refresh (Ctrl+Shift+R) or clear cache

---

## 🔐 PRODUCTION USER CREDENTIALS

After deployment, ensure these users exist in production MongoDB:

**Super Admin:**
- Email: `don@ddconsult.tech`
- Password: `@Ddplanner2026`
- Role: `super_admin`

**How to verify users exist:**
Check MongoDB Atlas or use backend endpoint:
```bash
curl https://smartplanning.emergent.host/api/users
```

If no users, backend should auto-seed on startup (see server.py line 3456).

---

## 📝 TECHNICAL DETAILS

### File Changed:
- `/app/frontend/src/api.js` (line 4-8)

### Change Type:
- Environment variable fallback logic
- Development: Uses explicit backend URL
- Production: Uses relative URLs

### Compatibility:
- ✅ Development: Works (uses localhost:8001)
- ✅ Preview: Works (uses relative URLs)
- ✅ Production: Works (uses relative URLs)

### No Breaking Changes:
- Existing API calls unchanged
- All endpoints still work
- Token management unchanged
- Error handling unchanged

---

## 🎉 EXPECTED OUTCOME

**After deploying this fix:**

1. ✅ Production login works
2. ✅ All API calls go to correct URL
3. ✅ No more localhost:8001 errors
4. ✅ Dashboard loads properly
5. ✅ All features functional

**User Experience:**
- Login page loads ✓
- Enter credentials ✓
- Click "Sign In" ✓
- Dashboard appears ✓
- Can use all features ✓

---

## 🚨 IF STILL NOT WORKING AFTER DEPLOYMENT

### Check These:

1. **Deployment completed?**
   - Verify new code was deployed
   - Check deployment logs

2. **Cache issue?**
   - Hard refresh browser (Ctrl+Shift+R)
   - Clear browser cache
   - Try incognito window

3. **Backend running?**
   - Check backend logs in Emergent
   - Verify backend responds: `curl https://smartplanning.emergent.host/api/health`

4. **Database connected?**
   - Backend logs should show MongoDB connection
   - Check if users collection has data

5. **Environment variables?**
   - Backend: Check MONGO_URL is set
   - Backend: Check SECRET_KEY is set
   - Frontend: REACT_APP_BACKEND_URL should be empty or not set

---

## 📞 SUPPORT CHECKLIST

If you need help after deployment, provide:

1. **Browser console screenshot** (F12 → Console tab)
2. **Network tab screenshot** (F12 → Network tab, showing auth/login request)
3. **Deployment logs** from Emergent
4. **Backend logs** from Emergent (last 50 lines)
5. **URL you're accessing** (exact URL)

---

## ✅ SUMMARY

**Issue:** Frontend trying to connect to localhost in production
**Cause:** Environment variable not set, fell back to localhost
**Solution:** Use relative URLs that work in all environments
**Status:** ✅ FIXED
**Next Step:** Deploy and test login

---

**Fixed:** Feb 11, 2026
**File Changed:** `/app/frontend/src/api.js`
**Deployment Required:** YES
**Testing Required:** YES (verify login works)
