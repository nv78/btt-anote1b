# AGENTS.md — Anote Model Leaderboard

This file is the **primary onboarding document for AI coding agents** (Codex, Claude, Cursor, etc.).
Read this before touching any file. See CLAUDE.md for legacy notes.

---

## What we are building

**Anote Model Leaderboard** is a benchmarking platform where anyone can:
1. Browse ranked AI model performance across curated datasets.
2. Submit their own model's predictions to get evaluated and ranked automatically.
3. See **transparent, reproducible scores** with full metric breakdowns — not just a single number.

It lives at: `https://leaderboard.anote.ai` (frontend) + `https://api.anote.ai` (backend).

The active development branch is **`jeremy`** on `https://github.com/anote-ai/Leaderboard.git`.

---

## Repository layout

```
Leaderboard/
├── backend/                    # Flask (Python) REST API
│   ├── app.py                  # Flask app factory, CORS, core routes/OpenAPI, blueprint registration (~248 lines)
│   ├── shared.py               # Shared state/helpers imported by blueprints (~428 lines)
│   ├── blueprints/
│   │   ├── __init__.py
│   │   ├── leaderboard.py      # Dataset, leaderboard, export, curated seed/list routes (~1060 lines)
│   │   ├── submissions.py      # Submit, my submissions, submission detail, eval jobs routes (~622 lines)
│   │   ├── eval.py             # HF import/model runner, CSV benchmark routes (~508 lines)
│   │   ├── auth.py             # Google OAuth start/callback routes (~62 lines)
│   │   ├── admin.py            # Admin submissions moderation route (~219 lines)
│   │   └── metrics.py          # Metrics catalog routes (~23 lines)
│   ├── auth_helpers.py         # JWT decode helpers (HS256 + optional JWKS)
│   ├── composite_score.py      # Aggregate 0-100 score from detailed_scores
│   ├── csv_bench.py            # CSV benchmark: task inference, scoring
│   ├── hf_importer.py          # Hugging Face dataset import logic
│   ├── metrics_info.py         # Legacy metrics stub (for backward compat)
│   ├── metrics_info_full.py    # Full METRICS_CATALOG + per-task metric lists ← edit this for metric changes
│   ├── models.py               # LLM provider wrappers (OpenAI, Anthropic, Gemini, Ollama, echo)
│   ├── pagination.py           # Keyset cursor encode/decode
│   ├── ui_fallback_dataset_catalog.py  # Static metadata for demo leaderboard cards
│   ├── eval_core/
│   │   ├── evaluators.py       # TextClassification, NER, QA, Retrieval, Translation evaluators
│   │   ├── hf_dataset_recipes.py  # HF dataset → ground_truth conversion
│   │   └── leaderboard_bridge.py  # Bridges evaluators to submission format
│   ├── ingestion/              # Pluggable dataset ingestion (HF, HTTP)
│   ├── sdk/leaderboard_sdk.py  # Python client SDK (LeaderboardClient)
│   ├── database/               # SQL schemas + dev init script
│   ├── examples/               # Seed scripts + example JSON payloads
│   ├── scripts/                # Bulk import, OpenAPI export, model submission examples
│   ├── tests/                  # pytest suite (tests/ folder — run these for CI)
│   │   ├── conftest.py
│   │   ├── test_bearer_write_auth.py
│   │   ├── test_composite_score.py
│   │   ├── test_eval_core.py
│   │   ├── test_metrics_task_lists.py
│   │   ├── test_pagination_and_admin.py
│   │   └── test_submission_contract.py
│   ├── pytest/                 # Older integration tests (also runnable, but secondary)
│   ├── .env                    # Local secrets — GITIGNORED, never commit
│   ├── .env.example            # Template — keep this updated
│   └── requirements.txt
│
├── frontend/                   # Create React App (CRA) + Tailwind
│   ├── src/
│   │   ├── App.js              # Router + Google Analytics setup
│   │   ├── landing_page/
│   │   │   ├── LandingPage.js  # Route definitions — register new pages here
│   │   │   └── landing_page_components/
│   │   │       ├── Leaderboard.js          # Main leaderboard grid (hardcoded demo + live API)
│   │   │       ├── DatasetDetails.js       # /dataset/:name page
│   │   │       ├── TaskAdvancedMetricsPanel.js  # Reusable metrics glossary table
│   │   │       ├── SubmitToLeaderboard.js  # Submission form
│   │   │       ├── MySubmissions.js        # User's past submissions
│   │   │       ├── AdminLeaderboardManager.js  # Admin: curated datasets
│   │   │       ├── AdminSubmissionsModeration.js  # Admin: review submissions
│   │   │       ├── LoginPage.js            # Google OAuth start
│   │   │       ├── OAuthCallback.js        # Handles #access_token fragment post-OAuth
│   │   │       ├── AuthGuard.js            # Redirects unauthenticated users
│   │   │       ├── CsvBenchmarksDemo.js    # Run CSV benchmarks against live LLMs
│   │   │       └── ...
│   │   ├── utils/
│   │   │   ├── formatMetricsSummary.js     # Format detailed_scores into compact string
│   │   │   └── leaderboardAuth.js          # Token retrieval helpers
│   │   └── constants/RouteConstants.js     # All SPA route paths
│   ├── public/benchmark_csvs/  # 60+ CSV benchmark files served statically
│   ├── .env.development        # REACT_APP_API_ENDPOINT=http://localhost:5000
│   └── .env.production         # REACT_APP_API_ENDPOINT=https://api.anote.ai
│
├── docs/                       # MkDocs documentation source
├── docker-compose.yml
├── AGENTS.md                   # ← this file
├── CLAUDE.md                   # Legacy agent notes (lower priority than AGENTS.md)
└── README.md
```

