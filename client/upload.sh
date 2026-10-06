#!/usr/bin/env bash
# ==============================================================================
# NOAA GCS Portal - Upload CLI Script for Linux (Rocky 8/9, RHEL, Ubuntu, etc.)
# ==============================================================================
# Usage:
#   ./upload.sh <LOCAL_FILE> [REMOTE_DESTINATION_PREFIX]
#
# Examples:
#   ./upload.sh model_output.nc
#   ./upload.sh forecast.grib2 outputs/20261006/
#
# Environment variables (optional):
#   PORTAL_URL      Default: https://gcs-portal-bewk3ak7hq-ez.a.run.app
#   PORTAL_USER     Default: noaa-user
#   PORTAL_PASS     Default: NOAA-Portal-2026!
# ==============================================================================

set -eo pipefail

PORTAL_URL="${PORTAL_URL:-https://gcs-portal-bewk3ak7hq-ez.a.run.app}"
PORTAL_USER="${PORTAL_USER:-noaa-user}"
PORTAL_PASS="${PORTAL_PASS:-NOAA-Portal-2026!}"

LOCAL_FILE="$1"
DEST_PREFIX="$2"

if [ -z "$LOCAL_FILE" ]; then
  echo "Usage: $0 <local_file> [destination_prefix]"
  echo "Example: $0 data.nc outputs/"
  exit 1
fi

if [ ! -f "$LOCAL_FILE" ]; then
  echo "Error: File '$LOCAL_FILE' not found!"
  exit 1
fi

FILE_NAME=$(basename "$LOCAL_FILE")
FILE_SIZE=$(stat -c%s "$LOCAL_FILE" 2>/dev/null || stat -f%z "$LOCAL_FILE" 2>/dev/null)

# Clean destination prefix
if [ -n "$DEST_PREFIX" ]; then
  DEST_PREFIX="${DEST_PREFIX#/}"
  if [[ "$DEST_PREFIX" != */ ]]; then
    DEST_PREFIX="${DEST_PREFIX}/"
  fi
  TARGET_PATH="${DEST_PREFIX}${FILE_NAME}"
else
  TARGET_PATH="${FILE_NAME}"
fi

echo "=========================================================="
echo " NOAA GCS Portal - File Upload"
echo "=========================================================="
echo "Portal:       $PORTAL_URL"
echo "Username:     $PORTAL_USER"
echo "Local File:   $LOCAL_FILE ($(numfmt --to=iec-i --suffix=B "$FILE_SIZE" 2>/dev/null || echo "$FILE_SIZE bytes"))"
echo "Destination:  gs://mb-noaa-eu/$TARGET_PATH"
echo "=========================================================="

COOKIE_JAR=$(mktemp)
trap 'rm -f "$COOKIE_JAR"' EXIT

# Step 1: Authenticate with portal
echo "[1/3] Authenticating..."
LOGIN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -c "$COOKIE_JAR" \
  -d "username=${PORTAL_USER}&password=${PORTAL_PASS}&next=/" \
  "${PORTAL_URL}/login")

if [ "$LOGIN_STATUS" -ne 200 ] && [ "$LOGIN_STATUS" -ne 302 ] && [ "$LOGIN_STATUS" -ne 303 ]; then
  echo "Error: Login failed! Received HTTP $LOGIN_STATUS from portal."
  exit 1
fi
echo "      Authenticated successfully."

# Step 2: Request signed upload URL (supports any file size up to 5 TB)
echo "[2/3] Requesting secure direct upload URL..."
RESPONSE=$(curl -s -b "$COOKIE_JAR" \
  -X POST "${PORTAL_URL}/api/upload-url" \
  -H "Content-Type: application/json" \
  -d "{\"path\": \"${TARGET_PATH}\", \"content_type\": \"application/octet-stream\"}")

# Extract upload URL using python (built-in on Rocky 8 & 9) or grep/sed fallback
UPLOAD_URL=$(python3 -c "import sys, json; print(json.load(sys.stdin).get('upload_url', ''))" <<< "$RESPONSE" 2>/dev/null || true)

if [ -z "$UPLOAD_URL" ]; then
  echo "Error: Failed to obtain upload URL from portal. Response was:"
  echo "$RESPONSE"
  exit 1
fi
echo "      Secure upload URL acquired."

# Step 3: Direct PUT transfer to GCS with native curl progress bar
echo "[3/3] Uploading file directly to Google Cloud Storage..."
HTTP_STATUS=$(curl -# -X PUT \
  -H "Content-Type: application/octet-stream" \
  -T "$LOCAL_FILE" \
  -w "%{http_code}" \
  -o /dev/null \
  "$UPLOAD_URL")

if [ "$HTTP_STATUS" -eq 200 ]; then
  echo ""
  echo "=========================================================="
  echo " Upload Succeeded!"
  echo " File is now available at gs://mb-noaa-eu/$TARGET_PATH"
  echo " View in portal: ${PORTAL_URL}/?prefix=${DEST_PREFIX}"
  echo "=========================================================="
else
  echo ""
  echo "Error: Upload failed with HTTP status $HTTP_STATUS"
  exit 1
fi
