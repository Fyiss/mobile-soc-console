"""
Auth API — issues JWT tokens to mobile clients.
Simple username/password for now, easy to extend.
"""

import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from jose import jwt

log = logging.getLogger("auth")

router = APIRouter()

# Hardcoded for now — move to DB or env vars in production
USERS = {
    "admin": "soc-password-123",
}

SECRET_KEY = "change-me-in-production"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def create_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    if USERS.get(req.username) != req.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_token(req.username)
    log.info(f"Token issued for: {req.username}")
    return TokenResponse(access_token=token)
