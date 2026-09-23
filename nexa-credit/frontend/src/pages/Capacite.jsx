import { useEffect, useState } from "react";
import { api } from "../api";
import { eur, eur2, pct } from "../format";
import { Field, Line, Select } from "../components/ui";

export default function Capacite({ cabinet }) {
  const [s, setS] = useState({ revenus: 5200, charges: 250, taux: 3.3, duree_mois: 300, taux_assurance: 0.1, apport: 40000, nature: "ancien" });
  const [r, setR] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.post("/api/simulations/capacite", s).then(x => { setR(x); setErr(""); }).catch(e => setErr(e.message));
  }, [s]);
  const u = k => v => setS({ ...s, [k]: v ?? 0 });
  return (
    <div>
      <div className="head"><div><h1>Capacité d'emprunt</h1><p className="sub">Calcul au plafond d'endettement du cabinet ({pct(cabinet.plafond_endettement, 0)}), assurance comprise</p></div></div>
      <div className="grid g2">
        <div className="panel"><div className="fields">
          <Field label="Revenus nets du foyer" suffix="€/mois" type="number" value={s.revenus} onSave={u("revenus")} />
          <Field label="Crédits conservés" suffix="€/mois" type="number" value={s.charges} onSave={u("charges")} />
          <Field label="Taux" suffix="%" type="number" step="0.01" value={s.taux} onSave={u("taux")} />
          <Field label="Durée" suffix="mois" type="number" value={s.duree_mois} onSave={u("duree_mois")} />
          <Field label="Assurance" suffix="%" type="number" step="0.01" value={s.taux_assurance} onSave={u("taux_assurance")} />
          <Field label="Apport" suffix="€" type="number" value={s.apport} onSave={u("apport")} />
          <Select label="Bien" value={s.nature} onSave={v => setS({ ...s, nature: v })} options={[["ancien", "Ancien"], ["neuf", "Neuf / VEFA"]]} />
        </div></div>
        <div className="panel">
          {err && <div className="alert bloquant">{err}</div>}
          {r && <div className="lines">
            <Line k="Mensualité maximale" v={eur2(r.mensualite_max)} />
            <Line total k="Capacité d'emprunt" v={eur(r.capacite)} />
            <Line k="+ Apport" v={eur(s.apport)} />
            <Line total k="Prix accessible, frais de notaire estimés déduits" v={eur(r.prix_accessible)} />
          </div>}
          {s.duree_mois > cabinet.duree_max_mois && <div className="alert attention" style={{ marginTop: 12 }}>Au-delà de {cabinet.duree_max_mois / 12} ans, seuls les projets neufs ou avec gros travaux sont éligibles.</div>}
          <p className="muted small">Hors garantie, frais de dossier et honoraires. Le reste à vivre et la politique de chaque banque restent déterminants.</p>
        </div>
      </div>
    </div>
  );
}
