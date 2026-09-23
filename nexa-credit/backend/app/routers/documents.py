from __future__ import annotations

import hashlib
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models as m
from ..audit import log
from ..calc.analyse import PIECES
from ..config import ALLOWED_MIME, MAX_UPLOAD_MB, UPLOAD_DIR
from ..db import get_db
from ..deps import current_user, get_dossier
from ..schemas import DocumentOut, DocumentPatch
from ..security import decrypt, encrypt

router = APIRouter(prefix="/api/dossiers/{dossier_id}/documents", tags=["documents"])

# Signatures de fichiers : on ne fait pas confiance au type annoncé par le navigateur.
MAGIC = {b"%PDF": "application/pdf", b"\xff\xd8\xff": "image/jpeg", b"\x89PNG": "image/png"}


def _detect(head: bytes) -> str | None:
    for sig, mime in MAGIC.items():
        if head.startswith(sig):
            return mime
    if head[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1"):
        return "image/heic"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def _get(db: Session, d: m.Dossier, doc_id: int) -> m.Document:
    doc = db.get(m.Document, doc_id)
    if not doc or doc.dossier_id != d.id:
        raise HTTPException(404, "Document introuvable.")
    return doc


@router.get("/categories")
def categories(dossier_id: int):
    return PIECES


async def enregistrer_fichier(db: Session, d: m.Dossier, categorie: str, fichier: UploadFile,
                              emprunteur_id: int | None = None, user_id: int | None = None,
                              source: str = "cabinet") -> m.Document:
    """Contrôle, chiffre et enregistre un fichier déposé (par le cabinet ou par le client)."""
    if categorie not in PIECES and categorie != "autre":
        raise HTTPException(422, "Catégorie de pièce inconnue.")
    if emprunteur_id is not None and emprunteur_id not in {e.id for e in d.emprunteurs}:
        raise HTTPException(422, "Emprunteur inconnu pour ce dossier.")
    data = await fichier.read(MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"Fichier trop volumineux (maximum {MAX_UPLOAD_MB} Mo).")
    if not data:
        raise HTTPException(422, "Fichier vide.")
    mime = _detect(data[:16])
    if mime not in ALLOWED_MIME:
        raise HTTPException(415, "Format non accepté : PDF, JPEG, PNG, HEIC ou WEBP uniquement.")
    dest_dir = UPLOAD_DIR / str(d.cabinet_id) / str(d.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    chemin = dest_dir / f"{uuid.uuid4().hex}.bin"
    chemin.write_bytes(encrypt(data))
    nom = (fichier.filename or "document").replace("/", "_").replace("\\", "_")[:255]
    doc = m.Document(dossier_id=d.id, emprunteur_id=emprunteur_id, categorie=categorie, nom_fichier=nom,
                     chemin=str(chemin.relative_to(UPLOAD_DIR)), mime=mime, taille=len(data),
                     sha256=hashlib.sha256(data).hexdigest(), depose_par=user_id, source=source)
    db.add(doc)
    d.updated_at = m.now()
    db.flush()
    return doc


@router.post("", response_model=DocumentOut)
async def deposer(dossier_id: int, request: Request, categorie: str = Form(...), emprunteur_id: int | None = Form(None),
                  fichier: UploadFile = File(...), user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_dossier(dossier_id, db, user)
    doc = await enregistrer_fichier(db, d, categorie, fichier, emprunteur_id, user.id)
    log(db, user, "document_depose", "dossier", d.id, {"document": doc.id, "categorie": categorie}, request)
    db.commit()
    return doc


@router.get("/{doc_id}/fichier")
def telecharger(dossier_id: int, doc_id: int, request: Request, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_dossier(dossier_id, db, user)
    doc = _get(db, d, doc_id)
    data = decrypt((UPLOAD_DIR / doc.chemin).read_bytes())
    log(db, user, "document_consulte", "dossier", d.id, {"document": doc.id}, request)
    db.commit()
    return Response(data, media_type=doc.mime, headers={
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(doc.nom_fichier)}",
        "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store",
    })


@router.patch("/{doc_id}", response_model=DocumentOut)
def modifier(dossier_id: int, doc_id: int, data: DocumentPatch, request: Request, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_dossier(dossier_id, db, user)
    doc = _get(db, d, doc_id)
    changes = data.model_dump(exclude_unset=True)
    if "categorie" in changes and changes["categorie"] not in PIECES and changes["categorie"] != "autre":
        raise HTTPException(422, "Catégorie de pièce inconnue.")
    for k, v in changes.items():
        setattr(doc, k, v)
    d.updated_at = m.now()
    log(db, user, "document_modifie", "dossier", d.id, {"document": doc.id, **{k: v for k, v in changes.items() if k != "commentaire"}}, request)
    db.commit()
    return doc


@router.delete("/{doc_id}")
def supprimer(dossier_id: int, doc_id: int, request: Request, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_dossier(dossier_id, db, user)
    doc = _get(db, d, doc_id)
    (UPLOAD_DIR / doc.chemin).unlink(missing_ok=True)
    db.delete(doc)
    log(db, user, "document_supprime", "dossier", d.id, {"document": doc_id}, request)
    db.commit()
    return {"ok": True}
