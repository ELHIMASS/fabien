"""Analyse d'un dossier : plan de financement, ratios, contrôles, pièces attendues, synthèse."""
from __future__ import annotations

from datetime import date

from .. import models as m
from .finance import Pret, echeancier, estimation_frais_notaire, mensualites_agregees, taeg

CONTRATS_STABLES = {"CDI", "Fonctionnaire", "Retraité"}


# ---------------------------------------------------------------- plan
def plan_financement(d: m.Dossier, cab: m.Cabinet) -> dict:
    notaire = d.frais_notaire if d.frais_notaire is not None else estimation_frais_notaire(d.prix, d.projet_nature)
    besoin = d.prix + notaire + d.travaux + d.garantie + d.frais_dossier + d.honoraires

    fixes = [p for p in d.prets if not p.ajuste]
    finance_fixe = sum(p.montant for p in fixes if p.type != "relais")
    relais = sum(p.montant for p in fixes if p.type == "relais")
    a_financer = max(0.0, besoin - d.apport - relais)
    ajustables = [p for p in d.prets if p.ajuste]
    montant_ajuste = max(0.0, a_financer - finance_fixe)

    lignes, echs = [], []
    for p in d.prets:
        montant = (montant_ajuste / len(ajustables)) if p.ajuste else p.montant
        pr = Pret(p.libelle, montant, p.taux, p.duree_mois, p.type, p.differe_mois, p.differe_type, p.taux_assurance)
        e = echeancier(pr)
        echs.append(e)
        lignes.append({
            "id": p.id, "libelle": p.libelle, "type": p.type, "montant": round(montant, 2),
            "taux": p.taux, "duree_mois": p.duree_mois, "differe_mois": p.differe_mois, "differe_type": p.differe_type,
            "taux_assurance": p.taux_assurance, "ajuste": p.ajuste,
            "mensualite_hors_assurance": round(e.lignes[min(len(e.lignes) - 1, p.differe_mois if p.differe_type != "aucun" else 0)].echeance, 2) if e.lignes and p.type not in ("in_fine", "relais") else round(e.lignes[0].interets, 2) if e.lignes else 0,
            "assurance_mensuelle": round(e.lignes[0].assurance, 2) if e.lignes else 0,
            "cout_interets": round(e.total_interets, 2), "cout_assurance": round(e.total_assurance, 2),
        })

    agreg = mensualites_agregees(echs)
    mens_max = max(agreg, default=0.0)
    mens_initiale = agreg[0] if agreg else 0.0
    total_emprunte = sum(l["montant"] for l in lignes)
    cout_interets = sum(e.total_interets for e in echs)
    cout_assurance = sum(e.total_assurance for e in echs)

    # TAEG estimé : capital mis à disposition net des frais (dossier, garantie, courtage).
    flux = [0.0] * max((len(e.lignes) for e in echs), default=0)
    for e in echs:
        for l in e.lignes:
            flux[l.mois - 1] += l.echeance + l.assurance
    frais = d.frais_dossier + d.garantie + d.honoraires
    taeg_est = taeg(total_emprunte - frais, flux) if total_emprunte > 0 else 0.0

    return {
        "prix": d.prix, "frais_notaire": round(notaire, 2), "frais_notaire_estime": d.frais_notaire is None,
        "travaux": d.travaux, "garantie": d.garantie, "frais_dossier": d.frais_dossier, "honoraires": d.honoraires,
        "cout_operation": round(besoin, 2), "apport": d.apport, "a_financer": round(a_financer, 2),
        "total_emprunte": round(total_emprunte, 2), "ecart_plan": round(total_emprunte - relais - a_financer, 2),
        "prets": lignes,
        "mensualite_initiale": round(mens_initiale, 2), "mensualite_max": round(mens_max, 2),
        "profil_mensualites": [round(x, 2) for x in agreg[::12]],
        "cout_interets": round(cout_interets, 2), "cout_assurance": round(cout_assurance, 2),
        "cout_total_credit": round(cout_interets + cout_assurance + frais, 2),
        "taeg_estime": round(taeg_est, 3),
        "duree_max_mois": max((p.duree_mois for p in d.prets), default=0),
    }


