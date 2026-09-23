from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import inspect, text

from .db import Base, engine
from .routers import auth, cabinet, documents, dossiers, espace, outils

Base.metadata.create_all(engine)

# Mise à niveau légère des bases existantes (v0.1 → v0.2) : colonnes ajoutées depuis.
# À remplacer par Alembic avant la production.
_AJOUTS = {"documents": {"source": "VARCHAR(10) DEFAULT 'cabinet' NOT NULL"}}
with engine.begin() as _c:
    for _table, _cols in _AJOUTS.items():
        _existantes = {c["name"] for c in inspect(_c).get_columns(_table)}
        for _col, _ddl in _cols.items():
            if _col not in _existantes:
                _c.execute(text(f"ALTER TABLE {_table} ADD COLUMN {_col} {_ddl}"))

from .config import DOCS_API

app = FastAPI(title="NEXA CREDIT", version="0.2.0",
              docs_url="/api/docs" if DOCS_API else None, openapi_url="/api/openapi.json" if DOCS_API else None,
              redoc_url=None)


@app.middleware("http")
async def securite(request: Request, call_next):
    # Protection CSRF complémentaire du cookie SameSite=Strict : toute requête
    # modifiante doit porter un en-tête que seul notre front sait ajouter.
    if request.method in ("POST", "PATCH", "PUT", "DELETE") and request.url.path.startswith("/api/"):
        if request.headers.get("x-nexa") != "1":
            return JSONResponse({"detail": "Requête refusée (en-tête manquant)."}, status_code=403)
    resp = await call_next(request)
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        resp.headers["Strict-Transport-Security"] = "max-age=31536000"
    if request.url.path.startswith("/api/"):
        resp.headers.setdefault("Cache-Control", "no-store")
    return resp


for r in (auth, cabinet, dossiers, documents, espace, outils):
    app.include_router(r.router)


@app.get("/api/sante")
def sante():
    return {"ok": True}


# Front React compilé (npm run build) servi par le même serveur.
DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "Introuvable"}, status_code=404)
        f = DIST / path
        if path and f.is_file() and DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
