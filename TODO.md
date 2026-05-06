# TODO — Production Readiness Checklist

Last updated: May 2026. Check off items as they are completed.

---

## 🔴 Auth & Security (blocking for production)

- [ ] **Set `GOOGLE_CLIENT_SECRET`** — currently missing from `backend/.env`. Get from Google Cloud Console → APIs & Services → Credentials → your OAuth 2.0 Web client. Without this the token exchange in `blueprints/auth.py` will fail with a 400 from Google.
- [ ] **Set `LEADERBOARD_JWT_SECRET`** — currently a placeholder. Generate with `openssl rand -hex 32` and add to `backend/.env`. Used to sign session JWTs after OAuth.
- [ ] **Set `FLASK_SECRET_KEY`** — currently unset (Flask uses a weak default). Required for session security. Add to `backend/.env`.
- [ ] **Set `LEADERBOARD_ADMIN_API_KEYS`** — without this, `POST /api/leaderboard/seed` returns 503. Set to a strong random string in `backend/.env`. See `shared.py` → `require_admin`.
- [ ] **Register Google OAuth redirect URIs** — add both `http://localhost:5001/public/auth/google/callback` AND `http://127.0.0.1:5001/public/auth/google/callback` in Google Cloud Console → Authorized redirect URIs (for local dev), plus the production URL when deployed.
- [ ] **Set `ALLOWED_ORIGINS` for production** — currently defaults to localhost origins. Must be set to `https://your-frontend-domain.com` before deploying. See `shared.py` CORS setup.
- [ ] **Verify write routes all enforce auth** — `POST /public/submit_model`, `POST /public/add_dataset`, `POST /api/leaderboard/add_dataset`, `POST /api/leaderboard/add_model` should all require `X-API-Key` or Bearer JWT when `LEADERBOARD_API_KEYS` is set. Audit `require_api_key` decorator usage in blueprints.

---

## 🔴 Data & Persistence (blocking for production)

- [x] **`frontend/.env.development` points at wrong port** — fixed to `REACT_APP_API_BASE=http://127.0.0.1:5001`. File: `frontend/.env.development`.
- [x] **`docker-compose.yml` uses MySQL but SQLite is now default** — fixed by removing MySQL and mounting `leaderboard_data` at `/data` with `SQLITE_DB_PATH=/data/leaderboard.db`. File: `docker-compose.yml`.
- [x] **SQLite DB is gitignored** — `leaderboard.db` is in `.gitignore`, correct.
- [x] **Auto-seed on empty DB** — verified working; `before_request` hook in `app.py` seeds 25 entries on first request.
- [ ] **`_STORE` (RAM) still used as fallback** — submissions and evaluations that fail the DB write fall into `_STORE["submissions"]` / `_STORE["evaluations"]` and are lost on restart. Long-term: ensure all writes succeed to SQLite. File: `shared.py`.

---

## 🟡 Submission Pipeline (end-to-end Kaggle flow)

- [ ] **Test full flow manually** — browse leaderboard → click dataset → download questions via `GET /public/dataset_questions?dataset=<name>` → run a model → `POST /public/submit_model` with predictions → verify score appears on leaderboard. This has never been tested end-to-end.
- [ ] **`GET /public/dataset_questions` only works for datasets with `reference_data`** — the 10 auto-seeded demo datasets do NOT have `reference_data.ground_truth` set (they are curated score-only entries). The questions endpoint will return empty for them. Need to import a real HF dataset first to get a dataset with actual questions + hidden labels. File: `blueprints/leaderboard.py`.
- [ ] **Submission format block in SubmitToLeaderboard.js** — the collapsible format block calls `GET /public/submission_format?dataset=<name>`. Verify it renders correctly for each task type (text_classification, NER, QA, retrieval, translation). File: `frontend/src/landing_page/landing_page_components/SubmitToLeaderboard.js`.
- [ ] **Daily quota display** — `POST /public/submit_model` returns `X-Submissions-Remaining` header but `MySubmissions.js` doesn't show the user how many submissions they have left today. Add a "X of 5 daily submissions used" indicator. File: `frontend/src/landing_page/landing_page_components/MySubmissions.js`.
- [ ] **`eval_core/leaderboard_bridge.py` uses placeholder results for submission format** — lines 217–242 return `<predicted_label>` / `ENTITY_ONE; ENTITY_TWO` etc. as example predictions. This is intentional for the format endpoint but should be clearly documented so it isn't confused with a real evaluation. File: `backend/eval_core/leaderboard_bridge.py:217`.

---

## 🟡 HF Import & Model Runner

- [ ] **Test `/create-leaderboard` wizard end-to-end** — open `http://localhost:3000/create-leaderboard`, import `nyu-mll/glue` config `sst2` split `validation`, verify a new leaderboard card appears. This requires `pip install datasets` in the backend venv.
- [ ] **`POST /public/run_hf_model` requires `transformers` + `torch`** — verify it returns a clean 422 with install instructions when those packages are missing (not a 500). File: `blueprints/eval.py`.
- [ ] **HF import error handling in UI** — the wizard (`CreateLeaderboardFromHF.js`) should show a user-friendly error message for: private dataset (403), wrong split name, config required but not provided. Verify the error states render.
- [ ] **`TRUSTED_REMOTE_CODE_MODELS` env var** — documents that HF models requiring `trust_remote_code=True` must be explicitly allowlisted. Make sure this is enforced in the `run_hf_model` route. File: `blueprints/eval.py`, `backend/.env.example`.

---

## 🟡 Frontend Polish

