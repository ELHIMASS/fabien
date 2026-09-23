import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { fdate } from "../format";

const STATUT = {
  manquant: ["À envoyer", "bad"],
  recu: ["Reçue, en cours de vérification", "warn"],
  valide: ["Validée", "ok"],
  refuse: ["À renvoyer", "bad"],
};

export default function EspaceClient() {
  const { token } = useParams();
  const [etat, setEtat] = useState("chargement"); // chargement | code | ok | invalide
  const [data, setData] = useState(null);
  const [code, setCode] = useState("");
  const [err, setErr] = useState("");
  const [envoi, setEnvoi] = useState(null);
  const [info, setInfo] = useState("");

  const charger = useCallback(async () => {
    try { setData(await api.get("/api/espace/moi")); setEtat("ok"); }
    catch (e) { if (e.status === 410) { setErr(e.message); setEtat("invalide"); } else setEtat("code"); }
  }, []);
  useEffect(() => { charger(); }, [charger]);

  const connexion = async e => {
    e.preventDefault(); setErr("");
    try { await api.post(`/api/espace/${token}/connexion`, { code }); setCode(""); await charger(); }
    catch (x) { setErr(x.message); if (x.status === 410) setEtat("invalide"); }
  };

  const deposer = async (categorie, files) => {
    setEnvoi(categorie); setInfo(""); setErr("");
    let ok = 0;
    for (const f of files) {
      const fd = new FormData(); fd.append("categorie", categorie); fd.append("fichier", f);
      try { await api.upload("/api/espace/documents", fd); ok++; }
      catch (x) {
        if (x.status === 401) { setEtat("code"); setErr(x.message); break; }
        setErr(`${f.name} : ${x.message}`);
      }
    }
    setEnvoi(null);
    if (ok) setInfo(`${ok} fichier${ok > 1 ? "s" : ""} envoyé${ok > 1 ? "s" : ""}. Merci !`);
    charger();
  };

  const quitter = async () => { await api.post("/api/espace/deconnexion"); setData(null); setEtat("code"); };

  if (etat === "chargement") return null;

  if (etat === "invalide" || etat === "code") return (
    <div className="auth">
      <form className="panel stack" onSubmit={connexion}>
        <div className="brand" style={{ paddingInline: 0 }}>Espace client<small>Dépôt sécurisé de vos justificatifs</small></div>
        {etat === "invalide" ? <div className="alert bloquant">{err || "Ce lien n'est plus valide. Contactez votre courtier."}</div> : <>
          <p className="muted" style={{ margin: 0 }}>Saisissez le code à 6 chiffres que votre courtier vous a communiqué.</p>
          <div className="f"><label htmlFor="code">Code d'accès</label>
            <input id="code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} pattern="\d{6}" required
              style={{ fontFamily: "var(--mono)", fontSize: 22, letterSpacing: ".3em", textAlign: "center" }}
              value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ""))} /></div>
          {err && <div className="error" role="alert">{err}</div>}
          <button className="btn primary" style={{ justifyContent: "center" }} disabled={code.length !== 6}>Accéder à mon dossier</button>
        </>}
      </form>
    </div>
  );

  const aFaire = data.pieces.filter(p => p.statut === "manquant" || p.statut === "refuse");
  const faits = data.pieces.filter(p => p.statut === "recu" || p.statut === "valide");
  const Piece = ({ p }) => {
    const [l, tone] = STATUT[p.statut];
    return (
      <div className="piece">
        <div className="stack" style={{ gap: 4 }}>
          <strong>{p.libelle}</strong>
          <span><span className={`pill ${tone}`}>{l}</span></span>
          {p.motif_refus && <span className="small" style={{ color: "var(--bad)" }}>Motif : {p.motif_refus}</span>}
        </div>
        <label className={`btn ${p.statut === "manquant" || p.statut === "refuse" ? "primary" : ""}`} style={{ cursor: "pointer" }}>
          {envoi === p.categorie ? "Envoi…" : p.statut === "manquant" ? "Envoyer" : "Ajouter"}
          <input type="file" multiple hidden accept="image/*,.pdf,.heic" disabled={!!envoi}
            onChange={e => { deposer(p.categorie, [...e.target.files]); e.target.value = ""; }} />
        </label>
        {p.fichiers.length > 0 && <div className="docs">{p.fichiers.map((f, i) => (
          <div className="doc" key={i}><span>{f.nom}</span><span className="muted small">envoyé le {fdate(f.date)}</span></div>))}</div>}
      </div>
    );
  };

  return (
    <main style={{ maxWidth: 720, marginInline: "auto" }}>
      <div className="head">
        <div>
          <div className="brand" style={{ paddingInline: 0 }}>{data.cabinet}<small>Espace client{data.orias ? ` · ORIAS ${data.orias}` : ""}</small></div>
          <h1 style={{ marginTop: 14 }}>Bonjour{data.prenoms ? ` ${data.prenoms}` : ""}</h1>
          <p className="sub">{aFaire.length === 0 ? "Toutes les pièces demandées ont été envoyées. Merci !" : `Il reste ${aFaire.length} pièce${aFaire.length > 1 ? "s" : ""} à envoyer pour votre dossier de financement.`}</p>
        </div>
        <button className="btn ghost small" onClick={quitter}>Se déconnecter</button>
      </div>
      <div className="progress" style={{ marginBottom: 16 }}><span style={{ width: `${data.pieces.length ? (faits.length / data.pieces.length) * 100 : 0}%` }} /></div>
      {info && <div className="alert ok" role="status" style={{ marginBottom: 12 }}>{info}</div>}
      {err && <div className="alert bloquant" role="alert" style={{ marginBottom: 12 }}>{err}</div>}
      <div className="stack" style={{ gap: 16 }}>
        {aFaire.length > 0 && <section className="panel"><h3>À envoyer</h3>{aFaire.map(p => <Piece key={p.categorie} p={p} />)}</section>}
        {faits.length > 0 && <section className="panel"><h3>Déjà envoyées</h3>{faits.map(p => <Piece key={p.categorie} p={p} />)}</section>}
        <section className="panel stack small">
          <strong>Conseils</strong>
          <span>PDF de préférence. Depuis un téléphone, vous pouvez photographier le document : posez-le à plat, bien éclairé, les quatre coins visibles.</span>
          <span className="muted">Formats acceptés : PDF, JPEG, PNG, HEIC, WEBP — 15 Mo maximum par fichier. Vos documents sont chiffrés dès leur réception et seul votre courtier y a accès.</span>
          {data.courtier && <span>Une question ? Votre courtier : <strong>{data.courtier.nom}</strong> — <span className="num">{data.courtier.email}</span></span>}
          <span className="muted">Ce lien est valable jusqu'au {fdate(data.expire_le)}.</span>
        </section>
      </div>
    </main>
  );
}