---

## Tech stack

| Layer | Choice |
|-------|--------|
| Backend | Python 3.11, Flask 2.3, Authlib, PyJWT, python-dotenv |
| Database | SQLite by default (`SQLITE_DB_PATH`), optional MySQL, in-memory `_STORE` fallback only if disk DB unavailable |
| Frontend | React 18, Create React App, Tailwind CSS |
| State | Redux Toolkit + Redux Persist (cross-component), Zustand (local) |
| Auth | Google OAuth 2.0 → HS256 JWT minted by Flask; or Bearer JWT via JWKS |
| Tests | pytest (`backend/tests/` is the primary suite; 31 tests, all must pass) |
| CI | `.github/workflows/ci.yml` — pytest + Ruff + frontend build |

---

## How to run locally

```bash
# 1. Backend
cd Leaderboard/backend
pip install -r requirements.txt
cp .env.example .env          # then fill in GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, LEADERBOARD_JWT_SECRET
python app.py                 # runs on :5001 by default

# 2. Frontend
cd Leaderboard/frontend
npm install
REACT_APP_API_ENDPOINT=http://localhost:5001 npm start   # runs on :3000

# 3. Tests (must all pass before commit)
cd Leaderboard/backend
PYTHONPATH=. pytest -q tests/
```

---

## All API routes (current)

```
GET  /                                  Info / welcome
GET  /health                            Health check
GET  /openapi.json                      OpenAPI spec
GET  /public/datasets                   List benchmark datasets
GET  /public/dataset_details            Dataset detail + metric docs (name= query param)
GET  /public/get_source_sentences       Translation sentences for evaluation
GET  /public/dataset_questions          Dataset inputs/questions without labels (dataset= query param)
POST /public/submit_model               Submit model predictions → evaluates → ranks
GET  /public/get_leaderboard            Ranked results (keyset pagination + dataset filter)
GET  /public/my_submissions             Caller's past submissions (JWT or submitter_id)
GET  /public/submission_quota           Daily quota usage for submitter_id or caller IP
GET  /public/submissions/<id>           Single submission detail
GET  /public/export/leaderboard         CSV or JSON dump of leaderboard
GET  /public/submission_format          Template for a dataset's submission format
POST /public/import_hf_dataset          Import a Hugging Face dataset split
POST /public/run_hf_model               Run a Hugging Face model on an imported dataset
POST /api/datasets/ingest               HF ingestion alias
GET  /public/benchmark_csvs             List available CSV benchmark files
GET  /public/benchmark_models           List available model providers
POST /public/run_csv_benchmarks         Run LLMs over CSV benchmarks inline
GET  /public/eval_jobs/<job_id>         Async eval job status
GET  /public/auth/google/start          Redirect to Google OAuth
GET  /public/auth/google/callback       OAuth callback → JWT → redirect to SPA
GET  /api/admin/submissions             Admin: list all submissions (X-Admin-Key)
GET  /api/metrics                       Full metric catalog
GET  /api/metrics/task/<task_type>      Per-task metric glossary + formulas
POST /api/leaderboard/add_dataset       Add curated dataset (API key required)
POST /api/leaderboard/add_model         Add model result to curated dataset
POST /api/leaderboard/seed              Admin: seed the 10 built-in benchmark datasets
GET  /api/leaderboard/list              List curated datasets
```

---

## Key modules explained

