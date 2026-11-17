"""Accesso con password. La password non è mai nel codice né nel repository:
nel database c'è solo il suo hash (scrypt con sale casuale). La sessione è un cookie
firmato con SESSION_SECRET, che sta solo nelle variabili d'ambiente del server."""
import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base, get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])
COOKIE = "nexus_session"
MAX_AGE = 60 * 60 * 24 * 30
MAX_FAILS, LOCK_MINUTES = 5, 15


class AuthConfig(Base):
    __tablename__ = "app_auth"
    id: Mapped[int] = mapped_column(primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${base64.b64encode(salt).decode()}${base64.b64encode(h).decode()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, s, h = stored.split("$")
        salt, expected = base64.b64decode(s), base64.b64decode(h)
    except Exception:
        return False
    got = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return hmac.compare_digest(got, expected)


def _secret() -> bytes:
    s = os.getenv("SESSION_SECRET", "")
    if len(s) < 32:
        raise HTTPException(500, "Configurazione mancante sul server: SESSION_SECRET")
    return s.encode()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _version(pw_hash: str) -> str:
    return hashlib.sha256(pw_hash.encode()).hexdigest()[:16]


def make_token(pw_hash: str) -> str:
    payload = json.dumps({"exp": int(time.time()) + MAX_AGE, "v": _version(pw_hash)}).encode()
    sig = hmac.new(_secret(), payload, hashlib.sha256).digest()
    return f"{_b64(payload)}.{_b64(sig)}"


def valid_token(token: str, pw_hash: str) -> bool:
    try:
        p, s = token.split(".")
        payload = _unb64(p)
        if not hmac.compare_digest(_unb64(s), hmac.new(_secret(), payload, hashlib.sha256).digest()):
            return False
        d = json.loads(payload)
        return d["exp"] > time.time() and hmac.compare_digest(d["v"], _version(pw_hash))
    except HTTPException:
        raise
    except Exception:
        return False


def _aware(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _set_cookie(request: Request, response: Response, pw_hash: str) -> None:
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    response.set_cookie(COOKIE, make_token(pw_hash), max_age=MAX_AGE, httponly=True,
                        secure=secure, samesite="lax", path="/")


def require_auth(request: Request, db: Session = Depends(get_db)) -> None:
    cfg, tok = db.get(AuthConfig, 1), request.cookies.get(COOKIE)
    if not cfg or not tok or not valid_token(tok, cfg.password_hash):
        raise HTTPException(401, "Accesso richiesto")


class SetupIn(BaseModel):
    code: str = Field(max_length=200)
    password: str = Field(min_length=10, max_length=200)


class LoginIn(BaseModel):
    password: str = Field(max_length=200)


@router.get("/status")
def status(request: Request, db: Session = Depends(get_db)):
    cfg, tok = db.get(AuthConfig, 1), request.cookies.get(COOKIE)
    return {"setup_required": cfg is None, "setup_available": len(os.getenv("SETUP_CODE", "")) >= 16,
            "authenticated": bool(cfg and tok and valid_token(tok, cfg.password_hash))}


@router.post("/setup")
def setup(d: SetupIn, request: Request, response: Response, db: Session = Depends(get_db)):
    if db.get(AuthConfig, 1):
        raise HTTPException(409, "La password è già impostata")
    code = os.getenv("SETUP_CODE", "")
    if len(code) < 16:
        raise HTTPException(503, "SETUP_CODE mancante sul server (almeno 16 caratteri)")
    if not hmac.compare_digest(d.code.encode(), code.encode()):
        raise HTTPException(403, "Codice di configurazione errato")
    cfg = AuthConfig(id=1, password_hash=hash_password(d.password))
    db.add(cfg)
    db.commit()
    _set_cookie(request, response, cfg.password_hash)
    return {"ok": True}


@router.post("/login")
def login(d: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    cfg = db.get(AuthConfig, 1)
    if not cfg:
        raise HTTPException(409, "Password non ancora impostata")
    now = datetime.now(timezone.utc)
    lock = _aware(cfg.locked_until)
    if lock and lock > now:
        raise HTTPException(429, "Troppi tentativi. Riprova tra qualche minuto.")
    if not verify_password(d.password, cfg.password_hash):
        cfg.failed_count += 1
        if cfg.failed_count >= MAX_FAILS:
            cfg.locked_until, cfg.failed_count = now + timedelta(minutes=LOCK_MINUTES), 0
        db.commit()
        raise HTTPException(401, "Password errata")
    cfg.failed_count, cfg.locked_until = 0, None
    db.commit()
    _set_cookie(request, response, cfg.password_hash)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}