# ---------------------------------------------------------------- ratios
def ratios(d: m.Dossier, cab: m.Cabinet, plan: dict) -> dict:
    revenus = sum(e.revenus_nets_mensuels * (e.nb_mois_salaire or 12) / 12 for e in d.emprunteurs) + d.autres_revenus
    loyers_ponderes = (d.loyer_attendu if d.projet_type == "Locatif" else 0) * cab.ponderation_loyers + d.revenus_locatifs_existants * cab.ponderation_loyers
    revenus_retenus = revenus + loyers_ponderes
    loyer_conserve = d.loyer_actuel if d.projet_type in ("Locatif", "Résidence secondaire") else 0
    charges = d.credits_conserves + d.pension_versee + plan["mensualite_max"] + loyer_conserve
    endettement = charges / revenus_retenus if revenus_retenus else 0.0
    nb_personnes = max(1, len(d.emprunteurs)) + d.enfants
    rav = revenus_retenus - charges
    rav_min = cab.reste_a_vivre_base + cab.reste_a_vivre_par_personne * (nb_personnes - 1)
    saut = plan["mensualite_max"] - d.loyer_actuel if d.projet_type == "Résidence principale" else None
    epargne_residuelle = d.epargne - d.apport
    return {
        "revenus_mensuels": round(revenus, 2), "loyers_ponderes": round(loyers_ponderes, 2),
        "revenus_retenus": round(revenus_retenus, 2), "charges_apres_projet": round(charges, 2),
        "taux_endettement": round(endettement, 4), "plafond_endettement": cab.plafond_endettement,
        "reste_a_vivre": round(rav, 2), "reste_a_vivre_reference": rav_min, "nb_personnes": nb_personnes,
        "saut_de_charge": round(saut, 2) if saut is not None else None,
        "apport_sur_cout": round(d.apport / plan["cout_operation"], 4) if plan["cout_operation"] else 0,
        "epargne_residuelle": round(epargne_residuelle, 2),
        "epargne_en_mois_de_mensualite": round(epargne_residuelle / plan["mensualite_max"], 1) if plan["mensualite_max"] else None,
    }


# ---------------------------------------------------------------- pièces attendues
PIECES = {
    "identite": "Pièce d'identité en cours de validité",
    "situation_familiale": "Livret de famille / PACS / jugement de divorce",
    "domicile": "Justificatif de domicile de moins de 3 mois",
    "bulletins": "3 derniers bulletins de salaire",
    "bulletin_decembre": "Bulletin de salaire de décembre N-1",
    "contrat_travail": "Contrat de travail ou attestation employeur",
    "avis_imposition": "2 derniers avis d'imposition",
    "releves": "3 derniers relevés de tous les comptes",
    "epargne": "Justificatifs d'épargne (apport)",
    "credits_en_cours": "Offres et tableaux d'amortissement des crédits en cours",
    "bail": "Bail ou quittances de loyer",
    "compromis": "Compromis / contrat de réservation",
    "devis": "Devis des travaux",
    "bilans": "3 derniers bilans et liasses fiscales",
    "kbis": "Extrait Kbis / avis de situation INSEE",
    "statuts_sci": "Statuts de la SCI et PV d'AG autorisant l'emprunt",
    "estimation_loyer": "Estimation locative (agence) ou bail en place",
    "titre_retraite": "Notification de pension de retraite",
    "permis_construire": "Permis de construire et contrat de construction (CCMI)",
    "terrain": "Compromis d'achat du terrain",
    "estimation_bien_vendu": "Estimation du bien à vendre (relais) et titre de propriété",
    "tableau_amortissement_bien_vendu": "Tableau d'amortissement du prêt en cours sur le bien vendu",
}


def pieces_attendues(d: m.Dossier) -> list[str]:
    req = ["identite", "situation_familiale", "domicile", "avis_imposition", "releves", "compromis"]
    contrats = {e.contrat for e in d.emprunteurs}
    if contrats & {"CDI", "CDD", "Fonctionnaire", "Intérim"}:
        req += ["bulletins", "bulletin_decembre", "contrat_travail"]
    if contrats & {"TNS", "Profession libérale", "Dirigeant"}:
        req += ["bilans", "kbis"]
    if "Retraité" in contrats:
        req.append("titre_retraite")
    if d.apport > 0:
        req.append("epargne")
    if d.credits_conserves > 0:
        req.append("credits_en_cours")
    if d.loyer_actuel > 0:
        req.append("bail")
    if d.travaux > 0:
        req.append("devis")
    if d.projet_type == "Locatif":
        req.append("estimation_loyer")
    if d.situation_familiale == "SCI":
        req.append("statuts_sci")
    if d.projet_nature == "construction":
        req = [r for r in req if r != "compromis"] + ["permis_construire", "terrain"]
    if any(p.type == "relais" for p in d.prets):
        req += ["estimation_bien_vendu", "tableau_amortissement_bien_vendu"]
    seen, out = set(), []
    for r in req:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def etat_pieces(d: m.Dossier) -> list[dict]:
    res = []
    for cat in pieces_attendues(d):
        docs = [x for x in d.documents if x.categorie == cat]
        statut = "manquant"
        if any(x.statut == "valide" for x in docs):
            statut = "valide"
        elif any(x.statut == "recu" for x in docs):
            statut = "recu"
        elif docs:
            statut = "refuse"
        res.append({"categorie": cat, "libelle": PIECES[cat], "statut": statut, "documents": [x.id for x in docs]})
    return res


