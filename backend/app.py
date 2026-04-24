import os
import json
import csv
import logging
import re
from collections import defaultdict, deque
from datetime import datetime, timezone
from functools import wraps
from io import StringIO
from time import time

from flask import Flask, Response, request, jsonify
from flask_cors import CORS
import uuid

# Optional imports for evaluation
try:
    from nltk.translate.bleu_score import sentence_bleu
except Exception:
    sentence_bleu = None

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
        logger.warning("db_connection_unavailable", extra={"error": str(e)})
        return None, None


app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("leaderboard")

# Allow overriding CORS origins via ALLOWED_ORIGINS env (comma-separated).
_flask_env = os.getenv("FLASK_ENV", "development").lower()
_origins = os.getenv("ALLOWED_ORIGINS")
if _origins:
    _origins_list = [origin.strip() for origin in _origins.split(",") if origin.strip()]
elif _flask_env == "development":
    _origins_list = ["http://localhost:3000", "http://127.0.0.1:3000"]
else:
    raise RuntimeError("ALLOWED_ORIGINS must be set outside development")
CORS(app, resources={r"/*": {"origins": _origins_list}})


@app.after_request
def add_compatible_response_envelope(response):
    """Add `ok` without removing legacy `success`/`status` fields."""
    if response.mimetype != "application/json":
        return response
    try:
        payload = response.get_json(silent=True)
    except Exception:
        return response
    if not isinstance(payload, dict) or "ok" in payload:
        return response
    if "success" in payload:
        payload["ok"] = bool(payload["success"])
    elif payload.get("status") == "success":
        payload["ok"] = True
    elif payload.get("status") == "error" or "error" in payload:
        payload["ok"] = False
    else:
        payload["ok"] = 200 <= response.status_code < 400
    response.set_data(json.dumps(payload))
    response.content_length = len(response.get_data())
    return response


def utc_now():
    return datetime.now(timezone.utc)


def validate_text(value, field, max_len=200):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} cannot be empty")
    value = value.strip()
    if len(value) > max_len:
        raise ValueError(f"{field} exceeds {max_len} characters")
    return value


def validate_metadata(value):
    if value in (None, ""):
        return None
    if not isinstance(value, dict):
        raise ValueError("metadata must be a JSON object")
    encoded = json.dumps(value)
    if len(encoded.encode("utf-8")) > 4096:
        raise ValueError("metadata exceeds 4 KB")
    return value


def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        configured = [key.strip() for key in os.getenv("LEADERBOARD_API_KEYS", "").split(",") if key.strip()]
        require_key = os.getenv("REQUIRE_API_KEY", "").lower() in {"1", "true", "yes"} or bool(configured)
        if not require_key:
            return fn(*args, **kwargs)
        supplied = request.headers.get("X-API-Key", "")
        if supplied not in configured:
            logger.warning("unauthorized_write", extra={"endpoint": request.path, "ip": request.remote_addr})
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return fn(*args, **kwargs)

    return wrapper


_RATE_WINDOWS = defaultdict(deque)


