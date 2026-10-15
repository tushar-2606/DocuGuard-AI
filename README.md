# DocuGuard AI

Document intelligence workspace: upload PDFs, extract actionable tasks and deadlines with **local rule-based analysis** (not an LLM), review results, and manage tasks in a dashboard.

## Stack

- **Frontend:** React 19, Vite, CSS (`frontend/`)
- **Backend:** FastAPI, SQLAlchemy, PyMuPDF, dateparser (`backend/`)
- **Database:** SQLite by default; set `DATABASE_URL` for PostgreSQL

## Windows — run locally (PowerShell)

```powershell
cd C:\Users\tusha\DocuGuard-AI

# One-time setup
py -m pip install -r backend\requirements.txt
cd frontend
npm install
cd ..

# Configure secrets (do not commit .env)
Copy-Item backend\.env.example backend\.env
# Edit backend\.env and set JWT_SECRET_KEY to a long random value
```

Start both servers:

```powershell
# Option A — helper script (opens two console windows)
.\run-dev.bat

# Option B — manual
cd backend
py -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd C:\Users\tusha\DocuGuard-AI\frontend
npm run dev -- --host 127.0.0.1
```

- App: http://127.0.0.1:5173
- API health: http://127.0.0.1:8000/health
- API docs: http://127.0.0.1:8000/docs

Vite proxies `/api` to the backend on port 8000.

## Environment variables

See `backend/.env.example`. Important keys:

| Variable | Purpose |
|----------|---------|
| `JWT_SECRET_KEY` | Required strong secret in production |
| `DATABASE_URL` | `sqlite:///./docuguard.db` or Postgres URL |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `ENVIRONMENT` | `development` or `production` |
| `APP_TIMEZONE` | IANA timezone used for new reminder preferences (default `UTC`) |
| `DEFAULT_DATE_ONLY_REMINDER_TIME` | Local time for deadlines without an explicit time (default `09:00`) |
| `REMINDER_CHECK_INTERVAL_SECONDS` | Scheduler polling interval; minimum 15 seconds (default `60`) |
| `ENABLE_REMINDER_SCHEDULER` | Enable the in-process scheduler (default `true`) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM` | Optional SMTP server and sender for email reminders |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Optional SMTP credentials; configure both or neither |
| `SMTP_USE_TLS`, `SMTP_USE_SSL` | SMTP transport security; do not enable both |

Existing local `backend/.env` files are never overwritten by setup docs.

## Tests

```powershell
cd C:\Users\tusha\DocuGuard-AI\backend
py -m pytest -q
```

Frontend:

```powershell
cd C:\Users\tusha\DocuGuard-AI\frontend
npm run lint
npm run build
```

## Security notes

- Passwords are hashed with bcrypt.
- Private APIs require JWT Bearer tokens; resources are scoped by `user_id`.
- Uploads validate PDF magic bytes, size, and page counts server-side.
- CORS is origin-restricted via `CORS_ORIGINS`.
- Auth and upload endpoints are rate-limited (in-memory; suitable for single-process deploys).
- Production rejects insecure default JWT secrets.

## Extraction honesty

Analysis is **rule-based**. Confidence scores are heuristics for review prioritization, not calibrated probabilities. See `docs/EXTRACTION.md`.

## Limits (current build)

- PDF text extraction only — scanned PDFs need OCR (not enabled).
- No paid LLM / OpenAI dependency in application code.
- JWT logout is client-side (tokens are not server-revoked).
- In-memory rate limits do not share state across multiple workers.
- Reminder delivery is scheduled by the running backend; downtime can delay delivery.
- Desktop alerts require explicit browser permission and are delivered only while the app is open; closed-browser delivery needs a separately configured Web Push service.
- Email delivery requires valid SMTP settings and per-user opt-in.

## Documentation

- `docs/IMPLEMENTATION_PLAN.md` — upgrade plan and status
- `docs/EXTRACTION.md` — extraction behavior and limitations
- `docs/REMINDERS.md` — reminder scheduling, settings, delivery, and operational limits
