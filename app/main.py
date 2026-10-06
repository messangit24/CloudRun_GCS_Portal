import os
from typing import Optional
from pydantic import BaseModel

from fastapi import (
    FastAPI,
    Request,
    Form,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Query,
    status
)
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import (
    PROJECT_ID,
    BUCKET_NAME,
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE,
    COOKIE_SECURE
)
from app.auth import (
    verify_credentials,
    create_session_token,
    get_current_user_from_request,
    require_auth_api
)
from app.storage import storage_service

app = FastAPI(
    title="NOAA GCS Data Portal",
    description="Secure UI Portal for Cloud Storage Access",
    version="1.0.0"
)

# Static files and templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# Request models
class UploadUrlRequest(BaseModel):
    path: str
    content_type: Optional[str] = "application/octet-stream"


class CreateFolderRequest(BaseModel):
    path: str


class DeleteItemRequest(BaseModel):
    path: str


# ================= PAGE ROUTES =================

@app.get("/health")
@app.get("/api/health")
@app.get("/healthz")
async def health_check():
    """Health check endpoint for Cloud Run."""
    return {"status": "healthy", "bucket": BUCKET_NAME, "project": PROJECT_ID}


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/"):
    user = get_current_user_from_request(request)
    if user:
        return RedirectResponse(url=next, status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"next": next, "error": None, "bucket_name": BUCKET_NAME}
    )


@app.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/")
):
    if verify_credentials(username.strip(), password):
        token = create_session_token(username.strip())
        response = RedirectResponse(url=next if next else "/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            max_age=SESSION_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=COOKIE_SECURE
        )
        return response

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "next": next,
            "error": "Invalid username or password.",
            "bucket_name": BUCKET_NAME
        },
        status_code=status.HTTP_401_UNAUTHORIZED
    )


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE
    )
    return response


@app.get("/", response_class=HTMLResponse)
async def portal_page(request: Request):
    user = get_current_user_from_request(request)
    if not user:
        target = str(request.url.path)
        if request.url.query:
            target += f"?{request.url.query}"
        return RedirectResponse(url=f"/login?next={target}", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        request=request,
        name="portal.html",
        context={
            "username": user,
            "bucket_name": BUCKET_NAME,
            "project_id": PROJECT_ID
        }
    )


# ================= REST API ENDPOINTS =================

@app.get("/api/me")
async def get_current_user_info(user: str = Depends(require_auth_api)):
    return {
        "username": user,
        "bucket": BUCKET_NAME,
        "project": PROJECT_ID
    }


@app.get("/api/files")
async def list_files_endpoint(
    prefix: str = Query("", description="Folder path prefix"),
    user: str = Depends(require_auth_api)
):
    try:
        data = storage_service.list_files(prefix=prefix)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download-url")
async def get_download_url(
    path: str = Query(..., description="Full path to object in bucket"),
    user: str = Depends(require_auth_api)
):
    try:
        url = storage_service.generate_download_url(blob_path=path, expiration_minutes=60)
        filename = os.path.basename(path.rstrip("/"))
        return {
            "signed_url": url,
            "filename": filename,
            "expires_in": 3600
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate download link: {e}")


@app.get("/api/stream-download")
async def stream_download_endpoint(
    path: str = Query(..., description="Full path to object in bucket"),
    user: str = Depends(require_auth_api)
):
    try:
        meta = storage_service.get_blob_metadata(path)
        if not meta:
            raise HTTPException(status_code=404, detail="File not found")

        filename = os.path.basename(path)
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(meta["size"])
        }
        return StreamingResponse(
            storage_service.stream_download(path),
            media_type=meta.get("content_type") or "application/octet-stream",
            headers=headers
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload-url")
async def get_upload_url(
    payload: UploadUrlRequest,
    user: str = Depends(require_auth_api)
):
    try:
        clean_path = payload.path.lstrip("/")
        if not clean_path:
            raise HTTPException(status_code=400, detail="Path cannot be empty")
        
        url = storage_service.generate_upload_url(
            blob_path=clean_path,
            content_type=payload.content_type or "application/octet-stream",
            expiration_minutes=30
        )
        return {
            "upload_url": url,
            "path": clean_path,
            "content_type": payload.content_type,
            "expires_in": 1800
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate upload URL: {e}")


@app.post("/api/upload-direct")
async def upload_direct_endpoint(
    prefix: str = Form(""),
    file: UploadFile = File(...),
    user: str = Depends(require_auth_api)
):
    try:
        clean_prefix = prefix.strip("/")
        blob_path = f"{clean_prefix}/{file.filename}" if clean_prefix else file.filename
        
        result = storage_service.upload_file_direct(
            blob_path=blob_path,
            file_obj=file.file,
            content_type=file.content_type or "application/octet-stream"
        )
        return {"status": "success", "file": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@app.post("/api/create-folder")
async def create_folder_endpoint(
    payload: CreateFolderRequest,
    user: str = Depends(require_auth_api)
):
    try:
        created = storage_service.create_folder(payload.path)
        return {"status": "success", "folder": created}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/delete")
async def delete_item_endpoint(
    payload: DeleteItemRequest,
    user: str = Depends(require_auth_api)
):
    try:
        count = storage_service.delete_item(payload.path)
        return {"status": "success", "deleted_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/preview")
async def preview_endpoint(
    path: str = Query(..., description="Path to file to preview"),
    user: str = Depends(require_auth_api)
):
    try:
        preview = storage_service.preview_text(path)
        return preview
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
