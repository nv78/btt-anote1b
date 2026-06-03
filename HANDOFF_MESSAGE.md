# Anote Model Leaderboard Handoff Message

Hey everyone!

I worked with Anote through Break Through Tech's AI Fellow program, and I am handing off my group's project: the **Anote Model Leaderboard**.

Repo: <https://github.com/anote-ai/Leaderboard>  
Frontend target: `https://leaderboard.anote.ai`  
Backend target in the current deploy workflow: `https://api-leaderboard.anote.ai`

If the final backend domain should be `api.anote.ai`, update the deploy workflow and frontend environment before production launch. The current code is wired around `api-leaderboard.anote.ai`.

## What It Is

Think Kaggle leaderboards, but for enterprise AI model evaluation.

Users can benchmark model outputs on fixed datasets, submit predictions through the web UI or backend API, get automatically evaluated, and compare performance on public or private leaderboards. The goal is to support real model iteration: fine-tuning, longer training, prompt/model changes, architecture changes, synthetic-data evaluation, niche enterprise benchmarks, and eventually true blind evaluation on hidden test sets.

This is not only a frontend. The product depends on a backend API that owns evaluation, auth, submissions, quotas, admin moderation, async job status, provider-backed LLM runs, and leaderboard persistence.

## What Is Built

### Backend

- Flask API under `backend/`.
- SQLite by default for local development.
- Optional MySQL/RDS-style persistence for production.
- Blueprint modules for leaderboard, submissions, eval jobs, auth, admin, metrics, and dataset requests.
- Google OAuth login that mints JWT sessions.
- API key auth and admin key auth.
- Optional JWKS bearer-token validation for tokens issued by another Anote auth system.
- Daily submission quotas and per-minute rate limits, DB-backed when persistence is configured.
- JSON API error responses for 404/405/500 and validation failures.
- Security hardening around timing-safe API key comparison, JWT expiration verification, CORS, and production secret defaults.

### Frontend

- React 18 Create React App under `frontend/`.
- Tailwind/MUI UI.
- Redux/Zustand state.
- Main product surfaces: leaderboard, dataset details, submit flow, My Submissions, admin moderation, CSV benchmark demo, and OAuth callback.
- JSON and CSV upload support for submissions.
- Manual prediction entry.
- LLM prompt workflow that shows the expected JSON output format.
- Discrete labels/options shown on submission screens for datasets where users must choose from fixed classes, without exposing answer keys.
- My Submissions page for user-owned history, details, delete/visibility actions, pagination, and comparisons.

### Evaluation And Workflows

- Automatic scoring for multiple NLP task families: text classification, NER, QA/document QA, retrieval, translation, and CSV benchmarks.
- Metric breakdowns stored as `detailed_scores`.
- Composite 0-100 leaderboard scoring.
- Advanced metric panels in the UI.
- Keyset pagination for leaderboard reads.
- CSV/JSON leaderboard export.
- `GET /public/submission_format` returns copy-paste-ready submission JSON templates.
- `POST /public/submit_model` supports sync submissions and async submissions with job polling.
- `GET /public/eval_jobs/<job_id>` polls async evaluation jobs.
- `POST /public/run_llm_submission` supports backend-run LLM submissions using configured provider packages/keys.
- Hugging Face dataset import and HF model runner endpoints exist, with optional dependencies.
- Admin moderation and dataset/question visibility controls.
- Metric catalog endpoints for explaining metrics by task type.

## Current Verification Status

As of the latest pushed `main` branch:

- GitHub Actions `CI`: passing.
- GitHub Actions `Deploy`: passing.
- Backend tests: 100 passing.
- Frontend build: passing.
- Frontend lint: passing with existing non-blocking warnings.
- Frontend helper tests exist for submission-format utilities.

Note: CI currently enforces backend tests plus frontend lint/build. It does not yet run a full browser E2E suite.

## How To Run Locally

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

Useful checks:

```bash
cd Leaderboard
uv run pytest -q backend/tests

cd Leaderboard/frontend
npm run lint
npm run build
```

## Deployment Notes

The current GitHub deploy workflow is set up for:

- Backend Docker image pushed to ECR.
- Backend deployed to AWS Elastic Beanstalk, which runs on EC2 underneath.
- Frontend built as static CRA assets.
- Frontend synced to S3.
- CloudFront invalidation after frontend deploy.

GitHub repository secrets needed:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_ACCOUNT_ID
CLOUDFRONT_DIST_ID
```

AWS resources expected by the workflow:

```text
ECR repo: anote-leaderboard-backend
Elastic Beanstalk app: anote-leaderboard
Elastic Beanstalk env: anote-leaderboard-prod
S3 bucket: anote-leaderboard-frontend
CloudFront distribution for the frontend
Backend DNS: api-leaderboard.anote.ai
Frontend DNS: leaderboard.anote.ai
```

Backend production environment values to configure in Elastic Beanstalk or the chosen EC2 runtime:

```text
FLASK_ENV=production
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

Provider keys for backend-hosted LLM runs, only if Anote wants to enable those providers:

```text
OPENAI_API_KEY
ANTHROPIC_API_KEY
GOOGLE_API_KEY
XAI_API_KEY
OPENAI_BASE_URL
OLLAMA_BASE_URL
```

For serious production use, use RDS/MySQL or another durable database instead of instance-local SQLite. SQLite is fine for local development and demos, but not for resilient multi-instance production.

Production smoke checklist:

- `GET /health`
- `GET /openapi.json`
- Google OAuth login and callback
- Fetch datasets
- Open dataset details
- Copy/download submission format
- Submit JSON predictions
- Submit CSV predictions
- Run one LLM submission with a provider key configured
- Poll async eval job
- Check My Submissions
- Check admin moderation with admin key
- Export leaderboard CSV/JSON

## What Matches The Product Vision

The backend API and evaluation loop are mostly there:

- Users can submit model predictions programmatically.
- The app can evaluate multiple task types.
- The system stores detailed metrics, composite scores, metadata, and submission history.
- The UI now guides users through the submission format, valid labels/options, uploads, LLM prompt formatting, and personal submission history.
- Hosted LLM runs are wired so production can abstract provider keys away from users if server-side provider keys are configured.

The analytics foundation is there, but the full analytics product is not finished:

- Built: detailed metric breakdowns, composite scoring, advanced metric panels, submission history, comparisons, exports.
- Not fully built yet: performance-over-time dashboards, model notes, experiment tracking, regression charts, automatic critique/error analysis, and cost/latency analytics.

## Important Future Work

### Production Infrastructure

- Add the real AWS secrets to GitHub Actions.
- Create or verify the AWS resources listed above.
- Configure Google OAuth redirect URIs for production.
- Move production persistence to RDS/MySQL.
- Replace in-process/thread-backed async jobs with a durable queue such as Celery, RQ, SQS, or another worker system.
- Add Redis or another shared store if horizontally scaling quotas/rate limits.
- Add cost caps/timeouts for hosted LLM runs.

### Testing

- Add Playwright or Cypress E2E tests for OAuth, JSON upload, CSV upload, LLM submission, My Submissions, and admin workflows.
- Add frontend unit tests to CI, not just lint/build.
- Keep `uv run pytest -q backend/tests` green before every backend change.

### Blind Evaluation And Label Protection

- Current dataset question endpoints avoid exposing answer keys.
- Current submission-format endpoint exposes valid labels/options but not answers.
- Future version should support public dev sets plus hidden test sets.
- Longer-term, users should be able to submit model weights, containers, or standardized inference adapters so Anote can run true server-side blind evaluation.
- Add audit trails and signed submissions for high-stakes enterprise evals.

### More Benchmark Types

- Code generation benchmarks.
- VLM/multimodal benchmarks.
- Audio/speech benchmarks.
- Agent/tool-use benchmarks.
- Safety, hallucination, calibration, robustness, and LLM-as-judge style evals.
- Optional richer metrics such as COMET, BERTScore, calibration metrics, and domain-specific custom scorers where dependencies/costs are acceptable.

### Better Model Lifecycle And Analytics

- Model notes/changelogs.
- Tags for training run, dataset version, prompt version, architecture, fine-tune config, and owner/team.
- Performance-over-time charts.
- Regression detection.
- Automatic critique: weakest classes, common error buckets, representative failure examples, and suggested next experiments without leaking hidden labels.

### Bigger Product Directions

- Let users upload a small amount of their own task data, then generate benchmark datasets from it using Anote's synthetic data pipelines.
- Create private company-specific benchmark suites for niche workflows, then let teams track model quality against those suites over time.
- Support hidden/public benchmark splits so users can iterate on public examples while Anote preserves a true blind test set.
- Add dataset quality tooling: deduplication, label-balance checks, ambiguity detection, adversarial example generation, and benchmark difficulty scoring.
- Build an "eval suite generator" where a user describes a target behavior, uploads examples, and gets a ready-to-run leaderboard benchmark with labels, scoring, and starter prompts.
- Add model report cards that summarize strengths, weaknesses, regressions, safety risks, and recommended next training/evaluation steps.
- Support standardized model containers or inference adapters so users can submit a model once and Anote runs it against multiple private benchmarks.
- Add longitudinal team analytics: compare model families, fine-tune versions, prompt versions, datasets, and training recipes across time.
- Expand beyond NLP into code generation, VLM/multimodal, audio/speech, tool-use agents, structured extraction, and enterprise workflow automation benchmarks.
- Use evaluator ensembles for richer scoring: deterministic metrics, embedding similarity, LLM-as-judge, rubric-based grading, and human review queues for high-value edge cases.

## Read First Before Continuing

- `KNOWLEDGE_TRANSFER.md`
- `AGENTS.md`
- `README.md`
- `backend/.env.example`
- `.github/workflows/ci.yml`
- `.github/workflows/deploy.yml`
- `AUDIT_FIX_NOTES.md`

## Files To Be Careful With

- `backend/pagination.py` — keyset cursor logic.
- `backend/auth_helpers.py` — JWT/JWKS auth.
- `backend/shared.py` — auth, quotas, DB adapters.
- `backend/blueprints/submissions.py` — core submission/eval/job flow.
- `backend/eval_core/evaluators.py` — task scoring logic.
- `backend/eval_core/leaderboard_bridge.py` — bridges datasets/submissions into eval.
- `frontend/src/landing_page/landing_page_components/SubmitToLeaderboard.js` — main submission UX.
- `frontend/src/landing_page/landing_page_components/MySubmissions.js` — user submission history.

## Main Caveat

This is handoff-ready as a strong product prototype and integration baseline. The remaining work is mostly productionization: AWS secrets/resources, a durable production database, one real production smoke test with OAuth/provider keys, and a durable async worker if this will handle serious traffic.
