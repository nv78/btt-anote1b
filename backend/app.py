import os
import csv
import io
import json
import logging
import functools
from datetime import datetime
from typing import Any, Dict, Optional
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import uuid

# ---------------------------
# Logging configuration
# ---------------------------
_LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger('leaderboard')

# Optional imports for evaluation
try:
    from nltk.translate.bleu_score import sentence_bleu
except Exception:
    sentence_bleu = None

# Optional Flask-Limiter
try:
    from flask_limiter import Limiter  # type: ignore
    from flask_limiter.util import get_remote_address  # type: ignore
    FLASK_LIMITER_AVAILABLE = True
except ImportError:
    FLASK_LIMITER_AVAILABLE = False
    logger.warning(
        "flask-limiter not installed; rate limiting will be disabled. "
        "Install with: pip install Flask-Limiter>=3.5.0"
    )


# Optional Flasgger (Swagger UI)
try:
    from flasgger import Swagger  # type: ignore
    FLASGGER_AVAILABLE = True
except ImportError:
    FLASGGER_AVAILABLE = False
    logger.warning(
        "flasgger not installed; Swagger UI will be disabled. "
        "Install with: pip install flasgger>=0.9.7"
    )

# Optional BERTScore
def _optional_bertscore(predictions, references):
    try:
        from bert_score import BERTScorer
        scorer = BERTScorer(model_type='bert-base-multilingual-cased')
        P, R, F1 = scorer.score(predictions, references)
        return float(F1.mean().item())
    except Exception:
        # Library not available; fall back to 0.0 rather than failing
        return 0.0

# Optional MySQL connection
def get_db_connection():
    try:
        import mysql.connector  # type: ignore
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'agents'),
            port=int(os.getenv('DB_PORT', '3306')),
        )
        cursor = conn.cursor(dictionary=True)
        return conn, cursor
    except Exception as e:
        # Database might not be configured in local dev. Return None to use in-memory fallback.
        logger.warning(
            "Database connection unavailable; using in-memory fallback",
            extra={"event": "db_connection_failure", "error": str(e)},
        )
        return None, None


app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
# Allow overriding CORS origins via ALLOWED_ORIGINS env (comma-separated). Defaults to permissive for local dev.
_origins = os.getenv('ALLOWED_ORIGINS')
if _origins:
    _origins_list = [o.strip() for o in _origins.split(',') if o.strip()]
else:
    _origins_list = ['*']
CORS(app, resources={r"/*": {"origins": _origins_list}})

# ---------------------------
# Rate limiting (optional)
# ---------------------------
_RATE_LIMIT_DEFAULT = os.getenv('RATE_LIMIT_DEFAULT', '200 per day, 50 per hour')
_RATE_LIMIT_SUBMIT = os.getenv('RATE_LIMIT_SUBMIT', '10 per minute')
_RATE_LIMIT_CSV_BENCH = os.getenv('RATE_LIMIT_CSV_BENCH', '5 per minute')

if FLASK_LIMITER_AVAILABLE:
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[_RATE_LIMIT_DEFAULT],
        storage_uri='memory://',
    )
else:
    # Stub limiter with a no-op limit decorator so endpoint code is identical
    class _NoOpLimiter:
        def limit(self, *args, **kwargs):
            def decorator(f):
                return f
            return decorator
    limiter = _NoOpLimiter()


# ---------------------------
# Swagger / OpenAPI docs (optional, disabled in production)
# ---------------------------
_SWAGGER_ENABLED = (
    os.getenv('FLASK_ENV', 'development') != 'production'
    or os.getenv('ENABLE_SWAGGER', '').lower() == 'true'
)

if FLASGGER_AVAILABLE and _SWAGGER_ENABLED:
    _swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "Anote Model Leaderboard API",
            "description": (
                "REST API for submitting model predictions, retrieving benchmark results, "
                "and managing datasets on the Anote Model Leaderboard."
            ),
            "version": "0.1.0",
            "contact": {"email": "support@anote.ai"},
            "license": {"name": "MIT"},
        },
        "basePath": "/",
        "schemes": ["http", "https"],
        "consumes": ["application/json"],
        "produces": ["application/json"],
        "tags": [
            {"name": "general", "description": "Health and info endpoints"},
            {"name": "leaderboard", "description": "Leaderboard retrieval and export"},
            {"name": "submissions", "description": "Model submission and evaluation"},
            {"name": "datasets", "description": "Dataset management"},
        ],
    }
    swagger = Swagger(app, template=_swagger_template)
    logger.info("Swagger UI enabled at /apidocs")

# Lazy import to avoid import-time failures if files not present
try:
    import csv_bench  # type: ignore
except Exception:
    csv_bench = None


# ---------------------------
# API key authentication
# ---------------------------
_API_KEYS_RAW = os.getenv('API_KEYS', '')
if _API_KEYS_RAW.strip():
    _VALID_API_KEYS = {k.strip() for k in _API_KEYS_RAW.split(',') if k.strip()}
    logger.info("API key authentication enabled (%d key(s) loaded)", len(_VALID_API_KEYS))
else:
    _VALID_API_KEYS = set()
    logger.warning(
        "API_KEYS env var not set; write endpoint authentication is DISABLED. "
        "Set API_KEYS=<comma-separated keys> to enable."
    )


