"""
Authentication API — simple demo admin login.

Single hardcoded admin account for demonstration purposes.
In production, this would use a proper user store, hashed passwords, and JWT tokens.
"""

import hashlib
import secrets
import time
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Authentication"])

# ─── Demo Admin Credentials ───────────────────────────────────────────
DEMO_ADMIN = {
    "username": "admin",
    "password": "demo123",
    "name": "Admin Officer",
    "role": "SUPERINTENDENT",
    "badge": "NX-ADMIN-001",
}

# Simple in-memory session store (demo only)
_sessions: dict[str, dict] = {}


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: dict


class UserResponse(BaseModel):
    username: str
    name: str
    role: str
    badge: str


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest):
    """Authenticate with demo admin credentials."""
    if (
        payload.username.strip().lower() != DEMO_ADMIN["username"]
        or payload.password != DEMO_ADMIN["password"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Use admin / demo123",
        )

    token = secrets.token_hex(32)
    _sessions[token] = {
        "username": DEMO_ADMIN["username"],
        "name": DEMO_ADMIN["name"],
        "role": DEMO_ADMIN["role"],
        "badge": DEMO_ADMIN["badge"],
        "created_at": time.time(),
    }

    return LoginResponse(
        token=token,
        user={
            "username": DEMO_ADMIN["username"],
            "name": DEMO_ADMIN["name"],
            "role": DEMO_ADMIN["role"],
            "badge": DEMO_ADMIN["badge"],
        },
    )


@router.post("/logout")
async def logout():
    """Logout (clears frontend token — demo only)."""
    return {"status": "logged_out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user():
    """Return demo admin info (no token validation in demo mode)."""
    return UserResponse(
        username=DEMO_ADMIN["username"],
        name=DEMO_ADMIN["name"],
        role=DEMO_ADMIN["role"],
        badge=DEMO_ADMIN["badge"],
    )