### `composite_score.py`
Computes a **0–100 aggregate score** across all reported metrics in `detailed_scores`.
- Normalizes each component to [0,1] (inverts lower-is-better metrics like `median_distance_error`, `ter`).
- Applies soft weights that slightly boost canonical metrics (accuracy, f1, bleu, exact_match).
- Called in `get_leaderboard` for every row — output fields are `composite_score` and `composite_breakdown`.

### `metrics_info_full.py`
Single source of truth for every evaluation metric.
- `METRICS_CATALOG` — dict of metric key → `{name, formula, description, range, when_to_use, limitations, interpretation}`.
- `get_metrics_for_task(task_type)` — returns ordered list of metric keys for each task. **Edit this when adding/removing metrics per task.**
- `normalize_task_type_for_metrics(task_type)` — alias mapping so `"ner"`, `"qa"`, `"rag"`, `"sum"`, etc. resolve to canonical keys.
- `metrics_for_task(task_type)` — used by `GET /api/metrics/task/<task_type>`.

### `eval_core/evaluators.py`
One evaluator class per task type:
- `TextClassificationEvaluator` — accuracy, macro/micro F1, precision, recall, balanced accuracy, Cohen's κ, MCC.
- `NEREvaluator` — strict + partial span F1/precision/recall.
- `QAEvaluator` — exact match, token F1, BLEU, ROUGE-1/L, METEOR, length ratio.
- `RetrievalEvaluator` — retrieval accuracy, MRR, MAP, nDCG, P@K, R@K.
- `TranslationEvaluator` — BLEU, BERTScore (optional), chrF/TER placeholder.

Each `evaluate(ground_truth, predictions)` returns a flat dict of `{metric_key: float}` — this becomes `evaluation_details.detailed_scores` in the DB.

### `ui_fallback_dataset_catalog.py`
Provides static metadata for the 10 demo cards hardcoded in the frontend `Leaderboard.js` fallback array.
When the live API returns no rows, Details navigation still works because `dataset_details` falls back to this catalog.
**If you add a new hardcoded demo dataset to `Leaderboard.js`, add a matching entry here.**

### Backend blueprints
`backend/app.py` creates the Flask app, configures CORS/OAuth, registers all blueprints, and re-exports shared globals for older tests/scripts. Route ownership is split across:
- `blueprints/leaderboard.py` — datasets, dataset details/questions, submission format, leaderboard, export, curated add/list/seed.
- `blueprints/submissions.py` — submit model, my submissions, submission detail, eval jobs.
- `blueprints/eval.py` — HF import/model runner, CSV benchmark listing/runs, source sentences, ingestion alias.
- `blueprints/auth.py` — Google OAuth start/callback.
- `blueprints/admin.py` — admin submission listing.
- `blueprints/metrics.py` — metric catalog and per-task metric glossary.

### `TaskAdvancedMetricsPanel.js`
Reusable React component:
- Calls `GET /api/metrics/task/<taskType>`.
- Renders grouped, collapsible metric categories with formula, range, and one score column per model.
- Used in `Leaderboard.js` (advanced toggle per card) and `DatasetDetails.js` (full glossary).
- Values are resolved via `lookupDetailedScore(detailedScores, catalogKey)` — tolerates case/`_` differences.

---

## Authentication model

| Who | How |
|-----|-----|
| **Read** (leaderboard, datasets, metrics) | No auth required |
| **Write** (submit model, add dataset) | `X-API-Key` header OR `Authorization: Bearer <jwt>` with non-empty `sub` claim |
| **Admin** (list/moderate submissions) | `X-Admin-Key` or `X-API-Key` matching `LEADERBOARD_ADMIN_API_KEYS` |
| **Google login** | `GET /public/auth/google/start` → Google → callback mints HS256 JWT → SPA stores in `sessionStorage` as `lb_jwt` |

JWT secret: `LEADERBOARD_JWT_SECRET` (env). Redirect URI is derived per-request from `request.url_root` to avoid `redirect_uri_mismatch` issues.

---

## Environment variables (complete)

All loaded from `backend/.env` (gitignored) or the monorepo root `Anote/.env` (gitignored). Both are auto-loaded by `app.py` via `python-dotenv`.

