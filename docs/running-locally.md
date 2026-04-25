# Running Locally

## Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
export PORT=5001 FLASK_ENV=development
python backend/app.py
```

Health check:

```bash
curl http://localhost:5001/health
```

## Seed Demo Data

```bash
export LEADERBOARD_API_BASE=http://localhost:5001
python backend/examples/seed_demo.py
```

## Frontend

```bash
cd frontend
npm install
REACT_APP_API_BASE=http://localhost:5001 npm start
```

Open `http://localhost:3000`.

## Docker Compose

```bash
docker compose up --build
```

This starts MySQL, the Flask backend on `http://localhost:5001`, and the React frontend on `http://localhost:3000`.

## Docs

```bash
pip install mkdocs-material
mkdocs serve
```

Open `http://127.0.0.1:8000`.
