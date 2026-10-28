#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
command -v python3 >/dev/null || { echo 'Python 3 required'; exit 1; }
command -v npm >/dev/null || { echo 'Node.js/npm required'; exit 1; }
if [[ ! -f .env ]]; then
  python3 - <<'PY'
from pathlib import Path
import secrets
Path('.env').write_text('JWT_SECRET='+secrets.token_urlsafe(64)+'\nDATABASE_URL=sqlite:///./dpdp.db\nCORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173\nOLLAMA_BASE_URL=http://127.0.0.1:11434\n')
PY
  chmod 600 .env
fi
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
# Headless Chromium for the website scanner (renders JavaScript sites). If this fails the scanner
# falls back to static HTML analysis. On a Linux server also run (as root): backend/.venv/bin/python -m playwright install-deps chromium
backend/.venv/bin/python -m playwright install chromium || echo 'WARNING: Chromium not installed; website scans will use static mode'
(cd frontend && npm install && npm run build)
echo 'Setup complete. Start with ./scripts/start_native.sh'