- [ ] **Demo chip renders correctly** — when API is down or empty, each leaderboard card should show a grey "Demo" badge. Start the frontend with the backend stopped and verify the banner + chips appear. File: `Leaderboard.js`.
- [ ] **`TaskAdvancedMetricsPanel` — verify grouped layout** — open a dataset card, click "Advanced metrics", confirm categories (Core / Precision-Recall / Semantic overlap / Ranking / Translation) are grouped with collapse/expand. Metrics with no model scores should show "—" not blank.
- [ ] **`DatasetDetails.js` — verify Details page works for all 10 demo datasets** — click "Details" on each leaderboard card. Should not 404. Backed by `ui_fallback_dataset_catalog.py`.
- [ ] **`/create-leaderboard` link not exposed in nav** — the page exists at the route but there's no link to it from the header or leaderboard. Add a "➕ Create Leaderboard" button somewhere accessible (e.g. next to the leaderboard title or in the nav). File: `HeaderBar.js` or `Leaderboard.js`.
- [ ] **Remove unused state variables in `SubmitToLeaderboard.js`** — there are ~20 `useState` declarations for features that were never wired up (pre-existing lint warnings). Clean up to reduce confusion. File: `frontend/src/landing_page/landing_page_components/SubmitToLeaderboard.js`.

---

## 🟡 Deployment

- [x] **Update `docker-compose.yml`** for SQLite — removed MySQL service/dependency and added the `leaderboard_data` volume.
- [x] **Validate `backend/Dockerfile`** — Dockerfile now uses `WORKDIR /app`, `COPY . .`, `RUN pip install --no-cache-dir -r requirements.txt`, and `CMD ["python", "app.py"]`.
- [x] **No Railway / Render config file** — added `railway.json` using the backend Dockerfile, `python app.py`, and `/health`.
- [ ] **Frontend build must be served** — decide: serve the React build from Flask (add `send_from_directory` for `frontend/build/`) OR deploy frontend separately to Vercel/Netlify and set `ALLOWED_ORIGINS` accordingly.
- [ ] **Production env vars checklist** — before deploying, all of these must be set:
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `LEADERBOARD_JWT_SECRET`
  - `FLASK_SECRET_KEY`
  - `LEADERBOARD_ADMIN_API_KEYS`
  - `LEADERBOARD_API_KEYS`
  - `ALLOWED_ORIGINS`
  - `LEADERBOARD_FRONTEND_URL`
  - `LEADERBOARD_OAUTH_PUBLIC_BASE_URL`
  - `DISABLE_AUTO_SEED=1` (use the seed route manually instead)

---

## 🟢 Tests & CI

- [ ] **No test coverage for auth flow** — `blueprints/auth.py` (Google OAuth start + callback) has zero tests. Add tests mocking `authlib` OAuth exchange.
- [ ] **No test coverage for HF runner** — `POST /public/run_hf_model` has no test in `tests/`. Add a test mocking `transformers.pipeline`.
- [ ] **`pytest/` folder vs `tests/` folder** — CI runs `tests/` only. The older `pytest/` integration tests require a live server and are not in CI. Either move useful coverage into `tests/` or delete `pytest/`.
- [ ] **No frontend tests** — zero React Testing Library or Cypress tests exist. At minimum add smoke tests for `Leaderboard.js` render and the submission form.
- [ ] **Routes with zero test coverage** — `GET /public/export/leaderboard`, `GET /public/benchmark_models`, `POST /public/run_csv_benchmarks`, `POST /api/leaderboard/add_model`, `GET /api/leaderboard/list`. Add at least a status-200 test for each.

---

## 🟢 Code Quality

- [ ] **`app.py` is still 248 lines** — target was ~80. The auto-seed hook, compatibility exports, and some helpers could move to `shared.py`. Non-blocking but worth cleaning up.
- [ ] **`shared.py` is 428 lines** — contains route-level logic that belongs in blueprints. Audit and move anything that's not pure shared state/helpers.
- [ ] **`blueprints/leaderboard.py` is 1059 lines** — still the heaviest file. Could be split into `leaderboard_read.py` (GET routes) and `leaderboard_write.py` (POST/admin routes) if it grows further.
- [ ] **Ruff linting** — run `ruff check backend/` from repo root and fix any errors. `pyproject.toml` is configured. CI should fail on ruff errors but currently does not enforce it.

---

## ✅ Completed (for reference)

- [x] SQLite persistence — data survives server restarts without MySQL
- [x] Composite 0–100 scoring — `composite_score.py`
- [x] Per-task advanced metrics glossary — `metrics_info_full.py` + `TaskAdvancedMetricsPanel.js`
- [x] Top-3 ranks + "Show more" on leaderboard cards
- [x] Dataset Details page no longer 404s — `ui_fallback_dataset_catalog.py`
- [x] Auto-seed on empty DB — `before_request` hook in `app.py`
- [x] `GET /public/dataset_questions` — returns unlabeled inputs for submission pipeline
- [x] Daily submission quota — `DAILY_SUBMISSION_LIMIT` env var + `X-Submissions-Remaining` header
- [x] `POST /public/run_hf_model` — sync/async HF model evaluation route
- [x] `/create-leaderboard` wizard UI page
- [x] Demo chip + API failure banner in `Leaderboard.js`
- [x] Blueprint refactor — `app.py` is thin; routes split across 6 blueprint files
- [x] `eval_core` lazy imports — no more numpy segfault on macOS
- [x] `AGENTS.md` — comprehensive agent onboarding document
