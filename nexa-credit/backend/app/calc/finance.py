"""Moteur de calcul du crédit immobilier.

Fonctions pures, sans accès base de données, pour pouvoir être testées
et réutilisées (API, génération de synthèse, futur moteur Cred'IA).

Conventions :
- taux exprimés en pourcentage annuel (3.35 = 3,35 %) ;
- durées en mois ;
- assurance calculée sur le capital initial (cas le plus courant en
  contrat groupe ; la délégation sur capital restant dû n'est pas gérée).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

TypePret = Literal["amortissable", "in_fine", "ptz", "relais"]
TypeDiffere = Literal["aucun", "partiel", "total"]


@dataclass
class Pret:
    libelle: str
    montant: float
    taux: float  # % annuel nominal
    duree_mois: int
    type: TypePret = "amortissable"
    differe_mois: int = 0
    differe_type: TypeDiffere = "aucun"
    taux_assurance: float = 0.0  # % annuel sur capital initial


@dataclass
class Ligne:
    mois: int
    interets: float
    capital: float
    assurance: float
    echeance: float  # hors assurance
    crd: float  # capital restant dû après l'échéance


@dataclass
class Echeancier:
    pret: Pret
    lignes: list[Ligne] = field(default_factory=list)

    @property
    def total_interets(self) -> float:
        return sum(l.interets for l in self.lignes)

    @property
    def total_assurance(self) -> float:
        return sum(l.assurance for l in self.lignes)

    @property
    def mensualite_max(self) -> float:
        return max((l.echeance + l.assurance for l in self.lignes), default=0.0)

    @property
    def mensualite_amortissement(self) -> float:
        """Échéance (assurance comprise) de la phase d'amortissement."""
        if not self.lignes:
            return 0.0
        if self.pret.type in ("in_fine", "relais"):
            l = self.lignes[0]
        else:
            differe = self.pret.differe_mois if self.pret.differe_type != "aucun" else 0
            l = self.lignes[min(len(self.lignes) - 1, differe)]
        return l.echeance + l.assurance


def mensualite_constante(capital: float, taux_annuel: float, n_mois: int) -> float:
    if capital <= 0 or n_mois <= 0:
        return 0.0
    r = taux_annuel / 100 / 12
    if r == 0:
        return capital / n_mois
    return capital * r / (1 - (1 + r) ** -n_mois)


def echeancier(p: Pret) -> Echeancier:
    """Tableau d'amortissement mensuel.

    - amortissable / ptz : différé partiel (intérêts seuls) ou total
      (intérêts capitalisés) puis échéances constantes ;
    - in_fine / relais : intérêts payés chaque mois (ou capitalisés si
      différé total), capital remboursé à la dernière échéance.
    """
    e = Echeancier(pret=p)
    n = int(p.duree_mois)
    if p.montant <= 0 or n <= 0:
        return e
    r = p.taux / 100 / 12
    assu = p.montant * p.taux_assurance / 100 / 12
    crd = float(p.montant)

    if p.type in ("in_fine", "relais"):
        for m in range(1, n + 1):
            i = crd * r
            if p.differe_type == "total":
                crd += i
                ech, cap = 0.0, 0.0
                if m == n:
                    ech, cap = crd, crd
                    crd = 0.0
                e.lignes.append(Ligne(m, i, cap, assu, ech, crd))
            else:
                cap = crd if m == n else 0.0
                ech = i + cap
                crd -= cap
                e.lignes.append(Ligne(m, i, cap, assu, ech, crd))
        return e

    differe = max(0, min(int(p.differe_mois), n - 1)) if p.differe_type != "aucun" else 0
    for m in range(1, differe + 1):
        i = crd * r
        if p.differe_type == "total":
            crd += i
            e.lignes.append(Ligne(m, i, 0.0, assu, 0.0, crd))
        else:
            e.lignes.append(Ligne(m, i, 0.0, assu, i, crd))
    reste = n - differe
    mens = mensualite_constante(crd, p.taux, reste)
    for k in range(1, reste + 1):
        i = crd * r
        cap = mens - i
        if k == reste:
            cap = crd
            mens_k = cap + i
        else:
            mens_k = mens
        crd -= cap
        e.lignes.append(Ligne(differe + k, i, cap, assu, mens_k, max(0.0, crd)))
    return e


def estimation_frais_notaire(prix: float, nature: str) -> float:
    """Estimation grossière : ~7,8 % dans l'ancien, ~2,5 % dans le neuf/VEFA.

    À remplacer par le décompte du notaire dès qu'il est disponible.
    """
    if prix <= 0:
        return 0.0
    taux = 0.025 if nature in ("neuf", "vefa", "construction") else 0.078
    return round(prix * taux, 2)


def mensualites_agregees(echeanciers: list[Echeancier]) -> list[float]:
    """Charge mensuelle totale (assurance comprise) mois par mois.

    La dernière échéance d'un prêt in fine / relais (remboursement du
    capital, en principe par la vente) est exclue.
    """
    n = max((len(e.lignes) for e in echeanciers), default=0)
    res = [0.0] * n
    for e in echeanciers:
        for l in e.lignes:
            ech = l.echeance
            if e.pret.type in ("in_fine", "relais") and l.capital > 0:
                ech -= l.capital
            res[l.mois - 1] += ech + l.assurance
    return res


def taeg(capital_net: float, flux_mensuels: list[float]) -> float:
    """TAEG actuariel estimé (en %) : taux annuel équivalent au taux
    mensuel qui égalise le capital réellement mis à disposition et les
    flux remboursés. Résolution par dichotomie.
    """
    if capital_net <= 0 or not flux_mensuels or sum(flux_mensuels) <= capital_net:
        return 0.0

    def van(i: float) -> float:
        return sum(f / (1 + i) ** (k + 1) for k, f in enumerate(flux_mensuels)) - capital_net

    lo, hi = 0.0, 0.05
    for _ in range(200):
        mid = (lo + hi) / 2
        if van(mid) > 0:
            lo = mid
        else:
            hi = mid
    return ((1 + (lo + hi) / 2) ** 12 - 1) * 100


def capacite_emprunt(revenus: float, charges: float, taux: float, duree_mois: int,
                     taux_assurance: float, plafond: float = 0.35) -> dict:
    mens_max = max(0.0, revenus * plafond - charges)
    r = taux / 100 / 12
    if duree_mois <= 0:
        return {"mensualite_max": mens_max, "capacite": 0.0}
    facteur = (1 / duree_mois if r == 0 else r / (1 - (1 + r) ** -duree_mois)) + taux_assurance / 100 / 12
    return {"mensualite_max": mens_max, "capacite": mens_max / facteur if facteur else 0.0}
