import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { ETAPES, eur, eur2, fdate, fdatetime, pct, taux, today } from "../format";
import { Check, ConfirmButton, Field, Line, Select, TextArea, copier, useToast } from "../components/ui";

const CONTRATS = ["CDI", "Fonctionnaire", "CDD", "Intérim", "TNS", "Profession libérale", "Dirigeant", "Retraité", "Sans emploi"];
const STATUTS_OFFRE = ["Envoyé", "Étude en cours", "Accord de principe", "Accord ferme", "Offre émise", "Offre acceptée", "Refus"];

export default function Dossier({ session }) {
  const { id } = useParams();
  const [d, setD] = useState(null);
  const [tab, setTab] = useState("synthese");
  const toast = useToast();
  const nav = useNavigate();
  const base = `/api/dossiers/${id}`;

  const charger = useCallback(() => api.get(base).then(setD).catch(e => { toast(e.message, true); if (e.status === 404) nav("/dossiers"); }), [base, toast, nav]);
  useEffect(() => { charger(); }, [charger]);

  // Chaque action renvoie une promesse ; on recharge le dossier pour recalculer l'analyse côté serveur.
  const act = useCallback(async (fn, ok) => {
    try { const r = await fn(); if (r && r.analyse) setD(r); else await charger(); if (ok) toast(ok); return true; }
    catch (e) { toast(e.message, true); await charger(); return false; }
  }, [charger, toast]);
  const patch = useCallback(champs => act(() => api.patch(base, champs)), [act, base]);

  if (!d) return <p className="muted">Chargement…</p>;
  const a = d.analyse;
  const nbBloq = a.controles.filter(c => c.niveau === "bloquant").length;
  const piecesOk = a.pieces.filter(p => p.statut === "valide").length;
  const props = { d, a, act, patch, base, toast, session };
  const tabs = [
    ["synthese", `Synthèse${nbBloq ? ` · ${nbBloq} bloquant${nbBloq > 1 ? "s" : ""}` : ""}`],
    ["emprunteurs", "Emprunteurs"], ["financement", "Financement"],
    ["pieces", `Pièces ${piecesOk}/${a.pieces.length}`], ["banques", `Banques${d.offres.length ? ` (${d.offres.length})` : ""}`],
    ["facturation", "Facturation"], ["rgpd", "RGPD"],
  ];

  return (
    <div>
      <div className="head">
        <div>
          <Link to="/dossiers" className="btn ghost small" style={{ paddingInline: 0 }}>← Dossiers</Link>
          <h1 style={{ marginTop: 6 }}>{d.nom}</h1>
          <p className="sub"><span className="num">{d.ref}</span> · {d.projet_type} · {d.projet_nature} · {d.ville || "ville à préciser"} · ouvert le {fdate(d.created_at)}</p>
        </div>
        <div className="row">
          <button className="btn" onClick={() => patch({ archive: !d.archive })}>{d.archive ? "Désarchiver" : "Archiver"}</button>
        </div>
      </div>
      <div className="stages" role="group" aria-label="Étape du dossier">
        {ETAPES.map((e, i) => {
          const cur = ETAPES.indexOf(d.etape);
          return <button key={e} className={i === cur ? "cur" : i < cur && d.etape !== "Abandonné" ? "done" : ""} onClick={() => patch({ etape: e })}>{e}</button>;
        })}
      </div>
      <div className="tabs" role="tablist">
        {tabs.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}</button>)}
      </div>
      {tab === "synthese" && <Synthese {...props} />}
      {tab === "emprunteurs" && <Emprunteurs {...props} />}
      {tab === "financement" && <Financement {...props} />}
      {tab === "pieces" && <Pieces {...props} />}
      {tab === "banques" && <Banques {...props} />}
      {tab === "facturation" && <FactureTab {...props} />}
      {tab === "rgpd" && <Rgpd {...props} />}
    </div>
  );
}

/* ------------------------------------------------------------ Synthèse */
function Ratios({ a }) {
  const r = a.ratios, p = a.plan;
  const e = r.taux_endettement, plafond = r.plafond_endettement;
  const col = e > plafond ? "var(--bad)" : e > plafond - 0.02 ? "var(--warn)" : "var(--ok)";
  return (
    <div className="panel">
      <h3>Analyse bancaire</h3>
      <div className="row" style={{ alignItems: "baseline" }}><span className="big" style={{ color: col }}>{pct(e)}</span><span className="muted">taux d'endettement (mensualité max.)</span></div>
      <div className="gauge"><span style={{ width: `${Math.min(e / 0.5, 1) * 100}%`, background: col }} /><i style={{ left: `${(plafond / 0.5) * 100}%` }} /></div>
      <div className="muted small row between"><span>0 %</span><span>{pct(plafond, 0)} plafond</span><span>50 %</span></div>
      <div className="lines" style={{ marginTop: 10 }}>
        <Line k="Revenus retenus / mois" v={eur(r.revenus_retenus)} />
        {r.loyers_ponderes > 0 && <Line k="dont loyers pondérés" v={eur(r.loyers_ponderes)} />}
        <Line k="Charges après projet" v={eur(r.charges_apres_projet)} />
        <Line k="Mensualité initiale / maximale" v={`${eur(p.mensualite_initiale)} / ${eur(p.mensualite_max)}`} />
        <Line k={`Reste à vivre (réf. ${eur(r.reste_a_vivre_reference)})`} v={eur(r.reste_a_vivre)} />
        {r.saut_de_charge !== null && <Line k="Saut de charge" v={`${r.saut_de_charge > 0 ? "+" : ""}${eur(r.saut_de_charge)}`} />}
        <Line k="Apport / coût de l'opération" v={pct(r.apport_sur_cout)} />
        <Line k="Épargne résiduelle" v={`${eur(r.epargne_residuelle)}${r.epargne_en_mois_de_mensualite !== null ? ` · ${r.epargne_en_mois_de_mensualite} mois` : ""}`} />
        <Line k="TAEG estimé" v={taux(p.taeg_estime)} />
      </div>
    </div>
  );
}

