import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { eur, etapeTone, fdate } from "../format";
import { useToast } from "../components/ui";

const STATUTS = ["À venir", "À facturer", "Facturé", "Payé"];

export default function Facturation() {
  const [rows, setRows] = useState(null);
  const nav = useNavigate();
  const toast = useToast();
  useEffect(() => { api.get("/api/facturation").then(setRows).catch(e => toast(e.message, true)); }, [toast]);
  if (!rows) return <p className="muted">Chargement…</p>;
  const tot = r => (r.honoraires || 0) + (r.commission_banque || 0);
  return (
    <div>
      <div className="head"><div><h1>Facturation</h1><p className="sub">Honoraires clients et commissions bancaires</p></div></div>
      <div className="kpis">{STATUTS.map(s => <div className="kpi" key={s}><div className="v">{eur(rows.filter(r => r.statut === s).reduce((a, r) => a + tot(r), 0))}</div><div className="l">{s}</div></div>)}</div>
      <div className="panel flush"><div className="tablewrap"><table>
        <thead><tr><th>Dossier</th><th>Étape</th><th className="r">Honoraires</th><th className="r">Commission</th><th className="r">Total</th><th>Déblocage</th><th>Facture</th><th>Statut</th></tr></thead>
        <tbody>{rows.map(r => (
          <tr key={r.dossier_id} className="click" onClick={() => nav(`/dossiers/${r.dossier_id}`)}>
            <td><strong>{r.nom}</strong><div className="muted small num">{r.ref}</div></td>
            <td><span className={`pill ${etapeTone(r.etape)}`}>{r.etape}</span></td>
            <td className="r num">{eur(r.honoraires)}</td><td className="r num">{eur(r.commission_banque)}</td><td className="r num"><strong>{eur(tot(r))}</strong></td>
            <td className="small">{fdate(r.date_deblocage_fonds)}</td>
            <td className="small num">{r.numero || "—"}{r.date_emission && <span className="muted"> · {fdate(r.date_emission)}</span>}</td>
            <td><span className={`pill ${{ "Payé": "ok", "Facturé": "acc", "À facturer": "warn" }[r.statut] || "neutral"}`}>{r.statut}</span></td>
          </tr>))}</tbody>
      </table></div></div>
    </div>
  );
}
