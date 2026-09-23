import { useEffect, useState } from "react";
import { api } from "../api";
import { fdate } from "../format";
import { Field, Select, useToast } from "../components/ui";

export default function Parametres({ session, onChange }) {
  const admin = session.user.role === "admin";
  const toast = useToast();
  const [cab, setCab] = useState(session.cabinet);
  const [users, setUsers] = useState([]);
  const [nu, setNu] = useState({ nom: "", email: "", role: "courtier", password: "" });
  const [pw, setPw] = useState({ ancien: "", nouveau: "" });
  const [purge, setPurge] = useState(null);
  useEffect(() => {
    api.get("/api/cabinet/utilisateurs").then(setUsers).catch(() => {});
    if (admin) api.get("/api/rgpd/a-purger").then(setPurge).catch(() => {});
  }, [admin]);

  const saveCab = async champs => {
    try { setCab(await api.patch("/api/cabinet", champs)); onChange(); toast("Paramètre enregistré"); } catch (e) { toast(e.message, true); }
  };
  const usure = (k, v) => {
    const t = { ...(cab.taux_usure || {}) };
    if (v === null || v === "") delete t[k]; else t[k] = v;
    saveCab({ taux_usure: t });
  };
  const creer = async e => {
    e.preventDefault();
    try { const u = await api.post("/api/cabinet/utilisateurs", nu); setUsers([...users, u]); setNu({ nom: "", email: "", role: "courtier", password: "" }); toast("Compte créé"); }
    catch (x) { toast(x.message, true); }
  };
  const majUser = async (u, champs) => {
    try { const r = await api.patch(`/api/cabinet/utilisateurs/${u.id}`, champs); setUsers(users.map(x => x.id === u.id ? r : x)); }
    catch (x) { toast(x.message, true); }
  };
  const changerMdp = async e => {
    e.preventDefault();
    try { await api.post("/api/auth/mot-de-passe", pw); setPw({ ancien: "", nouveau: "" }); toast("Mot de passe modifié"); }
    catch (x) { toast(x.message, true); }
  };

  return (
    <div>
      <div className="head"><div><h1>Paramètres</h1><p className="sub">{cab.nom}{cab.orias && ` · ORIAS ${cab.orias}`}</p></div></div>
      <div className="grid g2">
        <div className="stack">
          <div className="panel">
            <h3>Règles d'analyse du cabinet</h3>
            {!admin && <p className="muted small">Modifiable par l'administrateur uniquement.</p>}
            <fieldset disabled={!admin} style={{ border: 0, padding: 0, margin: 0 }}>
              <div className="fields">
                <Field label="Nom du cabinet" value={cab.nom} onSave={v => saveCab({ nom: v })} />
                <Field label="N° ORIAS" value={cab.orias || ""} onSave={v => saveCab({ orias: v })} />
                <Field label="Plafond d'endettement" suffix="ex. 0.35" type="number" step="0.01" value={cab.plafond_endettement} onSave={v => saveCab({ plafond_endettement: v })} />
                <Field label="Durée max." suffix="mois" type="number" value={cab.duree_max_mois} onSave={v => saveCab({ duree_max_mois: v })} />
                <Field label="Durée max. neuf / gros travaux" suffix="mois" type="number" value={cab.duree_max_mois_neuf} onSave={v => saveCab({ duree_max_mois_neuf: v })} />
                <Field label="Reste à vivre de base" suffix="€" type="number" value={cab.reste_a_vivre_base} onSave={v => saveCab({ reste_a_vivre_base: v })} />
                <Field label="+ par personne" suffix="€" type="number" value={cab.reste_a_vivre_par_personne} onSave={v => saveCab({ reste_a_vivre_par_personne: v })} />
                <Field label="Pondération des loyers" suffix="ex. 0.70" type="number" step="0.05" value={cab.ponderation_loyers} onSave={v => saveCab({ ponderation_loyers: v })} />
                <Field label="Conservation des dossiers" suffix="mois" type="number" value={cab.duree_conservation_mois} onSave={v => saveCab({ duree_conservation_mois: v })} />
              </div>
            </fieldset>
          </div>
          <div className="panel">
            <h3>Taux d'usure (TAEG maximum)</h3>
            <p className="muted small">Publiés chaque trimestre par la Banque de France. Saisissez les valeurs officielles du trimestre en cours : sans elles, le contrôle d'usure est désactivé.</p>
            <fieldset disabled={!admin} style={{ border: 0, padding: 0, margin: 0 }}>
              <div className="fields">
                <Field label="Trimestre" placeholder="ex. T4 2026" value={cab.taux_usure_trimestre || ""} onSave={v => saveCab({ taux_usure_trimestre: v })} />
                <Field label="Moins de 10 ans" suffix="%" type="number" step="0.01" value={cab.taux_usure?.moins_10_ans ?? ""} onSave={v => usure("moins_10_ans", v)} />
                <Field label="10 à 20 ans" suffix="%" type="number" step="0.01" value={cab.taux_usure?.["10_20_ans"] ?? ""} onSave={v => usure("10_20_ans", v)} />
                <Field label="20 ans et plus" suffix="%" type="number" step="0.01" value={cab.taux_usure?.["20_ans_et_plus"] ?? ""} onSave={v => usure("20_ans_et_plus", v)} />
              </div>
            </fieldset>
          </div>
          <form className="panel" onSubmit={changerMdp}>
            <h3>Mon mot de passe</h3>
            <div className="fields">
              <div className="f"><label htmlFor="pw-a">Actuel</label><input id="pw-a" type="password" autoComplete="current-password" value={pw.ancien} onChange={e => setPw({ ...pw, ancien: e.target.value })} /></div>
              <div className="f"><label htmlFor="pw-n">Nouveau</label><input id="pw-n" type="password" autoComplete="new-password" value={pw.nouveau} onChange={e => setPw({ ...pw, nouveau: e.target.value })} /></div>
            </div>
            <button className="btn" style={{ marginTop: 10 }}>Modifier</button>
          </form>
        </div>
        <div className="stack">
          <div className="panel">
            <h3>Utilisateurs</h3>
            <div className="tablewrap"><table>
              <thead><tr><th>Nom</th><th>Rôle</th><th>Actif</th></tr></thead>
              <tbody>{users.map(u => (
                <tr key={u.id}>
                  <td>{u.nom}<div className="muted small">{u.email}</div></td>
                  <td>{admin ? <select className="input" style={{ width: "auto" }} value={u.role} onChange={e => majUser(u, { role: e.target.value })}><option value="admin">Admin</option><option value="courtier">Courtier</option><option value="assistant">Assistant</option></select> : u.role}</td>
                  <td>{admin ? <input type="checkbox" checked={u.actif} onChange={e => majUser(u, { actif: e.target.checked })} aria-label={`Compte actif : ${u.nom}`} /> : (u.actif ? "oui" : "non")}</td>
                </tr>))}</tbody>
            </table></div>
            {admin && <form onSubmit={creer} style={{ marginTop: 14 }}>
              <div className="fields">
                <div className="f"><label htmlFor="nu-nom">Nom</label><input id="nu-nom" required value={nu.nom} onChange={e => setNu({ ...nu, nom: e.target.value })} /></div>
                <div className="f"><label htmlFor="nu-email">Email</label><input id="nu-email" type="email" required value={nu.email} onChange={e => setNu({ ...nu, email: e.target.value })} /></div>
                <Select label="Rôle" value={nu.role} onSave={v => setNu({ ...nu, role: v })} options={[["courtier", "Courtier"], ["assistant", "Assistant"], ["admin", "Admin"]]} />
                <div className="f"><label htmlFor="nu-pw">Mot de passe provisoire</label><input id="nu-pw" type="password" autoComplete="new-password" required value={nu.password} onChange={e => setNu({ ...nu, password: e.target.value })} /></div>
              </div>
              <button className="btn primary" style={{ marginTop: 10 }}>Créer le compte</button>
            </form>}
          </div>
          {admin && purge && <div className="panel">
            <h3>Dossiers au-delà de la durée de conservation</h3>
            {purge.length === 0 ? <p className="muted">Aucun dossier à purger.</p> :
              <ul>{purge.map(p => <li key={p.id}><a href={`/dossiers/${p.id}`}>{p.nom}</a> <span className="muted small">· {p.ref} · dernière activité {fdate(p.updated_at)}</span></li>)}</ul>}
          </div>}
        </div>
      </div>
    </div>
  );
}
