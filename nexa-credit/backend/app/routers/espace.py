"""Espace client : le client dépose ses pièces via un lien secret + un code à 6 chiffres.

Choix de sécurité :
- le jeton du lien (256 bits) n'est stocké que sous forme de SHA-256 ;
- le code est haché en Argon2 ; 5 erreurs verrouillent le lien, le courtier doit en recréer un ;
- le lien expire (30 jours par défaut) et un seul lien est actif par dossier ;
- le client ne peut ni télécharger, ni supprimer de document : il dépose et voit les statuts ;
- il ne voit aucune donnée financière du dossier.
"""
import hashlib
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..audit import log
from ..calc.analyse import PIECES, etat_pieces
from ..config import COOKIE_SECURE
from ..db import get_db
from ..deps import current_user, get_dossier
from ..security import (
    CLIENT_SESSION_MIN, COOKIE_CLIENT, create_client_token, espace_limiter, hash_password, read_client_token,
    verify_password,
)
from .documents import enregistrer_fichier

router = APIRouter(tags=["espace client"])

VALIDITE_JOURS = 30
MAX_ECHECS = 5
MAX_DEPOTS = 150


def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _aware(dt):
    # SQLite renvoie des dates sans fuseau : elles sont stockées en UTC.
    from datetime import timezone
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _statut(e: m.EspaceClient) -> str:
    if e.revoque:
        return "révoqué"
    if e.echecs >= MAX_ECHECS:
        return "verrouillé"
    if _aware(e.expire_le) < m.now():
        return "expiré"
    return "actif"


def _vue_courtier(e: m.EspaceClient | None) -> dict | None:
    if not e:
        return None
    return {"id": e.id, "statut": _statut(e), "expire_le": e.expire_le, "created_at": e.created_at,
            "dernier_acces": e.dernier_acces, "nb_depots": e.nb_depots, "echecs": e.echecs}


def _actuel(db: Session, dossier_id: int) -> m.EspaceClient | None:
    return db.scalar(select(m.EspaceClient).where(m.EspaceClient.dossier_id == dossier_id).order_by(m.EspaceClient.id.desc()).limit(1))


