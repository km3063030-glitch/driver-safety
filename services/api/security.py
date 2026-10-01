import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

_configured_secret = os.getenv("JWT_SECRET")
if not _configured_secret and os.getenv("APP_ENV", "development").lower() == "production":
    raise RuntimeError("JWT_SECRET must be configured in production")
SECRET = _configured_secret or "dev-only-insecure-secret-set-jwt-secret-in-env-32-bytes-minimum"
if len(SECRET.encode("utf-8")) < 32:
    raise RuntimeError("JWT_SECRET must be at least 32 bytes")
ALGO = "HS256"
TTL_S = 3600
bearer = HTTPBearer(auto_error=False)


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()
    return f"{salt}${digest}"


def verify_password(password, stored):
    salt, _ = stored.split("$")
    return hmac.compare_digest(hash_password(password, salt), stored)


def make_token(username, fleet_id, role):
    now = int(time.time())
    claims = {"sub": username, "fleet": fleet_id, "role": role,
              "iat": now, "exp": now + TTL_S}
    return jwt.encode(claims, SECRET, algorithm=ALGO)


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    if creds is None:
        raise HTTPException(401, "Missing token")
    try:
        return jwt.decode(creds.credentials, SECRET, algorithms=[ALGO])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")