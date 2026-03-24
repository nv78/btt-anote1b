# CLAUDE.md — Anote Model Leaderboard

This file provides AI assistants with the context needed to work effectively in this repository.

---

## Project Overview

The **Anote Model Leaderboard** is a transparent, community-driven benchmarking platform for evaluating and ranking AI models across multiple datasets and task types. It supports:

- Text classification, named entity recognition, Q&A, and translation benchmarks
- Multi-language translation evaluation (Spanish, Arabic, Japanese, Chinese, Korean)
- Dual evaluation metrics: BLEU (exact n-gram) and BERTScore (semantic similarity)
- REST API for submitting model predictions and retrieving ranked results
- A React frontend for browsing results, submitting models, and running CSV benchmarks

---

## Architecture

This is a **monorepo** with two independent sub-projects:

```
Leaderboard/
├── backend/          # Flask (Python) REST API
└── frontend/         # React (JavaScript) web app
```

### Backend (`backend/`)

| File | Purpose |
|------|---------|
| `app.py` | Main Flask application — all API endpoints (~850 lines) |
| `models.py` | Model provider wrappers (OpenAI, Anthropic, Google, Ollama, echo) |
| `csv_bench.py` | CSV benchmark utilities: task inference, scoring, dataset listing |
| `sdk/leaderboard_sdk.py` | Python client SDK (`LeaderboardClient`) for API access |
| `database/schema.sql` | MySQL schema: `benchmark_datasets`, `model_submissions`, `evaluation_results` |
| `database/init_db_dev.py` | Dev database initialization script |
| `examples/seed_demo.py` | Seeds demo data into a running backend |
| `pytest/` | Test suite (see Testing section) |
| `.env.example` | Template for environment variables |
| `requirements.txt` | Python dependencies |

**Storage:** MySQL primary store with automatic in-memory (`_STORE` dict) fallback when DB is unavailable.

**Optional dependencies:** `bert-score`, `mysql-connector-python`, `openai`, `anthropic`, `google-generativeai`, `transformers`, `torch` are all optional — the backend degrades gracefully if missing.

### Frontend (`frontend/`)

| Path | Purpose |
|------|---------|
| `src/App.js` | App entry point, Google Analytics 4 setup, React Router |
| `src/landing_page/LandingPage.js` | Main layout — renders all major sections |
| `src/landing_page/landing_page_components/` | Modular UI components (header, banner, leaderboard, submission form, etc.) |
| `src/redux/DatasetSlice.js` | Redux slice for dataset state |
| `src/stores/store.js` | Redux store configuration |
| `src/zustand/` | Zustand stores (lightweight local state) |
| `src/constants/` | Route constants, DB enums |
| `public/benchmark_csvs/` | 20+ CSV benchmark datasets served statically |

**State management:** Redux Toolkit + Redux Persist for global/persistent state; Zustand for local component state.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend language | Python 3.8+ |
| Backend framework | Flask 2.3+ |
| Database | MySQL (optional; in-memory fallback) |
| Frontend language | JavaScript (ES2020+) |
| Frontend framework | React 18 |
| UI library | Material-UI (MUI) v5 |
| CSS | Tailwind CSS + Emotion (CSS-in-JS) |
| State management | Redux Toolkit + Zustand |
| Charts | D3 / react-d3-components |
| File upload | Uppy (XHR backend) |
| Analytics | React GA4 |
| Package managers | pip (backend), npm (frontend) |

---

## Development Setup

### Backend

```bash
cd backend

# Optional: create a virtual environment
python -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy env template and configure (optional — works without API keys)
cp .env.example .env

# Run on port 5001
PORT=5001 FLASK_ENV=development python app.py
```

Backend is now available at `http://localhost:5001`.

### Frontend

```bash
cd frontend

npm install

# Point at the local backend
REACT_APP_API_ENDPOINT=http://localhost:5001 npm start
```

Frontend is now available at `http://localhost:3000`.

### Seed Demo Data (optional)

```bash
LEADERBOARD_API_BASE=http://localhost:5001 python backend/examples/seed_demo.py
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | `5001` | Flask server port |
| `FLASK_ENV` | `development` | Flask environment |
| `OPENAI_API_KEY` | — | OpenAI model evaluation |
| `ANTHROPIC_API_KEY` | — | Anthropic model evaluation |
| `GOOGLE_API_KEY` | — | Google Gemini evaluation |
| `XAI_API_KEY` | — | xAI model evaluation |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama local inference |
| `OPENAI_BASE_URL` | `https://api.openai.com` | OpenAI-compatible base URL |
| `DB_HOST` | `localhost` | MySQL host |
| `DB_USER` | `root` | MySQL user |
| `DB_PASSWORD` | — | MySQL password |
| `DB_NAME` | `agents` | MySQL database |
| `DB_PORT` | `3306` | MySQL port |
| `ALLOWED_ORIGINS` | `*` | CORS allowed origins |
| `LEADERBOARD_API_BASE` | `http://localhost:5001` | Used by seed/test scripts |

**No API keys are required to run the platform.** API keys are only needed if you want to evaluate GPT-4, Claude, Gemini, etc.

### Frontend

| File | `REACT_APP_API_ENDPOINT` |
|------|--------------------------|
| `.env.development` | `http://localhost:5000` |
| `.env.production` | `https://api.anote.ai` |

