#!/usr/bin/env python3
"""
NOAA GCS Portal - Zero-Dependency Python Upload Script
Compatible with Python 3.6+ on Rocky Linux 8, Rocky Linux 9, RHEL, Fedora, Debian, Ubuntu.
Uses only standard library (urllib, json, sys, os).

Usage:
    python3 upload.py <local_file> [destination_prefix]

Example:
    python3 upload.py aigfs_output.nc outputs/20261006/
"""

import sys
import os
import json
import urllib.request
import urllib.parse
import http.cookiejar

PORTAL_URL = os.environ.get("PORTAL_URL", "https://gcs-portal-bewk3ak7hq-ez.a.run.app")
PORTAL_USER = os.environ.get("PORTAL_USER", "noaa-user")
PORTAL_PASS = os.environ.get("PORTAL_PASS", "NOAA-Portal-2026!")


def format_bytes(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


class ProgressReader:
    """Wrapper around file object that prints upload progress in the terminal."""
    def __init__(self, filepath):
        self._file = open(filepath, 'rb')
        self._total = os.path.getsize(filepath)
        self._read = 0

    def read(self, size=-1):
        chunk = self._file.read(size)
        self._read += len(chunk)
        percent = (self._read / self._total) * 100 if self._total > 0 else 100
        bar_len = 30
        filled = int(bar_len * self._read / self._total) if self._total > 0 else bar_len
        bar = '=' * filled + '-' * (bar_len - filled)
        sys.stdout.write(f"\rUploading: [{bar}] {percent:.1f}% ({format_bytes(self._read)}/{format_bytes(self._total)})")
        sys.stdout.flush()
        return chunk

    def __len__(self):
        return self._total

    def close(self):
        self._file.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 upload.py <local_file> [destination_prefix]")
        print("Example: python3 upload.py model.nc outputs/")
        sys.exit(1)

    local_file = sys.argv[1]
    dest_prefix = sys.argv[2] if len(sys.argv) > 2 else ""

    if not os.path.isfile(local_file):
        print(f"Error: File '{local_file}' does not exist.")
        sys.exit(1)

    file_name = os.path.basename(local_file)
    file_size = os.path.getsize(local_file)

    if dest_prefix:
        dest_prefix = dest_prefix.strip("/") + "/"
        target_path = f"{dest_prefix}{file_name}"
    else:
        target_path = file_name

    print("=" * 60)
    print(" NOAA GCS Portal - Python CLI Upload")
    print("=" * 60)
    print(f"Portal:      {PORTAL_URL}")
    print(f"User:        {PORTAL_USER}")
    print(f"Local File:  {local_file} ({format_bytes(file_size)})")
    print(f"Target:      gs://mb-noaa-eu/{target_path}")
    print("=" * 60)

    # Setup session cookie jar
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    # 1. Login
    print("[1/3] Authenticating with portal...")
    login_data = urllib.parse.urlencode({
        "username": PORTAL_USER,
        "password": PORTAL_PASS,
        "next": "/"
    }).encode("utf-8")

    req = urllib.request.Request(f"{PORTAL_URL}/login", data=login_data, method="POST")
    try:
        with opener.open(req) as resp:
            if resp.status not in (200, 302, 303):
                print(f"Login failed: HTTP {resp.status}")
                sys.exit(1)
    except Exception as e:
        print(f"Authentication error: {e}")
        sys.exit(1)
    print("      Authenticated successfully.")

    # 2. Get Signed Upload URL
    print("[2/3] Requesting signed upload URL...")
    payload = json.dumps({
        "path": target_path,
        "content_type": "application/octet-stream"
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{PORTAL_URL}/api/upload-url",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with opener.open(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            upload_url = data.get("upload_url")
    except Exception as e:
        print(f"Failed to obtain upload URL: {e}")
        sys.exit(1)
    print("      Signed upload URL obtained.")

    # 3. Direct PUT to GCS
    print("[3/3] Uploading file to Google Cloud Storage...")
    progress_stream = ProgressReader(local_file)
    put_req = urllib.request.Request(
        upload_url,
        data=progress_stream,
        headers={
            "Content-Type": "application/octet-stream",
            "Content-Length": str(file_size)
        },
        method="PUT"
    )

    try:
        with urllib.request.urlopen(put_req) as resp:
            print("\n")
            if resp.status in (200, 201):
                print("=" * 60)
                print(" Upload Completed Successfully!")
                print(f" File: gs://mb-noaa-eu/{target_path}")
                print(f" View: {PORTAL_URL}/?prefix={dest_prefix}")
                print("=" * 60)
            else:
                print(f"Upload failed with HTTP status: {resp.status}")
                sys.exit(1)
    except Exception as e:
        print(f"\nUpload error: {e}")
        sys.exit(1)
    finally:
        progress_stream.close()


if __name__ == "__main__":
    main()
