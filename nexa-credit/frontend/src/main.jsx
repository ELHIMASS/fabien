import { StrictMode, useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, NavLink, Route, Routes } from "react-router-dom";
import "./styles.css";
import { api } from "./api";
import { Toast, ToastCtx } from "./components/ui";
import Auth from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import Dossiers from "./pages/Dossiers";
import Dossier from "./pages/Dossier";
import Capacite from "./pages/Capacite";
import Facturation from "./pages/Facturation";
import Parametres from "./pages/Parametres";
import Journal from "./pages/Journal";

function App() {
  const [session, setSession] = useState(undefined); // undefined = chargement, null = déconnecté
  const [msg, setMsg] = useState(null);
  const toast = useCallback((text, err = false) => setMsg({ text, err, t: Date.now() }), []);

  const charger = useCallback(() => api.get("/api/auth/moi").then(setSession).catch(() => setSession(null)), []);
  useEffect(() => { charger(); }, [charger]);
  useEffect(() => {
    const h = () => setSession(null);
    window.addEventListener("nexa:deconnecte", h);
    return () => window.removeEventListener("nexa:deconnecte", h);
  }, []);
  useEffect(() => { if (!msg) return; const t = setTimeout(() => setMsg(null), 2600); return () => clearTimeout(t); }, [msg]);

  if (session === undefined) return null;
  if (!session) return <ToastCtx.Provider value={toast}><Auth onConnecte={charger} /><Toast msg={msg} /></ToastCtx.Provider>;

  const admin = session.user.role === "admin";
  const deconnexion = async () => { await api.post("/api/auth/deconnexion"); setSession(null); };

  return (
    <ToastCtx.Provider value={toast}>
      <div className="app">
        <aside className="side">
          <div className="brand">NEXA CREDIT<small>{session.cabinet.nom}</small></div>
          <nav className="nav">
            <NavLink to="/" end>Tableau de bord</NavLink>
            <NavLink to="/dossiers">Dossiers</NavLink>
            <NavLink to="/capacite">Capacité</NavLink>
            <NavLink to="/facturation">Facturation</NavLink>
            <NavLink to="/parametres">Paramètres</NavLink>
            {admin && <NavLink to="/journal">Journal</NavLink>}
          </nav>
          <div className="side-foot">
            <span>{session.user.nom}<br /><span className="muted">{session.user.email}</span></span>
            <button className="btn ghost small" style={{ alignSelf: "flex-start", paddingInline: 0 }} onClick={deconnexion}>Se déconnecter</button>
          </div>
        </aside>
        <main>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/dossiers" element={<Dossiers />} />
            <Route path="/dossiers/:id" element={<Dossier session={session} />} />
            <Route path="/capacite" element={<Capacite cabinet={session.cabinet} />} />
            <Route path="/facturation" element={<Facturation />} />
            <Route path="/parametres" element={<Parametres session={session} onChange={charger} />} />
            {admin && <Route path="/journal" element={<Journal />} />}
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
      <Toast msg={msg} />
    </ToastCtx.Provider>
  );
}

createRoot(document.getElementById("root")).render(<StrictMode><BrowserRouter><App /></BrowserRouter></StrictMode>);
