"""Crée un cabinet de démonstration avec des dossiers FICTIFS.

    python -m app.demo  →  compte demo@nexa-credit.fr / DemoNexa2026!
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from . import models as m
from .db import Base, SessionLocal, engine
from .security import hash_password

EMAIL, MDP = "demo@nexa-credit.fr", "DemoNexa2026!"


def run() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    if db.scalar(select(m.User).where(m.User.email == EMAIL)):
        print("Démo déjà présente.")
        return
    cab = m.Cabinet(nom="Cabinet Démo (fictif)", orias="00000000")
    db.add(cab)
    db.flush()
    u = m.User(cabinet_id=cab.id, email=EMAIL, nom="Fabien Bernillon", role="admin", password_hash=hash_password(MDP))
    db.add(u)
    db.flush()
    t = date.today()

    def dossier(ref, etape, emps, prets, offres=(), taches=(), facture=None, **kw):
        d = m.Dossier(cabinet_id=cab.id, ref=ref, etape=etape, courtier_id=u.id, consentement_rgpd=True, **kw)
        d.emprunteurs = [m.Emprunteur(**e) for e in emps]
        d.prets = [m.PretLigne(ordre=i, **p) for i, p in enumerate(prets)]
        d.offres = [m.Offre(**o) for o in offres]
        d.taches = [m.Tache(**x) for x in taches]
        d.facture = m.Facture(**(facture or {"honoraires": kw.get("honoraires", 0)}))
        db.add(d)

    dossier("D-DEMO-0001", "En banque",
            [dict(nom="Durand", prenom="Martin", profession="Ingénieur méthodes", employeur="Industrie Rhône SAS", contrat="CDI", anciennete_mois=74, revenus_nets_mensuels=3250, nb_mois_salaire=13, date_naissance=date(1988, 4, 12)),
             dict(nom="Durand", prenom="Sophie", profession="Infirmière", employeur="Hospices Civils", contrat="Fonctionnaire", anciennete_mois=110, revenus_nets_mensuels=2480, date_naissance=date(1990, 9, 3))],
            [dict(libelle="Prêt principal", ajuste=True, taux=3.30, duree_mois=300, taux_assurance=0.09)],
            offres=[dict(banque="Banque A", statut="Accord de principe", taux=3.25, duree_mois=300, taux_assurance=0.10, frais_dossier=1000, garantie_type="Caution", garantie_cout=3600, ira="Exonération mobilité pro", domiciliation="Salaires, 10 ans"),
                    dict(banque="Banque B", statut="Étude en cours", taux=3.35, duree_mois=300, taux_assurance=0.09, frais_dossier=500, garantie_type="Caution", garantie_cout=4100, ira="Légales", domiciliation="Non exigée")],
            taches=[dict(libelle="Relancer Banque B sur délai de retour", echeance=t + timedelta(days=2)), dict(libelle="Récupérer devis cuisine définitif", echeance=t + timedelta(days=7))],
            situation_familiale="Marié", enfants=2, epargne=62000, loyer_actuel=1150, projet_type="Résidence principale", projet_nature="ancien",
            ville="Lyon 7e", code_postal="69007", prix=385000, travaux=18000, garantie=3900, frais_dossier=800, honoraires=3500, apport=45000,
            date_compromis=t - timedelta(days=30), date_condition_suspensive=t + timedelta(days=28),
            notes="Épargne régulière de 600 €/mois visible sur les relevés.")

    dossier("D-DEMO-0002", "Montage",
            [dict(nom="Benali", prenom="Karim", profession="Commercial B2B", contrat="CDI", anciennete_mois=50, revenus_nets_mensuels=3850, date_naissance=date(1992, 1, 20))],
            [dict(libelle="Prêt principal", ajuste=True, taux=3.25, duree_mois=240, taux_assurance=0.12)],
            taches=[dict(libelle="Obtenir attestation de valeur locative", echeance=t - timedelta(days=1))],
            situation_familiale="Célibataire", epargne=31000, loyer_actuel=780, credits_conserves=290, projet_type="Locatif", projet_nature="ancien",
            ville="Villeurbanne", code_postal="69100", prix=182000, travaux=12000, garantie=1900, frais_dossier=500, honoraires=2500, apport=22000, loyer_attendu=820)

    dossier("D-DEMO-0003", "Accord",
            [dict(nom="Perret", prenom="Julie", profession="Chargée de communication", contrat="CDI", anciennete_mois=38, revenus_nets_mensuels=2350),
             dict(nom="Morel", prenom="Thomas", profession="Technicien réseau", contrat="CDI", anciennete_mois=6, revenus_nets_mensuels=2200)],
            [dict(libelle="PTZ", type="ptz", montant=40000, taux=0, duree_mois=300, differe_mois=180, differe_type="total", taux_assurance=0.08),
             dict(libelle="Prêt principal", ajuste=True, taux=3.15, duree_mois=300, taux_assurance=0.08)],
            offres=[dict(banque="Banque C", statut="Accord ferme", taux=3.15, duree_mois=300, taux_assurance=0.08, frais_dossier=500, garantie_type="Caution", garantie_cout=2800, ira="0 € en cas de revente (négocié)", domiciliation="3 ans")],
            situation_familiale="Pacsé", epargne=24000, loyer_actuel=890, projet_type="Résidence principale", projet_nature="vefa",
            ville="Meyzieu", code_postal="69330", prix=268000, garantie=2800, frais_dossier=500, honoraires=3000, apport=21000,
            notes="PTZ : montant et différé à vérifier selon la zone et les revenus fiscaux de référence.")

    dossier("D-DEMO-0004", "Facturé",
            [dict(nom="Rey", prenom="Laurent", profession="Gérant de SCI", contrat="Dirigeant", anciennete_mois=144, revenus_nets_mensuels=6200)],
            [dict(libelle="Prêt SCI", ajuste=True, taux=3.45, duree_mois=240, taux_assurance=0.15)],
            facture=dict(honoraires=5000, commission_banque=2300, statut="Facturé", numero="F-2026-018", date_emission=t - timedelta(days=11), date_deblocage_fonds=t - timedelta(days=15)),
            situation_familiale="SCI", epargne=85000, credits_conserves=1450, autres_revenus=900, projet_type="Locatif", projet_nature="ancien",
            ville="Tassin-la-Demi-Lune", code_postal="69160", prix=420000, travaux=35000, garantie=4500, frais_dossier=1200, honoraires=5000, apport=80000, loyer_attendu=2100)

    db.commit()
    print(f"Démo créée. Connexion : {EMAIL} / {MDP}")


if __name__ == "__main__":
    run()