# ---------------------------------------------------------------- côté courtier
@router.get("/api/dossiers/{dossier_id}/espace")
def lire_espace(dossier_id: int, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_dossier(dossier_id, db, user)
    return _vue_courtier(_actuel(db, d.id))


@router.post("/api/dossiers/{dossier_id}/espace")
def creer_espace(dossier_id: int, request: Request, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_dossier(dossier_id, db, user)
    for ancien in db.scalars(select(m.EspaceClient).where(m.EspaceClient.dossier_id == d.id, m.EspaceClient.revoque.is_(False))):
        ancien.revoque = True
    token = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(1_000_000):06d}"
    e = m.EspaceClient(dossier_id=d.id, token_hash=_h(token), code_hash=hash_password(code),
                       expire_le=m.now() + timedelta(days=VALIDITE_JOURS), cree_par=user.id)
    db.add(e)
    db.flush()
    log(db, user, "espace_client_cree", "dossier", d.id, {"espace": e.id}, request)
    db.commit()
    # Le jeton et le code ne sont renvoyés qu'une seule fois : ils ne sont pas récupérables ensuite.
    return {**_vue_courtier(e), "chemin": f"/espace/{token}", "code": code}


@router.delete("/api/dossiers/{dossier_id}/espace")
def revoquer_espace(dossier_id: int, request: Request, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_dossier(dossier_id, db, user)
    e = _actuel(db, d.id)
    if not e:
        raise HTTPException(404, "Aucun espace client pour ce dossier.")
    e.revoque = True
    log(db, user, "espace_client_revoque", "dossier", d.id, {"espace": e.id}, request)
    db.commit()
    return _vue_courtier(e)


# ---------------------------------------------------------------- côté client
class CodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


LIEN_INVALIDE = "Ce lien n'est plus valide. Contactez votre courtier pour en obtenir un nouveau."


@router.post("/api/espace/{token}/connexion")
def connexion_client(token: str, data: CodeIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else ""
    if not espace_limiter.allow(f"{ip}:{token[:12]}"):
        raise HTTPException(429, "Trop de tentatives. Réessayez dans 10 minutes.")
    e = db.scalar(select(m.EspaceClient).where(m.EspaceClient.token_hash == _h(token)))
    if not e or _statut(e) != "actif":
        raise HTTPException(410, LIEN_INVALIDE)
    d = db.get(m.Dossier, e.dossier_id)
    if not verify_password(data.code, e.code_hash):
        e.echecs += 1
        log(db, None, "espace_client_echec", "dossier", d.id, {"espace": e.id, "echecs": e.echecs}, request, cabinet_id=d.cabinet_id, acteur="client (espace)")
        db.commit()
        if e.echecs >= MAX_ECHECS:
            raise HTTPException(410, "Trop de codes erronés : ce lien est verrouillé. Contactez votre courtier.")
        raise HTTPException(401, f"Code incorrect. {MAX_ECHECS - e.echecs} essai(s) restant(s).")
    e.echecs = 0
    e.dernier_acces = m.now()
    log(db, None, "espace_client_connexion", "dossier", d.id, {"espace": e.id}, request, cabinet_id=d.cabinet_id, acteur="client (espace)")
    db.commit()
    response.set_cookie(COOKIE_CLIENT, create_client_token(e.id), httponly=True, secure=COOKIE_SECURE,
                        samesite="strict", max_age=CLIENT_SESSION_MIN * 60, path="/api/espace")
    return {"ok": True}


def client_espace(request: Request, db: Session = Depends(get_db)) -> m.EspaceClient:
    tok = request.cookies.get(COOKIE_CLIENT)
    eid = read_client_token(tok) if tok else None
    e = db.get(m.EspaceClient, eid) if eid else None
    if not e:
        raise HTTPException(401, "Session expirée : saisissez à nouveau votre code.")
    if _statut(e) != "actif":
        raise HTTPException(410, LIEN_INVALIDE)
    return e


@router.get("/api/espace/moi")
def moi_client(e: m.EspaceClient = Depends(client_espace), db: Session = Depends(get_db)):
    d = db.get(m.Dossier, e.dossier_id)
    cab = db.get(m.Cabinet, d.cabinet_id)
    pieces = etat_pieces(d)
    docs = {x.id: x for x in d.documents}
    return {
        "cabinet": cab.nom, "orias": cab.orias,
        "courtier": {"nom": d.courtier.nom, "email": d.courtier.email} if d.courtier else None,
        "prenoms": " et ".join(x.prenom for x in d.emprunteurs if x.prenom) or None,
        "expire_le": e.expire_le,
        "pieces": [{
            "categorie": p["categorie"], "libelle": p["libelle"], "statut": p["statut"],
            # Seul le motif de refus est montré au client ; les autres commentaires restent internes.
            "motif_refus": next((docs[i].commentaire for i in reversed(p["documents"]) if docs[i].statut == "refuse" and docs[i].commentaire), None)
                           if p["statut"] == "refuse" else None,
            "fichiers": [{"nom": docs[i].nom_fichier, "date": docs[i].created_at, "statut": docs[i].statut}
                         for i in p["documents"] if docs[i].source == "client"],
        } for p in pieces],
    }


@router.post("/api/espace/documents")
async def depot_client(request: Request, categorie: str = Form(...), fichier: UploadFile = File(...),
                       e: m.EspaceClient = Depends(client_espace), db: Session = Depends(get_db)):
    if e.nb_depots >= MAX_DEPOTS:
        raise HTTPException(429, "Nombre maximal de dépôts atteint. Contactez votre courtier.")
    d = db.get(m.Dossier, e.dossier_id)
    if categorie != "autre" and categorie not in {p["categorie"] for p in etat_pieces(d)}:
        raise HTTPException(422, "Cette pièce n'est pas demandée pour votre dossier.")
    doc = await enregistrer_fichier(db, d, categorie, fichier, source="client")
    e.nb_depots += 1
    e.dernier_acces = m.now()
    libelle = PIECES.get(categorie, "Autre document")
    # Une seule tâche ouverte « pièces client » par dossier, pour ne pas noyer le courtier.
    ouverte = next((t for t in d.taches if not t.faite and t.libelle.startswith("Contrôler les pièces déposées par le client")), None)
    if ouverte:
        ouverte.libelle = f"Contrôler les pièces déposées par le client (dernière : {libelle})"[:300]
    else:
        d.taches.append(m.Tache(libelle=f"Contrôler les pièces déposées par le client (dernière : {libelle})"[:300],
                                echeance=m.now().date(), assigne_id=d.courtier_id))
    log(db, None, "espace_client_depot", "dossier", d.id, {"espace": e.id, "document": doc.id, "categorie": categorie},
        request, cabinet_id=d.cabinet_id, acteur="client (espace)")
    db.commit()
    return {"ok": True, "nom": doc.nom_fichier}


@router.post("/api/espace/deconnexion")
def deconnexion_client(response: Response):
    response.delete_cookie(COOKIE_CLIENT, path="/api/espace")
    return {"ok": True}
