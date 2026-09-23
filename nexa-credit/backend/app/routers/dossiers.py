from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..audit import log
from ..calc.analyse import analyse_complete, mail_relance_pieces, synthese_bancaire
from ..calc.finance import Pret, echeancier
from ..db import get_db
from ..deps import current_user, get_dossier
from ..schemas import (
    DocumentOut, DossierCreate, DossierPatch, DossierResume, EmprunteurBase, EmprunteurOut, EmprunteurPatch,
    FactureOut, FacturePatch, OffreBase, OffreOut, OffrePatch, PretBase, PretOut, PretPatch, TacheIn, TacheOut,
    TachePatch,
)

router = APIRouter(prefix="/api/dossiers", tags=["dossiers"])


def nom_dossier(d: m.Dossier) -> str:
    if not d.emprunteurs:
        return "Sans emprunteur"
    noms = []
    for e in d.emprunteurs:
        if e.nom not in noms:
            noms.append(e.nom)
    prenoms = " & ".join(e.prenom for e in d.emprunteurs if e.prenom)
    return " / ".join(noms) + (f" ({prenoms})" if prenoms else "")


def resume(d: m.Dossier) -> DossierResume:
    a = analyse_complete(d, d_cab(d))
    pieces = a["pieces"]
    return DossierResume(
        id=d.id, ref=d.ref, etape=d.etape, nom=nom_dossier(d), projet_type=d.projet_type, ville=d.ville,
        montant=a["plan"]["total_emprunte"], mensualite=a["plan"]["mensualite_max"],
        taux_endettement=a["ratios"]["taux_endettement"],
        alertes_bloquantes=sum(1 for c in a["controles"] if c["niveau"] == "bloquant"),
        alertes=sum(1 for c in a["controles"] if c["niveau"] in ("bloquant", "attention")),
        pieces_ok=sum(1 for p in pieces if p["statut"] == "valide"), pieces_total=len(pieces),
        courtier=d.courtier.nom if d.courtier else None, updated_at=d.updated_at,
        date_condition_suspensive=d.date_condition_suspensive,
    )


def d_cab(d: m.Dossier) -> m.Cabinet:
    from sqlalchemy.orm import object_session
    return object_session(d).get(m.Cabinet, d.cabinet_id)


def detail(d: m.Dossier) -> dict:
    return {
        "id": d.id, "ref": d.ref, "nom": nom_dossier(d), "created_at": d.created_at, "updated_at": d.updated_at,
        **{k: getattr(d, k) for k in DossierPatch.model_fields},
        "emprunteurs": [EmprunteurOut.model_validate(e) for e in d.emprunteurs],
        "prets": [PretOut.model_validate(p) for p in d.prets],
        "offres": [OffreOut.model_validate(o) for o in d.offres],
        "documents": [DocumentOut.model_validate(x) for x in d.documents],
        "taches": [TacheOut.model_validate(t) for t in d.taches],
        "facture": FactureOut.model_validate(d.facture) if d.facture else None,
        "analyse": analyse_complete(d, d_cab(d)),
    }


def _touch(d: m.Dossier) -> None:
    d.updated_at = m.now()


