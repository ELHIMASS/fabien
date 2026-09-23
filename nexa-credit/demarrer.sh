#!/usr/bin/env bash
# Installe et lance NEXA CREDIT en local : http://127.0.0.1:8000
set -euo pipefail
cd "$(dirname "$0")"
( cd frontend && npm install --no-audit --no-fund && npm run build )
cd backend
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
[ "${1:-}" = "--demo" ] && .venv/bin/python -m app.demo
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