# ---------------------------------------------------------------- contrôles
def controles(d: m.Dossier, cab: m.Cabinet, plan: dict, r: dict, aujourd_hui: date | None = None) -> list[dict]:
    t = aujourd_hui or date.today()
    out: list[dict] = []

    def add(niveau: str, code: str, msg: str):
        out.append({"niveau": niveau, "code": code, "message": msg})

    if not d.emprunteurs:
        add("bloquant", "EMPRUNTEUR", "Aucun emprunteur renseigné.")
    if not d.prets:
        add("bloquant", "PRET", "Aucune ligne de prêt dans le plan de financement.")
    if abs(plan["ecart_plan"]) > 1:
        sens = "excédent" if plan["ecart_plan"] > 0 else "manque"
        add("bloquant", "PLAN_DESEQUILIBRE", f"Plan déséquilibré : {sens} de {abs(plan['ecart_plan']):,.0f} € entre prêts et besoin.".replace(",", " "))

    te = r["taux_endettement"]
    if te > cab.plafond_endettement:
        add("bloquant", "HCSF_ENDETTEMENT", f"Endettement {_pc(te)} > {_pc(cab.plafond_endettement, 0)} : dossier à présenter en dérogation HCSF.")
    elif te > cab.plafond_endettement - 0.02:
        add("attention", "ENDETTEMENT_LIMITE", f"Endettement {_pc(te)} : proche du plafond.")

    dmax = cab.duree_max_mois_neuf if (d.projet_nature in ("vefa", "construction") or (d.prix and d.travaux > 0.10 * d.prix)) else cab.duree_max_mois
    if plan["duree_max_mois"] > dmax:
        add("bloquant", "HCSF_DUREE", f"Durée {plan['duree_max_mois'] // 12} ans > {dmax // 12} ans autorisés pour ce projet.")

    if r["epargne_residuelle"] < 0:
        add("bloquant", "APPORT_EPARGNE", f"Apport déclaré ({d.apport:,.0f} €) supérieur à l'épargne ({d.epargne:,.0f} €).".replace(",", " "))
    elif r["epargne_en_mois_de_mensualite"] is not None and r["epargne_en_mois_de_mensualite"] < 3:
        add("attention", "EPARGNE_RESIDUELLE", f"Épargne résiduelle faible : {r['epargne_en_mois_de_mensualite']} mois de mensualité.")

    if plan["cout_operation"] and d.apport < (plan["frais_notaire"] + d.garantie + d.frais_dossier):
        add("attention", "APPORT_FRAIS", "L'apport ne couvre pas les frais (notaire, garantie, dossier) : financement supérieur au prix.")

    if r["revenus_retenus"] and r["reste_a_vivre"] < r["reste_a_vivre_reference"]:
        add("attention", "RESTE_A_VIVRE", f"Reste à vivre {r['reste_a_vivre']:,.0f} € sous la référence cabinet ({r['reste_a_vivre_reference']:,.0f} €).".replace(",", " "))

    if r["saut_de_charge"] is not None and r["saut_de_charge"] > 500:
        add("attention", "SAUT_DE_CHARGE", f"Saut de charge de {r['saut_de_charge']:,.0f} €/mois : démontrer la capacité d'épargne sur les relevés.".replace(",", " "))

    for e in d.emprunteurs:
        nom = f"{e.prenom} {e.nom}".strip()
        if e.contrat in ("CDD", "Intérim"):
            add("attention", "CONTRAT_PRECAIRE", f"{nom} : {e.contrat}, revenus à justifier sur plusieurs années.")
        if e.contrat == "CDI" and not e.periode_essai_validee:
            add("bloquant", "PERIODE_ESSAI", f"{nom} : période d'essai en cours.")
        if e.contrat in ("TNS", "Profession libérale", "Dirigeant") and e.anciennete_mois < 36:
            add("attention", "TNS_ANCIENNETE", f"{nom} : activité indépendante de moins de 3 ans (3 bilans souvent exigés).")
        if e.date_naissance:
            age_fin = (t - e.date_naissance).days / 365.25 + plan["duree_max_mois"] / 12
            if age_fin > 75:
                add("attention", "AGE_FIN_PRET", f"{nom} : {age_fin:.0f} ans en fin de prêt, contraintes d'assurance probables.")

    usure = (cab.taux_usure or {}).get(_tranche_usure(plan["duree_max_mois"]))
    if usure is None:
        add("info", "USURE_NON_RENSEIGNE", "Taux d'usure du trimestre non renseigné dans les paramètres : contrôle impossible.")
    elif plan["taeg_estime"] > usure:
        add("bloquant", "USURE", f"TAEG estimé {_tx(plan['taeg_estime'])} > taux d'usure {_tx(usure)} ({cab.taux_usure_trimestre or 'trimestre non précisé'}).")

    pieces = etat_pieces(d)
    manquantes = [p for p in pieces if p["statut"] in ("manquant", "refuse")]
    if manquantes and d.etape in ("En banque", "Accord", "Offre émise"):
        add("attention", "PIECES", f"{len(manquantes)} pièce(s) manquante(s) ou refusée(s) alors que le dossier est en banque.")

    if d.date_condition_suspensive and d.etape in ("Découverte", "Montage", "En banque"):
        jours = (d.date_condition_suspensive - t).days
        if jours < 0:
            add("bloquant", "CONDITION_SUSPENSIVE", f"Condition suspensive dépassée depuis {-jours} jour(s).")
        elif jours <= 15:
            add("attention", "CONDITION_SUSPENSIVE", f"Condition suspensive dans {jours} jour(s) sans accord bancaire.")

    if not d.consentement_rgpd:
        add("attention", "RGPD", "Consentement / information RGPD du client non tracé.")
    return out


