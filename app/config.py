import os
import secrets
import json

PROJECT_ID = os.environ.get("PROJECT_ID", "mb-development-447000")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "mb-noaa-eu")
SERVICE_ACCOUNT_EMAIL = os.environ.get(
    "SERVICE_ACCOUNT_EMAIL",
    "gcs-portal-sa@mb-development-447000.iam.gserviceaccount.com"
)

# Authentication Configuration
DEFAULT_USERNAME = os.environ.get("PORTAL_USERNAME", "noaa-user")
DEFAULT_PASSWORD = os.environ.get("PORTAL_PASSWORD", "NOAA-Portal-2026!")

# Multi-user support via JSON if provided
USERS_JSON = os.environ.get("PORTAL_USERS_JSON")
if USERS_JSON:
    try:
        USERS = json.loads(USERS_JSON)
    except Exception:
        USERS = {DEFAULT_USERNAME: DEFAULT_PASSWORD}
else:
    USERS = {DEFAULT_USERNAME: DEFAULT_PASSWORD}

# Session cookie configuration
SECRET_KEY = os.environ.get("SECRET_KEY", "noaa-portal-secret-key-salt-2026-production")
SESSION_COOKIE_NAME = "gcs_portal_session"
SESSION_MAX_AGE = int(os.environ.get("SESSION_MAX_AGE", "86400"))  # 24 hours
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() in ("true", "1", "yes")
