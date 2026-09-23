from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Contrat = Literal["CDI", "Fonctionnaire", "CDD", "Intérim", "TNS", "Profession libérale", "Dirigeant", "Retraité", "Sans emploi"]
TypeProjet = Literal["Résidence principale", "Résidence secondaire", "Locatif", "Professionnel"]
Nature = Literal["ancien", "neuf", "vefa", "construction"]
TypePret = Literal["amortissable", "in_fine", "ptz", "relais"]
Differe = Literal["aucun", "partiel", "total"]
Etape = Literal["Découverte", "Montage", "En banque", "Accord", "Offre émise", "Signé notaire", "Facturé", "Abandonné"]
StatutOffre = Literal["Envoyé", "Étude en cours", "Accord de principe", "Accord ferme", "Offre émise", "Offre acceptée", "Refus"]
StatutFacture = Literal["À venir", "À facturer", "Facturé", "Payé"]
Money = Field(default=None, ge=0, le=100_000_000)


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- auth / users
class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


class SetupIn(BaseModel):
    cabinet: str = Field(min_length=2, max_length=200)
    orias: str | None = Field(default=None, max_length=20)
    nom: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(max_length=200)


class UserOut(ORM):
    id: int
    email: str
    nom: str
    role: str
    actif: bool


class UserIn(BaseModel):
    email: EmailStr
    nom: str = Field(min_length=2, max_length=200)
    role: Literal["admin", "courtier", "assistant"] = "courtier"
    password: str = Field(max_length=200)


class UserPatch(BaseModel):
    nom: str | None = None
    role: Literal["admin", "courtier", "assistant"] | None = None
    actif: bool | None = None


class PasswordIn(BaseModel):
    ancien: str
    nouveau: str = Field(max_length=200)


class CabinetOut(ORM):
    id: int
    nom: str
    orias: str | None
    plafond_endettement: float
    duree_max_mois: int
    duree_max_mois_neuf: int
    reste_a_vivre_base: float
    reste_a_vivre_par_personne: float
    ponderation_loyers: float
    taux_usure: dict
    taux_usure_trimestre: str | None
    duree_conservation_mois: int


class CabinetPatch(BaseModel):
    nom: str | None = None
    orias: str | None = None
    plafond_endettement: float | None = Field(default=None, gt=0, lt=1)
    duree_max_mois: int | None = Field(default=None, gt=0, le=480)
    duree_max_mois_neuf: int | None = Field(default=None, gt=0, le=480)
    reste_a_vivre_base: float | None = Field(default=None, ge=0)
    reste_a_vivre_par_personne: float | None = Field(default=None, ge=0)
    ponderation_loyers: float | None = Field(default=None, ge=0, le=1)
    taux_usure: dict[Literal["moins_10_ans", "10_20_ans", "20_ans_et_plus"], float] | None = None
    taux_usure_trimestre: str | None = None
    duree_conservation_mois: int | None = Field(default=None, gt=0, le=240)


# ---------------------------------------------------------------- dossier
class EmprunteurBase(BaseModel):
    civilite: str = ""
    nom: str = Field(min_length=1, max_length=120)
    prenom: str = ""
    date_naissance: date | None = None
    email: str = ""
    telephone: str = ""
    profession: str = ""
    employeur: str = ""
    contrat: Contrat = "CDI"
    anciennete_mois: int = Field(default=0, ge=0, le=720)
    periode_essai_validee: bool = True
    revenus_nets_mensuels: float = Field(default=0, ge=0, le=1_000_000)
    nb_mois_salaire: float = Field(default=12, ge=12, le=16)
    fumeur: bool = False


class EmprunteurOut(EmprunteurBase, ORM):
    id: int


class EmprunteurPatch(BaseModel):
    civilite: str | None = None
    nom: str | None = Field(default=None, min_length=1, max_length=120)
    prenom: str | None = None
    date_naissance: date | None = None
    email: str | None = None
    telephone: str | None = None
    profession: str | None = None
    employeur: str | None = None
    contrat: Contrat | None = None
    anciennete_mois: int | None = Field(default=None, ge=0, le=720)
    periode_essai_validee: bool | None = None
    revenus_nets_mensuels: float | None = Field(default=None, ge=0, le=1_000_000)
    nb_mois_salaire: float | None = Field(default=None, ge=12, le=16)
    fumeur: bool | None = None


class PretBase(BaseModel):
    ordre: int = 0
    libelle: str = Field(default="Prêt principal", max_length=80)
    type: TypePret = "amortissable"
    ajuste: bool = False
    montant: float = Field(default=0, ge=0, le=100_000_000)
    taux: float = Field(default=0, ge=0, le=20)
    duree_mois: int = Field(default=300, gt=0, le=480)
    differe_mois: int = Field(default=0, ge=0, le=300)
    differe_type: Differe = "aucun"
    taux_assurance: float = Field(default=0, ge=0, le=5)


class PretOut(PretBase, ORM):
    id: int


class PretPatch(BaseModel):
    ordre: int | None = None
    libelle: str | None = None
    type: TypePret | None = None
    ajuste: bool | None = None
    montant: float | None = Field(default=None, ge=0, le=100_000_000)
    taux: float | None = Field(default=None, ge=0, le=20)
    duree_mois: int | None = Field(default=None, gt=0, le=480)
    differe_mois: int | None = Field(default=None, ge=0, le=300)
    differe_type: Differe | None = None
    taux_assurance: float | None = Field(default=None, ge=0, le=5)


