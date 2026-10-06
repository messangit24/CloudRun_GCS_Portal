import os
import mimetypes
import math
from datetime import timedelta
from typing import Dict, Any, List, Optional, Tuple

import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.cloud import storage

from app.config import PROJECT_ID, BUCKET_NAME, SERVICE_ACCOUNT_EMAIL

# Additional MIME types for scientific / weather datasets
mimetypes.add_type("application/x-netcdf", ".nc")
mimetypes.add_type("application/x-netcdf", ".nc4")
mimetypes.add_type("application/x-hdf5", ".h5")
mimetypes.add_type("application/x-hdf5", ".hdf5")
mimetypes.add_type("application/x-grib", ".grb")
mimetypes.add_type("application/x-grib2", ".grib2")
mimetypes.add_type("application/x-zarr", ".zarr")


def format_size(bytes_num: int) -> str:
    """Formats raw bytes into a human-readable size string."""
    if bytes_num is None or bytes_num == 0:
        return "0 B"
    sizes = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = int(math.floor(math.log(bytes_num, 1024)))
    p = math.pow(1024, i)
    s = round(bytes_num / p, 2)
    return f"{s} {sizes[i]}"


class StorageService:
    def __init__(self):
        self.project_id = PROJECT_ID
        self.bucket_name = BUCKET_NAME
        self.sa_email = SERVICE_ACCOUNT_EMAIL
        self._client: Optional[storage.Client] = None
        self._credentials = None

    def _get_credentials(self):
        """Resolves valid credentials for GCP, supporting Cloud Run ADC and local development."""
        try:
            creds, _ = google.auth.default()
            if not creds.valid:
                req = Request()
                creds.refresh(req)
            self._credentials = creds
            return creds
        except Exception:
            # Fallback for local development if gcloud CLI is available
            try:
                import subprocess
                token = subprocess.check_output(
                    ["gcloud", "auth", "print-access-token"],
                    stderr=subprocess.DEVNULL
                ).decode().strip()
                creds = Credentials(token)
                self._credentials = creds
                return creds
            except Exception as e:
                raise RuntimeError(f"Unable to initialize Google Cloud credentials: {e}")

    def get_client(self) -> storage.Client:
        """Returns or creates a cached storage.Client."""
        creds = self._get_credentials()
        # Always re-init or check client to ensure fresh tokens
        return storage.Client(project=self.project_id, credentials=creds)

    def get_bucket(self):
        client = self.get_client()
        return client.bucket(self.bucket_name)

    def _ensure_token(self) -> str:
        """Ensures access token is refreshed and returns it."""
        creds = self._get_credentials()
        req = Request()
        if hasattr(creds, "refresh"):
            try:
                creds.refresh(req)
            except Exception:
                pass
        return getattr(creds, "token", None)

    def list_files(self, prefix: str = "") -> Dict[str, Any]:
        """
        Lists folders and files under a given prefix using GCS delimiter='/' for directory simulation.
        """
        if prefix and not prefix.endswith("/"):
            prefix = prefix + "/"
        
        # Avoid leading slash in GCS prefixes
        prefix = prefix.lstrip("/")

        client = self.get_client()
        bucket = client.bucket(self.bucket_name)

        iterator = client.list_blobs(bucket, prefix=prefix, delimiter="/")
        
        # Blobs immediately under prefix
        items = []
        total_size = 0
        total_files = 0

        for blob in iterator:
            # Skip the directory placeholder itself
            if blob.name == prefix:
                continue
            
            # Extract simple name relative to current prefix
            file_name = blob.name[len(prefix):] if prefix else blob.name
            size = blob.size or 0
            total_size += size
            total_files += 1

            mime_type, _ = mimetypes.guess_type(blob.name)
            if not mime_type:
                mime_type = "application/octet-stream"

            items.append({
                "name": file_name,
                "full_path": blob.name,
                "size": size,
                "size_formatted": format_size(size),
                "updated": blob.updated.isoformat() if blob.updated else None,
                "content_type": blob.content_type or mime_type,
                "is_dir": False
            })

        # Subfolders
        subfolders = []
        for p in iterator.prefixes:
            # Strip trailing slash for display name
            dir_name = p[len(prefix):].rstrip("/") if prefix else p.rstrip("/")
            subfolders.append({
                "name": dir_name,
                "full_path": p,
                "is_dir": True
            })

        # Calculate parent path for navigation
        parent_path = None
        if prefix:
            clean_p = prefix.rstrip("/")
            if "/" in clean_p:
                parent_path = clean_p.rsplit("/", 1)[0] + "/"
            else:
                parent_path = ""

        # Build breadcrumb trail
        breadcrumbs = [{"name": "root", "path": ""}]
        if prefix:
            parts = [p for p in prefix.rstrip("/").split("/") if p]
            accum = ""
            for part in parts:
                accum += part + "/"
                breadcrumbs.append({"name": part, "path": accum})

        return {
            "current_path": prefix,
            "parent_path": parent_path,
            "breadcrumbs": breadcrumbs,
            "folders": sorted(subfolders, key=lambda x: x["name"].lower()),
            "files": sorted(items, key=lambda x: x["name"].lower()),
            "total_files": total_files,
            "total_size": total_size,
            "total_size_formatted": format_size(total_size),
            "bucket": self.bucket_name
        }

    def generate_download_url(self, blob_path: str, expiration_minutes: int = 60) -> str:
        """Generates a v4 signed URL for GET download."""
        token = self._ensure_token()
        client = self.get_client()
        bucket = client.bucket(self.bucket_name)
        blob = bucket.blob(blob_path)

        filename = os.path.basename(blob_path.rstrip("/"))
        response_disposition = f'attachment; filename="{filename}"'

        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
            response_disposition=response_disposition,
            service_account_email=self.sa_email,
            access_token=token
        )

    def generate_upload_url(
        self,
        blob_path: str,
        content_type: str = "application/octet-stream",
        expiration_minutes: int = 30
    ) -> str:
        """Generates a v4 signed URL for direct browser PUT upload."""
        token = self._ensure_token()
        client = self.get_client()
        bucket = client.bucket(self.bucket_name)
        blob = bucket.blob(blob_path)

        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="PUT",
            content_type=content_type,
            service_account_email=self.sa_email,
            access_token=token
        )

    def stream_download(self, blob_path: str, chunk_size: int = 1024 * 1024):
        """Generator that yields file chunks directly from GCS."""
        client = self.get_client()
        bucket = client.bucket(self.bucket_name)
        blob = bucket.get_blob(blob_path)
        if not blob:
            raise FileNotFoundError(f"Object {blob_path} not found")

        with blob.open("rb") as f:
            while chunk := f.read(chunk_size):
                yield chunk

    def get_blob_metadata(self, blob_path: str) -> Optional[Dict[str, Any]]:
        client = self.get_client()
        bucket = client.bucket(self.bucket_name)
        blob = bucket.get_blob(blob_path)
        if not blob:
            return None
        return {
            "name": blob.name,
            "size": blob.size,
            "size_formatted": format_size(blob.size or 0),
            "content_type": blob.content_type,
            "updated": blob.updated.isoformat() if blob.updated else None
        }

    def upload_file_direct(self, blob_path: str, file_obj, content_type: str = "application/octet-stream"):
        client = self.get_client()
        bucket = client.bucket(self.bucket_name)
        blob = bucket.blob(blob_path)
        blob.upload_from_file(file_obj, content_type=content_type)
        return {
            "name": blob.name,
            "size": blob.size,
            "size_formatted": format_size(blob.size or 0)
        }

    def create_folder(self, folder_path: str) -> str:
        """Creates an empty 0-byte directory marker in GCS."""
        folder_path = folder_path.strip("/")
        if not folder_path:
            raise ValueError("Folder name cannot be empty")
        folder_path = folder_path + "/"
        
        client = self.get_client()
        bucket = client.bucket(self.bucket_name)
        blob = bucket.blob(folder_path)
        blob.upload_from_string(b"", content_type="application/x-directory")
        return folder_path

    def delete_item(self, path: str) -> int:
        """Deletes a file or directory prefix. Returns count of deleted blobs."""
        client = self.get_client()
        bucket = client.bucket(self.bucket_name)

        if path.endswith("/"):
            # Delete directory prefix contents
            blobs = list(client.list_blobs(bucket, prefix=path))
            if blobs:
                bucket.delete_blobs(blobs)
                return len(blobs)
            return 0
        else:
            blob = bucket.get_blob(path)
            if blob:
                blob.delete()
                return 1
            return 0

    def preview_text(self, blob_path: str, max_bytes: int = 512 * 1024) -> Dict[str, Any]:
        """Reads a preview of a text/JSON/CSV/code file up to max_bytes."""
        client = self.get_client()
        bucket = client.bucket(self.bucket_name)
        blob = bucket.get_blob(blob_path)
        if not blob:
            raise FileNotFoundError(f"Object {blob_path} not found")

        size = blob.size or 0
        if size > max_bytes:
            data = blob.download_as_bytes(start=0, end=max_bytes)
            truncated = True
        else:
            data = blob.download_as_bytes()
            truncated = False

        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError:
            try:
                content = data.decode("latin-1")
            except Exception:
                content = "[Binary content - cannot display text preview]"

        return {
            "name": os.path.basename(blob.name),
            "full_path": blob.name,
            "size": size,
            "size_formatted": format_size(size),
            "content": content,
            "truncated": truncated,
            "content_type": blob.content_type
        }


storage_service = StorageService()
