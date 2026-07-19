#!/bin/bash
# ============================================================
# DD Planner — Full GCP Deployment (run in GCP Cloud Shell)
# ============================================================
# Paste this ENTIRE block into GCP Cloud Shell and press Enter.
# It does everything: clone, secrets, build, deploy.
# ============================================================

set -e

PROJECT_ID="dd-planner-494404"
REGION="australia-southeast1"
SERVICE_NAME="dd-planner"
REPO_URL="https://github.com/DD-Consult/Project-planner.git"
BRANCH="Main_V2"

echo ""
echo "============================================="
echo "  DD Planner — Full GCP Deployment"
echo "============================================="
echo ""

# ---- Set Project ----
echo "[1/8] Setting project..."
gcloud config set project $PROJECT_ID

# ---- Enable APIs ----
echo "[2/8] Enabling APIs..."
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    --quiet
echo "  Done."

# ---- Create Artifact Registry ----
echo "[3/8] Creating Docker repository..."
gcloud artifacts repositories describe $SERVICE_NAME --location=$REGION 2>/dev/null || \
    gcloud artifacts repositories create $SERVICE_NAME \
        --repository-format=docker \
        --location=$REGION \
        --description="DD Planner" \
        --quiet
echo "  Done."

# ---- Create Secrets ----
echo "[4/8] Creating secrets..."

create_secret() {
    local name=$1
    local value=$2
    if gcloud secrets describe $name 2>/dev/null; then
        echo -n "$value" | gcloud secrets versions add $name --data-file=- --quiet
        echo "  $name updated."
    else
        echo -n "$value" | gcloud secrets create $name --data-file=- --quiet
        echo "  $name created."
    fi
}

SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

create_secret "MONGO_URL" "mongodb+srv://ddplanner:%40DDplanner2026%21@cluster0.iy30moq.mongodb.net/resource_planner?retryWrites=true&w=majority"
create_secret "SECRET_KEY" "$SECRET_KEY"
create_secret "EMERGENT_LLM_KEY" "sk-emergent-8F6C7F8Be7324AaDa9"
create_secret "EXPORT_API_KEY" "0ulG5kuzP1NRFKk8kH4D1GM0jd7IgMfZECLnAFIO_zvHNDA8hk8QI5pB9NVPaHlB"

# ---- Grant Permissions ----
echo "[5/8] Granting permissions..."
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

for SA in "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" "${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"; do
    for secret in MONGO_URL SECRET_KEY EMERGENT_LLM_KEY EXPORT_API_KEY; do
        gcloud secrets add-iam-policy-binding $secret \
            --member="serviceAccount:$SA" \
            --role="roles/secretmanager.secretAccessor" \
            --quiet 2>/dev/null || true
    done
done
echo "  Done."

# ---- Clone & Build ----
echo "[6/8] Cloning repo and building Docker image (~5 min)..."
cd ~
rm -rf Project-planner
git clone --branch $BRANCH $REPO_URL
cd Project-planner

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}/${SERVICE_NAME}:latest"

gcloud builds submit --tag "$IMAGE" --timeout=900 --quiet
echo "  Image built: $IMAGE"

# ---- Deploy ----
echo "[7/8] Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image "$IMAGE" \
    --region $REGION \
    --platform managed \
    --port 8080 \
    --memory 1Gi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 3 \
    --timeout 300 \
    --allow-unauthenticated \
    --set-env-vars "DB_NAME=resource_planner" \
    --set-secrets "MONGO_URL=MONGO_URL:latest,SECRET_KEY=SECRET_KEY:latest,EMERGENT_LLM_KEY=EMERGENT_LLM_KEY:latest,EXPORT_API_KEY=EXPORT_API_KEY:latest" \
    --quiet

# ---- Done ----
echo "[8/8] Verifying..."
URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

sleep 5
HEALTH=$(curl -s "$URL/health" 2>&1 || echo "waiting for startup...")

echo ""
echo "============================================="
echo ""
echo "  YOUR APP IS LIVE!"
echo ""
echo "  URL: $URL"
echo ""
echo "  Login:"
echo "    Email:    don@ddconsult.tech"
echo "    Password: @Ddplanner2026"
echo ""
echo "  Health: $HEALTH"
echo ""
echo "============================================="
