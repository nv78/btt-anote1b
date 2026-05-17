# Leaderboard — Codebase Setup

## What is Leaderboard?

Leaderboard provides LLM performance rankings hosted at [anote.ai/leaderboard](https://anote.ai/leaderboard). It benchmarks and compares language models across a variety of tasks and domains.

## Architecture

| Layer | Technology | Location |
|-------|-----------|----------|
| Frontend | React (Create React App) | `frontend/` |
| Backend | Python 3.11, FastAPI | `backend/` |
| Container orchestration | Docker Compose | `docker-compose.yml` |

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) (recommended path)
- Node 18+ (manual frontend setup)
- Python 3.11+ (manual backend setup)

## Quick Start with Docker Compose (RECOMMENDED)

```bash
# 1. Clone the repo
git clone https://github.com/anote-ai/Leaderboard.git
cd Leaderboard

# 2. Create your local env file and fill in values
cp .env.example .env

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
uvicorn app:app --reload --port 8000
```

Dependencies are declared in `pyproject.toml` at the repo root.

### Frontend

```bash
cd frontend
npm install
npm start   # starts on http://localhost:3000
```

## Environment Variables

Copy `.env.example` to `.env` and set the following:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `OPENAI_API_KEY` | OpenAI API key for LLM evaluation calls |
| `REACT_APP_BACK_END_HOST` | Backend URL consumed by the React app |

## Dependency Management

Python dependencies are managed via `pyproject.toml`. Install everything including dev tools with:

```bash
pip install -e ".[dev]"
```

## CI / CD

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| `backend.yml` | Pull request | Runs backend tests |
| `ci.yml` | Pull request | Lint and type-check |
| `deploy.yml` | Manual (`workflow_dispatch`) | Builds Docker image (ECR repository: `leaderboard-backend`) → pushes to ECR → updates ECS service; syncs frontend build to S3 and invalidates CloudFront |

### Required GitHub Secrets for Deployment

Set these in **Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | IAM access key with ECS/ECR/S3/CloudFront permissions |
| `AWS_SECRET_ACCESS_KEY` | Corresponding IAM secret |
| `AWS_REGION` | AWS region, e.g. `us-east-1` |
| `ECS_CLUSTER` | Name of the ECS cluster |
| `ECS_SERVICE_BACKEND` | Name of the ECS service for the backend |
| `S3_BUCKET_FRONTEND` | S3 bucket name for the frontend static files |
| `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront distribution ID to invalidate after deploy |
| `REACT_APP_BACK_END_HOST` | Backend URL injected at React build time |
| `SLACK_WEBHOOK_URL` | (Optional) Slack incoming webhook for failure notifications |
