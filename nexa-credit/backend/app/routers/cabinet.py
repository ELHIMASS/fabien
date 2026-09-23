from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..audit import log
from ..db import get_db
from ..deps import admin_user, current_user
from ..schemas import CabinetOut, CabinetPatch, UserIn, UserOut, UserPatch
from ..security import hash_password, password_policy

router = APIRouter(prefix="/api/cabinet", tags=["cabinet"])


@router.get("", response_model=CabinetOut)
def lire(user: m.User = Depends(current_user)):
    return user.cabinet


@router.patch("", response_model=CabinetOut)
def modifier(data: CabinetPatch, request: Request, user: m.User = Depends(admin_user), db: Session = Depends(get_db)):
    cab = db.get(m.Cabinet, user.cabinet_id)
    changes = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(cab, k, v)
    log(db, user, "parametres", "cabinet", cab.id, {"champs": list(changes)}, request)
    db.commit()
    return cab


@router.get("/utilisateurs", response_model=list[UserOut])
def utilisateurs(user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(m.User).where(m.User.cabinet_id == user.cabinet_id).order_by(m.User.nom)).all()


@router.post("/utilisateurs", response_model=UserOut)
def creer_utilisateur(data: UserIn, request: Request, user: m.User = Depends(admin_user), db: Session = Depends(get_db)):
    if db.scalar(select(m.User).where(m.User.email == data.email.lower())):
        raise HTTPException(409, "Un compte existe déjà avec cet email.")
    if err := password_policy(data.password):
        raise HTTPException(422, err)
    u = m.User(cabinet_id=user.cabinet_id, email=data.email.lower(), nom=data.nom, role=data.role, password_hash=hash_password(data.password))
    db.add(u)
    db.flush()
    log(db, user, "utilisateur_cree", "user", u.id, {"role": data.role}, request)
    db.commit()
    return u


@router.patch("/utilisateurs/{uid}", response_model=UserOut)
def modifier_utilisateur(uid: int, data: UserPatch, request: Request, user: m.User = Depends(admin_user), db: Session = Depends(get_db)):
    u = db.get(m.User, uid)
    if not u or u.cabinet_id != user.cabinet_id:
        raise HTTPException(404, "Utilisateur introuvable.")
    if u.id == user.id and (data.actif is False or (data.role and data.role != "admin")):
        raise HTTPException(400, "Vous ne pouvez pas retirer vos propres droits d'administrateur.")
    changes = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(u, k, v)
    log(db, user, "utilisateur_modifie", "user", u.id, changes, request)
    db.commit()
    return u
