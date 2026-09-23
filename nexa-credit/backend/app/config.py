"""Configuration par variables d'environnement."""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("NEXA_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get("NEXA_DATABASE_URL", f"sqlite:///{DATA_DIR / 'nexa.db'}")
UPLOAD_DIR = DATA_DIR / "documents"

ENV = os.environ.get("NEXA_ENV", "dev")


def _secret(name: str, generator) -> str:
    """Secret lu dans l'environnement ; en dev, généré et conservé dans DATA_DIR."""
    val = os.environ.get(name)
    if val:
        return val
    if ENV == "prod":
        raise RuntimeError(f"Variable d'environnement {name} obligatoire en production")
    f = DATA_DIR / f".{name.lower()}"
    if not f.exists():
        f.write_text(generator())
        f.chmod(0o600)
    return f.read_text().strip()


def _fernet_key() -> str:
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


JWT_SECRET = _secret("NEXA_JWT_SECRET", lambda: secrets.token_urlsafe(48))
# Clé de chiffrement des pièces justificatives au repos (Fernet / AES-128-CBC + HMAC).
# Sa perte rend les documents illisibles : la sauvegarder hors du serveur.
FILE_KEY = _secret("NEXA_FILE_KEY", _fernet_key)

SESSION_HOURS = int(os.environ.get("NEXA_SESSION_HOURS", "10"))
COOKIE_SECURE = ENV == "prod"
MAX_UPLOAD_MB = int(os.environ.get("NEXA_MAX_UPLOAD_MB", "15"))
ALLOWED_MIME = {"application/pdf", "image/jpeg", "image/png", "image/heic", "image/webp"}
