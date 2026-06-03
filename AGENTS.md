# AGENTS.md — Anote Model Leaderboard

This is the primary onboarding document for AI coding agents and new contributors working in this repository. Read this before touching code. `CLAUDE.md` is retained for legacy context, but this file is the source of truth.

## Project Summary

The **Anote Model Leaderboard** is a benchmarking platform for evaluating AI models on fixed datasets. Users can browse datasets, submit model predictions through the UI or backend API, get automatic scores, and compare ranked results with detailed metric breakdowns.

Repository: <https://github.com/anote-ai/Leaderboard>  
Current main branch: `main`  
Frontend target: `https://leaderboard.anote.ai`  
Backend target in the current deploy workflow: `https://api-leaderboard.anote.ai`

If the final production backend domain changes, update the deploy workflow, frontend environment variables, CORS settings, and OAuth redirect configuration together.

## Core Product Shape

This is a backend-backed product, not a static frontend.

- The frontend renders the leaderboard, dataset details, submission flow, My Submissions, OAuth callback, CSV benchmark demo, and admin views.
- The backend owns auth, dataset reads, submission validation, evaluation, async job polling, quotas, admin moderation, exports, provider-backed LLM runs, and persistence.
- Local development can use SQLite with no MySQL.
- Production should use a durable DB such as RDS/MySQL instead of instance-local SQLite.

## Repository Layout

```text
Leaderboard/
├── backend/                         Flask API
│   ├── app.py                       App setup, CORS, JSON errors, blueprint registration
│   ├── shared.py                    DB helpers, auth decorators, quotas, shared state
│   ├── auth_helpers.py              JWT/JWKS decode helpers
│   ├── composite_score.py           0-100 aggregate score from detailed_scores
│   ├── csv_bench.py                 CSV benchmark task inference/scoring
│   ├── hf_importer.py               Hugging Face dataset import logic
│   ├── metrics_info_full.py         Metric catalog and per-task metric lists
│   ├── models.py                    Provider wrappers for OpenAI/Anthropic/Gemini/Ollama/etc.
│   ├── pagination.py                Keyset cursor encode/decode
│   ├── ui_fallback_dataset_catalog.py
│   ├── blueprints/
│   │   ├── leaderboard.py           Datasets, details, questions, format, leaderboard, export
│   │   ├── submissions.py           Submit, async jobs, LLM runs, My Submissions, detail/delete
│   │   ├── eval.py                  HF import/model runner, CSV benchmark routes
│   │   ├── auth.py                  Google OAuth start/callback
│   │   ├── admin.py                 Admin moderation
│   │   ├── metrics.py               Metric catalog routes
│   │   └── dataset_requests.py      Dataset request workflow
│   ├── eval_core/
│   │   ├── evaluators.py            Task scoring implementations
│   │   ├── hf_dataset_recipes.py    HF dataset to ground-truth conversion
│   │   └── leaderboard_bridge.py    Submission format and evaluator bridge
│   ├── database/schema_leaderboard.sql
│   ├── sdk/leaderboard_sdk.py
│   ├── examples/
│   ├── scripts/
│   ├── tests/                       Primary pytest suite
│   ├── .env.example                 Keep env docs current
│   └── requirements.txt
├── frontend/                        React 18 Create React App
│   ├── src/App.js
│   ├── src/stores/store.js
│   ├── src/landing_page/LandingPage.js
│   ├── src/landing_page/landing_page_components/
│   │   ├── Leaderboard.js
│   │   ├── DatasetDetails.js
│   │   ├── SubmitToLeaderboard.js
│   │   ├── MySubmissions.js
│   │   ├── AdminLeaderboardManager.js
│   │   ├── AdminSubmissionsModeration.js
│   │   ├── LoginPage.js
│   │   ├── OAuthCallback.js
│   │   ├── AuthGuard.js
│   │   └── CsvBenchmarksDemo.js
│   ├── src/landing_page/landing_page_components/submissionFormatUtils.js
│   ├── src/utils/leaderboardAuth.js
│   ├── src/constants/RouteConstants.js
│   └── public/benchmark_csvs/
├── docs/                            MkDocs docs
├── aws_deploy/                      Elastic Beanstalk deployment files
├── .github/workflows/ci.yml
├── .github/workflows/deploy.yml
├── HANDOFF_MESSAGE.md               Sendable project handoff
├── KNOWLEDGE_TRANSFER.md            Deployment-focused handoff notes
├── AUDIT_FIX_NOTES.md               Audit/fix working history
├── README.md
└── AGENTS.md
```