class OffreBase(BaseModel):
    banque: str = Field(min_length=1, max_length=120)
    agence: str = ""
    interlocuteur: str = ""
    statut: StatutOffre = "Envoyé"
    date_envoi: date | None = None
    date_reponse: date | None = None
    taux: float = Field(default=0, ge=0, le=20)
    duree_mois: int = Field(default=300, gt=0, le=480)
    taux_assurance: float = Field(default=0, ge=0, le=5)
    frais_dossier: float = Field(default=0, ge=0)
    garantie_type: str = ""
    garantie_cout: float = Field(default=0, ge=0)
    ira: str = ""
    domiciliation: str = ""
    modularite: str = ""
    produits_annexes: str = ""
    commentaire: str = ""


class OffreOut(OffreBase, ORM):
    id: int


class OffrePatch(BaseModel):
    banque: str | None = None
    agence: str | None = None
    interlocuteur: str | None = None
    statut: StatutOffre | None = None
    date_envoi: date | None = None
    date_reponse: date | None = None
    taux: float | None = Field(default=None, ge=0, le=20)
    duree_mois: int | None = Field(default=None, gt=0, le=480)
    taux_assurance: float | None = Field(default=None, ge=0, le=5)
    frais_dossier: float | None = Field(default=None, ge=0)
    garantie_type: str | None = None
    garantie_cout: float | None = Field(default=None, ge=0)
    ira: str | None = None
    domiciliation: str | None = None
    modularite: str | None = None
    produits_annexes: str | None = None
    commentaire: str | None = None


class DocumentOut(ORM):
    id: int
    emprunteur_id: int | None
    categorie: str
    statut: str
    nom_fichier: str
    mime: str
    taille: int
    commentaire: str
    source: str
    created_at: datetime


class DocumentPatch(BaseModel):
    categorie: str | None = None
    statut: Literal["recu", "valide", "refuse"] | None = None
    commentaire: str | None = None


class TacheIn(BaseModel):
    libelle: str = Field(min_length=1, max_length=300)
    echeance: date | None = None
    assigne_id: int | None = None


class TacheOut(ORM):
    id: int
    dossier_id: int
    libelle: str
    echeance: date | None
    faite: bool
    assigne_id: int | None


class TachePatch(BaseModel):
    libelle: str | None = None
    echeance: date | None = None
    faite: bool | None = None
    assigne_id: int | None = None


class FactureOut(ORM):
    honoraires: float
    commission_banque: float
    statut: str
    numero: str
    date_emission: date | None
    date_paiement: date | None
    date_deblocage_fonds: date | None


class FacturePatch(BaseModel):
    honoraires: float | None = Field(default=None, ge=0)
    commission_banque: float | None = Field(default=None, ge=0)
    statut: StatutFacture | None = None
    numero: str | None = None
    date_emission: date | None = None
    date_paiement: date | None = None
    date_deblocage_fonds: date | None = None


DOSSIER_FIELDS = [
    "situation_familiale", "enfants", "epargne", "loyer_actuel", "credits_conserves", "pension_versee",
    "autres_revenus", "revenus_locatifs_existants", "projet_type", "projet_nature", "ville", "code_postal",
    "prix", "travaux", "frais_notaire", "garantie", "frais_dossier", "honoraires", "apport", "loyer_attendu",
    "date_compromis", "date_condition_suspensive", "date_signature", "notes", "consentement_rgpd", "etape",
    "courtier_id", "archive",
]


class DossierPatch(BaseModel):
    situation_familiale: str | None = None
    enfants: int | None = Field(default=None, ge=0, le=20)
    epargne: float | None = Money
    loyer_actuel: float | None = Money
    credits_conserves: float | None = Money
    pension_versee: float | None = Money
    autres_revenus: float | None = Money
    revenus_locatifs_existants: float | None = Money
    projet_type: TypeProjet | None = None
    projet_nature: Nature | None = None
    ville: str | None = None
    code_postal: str | None = None
    prix: float | None = Money
    travaux: float | None = Money
    frais_notaire: float | None = Money
    garantie: float | None = Money
    frais_dossier: float | None = Money
    honoraires: float | None = Money
    apport: float | None = Money
    loyer_attendu: float | None = Money
    date_compromis: date | None = None
    date_condition_suspensive: date | None = None
    date_signature: date | None = None
    notes: str | None = Field(default=None, max_length=20000)
    consentement_rgpd: bool | None = None
    etape: Etape | None = None
    courtier_id: int | None = None
    archive: bool | None = None


class DossierCreate(DossierPatch):
    emprunteurs: list[EmprunteurBase] = Field(default_factory=list)


class DossierResume(BaseModel):
    id: int
    ref: str
    etape: str
    nom: str
    projet_type: str
    ville: str
    montant: float
    mensualite: float
    taux_endettement: float
    alertes_bloquantes: int
    alertes: int
    pieces_ok: int
    pieces_total: int
    courtier: str | None
    updated_at: datetime
    date_condition_suspensive: date | None


class SimulationCapaciteIn(BaseModel):
    revenus: float = Field(ge=0)
    charges: float = Field(default=0, ge=0)
    taux: float = Field(ge=0, le=20)
    duree_mois: int = Field(gt=0, le=480)
    taux_assurance: float = Field(default=0, ge=0, le=5)
    apport: float = Field(default=0, ge=0)
    nature: Nature = "ancien"


class SimulationPretIn(BaseModel):
    montant: float = Field(gt=0)
    taux: float = Field(ge=0, le=20)
    duree_mois: int = Field(gt=0, le=480)
    type: TypePret = "amortissable"
    differe_mois: int = Field(default=0, ge=0, le=300)
    differe_type: Differe = "aucun"
    taux_assurance: float = Field(default=0, ge=0, le=5)
