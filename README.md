# Verity DPDP by Elevatics AI - React + FastAPI (native deployment, NO DOCKER)

Commercial SaaS foundation for DPDP company assessment. This version uses **React + Vite**, **Python FastAPI**, and **SQLite for local development / PostgreSQL for production**. Docker is not required or included. It is **not yet security-approved for production client data**.

## Local installation (Ubuntu 22.04/24.04; macOS with Python 3.12+ and Node 22+)

```bash
unzip dpdp_enterprise_react_native_v0.3.zip
cd dpdp_enterprise
./scripts/setup_native.sh
./scripts/start_native.sh
```

In another terminal:

```bash
cd dpdp_enterprise
./scripts/start_frontend_dev.sh
```

Open **http://localhost:5173**. The Vite development proxy forwards `/api` to **http://127.0.0.1:8000**. To run the backend on a different port, update `frontend/vite.config.js` accordingly. The API uses `/api/health` and `/docs` locally.

The bootstrap generates `.env` with a strong JWT secret and local SQLite settings; `.env` is ignored by Git. The SQLite database is stored as `backend/dpdp.db`. Start scripts are for development only.

## Native Linux server deployment (no containers)

1. Install Node 22+, Python 3.12+, PostgreSQL 16+, Nginx, and TLS certificates on Ubuntu. Create dedicated unprivileged service user `verity`.
2. Place application at `/opt/verity-dpdp`; install Python requirements into `backend/.venv` and run `npm ci && npm run build` from `frontend/`.
3. Create a PostgreSQL database and a least-privileged database account. Use `.env.native.example` as the basis for `/opt/verity-dpdp/.env` with `DATABASE_URL=postgresql+psycopg://...` and long random `JWT_SECRET`. Set `.env` permissions to 600, owned by the service user. Set `CORS_ORIGINS` to the HTTPS frontend origin.
4. Configure your Nginx site using `deploy/nginx-site.conf` (update domain, certificate paths, application root); copy `deploy/verity-api.service` to `/etc/systemd/system/`.
5. Run `sudo systemctl daemon-reload && sudo systemctl enable --now verity-api`, then validate `curl http://127.0.0.1:8000/api/health`, test HTTPS, and check the Nginx configuration before public access.
6. Configure encrypted PostgreSQL backups and restore tests, secure evidence-file storage, monitoring, a WAF/rate limits, and a vulnerability assessment.

**Caution:** Startup currently calls SQLAlchemy `create_all()`; replace with explicit, reviewed Alembic migrations before operating on production data. The provided reverse-proxy and service files are deployment templates, not hardened/verified infrastructure-as-code.

## Features

- React Apple-inspired client-facing portal, dashboards, 260 provisional DPDP control questions across 16 domains
- Organisation onboarding, tenant-specific API access, password authentication, data systems inventory
- Passive public website scan for links, forms, third parties, cookies set before consent and observable security indicators. Pages are rendered in headless Chromium (Playwright) so JavaScript/React sites are inspected; install it once with `backend/.venv/bin/python -m playwright install chromium` (done by `setup_native.sh`; on Linux servers also run `python -m playwright install-deps chromium` as root). Without a browser the scanner falls back to static HTML and reports JavaScript-built sites as incomplete. Tunables: `SCAN_MODE`, `SCAN_MAX_PAGES`, `SCAN_TIME_BUDGET`, `SCAN_BROWSER_SLOTS`.
- The scan is evaluated against the 76-point DPDP website checklist (`backend/checklist.json`, generated from the Excel workbook with `python scripts/build_checklist_json.py`). The rule engine in `backend/assess.py` re-runs on every request, so scoping answers (S1 to S45) and owner declarations update results instantly without re-crawling. Statuses are Met, Not met, Needs review, Needs your input, Not testable externally, Self-declared (unverified) and Not applicable. The result is a findings list, not a compliance score. Scans are limited to the organisation's registered domain unless `SCAN_ANY_HOST=true`.
- **Reports & exports** shows a detailed website scan report built from the latest scan (or any earlier one): cover with the observed-checks-met ring, penalty exposure tier, status and risk breakdowns, a written summary, a scorecard per section, findings grouped as critical gaps, other gaps, needs review, open, met and not applicable (each with evidence and a "how to fix" box), recommended next steps and scope notes. **Download PDF** calls `GET /api/orgs/{org}/scans/{scan}/report.pdf`, which renders the print-only route `/report/{org}/{scan}/print` (`frontend/src/ReportDoc.jsx`, `reportPrint.css`) in headless Chromium: A4, cover, executive summary, section scorecard, full cards for gaps and reviews, compact tables for open and met checks, an appendix, a branded footer with page numbers and a report ID plus SHA-256 fingerprint. It needs the same Chromium install as the scanner and uses `PUBLIC_APP_URL` (default: first `CORS_ORIGINS` entry) to reach the frontend. **Print** uses the same layout through the browser (turn off "Headers and footers" in the print dialog); it can also be exported to CSV. The fix text for each check lives in `backend/remediation.py`.
- **Public website score (no login).** Logged-out visitors see a landing page, then company details, then a website address, and get only the headline result: the "checks met" ring, "X of Y checks the scan could settle are met" and the Gaps / To review / Open / Met counts. Findings, evidence, fixes, the scoping questions, declarations and the report need an account; "Log in to see details" opens signup, and the company details and address prefill the workspace form. The scan is repeated inside the account (the public result is not stored). Backend: `POST /api/public/scan` (`frontend/src/PublicCheck.jsx`). It is limited per visitor IP (a salted hash is kept in `audit_events`) by `PUBLIC_SCANS_PER_HOUR` (default 3; `0` turns the limit off, handy for local testing) and runs at most `PUBLIC_SCAN_SLOTS` scans at once per API worker (default 2).
- Evidence uploads, audit answers, declarations, CSV report export and AI-assisted analysis via OpenRouter, Gemini, Claude or local Ollama

## Open production gaps

Formal DPDP legal-clause review and ongoing updates, domain ownership verification, SSO/MFA and hardened sessions, strict auditor role workflows, rate limits, evidence encryption/malware scanning, immutable signatures, full declaration snapshots, independent security assessment, SaaS billing, audit logs retention, database migrations, backup restore drills and end-to-end UI tests. Never claim a questionnaire alone certifies full compliance.

## Sources

- https://www.indiacode.nic.in/bitstream/123456789/22037/1/a2023-22.pdf
- https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa?pageTitle=Digital-Personal-Data-Protection-Rules-2025%3B
