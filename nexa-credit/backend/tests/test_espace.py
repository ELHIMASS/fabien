import io
import re

import pytest
from fastapi.testclient import TestClient

from app.main import app

H = {"x-nexa": "1"}
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


@pytest.fixture(scope="module")
def courtier():
    from app.security import login_limiter
    login_limiter.hits.clear()  # test_api épuise volontairement les tentatives de connexion
    c = TestClient(app)
    r = c.post("/api/auth/connexion", headers=H, json={"email": "admin@test.fr", "password": "MotDePasse2026"})
    if r.status_code != 200:  # module lancé seul : installation
        r = c.post("/api/auth/installation", headers=H, json={"cabinet": "Cabinet Test", "nom": "Admin", "email": "admin@test.fr", "password": "MotDePasse2026"})
    assert r.status_code == 200, r.text
    return c


def _dossier(c):
    r = c.post("/api/dossiers", headers=H, json={"prix": 250000, "apport": 30000, "epargne": 50000, "loyer_actuel": 800,
                                                "emprunteurs": [{"nom": "Client", "prenom": "Léa", "contrat": "CDI", "revenus_nets_mensuels": 4000}]})
    return r.json()


def _espace(c, d):
    r = c.post(f"/api/dossiers/{d['id']}/espace", headers=H)
    assert r.status_code == 200, r.text
    e = r.json()
    assert re.fullmatch(r"\d{6}", e["code"]) and e["chemin"].startswith("/espace/")
    return e["chemin"].split("/")[-1], e["code"]


def _client(token, code):
    cl = TestClient(app)
    r = cl.post(f"/api/espace/{token}/connexion", headers=H, json={"code": code})
    return cl, r


def test_parcours_complet(courtier):
    d = _dossier(courtier)
    token, code = _espace(courtier, d)
    cl, r = _client(token, code)
    assert r.status_code == 200
    moi = cl.get("/api/espace/moi").json()
    assert moi["prenoms"] == "Léa"
    assert "plan" not in moi and "analyse" not in moi  # aucune donnée financière
    assert any(p["categorie"] == "bail" for p in moi["pieces"])
    r = cl.post("/api/espace/documents", headers=H, data={"categorie": "identite"},
                files={"fichier": ("cni.pdf", io.BytesIO(PDF), "application/pdf")})
    assert r.status_code == 200, r.text
    det = courtier.get(f"/api/dossiers/{d['id']}").json()
    doc = next(x for x in det["documents"] if x["categorie"] == "identite")
    assert doc["source"] == "client" and doc["statut"] == "recu"
    assert any(t["libelle"].startswith("Contrôler les pièces déposées par le client") for t in det["taches"])
    # un second dépôt ne crée pas une seconde tâche
    cl.post("/api/espace/documents", headers=H, data={"categorie": "domicile"}, files={"fichier": ("d.pdf", io.BytesIO(PDF), "application/pdf")})
    det = courtier.get(f"/api/dossiers/{d['id']}").json()
    assert sum(t["libelle"].startswith("Contrôler les pièces") for t in det["taches"]) == 1
    # motif de refus visible par le client
    courtier.patch(f"/api/dossiers/{d['id']}/documents/{doc['id']}", headers=H, json={"statut": "refuse", "commentaire": "Pièce expirée"})
    p = next(p for p in cl.get("/api/espace/moi").json()["pieces"] if p["categorie"] == "identite")
    assert p["statut"] == "refuse" and p["motif_refus"] == "Pièce expirée"
    assert courtier.get(f"/api/dossiers/{d['id']}/espace").json()["nb_depots"] == 2


def test_client_ne_peut_pas_lire_les_fichiers_ni_l_api_courtier(courtier):
    d = _dossier(courtier)
    token, code = _espace(courtier, d)
    cl, _ = _client(token, code)
    assert cl.get(f"/api/dossiers/{d['id']}").status_code == 401
    assert cl.get("/api/dossiers").status_code == 401


def test_piece_non_demandee_refusee(courtier):
    d = _dossier(courtier)
    cl, _ = _client(*_espace(courtier, d))
    r = cl.post("/api/espace/documents", headers=H, data={"categorie": "statuts_sci"}, files={"fichier": ("s.pdf", io.BytesIO(PDF), "application/pdf")})
    assert r.status_code == 422


def test_code_errone_puis_verrouillage(courtier):
    d = _dossier(courtier)
    token, code = _espace(courtier, d)
    faux = "000000" if code != "000000" else "111111"
    codes = [_client(token, faux)[1].status_code for _ in range(5)]
    assert codes[:4] == [401] * 4 and codes[4] == 410
    assert _client(token, code)[1].status_code == 410  # même le bon code ne passe plus
    assert courtier.get(f"/api/dossiers/{d['id']}/espace").json()["statut"] == "verrouillé"


def test_revocation_et_nouveau_lien(courtier):
    d = _dossier(courtier)
    t1, c1 = _espace(courtier, d)
    cl, _ = _client(t1, c1)
    assert cl.get("/api/espace/moi").status_code == 200
    t2, c2 = _espace(courtier, d)  # un nouveau lien révoque l'ancien
    assert cl.get("/api/espace/moi").status_code == 410
    assert _client(t2, c2)[1].status_code == 200
    courtier.delete(f"/api/dossiers/{d['id']}/espace", headers=H)
    assert _client(t2, c2)[1].status_code == 410


def test_lien_inconnu_et_session_absente():
    assert TestClient(app).post("/api/espace/inexistant/connexion", headers=H, json={"code": "123456"}).status_code == 410
    assert TestClient(app).get("/api/espace/moi").status_code == 401


def test_jeton_client_refuse_cote_courtier(courtier):
    from app.security import create_client_token, read_token
    assert read_token(create_client_token(1)) is None
