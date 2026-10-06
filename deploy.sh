#!/usr/bin/env bash
set -e

SERVICE_NAME="${SERVICE_NAME:-gcs-portal}"
PROJECT_ID="${PROJECT_ID:-mb-development-447000}"
REGION="${REGION:-europe-west4}"
BUCKET_NAME="${BUCKET_NAME:-mb-noaa-eu}"
SERVICE_ACCOUNT="gcs-portal-sa@mb-development-447000.iam.gserviceaccount.com"

PORTAL_USERNAME="${PORTAL_USERNAME:-noaa-user}"
PORTAL_PASSWORD="${PORTAL_PASSWORD:-NOAA-Portal-2026!}"
SECRET_KEY="${SECRET_KEY:-$(openssl rand -hex 32 2>/dev/null || echo 'gcs-portal-super-secret-key-salt-2026')}"

echo "=========================================================="
echo " Deploying NOAA GCS UI Portal to Google Cloud Run"
echo "=========================================================="
echo "Project:         $PROJECT_ID"
echo "Region:          $REGION"
echo "Service Name:    $SERVICE_NAME"
echo "Service Account: $SERVICE_ACCOUNT"
echo "Target Bucket:   gs://$BUCKET_NAME"
echo "Portal User:     $PORTAL_USERNAME"
echo "=========================================================="

gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --service-account "$SERVICE_ACCOUNT" \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 3600 \
  --concurrency 80 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars "^:^PROJECT_ID=${PROJECT_ID}:BUCKET_NAME=${BUCKET_NAME}:SERVICE_ACCOUNT_EMAIL=${SERVICE_ACCOUNT}:PORTAL_USERNAME=${PORTAL_USERNAME}:PORTAL_PASSWORD=${PORTAL_PASSWORD}:SECRET_KEY=${SECRET_KEY}:COOKIE_SECURE=true" \
  --quiet

URL=$(gcloud run services describe "$SERVICE_NAME" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')

echo ""
echo "=========================================================="
echo " Deployment Successfully Completed!"
echo "=========================================================="
echo "Portal URL:  $URL"
echo "Username:    $PORTAL_USERNAME"
echo "Password:    $PORTAL_PASSWORD"
echo "=========================================================="
