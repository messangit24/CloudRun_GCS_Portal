import hmac
import hashlib
import base64
import json
import time
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from app.config import (
    USERS,
    SECRET_KEY,
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE,
    COOKIE_SECURE
)


def verify_credentials(username: str, password: str) -> bool:
    """Verifies username and password against configured users using constant-time comparison."""
    if not username or not password:
        return False
    stored_password = USERS.get(username)
    if not stored_password:
        return False
    return hmac.compare_digest(stored_password.encode("utf-8"), password.encode("utf-8"))


def create_session_token(username: str) -> str:
    """Generates a cryptographically signed session token with expiration."""
    payload = {
        "user": username,
        "exp": int(time.time()) + SESSION_MAX_AGE
    }
    raw_payload = json.dumps(payload, separators=(',', ':')).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(raw_payload).decode("utf-8")
    signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        b64_payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"{b64_payload}.{signature}"


def verify_session_token(token: Optional[str]) -> Optional[str]:
    """Validates token signature and expiration. Returns username if valid, None otherwise."""
    if not token or "." not in token:
        return None
    try:
        b64_payload, signature = token.rsplit(".", 1)
        expected_sig = hmac.new(
            SECRET_KEY.encode("utf-8"),
            b64_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_sig):
            return None
        
        payload_bytes = base64.urlsafe_b64decode(b64_payload.encode("utf-8"))
        payload = json.loads(payload_bytes.decode("utf-8"))
        
        if payload.get("exp", 0) < time.time():
            return None
            
        return payload.get("user")
    except Exception:
        return None


def get_current_user_from_request(request: Request) -> Optional[str]:
    """Extracts and verifies username from request cookie."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    return verify_session_token(token)


async def require_auth_api(request: Request) -> str:
    """API dependency that returns username or raises 401 Unauthorized."""
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user


async def require_auth_page(request: Request) -> Optional[str]:
    """HTML route dependency that returns username or redirects to login."""
    user = get_current_user_from_request(request)
    if not user:
        # Save original URL for post-login redirect
        target = str(request.url.path)
        if request.url.query:
            target += f"?{request.url.query}"
        return None
    return user
