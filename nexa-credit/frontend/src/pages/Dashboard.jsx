import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { ETAPES, eur, endettementTone, fdate, pct, today } from "../format";
import { useToast } from "../components/ui";

export default function Dashboard() {
  const [dossiers, setDossiers] = useState(null);
  const [taches, setTaches] = useState([]);
  const [factu, setFactu] = useState([]);
  const nav = useNavigate();
  const toast = useToast();
  useEffect(() => {
    Promise.all([api.get("/api/dossiers"), api.get("/api/taches"), api.get("/api/facturation")])
      .then(([d, t, f]) => { setDossiers(d); setTaches(t); setFactu(f); })
      .catch(e => toast(e.message, true));
  }, [toast]);
  if (!dossiers) return <p className="muted">Chargement…</p>;

  const actifs = dossiers.filter(d => !["Facturé", "Abandonné"].includes(d.etape));
  const tot = f => (f.honoraires || 0) + (f.commission_banque || 0);
  const somme = s => factu.filter(f => f.statut === s).reduce((a, f) => a + tot(f), 0);
  const aFacturer = factu.filter(f => ["Offre émise", "Signé notaire"].includes(f.etape) && !["Facturé", "Payé"].includes(f.statut)).reduce((a, f) => a + tot(f), 0);
  const t = today();
  const urgences = dossiers.filter(d => d.date_condition_suspensive && ["Découverte", "Montage", "En banque"].includes(d.etape))
    .map(d => ({ ...d, jours: Math.round((new Date(d.date_condition_suspensive) - new Date(t)) / 864e5) }))
    .filter(d => d.jours <= 21).sort((a, b) => a.jours - b.jours);

  const nouveau = async () => {
    try { const d = await api.post("/api/dossiers", { emprunteurs: [{ nom: "Nouveau client" }] }); nav(`/dossiers/${d.id}`); }
    catch (e) { toast(e.message, true); }
  };

  return (
    <div>
      <div className="head">
        <div><h1>Tableau de bord</h1><p className="sub">{actifs.length} dossier{actifs.length > 1 ? "s" : ""} actif{actifs.length > 1 ? "s" : ""}</p></div>
        <button className="btn primary" onClick={nouveau}>Nouveau dossier</button>
      </div>
      <div className="kpis">
        <div className="kpi"><div className="v">{eur(actifs.reduce((a, d) => a + d.montant, 0))}</div><div className="l">Volume en cours de financement</div></div>
        <div className="kpi"><div className="v">{eur(aFacturer)}</div><div className="l">À facturer (offre émise / signé)</div></div>
        <div className="kpi"><div className="v">{eur(somme("Facturé"))}</div><div className="l">Facturé, non encaissé</div></div>
        <div className="kpi"><div className="v">{eur(somme("Payé"))}</div><div className="l">Encaissé</div></div>
      </div>
      <div className="stack" style={{ gap: 20 }}>
        {urgences.length > 0 && (
          <section className="panel">
            <h2>Conditions suspensives à surveiller</h2>
            <div className="stack" style={{ gap: 6 }}>
              {urgences.map(d => (
                <Link key={d.id} to={`/dossiers/${d.id}`} className={`alert ${d.jours < 0 ? "bloquant" : "attention"}`} style={{ textDecoration: "none" }}>
                  <strong>{d.nom}</strong> — {d.etape} — {d.jours < 0 ? `dépassée depuis ${-d.jours} j` : `échéance dans ${d.jours} j`} ({fdate(d.date_condition_suspensive)})
                </Link>))}
            </div>
          </section>)}
        <section>
          <h3>Pipeline</h3>
          <div className="pipe">
            {ETAPES.filter(e => e !== "Abandonné").map(e => {
              const ds = dossiers.filter(d => d.etape === e);
              return (
                <div className="col" key={e}>
                  <div className="col-h"><span>{e}</span><span className="num">{ds.length}</span></div>
                  {ds.map(d => (
                    <Link key={d.id} to={`/dossiers/${d.id}`} className="card">
                      <strong>{d.nom}</strong>
                      <span className="m"><span>{d.projet_type === "Résidence principale" ? "RP" : d.projet_type} · {d.ville || "—"}</span><span className="num">{eur(d.montant)}</span></span>
                      <span className="m">
                        <span className={`pill ${endettementTone(d.taux_endettement)}`}>{pct(d.taux_endettement)}</span>
                        {d.alertes_bloquantes > 0 ? <span className="pill bad">{d.alertes_bloquantes} bloquant{d.alertes_bloquantes > 1 ? "s" : ""}</span>
                          : d.alertes > 0 ? <span className="pill warn">{d.alertes} alerte{d.alertes > 1 ? "s" : ""}</span> : null}
                      </span>
                    </Link>))}
                </div>);
            })}
          </div>
        </section>
        <section className="panel">
          <h2>Tâches à faire</h2>
          {taches.length === 0 ? <p className="muted">Aucune tâche en attente.</p> : (
            <div className="tablewrap"><table>
              <thead><tr><th>Échéance</th><th>Tâche</th><th>Dossier</th></tr></thead>
              <tbody>{taches.slice(0, 15).map(x => (
                <tr key={x.id} className="click" onClick={() => nav(`/dossiers/${x.dossier_id}`)}>
                  <td style={{ whiteSpace: "nowrap" }}><span className={`pill ${!x.echeance ? "neutral" : x.echeance < t ? "bad" : x.echeance === t ? "warn" : "neutral"}`}>{x.echeance ? fdate(x.echeance) : "sans date"}</span></td>
                  <td>{x.libelle}</td><td className="muted">{x.dossier}</td>
                </tr>))}</tbody>
            </table></div>)}
        </section>
      </div>
    </div>
  );
}
