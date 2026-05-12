"""
Auth routes and dependency for AccountIQ.
Register, login, logout, get_current_user.

Uses PyJWT (HS256) for tokens and pwdlib (Argon2) for password hashing.
Tokens are stored in HTTP-only cookies named 'accountiq_session'.
"""
import os
from datetime import datetime, timedelta, UTC

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Response
import aiosqlite
import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from db import get_db

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SECRET_KEY = os.environ.get("SECRET_KEY", "")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7
COOKIE_NAME = "accountiq_session"
COOKIE_MAX_AGE = TOKEN_EXPIRE_DAYS * 24 * 60 * 60  # 604800
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "").strip().lower()
PASSWORD_MIN_LEN = 8

_password_hash = PasswordHash.recommended()

auth_router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Password + token helpers
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return _password_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _password_hash.verify(plain, hashed)
    except Exception:
        return False


def create_access_token(data: dict) -> str:
    to_encode = dict(data)
    to_encode["exp"] = datetime.now(UTC) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
        secure=COOKIE_SECURE,
        path="/",
    )


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

async def get_current_user(
    accountiq_session: str | None = Cookie(default=None),
    db: aiosqlite.Connection = Depends(get_db),
) -> dict:
    """Return the authenticated user dict, or raise 401."""
    if not accountiq_session:
        raise HTTPException(401, "Not authenticated")
    if not SECRET_KEY:
        # Misconfiguration safeguard — never accept tokens with empty secret
        raise HTTPException(500, "Server auth not configured")
    try:
        payload = jwt.decode(accountiq_session, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(401, "Invalid token")
    except InvalidTokenError:
        raise HTTPException(401, "Invalid or expired token")
    async with db.execute(
        "SELECT id, email, is_admin, created_at FROM users WHERE id=?", (user_id,)
    ) as cur:
        user = await cur.fetchone()
    if not user:
        raise HTTPException(401, "User not found")
    return dict(user)


async def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Return user if admin, else 403. Unauthenticated callers still get 401 (from get_current_user)."""
    if not current_user.get("is_admin"):
        raise HTTPException(403, "Admin access required")
    return current_user


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@auth_router.post("/register", status_code=201)
async def register(
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    db: aiosqlite.Connection = Depends(get_db),
):
    email = email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Valid email required")
    if len(password) < PASSWORD_MIN_LEN:
        raise HTTPException(
            400, f"Password must be at least {PASSWORD_MIN_LEN} characters"
        )

    hashed = hash_password(password)
    try:
        async with db.execute(
            "INSERT INTO users (email, hashed_pw) VALUES (?, ?)",
            (email, hashed),
        ) as cur:
            user_id = cur.lastrowid
        await db.commit()
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(409, "Email already registered")
        raise HTTPException(500, str(e))

    # Promote to admin if registration email matches OWNER_EMAIL (per D-02)
    if OWNER_EMAIL and email == OWNER_EMAIL:
        await db.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (user_id,))
        await db.commit()

    token = create_access_token({"sub": str(user_id), "email": email})
    _set_session_cookie(response, token)
    print(f"[AUTH] User registered: {email}")
    return {"id": user_id, "email": email}


@auth_router.post("/login")
async def login(
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    db: aiosqlite.Connection = Depends(get_db),
):
    email = email.strip().lower()
    async with db.execute(
        "SELECT id, email, hashed_pw FROM users WHERE email=?", (email,)
    ) as cur:
        row = await cur.fetchone()
    if not row or not verify_password(password, row["hashed_pw"]):
        print(f"[AUTH] Login failed for: {email}")
        raise HTTPException(401, "Invalid email or password")
    token = create_access_token({"sub": str(row["id"]), "email": row["email"]})
    _set_session_cookie(response, token)
    print(f"[AUTH] Login OK: {email}")
    return {"id": row["id"], "email": row["email"]}


@auth_router.post("/logout")
async def logout(response: Response):
    # Overwrite the cookie with Max-Age=0 to clear it
    response.set_cookie(
        key=COOKIE_NAME,
        value="",
        httponly=True,
        samesite="lax",
        max_age=0,
        secure=COOKIE_SECURE,
        path="/",
    )
    return {"ok": True}


@auth_router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user