| Variable | Required | Purpose |
|----------|----------|---------|
| `GOOGLE_CLIENT_ID` | For OAuth | OAuth Web application client ID |
| `GOOGLE_CLIENT_SECRET` | For OAuth | OAuth secret — **TODO: add to .env** |
| `LEADERBOARD_JWT_SECRET` | For OAuth | HS256 signing key for post-login JWTs — **TODO: add to .env** |
| `LEADERBOARD_FRONTEND_URL` | For OAuth | SPA origin for post-login redirect (default `http://localhost:3000`) |
| `LEADERBOARD_OAUTH_PUBLIC_BASE_URL` | Prod only | Override when Flask sees internal URL behind TLS proxy |
| `LEADERBOARD_API_KEYS` | Optional | Comma-separated write keys; when set, enforces `X-API-Key` auth |
| `LEADERBOARD_ADMIN_API_KEYS` | Optional | Comma-separated admin keys (separate from write keys) |
| `REQUIRE_API_KEY` | Optional | `1`/`true` to enforce write auth even if `LEADERBOARD_API_KEYS` is empty |
| `FLASK_SECRET_KEY` | Recommended | Flask session secret |
| `FLASK_ENV` | Dev | Set to `production` for prod deployments |
| `ALLOWED_ORIGINS` | Prod required | Comma-separated CORS origins |
| `DB_HOST/USER/PASSWORD/NAME/PORT` | Optional | MySQL connection; SQLite is used when unset/unavailable |
| `SQLITE_DB_PATH` | Optional | SQLite file path for zero-config persistence; default `./leaderboard.db` |
| `OPENAI_API_KEY` | Optional | For OpenAI LLM evaluation in CSV benchmarks |
| `ANTHROPIC_API_KEY` | Optional | For Anthropic LLM evaluation |
| `GOOGLE_API_KEY` | Optional | For Gemini LLM evaluation |
| `PORT` | Optional | Flask port (default 5001) |

---

## Current state of the codebase (May 2026)

> See `TODO.md` for the full prioritized production-readiness checklist.

### What works
- **Leaderboard auto-seeds on first request** — 25 entries appear immediately; no manual seeding step
- **Live data + demo fallback** — "Demo" chip badge + API failure banner when API is empty/unreachable
- **Loading skeleton cards** + **Refresh button** in `Leaderboard.js`
- **SQLite persistence** — data survives restarts without MySQL (`SQLITE_DB_PATH=./leaderboard.db`)
- **Composite 0–100 scoring** from all reported metrics (`composite_score.py`)
- **Advanced metrics panel** — grouped/collapsible (Core, Precision/Recall, Semantic overlap, Ranking, Translation) with formula pills and range badges (`TaskAdvancedMetricsPanel.js`)
- **Show top 3 / Show more** per leaderboard card
- **Dataset Details page** never 404s for demo cards (`ui_fallback_dataset_catalog.py`)
- **All 5 evaluator classes** (TextClassification, NER, QA, Retrieval, Translation) in `eval_core/evaluators.py`
- **`GET /public/dataset_questions`** — returns unlabeled inputs for submission pipeline
- **Daily submission quota** via `DAILY_SUBMISSION_LIMIT` env var + `X-Submissions-Remaining` header
- **`POST /public/run_hf_model`** — sync/async HF model evaluation (requires `transformers`)
- **`/create-leaderboard` wizard** — import a HF dataset + optionally run a HF model
- **Blueprint structure** — routes split across 6 focused files; `app.py` ~250 lines
- **`eval_core` lazy imports** — no numpy segfault on macOS
- **Collapsible submission format block** in `SubmitToLeaderboard.js`
- **Full metric breakdown per submission** in `MySubmissions.js`
- **31 tests passing** in `backend/tests/`

### What is deferred / incomplete

See `TODO.md` for the full prioritized checklist. Top blockers:

- **Auth secrets missing** — `GOOGLE_CLIENT_SECRET`, `LEADERBOARD_JWT_SECRET`, `FLASK_SECRET_KEY`, `LEADERBOARD_ADMIN_API_KEYS` all unset in `backend/.env`
- **Manual browser submission flow still needs QA** — API-level e2e tests cover the runnable `SST-2 Sentiment (Sample)` dataset, but the full UI click path still needs manual verification
- **`_STORE` fallback remains volatile** — submissions/evaluations that cannot write to SQLite are kept in RAM and lost on restart

---

## Conventions agents must follow

### Always
1. **Run `PYTHONPATH=. pytest -q tests/` from `backend/` before finishing.** All 31 tests must pass.
2. **Run `npm run build` from `frontend/` before finishing.** Build must succeed (warnings OK, errors not).
3. Keep the **SQLite default and in-memory `_STORE` fallback working** — never assume MySQL is available.
4. Both `backend/tests/` and frontend build checks must stay green.

