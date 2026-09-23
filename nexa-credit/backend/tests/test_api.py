import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import UPLOAD_DIR

H = {"x-nexa": "1"}
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


@pytest.fixture(scope="module")
def admin():
    c = TestClient(app)
    r = c.post("/api/auth/installation", headers=H, json={"cabinet": "Cabinet Test", "nom": "Admin", "email": "admin@test.fr", "password": "MotDePasse2026"})
    assert r.status_code == 200, r.text
    return c


def _dossier(c, **kw):
    body = {"prix": 300000, "apport": 40000, "epargne": 60000, "garantie": 3000, "frais_dossier": 500,
            "emprunteurs": [{"nom": "Test", "prenom": "Alice", "contrat": "CDI", "anciennete_mois": 48, "revenus_nets_mensuels": 5000}], **kw}
    r = c.post("/api/dossiers", headers=H, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_installation_unique(admin):
    r = TestClient(app).post("/api/auth/installation", headers=H, json={"cabinet": "Autre cabinet", "nom": "Yves", "email": "yves@test.fr", "password": "MotDePasse2026"})
    assert r.status_code == 409


def test_non_authentifie_refuse():
    assert TestClient(app).get("/api/dossiers").status_code == 401


def test_csrf_entete_obligatoire(admin):
    assert admin.post("/api/dossiers", json={}).status_code == 403


def test_mot_de_passe_faible_refuse(admin):
    r = admin.post("/api/cabinet/utilisateurs", headers=H, json={"email": "c@test.fr", "nom": "C", "password": "court"})
    assert r.status_code == 422


def test_limitation_connexion():
    c = TestClient(app)
    codes = [c.post("/api/auth/connexion", headers=H, json={"email": "admin@test.fr", "password": "faux"}).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_dossier_plan_equilibre(admin):
    d = _dossier(admin)
    p = d["analyse"]["plan"]
    assert d["ref"].startswith("D-")
    assert p["frais_notaire_estime"] is True
    assert p["total_emprunte"] == pytest.approx(p["a_financer"], abs=0.01)
    assert p["cout_operation"] == pytest.approx(300000 + p["frais_notaire"] + 3000 + 500)
    assert not any(c["code"] == "PLAN_DESEQUILIBRE" for c in d["analyse"]["controles"])


def test_controle_endettement_et_apport(admin):
    d = _dossier(admin, apport=70000, epargne=50000,
                 emprunteurs=[{"nom": "Juste", "contrat": "CDD", "revenus_nets_mensuels": 1800}])
    codes = {c["code"] for c in d["analyse"]["controles"]}
    assert {"HCSF_ENDETTEMENT", "APPORT_EPARGNE", "CONTRAT_PRECAIRE", "USURE_NON_RENSEIGNE"} <= codes


def test_usure_parametrable(admin):
    r = admin.patch("/api/cabinet", headers=H, json={"taux_usure": {"20_ans_et_plus": 1.0}, "taux_usure_trimestre": "test"})
    assert r.status_code == 200
    d = _dossier(admin)
    assert any(c["code"] == "USURE" for c in d["analyse"]["controles"])
    admin.patch("/api/cabinet", headers=H, json={"taux_usure": {}})


def test_ptz_et_pret_ajuste(admin):
    d = _dossier(admin)
    r = admin.post(f"/api/dossiers/{d['id']}/prets", headers=H, json={"libelle": "PTZ", "type": "ptz", "montant": 50000, "taux": 0, "duree_mois": 300, "differe_mois": 180, "differe_type": "total"})
    assert r.status_code == 200
    d2 = admin.get(f"/api/dossiers/{d['id']}").json()
    principal = next(p for p in d2["analyse"]["plan"]["prets"] if p["ajuste"])
    assert principal["montant"] == pytest.approx(d["analyse"]["plan"]["a_financer"] - 50000, abs=0.01)


def test_cloisonnement_cabinets(admin):
    d = _dossier(admin)
    autre = TestClient(app)
    # Second cabinet créé directement en base (l'installation publique n'est possible qu'une fois).
    from app.db import SessionLocal
    from app import models as m
    from app.security import hash_password
    db = SessionLocal()
    cab = m.Cabinet(nom="Concurrent")
    db.add(cab); db.flush()
    db.add(m.User(cabinet_id=cab.id, email="autre@x.fr", nom="Autre", role="admin", password_hash=hash_password("MotDePasse2026")))
    db.commit(); db.close()
    assert autre.post("/api/auth/connexion", headers=H, json={"email": "autre@x.fr", "password": "MotDePasse2026"}).status_code == 200
    assert autre.get(f"/api/dossiers/{d['id']}").status_code == 404
    assert autre.patch(f"/api/dossiers/{d['id']}", headers=H, json={"prix": 1}).status_code == 404
    assert all(x["id"] != d["id"] for x in autre.get("/api/dossiers").json())


def test_document_chiffre_et_type_verifie(admin):
    d = _dossier(admin)
    r = admin.post(f"/api/dossiers/{d['id']}/documents", headers=H, data={"categorie": "identite"},
                   files={"fichier": ("cni.pdf", io.BytesIO(PDF), "application/pdf")})
    assert r.status_code == 200, r.text
    doc = r.json()
    stocke = next(UPLOAD_DIR.rglob("*.bin")).read_bytes()
    assert PDF not in stocke  # chiffré au repos
    assert admin.get(f"/api/dossiers/{d['id']}/documents/{doc['id']}/fichier").content == PDF
    faux = admin.post(f"/api/dossiers/{d['id']}/documents", headers=H, data={"categorie": "identite"},
                      files={"fichier": ("x.pdf", io.BytesIO(b"MZ\x90 executable"), "application/pdf")})
    assert faux.status_code == 415
    pieces = admin.get(f"/api/dossiers/{d['id']}").json()["analyse"]["pieces"]
    assert next(p for p in pieces if p["categorie"] == "identite")["statut"] == "recu"


def test_honoraires_interdits_avant_deblocage(admin):
    d = _dossier(admin)
    r = admin.patch(f"/api/dossiers/{d['id']}/facture", headers=H, json={"honoraires": 3000, "statut": "Facturé"})
    assert r.status_code == 422
    r = admin.patch(f"/api/dossiers/{d['id']}/facture", headers=H, json={"honoraires": 3000, "statut": "Facturé", "date_deblocage_fonds": "2026-09-01"})
    assert r.status_code == 200


def test_synthese_et_audit(admin):
    d = _dossier(admin)
    s = admin.get(f"/api/dossiers/{d['id']}/synthese").json()
    assert "LE FINANCEMENT" in s["texte"] and "Alice" in s["texte"]
    assert "Pièce d'identité" in s["relance"]
    actions = {a["action"] for a in admin.get(f"/api/audit?dossier_id={d['id']}").json()}
    assert {"dossier_cree"} <= actions


def test_rgpd_effacement(admin):
    d = _dossier(admin)
    assert admin.delete(f"/api/rgpd/effacer/{d['id']}?confirmation=mauvaise", headers=H).status_code == 422
    assert admin.delete(f"/api/rgpd/effacer/{d['id']}?confirmation={d['ref']}", headers=H).status_code == 200
    assert admin.get(f"/api/dossiers/{d['id']}").status_code == 404