When running locally, override with `REACT_APP_API_ENDPOINT=http://localhost:5001`.

---

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Welcome / info |
| GET | `/health` | Health check |
| GET | `/public/datasets` | List benchmark datasets |
| GET | `/public/get_source_sentences` | Sentences to translate (for evaluation) |
| POST | `/public/submit_model` | Submit model predictions for scoring |
| GET | `/public/get_leaderboard` | Ranked model results |
| GET | `/public/benchmark_csvs` | List CSV benchmark files |
| POST | `/public/run_csv_benchmarks` | Benchmark models against CSV datasets |
| POST | `/api/leaderboard/add_dataset` | Add a new benchmark dataset |
| POST | `/api/leaderboard/add_model` | Add a model result to a dataset |
| GET | `/api/leaderboard/list` | List all datasets |

---

## Model Providers

The `provider` field in `submit_model` selects the inference backend:

| Provider | Description | Requirement |
|----------|-------------|-------------|
| `openai` | OpenAI API (GPT-4o, etc.) | `OPENAI_API_KEY` |
| `anthropic` | Anthropic API (Claude) | `ANTHROPIC_API_KEY` |
| `google` | Google Generative AI (Gemini) | `GOOGLE_API_KEY` |
| `ollama` | Local Ollama instance | Running Ollama at `OLLAMA_BASE_URL` |
| `echo` | Dummy echo provider | No requirement (good for tests) |
| `py` | Python function in `models.py` | N/A |

---

## Testing

Tests live in `backend/pytest/`.

```bash
cd backend
python -m pytest pytest/
```

| File | Coverage |
|------|---------|
| `test_dataset_endpoints.py` | API endpoint integration tests |
| `test_sdk_client.py` | `LeaderboardClient` SDK tests |
| `pytest/test_data/` | Test fixture files |
| `pytest/TESTING_GUIDE.md` | Complete guide with 13+ test scenarios |

Key test scenarios:
- BLEU scoring for 5 languages (Spanish, Arabic, Korean, Japanese, Chinese)
- BERTScore evaluation for all languages
- Model submission and validation
- Leaderboard ranking verification

---

## Key Conventions

### Backend

- **Optional imports:** Wrap optional deps in `try/except ImportError` with a flag (e.g., `BERT_SCORE_AVAILABLE = False`). Never fail hard on missing optional packages.
- **DB fallback:** Always write logic to work with both MySQL (`get_db_connection()`) and the in-memory `_STORE` dict.
- **BLEU vs BERTScore:** BLEU scores 0 for Asian scripts (Japanese, Chinese, Korean) — always use BERTScore for those. Spanish/Arabic BLEU is meaningful (~0.4).
- **Type hints:** Use Python type annotations for all new functions.
- **Lazy imports:** Import heavy modules (e.g., `csv_bench`) inside the function scope when called infrequently.

### Frontend

- **Component structure:** Page-level components go in `src/landing_page/landing_page_components/`. Keep them self-contained.
- **State management choice:** Use Redux for data shared across many components or needing persistence; use Zustand for local/ephemeral state.
- **Styling:** Prefer MUI's `sx` prop and Tailwind utility classes. Avoid inline styles for anything non-trivial.
- **Environment vars:** Always prefix frontend env vars with `REACT_APP_`. Access via `process.env.REACT_APP_*`.
- **Analytics:** Call `ReactGA.event()` for significant user interactions (model submissions, benchmark runs).

### General

- **No database required:** The project must remain functional without MySQL. Do not break the in-memory fallback.
- **No API keys required:** Core functionality (browsing leaderboard, running CSV benchmarks with `echo` provider) must work without any API keys configured.
- **Port 5001 for backend:** macOS reserves port 5000; use 5001 locally.

---

## Database Schema

Three tables in MySQL (all have an `id` PK and `created` timestamp):

- **`benchmark_datasets`** — available benchmarks (`name`, `task_type`, `evaluation_metric`, `reference_data`, `active`)
- **`model_submissions`** — model predictions (`benchmark_dataset_id` FK, `model_name`, `submitted_by`, `model_results`)
- **`evaluation_results`** — computed scores (`model_submission_id` FK, `score`, `evaluation_details`)

Pre-seeded with 9 translation benchmarks (5 languages × BLEU + BERTScore, minus one).

---

## Common Tasks

### Add a new API endpoint
1. Add the route in `backend/app.py` following the existing pattern
2. Add a corresponding test in `backend/pytest/test_dataset_endpoints.py`

### Add a new model provider
1. Add a wrapper function in `backend/models.py`
2. Register it in the provider dispatch logic in `app.py`
3. Document the required env variable above

### Add a new CSV benchmark dataset
1. Place the `.csv` file in `frontend/public/benchmark_csvs/`
2. Ensure it has headers recognizable by `csv_bench.py`'s `infer_task_type()` function

### Add a new frontend component
1. Create the component in `src/landing_page/landing_page_components/`
2. Import and render it in `LandingPage.js`
3. Add the route to `src/constants/RouteConstants.js` if it needs its own page

---

## Branch Strategy

- `main` / `master` — production-ready code
- Feature branches — use descriptive names; PRs target `main`

---

## External Services (Production)

- Backend API: `https://api.anote.ai`
- Frontend: served as a static React build
- Analytics: Google Analytics 4 (configured in `App.js`)
