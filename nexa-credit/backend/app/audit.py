from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from . import models as m


def log(db: Session, user: m.User | None, action: str, entite: str = "", entite_id: int | None = None,
        details: dict | None = None, request: Request | None = None, cabinet_id: int | None = None,
        acteur: str = "") -> None:
    """Journal d'audit : qui a fait quoi, quand, sur quel dossier (traçabilité RGPD).
    Ne jamais y écrire de données personnelles en clair au-delà de l'identifiant."""
    db.add(m.AuditLog(
        cabinet_id=cabinet_id or (user.cabinet_id if user else None),
        user_id=user.id if user else None,
        user_email=user.email if user else acteur,
        action=action, entite=entite, entite_id=entite_id, details=details or {},
        ip=(request.client.host if request and request.client else ""),
    ))
