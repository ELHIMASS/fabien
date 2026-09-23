import pytest

from app.calc.finance import Pret, capacite_emprunt, echeancier, mensualite_constante, taeg


def test_mensualite_reference():
    # 200 000 € sur 20 ans à 3 % : 1 109,20 € (valeur de référence des tables usuelles)
    assert mensualite_constante(200_000, 3.0, 240) == pytest.approx(1109.20, abs=0.01)


def test_taux_zero():
    assert mensualite_constante(120_000, 0, 240) == pytest.approx(500)


def test_echeancier_solde_a_zero():
    e = echeancier(Pret("p", 250_000, 3.5, 300))
    assert len(e.lignes) == 300
    assert e.lignes[-1].crd == pytest.approx(0, abs=1e-6)
    assert sum(l.capital for l in e.lignes) == pytest.approx(250_000, abs=0.01)


def test_assurance_capital_initial():
    e = echeancier(Pret("p", 100_000, 3, 120, taux_assurance=0.36))
    assert e.lignes[0].assurance == pytest.approx(30)
    assert e.total_assurance == pytest.approx(3600)


def test_differe_partiel_puis_amortissement():
    e = echeancier(Pret("p", 100_000, 3, 240, differe_mois=12, differe_type="partiel"))
    assert e.lignes[0].echeance == pytest.approx(250)  # intérêts seuls
    assert e.lignes[11].crd == pytest.approx(100_000)
    assert e.lignes[12].echeance == pytest.approx(mensualite_constante(100_000, 3, 228), abs=0.01)
    assert e.lignes[-1].crd == pytest.approx(0, abs=1e-6)


def test_ptz_differe_total_sans_interets():
    e = echeancier(Pret("PTZ", 40_000, 0, 300, "ptz", 180, "total"))
    assert all(l.echeance == 0 for l in e.lignes[:180])
    assert e.lignes[180].echeance == pytest.approx(40_000 / 120)
    assert e.total_interets == pytest.approx(0)


def test_differe_total_capitalise():
    e = echeancier(Pret("p", 100_000, 3.6, 240, differe_mois=12, differe_type="total"))
    assert e.lignes[11].crd == pytest.approx(100_000 * (1.003 ** 12), rel=1e-9)


def test_relais_in_fine():
    e = echeancier(Pret("Relais", 150_000, 4.2, 24, "relais"))
    assert e.lignes[0].echeance == pytest.approx(525)
    assert e.lignes[-1].capital == pytest.approx(150_000)
    assert e.lignes[-1].crd == 0


def test_taeg_sans_frais_egal_taux_actuariel():
    e = echeancier(Pret("p", 200_000, 3.0, 240))
    t = taeg(200_000, [l.echeance for l in e.lignes])
    assert t == pytest.approx(((1 + 0.03 / 12) ** 12 - 1) * 100, abs=1e-4)


def test_taeg_augmente_avec_frais():
    e = echeancier(Pret("p", 200_000, 3.0, 240, taux_assurance=0.1))
    flux = [l.echeance + l.assurance for l in e.lignes]
    assert taeg(197_000, flux) > taeg(200_000, flux) > 3.0


def test_capacite_coherente():
    c = capacite_emprunt(5000, 250, 3.3, 300, 0.1)
    assert c["mensualite_max"] == pytest.approx(1500)
    m = mensualite_constante(c["capacite"], 3.3, 300) + c["capacite"] * 0.1 / 100 / 12
    assert m == pytest.approx(1500, abs=0.01)