def _pc(v: float, d: int = 1) -> str:
    return f"{v * 100:.{d}f} %".replace(".", ",")


def _tx(v: float) -> str:
    return f"{v:.2f} %".replace(".", ",")


def _tranche_usure(duree_mois: int) -> str:
    if duree_mois < 120:
        return "moins_10_ans"
    if duree_mois < 240:
        return "10_20_ans"
    return "20_ans_et_plus"


# ---------------------------------------------------------------- offres
def comparer_offres(d: m.Dossier, plan: dict) -> list[dict]:
    montant = plan["total_emprunte"] or plan["a_financer"]
    res = []
    for o in d.offres:
        e = echeancier(Pret(o.banque, montant, o.taux, o.duree_mois, "amortissable", 0, "aucun", o.taux_assurance))
        cout = e.total_interets + e.total_assurance + o.frais_dossier + o.garantie_cout
        flux = [l.echeance + l.assurance for l in e.lignes]
        res.append({
            "id": o.id, "banque": o.banque, "statut": o.statut,
            "mensualite": round(e.mensualite_max, 2), "cout_total": round(cout, 2),
            "taeg_estime": round(taeg(montant - o.frais_dossier - o.garantie_cout - d.honoraires, flux), 3),
        })
    if res:
        best = min(r["cout_total"] for r in res)
        for r in res:
            r["ecart"] = round(r["cout_total"] - best, 2)
            r["meilleure"] = r["ecart"] == 0
    return res


def analyse_complete(d: m.Dossier, cab: m.Cabinet) -> dict:
    p = plan_financement(d, cab)
    r = ratios(d, cab, p)
    return {"plan": p, "ratios": r, "controles": controles(d, cab, p, r), "pieces": etat_pieces(d), "offres": comparer_offres(d, p)}


# ---------------------------------------------------------------- synthèse
def _eur(v: float) -> str:
    return f"{v:,.0f} €".replace(",", " ")


