# DD Planner — Deployment Reference

> **READ THIS BEFORE TOUCHING ANY DEPLOYMENT FILE**
> Any change to the files listed below can break the GCP Cloud Run deployment.
> Always validate with `bash scripts/validate-deploy.sh` before pushing.

---

## Architecture Overview

```
GitHub push
    └─► Cloud Build (cloudbuild.yaml)
            ├─► docker build  (Dockerfile)
            ├─► docker push   (Artifact Registry)
            └─► gcloud run deploy  (Cloud Run)
                    └─► Container runs:
                            ├─► supervisord
                            │       ├─► uvicorn (port 8001)  ← Python/FastAPI
                            │       └─► nginx   (port 8080)  ← serves frontend + proxies /api/
                            └─► nginx proxies /api/* → uvicorn
```

---

## Deployment-Critical Files — DO NOT MODIFY WITHOUT REVIEW

| File | Purpose | Risk if broken |
|------|---------|----------------|
| `cloudbuild.yaml` | GCP Cloud Build pipeline | Build fails, no deployment |
| `Dockerfile` | Container image definition | Image build fails |
| `nginx.conf` | Web server + API proxy config | All requests fail (502/404) |
| `supervisord.conf` | Process manager (starts nginx + uvicorn) | Container starts but serves nothing |
| `backend/requirements.txt` | Python dependencies | Backend crashes on startup |
| `frontend/package.json` | Frontend dependencies + build config | Frontend build fails |

---

## `cloudbuild.yaml` — Rules

### Valid `gcloud run deploy` flags (verified working)
```
--image, --region, --platform managed, --port, --memory, --cpu
--min-instances, --max-instances, --timeout, --allow-unauthenticated
--set-env-vars, --update-secrets
```

### ❌ NEVER add these (they don't exist or break the deploy)
```
--startup-probe-initial-delay   ← INVALID (broke deploy on 2026-04-26)
--startup-probe-path            ← use --startup-probe instead (different syntax)
```

### Current secrets required in GCP Secret Manager
All 4 must exist or deployment fails:
- `MONGO_URL` — MongoDB Atlas connection string
- `SECRET_KEY` — JWT signing secret
- `EMERGENT_LLM_KEY` — Emergent LLM API key
- `EXPORT_API_KEY` — Export feature key

### Current settings (do not change without reason)
- `--min-instances 1` — Keeps 1 container always warm (prevents cold-start 502)
- `--memory 1Gi` — Enough for Python + nginx
- `--port 8080` — nginx listens here, Cloud Run routes to this port

---

## `Dockerfile` — Rules

- **Stage 1**: Node 20 Alpine → builds React frontend via `yarn build`
- **Stage 2**: Python 3.11 slim → runs backend + serves frontend via nginx
- `COPY backend/requirements.txt` then `pip install` — do NOT skip pinned versions
- `emergentintegrations` is installed separately (private index) — do NOT move to requirements.txt
- `EXPOSE 8080` must stay — Cloud Run uses this port
- The health check uses `/health` endpoint — do NOT remove that route from backend

---

## `nginx.conf` — Rules

- Port must be `8080` (Cloud Run requirement)
- `/api/` must proxy to `http://127.0.0.1:8001` (uvicorn's port)
- `/health` must proxy to `http://127.0.0.1:8001/health`
- `try_files $uri $uri/ /index.html` must stay for React Router to work
- Do NOT add `listen 80` or change the port

---

## `supervisord.conf` — Rules

- `backend` has `priority=10` → starts BEFORE nginx (priority=20)
- `startretries=5` on backend → survives transient startup failures
- `--workers 1` on uvicorn → single worker is reliable in Cloud Run
- Do NOT set `minPoolSize` > 0 in database.py (causes aggressive connections at startup)

---

## `frontend/package.json` — Rules

- Do NOT add a `"proxy"` field — it confuses the Docker production build
- Use `frontend/src/setupProxy.js` for local dev proxy instead
- `yarn build` is used in Docker (NOT `npm build`)
- All new frontend packages must be added via `yarn add` (NOT npm)

---

## `backend/requirements.txt` — Rules

- All versions are pinned — do NOT change versions without testing
- If adding a new package: add it to requirements.txt AND install it locally
- Never remove packages that are imported anywhere in the backend

---

## Safe to Modify Freely

These files do NOT affect deployment:
- `backend/routes/*.py` — backend logic
- `backend/models/schemas.py` — Pydantic models
- `backend/services/*.py` — helper services
- `frontend/src/**/*.js` — React components
- `frontend/src/api.js` — API client
- `frontend/src/setupProxy.js` — local dev only, not in Docker build

---

## Quick Deploy Checklist

Before clicking **Save to Github**:
- [ ] Run `bash scripts/validate-deploy.sh` — checks cloudbuild.yaml flags
- [ ] Backend starts locally: `tail -n 5 /var/log/supervisor/backend.err.log`
- [ ] No lint errors: check browser console
- [ ] `cloudbuild.yaml` has no new flags you're not 100% sure about
