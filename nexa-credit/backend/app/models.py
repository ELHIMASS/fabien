from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


ETAPES = ["Découverte", "Montage", "En banque", "Accord", "Offre émise", "Signé notaire", "Facturé", "Abandonné"]


class Cabinet(Base):
    __tablename__ = "cabinets"
    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(200))
    orias: Mapped[str | None] = mapped_column(String(20))
    # Paramètres métier modifiables par l'administrateur du cabinet.
    plafond_endettement: Mapped[float] = mapped_column(Float, default=0.35)
    duree_max_mois: Mapped[int] = mapped_column(Integer, default=300)
    duree_max_mois_neuf: Mapped[int] = mapped_column(Integer, default=324)
    reste_a_vivre_base: Mapped[float] = mapped_column(Float, default=800)
    reste_a_vivre_par_personne: Mapped[float] = mapped_column(Float, default=300)
    ponderation_loyers: Mapped[float] = mapped_column(Float, default=0.70)
    # Taux d'usure publiés chaque trimestre par la Banque de France : à saisir, jamais devinés.
    taux_usure: Mapped[dict] = mapped_column(JSON, default=dict)
    taux_usure_trimestre: Mapped[str | None] = mapped_column(String(20))
    duree_conservation_mois: Mapped[int] = mapped_column(Integer, default=60)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    cabinet_id: Mapped[int] = mapped_column(ForeignKey("cabinets.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    nom: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20), default="courtier")  # admin | courtier | assistant
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    cabinet: Mapped[Cabinet] = relationship()


class Dossier(Base):
    __tablename__ = "dossiers"
    __table_args__ = (UniqueConstraint("cabinet_id", "ref"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    cabinet_id: Mapped[int] = mapped_column(ForeignKey("cabinets.id", ondelete="CASCADE"), index=True)
    ref: Mapped[str] = mapped_column(String(30))
    etape: Mapped[str] = mapped_column(String(30), default="Découverte")
    courtier_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    situation_familiale: Mapped[str] = mapped_column(String(30), default="Célibataire")
    enfants: Mapped[int] = mapped_column(Integer, default=0)
    epargne: Mapped[float] = mapped_column(Float, default=0)
    loyer_actuel: Mapped[float] = mapped_column(Float, default=0)
    credits_conserves: Mapped[float] = mapped_column(Float, default=0)  # mensualités conservées
    pension_versee: Mapped[float] = mapped_column(Float, default=0)
    autres_revenus: Mapped[float] = mapped_column(Float, default=0)
    revenus_locatifs_existants: Mapped[float] = mapped_column(Float, default=0)

    projet_type: Mapped[str] = mapped_column(String(40), default="Résidence principale")
    projet_nature: Mapped[str] = mapped_column(String(20), default="ancien")  # ancien|neuf|vefa|construction
    ville: Mapped[str] = mapped_column(String(120), default="")
    code_postal: Mapped[str] = mapped_column(String(10), default="")
    prix: Mapped[float] = mapped_column(Float, default=0)
    travaux: Mapped[float] = mapped_column(Float, default=0)
    frais_notaire: Mapped[float | None] = mapped_column(Float)  # None = estimation automatique
    garantie: Mapped[float] = mapped_column(Float, default=0)
    frais_dossier: Mapped[float] = mapped_column(Float, default=0)
    honoraires: Mapped[float] = mapped_column(Float, default=0)
    apport: Mapped[float] = mapped_column(Float, default=0)
    loyer_attendu: Mapped[float] = mapped_column(Float, default=0)
    date_compromis: Mapped[date | None] = mapped_column(Date)
    date_condition_suspensive: Mapped[date | None] = mapped_column(Date)
    date_signature: Mapped[date | None] = mapped_column(Date)

    notes: Mapped[str] = mapped_column(Text, default="")
    consentement_rgpd: Mapped[bool] = mapped_column(Boolean, default=False)
    archive: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    emprunteurs: Mapped[list[Emprunteur]] = relationship(cascade="all, delete-orphan", order_by="Emprunteur.id")
    prets: Mapped[list[PretLigne]] = relationship(cascade="all, delete-orphan", order_by="PretLigne.ordre")
    offres: Mapped[list[Offre]] = relationship(cascade="all, delete-orphan", order_by="Offre.id")
    documents: Mapped[list[Document]] = relationship(cascade="all, delete-orphan", order_by="Document.id")
    taches: Mapped[list[Tache]] = relationship(cascade="all, delete-orphan", order_by="Tache.echeance")
    facture: Mapped[Facture | None] = relationship(cascade="all, delete-orphan", uselist=False)
    courtier: Mapped[User | None] = relationship()


class Emprunteur(Base):
    __tablename__ = "emprunteurs"
    id: Mapped[int] = mapped_column(primary_key=True)
    dossier_id: Mapped[int] = mapped_column(ForeignKey("dossiers.id", ondelete="CASCADE"), index=True)
    civilite: Mapped[str] = mapped_column(String(10), default="")
    nom: Mapped[str] = mapped_column(String(120))
    prenom: Mapped[str] = mapped_column(String(120), default="")
    date_naissance: Mapped[date | None] = mapped_column(Date)
    email: Mapped[str] = mapped_column(String(254), default="")
    telephone: Mapped[str] = mapped_column(String(30), default="")
    profession: Mapped[str] = mapped_column(String(120), default="")
    employeur: Mapped[str] = mapped_column(String(160), default="")
    contrat: Mapped[str] = mapped_column(String(30), default="CDI")
    anciennete_mois: Mapped[int] = mapped_column(Integer, default=0)
    periode_essai_validee: Mapped[bool] = mapped_column(Boolean, default=True)
    revenus_nets_mensuels: Mapped[float] = mapped_column(Float, default=0)
    nb_mois_salaire: Mapped[float] = mapped_column(Float, default=12)
    fumeur: Mapped[bool] = mapped_column(Boolean, default=False)


class PretLigne(Base):
    """Ligne du plan de financement : prêt principal, PTZ, prêt employeur, relais..."""
    __tablename__ = "prets"
    id: Mapped[int] = mapped_column(primary_key=True)
    dossier_id: Mapped[int] = mapped_column(ForeignKey("dossiers.id", ondelete="CASCADE"), index=True)
    ordre: Mapped[int] = mapped_column(Integer, default=0)
    libelle: Mapped[str] = mapped_column(String(80), default="Prêt principal")
    type: Mapped[str] = mapped_column(String(20), default="amortissable")
    # Si ajuste=True, le montant est calculé : besoin − apport − autres prêts (hors relais).
    ajuste: Mapped[bool] = mapped_column(Boolean, default=False)
    montant: Mapped[float] = mapped_column(Float, default=0)
    taux: Mapped[float] = mapped_column(Float, default=0)
    duree_mois: Mapped[int] = mapped_column(Integer, default=300)
    differe_mois: Mapped[int] = mapped_column(Integer, default=0)
    differe_type: Mapped[str] = mapped_column(String(10), default="aucun")
    taux_assurance: Mapped[float] = mapped_column(Float, default=0)


class Offre(Base):
    __tablename__ = "offres"
    id: Mapped[int] = mapped_column(primary_key=True)
    dossier_id: Mapped[int] = mapped_column(ForeignKey("dossiers.id", ondelete="CASCADE"), index=True)
    banque: Mapped[str] = mapped_column(String(120))
    agence: Mapped[str] = mapped_column(String(160), default="")
    interlocuteur: Mapped[str] = mapped_column(String(160), default="")
    statut: Mapped[str] = mapped_column(String(30), default="Envoyé")
    date_envoi: Mapped[date | None] = mapped_column(Date)
    date_reponse: Mapped[date | None] = mapped_column(Date)
    taux: Mapped[float] = mapped_column(Float, default=0)
    duree_mois: Mapped[int] = mapped_column(Integer, default=300)
    taux_assurance: Mapped[float] = mapped_column(Float, default=0)
    frais_dossier: Mapped[float] = mapped_column(Float, default=0)
    garantie_type: Mapped[str] = mapped_column(String(80), default="")
    garantie_cout: Mapped[float] = mapped_column(Float, default=0)
    ira: Mapped[str] = mapped_column(String(200), default="")
    domiciliation: Mapped[str] = mapped_column(String(200), default="")
    modularite: Mapped[str] = mapped_column(String(200), default="")
    produits_annexes: Mapped[str] = mapped_column(String(300), default="")
    commentaire: Mapped[str] = mapped_column(Text, default="")


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    dossier_id: Mapped[int] = mapped_column(ForeignKey("dossiers.id", ondelete="CASCADE"), index=True)
    emprunteur_id: Mapped[int | None] = mapped_column(ForeignKey("emprunteurs.id", ondelete="SET NULL"))
    categorie: Mapped[str] = mapped_column(String(40))
    statut: Mapped[str] = mapped_column(String(20), default="recu")  # recu | valide | refuse
    nom_fichier: Mapped[str] = mapped_column(String(255))
    chemin: Mapped[str] = mapped_column(String(500))
    mime: Mapped[str] = mapped_column(String(100))
    taille: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    commentaire: Mapped[str] = mapped_column(Text, default="")
    depose_par: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Tache(Base):
    __tablename__ = "taches"
    id: Mapped[int] = mapped_column(primary_key=True)
    dossier_id: Mapped[int] = mapped_column(ForeignKey("dossiers.id", ondelete="CASCADE"), index=True)
    libelle: Mapped[str] = mapped_column(String(300))
    echeance: Mapped[date | None] = mapped_column(Date)
    faite: Mapped[bool] = mapped_column(Boolean, default=False)
    assigne_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Facture(Base):
    __tablename__ = "factures"
    id: Mapped[int] = mapped_column(primary_key=True)
    dossier_id: Mapped[int] = mapped_column(ForeignKey("dossiers.id", ondelete="CASCADE"), unique=True)
    honoraires: Mapped[float] = mapped_column(Float, default=0)
    commission_banque: Mapped[float] = mapped_column(Float, default=0)
    statut: Mapped[str] = mapped_column(String(20), default="À venir")  # À venir | À facturer | Facturé | Payé
    numero: Mapped[str] = mapped_column(String(40), default="")
    date_emission: Mapped[date | None] = mapped_column(Date)
    date_paiement: Mapped[date | None] = mapped_column(Date)
    date_deblocage_fonds: Mapped[date | None] = mapped_column(Date)


class AuditLog(Base):
    __tablename__ = "audit"
    id: Mapped[int] = mapped_column(primary_key=True)
    cabinet_id: Mapped[int | None] = mapped_column(ForeignKey("cabinets.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    user_email: Mapped[str] = mapped_column(String(254), default="")
    action: Mapped[str] = mapped_column(String(40))
    entite: Mapped[str] = mapped_column(String(40), default="")
    entite_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
