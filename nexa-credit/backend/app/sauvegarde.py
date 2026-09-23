"""Sauvegarde et restauration chiffrées de NEXA CREDIT.

    python -m app.sauvegarde                      crée une sauvegarde (base + pièces), chiffrée
    python -m app.sauvegarde liste                liste les sauvegardes
    python -m app.sauvegarde restaurer FICHIER    restaure (serveur ARRÊTÉ uniquement)

L'archive est chiffrée avec NEXA_FILE_KEY : sans cette clé, elle est inutilisable.
Conservez la clé ailleurs que sur le NAS (gestionnaire de mots de passe, coffre).
"""
from __future__ import annotations

import io
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR, DATABASE_URL, SAUVEGARDE_CONSERVER, SAUVEGARDE_DIR, UPLOAD_DIR
from .security import decrypt, encrypt

SUFFIXE = ".nexa-sauvegarde"


def _db_path() -> Path:
    if not DATABASE_URL.startswith("sqlite:///"):
        raise SystemExit("Sauvegarde intégrée prévue pour SQLite. Avec PostgreSQL, utilisez pg_dump.")
    return Path(DATABASE_URL.removeprefix("sqlite:///"))


def sauvegarder() -> Path:
    SAUVEGARDE_DIR.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now().strftime("%Y%m%d-%H%M%S")
    with tempfile.TemporaryDirectory() as tmp:
        instantane = Path(tmp) / "nexa.db"
        # API de sauvegarde SQLite : copie cohérente même si le serveur tourne.
        src, dst = sqlite3.connect(_db_path()), sqlite3.connect(instantane)
        with dst:
            src.backup(dst)
        src.close(); dst.close()
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            tar.add(instantane, arcname="nexa.db")
            if UPLOAD_DIR.exists():
                tar.add(UPLOAD_DIR, arcname="documents")  # déjà chiffrés individuellement
    cible = SAUVEGARDE_DIR / f"nexa-{horodatage}{SUFFIXE}"
    cible.write_bytes(encrypt(buf.getvalue()))
    cible.chmod(0o600)
    anciennes = sorted(SAUVEGARDE_DIR.glob(f"*{SUFFIXE}"))[:-SAUVEGARDE_CONSERVER]
    for f in anciennes:
        f.unlink()
    return cible


def restaurer(fichier: Path) -> None:
    donnees = decrypt(fichier.read_bytes())  # échoue si la clé ne correspond pas
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(fileobj=io.BytesIO(donnees), mode="r:gz") as tar:
            tar.extractall(tmp, filter="data")
        db = _db_path()
        if db.exists():
            db.rename(db.with_suffix(f".avant-restauration-{datetime.now():%Y%m%d-%H%M%S}"))
        shutil.copy2(Path(tmp) / "nexa.db", db)
        if (Path(tmp) / "documents").exists():
            if UPLOAD_DIR.exists():
                UPLOAD_DIR.rename(DATA_DIR / f"documents.avant-restauration-{datetime.now():%Y%m%d-%H%M%S}")
            shutil.copytree(Path(tmp) / "documents", UPLOAD_DIR)


def main(argv: list[str]) -> None:
    if not argv:
        f = sauvegarder()
        print(f"Sauvegarde créée : {f} ({f.stat().st_size // 1024} Ko)")
    elif argv[0] == "liste":
        for f in sorted(SAUVEGARDE_DIR.glob(f"*{SUFFIXE}")):
            print(f"{f.name}  {f.stat().st_size // 1024} Ko")
    elif argv[0] == "restaurer" and len(argv) == 2:
        restaurer(Path(argv[1]))
        print("Restauration terminée. Redémarrez le serveur.")
    else:
        print(__doc__)
        raise SystemExit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
