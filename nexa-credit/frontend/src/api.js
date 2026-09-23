// Client HTTP : cookie de session httpOnly + en-tête anti-CSRF exigé par le serveur.
export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

async function request(method, url, body, isForm = false) {
  const opts = { method, credentials: "same-origin", headers: { "x-nexa": "1" } };
  if (body !== undefined) {
    if (isForm) opts.body = body;
    else { opts.headers["content-type"] = "application/json"; opts.body = JSON.stringify(body); }
  }
  const r = await fetch(url, opts);
  if (r.status === 401 && !url.startsWith("/api/auth/")) {
    window.dispatchEvent(new Event("nexa:deconnecte"));
  }
  if (!r.ok) {
    let msg = `Erreur ${r.status}`;
    try {
      const j = await r.json();
      if (typeof j.detail === "string") msg = j.detail;
      else if (Array.isArray(j.detail)) msg = j.detail.map(d => `${(d.loc || []).slice(-1)[0]} : ${d.msg}`).join(" · ");
    } catch { /* réponse non JSON */ }
    throw new ApiError(r.status, msg);
  }
  const ct = r.headers.get("content-type") || "";
  return ct.includes("application/json") ? r.json() : r;
}

export const api = {
  get: url => request("GET", url),
  post: (url, body) => request("POST", url, body ?? {}),
  patch: (url, body) => request("PATCH", url, body),
  del: url => request("DELETE", url),
  upload: (url, form) => request("POST", url, form, true),
};
