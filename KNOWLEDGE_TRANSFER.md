# Anote Leaderboard Knowledge Transfer

This repo contains the deployable Anote Leaderboard application:

- Backend: Flask API in `backend/`
- Frontend: Create React App in `frontend/`
- Deployment target: backend Docker image on AWS Elastic Beanstalk, frontend static build on S3 + CloudFront

The goal of the project is to let users benchmark models against fixed datasets, submit predictions, compare scores on a leaderboard, and optionally run hosted LLM submissions through the backend so users do not need to manage provider calls themselves.

## What Was Built

- Public leaderboard views for datasets and model submissions.
- JSON and CSV submission flows, including drag/drop upload fixes.
- A clearer LLM prompt flow that shows the expected JSON output format.
- Discrete label/options display for datasets where answers must come from a known set.
- Google OAuth login callback handling for local and deployed frontend URLs.
- Private/public submissions, owner-only visibility toggles, owner delete, and My Submissions pagination.
- Admin submission management and moderation endpoints.
- Daily submission quota and per-minute rate limits.
- Backend provider runners for OpenAI, Anthropic, Gemini, xAI/Ollama hooks, and CSV benchmark execution.
- Email notification hooks via SMTP or AWS SES.
- Security hardening around JWT expiry, API-key comparison, JSON error responses, CORS, and production secret defaults.
- CI/CD scaffolding for backend/frontend checks and AWS deployment.

## Current Repo Status

As of the final handoff commit, GitHub Actions reports:

- `CI`: passing.
- `Deploy`: passing, but AWS deploy jobs are skipped until AWS repository secrets are configured.

The deploy workflow intentionally checks for required AWS secrets first. If they are missing, it exits successfully with a warning instead of leaving the repo in a permanently red state.

## Where To Configure AWS / CloudFront / EC2

The deployment workflow lives at `.github/workflows/deploy.yml`.

Required GitHub repository secrets:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_ACCOUNT_ID
CLOUDFRONT_DIST_ID
```

These are added in GitHub:

```text
Repo -> Settings -> Secrets and variables -> Actions -> Repository secrets
```

The CloudFront distribution ID goes into `CLOUDFRONT_DIST_ID`.

The backend compute target is Elastic Beanstalk, which runs on EC2 under the hood. The workflow uses these names:

```text
AWS_REGION=us-east-1
ECR_REPO=anote-leaderboard-backend
EB_APP=anote-leaderboard
EB_ENV=anote-leaderboard-prod
S3_BUCKET=anote-leaderboard-frontend
REACT_APP_API_ENDPOINT=https://api-leaderboard.anote.ai
```

If Natan wants raw EC2 instead of Elastic Beanstalk, the backend Docker image can still be used, but the workflow would need to be changed from `eb deploy` to a raw EC2/ALB deployment process. The current intended path is EB because it handles EC2 instances, health checks, app versions, and rolling deploys with less custom infrastructure.

## AWS Resources Needed

Create or verify these resources before enabling real deployment:

- ECR repository: `anote-leaderboard-backend`
- Elastic Beanstalk application: `anote-leaderboard`
- Elastic Beanstalk environment: `anote-leaderboard-prod`
- S3 bucket for frontend: `anote-leaderboard-frontend`
- CloudFront distribution in front of the frontend bucket
- Backend DNS name, expected by frontend: `https://api-leaderboard.anote.ai`
- Frontend DNS name, expected by OAuth/CORS: `https://leaderboard.anote.ai`
- Optional RDS/MySQL database if SQLite is not enough for production

## Backend Runtime Environment

Elastic Beanstalk environment properties should be configured in:

```text
Elastic Beanstalk -> Environment -> Configuration -> Software -> Environment properties
```

The template is in `aws_deploy/.ebextensions/01_env.config` and mirrored in `.ebextensions/01_env.config`.

Important production values:

```text
FLASK_ENV=production
PORT=5000
ALLOWED_ORIGINS=https://leaderboard.anote.ai
LEADERBOARD_FRONTEND_URL=https://leaderboard.anote.ai
LEADERBOARD_OAUTH_PUBLIC_BASE_URL=https://api-leaderboard.anote.ai
LEADERBOARD_JWT_SECRET=<random 32+ byte secret>
FLASK_SECRET_KEY=<random 32+ byte secret>
LEADERBOARD_ADMIN_API_KEYS=<comma-separated admin keys>
LEADERBOARD_API_KEYS=<comma-separated write keys, if API key auth is required>
```

Google OAuth:

```text
GOOGLE_CLIENT_ID=<from Google Cloud Console>
GOOGLE_CLIENT_SECRET=<from Google Cloud Console>
```

