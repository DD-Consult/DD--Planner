#!/bin/bash
# ============================================================
# DD Planner — One-Click GCP Cloud Run Deployment Script
# ============================================================
# 
# PREREQUISITES (you only need to do these once):
#   1. Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install
#   2. Run: gcloud auth login  (logs in via browser)
#   3. Clone your GitHub repo and cd into it
#   4. Run this script: bash deploy_to_gcp.sh
#
# ============================================================

set -e  # Stop on any error

# ---- Configuration ----
PROJECT_ID="dd-planner-494404"
REGION="australia-southeast1"
SERVICE_NAME="dd-planner"
REPO_NAME="dd-planner"

# MongoDB Atlas (your cluster — already migrated)
MONGO_URL="mongodb+srv://ddplanner:%40DDplanner2026%21@cluster0.iy30moq.mongodb.net/resource_planner?retryWrites=true&w=majority"

# Emergent LLM Key (for AI features)
EMERGENT_LLM_KEY="sk-emergent-8F6C7F8Be7324AaDa9"

# Export API Key
EXPORT_API_KEY="0ulG5kuzP1NRFKk8kH4D1GM0jd7IgMfZECLnAFIO_zvHNDA8hk8QI5pB9NVPaHlB"

# ---- Helper ----
echo_step() {
    echo ""
    echo "========================================"
    echo "  STEP: $1"
    echo "========================================"
}

echo ""
echo "============================================="
echo "  DD Planner — GCP Cloud Run Deployment"
echo "  Project: $PROJECT_ID"
echo "  Region:  $REGION"
echo "============================================="
echo ""

# ---- Step 1: Set GCP Project ----
echo_step "Setting GCP project"
gcloud config set project $PROJECT_ID
echo "Project set to $PROJECT_ID"

# ---- Step 2: Enable Required APIs ----
echo_step "Enabling GCP APIs (this may take a minute)"
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    --quiet
echo "APIs enabled."

# ---- Step 3: Create Artifact Registry (if not exists) ----
echo_step "Creating Artifact Registry repository"
if gcloud artifacts repositories describe $REPO_NAME --location=$REGION --format="value(name)" 2>/dev/null; then
    echo "Repository already exists, skipping."
else
    gcloud artifacts repositories create $REPO_NAME \
        --repository-format=docker \
        --location=$REGION \
        --description="DD Planner Docker images" \
        --quiet
    echo "Repository created."
fi

# ---- Step 4: Create Secrets in Secret Manager ----
echo_step "Setting up Secret Manager"

create_or_update_secret() {
    local name=$1
    local value=$2
    if gcloud secrets describe $name --project=$PROJECT_ID 2>/dev/null; then
        echo "  Secret '$name' exists — updating..."
        echo -n "$value" | gcloud secrets versions add $name --data-file=- --quiet
    else
        echo "  Creating secret '$name'..."
        echo -n "$value" | gcloud secrets create $name --data-file=- --quiet
    fi
}

# Generate a secure SECRET_KEY
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)

create_or_update_secret "MONGO_URL" "$MONGO_URL"
create_or_update_secret "SECRET_KEY" "$SECRET_KEY"
create_or_update_secret "EMERGENT_LLM_KEY" "$EMERGENT_LLM_KEY"
create_or_update_secret "EXPORT_API_KEY" "$EXPORT_API_KEY"

echo "Secrets configured."

# ---- Step 5: Grant Cloud Run access to secrets ----
echo_step "Granting Cloud Run access to secrets"
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for secret in MONGO_URL SECRET_KEY EMERGENT_LLM_KEY EXPORT_API_KEY; do
    gcloud secrets add-iam-policy-binding $secret \
        --member="serviceAccount:$SA" \
        --role="roles/secretmanager.secretAccessor" \
        --quiet 2>/dev/null || true
done
echo "Permissions granted to $SA"

# ---- Step 6: Build & Push Docker Image ----
echo_step "Building Docker image via Cloud Build (this takes 3-5 minutes)"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:latest"

gcloud builds submit \
    --tag "$IMAGE" \
    --timeout=600 \
    --quiet

echo "Image built and pushed: $IMAGE"

# ---- Step 7: Deploy to Cloud Run ----
echo_step "Deploying to Cloud Run"
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

# ---- Step 8: Get URL & Verify ----
echo_step "Deployment complete!"
URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo ""
echo "============================================="
echo "  YOUR APP IS LIVE!"
echo "  URL: $URL"
echo "============================================="
echo ""
echo "Quick verification:"
echo "  Health check: curl $URL/health"
echo "  Login:        Open $URL in your browser"
echo "                Email: don@ddconsult.tech"
echo "                Password: @Ddplanner2026"
echo ""
echo "To set up a custom domain later, run:"
echo "  gcloud run domain-mappings create --service $SERVICE_NAME --region $REGION --domain YOUR_DOMAIN"
echo ""

# Auto health check
echo "Running health check..."
sleep 5
HEALTH=$(curl -s "$URL/health" 2>&1)
echo "Health check response: $HEALTH"
echo ""
echo "Done! Your DD Planner is now running on GCP Cloud Run."