## Tech Stack

| Area | Stack |
|------|-------|
| Backend | Python, Flask, Authlib, PyJWT, python-dotenv |
| Database | SQLite by default, optional MySQL/RDS, in-memory fallback only for development/failure cases |
| Auth | Google OAuth, HS256 JWT, optional JWKS bearer JWT, API keys, admin keys |
| Frontend | React 18, Create React App, Tailwind, MUI |
| State | Redux Toolkit + Redux Persist, Zustand |
| CI | GitHub Actions: backend tests, Ruff fatal checks, MkDocs, frontend lint/build, Docker builds |
| Deploy | Backend Docker to ECR/Elastic Beanstalk; frontend static build to S3/CloudFront |

## Current Verification Status

As of the latest handoff:

- `main` is pushed to `origin/main`.
- GitHub Actions `CI` is passing.
- GitHub Actions `Deploy` is passing.
- Backend tests: `100 passed`.
- Frontend build: passing.
- Frontend lint: passing with existing non-blocking warnings.
- Frontend helper tests exist for submission-format utilities.

CI currently enforces backend tests and frontend lint/build. It does not yet run a full browser E2E suite.

## Local Development

Backend:

```bash
cd Leaderboard/backend
pip install -r requirements.txt
cp .env.example .env
PORT=5001 FLASK_ENV=development python app.py
```

Frontend:

```bash
cd Leaderboard/frontend
npm install
PORT=3001 REACT_APP_API_BASE=http://127.0.0.1:5001 npm start
```

Common local URLs:

```text
Backend:  http://127.0.0.1:5001
Frontend: http://127.0.0.1:3001
Health:   http://127.0.0.1:5001/health
```

## Verification Commands

Use these before handing off code changes:

```bash
cd Leaderboard
uv run pytest -q backend/tests
uv run --with mkdocs-material mkdocs build --strict
ruff check backend --select E9,F63,F7,F82
```

```bash
cd Leaderboard/frontend
npm run lint
npm run build
npm test -- --watchAll=false --runTestsByPath src/landing_page/landing_page_components/submissionFormatUtils.test.js
```

For docs-only changes, it is acceptable to skip the full application test suite if the change is clearly documentation-only. Mention that in the final response.

## Important API Routes

```text
GET  /health
GET  /openapi.json
GET  /public/datasets
GET  /public/dataset_details
GET  /public/dataset_questions
GET  /public/submission_format
POST /public/submit_model
GET  /public/eval_jobs/<job_id>
POST /public/run_llm_submission
GET  /public/get_leaderboard
GET  /public/export/leaderboard
GET  /public/my_submissions
GET  /public/submission_quota
GET  /public/submissions/<id>
DELETE /public/submissions/<id>
POST /public/import_hf_dataset
POST /public/run_hf_model
GET  /public/benchmark_csvs
GET  /public/benchmark_models
POST /public/run_csv_benchmarks
GET  /public/auth/google/start
GET  /public/auth/google/callback
GET  /api/admin/submissions
POST /api/admin/submissions/<id>/activate
POST /api/admin/submissions/<id>/deactivate
POST /api/admin/datasets/<dataset>/questions_public
GET  /api/metrics
GET  /api/metrics/task/<task_type>
POST /api/leaderboard/add_dataset
POST /api/leaderboard/add_model
POST /api/leaderboard/seed
GET  /api/leaderboard/list
```

Route ownership:

- `backend/blueprints/leaderboard.py`: datasets, dataset details/questions, submission format, leaderboard reads/export, curated add/list/seed.
- `backend/blueprints/submissions.py`: submit model, async jobs, hosted LLM submission, My Submissions, detail/delete/visibility, quota.
- `backend/blueprints/eval.py`: HF import/model runner, CSV benchmark listing/runs, source sentence helpers, ingestion alias.
- `backend/blueprints/auth.py`: Google OAuth.
- `backend/blueprints/admin.py`: moderation/admin listing.
- `backend/blueprints/metrics.py`: metric catalog.
- `backend/blueprints/dataset_requests.py`: dataset request flow.

