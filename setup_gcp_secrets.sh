#!/bin/bash
# ============================================================
# DD Planner — GCP Secrets & Config Setup
# ============================================================
#
# Run this ONCE before your first Cloud Run deployment.
# After this, Cloud Run's GitHub integration handles everything.
#
# USAGE:
#   1. Open terminal
#   2. Run: gcloud auth login
#   3. Run: bash setup_gcp_secrets.sh
#
# ============================================================

set -e

PROJECT_ID="dd-planner-494404"
REGION="australia-southeast1"
SERVICE_NAME="dd-planner"

echo ""
echo "============================================="
echo "  DD Planner — GCP Setup"
echo "  Project: $PROJECT_ID"
echo "============================================="
echo ""

# ---- Set Project ----
echo "[1/6] Setting GCP project..."
gcloud config set project $PROJECT_ID

# ---- Enable APIs ----
echo "[2/6] Enabling required APIs..."
gcloud services enable \
    run.googleapis.com \
    secretmanager.googleapis.com \
    --quiet
echo "  Done."

# ---- Create Secrets ----
echo "[3/6] Creating secrets in Secret Manager..."

create_secret() {
    local name=$1
    local value=$2
    if gcloud secrets describe $name --project=$PROJECT_ID 2>/dev/null; then
        echo "  $name — already exists, adding new version..."
        echo -n "$value" | gcloud secrets versions add $name --data-file=- --quiet
    else
        echo "  $name — creating..."
        echo -n "$value" | gcloud secrets create $name --data-file=- --quiet
    fi
}

SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)

create_secret "MONGO_URL" "mongodb+srv://ddplanner:%40DDplanner2026%21@cluster0.iy30moq.mongodb.net/resource_planner?retryWrites=true&w=majority"
create_secret "SECRET_KEY" "$SECRET_KEY"
create_secret "EMERGENT_LLM_KEY" "sk-emergent-8F6C7F8Be7324AaDa9"
create_secret "EXPORT_API_KEY" "0ulG5kuzP1NRFKk8kH4D1GM0jd7IgMfZECLnAFIO_zvHNDA8hk8QI5pB9NVPaHlB"
echo "  Done."

# ---- Grant Permissions ----
echo "[4/6] Granting Cloud Run access to secrets..."
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for secret in MONGO_URL SECRET_KEY EMERGENT_LLM_KEY EXPORT_API_KEY; do
    gcloud secrets add-iam-policy-binding $secret \
        --member="serviceAccount:$SA" \
        --role="roles/secretmanager.secretAccessor" \
        --quiet 2>/dev/null || true
done

# Also grant to Cloud Build service account (needed for GitHub-triggered builds)
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
for secret in MONGO_URL SECRET_KEY EMERGENT_LLM_KEY EXPORT_API_KEY; do
    gcloud secrets add-iam-policy-binding $secret \
        --member="serviceAccount:$CLOUDBUILD_SA" \
        --role="roles/secretmanager.secretAccessor" \
        --quiet 2>/dev/null || true
done
echo "  Done."

# ---- Update Cloud Run Service ----
echo "[5/6] Configuring Cloud Run service with secrets and settings..."

# Check if service exists
if gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)" 2>/dev/null; then
    echo "  Service exists — updating configuration..."
    gcloud run services update $SERVICE_NAME \
        --region $REGION \
        --port 8080 \
        --memory 1Gi \
        --cpu 1 \
        --min-instances 0 \
        --max-instances 3 \
        --timeout 300 \
        --set-env-vars "DB_NAME=resource_planner" \
        --set-secrets "MONGO_URL=MONGO_URL:latest,SECRET_KEY=SECRET_KEY:latest,EMERGENT_LLM_KEY=EMERGENT_LLM_KEY:latest,EXPORT_API_KEY=EXPORT_API_KEY:latest" \
        --quiet
    echo "  Done."
else
    echo "  Service not yet deployed. Secrets are ready — they'll be picked up on first deploy."
    echo ""
    echo "  When Cloud Run asks for configuration during GitHub setup, use:"
    echo "    Port: 8080"
    echo "    Memory: 1 GiB"
    echo "    CPU: 1"
    echo "    Environment variable: DB_NAME = resource_planner"
    echo "    Secrets: MONGO_URL, SECRET_KEY, EMERGENT_LLM_KEY, EXPORT_API_KEY"
fi

# ---- Verify ----
echo ""
echo "[6/6] Verification..."
echo "  Secrets created:"
gcloud secrets list --format="table(name)" --quiet 2>/dev/null | grep -E "MONGO_URL|SECRET_KEY|EMERGENT_LLM_KEY|EXPORT_API_KEY" || true

URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)" 2>/dev/null || echo "NOT YET DEPLOYED")

echo ""
echo "============================================="
echo "  SETUP COMPLETE!"
echo ""
echo "  Cloud Run URL: $URL"
echo ""
if [ "$URL" != "NOT YET DEPLOYED" ]; then
    echo "  Test it: curl $URL/health"
    echo "  Login:   $URL"
    echo "           Email: don@ddconsult.tech"
    echo "           Password: @Ddplanner2026"
else
    echo "  Next: Push code to GitHub — Cloud Run will"
    echo "  auto-build and deploy using the Dockerfile."
    echo "  The secrets are ready and will be picked up."
fi
echo "============================================="