def rate_limit(env_name, default_limit):
    """Small in-process limiter for write/evaluation endpoints.

    Format: count/minute, for example 10/minute. Set DISABLE_RATE_LIMIT=1 to bypass.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if os.getenv("DISABLE_RATE_LIMIT", "").lower() in {"1", "true", "yes"}:
                return fn(*args, **kwargs)
            raw_limit = os.getenv(env_name, default_limit)
            match = re.match(r"^(\d+)/minute$", raw_limit)
            if not match:
                return fn(*args, **kwargs)
            max_calls = int(match.group(1))
            now = time()
            key = (request.remote_addr or "unknown", request.path)
            window = _RATE_WINDOWS[key]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= max_calls:
                return jsonify({"success": False, "error": "Rate limit exceeded"}), 429
            window.append(now)
            return fn(*args, **kwargs)

        return wrapper

    return decorator

# Lazy import to avoid import-time failures if files not present
try:
    import csv_bench  # type: ignore
except Exception:
    csv_bench = None

try:
    from metrics_info import METRICS_CATALOG, metrics_for_task  # type: ignore
except Exception:
    try:
        from backend.metrics_info import METRICS_CATALOG, metrics_for_task  # type: ignore
    except Exception:
        METRICS_CATALOG = {}

        def metrics_for_task(_task_type):
            return {}


# Root welcome endpoint for quick sanity check
@app.get('/')
def index():
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
    return jsonify({"ok": True, "time": utc_now().isoformat()})


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
    "datasets": [],  # {name, task_type, evaluation_metric, reference_data}
}

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
        return jsonify({"success": False, "error": "Invalid count or start_idx"}), 400

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
                cursor.close()
                conn.close()
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

    return jsonify({
        "success": True,
        "dataset_name": dataset_name,
        "sentence_ids": sentence_ids,
        "source_sentences": selected,
        "count": len(selected),
    })


@app.get('/public/get_leaderboard')
def get_leaderboard():
    """Get leaderboard showing model submissions and scores.
    Supports DB if configured, otherwise returns in-memory results.
    """
    dataset_filter = request.args.get("dataset")
    page = max(1, int(request.args.get("page", 1)))
    page_size = min(100, max(1, int(request.args.get("page_size", request.args.get("limit", 25)))))
    offset = (page - 1) * page_size
    conn, cursor = get_db_connection()

    if conn and cursor:
        try:
            where = "WHERE bd.active = TRUE"
            params = []
            if dataset_filter:
                where += " AND bd.name = %s"
                params.append(dataset_filter)

            count_query = (
                "SELECT COUNT(*) AS total "
                "FROM model_submissions ms "
                "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                f"{where}"
            )
            cursor.execute(count_query, tuple(params))
            total_row = cursor.fetchone() or {}
            total = int(total_row.get("total", 0))

            query = (
                "SELECT ms.model_name, bd.name AS dataset_name, bd.task_type, bd.evaluation_metric, "
                "er.score, er.evaluation_details, ms.created AS submitted_at, "
                "ms.submitted_by, ms.model_results "
                "FROM model_submissions ms "
                "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                f"{where} "
                "ORDER BY bd.name, er.score DESC "
                "LIMIT %s OFFSET %s"
            )
            cursor.execute(query, tuple(params + [page_size, offset]))
            rows = cursor.fetchall()
            leaderboard = []
            for i, row in enumerate(rows, start=offset):
                details = {}
                if row.get("evaluation_details"):
                    try:
                        details = json.loads(row["evaluation_details"]) if isinstance(row["evaluation_details"], str) else row["evaluation_details"]
                    except Exception:
                        details = {}
                leaderboard.append({
                    "rank": i + 1,
                    "model_name": row['model_name'],
                    "dataset_name": row['dataset_name'],
                    "task_type": row.get('task_type'),
                    "evaluation_metric": row.get('evaluation_metric'),
                    "score": float(row['score']),
                    "submitted_by": row.get("submitted_by"),
                    "metadata": details.get("metadata") if isinstance(details, dict) else None,
                    "submitted_at": row['submitted_at'].isoformat() if row.get('submitted_at') else None,
                })
            return jsonify({
                "success": True,
                "leaderboard": leaderboard,
                "page": page,
                "page_size": page_size,
                "total": total,
            })
        except Exception as e:
            logger.exception("leaderboard_db_read_failed", extra={"error": str(e)})
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

    # In-memory fallback
    mem_all = []
    for ev in _STORE["evaluations"]:
        sub = next((s for s in _STORE["submissions"] if s["id"] == ev["submission_id"]), None)
        if not sub:
            continue
        if dataset_filter and sub["benchmark_dataset_name"] != dataset_filter:
            continue
        mem_all.append((ev, sub))
    mem_all.sort(key=lambda x: x[0]["score"], reverse=True)
    total = len(mem_all)
    mem = mem_all[offset:offset + page_size]
    leaderboard = []
    for i, (ev, sub) in enumerate(mem, start=offset):
        leaderboard.append({
            "rank": i + 1,
            "model_name": sub["model_name"],
            "dataset_name": sub["benchmark_dataset_name"],
            "task_type": "translation",
            "evaluation_metric": ev["metric"],
            "score": ev["score"],
            "submitted_by": sub.get("submitted_by"),
            "metadata": sub.get("metadata"),
            "submitted_at": sub["created"].isoformat(),
        })
    return jsonify({
        "success": True,
        "leaderboard": leaderboard,
        "page": page,
        "page_size": page_size,
        "total": total,
    })


@app.post('/public/submit_model')
@rate_limit("SUBMIT_MODEL_RATE_LIMIT", "10/minute")
@require_api_key
def submit_model():
    """Submit model results to a benchmark dataset and compute evaluation.

    Expected JSON:
    {
      "benchmarkDatasetName": "flores_spanish_translation",
      "modelName": "my-model-v1",
      "modelResults": ["Traducción 1", ...],
      "sentence_ids": [0, 1, 2]
    }
    """
    data = request.get_json(silent=True) or {}
    try:
        benchmark_dataset_name = validate_text(data.get('benchmarkDatasetName'), "benchmarkDatasetName")
        model_name = validate_text(data.get('modelName'), "modelName")
        submitted_by = validate_text(data.get("submittedBy", "public@anote.ai"), "submittedBy", 255)
        metadata = validate_metadata(data.get("metadata"))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    model_results = data.get('modelResults')
    sentence_ids = data.get('sentence_ids')

    if not all([isinstance(model_results, list), isinstance(sentence_ids, list)]):
        return jsonify({
            "success": False,
            "error": "Missing required fields: benchmarkDatasetName, modelName, modelResults (list), sentence_ids (list)",
        }), 400

    if len(model_results) != len(sentence_ids):
        return jsonify({
            "success": False,
            "error": "Length of sentence_ids must match length of modelResults",
        }), 400

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
                cursor_meta.close()
                conn_meta.close()
            except Exception:
                pass

    if not dataset:
        dataset = next((d for d in _STORE["datasets"] if d.get("name") == benchmark_dataset_name), None)

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
        from collections import Counter
        labels = set(map(str, y_true)) | set(map(str, y_pred))
        tp = Counter()
        fp = Counter()
        fn = Counter()
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
        elif tt in ('chatbot', 'prompting', 'qa', 'document_qa', 'line_qa'):
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
        print(f"Evaluation failed: {e}")
        return jsonify({"success": False, "error": "Evaluation failed"}), 500

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
                "INSERT INTO model_submissions (benchmark_dataset_id, model_name, submitted_by, model_results) "
                "VALUES (%s, %s, %s, %s)",
                (dataset_id, model_name, submitted_by, json.dumps(model_results))
            )
            submission_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO evaluation_results (model_submission_id, score, evaluation_details) "
                "VALUES (%s, %s, %s)",
                (submission_id, float(score), json.dumps({"metric": metric, "metadata": metadata}))
            )
            conn.commit()
        except Exception as e:
            print(f"DB write failed, storing in memory instead: {e}")
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
            "submitted_by": submitted_by,
            "metadata": metadata,
            "results": model_results,
            "created": utc_now(),
        })
        _STORE["evaluations"].append({
            "submission_id": submission_id,
            "score": float(score),
            "metric": metric,
            "created": utc_now(),
        })

    logger.info(
        "model_submitted",
        extra={"dataset": benchmark_dataset_name, "model": model_name, "score": float(score)},
    )
    return jsonify({"success": True, "score": float(score)})


# ---------------------------
# Public dataset management
# ---------------------------
@app.get('/public/datasets')
def list_public_datasets():
    """List active benchmark datasets with basic metadata."""
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
            return jsonify({"success": True, "datasets": items})
        finally:
            try:
                cursor.close()
                conn.close()
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
    for ds in _STORE["datasets"]:
        rd = ds.get("reference_data") if isinstance(ds.get("reference_data"), dict) else {}
        fallback.append({
            "name": ds.get("name"),
            "task_type": ds.get("task_type"),
            "evaluation_metric": ds.get("evaluation_metric", ""),
            "url": rd.get("url"),
            "description": rd.get("description"),
            "size": len(rd.get("source_texts", [])) if isinstance(rd.get("source_texts"), list) else None,
        })
    return jsonify({"success": True, "datasets": fallback})


@app.post('/public/add_dataset')
@rate_limit("ADD_DATASET_RATE_LIMIT", "5/minute")
@require_api_key
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
    try:
        name = validate_text(data.get('name'), "name")
        task_type = validate_text(data.get('task_type'), "task_type", 100)
        evaluation_metric = validate_text(data.get('evaluation_metric'), "evaluation_metric", 100)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    reference_data = data.get('reference_data') or {}

    if not isinstance(reference_data, (dict, list)):
        return jsonify({"success": False, "error": "reference_data must be JSON object or array"}), 400

    conn, cursor = get_db_connection()
    if not (conn and cursor):
        # In-memory: store a shadow dataset in curated data for dev
        existing = next((d for d in _STORE["datasets"] if d.get("name") == name), None)
        if existing:
            return jsonify({"success": False, "error": "Dataset with this name already exists"}), 400
        _STORE["datasets"].append({
            "name": name,
            "task_type": task_type,
            "evaluation_metric": evaluation_metric,
            "reference_data": reference_data,
        })
        LEADERBOARD_DATA.append({
            "id": str(uuid.uuid4()),
            "name": name,
            "task_type": task_type,
            "description": reference_data.get('description') if isinstance(reference_data, dict) else None,
            "url": reference_data.get('url') if isinstance(reference_data, dict) else None,
            "models": [],
        })
        logger.info("dataset_added_memory", extra={"dataset": name, "task_type": task_type})
        return jsonify({"success": True, "message": "Dataset added (in-memory)"})

    try:
        cursor.execute(
            "INSERT INTO benchmark_datasets (name, task_type, evaluation_metric, reference_data, active) VALUES (%s, %s, %s, %s, TRUE)",
            (name, task_type, evaluation_metric, json.dumps(reference_data))
        )
        conn.commit()
        logger.info("dataset_added", extra={"dataset": name, "task_type": task_type})
        return jsonify({"success": True, "message": "Dataset added"})
    except Exception as e:
        if 'Duplicate' in str(e) or 'UNIQUE' in str(e):
            return jsonify({"success": False, "error": "Dataset with this name already exists"}), 400
        print(f"add_dataset_public error: {e}")
        return jsonify({"success": False, "error": "Failed to add dataset"}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


@app.get('/public/dataset_details')
def dataset_details():
    """Return detailed information about a dataset, including curation meta and top models."""
    name = request.args.get('name')
    if not name:
        return jsonify({"success": False, "error": "Missing name"}), 400

    # Try DB first
    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute("SELECT id, name, task_type, evaluation_metric, reference_data, created, active FROM benchmark_datasets WHERE name = %s", (name,))
            ds = cursor.fetchone()
            if not ds:
                return jsonify({"success": False, "error": "Dataset not found"}), 404
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
            return jsonify({
                "success": True,
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
                cursor.close()
                conn.close()
            except Exception:
                pass

    # Fallback: find in curated list and memory submissions
    matched = next((d for d in LEADERBOARD_DATA if d.get('name') == name), None)
    stored = next((d for d in _STORE["datasets"] if d.get("name") == name), None)
    if stored:
        rd = stored.get("reference_data") if isinstance(stored.get("reference_data"), dict) else {}
        matched = {
            "name": stored.get("name"),
            "task_type": stored.get("task_type"),
            "evaluation_metric": stored.get("evaluation_metric"),
            "url": rd.get("url"),
            "description": rd.get("description"),
            "size": len(rd.get("source_texts", [])) if isinstance(rd.get("source_texts"), list) else None,
            "examples": rd.get("source_texts", [])[:5] if isinstance(rd.get("source_texts"), list) else [],
        }
    if not matched and name.startswith('flores_spanish_translation'):
        matched = {"name": name, "task_type": "translation", "evaluation_metric": "bleu", "description": "FLORES-style demo", "url": None}
    if not matched:
        return jsonify({"success": False, "error": "Dataset not found"}), 404
    # Gather top models from memory store
    mem = []
    for ev in _STORE['evaluations']:
        sub = next((s for s in _STORE['submissions'] if s['id'] == ev['submission_id']), None)
        if sub and sub['benchmark_dataset_name'] == name:
            mem.append({"model": sub['model_name'], "score": ev['score'], "updated": sub['created'].isoformat()})
    mem.sort(key=lambda x: x['score'], reverse=True)
    examples = matched.get("examples") or _SPANISH_REFERENCES[:5]
    return jsonify({
        "success": True,
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


@app.get('/api/metrics')
def list_metrics():
    """Return metric metadata for UI help text and docs clients."""
    return jsonify({"success": True, "metrics": METRICS_CATALOG})


@app.get('/api/metrics/task/<task_type>')
def list_task_metrics(task_type):
    """Return recommended metrics for a specific task type."""
    return jsonify({"success": True, "task_type": task_type, "metrics": metrics_for_task(task_type)})


@app.get('/openapi.json')
def openapi_spec():
    """Small OpenAPI document for public integration endpoints."""
    return jsonify({
        "openapi": "3.0.3",
        "info": {"title": "Anote Leaderboard API", "version": "0.2.0"},
        "paths": {
            "/public/datasets": {"get": {"summary": "List public datasets"}},
            "/public/add_dataset": {"post": {"summary": "Create a public dataset"}},
            "/public/import_hf_dataset": {"post": {"summary": "Import a Hugging Face dataset split"}},
            "/api/datasets/ingest": {"post": {"summary": "Ingest a dataset from a configured source"}},
            "/public/submit_model": {"post": {"summary": "Submit model outputs for evaluation"}},
            "/public/get_leaderboard": {
                "get": {
                    "summary": "Get leaderboard rows",
                    "parameters": [
                        {"name": "dataset", "in": "query", "schema": {"type": "string"}},
                        {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                        {"name": "page_size", "in": "query", "schema": {"type": "integer", "default": 25}},
                    ],
                }
            },
            "/public/export/leaderboard": {"get": {"summary": "Export leaderboard rows as CSV or JSON"}},
            "/api/metrics": {"get": {"summary": "List metric metadata"}},
            "/api/metrics/task/{task_type}": {"get": {"summary": "List metrics for a task type"}},
        },
    })


@app.post('/public/import_hf_dataset')
@rate_limit("IMPORT_DATASET_RATE_LIMIT", "5/minute")
@require_api_key
def import_hf_dataset_public():
    """Import a bounded Hugging Face dataset split into benchmark_datasets/reference_data."""
    data = request.get_json(silent=True) or {}
    try:
        try:
            from hf_importer import import_hf_dataset  # type: ignore
        except Exception:
            from backend.hf_importer import import_hf_dataset  # type: ignore
        payload = import_hf_dataset(
            dataset_name=data.get("dataset_name") or data.get("name"),
            config=data.get("config"),
            split=data.get("split", "test"),
            limit=int(data.get("limit", 100)),
            task_type=data.get("task_type"),
            display_name=data.get("display_name"),
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

    if data.get("preview_only"):
        preview = dict(payload)
        rd = dict(preview.get("reference_data") or {})
        rd["source_texts"] = rd.get("source_texts", [])[:5]
        rd["ground_truth"] = rd.get("ground_truth", [])[:5]
        preview["reference_data"] = rd
        return jsonify({"success": True, "dataset": preview})

    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute(
                "INSERT INTO benchmark_datasets (name, task_type, evaluation_metric, reference_data, active) VALUES (%s, %s, %s, %s, TRUE)",
                (
                    payload["name"],
                    payload["task_type"],
                    payload["evaluation_metric"],
                    json.dumps(payload["reference_data"]),
                ),
            )
            conn.commit()
        except Exception as e:
            if 'Duplicate' in str(e) or 'UNIQUE' in str(e):
                return jsonify({"success": False, "error": "Dataset with this name already exists"}), 400
            return jsonify({"success": False, "error": "Failed to import dataset"}), 500
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass
    else:
        if any(d.get("name") == payload["name"] for d in _STORE["datasets"]):
            return jsonify({"success": False, "error": "Dataset with this name already exists"}), 400
        _STORE["datasets"].append(payload)
        LEADERBOARD_DATA.append({
            "id": str(uuid.uuid4()),
            "name": payload["name"],
            "task_type": payload["task_type"],
            "description": payload["reference_data"].get("description"),
            "url": payload["reference_data"].get("url"),
            "models": [],
        })

    return jsonify({
        "success": True,
        "message": "Dataset imported",
        "dataset": {
            "name": payload["name"],
            "task_type": payload["task_type"],
            "evaluation_metric": payload["evaluation_metric"],
            "size": len(payload["reference_data"].get("source_texts", [])),
        },
    })


@app.post('/api/datasets/ingest')
@rate_limit("IMPORT_DATASET_RATE_LIMIT", "5/minute")
@require_api_key
def ingest_dataset():
    """Issue-compatible ingestion endpoint for Hugging Face sources."""
    data = request.get_json(silent=True) or {}
    source = (data.get("source") or "").lower()
    if source not in {"huggingface", "hf"}:
        return jsonify({"success": False, "error": "Only source=huggingface is currently supported"}), 400
    mapped = {
        "dataset_name": data.get("dataset_id") or data.get("dataset_name"),
        "config": data.get("config"),
        "split": data.get("split", "test"),
        "limit": data.get("max_samples", data.get("limit", 100)),
        "task_type": data.get("task_type"),
        "display_name": data.get("display_name"),
        "preview_only": data.get("preview_only", False),
    }
    with app.test_request_context(
        "/public/import_hf_dataset",
        method="POST",
        json=mapped,
        headers=dict(request.headers),
    ):
        return import_hf_dataset_public()


@app.get('/public/export/leaderboard')
def export_leaderboard():
    """Export leaderboard rows as CSV or JSON."""
    dataset_name = request.args.get("dataset")
    export_format = (request.args.get("format") or "csv").lower()
    with app.test_request_context(
        "/public/get_leaderboard",
        query_string={
            "dataset": dataset_name or "",
            "page": "1",
            "page_size": "100",
        },
    ):
        payload = get_leaderboard().get_json()
    rows = payload.get("leaderboard", []) if payload else []
    if export_format == "json":
        return jsonify({"success": True, "leaderboard": rows})
    if export_format != "csv":
        return jsonify({"success": False, "error": "format must be csv or json"}), 400

    out = StringIO()
    writer = csv.DictWriter(
        out,
        fieldnames=["rank", "dataset_name", "model_name", "submitted_by", "score", "evaluation_metric", "submitted_at"],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field) for field in writer.fieldnames})
    filename = f"leaderboard-{dataset_name or 'all'}.csv"
    return Response(
        out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---------------------------
# Leaderboard UI API (per README)
# ---------------------------
@app.post('/api/leaderboard/add_dataset')
@rate_limit("ADD_DATASET_RATE_LIMIT", "5/minute")
@require_api_key
def add_dataset():
    data = request.get_json(silent=True) or {}
    try:
        name = validate_text(data.get("name"), "name")
        task_type = validate_text(data.get("task_type"), "task_type", 100)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    dataset_id = str(uuid.uuid4())
    new_ds = {
        "id": dataset_id,
        "name": name,
        "url": data.get("url"),
        "task_type": task_type,
        "description": data.get("description"),
        "models": data.get("models", []),
    }
    LEADERBOARD_DATA.append(new_ds)
    return jsonify({
        "status": "success",
        "message": "Dataset added to leaderboard.",
        "dataset_id": dataset_id,
    })


@app.post('/api/leaderboard/add_model')
@rate_limit("SUBMIT_MODEL_RATE_LIMIT", "10/minute")
@require_api_key
def add_model():
    data = request.get_json(silent=True) or {}
    required = ["rank", "score", "updated"]
    missing = [k for k in required if k not in data]
    if missing:
        return jsonify({"status": "error", "message": f"Missing required fields: {', '.join(missing)}"}), 400
    try:
        dataset_name = validate_text(data.get("dataset_name"), "dataset_name")
        model = validate_text(data.get("model"), "model")
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    for ds in LEADERBOARD_DATA:
        if ds.get("name") == dataset_name:
            ds.setdefault("models", []).append({
                "rank": data["rank"],
                "model": model,
                "score": data["score"],
                "ci": data.get("ci"),
                "updated": data["updated"],
            })
            # keep models sorted by rank
            ds["models"].sort(key=lambda m: (m.get("rank") is None, m.get("rank")))
            return jsonify({"status": "success", "message": "Model added to dataset on leaderboard."})
    return jsonify({"status": "error", "message": "Dataset not found."}), 404


@app.get('/api/leaderboard/list')
def list_leaderboard_datasets():
    """Return the curated leaderboard datasets and their models (in-memory).

    Response:
    {
      "status": "success",
      "datasets": [ { id, name, url, task_type, description, models: [...] }, ... ]
    }
    """
    return jsonify({
        "status": "success",
        "datasets": LEADERBOARD_DATA,
    })


# ---------------------------
# CSV Benchmarks (benchmark_csvs folder)
# ---------------------------
@app.get('/public/benchmark_csvs')
def list_benchmark_csvs():
    if not csv_bench:
        return jsonify({"success": False, "error": "CSV benchmark module unavailable"}), 500
    items = csv_bench.list_csv_datasets()
    # Only return filename and inferred task for brevity
    return jsonify({
        "success": True,
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
        print(f"list_benchmark_models error: {e}")
        return jsonify({"success": False, "error": "Model list unavailable"}), 500


@app.post('/public/run_csv_benchmarks')
@rate_limit("RUN_CSV_RATE_LIMIT", "5/minute")
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
    try:
        summary = csv_bench.run_benchmarks(models=models, datasets=datasets, sample_size=sample_size)
        return jsonify({"success": True, **summary})
    except Exception as e:
        print(f"CSV benchmarks error: {e}")
        return jsonify({"success": False, "error": "Failed to run benchmarks"}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', '5000'))
    # When running via Docker-compose, external is 5001 -> container 5000
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_ENV') == 'development')
