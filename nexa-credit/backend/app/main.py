from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .db import Base, engine
from .routers import auth, cabinet, documents, dossiers, outils

Base.metadata.create_all(engine)

app = FastAPI(title="NEXA CREDIT", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")


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
    if request.url.path.startswith("/api/"):
        resp.headers.setdefault("Cache-Control", "no-store")
    return resp


for r in (auth, cabinet, dossiers, documents, outils):
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
