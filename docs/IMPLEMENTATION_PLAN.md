# DocuGuard AI — Implementation Plan

**Date:** 2026-10-12  
**Branch:** `main` (up to date with `origin/main`)  
**Uncommitted user work preserved:** `frontend/src/App.css` (typography scale adjustments)

## Current architecture

```
DocuGuard-AI/
├── backend/app/
│   ├── main.py              FastAPI app, CORS, lifespan DB init
│   ├── config.py            Env-driven JWT + DATABASE_URL
│   ├── database.py          SQLAlchemy engine (SQLite default)
│   ├── models/              ORM + Pydantic schemas
│   ├── routers/             auth, documents, tasks, analytics
│   └── services/            auth (bcrypt+JWT), pdf (PyMuPDF), ai (rule-based NLP)
├── frontend/src/            React 19 + Vite SPA (no router)
│   ├── App.jsx              Shell, auth, upload, analysis UI
│   ├── components/          Dashboard, Documents, Tasks, Deadlines, Rules, modals
│   └── services/api.js      fetch + localStorage JWT
└── run-dev.bat              Windows dual-process launcher
```

**Stack facts (source of truth):**
- Extraction is **deterministic rule-based NLP** (regex + dateparser), not an LLM.
- Auth: bcrypt + HS256 JWT; ownership filters present on document/task/deadline/rule queries.
- Persistence: SQLAlchemy `create_all` on SQLite; no Alembic; PDFs not stored on disk.
- No automated tests or CI before this upgrade.
- Guest uploads analyze without persisting; logged-in uploads persist Document + Task/Rule/Deadline rows.

## Findings ranked by severity

### High
1. CORS `allow_origins=["*"]` with `allow_credentials=True`.
2. Default JWT secret used if env unset (forgable tokens in misconfigured deploys).
3. No rate limiting on auth or PDF upload (brute-force / CPU abuse).
4. Soft PDF validation (MIME/extension only before PyMuPDF); weak magic-byte gate.

### Medium
5. Extraction false positives: no negation/hypothetical/history filters; line-based only.
6. No task edit/delete/review workflow; toggle-only.
7. No schema migrations; additive fields risk runtime errors on existing DBs without upgrade path.
8. SQLite foreign keys not enabled via `PRAGMA foreign_keys=ON`.
9. Analytics load all rows into memory; no CSV export; no category/priority distribution.
10. Internal errors may leak traces in development-style defaults.
11. Password policy weak (min 6); search LIKE wildcards not escaped.

### Low
12. No CI, no backend/frontend tests.
13. README incomplete for env vars, security, limitations.
14. Auth modal `initialMode` sync edge case; dashboard silent error catch.
15. Unused `OPENAI_API_KEY` in local `.env` (not read by code; leave `.env` untouched).

## Implementation phases

| Phase | Focus | Status |
|-------|--------|--------|
| 0 | Audit + this plan | Done |
| 1 | Security & auth hardening | In progress |
| 2 | Extraction accuracy + evidence fields + corpus tests | Planned |
| 3 | DB schema upgrades (safe, non-destructive) + Postgres-ready URL | Planned |
| 4–5 | Document status, task edit/review/delete, filters | Planned |
| 6 | Analytics distributions + CSV export | Planned |
| 7 | UI polish preserving arctic/cyber identity + App.css edits | Planned |
| 8–10 | pytest, CI, README, `.env.example` | Planned |

## Files likely to change

- `backend/app/config.py`, `main.py`, `database.py`
- `backend/app/models/db_models.py`, `schemas.py`
- `backend/app/services/{auth,pdf,ai}_service.py` (+ new helpers)
- `backend/app/routers/{auth,documents,tasks,analytics}.py`
- `backend/requirements.txt`, `.env.example`
- `frontend/src/services/api.js`, selected components, `App.jsx` (minimal)
- `frontend/src/App.css` (preserve user typography; additive polish only)
- `docs/`, `README.md`, `.github/workflows/ci.yml`, `backend/tests/`

## Test and acceptance criteria

1. Register/login/me with ownership isolation (cross-user 404).
2. Upload rejects non-PDF, oversized, empty, corrupted bytes with 4xx.
3. Extraction skips negated/hypothetical lines; keeps clear deadlines; stores evidence.
4. Task edit/complete/delete persist across restart.
5. Dashboard stats match DB counts for the authenticated user.
6. CSV export sanitizes formula-injection prefixes.
7. `pytest` passes; `npm run build` succeeds; frontend lint clean where configured.
8. No secrets committed; `.env` never overwritten.

## Continuity notes

- Do **not** rewrite UI or replace visual identity.
- Do **not** introduce paid LLM APIs.
- Confidence scores remain **heuristic**, documented as such.
- Work proceeds in reversible batches; no commit/push without explicit permission.
