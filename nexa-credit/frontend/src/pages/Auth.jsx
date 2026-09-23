import { useEffect, useState } from "react";
import { api } from "../api";

export default function Auth({ onConnecte }) {
  const [installe, setInstalle] = useState(null);
  const [f, setF] = useState({ email: "", password: "", cabinet: "", orias: "", nom: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get("/api/auth/etat").then(r => setInstalle(r.installe)).catch(() => setInstalle(true)); }, []);
  const u = k => e => setF({ ...f, [k]: e.target.value });

  const submit = async e => {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      if (installe) await api.post("/api/auth/connexion", { email: f.email, password: f.password });
      else await api.post("/api/auth/installation", { cabinet: f.cabinet, orias: f.orias || null, nom: f.nom, email: f.email, password: f.password });
      onConnecte();
    } catch (x) { setErr(x.message); } finally { setBusy(false); }
  };
  if (installe === null) return null;

  return (
    <div className="auth">
      <form className="panel stack" onSubmit={submit}>
        <div>
          <div className="brand" style={{ paddingInline: 0 }}>NEXA CREDIT<small>Logiciel de courtage IOBSP</small></div>
          <h2 style={{ marginTop: 16, marginBottom: 0 }}>{installe ? "Connexion" : "Création du cabinet"}</h2>
          {!installe && <p className="muted small">Première utilisation : ce compte sera l'administrateur du cabinet.</p>}
        </div>
        {!installe && <>
          <div className="f"><label htmlFor="cab">Nom du cabinet</label><input id="cab" required value={f.cabinet} onChange={u("cabinet")} /></div>
          <div className="f"><label htmlFor="orias">N° ORIAS</label><input id="orias" value={f.orias} onChange={u("orias")} /></div>
          <div className="f"><label htmlFor="nom">Votre nom</label><input id="nom" required value={f.nom} onChange={u("nom")} /></div>
        </>}
        <div className="f"><label htmlFor="email">Email</label><input id="email" type="email" autoComplete="username" required value={f.email} onChange={u("email")} /></div>
        <div className="f"><label htmlFor="pw">Mot de passe</label><input id="pw" type="password" autoComplete={installe ? "current-password" : "new-password"} required value={f.password} onChange={u("password")} />
          {!installe && <span className="muted small">12 caractères minimum, majuscules, minuscules et chiffres.</span>}</div>
        {err && <div className="error" role="alert">{err}</div>}
        <button className="btn primary" disabled={busy} style={{ justifyContent: "center" }}>{installe ? "Se connecter" : "Créer le cabinet"}</button>
      </form>
    </div>
  );
}