def require_api_key(f):
    """Decorator that enforces X-API-Key header authentication on write endpoints.

    If API_KEYS env var is not configured, authentication is skipped (open dev mode).
    Returns 401 JSON when a key is missing or invalid.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not _VALID_API_KEYS:
            # Auth disabled — pass through
            return f(*args, **kwargs)
        provided_key = request.headers.get('X-API-Key', '')
        if provided_key not in _VALID_API_KEYS:
            return jsonify({"ok": False, "error": {"code": "UNAUTHORIZED", "message": "Unauthorized"}}), 401
        return f(*args, **kwargs)
    return decorated


# ---------------------------
# Input validation helpers
# ---------------------------
def validate_name(value: str, field: str, max_len: int = 200) -> str:
    """Validate a name/string field.

    Raises ValueError with a descriptive message if the value is empty,
    whitespace-only, or exceeds max_len characters.
    Returns the stripped value on success.
    """
    if not value or not str(value).strip():
        raise ValueError(f"'{field}' must not be empty or whitespace-only")
    stripped = str(value).strip()
    if len(stripped) > max_len:
        raise ValueError(f"'{field}' must not exceed {max_len} characters (got {len(stripped)})")
    return stripped


# ---------------------------
# Standard response helpers
# ---------------------------
def success_response(data):
    """Wrap data in a standard success envelope: {"ok": True, "data": ...}."""
    return jsonify({"ok": True, "data": data})


def error_response(message, code="ERROR", status=400):
    """Wrap an error in a standard envelope: {"ok": False, "error": {"code": ..., "message": ...}}."""
    return jsonify({"ok": False, "error": {"code": code, "message": message}}), status


# Root welcome endpoint for quick sanity check
@app.get('/')
def index():
    """Welcome endpoint — returns API name, version, and available routes.
    ---
    tags:
      - general
    summary: API info
    responses:
      200:
        description: API information
        schema:
          type: object
          properties:
            name:
              type: string
              example: Anote Leaderboard API
            version:
              type: string
              example: "0.1"
            endpoints:
              type: array
              items:
                type: string
            note:
              type: string
    """
    return jsonify({
        "name": "Anote Leaderboard API",
        "version": "0.1",
        "endpoints": [
            "/health",
            "/public/datasets",
            "/public/get_source_sentences",
            "/public/submit_model",
            "/public/get_leaderboard",
            "/api/leaderboard/*"
        ],
        "note": "Set PORT=5001 for local frontend integration.",
    })


# Simple health endpoint
@app.get('/health')
def health():
    """Health check endpoint.
    ---
    tags:
      - general
    summary: Health check
    responses:
      200:
        description: Service is healthy
        schema:
          type: object
          properties:
            ok:
              type: boolean
              example: true
            time:
              type: string
              format: date-time
              example: "2024-01-01T00:00:00"
    """
    return jsonify({"ok": True, "time": datetime.utcnow().isoformat()})


# ---------------------------
# Leaderboard helpers
# ---------------------------
def _get_bleu(translations, references, weights=(0.5, 0.5, 0, 0)):
    if not translations or not references or len(translations) != len(references):
        return 0.0
    if sentence_bleu is None:
        return 0.0
    try:
        scores = []
        for ref, hyp in zip(references, translations):
            ref_tokens = ref.split()
            hyp_tokens = hyp.split()
            score = sentence_bleu([ref_tokens], hyp_tokens, weights=weights)
            scores.append(score)
        return float(sum(scores) / len(scores))
    except Exception:
        return 0.0


# In-memory fallback storage when DB is not available
_STORE = {
    "submissions": [],  # {id, benchmark_dataset_name, model_name, results, created}
    "evaluations": [],  # {submission_id, score, metric, created}
    "csv_benchmark_cache": {},  # {cache_key: {result, cached_at}}
}

# CSV benchmark cache TTL in seconds (default 1 hour)
BENCHMARK_CACHE_TTL = int(os.getenv('BENCHMARK_CACHE_TTL', '3600'))

# UI-oriented datasets store (for add_dataset/add_model endpoints)
LEADERBOARD_DATA = []  # list of dicts with fields per README


# Small Spanish reference list to make BLEU behave reasonably if HF datasets are unavailable
_SPANISH_REFERENCES = [
    "Este es un ejemplo de oración para evaluación.",
    "La investigación todavía se encuentra en una etapa inicial.",
    "Como otros expertos, es escéptico sobre una cura definitiva.",
    "Actualmente tenemos resultados prometedores en nuestros estudios.",
    "El sistema se evalúa con métricas estándar de la industria."
]


@app.get('/public/get_source_sentences')
def get_source_sentences():
    """Return source sentences users should translate.

    Query params:
      - dataset_name (optional): defaults to 'flores_spanish_translation'
      - count (optional): number of sentences to return (default 3)
      - start_idx (optional): starting index in the pool (default 0)
    """
    dataset_name = request.args.get('dataset_name', 'flores_spanish_translation')
    try:
        count = int(request.args.get('count', 3))
        start_idx = int(request.args.get('start_idx', 0))
    except ValueError:
        return error_response("Invalid count or start_idx", code="INVALID_PARAM")

    # Try to pull from DB reference_data if available
    pool = None
    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute(
                "SELECT reference_data FROM benchmark_datasets WHERE name = %s AND active = TRUE",
                (dataset_name,)
            )
            row = cursor.fetchone()
            if row and row.get('reference_data'):
                try:
                    ref = json.loads(row['reference_data']) if isinstance(row['reference_data'], str) else row['reference_data']
                    if isinstance(ref, dict) and isinstance(ref.get('source_texts'), list):
                        pool = ref['source_texts']
                except Exception:
                    pool = None
        finally:
            try:
                cursor.close(); conn.close()
            except Exception:
                pass

    # If DB not available or no source_texts provided, fallback pools by dataset
    if not pool:
        if dataset_name.startswith('flores_spanish_translation'):
            pool = _SPANISH_REFERENCES
        else:
            pool = _SPANISH_REFERENCES

    if start_idx < 0:
        start_idx = 0
    end_idx = min(start_idx + count, len(pool))
    selected = pool[start_idx:end_idx]
    sentence_ids = list(range(start_idx, end_idx))

    return success_response({
        "dataset_name": dataset_name,
        "sentence_ids": sentence_ids,
        "source_sentences": selected,
        "count": len(selected),
    })


@app.get('/public/get_leaderboard')
def get_leaderboard():
    """Get leaderboard showing model submissions and scores.
    ---
    tags:
      - leaderboard
    summary: Get ranked leaderboard results
    description: >
      Returns paginated model evaluation results ordered by dataset and score.
      Uses MySQL if configured, otherwise falls back to in-memory store.
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
        description: 1-based page number
      - name: page_size
        in: query
        type: integer
        default: 25
        description: Number of results per page (max 100)
    responses:
      200:
        description: Paginated leaderboard entries
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            results:
              type: array
              items:
                type: object
                properties:
                  rank:
                    type: integer
                  model_name:
                    type: string
                  dataset_name:
                    type: string
                  task_type:
                    type: string
                  evaluation_metric:
                    type: string
                  score:
                    type: number
                    format: float
                  submitted_at:
                    type: string
                    format: date-time
            page:
              type: integer
            page_size:
              type: integer
            total:
              type: integer
    """
    page = max(1, int(request.args.get('page', 1)))
    page_size = min(100, max(1, int(request.args.get('page_size', 25))))
    offset = (page - 1) * page_size

    conn, cursor = get_db_connection()

    if conn and cursor:
        try:
            # Get total count first
            count_query = (
                "SELECT COUNT(*) AS total "
                "FROM model_submissions ms "
                "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                "WHERE bd.active = TRUE"
            )
            cursor.execute(count_query)
            total = cursor.fetchone()['total']

            query = (
                "SELECT ms.model_name, bd.name AS dataset_name, bd.task_type, bd.evaluation_metric, "
                "er.score, ms.created AS submitted_at, ms.metadata "
                "FROM model_submissions ms "
                "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                "WHERE bd.active = TRUE "
                "ORDER BY bd.name, er.score DESC "
                "LIMIT %s OFFSET %s"
            )
            cursor.execute(query, (page_size, offset))
            rows = cursor.fetchall()
            leaderboard = []
            for i, row in enumerate(rows):
                entry: Dict[str, Any] = {
                    "rank": offset + i + 1,
                    "model_name": row['model_name'],
                    "dataset_name": row['dataset_name'],
                    "task_type": row.get('task_type'),
                    "evaluation_metric": row.get('evaluation_metric'),
                    "score": float(row['score']),
                    "submitted_at": row['submitted_at'].isoformat() if row.get('submitted_at') else None,
                }
                raw_meta = row.get('metadata')
                if raw_meta is not None:
                    try:
                        entry["metadata"] = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
                    except Exception:
                        pass
                leaderboard.append(entry)
            return success_response({
                "results": leaderboard,
                "page": page,
                "page_size": page_size,
                "total": total,
            })
        except Exception as e:
            logger.error(
                "Error reading leaderboard from DB",
                extra={"event": "db_read_failure", "endpoint": "get_leaderboard", "error": str(e)},
            )
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

    # In-memory fallback
    all_entries = sorted(_STORE["evaluations"], key=lambda x: x["score"], reverse=True)
    total = len(all_entries)
    page_entries = all_entries[offset: offset + page_size]
    leaderboard = []
    for i, ev in enumerate(page_entries):
        sub = next((s for s in _STORE["submissions"] if s["id"] == ev["submission_id"]), None)
        if not sub:
            continue
        entry: Dict[str, Any] = {
            "rank": offset + i + 1,
            "model_name": sub["model_name"],
            "dataset_name": sub["benchmark_dataset_name"],
            "task_type": "translation",
            "evaluation_metric": ev["metric"],
            "score": ev["score"],
            "submitted_at": sub["created"].isoformat(),
        }
        if sub.get("metadata") is not None:
            entry["metadata"] = sub["metadata"]
        leaderboard.append(entry)
    return success_response({
        "results": leaderboard,
        "page": page,
        "page_size": page_size,
        "total": total,
    })



@app.get('/public/export/leaderboard')
def export_leaderboard():
    """Export leaderboard data as a downloadable CSV or JSON file.
    ---
    tags:
      - leaderboard
    summary: Export leaderboard data
    parameters:
      - name: dataset
        in: query
        type: string
        required: false
        description: Filter results to a specific dataset name
      - name: format
        in: query
        type: string
        enum: [json, csv]
        default: json
        description: Output format — json or csv
    produces:
      - application/json
      - text/csv
    responses:
      200:
        description: >
          Leaderboard export file. Content-Type is text/csv or application/json
          depending on the format parameter. Includes a Content-Disposition header
          to trigger a browser download.
      400:
        description: Invalid format parameter
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: false
            error:
              type: string
    """
    dataset_filter = request.args.get('dataset', '').strip()
    fmt = request.args.get('format', 'json').strip().lower()
    if fmt not in ('csv', 'json'):
        return error_response("format must be 'csv' or 'json'", code="INVALID_PARAM")

    limit = 10000  # generous cap for export
    conn, cursor = get_db_connection()
    leaderboard = []

    if conn and cursor:
        try:
            if dataset_filter:
                query = (
                    "SELECT ms.model_name, ms.submitted_by, bd.name AS dataset_name, "
                    "er.score, ms.created AS submitted_at "
                    "FROM model_submissions ms "
                    "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                    "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                    "WHERE bd.active = TRUE AND bd.name = %s "
                    "ORDER BY er.score DESC "
                    "LIMIT %s"
                )
                cursor.execute(query, (dataset_filter, limit))
            else:
                query = (
                    "SELECT ms.model_name, ms.submitted_by, bd.name AS dataset_name, "
                    "er.score, ms.created AS submitted_at "
                    "FROM model_submissions ms "
                    "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                    "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                    "WHERE bd.active = TRUE "
                    "ORDER BY bd.name, er.score DESC "
                    "LIMIT %s"
                )
                cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            rank = 1
            current_dataset = None
            for row in rows:
                ds = row['dataset_name']
                if ds != current_dataset:
                    rank = 1
                    current_dataset = ds
                leaderboard.append({
                    "rank": rank,
                    "model_name": row['model_name'],
                    "submitted_by": row.get('submitted_by') or "",
                    "score": float(row['score']),
                    "dataset_name": ds,
                    "submitted_at": row['submitted_at'].isoformat() if row.get('submitted_at') else "",
                })
                rank += 1
        except Exception as e:
            logger.error(
                "Error reading leaderboard for export",
                extra={"event": "db_read_failure", "endpoint": "export_leaderboard", "error": str(e)},
            )
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

    if not leaderboard:
        # In-memory fallback
        mem = sorted(_STORE["evaluations"], key=lambda x: x["score"], reverse=True)[:limit]
        for i, ev in enumerate(mem):
            sub = next((s for s in _STORE["submissions"] if s["id"] == ev["submission_id"]), None)
            if not sub:
                continue
            ds = sub["benchmark_dataset_name"]
            if dataset_filter and ds != dataset_filter:
                continue
            leaderboard.append({
                "rank": i + 1,
                "model_name": sub["model_name"],
                "submitted_by": sub.get("submitted_by") or "",
                "score": ev["score"],
                "dataset_name": ds,
                "submitted_at": sub["created"].isoformat(),
            })

    safe_dataset = dataset_filter.replace('/', '_').replace('\\', '_') if dataset_filter else "all"

    if fmt == 'csv':
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["rank", "model_name", "submitted_by", "score", "submitted_at"],
            extrasaction='ignore',
        )
        writer.writeheader()
        writer.writerows(leaderboard)
        csv_bytes = output.getvalue().encode('utf-8')
        return Response(
            csv_bytes,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=leaderboard-{safe_dataset}.csv',
                'Content-Length': str(len(csv_bytes)),
            },
        )

    # JSON format
    json_bytes = json.dumps(leaderboard, indent=2, default=str).encode('utf-8')
    return Response(
        json_bytes,
        mimetype='application/json',
        headers={
            'Content-Disposition': f'attachment; filename=leaderboard-{safe_dataset}.json',
            'Content-Length': str(len(json_bytes)),
        },
    )


@app.post('/public/submit_model')
@limiter.limit(_RATE_LIMIT_SUBMIT)
@require_api_key
def submit_model():
    """Submit model predictions to a benchmark dataset and receive an evaluation score.
    ---
    tags:
      - submissions
    summary: Submit model predictions for evaluation
    description: >
      Accepts model predictions alongside sentence IDs, evaluates them against
      reference data using the appropriate metric (BLEU, BERTScore, accuracy, F1),
      and persists the result to the leaderboard.
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - benchmarkDatasetName
            - modelName
            - modelResults
            - sentence_ids
          properties:
            benchmarkDatasetName:
              type: string
              example: flores_spanish_translation
              description: Name of the benchmark dataset to evaluate against
            modelName:
              type: string
              example: my-model-v1
              description: Display name for this model submission
            modelResults:
              type: array
              items:
                type: string
              example: ["Esta es una frase de ejemplo.", "La investigación está en curso."]
              description: Model predictions, one per sentence_id
            sentence_ids:
              type: array
              items:
                type: integer
              example: [0, 1]
              description: Indices of the source sentences that were translated/answered
            submittedBy:
              type: string
              example: user@example.com
              description: Optional submitter email
            metadata:
              type: object
              description: Optional extra metadata (max 4096 bytes when JSON-serialised)
    responses:
      200:
        description: Evaluation completed successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            score:
              type: number
              format: float
              example: 0.42
      400:
        description: Validation error (missing fields, length mismatch, etc.)
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: false
            error:
              type: string
      500:
        description: Evaluation failed
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: false
            error:
              type: string
    """
    data = request.get_json(silent=True) or {}
    benchmark_dataset_name = data.get('benchmarkDatasetName')
    model_name = data.get('modelName')
    model_results = data.get('modelResults')
    sentence_ids = data.get('sentence_ids')
    metadata = data.get('metadata')

    if not all([benchmark_dataset_name, model_name, isinstance(model_results, list), isinstance(sentence_ids, list)]):
        return error_response(
            "Missing required fields: benchmarkDatasetName, modelName, modelResults (list), sentence_ids (list)",
            code="MISSING_FIELDS",
        )

    # Validate optional metadata field
    if metadata is not None:
        if not isinstance(metadata, dict):
            return error_response("metadata must be a JSON object (dict)", code="INVALID_METADATA")
        try:
            metadata_json = json.dumps(metadata)
        except (TypeError, ValueError) as exc:
            return error_response(f"metadata is not JSON-serializable: {exc}", code="INVALID_METADATA")
        if len(metadata_json.encode('utf-8')) > 4096:
            return error_response("metadata exceeds maximum size of 4096 bytes", code="INVALID_METADATA")
    else:
        metadata_json = None

    try:
        benchmark_dataset_name = validate_name(benchmark_dataset_name, 'benchmarkDatasetName')
        model_name = validate_name(model_name, 'modelName')
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAM")

    if len(model_results) != len(sentence_ids):
        return error_response(
            "Length of sentence_ids must match length of modelResults",
            code="INVALID_PARAM",
        )

    # Pull dataset metadata if available
    dataset = None
    conn_meta, cursor_meta = get_db_connection()
    if conn_meta and cursor_meta:
        try:
            cursor_meta.execute(
                "SELECT id, task_type, evaluation_metric, reference_data FROM benchmark_datasets WHERE name = %s",
                (benchmark_dataset_name,)
            )
            dataset = cursor_meta.fetchone()
        finally:
            try:
                cursor_meta.close(); conn_meta.close()
            except Exception:
                pass

    task_type = None
    metric = None
    reference_sentences = None
    reference_labels = None
    reference_entities = None
    reference_answers = None
    if dataset:
        task_type = dataset.get('task_type')
        metric = dataset.get('evaluation_metric')
        try:
            rd = json.loads(dataset.get('reference_data')) if isinstance(dataset.get('reference_data'), str) else dataset.get('reference_data')
            if isinstance(rd, dict):
                if isinstance(rd.get('reference_translations'), list):
                    # map by sentence_ids
                    all_refs = rd['reference_translations']
                    reference_sentences = [all_refs[i] for i in sentence_ids if 0 <= i < len(all_refs)]
                    if len(reference_sentences) != len(sentence_ids):
                        reference_sentences = None
                if isinstance(rd.get('labels'), list):
                    all_labels = rd['labels']
                    reference_labels = [all_labels[i] for i in sentence_ids if 0 <= i < len(all_labels)]
                    if len(reference_labels) != len(sentence_ids):
                        reference_labels = None
                if isinstance(rd.get('entities'), list):
                    all_ents = rd['entities']
                    reference_entities = [all_ents[i] for i in sentence_ids if 0 <= i < len(all_ents)]
                    if len(reference_entities) != len(sentence_ids):
                        reference_entities = None
                if isinstance(rd.get('answers'), list):
                    all_ans = rd['answers']
                    reference_answers = [all_ans[i] for i in sentence_ids if 0 <= i < len(all_ans)]
                    if len(reference_answers) != len(sentence_ids):
                        reference_answers = None
        except Exception:
            pass

    # Helpers for classification
    def _accuracy(y_true, y_pred):
        if not y_true or len(y_true) != len(y_pred):
            return 0.0
        correct = sum(1 for a, b in zip(y_true, y_pred) if str(a).strip() == str(b).strip())
        return float(correct) / float(len(y_true)) if y_true else 0.0

    def _f1_macro(y_true, y_pred):
        # Simple macro-F1 without external deps
        from collections import Counter, defaultdict
        labels = set(map(str, y_true)) | set(map(str, y_pred))
        tp = Counter(); fp = Counter(); fn = Counter();
        for t, p in zip(map(str, y_true), map(str, y_pred)):
            if t == p:
                tp[t] += 1
            else:
                fp[p] += 1
                fn[t] += 1
        f1s = []
        for c in labels:
            precision = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) > 0 else 0.0
            recall = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) > 0 else 0.0
            f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            f1s.append(f1)
        return float(sum(f1s) / len(f1s)) if f1s else 0.0

    # Helpers for NER (simple entity-string macro-F1)
    def _f1_entities(ref_lists, pred_lists):
        # Each element is a list of strings. Compute micro or macro? We'll do macro over examples.
        import math
        if not ref_lists or not pred_lists or len(ref_lists) != len(pred_lists):
            return 0.0
        f1s = []
        for refs, preds in zip(ref_lists, pred_lists):
            rs = set(str(r).strip() for r in (refs or []) if str(r).strip())
            ps = set(str(p).strip() for p in (preds or []) if str(p).strip())
            tp = len(rs & ps)
            precision = tp / len(ps) if ps else 0.0
            recall = tp / len(rs) if rs else 0.0
            f1 = (2*precision*recall)/(precision+recall) if (precision+recall)>0 else 0.0
            f1s.append(f1)
        return float(sum(f1s)/len(f1s)) if f1s else 0.0

    # Helpers for QA (exact/token F1)
    def _normalize(s: str):
        import re
        return re.sub(r"\s+", " ", str(s).strip().lower())

    def _f1_tokens(a, b):
        at = _normalize(a).split()
        bt = _normalize(b).split()
        common = set(at) & set(bt)
        if not at and not bt:
            return 1.0
        if not common:
            return 0.0
        prec = len(common) / len(bt) if bt else 0.0
        rec = len(common) / len(at) if at else 0.0
        return (2*prec*rec)/(prec+rec) if (prec+rec)>0 else 0.0

    # Evaluate based on task
    try:
        tt = (task_type or '').lower()
        if tt == 'text_classification':
            if not reference_labels:
                return jsonify({"success": False, "error": "Dataset does not have reference labels"}), 400
            metric = (metric or 'accuracy').lower()
            if metric == 'f1':
                score = _f1_macro(reference_labels, model_results)
            else:
                score = _accuracy(reference_labels, model_results)
        elif tt == 'ner':
            if not reference_entities:
                return jsonify({"success": False, "error": "Dataset does not have reference entities"}), 400
            # Parse predicted entities by splitting on ';'
            pred_lists = []
            for out in model_results:
                parts = [p.strip() for p in str(out).split(';') if p and str(p).strip()]
                pred_lists.append(parts)
            score = _f1_entities(reference_entities, pred_lists)
        elif tt in ('chatbot', 'prompting', 'qa'):
            if not reference_answers:
                return jsonify({"success": False, "error": "Dataset does not have reference answers"}), 400
            metric = (metric or 'exact').lower()
            vals = []
            for ref, pred in zip(reference_answers, model_results):
                ref_s = ref if isinstance(ref, str) else (ref[0] if isinstance(ref, (list, tuple)) and ref else '')
                if metric == 'f1':
                    vals.append(_f1_tokens(ref_s, pred))
                else:
                    vals.append(1.0 if _normalize(ref_s) == _normalize(pred) else 0.0)
            score = float(sum(vals)/len(vals)) if vals else 0.0
        else:
            # translation default path
            if reference_sentences is None:
                # Choose references. For FLORES Spanish, use our local pool subset by ids.
                if benchmark_dataset_name.startswith('flores_spanish_translation'):
                    references_pool = _SPANISH_REFERENCES
                    for sid in sentence_ids:
                        if sid < 0 or sid >= len(references_pool):
                            return jsonify({
                                "success": False,
                                "error": f"sentence_id {sid} is out of range (0-{len(references_pool)-1})",
                            }), 400
                    reference_sentences = [references_pool[sid] for sid in sentence_ids]
                else:
                    reference_sentences = [
                        _SPANISH_REFERENCES[i % len(_SPANISH_REFERENCES)] for i in sentence_ids
                    ]
            metric = (metric or ('bertscore' if benchmark_dataset_name.endswith('_bertscore') else 'bleu')).lower()
            if metric == 'bleu':
                score = _get_bleu(model_results, reference_sentences)
            else:
                score = _optional_bertscore(model_results, reference_sentences)
    except Exception as e:
        logger.exception(
            "Unhandled exception during evaluation",
            extra={
                "event": "evaluation_error",
                "dataset": benchmark_dataset_name,
                "model_name": model_name,
                "error": str(e),
            },
        )
        return jsonify({"success": False, "error": "Evaluation failed"}), 500

    # Audit log: model submission received and evaluated
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    submitted_by = data.get('submittedBy') or 'public@anote.ai'
    logger.info(
        "Model submission evaluated",
        extra={
            "event": "model_submission",
            "dataset": benchmark_dataset_name,
            "model_name": model_name,
            "submitted_by": submitted_by,
            "ip": client_ip,
            "metric": metric,
            "score": round(float(score), 6),
        },
    )

    # Try to persist in DB; otherwise store in memory
    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            # Find dataset id (or create minimal if missing)
            cursor.execute(
                "SELECT id FROM benchmark_datasets WHERE name = %s",
                (benchmark_dataset_name,)
            )
            row = cursor.fetchone()
            if row:
                dataset_id = row['id']
            else:
                cursor.execute(
                    "INSERT INTO benchmark_datasets (name, task_type, evaluation_metric, reference_data, active) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (benchmark_dataset_name, 'translation', metric, json.dumps([]), True)
                )
                dataset_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO model_submissions (benchmark_dataset_id, model_name, submitted_by, model_results, metadata) "
                "VALUES (%s, %s, %s, %s, %s)",
                (dataset_id, model_name, 'public@anote.ai', json.dumps(model_results), metadata_json)
            )
            submission_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO evaluation_results (model_submission_id, score, evaluation_details) "
                "VALUES (%s, %s, %s)",
                (submission_id, float(score), json.dumps({"metric": metric}))
            )
            conn.commit()
            logger.info(
                "Evaluation result persisted to database",
                extra={
                    "event": "evaluation_completion",
                    "dataset": benchmark_dataset_name,
                    "model_name": model_name,
                    "submission_id": submission_id,
                    "metric": metric,
                    "score": round(float(score), 6),
                    "storage": "db",
                },
            )
        except Exception as e:
            logger.error(
                "DB write failed; falling back to in-memory store",
                extra={
                    "event": "db_write_failure",
                    "dataset": benchmark_dataset_name,
                    "model_name": model_name,
                    "error": str(e),
                },
            )
            submission_id = None
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass
    else:
        submission_id = None

    if submission_id is None:
        # In-memory fallback
        submission_id = len(_STORE["submissions"]) + 1
        _STORE["submissions"].append({
            "id": submission_id,
            "benchmark_dataset_name": benchmark_dataset_name,
            "model_name": model_name,
            "results": model_results,
            "metadata": metadata,
            "created": datetime.utcnow(),
        })
        _STORE["evaluations"].append({
            "submission_id": submission_id,
            "score": float(score),
            "metric": metric,
            "created": datetime.utcnow(),
        })
        logger.info(
            "Evaluation result persisted to in-memory store",
            extra={
                "event": "evaluation_completion",
                "dataset": benchmark_dataset_name,
                "model_name": model_name,
                "submission_id": submission_id,
                "metric": metric,
                "score": round(float(score), 6),
                "storage": "memory",
            },
        )

    response_data: Dict[str, Any] = {"score": float(score)}
    if metadata is not None:
        response_data["metadata"] = metadata
    return success_response(response_data)


# ---------------------------
# Public dataset management
# ---------------------------
@app.get('/public/datasets')
def list_public_datasets():
    """List active benchmark datasets with basic metadata.
    ---
    tags:
      - datasets
    summary: List benchmark datasets
    responses:
      200:
        description: List of active benchmark datasets
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            datasets:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                    example: flores_spanish_translation
                  task_type:
                    type: string
                    example: translation
                  evaluation_metric:
                    type: string
                    example: bleu
                  description:
                    type: string
                  url:
                    type: string
                  size:
                    type: integer
    """
    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute(
                "SELECT name, task_type, evaluation_metric, reference_data, created, active FROM benchmark_datasets WHERE active = TRUE ORDER BY name"
            )
            rows = cursor.fetchall()
            items = []
            for r in rows:
                extra = {}
                if r.get('reference_data'):
                    try:
                        rd = json.loads(r['reference_data']) if isinstance(r['reference_data'], str) else r['reference_data']
                        if isinstance(rd, dict):
                            # pass through selected user-facing fields if present
                            for k in ('url', 'description'):
                                if k in rd:
                                    extra[k] = rd[k]
                            if isinstance(rd.get('source_texts'), list):
                                extra['size'] = len(rd['source_texts'])
                    except Exception:
                        pass
                items.append({
                    "name": r['name'],
                    "task_type": r['task_type'],
                    "evaluation_metric": r['evaluation_metric'],
                    **extra,
                })
            return success_response({"datasets": items})
        finally:
            try:
                cursor.close(); conn.close()
            except Exception:
                pass
    # Fallback if DB not configured: include curated in-memory datasets too
    fallback = [
        {"name": "flores_spanish_translation", "task_type": "translation", "evaluation_metric": "bleu"},
        {"name": "flores_spanish_translation_bertscore", "task_type": "translation", "evaluation_metric": "bertscore"},
    ]
    for ds in LEADERBOARD_DATA:
        fallback.append({
            "name": ds.get("name"),
            "task_type": ds.get("task_type"),
            "evaluation_metric": ds.get("evaluation_metric", ""),
            "url": ds.get("url"),
            "description": ds.get("description"),
        })
    return success_response({"datasets": fallback})


@app.post('/public/add_dataset')
def add_dataset_public():
    """Create a new benchmark dataset entry.

    Expected JSON:
    {
      "name": str,
      "task_type": str,  # e.g., translation | text_classification | ner | chatbot | prompting
      "evaluation_metric": str,  # e.g., bleu | bertscore | accuracy | f1
      "reference_data": {...}  # optional; may include url, description, source_texts, reference_translations
    }
    """
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    task_type = data.get('task_type')
    evaluation_metric = data.get('evaluation_metric')
    reference_data = data.get('reference_data') or {}

    if not all([name, task_type, evaluation_metric]):
        return error_response("Missing required fields: name, task_type, evaluation_metric", code="MISSING_FIELDS")

    try:
        name = validate_name(name, 'name')
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAM")

    if not isinstance(reference_data, (dict, list)):
        return error_response("reference_data must be JSON object or array", code="INVALID_PARAM")

    conn, cursor = get_db_connection()
    if not (conn and cursor):
        # In-memory: store a shadow dataset in curated data for dev
        LEADERBOARD_DATA.append({
            "id": str(uuid.uuid4()),
            "name": name,
            "task_type": task_type,
            "description": reference_data.get('description') if isinstance(reference_data, dict) else None,
            "url": reference_data.get('url') if isinstance(reference_data, dict) else None,
            "models": [],
        })
        logger.info(
            "Dataset created (in-memory)",
            extra={"event": "dataset_creation", "name": name, "task_type": task_type, "storage": "memory"},
        )
        return success_response({"message": "Dataset added (in-memory)"})

    try:
        cursor.execute(
            "INSERT INTO benchmark_datasets (name, task_type, evaluation_metric, reference_data, active) VALUES (%s, %s, %s, %s, TRUE)",
            (name, task_type, evaluation_metric, json.dumps(reference_data))
        )
        conn.commit()
        logger.info(
            "Dataset created",
            extra={"event": "dataset_creation", "name": name, "task_type": task_type, "evaluation_metric": evaluation_metric, "storage": "db"},
        )
        return success_response({"message": "Dataset added"})
    except Exception as e:
        if 'Duplicate' in str(e) or 'UNIQUE' in str(e):
            return error_response("Dataset with this name already exists", code="DUPLICATE")
        logger.error(
            "Failed to add dataset to DB",
            extra={"event": "db_write_failure", "endpoint": "add_dataset_public", "name": name, "error": str(e)},
        )
        return error_response("Failed to add dataset", code="DB_ERROR", status=500)
    finally:
        try:
            cursor.close(); conn.close()
        except Exception:
            pass


@app.get('/public/dataset_details')
def dataset_details():
    """Return detailed information about a dataset, including curation meta and top models."""
    name = request.args.get('name')
    if not name:
        return error_response("Missing name", code="MISSING_FIELDS")

    # Try DB first
    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute("SELECT id, name, task_type, evaluation_metric, reference_data, created, active FROM benchmark_datasets WHERE name = %s", (name,))
            ds = cursor.fetchone()
            if not ds:
                return error_response("Dataset not found", code="NOT_FOUND", status=404)
            meta = {}
            examples = []
            count = None
            try:
                rd = json.loads(ds['reference_data']) if isinstance(ds['reference_data'], str) else ds['reference_data']
                if isinstance(rd, dict):
                    meta['url'] = rd.get('url')
                    meta['description'] = rd.get('description')
                    if isinstance(rd.get('source_texts'), list):
                        examples = rd['source_texts'][:5]
                        count = len(rd['source_texts'])
            except Exception:
                pass

            # Top models for this dataset
            cursor.execute(
                "SELECT ms.model_name, er.score, ms.created as submitted_at "
                "FROM model_submissions ms JOIN evaluation_results er ON er.model_submission_id = ms.id "
                "WHERE ms.benchmark_dataset_id = %s ORDER BY er.score DESC LIMIT 10",
                (ds['id'],)
            )
            rows = cursor.fetchall()
            top_models = [
                {
                    "model": r['model_name'],
                    "score": float(r['score']),
                    "updated": r['submitted_at'].isoformat() if r.get('submitted_at') else None
                } for r in rows
            ]
            return success_response({
                "dataset": {
                    "name": ds['name'],
                    "task_type": ds['task_type'],
                    "evaluation_metric": ds['evaluation_metric'],
                    **meta,
                    "size": count,
                    "examples": examples,
                },
                "top_models": top_models,
            })
        finally:
            try:
                cursor.close(); conn.close()
            except Exception:
                pass

    # Fallback: find in curated list and memory submissions
    matched = next((d for d in LEADERBOARD_DATA if d.get('name') == name), None)
    if not matched and name.startswith('flores_spanish_translation'):
        matched = {"name": name, "task_type": "translation", "evaluation_metric": "bleu", "description": "FLORES-style demo", "url": None}
    if not matched:
        return error_response("Dataset not found", code="NOT_FOUND", status=404)
    # Gather top models from memory store
    mem = []
    for ev in _STORE['evaluations']:
        sub = next((s for s in _STORE['submissions'] if s['id'] == ev['submission_id']), None)
        if sub and sub['benchmark_dataset_name'] == name:
            mem.append({"model": sub['model_name'], "score": ev['score'], "updated": sub['created'].isoformat()})
    mem.sort(key=lambda x: x['score'], reverse=True)
    examples = _SPANISH_REFERENCES[:5]
    return success_response({
        "dataset": {
            "name": matched.get('name'),
            "task_type": matched.get('task_type', 'translation'),
            "evaluation_metric": matched.get('evaluation_metric', 'bleu'),
            "url": matched.get('url'),
            "description": matched.get('description'),
            "size": None,
            "examples": examples,
        },
        "top_models": mem[:10],
    })


# ---------------------------
# Leaderboard UI API (per README)
# ---------------------------
@app.post('/api/leaderboard/add_dataset')
@require_api_key
def add_dataset():
    data = request.get_json(silent=True) or {}
    required = ["name", "task_type"]
    missing = [k for k in required if k not in data]
    if missing:
        return error_response(f"Missing required fields: {', '.join(missing)}", code="MISSING_FIELDS")
    try:
        dataset_name_val = validate_name(data["name"], 'name')
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAM")
    dataset_id = str(uuid.uuid4())
    new_ds = {
        "id": dataset_id,
        "name": dataset_name_val,
        "url": data.get("url"),
        "task_type": data["task_type"],
        "description": data.get("description"),
        "models": data.get("models", []),
    }
    LEADERBOARD_DATA.append(new_ds)
    logger.info(
        "Dataset added to leaderboard (in-memory)",
        extra={"event": "dataset_creation", "name": dataset_name_val, "task_type": data["task_type"], "dataset_id": dataset_id, "storage": "memory"},
    )
    return success_response({
        "message": "Dataset added to leaderboard.",
        "dataset_id": dataset_id,
    })


@app.post('/api/leaderboard/add_model')
@require_api_key
def add_model():
    data = request.get_json(silent=True) or {}
    required = ["dataset_name", "model", "rank", "score", "updated"]
    missing = [k for k in required if k not in data]
    if missing:
        return error_response(f"Missing required fields: {', '.join(missing)}", code="MISSING_FIELDS")
    try:
        dataset_name_val = validate_name(data["dataset_name"], 'dataset_name')
        model_name_val = validate_name(data["model"], 'model')
    except ValueError as exc:
        return error_response(str(exc), code="INVALID_PARAM")
    for ds in LEADERBOARD_DATA:
        if ds.get("name") == dataset_name_val:
            ds.setdefault("models", []).append({
                "rank": data["rank"],
                "model": model_name_val,
                "score": data["score"],
                "ci": data.get("ci"),
                "updated": data["updated"],
            })
            # keep models sorted by rank
            ds["models"].sort(key=lambda m: (m.get("rank") is None, m.get("rank")))
            return success_response({"message": "Model added to dataset on leaderboard."})
    return error_response("Dataset not found.", code="NOT_FOUND", status=404)


@app.get('/api/leaderboard/list')
def list_leaderboard_datasets():
    """Return the curated leaderboard datasets and their models (in-memory).

    Response:
    {
      "status": "success",
      "datasets": [ { id, name, url, task_type, description, models: [...] }, ... ]
    }
    """
    return success_response({"datasets": LEADERBOARD_DATA})



# ---------------------------
# Dataset ingestion pipeline
# ---------------------------
@app.post('/api/datasets/ingest')
@require_api_key
def ingest_dataset():
    """Ingest a dataset from an external source and store it as a benchmark dataset.

    Accepted JSON body:

      source: "huggingface" or "http_api" (required)

      HuggingFace keys: dataset_id, config_name (opt), split (opt, default "test"),
        max_samples (opt, default 500), input_field, reference_field, task_type (opt)

      HTTP API keys: url, auth_header (opt), input_field, reference_field,
        max_samples (opt), data_key (opt), task_type (opt)

      Shared optional keys: name (override dataset name), evaluation_metric (default "bleu")

    Returns the created dataset record on success (HTTP 201).
    """
    data = request.get_json(silent=True) or {}
    source = data.get("source", "").strip().lower()

    if source not in ("huggingface", "http_api"):
        return error_response("Field 'source' must be 'huggingface' or 'http_api'", code="INVALID_PARAM")

    # Lazy import — keeps the ingestion package optional at startup
    try:
        if source == "huggingface":
            from ingestion.huggingface import HuggingFaceIngestor  # type: ignore
            ingestor = HuggingFaceIngestor()
        else:
            from ingestion.http_api import HttpApiIngestor  # type: ignore
            ingestor = HttpApiIngestor()
    except ImportError as exc:
        logger.error(
            "Ingestion module import failed",
            extra={"event": "ingest_import_error", "source": source, "error": str(exc)},
        )
        return error_response(str(exc), code="MODULE_UNAVAILABLE", status=500)

    try:
        record = ingestor.ingest(data)
    except (KeyError, ValueError) as exc:
        logger.warning(
            "Ingestion config error",
            extra={"event": "ingest_config_error", "source": source, "error": str(exc)},
        )
        return error_response(str(exc), code="INVALID_PARAM")
    except Exception as exc:
        logger.exception(
            "Ingestion failed",
            extra={"event": "ingest_error", "source": source, "error": str(exc)},
        )
        return error_response(f"Ingestion failed: {exc}", code="INGEST_ERROR", status=500)

    # Build reference_data payload compatible with existing dataset schema
    source_texts = [s["input"] for s in record.samples]
    reference_translations = [s["reference"] for s in record.samples]
    reference_data: Dict[str, Any] = {
        "source_texts": source_texts,
        "reference_translations": reference_translations,
        "url": record.source_url,
        "description": record.metadata.get("description"),
        **{k: v for k, v in record.metadata.items() if k != "description"},
    }

    evaluation_metric = data.get("evaluation_metric", "bleu")

    # Persist to DB if available; otherwise fall back to in-memory store
    conn, cursor = get_db_connection()
    dataset_id_val: Optional[str] = None
    if conn and cursor:
        try:
            cursor.execute(
                "INSERT INTO benchmark_datasets "
                "(name, task_type, evaluation_metric, reference_data, active) "
                "VALUES (%s, %s, %s, %s, TRUE)",
                (record.name, record.task_type, evaluation_metric, json.dumps(reference_data)),
            )
            conn.commit()
            dataset_id_val = str(cursor.lastrowid)
            logger.info(
                "Ingested dataset persisted to database",
                extra={
                    "event": "ingest_complete",
                    "name": record.name,
                    "task_type": record.task_type,
                    "sample_count": len(record.samples),
                    "storage": "db",
                },
            )
        except Exception as exc:
            if "Duplicate" in str(exc) or "UNIQUE" in str(exc):
                return error_response(f"Dataset '{record.name}' already exists", code="DUPLICATE")
            logger.error(
                "DB write failed during ingestion; falling back to in-memory",
                extra={
                    "event": "db_write_failure",
                    "endpoint": "ingest_dataset",
                    "error": str(exc),
                },
            )
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

    if dataset_id_val is None:
        # In-memory fallback
        dataset_id_val = str(uuid.uuid4())
        LEADERBOARD_DATA.append({
            "id": dataset_id_val,
            "name": record.name,
            "task_type": record.task_type,
            "evaluation_metric": evaluation_metric,
            "description": record.metadata.get("description"),
            "url": record.source_url,
            "models": [],
        })
        logger.info(
            "Ingested dataset persisted to in-memory store",
            extra={
                "event": "ingest_complete",
                "name": record.name,
                "task_type": record.task_type,
                "sample_count": len(record.samples),
                "storage": "memory",
            },
        )

    return success_response({
        "dataset": {
            "id": dataset_id_val,
            "name": record.name,
            "task_type": record.task_type,
            "split": record.split,
            "evaluation_metric": evaluation_metric,
            "sample_count": len(record.samples),
            "source_url": record.source_url,
            "metadata": record.metadata,
        },
    }), 201


# ---------------------------
# CSV Benchmarks (benchmark_csvs folder)
# ---------------------------
@app.get('/public/benchmark_csvs')
def list_benchmark_csvs():
    if not csv_bench:
        return error_response("CSV benchmark module unavailable", code="MODULE_UNAVAILABLE", status=500)
    items = csv_bench.list_csv_datasets()
    # Only return filename and inferred task for brevity
    return success_response({
        "datasets": [
            {"filename": it["filename"], "task_type": it["task_type"], "columns": it.get("columns")}
            for it in items
        ]
    })


@app.get('/public/benchmark_models')
def list_benchmark_models():
    try:
        import models as _mdl  # type: ignore
        models = _mdl.list_models()
        return jsonify({"success": True, "models": models})
    except Exception as e:
        logger.error(
            "Failed to retrieve model list",
            extra={"event": "unhandled_exception", "endpoint": "list_benchmark_models", "error": str(e)},
        )
        return jsonify({"success": False, "error": "Model list unavailable"}), 500


@app.post('/public/run_csv_benchmarks')
@limiter.limit(_RATE_LIMIT_CSV_BENCH)
@require_api_key
def run_csv_benchmarks():
    """Run evaluations over CSV datasets using provided model configs.

    Body JSON:
      {
        "models": [
          {"name": "gpt-4o", "provider": "openai", "model": "gpt-4o-mini"},
          {"name": "llama3", "provider": "ollama", "model": "llama3:8b"},
          {"name": "echo", "provider": "echo"}
        ],
        "datasets": ["Commonsense.csv", ...],  # optional subset
        "sample_size": 25                         # optional per dataset
      }
    """
    if not csv_bench:
        return jsonify({"success": False, "error": "CSV benchmark module unavailable"}), 500
    data = request.get_json(silent=True) or {}
    models = data.get('models') or []
    datasets = data.get('datasets')
    sample_size = int(data.get('sample_size', 25))
    if not isinstance(models, list) or not models:
        # If no models provided, try backend/models.py list_models()
        try:
            import models as _mdl  # type: ignore
            models = _mdl.list_models()
        except Exception:
            return jsonify({"success": False, "error": "Missing models list"}), 400

    # Check cache for a single dataset + single model request
    force_refresh = bool(data.get('force_refresh', False))
    if not force_refresh and datasets and len(datasets) == 1 and len(models) == 1:
        model_name_key = models[0].get('name') or models[0].get('model') or 'model'
        cache_key = f"{datasets[0]}:{model_name_key}"
        cached = _STORE["csv_benchmark_cache"].get(cache_key)
        if cached:
            age = (datetime.utcnow() - cached["cached_at"]).total_seconds()
            if age < BENCHMARK_CACHE_TTL:
                return jsonify({"success": True, "cached": True, "cached_at": cached["cached_at"].isoformat(), **cached["result"]})

    try:
        summary = csv_bench.run_benchmarks(models=models, datasets=datasets, sample_size=sample_size)

        # Persist each (dataset, model) result to the in-memory cache
        for run in summary.get("runs", []):
            dataset_filename = run.get("dataset")
            for model_key in run.get("results", {}):
                cache_key = f"{dataset_filename}:{model_key}"
                _STORE["csv_benchmark_cache"][cache_key] = {
                    "result": {"runs": [run]},
                    "cached_at": datetime.utcnow(),
                }

        return jsonify({"success": True, "cached": False, **summary})
    except Exception as e:
        logger.exception(
            "CSV benchmarks run failed",
            extra={"event": "unhandled_exception", "endpoint": "run_csv_benchmarks", "error": str(e)},
        )
        return jsonify({"success": False, "error": "Failed to run benchmarks"}), 500


@app.get('/public/csv_benchmark_results')
def get_csv_benchmark_results():
    """Return cached CSV benchmark results for a given dataset and model.

    Query parameters:
      dataset  - CSV filename (e.g. ``Commonsense.csv``)
      model    - model name used in the benchmark run
    """
    dataset = request.args.get('dataset', '').strip()
    model = request.args.get('model', '').strip()
    if not dataset or not model:
        return jsonify({"success": False, "error": "Both 'dataset' and 'model' query parameters are required"}), 400

    cache_key = f"{dataset}:{model}"
    cached = _STORE["csv_benchmark_cache"].get(cache_key)
    if not cached:
        return jsonify({"success": False, "error": "No cached results found for the given dataset and model"}), 404

    age = (datetime.utcnow() - cached["cached_at"]).total_seconds()
    expired = age >= BENCHMARK_CACHE_TTL
    return jsonify({
        "success": True,
        "cached": True,
        "cached_at": cached["cached_at"].isoformat(),
        "expired": expired,
        "ttl_seconds": BENCHMARK_CACHE_TTL,
        "age_seconds": int(age),
        **cached["result"],
    })


if __name__ == '__main__':
    port = int(os.getenv('PORT', '5000'))
    # When running via Docker-compose, external is 5001 -> container 5000
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_ENV') == 'development')
