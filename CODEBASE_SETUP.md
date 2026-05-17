# Leaderboard — Codebase Setup

## What is Leaderboard?

Leaderboard is an LLM performance ranking platform available at [anote.ai/leaderboard](https://anote.ai/leaderboard). It tracks and compares model quality across tasks and datasets, giving teams an objective view of which models perform best for their use cases.

## Architecture

| Layer | Technology | Location |
|-------|-----------|----------|
| Frontend | React (Node 18) | `frontend/` |
| Backend | Python 3.11, FastAPI | `backend/` |
| Container orchestration | Docker Compose | `docker-compose.yml` |

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) (v2+)
- Node 18 (only needed for manual frontend setup)
- Python 3.11 (only needed for manual backend setup)

## Quick Start with Docker Compose (RECOMMENDED)

```bash
# 1. Clone the repo
git clone https://github.com/anote-ai/Leaderboard.git
cd Leaderboard

# 2. Copy and fill in environment variables
cp .env.example .env
# Edit .env and set the required values

# 3. Start all services
docker-compose up --build
```

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend API: [http://localhost:8000](http://localhost:8000)

## Manual Setup (without Docker)

### Backend

```bash
cd backend
pip install -e ".[dev]"
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Dependencies are declared in `pyproject.toml`. The `[dev]` extra includes linting and testing tools.

### Frontend

```bash
cd frontend
npm install
npm start
```

The dev server starts at `http://localhost:3000`.

## Environment Variables

Copy `.env.example` to `.env` and fill in the values.

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `ANTHROPIC_API_KEY` | No | Anthropic API key for Claude models |
| `SECRET_KEY` | Yes | Random secret for session signing |
| `REACT_APP_BACK_END_HOST` | Yes | Backend URL seen by the browser |

## CI/CD

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| `backend.yml` | PR / push to main | Runs backend tests |
| `ci.yml` | PR / push to main | Lint and type checks |
| `deploy.yml` | Manual (`workflow_dispatch`) | Builds Docker image → ECR → ECS (backend); React build → S3 → CloudFront (frontend) |

### Required GitHub Secrets for Deployment

Configure these in **Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | IAM access key with ECR/ECS/S3/CloudFront permissions |
| `AWS_SECRET_ACCESS_KEY` | Corresponding IAM secret key |
| `AWS_REGION` | AWS region (defaults to `us-east-1`) |
| `ECS_CLUSTER` | ECS cluster name |
| `ECS_SERVICE_BACKEND` | ECS service name for the backend |
| `S3_BUCKET_FRONTEND` | S3 bucket for the React build (ECR repository: `leaderboard-backend`) |
| `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront distribution ID |
| `REACT_APP_BACK_END_HOST` | Backend URL injected at build time |
| `SLACK_WEBHOOK_URL` | (Optional) Slack webhook for failure alerts |
