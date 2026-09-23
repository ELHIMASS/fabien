import { createContext, useContext, useEffect, useId, useState } from "react";

export const ToastCtx = createContext(() => {});
export const useToast = () => useContext(ToastCtx);

export function Toast({ msg }) {
  if (!msg) return null;
  return <div className={`toast ${msg.err ? "err" : ""}`} role="status">{msg.text}</div>;
}

/** Champ enregistré à la sortie du champ (blur) ou sur Entrée. */
export function Field({ label, value, onSave, type = "text", suffix, step, placeholder, disabled }) {
  const id = useId();
  const [v, setV] = useState(value ?? "");
  useEffect(() => setV(value ?? ""), [value]);
  const commit = () => {
    const cur = value ?? "";
    if (String(v) === String(cur)) return;
    if (type === "number") onSave(v === "" ? null : Number(v));
    else if (type === "date") onSave(v || null);
    else onSave(v);
  };
  return (
    <div className="f">
      <label htmlFor={id}>{label}{suffix && <span className="muted"> ({suffix})</span>}</label>
      <input id={id} type={type} step={step || (type === "number" ? "any" : undefined)} value={v} placeholder={placeholder}
        disabled={disabled} onChange={e => setV(e.target.value)} onBlur={commit}
        onKeyDown={e => e.key === "Enter" && e.currentTarget.blur()} />
    </div>
  );
}

export function Select({ label, value, onSave, options }) {
  const id = useId();
  return (
    <div className="f">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value ?? ""} onChange={e => onSave(e.target.value)}>
        {options.map(o => Array.isArray(o) ? <option key={o[0]} value={o[0]}>{o[1]}</option> : <option key={o}>{o}</option>)}
      </select>
    </div>
  );
}

export function Check({ label, value, onSave }) {
  const id = useId();
  return (
    <div className="f check">
      <input id={id} type="checkbox" checked={!!value} onChange={e => onSave(e.target.checked)} />
      <label htmlFor={id}>{label}</label>
    </div>
  );
}

export function TextArea({ label, value, onSave, rows = 4 }) {
  const id = useId();
  const [v, setV] = useState(value ?? "");
  useEffect(() => setV(value ?? ""), [value]);
  return (
    <div className="f">
      {label && <label htmlFor={id}>{label}</label>}
      <textarea id={id} rows={rows} value={v} onChange={e => setV(e.target.value)} onBlur={() => v !== (value ?? "") && onSave(v)} />
    </div>
  );
}

export const Line = ({ k, v, total }) => (
  <div className={`line ${total ? "total" : ""}`}><span className="k">{k}</span><span className="num">{v}</span></div>
);

/** Bouton de suppression avec confirmation intégrée (les dialogues natifs sont évités). */
export function ConfirmButton({ label = "Supprimer", confirm = "Confirmer", onConfirm, className = "btn ghost small" }) {
  const [ask, setAsk] = useState(false);
  if (!ask) return <button className={className} onClick={() => setAsk(true)}>{label}</button>;
  return (
    <span className="row">
      <button className="btn small" onClick={() => setAsk(false)}>Annuler</button>
      <button className="btn small danger" onClick={() => { setAsk(false); onConfirm(); }}>{confirm}</button>
    </span>
  );
}

export async function copier(texte, toast) {
  try { await navigator.clipboard.writeText(texte); toast("Copié dans le presse-papiers"); }
  catch { toast("Copie refusée par le navigateur : sélectionnez le texte", true); }
}
