"""Vues transverses : tâches, facturation, simulateurs, RGPD, journal d'audit."""
from __future__ import annotations

import shutil
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..audit import log
from ..calc.finance import Pret, capacite_emprunt, echeancier, estimation_frais_notaire
from ..config import UPLOAD_DIR
from ..db import get_db
from ..deps import admin_user, current_user, get_dossier
from ..schemas import SimulationCapaciteIn, SimulationPretIn
from .dossiers import detail, nom_dossier

router = APIRouter(prefix="/api", tags=["outils"])


@router.get("/taches")
def taches(user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    q = (select(m.Tache, m.Dossier).join(m.Dossier)
         .where(m.Dossier.cabinet_id == user.cabinet_id, m.Tache.faite.is_(False), m.Dossier.archive.is_(False))
         .order_by(m.Tache.echeance.is_(None), m.Tache.echeance))
    return [{"id": t.id, "libelle": t.libelle, "echeance": t.echeance, "dossier_id": d.id, "dossier": nom_dossier(d),
             "ref": d.ref, "assigne_id": t.assigne_id} for t, d in db.execute(q).all()]


@router.get("/facturation")
def facturation(user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(m.Dossier).where(m.Dossier.cabinet_id == user.cabinet_id).order_by(m.Dossier.updated_at.desc())
    out = []
    for d in db.scalars(q).all():
        f = d.facture or m.Facture(honoraires=0, commission_banque=0, statut="À venir", numero="")
        out.append({"dossier_id": d.id, "ref": d.ref, "nom": nom_dossier(d), "etape": d.etape,
                    "honoraires": f.honoraires or 0, "commission_banque": f.commission_banque or 0,
                    "statut": f.statut, "numero": f.numero, "date_emission": f.date_emission,
                    "date_paiement": f.date_paiement, "date_deblocage_fonds": f.date_deblocage_fonds})
    return out


@router.post("/simulations/capacite")
def sim_capacite(s: SimulationCapaciteIn, user: m.User = Depends(current_user)):
    cab = user.cabinet
    r = capacite_emprunt(s.revenus, s.charges, s.taux, s.duree_mois, s.taux_assurance, cab.plafond_endettement)
    taux_notaire = estimation_frais_notaire(100_000, s.nature) / 100_000
    r["prix_accessible"] = (r["capacite"] + s.apport) / (1 + taux_notaire)
    r["plafond"] = cab.plafond_endettement
    return r


@router.post("/simulations/pret")
def sim_pret(s: SimulationPretIn, user: m.User = Depends(current_user)):
    e = echeancier(Pret("Simulation", s.montant, s.taux, s.duree_mois, s.type, s.differe_mois, s.differe_type, s.taux_assurance))
    return {"mensualite_max": round(e.mensualite_max, 2), "mensualite": round(e.mensualite_amortissement, 2),
            "cout_interets": round(e.total_interets, 2), "cout_assurance": round(e.total_assurance, 2)}


# ---------------------------------------------------------------- RGPD
@router.get("/rgpd/export/{dossier_id}")
def rgpd_export(dossier_id: int, request: Request, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    """Droit d'accès / portabilité : toutes les données du dossier au format JSON."""
    d = get_dossier(dossier_id, db, user)
    log(db, user, "rgpd_export", "dossier", d.id, request=request)
    db.commit()
    data = detail(d)
    data.pop("analyse", None)
    return data


@router.delete("/rgpd/effacer/{dossier_id}")
def rgpd_effacer(dossier_id: int, confirmation: str, request: Request, user: m.User = Depends(admin_user), db: Session = Depends(get_db)):
    """Droit à l'effacement : suppression définitive du dossier et de ses pièces."""
    d = get_dossier(dossier_id, db, user)
    if confirmation != d.ref:
        raise HTTPException(422, "Confirmation incorrecte : saisissez la référence exacte du dossier.")
    shutil.rmtree(UPLOAD_DIR / str(d.cabinet_id) / str(d.id), ignore_errors=True)
    ref = d.ref
    db.delete(d)
    log(db, user, "rgpd_effacement", "dossier", dossier_id, {"ref": ref}, request)
    db.commit()
    return {"ok": True}


@router.get("/rgpd/a-purger")
def rgpd_a_purger(user: m.User = Depends(admin_user), db: Session = Depends(get_db)):
    """Dossiers inactifs au-delà de la durée de conservation fixée par le cabinet."""
    limite = date.today() - timedelta(days=30.44 * user.cabinet.duree_conservation_mois)
    q = select(m.Dossier).where(m.Dossier.cabinet_id == user.cabinet_id)
    return [{"id": d.id, "ref": d.ref, "nom": nom_dossier(d), "updated_at": d.updated_at, "etape": d.etape}
            for d in db.scalars(q).all() if d.updated_at.date() < limite]


@router.get("/audit")
def audit(dossier_id: int | None = None, limite: int = 200, user: m.User = Depends(admin_user), db: Session = Depends(get_db)):
    q = select(m.AuditLog).where(m.AuditLog.cabinet_id == user.cabinet_id)
    if dossier_id:
        q = q.where(m.AuditLog.entite == "dossier", m.AuditLog.entite_id == dossier_id)
    rows = db.scalars(q.order_by(m.AuditLog.id.desc()).limit(min(limite, 1000))).all()
    return [{"id": a.id, "date": a.created_at, "utilisateur": a.user_email, "action": a.action,
             "entite": a.entite, "entite_id": a.entite_id, "details": a.details, "ip": a.ip} for a in rows]