function Synthese({ d, a, act, base, toast, patch }) {
  const [syn, setSyn] = useState(null);
  const [tache, setTache] = useState({ libelle: "", echeance: "" });
  useEffect(() => { api.get(`${base}/synthese`).then(setSyn).catch(() => {}); }, [base, d.updated_at]);
  const addTache = e => {
    e.preventDefault();
    if (!tache.libelle.trim()) return;
    act(() => api.post(`${base}/taches`, { libelle: tache.libelle.trim(), echeance: tache.echeance || null })).then(ok => ok && setTache({ libelle: "", echeance: "" }));
  };
  const t = today();
  return (
    <div className="grid g2">
      <div className="stack">
        <Ratios a={a} />
        <div className="panel">
          <h3>Contrôles automatiques</h3>
          <div className="stack" style={{ gap: 6 }}>
            {a.controles.length === 0 && <div className="alert ok">Aucune anomalie détectée.</div>}
            {a.controles.map((c, i) => <div key={i} className={`alert ${c.niveau}`}><span className={`pill ${c.niveau}`}>{c.niveau}</span><span>{c.message}</span></div>)}
          </div>
        </div>
        <div className="panel">
          <h3>Tâches</h3>
          {d.taches.map(x => (
            <div key={x.id} className={`chk ${x.faite ? "done" : ""}`}>
              <input type="checkbox" id={`t${x.id}`} checked={x.faite} onChange={e => act(() => api.patch(`${base}/taches/${x.id}`, { faite: e.target.checked }))} />
              <label htmlFor={`t${x.id}`} className="t" style={{ flex: 1 }}>{x.libelle}</label>
              <span className={`pill ${x.faite ? "neutral" : !x.echeance ? "neutral" : x.echeance < t ? "bad" : "neutral"}`}>{x.echeance ? fdate(x.echeance) : "sans date"}</span>
              <ConfirmButton label="×" confirm="Supprimer" onConfirm={() => act(() => api.del(`${base}/taches/${x.id}`))} />
            </div>))}
          <form className="row" style={{ marginTop: 10 }} onSubmit={addTache}>
            <input id="nouvelle-tache" className="input" style={{ flex: "1 1 200px" }} placeholder="Nouvelle tâche…" value={tache.libelle} onChange={e => setTache({ ...tache, libelle: e.target.value })} />
            <input id="echeance-tache" type="date" className="input" style={{ width: 150 }} value={tache.echeance} onChange={e => setTache({ ...tache, echeance: e.target.value })} />
            <button className="btn small">Ajouter</button>
          </form>
        </div>
        <div className="panel">
          <h3>Suivi</h3>
          <div className="fields">
            <Field label="Date du compromis" type="date" value={d.date_compromis} onSave={v => patch({ date_compromis: v })} />
            <Field label="Condition suspensive de prêt" type="date" value={d.date_condition_suspensive} onSave={v => patch({ date_condition_suspensive: v })} />
            <Field label="Signature authentique" type="date" value={d.date_signature} onSave={v => patch({ date_signature: v })} />
          </div>
          <div style={{ marginTop: 10 }}><TextArea label="Notes internes" value={d.notes} onSave={v => patch({ notes: v })} /></div>
        </div>
      </div>
      <div className="panel">
        <div className="row between" style={{ marginBottom: 10 }}>
          <h3 style={{ margin: 0 }}>Synthèse bancaire</h3>
          <button className="btn small" disabled={!syn} onClick={() => copier(syn.texte, toast)}>Copier</button>
        </div>
        {syn ? <pre className="synth">{syn.texte}</pre> : <p className="muted">Génération…</p>}
        <p className="muted small">Générée à partir des données du dossier. Relisez-la et complétez-la avant envoi.</p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ Emprunteurs */
function Emprunteurs({ d, act, patch, base }) {
  const up = (e, champs) => act(() => api.patch(`${base}/emprunteurs/${e.id}`, champs));
  return (
    <div className="stack">
      <div className="panel">
        <h3>Foyer et charges</h3>
        <div className="fields">
          <Select label="Situation" value={d.situation_familiale} onSave={v => patch({ situation_familiale: v })} options={["Célibataire", "Marié", "Pacsé", "Concubinage", "Divorcé", "Veuf", "SCI"]} />
          <Field label="Enfants à charge" type="number" value={d.enfants} onSave={v => patch({ enfants: v ?? 0 })} />
          <Field label="Épargne totale" suffix="€" type="number" value={d.epargne} onSave={v => patch({ epargne: v ?? 0 })} />
          <Field label="Loyer actuel" suffix="€/mois" type="number" value={d.loyer_actuel} onSave={v => patch({ loyer_actuel: v ?? 0 })} />
          <Field label="Crédits conservés" suffix="€/mois" type="number" value={d.credits_conserves} onSave={v => patch({ credits_conserves: v ?? 0 })} />
          <Field label="Pension versée" suffix="€/mois" type="number" value={d.pension_versee} onSave={v => patch({ pension_versee: v ?? 0 })} />
          <Field label="Autres revenus" suffix="€/mois" type="number" value={d.autres_revenus} onSave={v => patch({ autres_revenus: v ?? 0 })} />
          <Field label="Loyers perçus existants" suffix="€/mois" type="number" value={d.revenus_locatifs_existants} onSave={v => patch({ revenus_locatifs_existants: v ?? 0 })} />
        </div>
      </div>
      {d.emprunteurs.map((e, i) => (
        <div className="panel" key={e.id}>
          <div className="row between"><h3>Emprunteur {i + 1}</h3>
            {d.emprunteurs.length > 1 && <ConfirmButton label="Retirer" onConfirm={() => act(() => api.del(`${base}/emprunteurs/${e.id}`))} />}</div>
          <div className="fields">
            <Select label="Civilité" value={e.civilite} onSave={v => up(e, { civilite: v })} options={[["", "—"], "M.", "Mme"]} />
            <Field label="Nom" value={e.nom} onSave={v => up(e, { nom: v })} />
            <Field label="Prénom" value={e.prenom} onSave={v => up(e, { prenom: v })} />
            <Field label="Date de naissance" type="date" value={e.date_naissance} onSave={v => up(e, { date_naissance: v })} />
            <Field label="Email" type="email" value={e.email} onSave={v => up(e, { email: v })} />
            <Field label="Téléphone" type="tel" value={e.telephone} onSave={v => up(e, { telephone: v })} />
            <Field label="Profession" value={e.profession} onSave={v => up(e, { profession: v })} />
            <Field label="Employeur" value={e.employeur} onSave={v => up(e, { employeur: v })} />
            <Select label="Contrat" value={e.contrat} onSave={v => up(e, { contrat: v })} options={CONTRATS} />
            <Field label="Ancienneté" suffix="mois" type="number" value={e.anciennete_mois} onSave={v => up(e, { anciennete_mois: v ?? 0 })} />
            <Field label="Revenus nets avant IR" suffix="€/mois" type="number" value={e.revenus_nets_mensuels} onSave={v => up(e, { revenus_nets_mensuels: v ?? 0 })} />
            <Field label="Nombre de mois de salaire" type="number" step="0.5" value={e.nb_mois_salaire} onSave={v => up(e, { nb_mois_salaire: v ?? 12 })} />
            <Check label="Période d'essai validée" value={e.periode_essai_validee} onSave={v => up(e, { periode_essai_validee: v })} />
            <Check label="Fumeur" value={e.fumeur} onSave={v => up(e, { fumeur: v })} />
          </div>
        </div>))}
      <div><button className="btn" onClick={() => act(() => api.post(`${base}/emprunteurs`, { nom: d.emprunteurs[0]?.nom || "Co-emprunteur" }), "Co-emprunteur ajouté")}>Ajouter un co-emprunteur</button></div>
    </div>
  );
}

/* ------------------------------------------------------------ Financement */
function Financement({ d, a, act, patch, base }) {
  const p = a.plan;
  const [amort, setAmort] = useState(null);
  const upPret = (x, champs) => act(() => api.patch(`${base}/prets/${x.id}`, champs));
  const voirAmort = async pretId => {
    if (amort?.id === pretId) return setAmort(null);
    const rows = await api.get(`${base}/echeancier/${pretId}`);
    setAmort({ id: pretId, rows });
  };
  const annuel = rows => {
    const out = [];
    for (let i = 0; i < rows.length; i += 12) {
      const s = rows.slice(i, i + 12);
      out.push({ annee: i / 12 + 1, int: s.reduce((x, l) => x + l.interets, 0), cap: s.reduce((x, l) => x + l.capital, 0), assu: s.reduce((x, l) => x + l.assurance, 0), crd: s[s.length - 1].crd });
    }
    return out;
  };
  return (
    <div className="grid g2">
      <div className="stack">
        <div className="panel">
          <h3>Projet</h3>
          <div className="fields">
            <Select label="Type" value={d.projet_type} onSave={v => patch({ projet_type: v })} options={["Résidence principale", "Résidence secondaire", "Locatif", "Professionnel"]} />
            <Select label="Nature" value={d.projet_nature} onSave={v => patch({ projet_nature: v })} options={[["ancien", "Ancien"], ["neuf", "Neuf"], ["vefa", "VEFA"], ["construction", "Construction"]]} />
            <Field label="Ville" value={d.ville} onSave={v => patch({ ville: v })} />
            <Field label="Code postal" value={d.code_postal} onSave={v => patch({ code_postal: v })} />
            <Field label="Prix du bien" suffix="€" type="number" value={d.prix} onSave={v => patch({ prix: v ?? 0 })} />
            <Field label="Travaux" suffix="€" type="number" value={d.travaux} onSave={v => patch({ travaux: v ?? 0 })} />
            {d.projet_type === "Locatif" && <Field label="Loyer attendu" suffix="€/mois" type="number" value={d.loyer_attendu} onSave={v => patch({ loyer_attendu: v ?? 0 })} />}
          </div>
        </div>
        <div className="panel">
          <h3>Frais et apport</h3>
          <div className="fields">
            <Field label="Frais de notaire" suffix={d.frais_notaire === null ? `vide = estimation ${eur(p.frais_notaire)}` : "€"} type="number" value={d.frais_notaire} onSave={v => patch({ frais_notaire: v })} />
            <Field label="Garantie" suffix="€" type="number" value={d.garantie} onSave={v => patch({ garantie: v ?? 0 })} />
            <Field label="Frais de dossier" suffix="€" type="number" value={d.frais_dossier} onSave={v => patch({ frais_dossier: v ?? 0 })} />
            <Field label="Honoraires courtage" suffix="€" type="number" value={d.honoraires} onSave={v => patch({ honoraires: v ?? 0 })} />
            <Field label="Apport" suffix="€" type="number" value={d.apport} onSave={v => patch({ apport: v ?? 0 })} />
          </div>
        </div>
        {d.prets.map(x => {
          const calc = p.prets.find(l => l.id === x.id) || {};
          return (
            <div className="panel" key={x.id}>
              <div className="row between"><h3>{x.libelle}</h3><ConfirmButton label="Retirer" onConfirm={() => act(() => api.del(`${base}/prets/${x.id}`))} /></div>
              <div className="fields">
                <Field label="Libellé" value={x.libelle} onSave={v => upPret(x, { libelle: v })} />
                <Select label="Type" value={x.type} onSave={v => upPret(x, { type: v })} options={[["amortissable", "Amortissable"], ["ptz", "PTZ"], ["in_fine", "In fine"], ["relais", "Relais"]]} />
                <Check label="Montant = solde du plan" value={x.ajuste} onSave={v => upPret(x, { ajuste: v })} />
                <Field label="Montant" suffix="€" type="number" value={x.ajuste ? Math.round(calc.montant || 0) : x.montant} disabled={x.ajuste} onSave={v => upPret(x, { montant: v ?? 0 })} />
                <Field label="Taux nominal" suffix="%" type="number" step="0.01" value={x.taux} onSave={v => upPret(x, { taux: v ?? 0 })} />
                <Field label="Durée" suffix="mois" type="number" value={x.duree_mois} onSave={v => upPret(x, { duree_mois: v ?? 1 })} />
                <Select label="Différé" value={x.differe_type} onSave={v => upPret(x, { differe_type: v })} options={[["aucun", "Aucun"], ["partiel", "Partiel (intérêts payés)"], ["total", "Total (intérêts capitalisés)"]]} />
                {x.differe_type !== "aucun" && <Field label="Durée du différé" suffix="mois" type="number" value={x.differe_mois} onSave={v => upPret(x, { differe_mois: v ?? 0 })} />}
                <Field label="Assurance" suffix="% capital initial" type="number" step="0.01" value={x.taux_assurance} onSave={v => upPret(x, { taux_assurance: v ?? 0 })} />
              </div>
              <div className="row small muted" style={{ marginTop: 10 }}>
                <span>Échéance hors assurance <strong className="num">{eur2(calc.mensualite_hors_assurance)}</strong></span>·
                <span>Assurance <strong className="num">{eur2(calc.assurance_mensuelle)}</strong></span>·
                <span>Intérêts <strong className="num">{eur(calc.cout_interets)}</strong></span>
                <button className="btn small" onClick={() => voirAmort(x.id)}>{amort?.id === x.id ? "Masquer" : "Tableau d'amortissement"}</button>
              </div>
              {amort?.id === x.id && (
                <div className="tablewrap" style={{ marginTop: 10, maxHeight: 360, overflowY: "auto" }}><table>
                  <thead><tr><th>Année</th><th className="r">Intérêts</th><th className="r">Capital</th><th className="r">Assurance</th><th className="r">Capital restant</th></tr></thead>
                  <tbody>{annuel(amort.rows).map(r => <tr key={r.annee}><td className="num">{r.annee}</td><td className="r num">{eur(r.int)}</td><td className="r num">{eur(r.cap)}</td><td className="r num">{eur(r.assu)}</td><td className="r num">{eur(r.crd)}</td></tr>)}</tbody>
                </table></div>)}
            </div>);
        })}
        <div className="row">
          <button className="btn" onClick={() => act(() => api.post(`${base}/prets`, { libelle: "PTZ", type: "ptz", taux: 0, duree_mois: 300, differe_mois: 180, differe_type: "total", ordre: 0 }))}>Ajouter un PTZ</button>
          <button className="btn" onClick={() => act(() => api.post(`${base}/prets`, { libelle: "Prêt relais", type: "relais", taux: 4, duree_mois: 24, ordre: 9 }))}>Ajouter un prêt relais</button>
          <button className="btn" onClick={() => act(() => api.post(`${base}/prets`, { libelle: "Prêt complémentaire", type: "amortissable", taux: 1, duree_mois: 240, ordre: 5 }))}>Autre prêt</button>
        </div>
        <p className="muted small">Les conditions du PTZ (zone, plafonds de revenus, quotité, différé) évoluent : vérifiez-les pour chaque dossier, le logiciel ne les calcule pas.</p>
      </div>
      <div className="stack">
        <div className="panel">
          <h3>Plan de financement</h3>
          <div className="lines">
            <Line k="Prix du bien" v={eur(p.prix)} />
            <Line k={`Frais de notaire${p.frais_notaire_estime ? " (estimation)" : ""}`} v={eur(p.frais_notaire)} />
            <Line k="Travaux" v={eur(p.travaux)} />
            <Line k="Garantie" v={eur(p.garantie)} />
            <Line k="Frais de dossier" v={eur(p.frais_dossier)} />
            <Line k="Honoraires courtage" v={eur(p.honoraires)} />
            <Line total k="Coût total de l'opération" v={eur(p.cout_operation)} />
            <Line k="Apport" v={`− ${eur(p.apport)}`} />
            {p.prets.map(l => <Line key={l.id} k={`${l.libelle}${l.type === "relais" ? " (relais)" : ""}`} v={`− ${eur(l.montant)}`} />)}
            <Line total k="Écart du plan" v={eur(p.ecart_plan)} />
          </div>
          {Math.abs(p.ecart_plan) > 1 && <div className="alert bloquant" style={{ marginTop: 10 }}>Le plan n'est pas équilibré. Cochez « Montant = solde du plan » sur le prêt principal ou ajustez les montants.</div>}
        </div>
        <div className="panel">
          <h3>Coût du crédit</h3>
          <div className="lines">
            <Line k="Total emprunté" v={eur(p.total_emprunte)} />
            <Line k="Mensualité initiale (assurance comprise)" v={eur2(p.mensualite_initiale)} />
            <Line k="Mensualité maximale" v={eur2(p.mensualite_max)} />
            <Line k="Intérêts" v={eur(p.cout_interets)} />
            <Line k="Assurance" v={eur(p.cout_assurance)} />
            <Line total k="Coût total (intérêts, assurance, frais)" v={eur(p.cout_total_credit)} />
            <Line k="TAEG estimé" v={taux(p.taeg_estime)} />
          </div>
          <Profil valeurs={p.profil_mensualites} />
          <p className="muted small">TAEG estimé par calcul actuariel sur les flux (frais de dossier, garantie et courtage inclus). Seul le TAEG de l'offre de prêt fait foi.</p>
        </div>
        <Ratios a={a} />
      </div>
    </div>
  );
}

function Profil({ valeurs }) {
  if (!valeurs || valeurs.length < 2) return null;
  const max = Math.max(...valeurs) || 1;
  const w = 300, h = 60, step = w / (valeurs.length - 1);
  const pts = valeurs.map((v, i) => `${(i * step).toFixed(1)},${(h - 4 - (v / max) * (h - 12)).toFixed(1)}`).join(" ");
  return (
    <div style={{ marginTop: 12 }}>
      <div className="muted small">Mensualité totale par année (1 → {valeurs.length})</div>
      <svg className="spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" role="img" aria-label="Évolution de la mensualité">
        <polygon points={`0,${h} ${pts} ${w},${h}`} fill="var(--accent-soft)" />
        <polyline points={pts} fill="none" stroke="var(--accent)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
  );
}

/* ------------------------------------------------------------ Pièces */
function Pieces({ d, a, act, base, toast }) {
  const [syn, setSyn] = useState(null);
  const [busy, setBusy] = useState(null);
  useEffect(() => { api.get(`${base}/synthese`).then(setSyn).catch(() => {}); }, [base, d.updated_at]);
  const docs = Object.fromEntries(d.documents.map(x => [x.id, x]));
  const attendues = new Set(a.pieces.map(p => p.categorie));
  const autres = d.documents.filter(x => !attendues.has(x.categorie));

  const deposer = async (categorie, files) => {
    setBusy(categorie);
    for (const f of files) {
      const fd = new FormData(); fd.append("categorie", categorie); fd.append("fichier", f);
      await act(() => api.upload(`${base}/documents`, fd), `${f.name} déposé`);
    }
    setBusy(null);
  };
  const Doc = ({ x }) => <DocLigne x={x} base={base} act={act} />;

  return (
    <div className="grid g2">
      <div className="panel">
        <div className="row between"><h3 style={{ margin: 0 }}>Pièces attendues pour ce profil</h3>
          <span className="muted small num">{a.pieces.filter(p => p.statut === "valide").length} validées / {a.pieces.length}</span></div>
        <p className="muted small">Liste générée selon le contrat, le projet et le plan de financement. Fichiers chiffrés au dépôt (PDF, JPEG, PNG, HEIC, WEBP ; 15 Mo max).</p>
        {a.pieces.map(p => (
          <div className="piece" key={p.categorie}>
            <span>{p.libelle}</span>
            <span className="row">
              <span className={`pill ${p.statut === "valide" ? "ok" : p.statut === "recu" ? "warn" : "bad"}`}>{{ valide: "validée", recu: "à contrôler", refuse: "refusée", manquant: "manquante" }[p.statut]}</span>
              <label className="btn small" style={{ cursor: "pointer" }}>
                {busy === p.categorie ? "Envoi…" : "Déposer"}
                <input type="file" multiple hidden accept=".pdf,.jpg,.jpeg,.png,.heic,.webp" onChange={e => { deposer(p.categorie, [...e.target.files]); e.target.value = ""; }} />
              </label>
            </span>
            {p.documents.length > 0 && <div className="docs">{p.documents.map(i => docs[i] && <Doc key={i} x={docs[i]} />)}</div>}
          </div>))}
        {autres.length > 0 && <>
          <h3 style={{ marginTop: 16 }}>Autres documents</h3>
          <div className="stack" style={{ gap: 4 }}>{autres.map(x => <Doc key={x.id} x={x} />)}</div>
        </>}
      </div>
      <div className="stack">
      <EspacePanel d={d} base={base} toast={toast} />
      <div className="panel">
        <div className="row between" style={{ marginBottom: 10 }}>
          <h3 style={{ margin: 0 }}>Mail de relance client</h3>
          <button className="btn small" disabled={!syn?.relance} onClick={() => copier(syn.relance, toast)}>Copier</button>
        </div>
        {syn?.relance ? <pre className="synth">{syn.relance}</pre> : <div className="alert ok">Toutes les pièces attendues sont reçues.</div>}
      </div>
      </div>
    </div>
  );
}

function DocLigne({ x, base, act }) {
  const [refus, setRefus] = useState(null); // null = fermé, sinon motif en cours de saisie
  return (
    <div className="doc">
      <a href={`${base}/documents/${x.id}/fichier`} target="_blank" rel="noreferrer">{x.nom_fichier}</a>
      <span className="muted small">{(x.taille / 1024).toFixed(0)} Ko · {fdatetime(x.created_at)}</span>
      {x.source === "client" && <span className="pill info">déposé par le client</span>}
      <span className={`pill ${x.statut === "valide" ? "ok" : x.statut === "refuse" ? "bad" : "warn"}`}>{x.statut === "recu" ? "à contrôler" : x.statut}</span>
      {x.statut === "refuse" && x.commentaire && <span className="small" style={{ color: "var(--bad)" }}>Motif : {x.commentaire}</span>}
      <span style={{ marginLeft: "auto" }} className="row">
        {x.statut !== "valide" && <button className="btn small" onClick={() => act(() => api.patch(`${base}/documents/${x.id}`, { statut: "valide" }))}>Valider</button>}
        {x.statut !== "refuse" && refus === null && <button className="btn small" onClick={() => setRefus("")}>Refuser</button>}
        <ConfirmButton label="Supprimer" onConfirm={() => act(() => api.del(`${base}/documents/${x.id}`))} />
      </span>
      {refus !== null && (
        <form className="row" style={{ width: "100%" }} onSubmit={e => { e.preventDefault(); act(() => api.patch(`${base}/documents/${x.id}`, { statut: "refuse", commentaire: refus.trim() })); setRefus(null); }}>
          <input id={`motif-${x.id}`} className="input" style={{ flex: "1 1 220px" }} autoFocus placeholder="Motif visible par le client (ex. : pièce expirée, page manquante)" value={refus} onChange={e => setRefus(e.target.value)} />
          <button type="button" className="btn small" onClick={() => setRefus(null)}>Annuler</button>
          <button className="btn small danger">Refuser</button>
        </form>)}
    </div>
  );
}

function EspacePanel({ d, base, toast }) {
  const [esp, setEsp] = useState(undefined);
  const [nouveau, setNouveau] = useState(null); // lien + code, affichés une seule fois
  useEffect(() => { api.get(`${base}/espace`).then(setEsp).catch(() => setEsp(null)); }, [base, d.updated_at]);
  const creer = async () => {
    try { const r = await api.post(`${base}/espace`); setNouveau({ url: window.location.origin + r.chemin, code: r.code }); setEsp(r); }
    catch (e) { toast(e.message, true); }
  };
  const revoquer = async () => {
    try { setEsp(await api.del(`${base}/espace`)); setNouveau(null); toast("Accès client révoqué"); }
    catch (e) { toast(e.message, true); }
  };
  const prenoms = d.emprunteurs.map(e => e.prenom).filter(Boolean).join(" et ");
  const msgLien = nouveau && `Bonjour${prenoms ? ` ${prenoms}` : ""},

Pour avancer sur votre dossier de financement, vous pouvez déposer vos justificatifs directement ici :
${nouveau.url}

Je vous envoie le code d'accès par SMS, séparément.

Bien cordialement,`;
  const msgCode = nouveau && `Votre code d'accès pour déposer vos justificatifs : ${nouveau.code}`;
  const actif = esp?.statut === "actif";
  const tone = { actif: "ok", "expiré": "neutral", "révoqué": "neutral", "verrouillé": "bad" };
  if (esp === undefined) return null;
  return (
    <div className="panel">
      <div className="row between" style={{ marginBottom: 10 }}>
        <h3 style={{ margin: 0 }}>Espace client</h3>
        {esp && <span className={`pill ${tone[esp.statut]}`}>{esp.statut}</span>}
      </div>
      {nouveau ? (
        <div className="stack">
          <div className="alert attention">Le lien et le code ne s'affichent qu'une fois. Envoyez-les <strong>par deux canaux différents</strong> : le lien par e-mail, le code par SMS.</div>
          <div className="lines">
            <div className="line"><span className="k">Lien</span><span className="num small" style={{ wordBreak: "break-all", textAlign: "right" }}>{nouveau.url}</span></div>
            <div className="line"><span className="k">Code</span><span className="num" style={{ fontSize: 20, letterSpacing: ".2em" }}>{nouveau.code}</span></div>
          </div>
          <div className="row">
            <button className="btn small" onClick={() => copier(msgLien, toast)}>Copier le mail avec le lien</button>
            <button className="btn small" onClick={() => copier(msgCode, toast)}>Copier le SMS avec le code</button>
            <button className="btn ghost small" onClick={() => setNouveau(null)}>J'ai envoyé</button>
          </div>
        </div>
      ) : (
        <div className="stack">
          {!esp && <p className="muted small" style={{ margin: 0 }}>Le client reçoit un lien et un code pour déposer lui-même ses pièces depuis son téléphone. Il ne voit ni les montants ni l'analyse du dossier.</p>}
          {esp && <div className="lines small">
            <Line k="Créé le" v={fdatetime(esp.created_at)} />
            <Line k="Expire le" v={fdate(esp.expire_le)} />
            <Line k="Dernière visite du client" v={esp.dernier_acces ? fdatetime(esp.dernier_acces) : "jamais"} />
            <Line k="Fichiers déposés" v={esp.nb_depots} />
            {esp.echecs > 0 && <Line k="Codes erronés" v={esp.echecs} />}
          </div>}
          <div className="row">
            <button className="btn primary small" onClick={creer}>{esp ? "Générer un nouveau lien" : "Créer l'accès client"}</button>
            {actif && <ConfirmButton label="Révoquer l'accès" confirm="Révoquer" onConfirm={revoquer} />}
          </div>
          {esp && actif && <p className="muted small" style={{ margin: 0 }}>Le code n'est plus affichable. S'il est perdu, générez un nouveau lien : l'ancien sera désactivé.</p>}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------ Banques */
function Banques({ d, a, act, base }) {
  const cmp = Object.fromEntries(a.offres.map(o => [o.id, o]));
  const up = (o, champs) => act(() => api.patch(`${base}/offres/${o.id}`, champs));
  const principal = d.prets.find(p => p.ajuste) || d.prets[0];
  return (
    <div className="stack">
      <div className="panel flush"><div className="tablewrap"><table>
        <thead><tr><th>Banque</th><th>Statut</th><th className="r">Taux</th><th className="r">Durée</th><th className="r">Assurance</th><th className="r">Mensualité</th><th className="r">Coût total</th><th className="r">TAEG est.</th><th className="r">Écart</th></tr></thead>
        <tbody>
          {d.offres.length === 0 && <tr><td colSpan={9} className="muted">Aucune banque consultée. Ajoutez chaque proposition pour les comparer sur le même montant.</td></tr>}
          {d.offres.map(o => { const c = cmp[o.id] || {}; return (
            <tr key={o.id} className={c.meilleure ? "best" : ""}>
              <td><strong>{o.banque}</strong>{c.meilleure && d.offres.length > 1 && <> <span className="pill acc">meilleur coût</span></>}</td>
              <td><span className={`pill ${/accept|ferme|émise/i.test(o.statut) ? "ok" : /principe/i.test(o.statut) ? "acc" : o.statut === "Refus" ? "bad" : "neutral"}`}>{o.statut}</span></td>
              <td className="r num">{taux(o.taux)}</td><td className="r num">{o.duree_mois / 12} ans</td><td className="r num">{taux(o.taux_assurance)}</td>
              <td className="r num">{eur2(c.mensualite)}</td><td className="r num">{eur(c.cout_total)}</td><td className="r num">{taux(c.taeg_estime)}</td>
              <td className="r num">{c.ecart ? `+${eur(c.ecart)}` : "—"}</td>
            </tr>); })}
        </tbody>
      </table></div></div>
      <p className="muted small" style={{ margin: 0 }}>Comparaison sur {eur(a.plan.total_emprunte)} : intérêts + assurance + frais de dossier + garantie.</p>
      {d.offres.map(o => (
        <div className="panel" key={o.id}>
          <div className="row between"><h3>{o.banque}</h3><ConfirmButton label="Retirer" onConfirm={() => act(() => api.del(`${base}/offres/${o.id}`))} /></div>
          <div className="fields">
            <Field label="Banque" value={o.banque} onSave={v => up(o, { banque: v })} />
            <Field label="Agence" value={o.agence} onSave={v => up(o, { agence: v })} />
            <Field label="Interlocuteur" value={o.interlocuteur} onSave={v => up(o, { interlocuteur: v })} />
            <Select label="Statut" value={o.statut} onSave={v => up(o, { statut: v })} options={STATUTS_OFFRE} />
            <Field label="Envoyé le" type="date" value={o.date_envoi} onSave={v => up(o, { date_envoi: v })} />
            <Field label="Réponse le" type="date" value={o.date_reponse} onSave={v => up(o, { date_reponse: v })} />
            <Field label="Taux" suffix="%" type="number" step="0.01" value={o.taux} onSave={v => up(o, { taux: v ?? 0 })} />
            <Field label="Durée" suffix="mois" type="number" value={o.duree_mois} onSave={v => up(o, { duree_mois: v ?? 1 })} />
            <Field label="Assurance" suffix="%" type="number" step="0.01" value={o.taux_assurance} onSave={v => up(o, { taux_assurance: v ?? 0 })} />
            <Field label="Frais de dossier" suffix="€" type="number" value={o.frais_dossier} onSave={v => up(o, { frais_dossier: v ?? 0 })} />
            <Field label="Garantie" value={o.garantie_type} onSave={v => up(o, { garantie_type: v })} />
            <Field label="Coût garantie" suffix="€" type="number" value={o.garantie_cout} onSave={v => up(o, { garantie_cout: v ?? 0 })} />
            <Field label="IRA" value={o.ira} onSave={v => up(o, { ira: v })} />
            <Field label="Domiciliation" value={o.domiciliation} onSave={v => up(o, { domiciliation: v })} />
            <Field label="Modularité" value={o.modularite} onSave={v => up(o, { modularite: v })} />
            <Field label="Produits annexes" value={o.produits_annexes} onSave={v => up(o, { produits_annexes: v })} />
          </div>
          <div style={{ marginTop: 10 }}><TextArea label="Commentaire / points à négocier" rows={2} value={o.commentaire} onSave={v => up(o, { commentaire: v })} /></div>
        </div>))}
      <div><button className="btn" onClick={() => act(() => api.post(`${base}/offres`, { banque: "Nouvelle banque", taux: principal?.taux ?? 0, duree_mois: principal?.duree_mois ?? 300, taux_assurance: principal?.taux_assurance ?? 0, garantie_cout: d.garantie }), "Proposition ajoutée")}>Ajouter une proposition bancaire</button></div>
    </div>
  );
}

/* ------------------------------------------------------------ Facturation */
function FactureTab({ d, a, act, base }) {
  const f = d.facture || { honoraires: 0, commission_banque: 0, statut: "À venir" };
  const up = champs => act(() => api.patch(`${base}/facture`, champs));
  const tot = (f.honoraires || 0) + (f.commission_banque || 0);
  return (
    <div className="grid g2">
      <div className="panel">
        <h3>Rémunération</h3>
        <div className="fields">
          <Field label="Honoraires client" suffix="€ TTC" type="number" value={f.honoraires} onSave={v => up({ honoraires: v ?? 0 })} />
          <Field label="Commission bancaire" suffix="€" type="number" value={f.commission_banque} onSave={v => up({ commission_banque: v ?? 0 })} />
          <Field label="Déblocage des fonds" type="date" value={f.date_deblocage_fonds} onSave={v => up({ date_deblocage_fonds: v })} />
          <Select label="Statut" value={f.statut} onSave={v => up({ statut: v })} options={["À venir", "À facturer", "Facturé", "Payé"]} />
          <Field label="N° de facture" value={f.numero} onSave={v => up({ numero: v })} />
          <Field label="Date d'émission" type="date" value={f.date_emission} onSave={v => up({ date_emission: v })} />
          <Field label="Date de paiement" type="date" value={f.date_paiement} onSave={v => up({ date_paiement: v })} />
        </div>
      </div>
      <div className="panel">
        <h3>Récapitulatif</h3>
        <div className="lines">
          <Line k="Honoraires client" v={eur(f.honoraires)} />
          <Line k="Commission bancaire" v={eur(f.commission_banque)} />
          <Line total k="Total rémunération" v={eur(tot)} />
          <Line k="Rapporté au montant financé" v={pct(a.plan.total_emprunte ? tot / a.plan.total_emprunte : 0, 2)} />
        </div>
        <div className="alert attention" style={{ marginTop: 12 }}>Aucun honoraire ne peut être perçu avant le versement effectif des fonds (art. L519-6 du Code monétaire et financier). Le logiciel bloque le passage en « Facturé » tant que la date de déblocage n'est pas saisie.</div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ RGPD */
function Rgpd({ d, patch, session, base, toast }) {
  const nav = useNavigate();
  const [conf, setConf] = useState("");
  const [journal, setJournal] = useState(null);
  const admin = session.user.role === "admin";
  useEffect(() => { if (admin) api.get(`/api/audit?dossier_id=${d.id}&limite=100`).then(setJournal).catch(() => {}); }, [admin, d.id, d.updated_at]);
  const exporter = async () => {
    try {
      const data = await api.get(`/api/rgpd/export/${d.id}`);
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
      toast("Export JSON copié dans le presse-papiers");
    } catch (e) { toast(e.message || "Export impossible", true); }
  };
  const effacer = async () => {
    try { await api.del(`/api/rgpd/effacer/${d.id}?confirmation=${encodeURIComponent(conf)}`); toast("Dossier effacé définitivement"); nav("/dossiers"); }
    catch (e) { toast(e.message, true); }
  };
  return (
    <div className="grid g2">
      <div className="stack">
        <div className="panel">
          <h3>Information et consentement</h3>
          <Check label="Le client a reçu l'information RGPD (finalités, durée de conservation, droits)" value={d.consentement_rgpd} onSave={v => patch({ consentement_rgpd: v })} />
        </div>
        <div className="panel">
          <h3>Droit d'accès et de portabilité</h3>
          <p className="muted small">Exporte toutes les données du dossier au format JSON (hors fichiers).</p>
          <button className="btn" onClick={exporter}>Copier l'export JSON</button>
        </div>
        {admin && <div className="panel">
          <h3>Droit à l'effacement</h3>
          <p className="muted small">Suppression définitive du dossier et de toutes ses pièces. Irréversible. Saisissez la référence <strong className="num">{d.ref}</strong> pour confirmer.</p>
          <div className="row"><input id="confirm-ref" className="input" style={{ width: 200 }} value={conf} onChange={e => setConf(e.target.value)} placeholder={d.ref} />
            <button className="btn danger" disabled={conf !== d.ref} onClick={effacer}>Effacer définitivement</button></div>
        </div>}
      </div>
      {admin && <div className="panel">
        <h3>Historique des accès et modifications</h3>
        <div className="tablewrap" style={{ maxHeight: 480, overflowY: "auto" }}><table>
          <thead><tr><th>Date</th><th>Utilisateur</th><th>Action</th></tr></thead>
          <tbody>{(journal || []).map(j => <tr key={j.id}><td className="small num">{fdatetime(j.date)}</td><td className="small">{j.utilisateur}</td><td className="small">{j.action}{j.details?.etape ? ` → ${j.details.etape}` : ""}</td></tr>)}</tbody>
        </table></div>
      </div>}
    </div>
  );
}
