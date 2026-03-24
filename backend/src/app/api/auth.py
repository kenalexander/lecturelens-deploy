from datetime import datetime
import os
import secrets
from pydantic import BaseModel
from fastapi import APIRouter, Cookie, HTTPException, Response, status

from app.core.db import get_db
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.core.user_schemas import UserCreate, UserLogin, UserOut

GOOGLE_IMPORT_ERROR: Exception | None = None

try:
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2 import id_token as google_id_token
except ImportError as exc:  # pragma: no cover - optional until dependency is installed
    GoogleRequest = None
    google_id_token = None
    GOOGLE_IMPORT_ERROR = exc

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "session"
COOKIE_SECURE = bool(int(os.getenv("COOKIE_SECURE", "0")))
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "none" if COOKIE_SECURE else "lax")
MOBILE_LINK_TTL_SECONDS = int(os.getenv("MOBILE_LINK_TTL_SECONDS", "600"))
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()


class MobileLinkOut(BaseModel):
    token: str
    expiresInSeconds: int


class MobileExchangeIn(BaseModel):
    token: str
    sessionId: str


class MobileLinkIn(BaseModel):
    sessionId: str


class GoogleLoginIn(BaseModel):
    credential: str


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
        max_age=60 * 60 * 24 * 7,
        path="/",
    )


def _verify_google_credential(credential: str) -> tuple[str, str]:
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google sign-in is not configured",
        )
    if google_id_token is None or GoogleRequest is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google auth backend dependency is unavailable: {GOOGLE_IMPORT_ERROR}",
        )

    try:
        payload = google_id_token.verify_oauth2_token(
            credential,
            GoogleRequest(),
            GOOGLE_CLIENT_ID,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential",
        ) from exc

    email = str(payload.get("email") or "").strip().lower()
    google_sub = str(payload.get("sub") or "").strip()
    email_verified = bool(payload.get("email_verified"))

    if not email or not google_sub or not email_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account email is not verified",
        )

    return google_sub, email


@router.post("/register", response_model=UserOut)
def register(payload: UserCreate, response: Response) -> UserOut:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email = %s", (payload.email,))
        existing = cur.fetchone()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use")
        now = datetime.utcnow().isoformat()
        password_hash = hash_password(payload.password)
        cur.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (%s, %s, %s) RETURNING id",
            (payload.email, password_hash, now),
        )
        user_id = cur.fetchone()["id"]
        cur.execute(
            "INSERT INTO profiles (user_id, full_name, program_name, institution, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, None, None, None, now, now),
        )
        token = create_access_token({"sub": str(user_id), "email": payload.email})
        _set_session_cookie(response, token)
        return UserOut(id=user_id, email=payload.email)


@router.post("/login", response_model=UserOut)
def login(payload: UserLogin, response: Response) -> UserOut:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, email, password_hash FROM users WHERE email = %s", (payload.email,)
        )
        row = cur.fetchone()
        if not row or not verify_password(payload.password, row["password_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        token = create_access_token({"sub": str(row["id"]), "email": row["email"]})
        _set_session_cookie(response, token)
        return UserOut(id=row["id"], email=row["email"])


@router.post("/google", response_model=UserOut)
def google_login(payload: GoogleLoginIn, response: Response) -> UserOut:
    google_sub, email = _verify_google_credential(payload.credential)
    now = datetime.utcnow().isoformat()

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, email, google_sub FROM users WHERE google_sub = %s",
            (google_sub,),
        )
        existing_google_user = cur.fetchone()
        if existing_google_user:
            user_id = int(existing_google_user["id"])
            user_email = str(existing_google_user["email"])
        else:
            cur.execute(
                "SELECT id, email, google_sub FROM users WHERE LOWER(email) = LOWER(%s)",
                (email,),
            )
            existing_email_user = cur.fetchone()
            if existing_email_user:
                linked_google_sub = existing_email_user["google_sub"]
                if linked_google_sub and str(linked_google_sub) != google_sub:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="This email is already linked to a different Google account",
                    )
                user_id = int(existing_email_user["id"])
                user_email = str(existing_email_user["email"])
                cur.execute(
                    "UPDATE users SET google_sub = %s WHERE id = %s",
                    (google_sub, user_id),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO users (email, password_hash, google_sub, created_at)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (email, hash_password(secrets.token_urlsafe(32)), google_sub, now),
                )
                user_id = int(cur.fetchone()["id"])
                user_email = email
                cur.execute(
                    """
                    INSERT INTO profiles (user_id, full_name, program_name, institution, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, None, None, None, now, now),
                )

        token = create_access_token({"sub": str(user_id), "email": user_email})
        _set_session_cookie(response, token)
        return UserOut(id=user_id, email=user_email)


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(session: str | None = Cookie(default=None)) -> UserOut:
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(session)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    return UserOut(id=int(payload["sub"]), email=payload["email"])


@router.post("/mobile-link", response_model=MobileLinkOut)
def create_mobile_link(payload: MobileLinkIn, session: str | None = Cookie(default=None)) -> MobileLinkOut:
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        token_payload = decode_token(session)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user_id = int(token_payload["sub"])
    email = token_payload["email"]
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT mobile_link_nonce FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        nonce = int(row["mobile_link_nonce"] or 0) + 1
        cur.execute(
            "UPDATE users SET mobile_link_nonce = %s WHERE id = %s",
            (nonce, user_id),
        )

    token = create_access_token(
        {
            "sub": str(user_id),
            "email": email,
            "scope": "mobile_link",
            "sid": payload.sessionId,
            "nonce": nonce,
        },
        expires_seconds=MOBILE_LINK_TTL_SECONDS,
    )
    return MobileLinkOut(token=token, expiresInSeconds=MOBILE_LINK_TTL_SECONDS)


@router.post("/mobile-exchange", response_model=UserOut)
def mobile_exchange(payload: MobileExchangeIn, response: Response) -> UserOut:
    try:
        token_payload = decode_token(payload.token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired link") from exc

    if token_payload.get("scope") != "mobile_link":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid link scope")

    user_id_raw = token_payload.get("sub")
    email = token_payload.get("email")
    nonce = token_payload.get("nonce")
    session_id = token_payload.get("sid")
    if not user_id_raw or not email or not nonce or not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid link payload")
    if str(session_id) != payload.sessionId:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session mismatch")
    user_id = int(user_id_raw)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, email, mobile_link_nonce FROM users WHERE id = %s", (user_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        if int(row["mobile_link_nonce"] or 0) != int(nonce):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Link has been refreshed")

    access_token = create_access_token({"sub": str(user_id), "email": str(row["email"])})
    _set_session_cookie(response, access_token)
    return UserOut(id=user_id, email=str(row["email"]))