def synthese_bancaire(d: m.Dossier, cab: m.Cabinet, courtier: str = "") -> str:
    a = analyse_complete(d, cab)
    p, r = a["plan"], a["ratios"]
    noms = " et ".join(f"{e.prenom} {e.nom}".strip() for e in d.emprunteurs) or "—"
    qui = "\n".join(
        f"- {e.prenom} {e.nom}, {e.profession or 'profession à préciser'}"
        f"{' chez ' + e.employeur if e.employeur else ''}, {e.contrat}"
        f"{f' depuis {e.anciennete_mois // 12} an(s)' if e.anciennete_mois >= 12 else f' depuis {e.anciennete_mois} mois' if e.anciennete_mois else ''}"
        f" – {_eur(e.revenus_nets_mensuels)} nets/mois sur {e.nb_mois_salaire:g} mois"
        for e in d.emprunteurs
    )
    nature = {"ancien": "dans l'ancien", "neuf": "dans le neuf", "vefa": "en VEFA", "construction": "en construction"}.get(d.projet_nature, "")
    prets = "\n".join(
        f"- {l['libelle']} : {_eur(l['montant'])} sur {l['duree_mois'] // 12} ans à {_tx(l['taux'])}"
        f"{' (différé ' + l['differe_type'] + ' ' + str(l['differe_mois']) + ' mois)' if l['differe_type'] != 'aucun' else ''}"
        for l in p["prets"]
    )
    forts = []
    if r["taux_endettement"] <= cab.plafond_endettement - 0.02:
        forts.append(f"endettement maîtrisé ({_pc(r['taux_endettement'])})")
    if r["reste_a_vivre"] >= r["reste_a_vivre_reference"] * 1.5:
        forts.append(f"reste à vivre confortable ({_eur(r['reste_a_vivre'])}/mois)")
    if d.apport >= p["frais_notaire"] + d.garantie + d.frais_dossier:
        forts.append(f"apport de {_eur(d.apport)} couvrant l'ensemble des frais")
    if r["epargne_en_mois_de_mensualite"] and r["epargne_en_mois_de_mensualite"] >= 6:
        forts.append(f"épargne résiduelle de {_eur(r['epargne_residuelle'])} après opération")
    if d.emprunteurs and all(e.contrat in CONTRATS_STABLES and e.anciennete_mois >= 24 for e in d.emprunteurs):
        forts.append("stabilité professionnelle des emprunteurs")
    if r["saut_de_charge"] is not None and r["saut_de_charge"] <= 300:
        forts.append(f"saut de charge limité ({_eur(r['saut_de_charge'])}/mois)")
    vigilance = [c["message"] for c in a["controles"] if c["niveau"] in ("bloquant", "attention") and c["code"] not in ("RGPD", "PIECES")]

    return f"""Objet : Demande de financement – {noms} – {d.projet_type} {d.ville}
Réf. dossier : {d.ref}

LES EMPRUNTEURS
{d.situation_familiale}{f', {d.enfants} enfant(s) à charge' if d.enfants else ''}.
{qui}
Charges actuelles : loyer {_eur(d.loyer_actuel)}, crédits conservés {_eur(d.credits_conserves)}. Épargne : {_eur(d.epargne)}.

LE PROJET
Acquisition {nature} à {d.ville or '—'} pour {_eur(d.prix)}{f', travaux {_eur(d.travaux)}' if d.travaux else ''}.
Frais de notaire {_eur(p['frais_notaire'])}{' (estimation)' if p['frais_notaire_estime'] else ''}, garantie {_eur(d.garantie)}, frais de dossier {_eur(d.frais_dossier)}, honoraires {_eur(d.honoraires)}.
Coût total de l'opération : {_eur(p['cout_operation'])}.

LE FINANCEMENT
Apport personnel : {_eur(d.apport)}
{prets}
Mensualité maximale assurance comprise : {_eur(p['mensualite_max'])}.
Endettement après projet : {_pc(r['taux_endettement'])} – reste à vivre : {_eur(r['reste_a_vivre'])}/mois.

POINTS FORTS
{chr(10).join('- ' + x for x in forts) if forts else '- à compléter par le courtier'}

POINTS DE VIGILANCE
{chr(10).join('- ' + x for x in vigilance) if vigilance else '- aucun point bloquant identifié'}

{('Contexte : ' + d.notes) if d.notes else ''}

{courtier}
{cab.nom}{f' – ORIAS {cab.orias}' if cab.orias else ''}
""".strip()


def mail_relance_pieces(d: m.Dossier, courtier: str) -> str:
    manquantes = [p for p in etat_pieces(d) if p["statut"] in ("manquant", "refuse")]
    if not manquantes:
        return ""
    prenoms = " et ".join(e.prenom for e in d.emprunteurs if e.prenom) or "Madame, Monsieur"
    lignes = "\n".join(f"- {p['libelle']}{' (document refusé, à renvoyer)' if p['statut'] == 'refuse' else ''}" for p in manquantes)
    return f"""Bonjour {prenoms},

Pour avancer sur votre dossier de financement, il me manque les pièces suivantes :
{lignes}

Vous pouvez me les transmettre en réponse à ce mail, en PDF de préférence.

Bien cordialement,
{courtier}"""
