"""Mots de passe (Argon2id), jetons de session (JWT en cookie httpOnly), chiffrement des fichiers."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet

from .config import FILE_KEY, JWT_SECRET, SESSION_HOURS

_ph = PasswordHasher()
_fernet = Fernet(FILE_KEY.encode())
COOKIE = "nexa_session"


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(pw: str, h: str) -> bool:
    try:
        return _ph.verify(h, pw)
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_policy(pw: str) -> str | None:
    if len(pw) < 12:
        return "Le mot de passe doit contenir au moins 12 caractères."
    if pw.lower() == pw or pw.upper() == pw or not any(c.isdigit() for c in pw):
        return "Le mot de passe doit mélanger majuscules, minuscules et chiffres."
    return None


COOKIE_CLIENT = "nexa_client"
CLIENT_SESSION_MIN = 120


def create_token(user_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)
    return jwt.encode({"sub": str(user_id), "typ": "staff", "exp": exp}, JWT_SECRET, algorithm="HS256")


def read_token(token: str) -> int | None:
    try:
        p = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return int(p["sub"]) if p.get("typ") == "staff" else None
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def create_client_token(espace_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=CLIENT_SESSION_MIN)
    return jwt.encode({"esp": espace_id, "typ": "client", "exp": exp}, JWT_SECRET, algorithm="HS256")


def read_client_token(token: str) -> int | None:
    try:
        p = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return int(p["esp"]) if p.get("typ") == "client" else None
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def encrypt(data: bytes) -> bytes:
    return _fernet.encrypt(data)


def decrypt(data: bytes) -> bytes:
    return _fernet.decrypt(data)


class RateLimiter:
    """Limiteur en mémoire (un seul processus). Remplacer par Redis si plusieurs workers."""

    def __init__(self, max_hits: int, window_s: int):
        self.max, self.window = max_hits, window_s
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        t = time.monotonic()
        q = self.hits[key]
        while q and t - q[0] > self.window:
            q.popleft()
        if len(q) >= self.max:
            return False
        q.append(t)
        return True

    def reset(self, key: str) -> None:
        self.hits.pop(key, None)


login_limiter = RateLimiter(max_hits=5, window_s=300)
espace_limiter = RateLimiter(max_hits=10, window_s=600)
