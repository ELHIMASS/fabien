from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from . import models as m
from .db import get_db
from .security import COOKIE, read_token


def current_user(request: Request, db: Session = Depends(get_db)) -> m.User:
    token = request.cookies.get(COOKIE)
    uid = read_token(token) if token else None
    user = db.get(m.User, uid) if uid else None
    if not user or not user.actif:
        raise HTTPException(401, "Session expirée, reconnectez-vous.")
    return user


def admin_user(user: m.User = Depends(current_user)) -> m.User:
    if user.role != "admin":
        raise HTTPException(403, "Réservé à l'administrateur du cabinet.")
    return user


def get_dossier(dossier_id: int, db: Session, user: m.User) -> m.Dossier:
    d = db.get(m.Dossier, dossier_id)
    # Cloisonnement : un cabinet ne voit jamais les dossiers d'un autre (404, pas 403, pour ne rien révéler).
    if not d or d.cabinet_id != user.cabinet_id:
        raise HTTPException(404, "Dossier introuvable.")
    return d
