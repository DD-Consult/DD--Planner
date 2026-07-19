# DD Planner — GCP Cloud Run Deployment Guide

## Prerequisites
- GCP Project: `dd-planner-494404` (Project #134869041805)
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed locally
- MongoDB Atlas account (free tier is fine for start)

---

## Step-by-Step Deployment

### 1. Authenticate & Set Project
```bash
gcloud auth login
gcloud config set project dd-planner-494404
```

### 2. Enable Required APIs
```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com
```

### 3. Create Artifact Registry Repository
```bash
gcloud artifacts repositories create dd-planner \
  --repository-format=docker \
  --location=australia-southeast1 \
  --description="DD Planner Docker images"
```

### 4. Set Up MongoDB Atlas

Your Atlas cluster is already set up and migrated:
- **Cluster**: `cluster0.iy30moq.mongodb.net`
- **Database**: `resource_planner`
- **Connection string**: `mongodb+srv://ddplanner:<URL-ENCODED-PASSWORD>@cluster0.iy30moq.mongodb.net/resource_planner?retryWrites=true&w=majority`
- **Data migrated**: 8 users, 25 projects, 74 allocations, 194 timesheets, 45 status updates, 6 risks

> **Note**: The password contains special characters (`@`, `!`) and must be URL-encoded in the connection string. The encoded form is: `%40DDplanner2026%21`

### 5. ~~Migrate Production Data~~ — DONE

Production data has been migrated to your Atlas cluster. Verified:
- 8 users (admin login tested: PASS)
- 25 projects, 74 allocations, 194 timesheets, 45 status updates
- All ObjectIds and dates properly restored

To re-run migration at any time (pulls fresh data from Emergent production):
```bash
python3 migrate_production_db.py import \
  --target-mongo "mongodb+srv://ddplanner:%40DDplanner2026%21@cluster0.iy30moq.mongodb.net/resource_planner?retryWrites=true&w=majority"
```

### 6. Store Secrets in GCP Secret Manager
```bash
# MongoDB connection string (URL-encoded password)
echo -n "mongodb+srv://ddplanner:%40DDplanner2026%21@cluster0.iy30moq.mongodb.net/resource_planner?retryWrites=true&w=majority" | \
  gcloud secrets create MONGO_URL --data-file=-

# JWT secret key (generate a strong one)
python3 -c "import secrets; print(secrets.token_hex(32), end='')" | \
  gcloud secrets create SECRET_KEY --data-file=-

# Emergent LLM key (for AI features — get from your Emergent profile)
echo -n "YOUR_EMERGENT_LLM_KEY" | \
  gcloud secrets create EMERGENT_LLM_KEY --data-file=-

# Export API key (for database export endpoint)
echo -n "0ulG5kuzP1NRFKk8kH4D1GM0jd7IgMfZECLnAFIO_zvHNDA8hk8QI5pB9NVPaHlB" | \
  gcloud secrets create EXPORT_API_KEY --data-file=-
```

Grant Cloud Run access to secrets:
```bash
# Get the Cloud Run service account
SA=$(gcloud iam service-accounts list --filter="displayName:Compute Engine default" --format="value(email)")

gcloud secrets add-iam-policy-binding MONGO_URL --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding SECRET_KEY --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding EMERGENT_LLM_KEY --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding EXPORT_API_KEY --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
```

### 7. Deploy to Cloud Run

#### Option A: Automatic via Cloud Build (Recommended)
```bash
# From repo root — builds image + deploys in one step
gcloud builds submit --config cloudbuild.yaml --substitutions=SHORT_SHA=$(git rev-parse --short HEAD)
```

#### Option B: Manual Deploy
```bash
# Build locally
docker build -t australia-southeast1-docker.pkg.dev/dd-planner-494404/dd-planner/dd-planner:latest .

# Push to Artifact Registry
docker push australia-southeast1-docker.pkg.dev/dd-planner-494404/dd-planner/dd-planner:latest

# Deploy to Cloud Run
gcloud run deploy dd-planner \
  --image australia-southeast1-docker.pkg.dev/dd-planner-494404/dd-planner/dd-planner:latest \
  --region australia-southeast1 \
  --platform managed \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --timeout 300 \
  --allow-unauthenticated \
  --set-env-vars "DB_NAME=resource_planner" \
  --set-secrets "MONGO_URL=MONGO_URL:latest,SECRET_KEY=SECRET_KEY:latest,EMERGENT_LLM_KEY=EMERGENT_LLM_KEY:latest,EXPORT_API_KEY=EXPORT_API_KEY:latest"
```

### 8. Verify Deployment
```bash
# Get the Cloud Run URL
URL=$(gcloud run services describe dd-planner --region=australia-southeast1 --format="value(status.url)")
echo "App URL: $URL"

# Health check
curl -s "$URL/health"

# Test login
curl -s -X POST "$URL/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=don@ddconsult.tech&password=@Ddplanner2026"
```

### 9. Custom Domain (Optional — can do after deployment)
```bash
# Map your domain (e.g., planner.ddconsult.tech)
gcloud run domain-mappings create \
  --service dd-planner \
  --region australia-southeast1 \
  --domain planner.ddconsult.tech

# It will show DNS records you need to add:
# Usually a CNAME record pointing to ghs.googlehosted.com
```

Then in your DNS provider (Cloudflare, Route53, etc.):
- Add CNAME: `planner` → `ghs.googlehosted.com`
- SSL is auto-provisioned by Google

---

## Architecture on GCP

```
[Browser] → [Cloud Run (port 8080)]
                ├─ Nginx (frontend static + /api proxy)
                └─ Uvicorn (FastAPI backend, port 8001)
                        └─ MongoDB Atlas (cloud database)
```

## Costs (Estimated)
- **Cloud Run**: ~$0-5/month (free tier: 2M requests/month, auto-scales to 0)
- **MongoDB Atlas M0**: Free (512MB, shared cluster)
- **Artifact Registry**: ~$0.10/GB/month storage
- **Cloud Build**: 120 min/day free tier
- **Custom Domain**: Free (Google-managed SSL)

**Total: ~$0-10/month** for typical DD Consulting usage.

---

## CI/CD with GitHub Actions (Optional)

Create `.github/workflows/deploy.yml`:
```yaml
name: Deploy to Cloud Run
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write

    steps:
      - uses: actions/checkout@v4

      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.WIF_SERVICE_ACCOUNT }}

      - uses: google-github-actions/setup-gcloud@v2

      - name: Build & Deploy
        run: |
          gcloud builds submit --config cloudbuild.yaml \
            --substitutions=SHORT_SHA=${{ github.sha }}
```

## Troubleshooting
- **Container won't start**: Check `gcloud run services logs dd-planner --region=australia-southeast1`
- **MongoDB connection fails**: Verify Atlas Network Access allows `0.0.0.0/0`
- **502 errors**: Increase `--timeout` or `--memory` in Cloud Run settings
- **Slow cold starts**: Set `--min-instances 1` to keep one instance warm (~$15/month extra)
