import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { fdatetime } from "../format";
import { useToast } from "../components/ui";

export default function Journal() {
  const [rows, setRows] = useState(null);
  const toast = useToast();
  useEffect(() => { api.get("/api/audit?limite=500").then(setRows).catch(e => toast(e.message, true)); }, [toast]);
  return (
    <div>
      <div className="head"><div><h1>Journal d'audit</h1><p className="sub">Connexions, consultations et modifications (500 dernières)</p></div></div>
      <div className="panel flush"><div className="tablewrap"><table>
        <thead><tr><th>Date</th><th>Utilisateur</th><th>Action</th><th>Objet</th><th>IP</th></tr></thead>
        <tbody>{(rows || []).map(j => (
          <tr key={j.id}>
            <td className="small num">{fdatetime(j.date)}</td>
            <td className="small">{j.utilisateur || "—"}</td>
            <td><span className={`pill ${j.action.includes("echec") || j.action.includes("rgpd") ? "bad" : "neutral"}`}>{j.action}</span></td>
            <td className="small">{j.entite === "dossier" && j.entite_id ? <Link to={`/dossiers/${j.entite_id}`}>Dossier #{j.entite_id}</Link> : j.entite}</td>
            <td className="small muted num">{j.ip}</td>
          </tr>))}</tbody>
      </table></div></div>
    </div>
  );
}
