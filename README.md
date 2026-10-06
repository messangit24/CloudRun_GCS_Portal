# NOAA GCS Secure Web Portal

An end-to-end, production-grade web portal deployed on **Google Cloud Run** in project `mb-development-447000`. It allows authenticated end users to securely browse, upload, download, and manage files in Google Cloud Storage bucket `gs://mb-noaa-eu` without requiring GCP IAM user accounts or Google Workspace identities.

---

## 🌟 Key Features

- **Password Authentication**:
  - Secure login portal with constant-time password verification (`hmac.compare_digest`).
  - Cryptographically signed sessions using HMAC-SHA256 in `HttpOnly`, `SameSite=Lax`, `Secure` cookies.
  - Multi-user configurable via environment variables (`PORTAL_USERNAME`, `PORTAL_PASSWORD`, `PORTAL_USERS_JSON`).
  - Automatic session expiration and clean logout.

- **High-Speed Direct Uploads & Downloads**:
  - **Direct GCS V4 Signed URLs**: Files are transferred directly between the client's browser and Google Cloud Storage edge network (`https://storage.googleapis.com`).
  - **Zero Payload Limits**: Handles multi-gigabyte scientific datasets (e.g. 21GB+ NetCDF `.nc` or `.zarr` forecast directories) without Cloud Run request size bottlenecks (32MB) or memory pressure.
  - **Real-Time Progress Tracking**: Granular upload progress bars (0% - 100%), transfer speeds, and status updates via `XMLHttpRequest` progress events.
  - **Streaming Fallback**: Server-side proxied streaming download (`/api/stream-download`) and multipart upload (`/api/upload-direct`) fallback endpoints.

- **Modern Explorer UI**:
  - Intuitive breadcrumb directory navigation (`root / outputs / ...`).
  - Instant client-side search filtering by filename and extension.
  - Contextual file-type icons (NetCDF, Zarr, CSV, JSON, logs, images, archives).
  - Human-readable file sizes and timestamps.
  - In-browser file preview for text, logs, JSON, CSV, and markdown datasets.
  - One-click copy for 1-hour signed direct download links.
  - Subfolder creation and item deletion with confirmation modals.

- **Enterprise Security**:
  - Dedicated service account: `gcs-portal-sa@mb-development-447000.iam.gserviceaccount.com`.
  - Scoped storage permissions (`roles/storage.objectUser` on `gs://mb-noaa-eu`).
  - IAM credentials signing (`roles/iam.serviceAccountTokenCreator`) eliminates the need to store long-lived service account key files in the container.
  - Non-root user in lightweight container image (`python:3.12-slim`).

---

## 🏗️ Architecture

```
                                      +---------------------------------------------+
                                      |                 Google Cloud                |
                                      |                                             |
[ End User Browser ]                  |  +--------------------+                     |
     |                                |  | Cloud Run          |                     |
     | 1. Authenticate (Password)     |  | "gcs-portal"       |                     |
     +---------------------------------->| (FastAPI + Uvicorn)|                     |
     | 2. Set HttpOnly Session Cookie |  +---------+----------+                     |
     |<----------------------------------+         |                                |
     |                                             | 3. List / Sign V4 URLs         |
     | 4. Direct Upload / Download (Signed URLs)   |    via IAM Credentials API     |
     |                                             v                                |
     +====================================> [ GCS Bucket: gs://mb-noaa-eu ]         |
                                                   - outputs/                       |
                                                   - NetCDF & Zarr datasets         |
                                      +---------------------------------------------+
```

---

## ⚙️ Configuration (Environment Variables)

| Variable | Description | Default |
| :--- | :--- | :--- |
| `PROJECT_ID` | GCP Project hosting the service and bucket | `mb-development-447000` |
| `BUCKET_NAME` | Target GCS bucket name | `mb-noaa-eu` |
| `SERVICE_ACCOUNT_EMAIL` | Service account used by Cloud Run | `gcs-portal-sa@mb-development-447000.iam.gserviceaccount.com` |
| `PORTAL_USERNAME` | Default login username | `noaa-user` |
| `PORTAL_PASSWORD` | Default login password | `NOAA-Portal-2026!` |
| `PORTAL_USERS_JSON` | Optional JSON string for multiple users: `{"user1": "pass1", "user2": "pass2"}` | *(Unset)* |
| `SECRET_KEY` | HMAC secret key used for signing session cookies | Generated random string |
| `SESSION_MAX_AGE` | Session validity duration in seconds | `86400` (24 hours) |
| `COOKIE_SECURE` | Enforce HTTPS secure cookies | `true` |

---

## 🚀 Deployment

### Automated Deployment Script
Deploy or update the Cloud Run service in a single command:

```bash
./deploy.sh
```

### Custom Credentials at Deploy Time
```bash
PORTAL_USERNAME="meteorologist" \
PORTAL_PASSWORD="MyStrongSecretPassword2026!" \
REGION="europe-west4" \
./deploy.sh
```

### Manual `gcloud` Command
```bash
gcloud run deploy gcs-portal \
  --source . \
  --project mb-development-447000 \
  --region europe-west4 \
  --service-account gcs-portal-sa@mb-development-447000.iam.gserviceaccount.com \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 3600 \
  --set-env-vars "PROJECT_ID=mb-development-447000,BUCKET_NAME=mb-noaa-eu,SERVICE_ACCOUNT_EMAIL=gcs-portal-sa@mb-development-447000.iam.gserviceaccount.com,PORTAL_USERNAME=noaa-user,PORTAL_PASSWORD=NOAA-Portal-2026!,COOKIE_SECURE=true"
```

---

## 💻 Local Development & Testing

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run local development server:
```bash
export PROJECT_ID=mb-development-447000
export BUCKET_NAME=mb-noaa-eu
export COOKIE_SECURE=false
uvicorn app.main:app --reload --port 8080
```

3. Open `http://localhost:8080` and log in with `noaa-user` / `NOAA-Portal-2026!`.