Provider keys for backend-run LLM submissions:

```text
OPENAI_API_KEY=<optional>
ANTHROPIC_API_KEY=<optional>
GOOGLE_API_KEY=<optional>
XAI_API_KEY=<optional>
OPENAI_BASE_URL=https://api.openai.com
```

Database options:

```text
SQLITE_DB_PATH=./leaderboard.db
DB_HOST=<rds-endpoint>
DB_USER=leaderboard
DB_PASSWORD=<secret>
DB_NAME=leaderboard
DB_PORT=3306
```

For serious production use, prefer RDS/MySQL over instance-local SQLite so data survives instance replacement and can work across multiple backend instances.

## Google OAuth Setup

In Google Cloud Console, add the backend callback URL as an authorized redirect URI:

```text
https://api-leaderboard.anote.ai/public/auth/google/callback
```

For local testing, also add:

```text
http://localhost:5001/public/auth/google/callback
http://127.0.0.1:5001/public/auth/google/callback
```

The backend redirects successful logins to:

```text
LEADERBOARD_FRONTEND_URL/oauth/callback#access_token=...
```

So `LEADERBOARD_FRONTEND_URL` must be the deployed frontend origin.

## Local Development

Backend:

```bash
cd backend
uv run python app.py
```

Common local backend URL:

```text
http://127.0.0.1:5001
```

Frontend:

```bash
cd frontend
REACT_APP_API_BASE=http://127.0.0.1:5001 npm start
```

Common local frontend URL:

```text
http://127.0.0.1:3001
```

Useful smoke checks:

```bash
curl http://127.0.0.1:5001/health
curl 'http://127.0.0.1:5001/public/submission_quota?submitter_id=smoke'
```

## Verification Commands

Backend tests:

```bash
uv run pytest -q backend/tests
```

Backend fatal static checks:

```bash
ruff check backend --select E9,F63,F7,F82
```

Frontend lint:

```bash
cd frontend
npm run lint
```

Frontend build:

```bash
cd frontend
npm run build
```

Docs:

```bash
uv run --with mkdocs-material mkdocs build --strict
```

Docker image checks, when Docker Desktop/daemon is running:

```bash
docker build -t anote-leaderboard-backend:local ./backend --platform linux/amd64
docker build -t anote-leaderboard-frontend:local ./frontend --platform linux/amd64
```

## CI/CD Behavior

`.github/workflows/ci.yml` runs:

- backend dependency install
- ruff fatal checks
- backend tests with coverage
- MkDocs build
- backend Docker build
- frontend dependency install
- frontend lint
- frontend production build
- frontend Docker build

`.github/workflows/deploy.yml` runs CI first, then checks for AWS secrets. If secrets are present:

- builds backend Docker image
- pushes it to ECR
- deploys backend to Elastic Beanstalk
- builds frontend
- syncs frontend build to S3
- invalidates CloudFront

If secrets are missing, AWS deploy jobs are skipped and the workflow shows a warning naming the missing secrets.

## Known Remaining Work

- Add real AWS secrets in GitHub Actions.
- Create or verify the AWS resources listed above.
- Confirm the S3 bucket policy / CloudFront setup. The workflow currently uses `--acl public-read`; if the bucket uses Object Ownership with ACLs disabled, remove the ACL flags and use CloudFront OAC/bucket policy instead.
- Decide whether production DB should be RDS/MySQL. Recommended for production.
- Configure production Google OAuth redirect URI.
- Configure production provider keys only for providers Anote wants to support.
- Run one real end-to-end production smoke after AWS is configured: login, export questions, submit JSON/CSV, run an LLM submission, check My Submissions, check admin view.
- Optional cleanup: frontend lint warnings are non-blocking but visible in CI annotations.
- Optional future infra: background workers/queue for long LLM/HF jobs if usage grows.

## Knowledge Transfer Talking Points

- The backend is required in production; this is not a static-only frontend.
- Elastic Beanstalk is the current EC2-backed deployment path.
- CloudFront is for the frontend static app, not the Flask API.
- `api-leaderboard.anote.ai` should point to the backend/EB environment or its load balancer.
- `leaderboard.anote.ai` should point to CloudFront/S3 frontend.
- The UI intentionally exposes label choices for discrete-label datasets so users and LLM prompts know valid outputs.
- Hosted LLM execution means the backend uses Anote-owned provider keys; users do not need to bring keys unless Anote chooses to expose that mode.
- Daily quota/rate limits exist in the backend, but scaling beyond one SQLite-backed instance should move durable state to RDS/MySQL and possibly Redis/queue infrastructure.