# ---------------------------------------------------------------- dossiers
@router.get("", response_model=list[DossierResume])
def lister(archives: bool = False, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(m.Dossier).where(m.Dossier.cabinet_id == user.cabinet_id, m.Dossier.archive == archives).order_by(m.Dossier.updated_at.desc())
    return [resume(d) for d in db.scalars(q).all()]


def _nouvelle_ref(db: Session, cabinet_id: int) -> str:
    annee = date.today().year
    n = db.scalar(select(func.count(m.Dossier.id)).where(m.Dossier.cabinet_id == cabinet_id, m.Dossier.ref.like(f"D-{annee}-%"))) or 0
    while True:
        n += 1
        ref = f"D-{annee}-{n:04d}"
        if not db.scalar(select(m.Dossier.id).where(m.Dossier.cabinet_id == cabinet_id, m.Dossier.ref == ref)):
            return ref


@router.post("")
def creer(data: DossierCreate, request: Request, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    d = m.Dossier(cabinet_id=user.cabinet_id, ref=_nouvelle_ref(db, user.cabinet_id), courtier_id=user.id)
    for k, v in data.model_dump(exclude_unset=True, exclude={"emprunteurs"}).items():
        setattr(d, k, v)
    for e in data.emprunteurs:
        d.emprunteurs.append(m.Emprunteur(**e.model_dump()))
    d.prets.append(m.PretLigne(libelle="Prêt principal", type="amortissable", ajuste=True, taux=3.3, duree_mois=300, taux_assurance=0.10))
    d.facture = m.Facture(honoraires=d.honoraires)
    db.add(d)
    db.flush()
    log(db, user, "dossier_cree", "dossier", d.id, {"ref": d.ref}, request)
    db.commit()
    return detail(d)


@router.get("/{dossier_id}")
def lire(dossier_id: int, request: Request, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_dossier(dossier_id, db, user)
    # Une trace de consultation par utilisateur et par dossier toutes les 30 minutes suffit.
    recent = db.scalar(select(m.AuditLog.id).where(
        m.AuditLog.user_id == user.id, m.AuditLog.action == "dossier_consulte", m.AuditLog.entite_id == d.id,
        m.AuditLog.created_at >= m.now() - timedelta(minutes=30)).limit(1))
    if not recent:
        log(db, user, "dossier_consulte", "dossier", d.id, request=request)
        db.commit()
    return detail(d)


@router.patch("/{dossier_id}")
def modifier(dossier_id: int, data: DossierPatch, request: Request, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_dossier(dossier_id, db, user)
    changes = data.model_dump(exclude_unset=True)
    if "courtier_id" in changes and changes["courtier_id"] is not None:
        u = db.get(m.User, changes["courtier_id"])
        if not u or u.cabinet_id != user.cabinet_id:
            raise HTTPException(422, "Courtier inconnu.")
    for k, v in changes.items():
        setattr(d, k, v)
    _touch(d)
    if "etape" in changes:
        log(db, user, "etape", "dossier", d.id, {"etape": changes["etape"]}, request)
    else:
        log(db, user, "dossier_modifie", "dossier", d.id, {"champs": list(changes)}, request)
    db.commit()
    return detail(d)


@router.get("/{dossier_id}/synthese")
def synthese(dossier_id: int, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_dossier(dossier_id, db, user)
    return {"texte": synthese_bancaire(d, d_cab(d), user.nom), "relance": mail_relance_pieces(d, user.nom)}


@router.get("/{dossier_id}/echeancier/{pret_id}")
def tableau_amortissement(dossier_id: int, pret_id: int, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_dossier(dossier_id, db, user)
    lignes = next((l for l in analyse_complete(d, d_cab(d))["plan"]["prets"] if l["id"] == pret_id), None)
    if not lignes:
        raise HTTPException(404, "Prêt introuvable.")
    e = echeancier(Pret(lignes["libelle"], lignes["montant"], lignes["taux"], lignes["duree_mois"], lignes["type"],
                        lignes["differe_mois"], lignes["differe_type"], lignes["taux_assurance"]))
    return [{"mois": l.mois, "interets": round(l.interets, 2), "capital": round(l.capital, 2),
             "assurance": round(l.assurance, 2), "echeance": round(l.echeance, 2), "crd": round(l.crd, 2)} for l in e.lignes]


# ---------------------------------------------------------------- sous-ressources génériques
def _sub(db: Session, model, obj_id: int, d: m.Dossier):
    o = db.get(model, obj_id)
    if not o or o.dossier_id != d.id:
        raise HTTPException(404, "Élément introuvable.")
    return o


def _crud(nom: str, model, base, patch, out, rel: str):
    @router.post(f"/{{dossier_id}}/{nom}", response_model=out, name=f"creer_{nom}")
    def create(dossier_id: int, data: base, request: Request, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
        d = get_dossier(dossier_id, db, user)
        o = model(**data.model_dump())
        getattr(d, rel).append(o)
        _touch(d)
        db.flush()
        log(db, user, f"{nom}_ajout", "dossier", d.id, {"id": o.id}, request)
        db.commit()
        return o

    @router.patch(f"/{{dossier_id}}/{nom}/{{obj_id}}", response_model=out, name=f"modifier_{nom}")
    def update(dossier_id: int, obj_id: int, data: patch, request: Request, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
        d = get_dossier(dossier_id, db, user)
        o = _sub(db, model, obj_id, d)
        changes = data.model_dump(exclude_unset=True)
        for k, v in changes.items():
            setattr(o, k, v)
        _touch(d)
        log(db, user, f"{nom}_modif", "dossier", d.id, {"id": o.id, "champs": list(changes)}, request)
        db.commit()
        return o

    @router.delete(f"/{{dossier_id}}/{nom}/{{obj_id}}", name=f"supprimer_{nom}")
    def delete(dossier_id: int, obj_id: int, request: Request, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
        d = get_dossier(dossier_id, db, user)
        o = _sub(db, model, obj_id, d)
        db.delete(o)
        _touch(d)
        log(db, user, f"{nom}_suppr", "dossier", d.id, {"id": obj_id}, request)
        db.commit()
        return {"ok": True}


_crud("emprunteurs", m.Emprunteur, EmprunteurBase, EmprunteurPatch, EmprunteurOut, "emprunteurs")
_crud("prets", m.PretLigne, PretBase, PretPatch, PretOut, "prets")
_crud("offres", m.Offre, OffreBase, OffrePatch, OffreOut, "offres")
_crud("taches", m.Tache, TacheIn, TachePatch, TacheOut, "taches")


@router.patch("/{dossier_id}/facture", response_model=FactureOut)
def facture(dossier_id: int, data: FacturePatch, request: Request, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    d = get_dossier(dossier_id, db, user)
    if not d.facture:
        d.facture = m.Facture()
    changes = data.model_dump(exclude_unset=True)
    f = d.facture
    futur_statut = changes.get("statut", f.statut)
    deblocage = changes.get("date_deblocage_fonds", f.date_deblocage_fonds)
    # Art. L519-6 CMF : aucun versement de l'emprunteur avant le déblocage des fonds.
    if futur_statut in ("Facturé", "Payé") and (changes.get("honoraires", f.honoraires) or 0) > 0 and not deblocage:
        raise HTTPException(422, "Renseignez la date de déblocage des fonds avant de facturer des honoraires au client (art. L519-6 CMF).")
    for k, v in changes.items():
        setattr(f, k, v)
    _touch(d)
    log(db, user, "facture_modif", "dossier", d.id, {"champs": list(changes)}, request)
    db.commit()
    return f