## Authentication Model

| Caller | Mechanism |
|--------|-----------|
| Public reads | No auth required |
| User writes/submissions | `X-API-Key` or `Authorization: Bearer <jwt>` with non-empty `sub` |
| Admin routes | `X-Admin-Key` or `X-API-Key` matching `LEADERBOARD_ADMIN_API_KEYS` |
| Google login | `/public/auth/google/start` -> Google -> callback -> Flask-minted JWT -> SPA stores `lb_jwt` |
| Main-app auth integration | Optional JWKS via `ANOTE_JWKS_URL`, with optional issuer/audience checks |

API key comparisons must use constant-time helpers. JWT decoding must verify expiration.

## Environment Variables

Keep `backend/.env.example` current whenever adding env usage.

Core production values:

```text
FLASK_ENV=production
PORT=5000
ALLOWED_ORIGINS=https://leaderboard.anote.ai
LEADERBOARD_FRONTEND_URL=https://leaderboard.anote.ai
LEADERBOARD_OAUTH_PUBLIC_BASE_URL=https://api-leaderboard.anote.ai
LEADERBOARD_JWT_SECRET=<strong random secret>
FLASK_SECRET_KEY=<strong random secret>
LEADERBOARD_API_KEYS=<optional write keys>
LEADERBOARD_ADMIN_API_KEYS=<admin keys>
GOOGLE_CLIENT_ID=<Google OAuth client id>
GOOGLE_CLIENT_SECRET=<Google OAuth secret>
```

Database:

```text
SQLITE_DB_PATH=./leaderboard.db
DB_HOST=<rds-endpoint>
DB_USER=<user>
DB_PASSWORD=<password>
DB_NAME=<database>
DB_PORT=3306
```

Provider keys:

```text
OPENAI_API_KEY
ANTHROPIC_API_KEY
GOOGLE_API_KEY
XAI_API_KEY
OPENAI_BASE_URL
OLLAMA_BASE_URL
TRUSTED_REMOTE_CODE_MODELS
```

Rate limits/quotas:

```text
DAILY_SUBMISSION_LIMIT
SUBMIT_MODEL_RATE_LIMIT
ADD_DATASET_RATE_LIMIT
IMPORT_DATASET_RATE_LIMIT
RUN_CSV_RATE_LIMIT
DISABLE_RATE_LIMIT
```

## Deployment Overview

