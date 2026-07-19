#!/bin/bash
# ============================================================
# validate-deploy.sh
# Run this BEFORE pushing to GitHub to catch deployment errors
# Usage: bash scripts/validate-deploy.sh
# ============================================================

set -e
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

check() {
  local desc="$1"
  local result="$2"
  if [ "$result" = "ok" ]; then
    echo -e "  ${GREEN}✓${NC} $desc"
    PASS=$((PASS+1))
  else
    echo -e "  ${RED}✗${NC} $desc — $result"
    FAIL=$((FAIL+1))
  fi
}

warn() {
  echo -e "  ${YELLOW}⚠${NC} $1"
}

echo ""
echo "=== DD Planner Deployment Validator ==="
echo ""

# ── 1. cloudbuild.yaml checks ──
echo "[1] cloudbuild.yaml"
CB=/app/cloudbuild.yaml

# Must exist
[ -f "$CB" ] && check "File exists" "ok" || check "File exists" "MISSING"

# Invalid flags that have broken deploys before
if grep -v '^\s*#' "$CB" 2>/dev/null | grep -q "startup-probe-initial-delay"; then
  check "No invalid --startup-probe-initial-delay flag" "FOUND invalid flag (remove it)"
else
  check "No invalid --startup-probe-initial-delay flag" "ok"
fi

# Must have min-instances
if grep -q "min-instances" "$CB" 2>/dev/null; then
  MIN=$(grep -A1 'min-instances' "$CB" | tail -1 | sed 's/#.*//' | tr -d ' "-')
  if [ "$MIN" -ge 1 ] 2>/dev/null; then
    check "--min-instances >= 1 (prevents cold-start 502)" "ok"
  else
    check "--min-instances >= 1" "WARN: set to $MIN, cold-start 502s likely"
  fi
else
  check "--min-instances present" "MISSING (cold-start 502s likely)"
fi

# Port must be 8080
if grep -q '"8080"' "$CB" 2>/dev/null; then
  check "Port is 8080" "ok"
else
  check "Port is 8080" "not found — Cloud Run requires 8080"
fi

# Secrets must be present
if grep -q 'MONGO_URL=MONGO_URL:latest' "$CB" 2>/dev/null; then
  check "MONGO_URL secret mapped" "ok"
else
  check "MONGO_URL secret mapped" "MISSING"
fi

# ── 2. Dockerfile checks ──
echo ""
echo "[2] Dockerfile"
DF=/app/Dockerfile

[ -f "$DF" ] && check "File exists" "ok" || check "File exists" "MISSING"

if grep -q 'EXPOSE 8080' "$DF" 2>/dev/null; then
  check "EXPOSE 8080" "ok"
else
  check "EXPOSE 8080" "MISSING — Cloud Run requires this"
fi

if grep -q 'yarn build' "$DF" 2>/dev/null; then
  check "Frontend built with yarn" "ok"
else
  check "Frontend built with yarn" "MISSING yarn build step"
fi

if grep -q 'emergentintegrations' "$DF" 2>/dev/null; then
  check "emergentintegrations installed" "ok"
else
  check "emergentintegrations installed" "MISSING — backend AI features will break"
fi

# ── 3. nginx.conf checks ──
echo ""
echo "[3] nginx.conf"
NX=/app/nginx.conf

[ -f "$NX" ] && check "File exists" "ok" || check "File exists" "MISSING"

if grep -q 'listen 8080' "$NX" 2>/dev/null; then
  check "Listening on port 8080" "ok"
else
  check "Listening on port 8080" "WRONG PORT — Cloud Run requires 8080"
fi

if grep -q 'proxy_pass http://127.0.0.1:8001' "$NX" 2>/dev/null; then
  check "/api/ proxied to uvicorn:8001" "ok"
else
  check "/api/ proxied to uvicorn:8001" "MISSING — API calls will 404"
fi

if grep -q 'try_files' "$NX" 2>/dev/null; then
  check "React Router fallback (try_files)" "ok"
else
  check "React Router fallback (try_files)" "MISSING — frontend routes will 404"
fi

# ── 4. supervisord.conf checks ──
echo ""
echo "[4] supervisord.conf"
SV=/app/supervisord.conf

[ -f "$SV" ] && check "File exists" "ok" || check "File exists" "MISSING"

if grep -q 'port 8001' "$SV" 2>/dev/null; then
  check "Uvicorn on port 8001" "ok"
else
  check "Uvicorn on port 8001" "MISSING — nginx can't proxy to backend"
fi

if grep -q 'priority=10' "$SV" 2>/dev/null && grep -q 'priority=20' "$SV" 2>/dev/null; then
  check "Backend starts before nginx (priority=10/20)" "ok"
else
  check "Backend starts before nginx" "priorities missing — race condition possible"
fi

# ── 5. Python backend import check ──
echo ""
echo "[5] Python backend imports"

if cd /app/backend && python3 -c "from server import app" 2>/dev/null; then
  check "server.py imports cleanly" "ok"
else
  check "server.py imports cleanly" "IMPORT ERROR — fix before deploying"
fi

if cd /app/backend && python3 -c "from database import users_collection" 2>/dev/null; then
  check "database.py imports cleanly" "ok"
else
  check "database.py imports cleanly" "IMPORT ERROR — fix before deploying"
fi

# ── 6. Frontend checks ──
echo ""
echo "[6] frontend/package.json"
PJ=/app/frontend/package.json

if python3 -c "import json; d=json.load(open('$PJ')); exit(0 if 'proxy' not in d else 1)" 2>/dev/null; then
  check "No 'proxy' field (breaks Docker build)" "ok"
else
  check "No 'proxy' field" "FOUND — remove it (breaks Docker prod build)"
  warn "Use frontend/src/setupProxy.js for local dev proxy instead"
fi

# ── Summary ──
echo ""
echo "================================"
if [ $FAIL -eq 0 ]; then
  echo -e "${GREEN}All $PASS checks passed — safe to deploy!${NC}"
else
  echo -e "${RED}$FAIL check(s) FAILED, $PASS passed${NC}"
  echo -e "${RED}Fix the above issues before pushing to GitHub.${NC}"
  exit 1
fi
echo ""
