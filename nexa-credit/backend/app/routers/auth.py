from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..audit import log
from ..config import COOKIE_SECURE, SESSION_HOURS
from ..db import get_db
from ..deps import current_user
from ..schemas import CabinetOut, LoginIn, PasswordIn, SetupIn, UserOut
from ..security import COOKIE, create_token, hash_password, login_limiter, password_policy, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_cookie(resp: Response, user: m.User) -> None:
    resp.set_cookie(COOKIE, create_token(user.id), httponly=True, secure=COOKIE_SECURE,
                    samesite="strict", max_age=SESSION_HOURS * 3600, path="/")


@router.get("/etat")
def etat(db: Session = Depends(get_db)):
    """Indique si l'installation initiale (création du cabinet) reste à faire."""
    return {"installe": db.scalar(select(func.count(m.User.id))) > 0}


@router.post("/installation", response_model=UserOut)
def installation(data: SetupIn, request: Request, response: Response, db: Session = Depends(get_db)):
    if db.scalar(select(func.count(m.User.id))) > 0:
        raise HTTPException(409, "Le logiciel est déjà installé. Connectez-vous.")
    if err := password_policy(data.password):
        raise HTTPException(422, err)
    cab = m.Cabinet(nom=data.cabinet, orias=data.orias)
    db.add(cab)
    db.flush()
    user = m.User(cabinet_id=cab.id, email=data.email.lower(), nom=data.nom, role="admin", password_hash=hash_password(data.password))
    db.add(user)
    db.flush()
    log(db, user, "installation", "cabinet", cab.id, request=request)
    db.commit()
    _set_cookie(response, user)
    return user


@router.post("/connexion", response_model=UserOut)
def connexion(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    key = f"{request.client.host if request.client else ''}:{data.email.lower()}"
    if not login_limiter.allow(key):
        raise HTTPException(429, "Trop de tentatives. Réessayez dans 5 minutes.")
    user = db.scalar(select(m.User).where(m.User.email == data.email.lower()))
    if not user or not user.actif or not verify_password(data.password, user.password_hash):
        log(db, user, "connexion_echec", details={"email": data.email.lower()}, request=request,
            cabinet_id=user.cabinet_id if user else None)
        db.commit()
        raise HTTPException(401, "Email ou mot de passe incorrect.")
    login_limiter.reset(key)
    log(db, user, "connexion", request=request)
    db.commit()
    _set_cookie(response, user)
    return user


@router.post("/deconnexion")
def deconnexion(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/moi")
def moi(user: m.User = Depends(current_user)):
    return {"user": UserOut.model_validate(user), "cabinet": CabinetOut.model_validate(user.cabinet)}


@router.post("/mot-de-passe")
def mot_de_passe(data: PasswordIn, request: Request, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(data.ancien, user.password_hash):
        raise HTTPException(400, "Mot de passe actuel incorrect.")
    if err := password_policy(data.nouveau):
        raise HTTPException(422, err)
    user = db.merge(user)
    user.password_hash = hash_password(data.nouveau)
    log(db, user, "mot_de_passe", "user", user.id, request=request)
    db.commit()
    return {"ok": True}