### Backend style
- Wrap optional imports in `try/except ImportError` with graceful degradation.
- All new functions need Python type annotations.
- New routes follow the existing pattern: register on the appropriate blueprint module and use `@rate_limit`, `@require_api_key` decorators as appropriate.
- New metrics go in `METRICS_CATALOG` in `metrics_info_full.py` with `name`, `formula`, `description`, `range`, `when_to_use`.
- New task types: add entry in `get_metrics_for_task()` AND alias in `normalize_task_type_for_metrics()` if needed.

### Frontend style
- Dark background is `bg-[#111827]` / `bg-[#0d1421]`. Accent yellow is `#defe47`. Accent blue is `#28b2fb`. Metric label gold is `#EDDC8F`.
- All API calls use `const API_BASE = process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || "http://localhost:5001"`.
- New page-level components live in `src/landing_page/landing_page_components/`.
- New routes: add path constant to `src/constants/RouteConstants.js`, then add `<Route>` in `LandingPage.js`.
- Avoid adding new npm dependencies without good reason — the bundle is already large.

### Git
- Active branch: **`jeremy`** on `origin` (`https://github.com/anote-ai/Leaderboard.git`).
- Always `git push origin jeremy` after committing — don't leave changes local.
- Commit message format: `type(scope): description` (e.g. `fix(oauth): ...`, `feat(metrics): ...`, `chore(env): ...`).

---

## Common tasks

### Add a new evaluation metric
1. Add entry to `METRICS_CATALOG` in `backend/metrics_info_full.py`.
2. Add the key to the relevant task list(s) in `get_metrics_for_task()`.
3. If the evaluator should compute it, add it to the appropriate class in `eval_core/evaluators.py`.
4. Add it to `composite_score.py`'s `_LOWER_IS_BETTER` if lower values are better.
5. Run tests.

### Add a new task type
1. Add evaluator class to `eval_core/evaluators.py` extending `BaseEvaluator`.
2. Register it in `eval_core/leaderboard_bridge.py` dispatch.
3. Add metric list in `get_metrics_for_task()` in `metrics_info_full.py`.
4. Add alias in `normalize_task_type_for_metrics()` if needed.
5. Add entry in `ui_fallback_dataset_catalog.py` if demo datasets use this task type.

### Add a new leaderboard demo card
1. Add the dataset object to the `datasets` array in `frontend/src/landing_page/landing_page_components/Leaderboard.js` with `task_type` and `evaluation_metric` fields.
2. Add a matching entry in `backend/ui_fallback_dataset_catalog.py` (key = lowercased name).

### Add a new API endpoint
1. Add the Flask route in the appropriate `backend/blueprints/` module.
2. Apply `@rate_limit` and `@require_api_key` / `@require_admin` as appropriate.
3. Add a test in `backend/tests/`.
4. Update the route table in this file (`AGENTS.md`) and `CLAUDE.md`.

### Fix a UI component
1. Components are in `frontend/src/landing_page/landing_page_components/`.
2. Check `src/constants/RouteConstants.js` for route path, `LandingPage.js` for rendering.
3. Run `npm run build` to verify — no new errors.

---

## Open issues / known bugs (as of May 2026)

> Full checklist with file locations is in `TODO.md`.

| Issue | Location | Priority |
|-------|----------|----------|
| Google OAuth broken — `GOOGLE_CLIENT_SECRET` missing | `backend/.env` | High |
| `LEADERBOARD_JWT_SECRET`, `FLASK_SECRET_KEY` are placeholders | `backend/.env` | High |
| `LEADERBOARD_ADMIN_API_KEYS` unset — seed route returns 503 | `backend/.env` | High |
| `frontend/.env.development` points to `:5005` not `:5001` | `frontend/.env.development` | High |
| Full UI submission flow needs manual QA | `SubmitToLeaderboard.js` + `MySubmissions.js` | Medium |
| `docker-compose.yml` uses MySQL; SQLite is now the default | `docker-compose.yml` | Medium |
| No frontend tests | — | Low |
| `SubmitToLeaderboard.js` has ~20 unused state variables | `frontend/…/SubmitToLeaderboard.js` | Low |
| Async eval job queue is stub only | `blueprints/submissions.py` + `blueprints/eval.py` | Low |
| `/create-leaderboard` link not exposed in nav | `HeaderBar.js` | Low |

---

## Do not touch (without understanding)

- `backend/pagination.py` — keyset cursor logic; tests cover it; changing break pagination.
- `backend/auth_helpers.py` — JWT decode for both HS256 and JWKS; fragile.
- `frontend/src/utils/leaderboardAuth.js` — token storage/retrieval used by AuthGuard and submit flow.
- `backend/eval_core/evaluators.py` — NER partial match logic is subtle; test before changing.
