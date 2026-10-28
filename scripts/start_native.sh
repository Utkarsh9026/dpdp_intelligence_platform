#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ -f .env ]] || { echo 'Run ./scripts/setup_native.sh first'; exit 1; }
set -a; source .env; set +a
# Relative SQLite URL is evaluated from backend working directory.
cd backend
exec .venv/bin/uvicorn main:app --host 127.0.0.1 --port "${API_PORT:-8000}"