`.github/workflows/deploy.yml` expects these GitHub repository secrets:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_ACCOUNT_ID
CLOUDFRONT_DIST_ID
```

Current workflow resources:

```text
AWS_REGION=us-east-1
ECR_REPO=anote-leaderboard-backend
EB_APP=anote-leaderboard
EB_ENV=anote-leaderboard-prod
S3_BUCKET=anote-leaderboard-frontend
REACT_APP_API_ENDPOINT=https://api-leaderboard.anote.ai
```

The deploy workflow:

1. Runs CI.
2. Checks for AWS secrets.
3. Builds/pushes backend Docker image to ECR.
4. Deploys backend to Elastic Beanstalk.
5. Builds frontend.
6. Syncs frontend build to S3.
7. Invalidates CloudFront.

If AWS secrets are missing, deploy jobs are skipped with a warning rather than failing the repo.

## Evaluation System

Key files:

- `backend/eval_core/evaluators.py`: task-specific scoring.
- `backend/eval_core/leaderboard_bridge.py`: converts dataset/reference/prediction payloads into evaluator inputs and builds submission formats.
- `backend/metrics_info_full.py`: metric metadata and per-task metric lists.
- `backend/composite_score.py`: 0-100 aggregate scoring.

Supported foundations include text classification, NER, QA/document QA, retrieval, translation, CSV benchmarks, HF import/model runners, and provider-backed LLM runs.

When adding a metric:

1. Add metadata in `metrics_info_full.py`.
2. Add it to the relevant task list.
3. Compute it in the evaluator if needed.
4. Update `composite_score.py` if lower values are better.
5. Add tests.

When adding a task type:

1. Add or extend an evaluator in `eval_core/evaluators.py`.
2. Register dispatch/conversion in `eval_core/leaderboard_bridge.py`.
3. Add metric catalog/task mappings.
4. Update submission-format behavior if the task has discrete labels/options.
5. Add backend tests and, when applicable, frontend submission-format tests.

## Frontend Conventions

- API base should use:
  `process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || "http://localhost:5001"`.
- Page-level components live in `frontend/src/landing_page/landing_page_components/`.
- New routes go in `frontend/src/constants/RouteConstants.js` and `LandingPage.js`.
- Keep the submission flow explicit about expected formats, allowed labels/options, and whether true labels are hidden.
- Do not expose answer keys in the frontend for benchmark datasets.
- Avoid adding new npm dependencies unless the value is clear.

Important components:

- `SubmitToLeaderboard.js`: JSON/CSV/manual/LLM submission UX.
- `submissionFormatUtils.js`: formats labels/options/sample JSON for submit prompts.
- `MySubmissions.js`: user-owned history and actions.
- `Leaderboard.js`: main leaderboard grid and advanced metric panel entry points.
- `DatasetDetails.js`: dataset details and metric explanations.
- `AdminSubmissionsModeration.js`: admin moderation surface.

## Current Product Capabilities

- Public dataset browsing and dataset details.
- Submission format endpoint with labels/options but no answer leakage.
- JSON upload, CSV upload, manual entry, and hosted LLM submission flows.
- Sync and async submit workflows with job polling.
- My Submissions history, private/public visibility, delete, detail, and compare flows.
- Admin moderation and dataset/question visibility controls.
- Daily quotas and per-minute rate limits.
- Composite 0-100 scoring plus detailed metric breakdowns.
- Leaderboard keyset pagination and export.
- CSV benchmark runner.
- Hugging Face import/model runner paths.
- Google OAuth and JWT/API key/admin auth.
- CI/CD and AWS deployment scaffold.

## Known Gaps And Future Work

Production/infrastructure:

- Configure real AWS secrets/resources.
- Use RDS/MySQL for production persistence.
- Run one real production smoke test with OAuth, provider keys, submissions, admin, and export.
- Replace in-process/thread-backed async jobs with a durable worker queue if usage grows.
- Add Redis/shared rate-limit state for horizontal scaling.
- Add provider cost caps/timeouts for hosted LLM runs.

Testing:

- Add Playwright/Cypress E2E tests for OAuth, JSON upload, CSV upload, hosted LLM submission, My Submissions, and admin.
- Add broader frontend unit tests to CI.

Product roadmap:

- Hidden/public benchmark splits for true blind evaluation.
- Generated benchmark suites from user sample data and Anote synthetic data pipelines.
- Model notes, tags, experiment history, and performance-over-time dashboards.
- Automatic critique/error analysis and model report cards.
- Code generation, VLM/multimodal, audio/speech, tool-use agent, and enterprise workflow benchmarks.
- Standardized model containers or inference adapters for true server-side blind eval.

## Files To Be Careful With

- `backend/pagination.py`: keyset cursor logic.
- `backend/auth_helpers.py`: JWT/JWKS verification.
- `backend/shared.py`: DB helpers, auth decorators, quotas, shared state.
- `backend/blueprints/submissions.py`: core submission/eval/job flow.
- `backend/eval_core/evaluators.py`: task scoring, especially NER span behavior.
- `backend/eval_core/leaderboard_bridge.py`: submission format and evaluator bridge.
- `frontend/src/landing_page/landing_page_components/SubmitToLeaderboard.js`: main submit UX.
- `frontend/src/landing_page/landing_page_components/MySubmissions.js`: authenticated submission history.
- `.github/workflows/deploy.yml`: deployment domains/secrets/resource names.

## Handoff References

- `HANDOFF_MESSAGE.md`: sendable high-level handoff and future directions.
- `KNOWLEDGE_TRANSFER.md`: deployment-focused handoff notes.
- `AUDIT_FIX_NOTES.md`: audit/fix history.
- `README.md`: general product and API docs.
- `TODO.md`: older backlog; useful, but verify against current code before treating any item as open.
