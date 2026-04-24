# Anote - Model Leaderboard

Anote's Model Leaderboard provides a way to benchmark and compare model performance. We have an API to:
1. **Adding new datasets** to the leaderboard across **all task types**.
2. **Adding new model submissions** to existing datasets.

The API is the backbone for a transparent, scalable, and community-driven benchmarking platform for AI models, supporting **text classification, named entity recognition, document-level Q&A (chatbot), and line-level Q&A (prompting)**.


### API Endpoints

#### `POST /api/leaderboard/add_dataset`
**Purpose**: Add a new benchmark dataset to the leaderboard.
**Input (JSON)**:
```json
{
  "name": "Financial Phrasebank - Classification Accuracy",
  "url": "https://huggingface.co/datasets/takala/financial_phrasebank",
  "task_type": "text_classification",
  "description": "A dataset for financial sentiment classification.",
  "models": [
    {
      "rank": 1,
      "model": "Gemini",
      "score": 0.95,
      "ci": "0.93 - 0.97",
      "updated": "Sep 2024"
    }
  ]
}
```
**Response**:
```json
{
  "status": "success",
  "message": "Dataset added to leaderboard.",
  "dataset_id": "uuid"
}
```

---

#### `GET /public/benchmark_csvs`
Purpose: List available CSV benchmark datasets in `frontend/public/benchmark_csvs` with inferred task types and columns.
Response:
```
{
  "success": true,
  "datasets": [ { "filename": "Commonsense.csv", "task_type": "multiple_choice", "columns": [ ... ] }, ... ]
}
```

#### `POST /public/run_csv_benchmarks`
Purpose: Evaluate one or more models across selected CSV datasets and return scores.
Input (JSON):
```
{
  "models": [
    {"name": "gpt-4o", "provider": "openai", "model": "gpt-4o-mini"},
    {"name": "llama3", "provider": "ollama", "model": "llama3:8b"},
    {"name": "echo", "provider": "echo"}
  ],
  "datasets": ["Commonsense.csv", "Covid.csv"],  // optional subset; defaults to all
  "sample_size": 25                                 // optional per dataset
}
```
Response:
```
{
  "success": true,
  "runs": [
    { "dataset": "Commonsense.csv", "task_type": "multiple_choice", "count": 25,
      "results": { "gpt-4o": {"metric": "accuracy", "score": 0.84}, "llama3": {"metric": "accuracy", "score": 0.78} } },
    { "dataset": "Covid.csv", "task_type": "text_classification", "count": 25,
      "results": { "gpt-4o": {"metric": "accuracy", "score": 0.92} } }
  ]
}
```

Notes
- Supported tasks detected from headers: multiple_choice (accuracy), text_classification (accuracy), qa (F1/EM). Others are skipped.
- Providers:
  - `openai`: uses `OPENAI_API_KEY` and optional `OPENAI_BASE_URL` for OpenAI-compatible endpoints.
  - `ollama`: uses `OLLAMA_BASE_URL` (default `http://localhost:11434`).
  - `echo`: returns a dummy output (useful for dry-runs).
  - `py`: calls a Python function from `backend/models.py` (see below).

#### Additional Public API Utilities

- `GET /api/metrics`: list metric metadata.
- `GET /api/metrics/task/<task_type>`: list recommended metrics for a task type.
- `POST /public/import_hf_dataset`: import a bounded Hugging Face split.
- `POST /api/datasets/ingest`: ingestion-compatible alias for Hugging Face imports.
- `GET /public/export/leaderboard?format=csv|json`: export leaderboard rows.

Optional write protection:
- Set `LEADERBOARD_API_KEYS=key1,key2` to require `X-API-Key` on write/evaluation endpoints.
- Set per-endpoint rate limits with values such as `SUBMIT_MODEL_RATE_LIMIT=10/minute`.
- Set `ALLOWED_ORIGINS` explicitly outside local development.

---

### Models Catalog (`backend/models.py`)
Define model wrappers that accept a `prompt` string and return a string response. Env vars supply keys; if `python-dotenv` is installed, `.env` is loaded automatically.

- Functions: `zero_shot_gpt4o`, `zero_shot_gpt4o_mini`, `zero_shot_claude`, `zero_shot_gemini`, and optional local HF models.
- Default set used when `POST /public/run_csv_benchmarks` is called without a `models` list comes from `list_models()`.
- Example `models` item for Python function provider:
```
{ "name": "gpt-4o", "provider": "py", "fn": "zero_shot_gpt4o" }
```

Env vars (.env example):
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`
- `XAI_API_KEY`


#### `POST /api/leaderboard/add_model`
**Purpose**: Add a new model submission to an existing dataset.
**Input (JSON)**:
```json
{
  "dataset_name": "Financial Phrasebank - Classification Accuracy",
  "model": "Llama3",
  "rank": 4,
  "score": 0.92,
  "ci": "0.90 - 0.94",
  "updated": "Sep 2024"
}
```
**Response**:
```json
{
  "status": "success",
  "message": "Model added to dataset on leaderboard."
}
```

---

### Supported Task Types
The API will support datasets across all current and future Anote task types:
- **Text Classification**
- **Named Entity Recognition**
- **Document-Level Q&A (Chatbot)**
- **Line-Level Q&A (Prompting)**
- *(Extensible for multimodal tasks and multilingual datasets)*

---

### 3. Example Code
Below is a **Flask implementation skeleton**:

```python
from flask import Flask, request, jsonify
import uuid

