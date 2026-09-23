import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { ETAPES, eur, endettementTone, etapeTone, fdate, pct } from "../format";
import { useToast } from "../components/ui";

export default function Dossiers() {
  const [rows, setRows] = useState(null);
  const [q, setQ] = useState("");
  const [etape, setEtape] = useState("Toutes");
  const [archives, setArchives] = useState(false);
  const nav = useNavigate();
  const toast = useToast();
  useEffect(() => { api.get(`/api/dossiers?archives=${archives}`).then(setRows).catch(e => toast(e.message, true)); }, [archives, toast]);

  const nouveau = async () => {
    try { const d = await api.post("/api/dossiers", { emprunteurs: [{ nom: "Nouveau client" }] }); nav(`/dossiers/${d.id}`); }
    catch (e) { toast(e.message, true); }
  };
  const liste = (rows || []).filter(d => (etape === "Toutes" || d.etape === etape) && `${d.nom} ${d.ref} ${d.ville}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <div>
      <div className="head">
        <div><h1>Dossiers</h1><p className="sub">{rows ? `${rows.length} dossier${rows.length > 1 ? "s" : ""}${archives ? " archivés" : ""}` : "Chargement…"}</p></div>
        <div className="row">
          <input id="recherche" className="input" style={{ width: 240, maxWidth: "100%" }} placeholder="Client, ville, référence" value={q} onChange={e => setQ(e.target.value)} />
          <select id="filtre-etape" className="input" style={{ width: "auto" }} value={etape} onChange={e => setEtape(e.target.value)}>
            <option>Toutes</option>{ETAPES.map(e => <option key={e}>{e}</option>)}
          </select>
          <button className="btn" onClick={() => setArchives(!archives)}>{archives ? "Dossiers actifs" : "Archives"}</button>
          <button className="btn primary" onClick={nouveau}>Nouveau dossier</button>
        </div>
      </div>
      <div className="panel flush"><div className="tablewrap"><table>
        <thead><tr><th>Réf.</th><th>Client</th><th>Projet</th><th className="r">Emprunt</th><th className="r">Mensualité</th><th className="r">Endett.</th><th>Contrôles</th><th>Pièces</th><th>Étape</th><th>Mis à jour</th></tr></thead>
        <tbody>
          {liste.map(d => (
            <tr key={d.id} className="click" onClick={() => nav(`/dossiers/${d.id}`)}>
              <td className="num muted">{d.ref}</td>
              <td><strong>{d.nom}</strong>{d.courtier && <div className="muted small">{d.courtier}</div>}</td>
              <td>{d.projet_type}{d.ville && ` · ${d.ville}`}</td>
              <td className="r num">{eur(d.montant)}</td>
              <td className="r num">{eur(d.mensualite)}</td>
              <td className="r"><span className={`pill ${endettementTone(d.taux_endettement)}`}>{pct(d.taux_endettement)}</span></td>
              <td>{d.alertes_bloquantes ? <span className="pill bad">{d.alertes_bloquantes} bloquant</span> : d.alertes ? <span className="pill warn">{d.alertes}</span> : <span className="pill ok">OK</span>}</td>
              <td style={{ minWidth: 90 }}><div className="progress"><span style={{ width: `${d.pieces_total ? (d.pieces_ok / d.pieces_total) * 100 : 0}%` }} /></div><span className="muted small num">{d.pieces_ok}/{d.pieces_total}</span></td>
              <td><span className={`pill ${etapeTone(d.etape)}`}>{d.etape}</span></td>
              <td className="muted small">{fdate(d.updated_at)}</td>
            </tr>))}
          {rows && liste.length === 0 && <tr><td colSpan={10} className="muted">Aucun dossier ne correspond.</td></tr>}
        </tbody>
      </table></div></div>
    </div>
  );
}