app = Flask(__name__)

leaderboard_data = []  # This would be replaced with a DB in production

@app.route('/api/leaderboard/add_dataset', methods=['POST'])
def add_dataset():
    data = request.json
    dataset_id = str(uuid.uuid4())
    data['id'] = dataset_id
    leaderboard_data.append(data)
    return jsonify({
        "status": "success",
        "message": "Dataset added to leaderboard.",
        "dataset_id": dataset_id
    })

@app.route('/api/leaderboard/add_model', methods=['POST'])
def add_model():
    data = request.json
    for dataset in leaderboard_data:
        if dataset['name'] == data['dataset_name']:
            dataset.setdefault('models', []).append({
                "rank": data["rank"],
                "model": data["model"],
                "score": data["score"],
                "ci": data["ci"],
                "updated": data["updated"]
            })
            return jsonify({
                "status": "success",
                "message": "Model added to dataset on leaderboard."
            })
    return jsonify({"status": "error", "message": "Dataset not found."}), 404

if __name__ == '__main__':
    app.run(debug=True)
```

---

### Integration with Frontend
The API will integrate with:
- **Leaderboard Page** ([https://leaderboard.anote.ai/](https://leaderboard.anote.ai/))
- **Submit to Leaderboard Page** ([https://leaderboard.anote.ai/submit](https://leaderboard.anote.ai/submit))

This allows direct testing of Flask API calls from the UI to verify real-time table updates.

---

## Quickstart (Local)

Run the backend on port 5001 and seed example data, then start the frontend.

1) Backend
- Create a virtualenv (optional) and install deps:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -r backend/requirements.txt`
- Start the API on port 5001:
  - `export PORT=5001 FLASK_ENV=development`
  - `python backend/app.py`
- Sanity check: open `http://localhost:5001/` or `http://localhost:5001/health`.

2) Seed demo data (in another terminal)
- `export LEADERBOARD_API_BASE="http://localhost:5001"`
- `python backend/examples/seed_demo.py`
- This seeds two demo submissions to the `flores_spanish_translation` dataset.

3) Frontend
- In `frontend/`: `npm install`
- Ensure the frontend points to the backend (default works):
  - `REACT_APP_API_BASE=http://localhost:5001 npm start`
- Open the Evaluations page to see demo scores populate.

4) Optional docs site
- Install MkDocs Material:
  - `pip install mkdocs-material`
- Serve the documentation:
  - `mkdocs serve`
- Open `http://127.0.0.1:8000`.

Notes
- The demo uses an in-memory store by default (no DB needed).
- If you configure MySQL and load `backend/database/schema.sql`, the API will persist to DB.
- Hugging Face imports require the optional `datasets` package:
  - `pip install datasets`

---

## Metrics and Hugging Face Imports

The API exposes metric metadata copied into this Flask app from the newer Personal implementation:

- `GET /api/metrics` lists all known metric definitions.
- `GET /api/metrics/task/<task_type>` lists recommended metrics for a task type.

You can import a bounded Hugging Face dataset split into the leaderboard:

```bash
curl -X POST http://localhost:5001/public/import_hf_dataset \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_name": "ag_news",
    "split": "test",
    "limit": 100,
    "task_type": "text_classification",
    "display_name": "AG News Test Sample"
  }'
```

Use `"preview_only": true` to inspect the converted payload without saving it. Imported datasets are stored in MySQL when configured, otherwise in the local in-memory store for development.

Leaderboard reads support pagination and dataset filtering:

```bash
curl "http://localhost:5001/public/get_leaderboard?page=1&page_size=25&dataset=AG%20News%20Test%20Sample"
```

Exports are available as JSON or CSV:

```bash
curl "http://localhost:5001/public/export/leaderboard?format=csv" -o leaderboard.csv
```

---

## Example: Programmatic Use (Python SDK)

```python
from backend.sdk.leaderboard_sdk import LeaderboardClient

client = LeaderboardClient(base_url="http://localhost:5001")

# Curated leaderboard entries (for the homepage tiles)
client.add_dataset(
    name="Financial Phrasebank - Classification Accuracy",
    task_type="text_classification",
    url="https://huggingface.co/datasets/takala/financial_phrasebank",
    description="A dataset for financial sentiment classification.",
)
client.add_model(
    dataset_name="Financial Phrasebank - Classification Accuracy",
    model="Llama3",
    rank=1,
    score=0.92,
    updated="Sep 2024",
)
print(client.list_datasets())

# Public evaluation flow (translation demo)
src = client.get_source_sentences(dataset_name="flores_spanish_translation", count=3)
sentence_ids = src["sentence_ids"]
model_results = src["source_sentences"]  # echo back for high BLEU in demo
print(client.submit_model(
    benchmark_dataset_name="flores_spanish_translation",
    model_name="my-demo-model",
    model_results=model_results,
    sentence_ids=sentence_ids,
))
print(client.get_leaderboard())
```
