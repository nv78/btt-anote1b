import os
import json
import csv
import logging
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from functools import wraps
from io import StringIO
from time import time
from urllib.parse import quote

from flask import Flask, Response, request, jsonify, redirect
from flask_cors import CORS
import uuid
import threading

try:
    from auth_helpers import jwt_sub_from_request, resolve_submitter_id
except ImportError:
    from backend.auth_helpers import jwt_sub_from_request, resolve_submitter_id

try:
    from pagination import (
        decode_cursor,
        leaderboard_cursor_decode,
        leaderboard_cursor_encode,
        my_submissions_cursor_decode,
        my_submissions_cursor_encode,
    )
except ImportError:
    from backend.pagination import (  # type: ignore
        decode_cursor,
        leaderboard_cursor_decode,
        leaderboard_cursor_encode,
        my_submissions_cursor_decode,
        my_submissions_cursor_encode,
    )

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
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-insecure-change-me")
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
    # Common CRA ports when 3000 is already in use (see frontend/.env.development)
    _origins_list = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
else:
    raise RuntimeError("ALLOWED_ORIGINS must be set outside development")
CORS(app, resources={r"/*": {"origins": _origins_list}})


def _init_google_oauth(app_):
    cid = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not cid:
        return None
    try:
        from authlib.integrations.flask_client import OAuth
    except ImportError:
        logger.warning("authlib_not_installed", extra={"hint": "pip install Authlib"})
        return None
    oauth = OAuth(app_)
    oauth.register(
        name="google",
        client_id=cid,
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET", "").strip(),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    return oauth


_OAUTH = _init_google_oauth(app)


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


def _parse_iso_datetime(val):
    if not val or not isinstance(val, str):
        return None
    s = val.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


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
    """Writes: ``X-API-Key`` in ``LEADERBOARD_API_KEYS`` or Bearer JWT with ``sub`` (HS256 or Anote JWKS)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            from auth_helpers import decode_leaderboard_bearer_token
        except ImportError:
            from backend.auth_helpers import decode_leaderboard_bearer_token  # type: ignore

        configured = [key.strip() for key in os.getenv("LEADERBOARD_API_KEYS", "").split(",") if key.strip()]
        require_key = os.getenv("REQUIRE_API_KEY", "").lower() in {"1", "true", "yes"} or bool(configured)
        if not require_key:
            return fn(*args, **kwargs)
        supplied = request.headers.get("X-API-Key", "")
        if supplied in configured:
            return fn(*args, **kwargs)
        auth = request.headers.get("Authorization", "") or ""
        if auth.startswith("Bearer "):
            payload = decode_leaderboard_bearer_token(auth[7:].strip())
            if payload and str(payload.get("sub", "")).strip():
                return fn(*args, **kwargs)
        logger.warning("unauthorized_write", extra={"endpoint": request.path, "ip": request.remote_addr})
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    return wrapper


def require_admin(fn):
    """Admin list/moderation: ``X-Admin-Key`` or ``X-API-Key`` must match ``LEADERBOARD_ADMIN_API_KEYS``."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        keys = [k.strip() for k in os.getenv("LEADERBOARD_ADMIN_API_KEYS", "").split(",") if k.strip()]
        if not keys:
            return jsonify({"success": False, "error": "Admin API not configured"}), 503
        supplied = (request.headers.get("X-Admin-Key") or request.headers.get("X-API-Key") or "").strip()
        if supplied not in keys:
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
    from metrics_info_full import (  # type: ignore
        METRICS_CATALOG,
        metrics_for_task,
        normalize_task_type_for_metrics,
        primary_metric_catalog_entry,
    )
except Exception:
    try:
        from backend.metrics_info_full import (  # type: ignore
            METRICS_CATALOG,
            metrics_for_task,
            normalize_task_type_for_metrics,
            primary_metric_catalog_entry,
        )
    except Exception:
        METRICS_CATALOG = {}

        def metrics_for_task(_task_type):
            return {}

        def normalize_task_type_for_metrics(t):
            if not t:
                return "translation"
            return str(t).lower().strip().replace(" ", "_").replace("-", "_")

        def primary_metric_catalog_entry(_m):
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
            "/public/submission_format",
            "/public/submit_model",
            "/public/eval_jobs/<job_id>",
            "/public/my_submissions",
            "/public/submissions/<id>",
            "/public/get_leaderboard",
            "/public/export/leaderboard",
            "/public/auth/google/start",
            "/public/auth/google/callback",
            "/api/admin/submissions",
            "/api/leaderboard/*",
        ],
        "note": "Set PORT=5001 for local frontend integration.",
    })


# Simple health endpoint
@app.get('/health')
def health():
    return jsonify({"ok": True, "time": utc_now().isoformat()})


# In-memory fallback storage when DB is not available
_STORE = {
    "submissions": [],  # {id, benchmark_dataset_name, model_name, submitter_id?, results, created}
    "evaluations": [],  # {submission_id, score, metric, evaluation_details?, created}
    "datasets": [],  # {name, task_type, evaluation_metric, reference_data}
}

# In-process async eval jobs (optional ``async: true`` on submit); not durable across restarts.
_EVAL_JOBS: dict = {}
_EVAL_JOBS_LOCK = threading.Lock()

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


@app.get('/public/submission_format')
def submission_format():
    """Return expected POST /public/submit_model JSON shape for a dataset name."""
    raw = request.args.get("dataset") or request.args.get("benchmarkDatasetName")
    if not raw:
        return jsonify({"success": False, "error": "Missing query parameter: dataset or benchmarkDatasetName"}), 400
    try:
        name = validate_text(raw, "dataset")
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    dataset = None
    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute(
                "SELECT name, task_type, evaluation_metric, reference_data FROM benchmark_datasets "
                "WHERE name = %s AND active = TRUE",
                (name,),
            )
            dataset = cursor.fetchone()
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass
    if not dataset:
        dataset = next((d for d in _STORE["datasets"] if d.get("name") == name), None)
    if not dataset:
        return jsonify({"success": False, "error": "Dataset not found"}), 404

    try:
        from eval_core.leaderboard_bridge import submission_format_for_dataset  # type: ignore
    except ImportError:
        from backend.eval_core.leaderboard_bridge import submission_format_for_dataset  # type: ignore

    payload = submission_format_for_dataset(
        dataset.get("name", name),
        dataset.get("task_type"),
        dataset.get("evaluation_metric"),
        dataset.get("reference_data"),
    )
    return jsonify(payload)


def _mem_leaderboard_row_after_anchor(item, dataset_filter, single_ds, an_d, an_s, an_i):
    """True if item sorts strictly after anchor (DB order: dataset ASC, score DESC, id DESC)."""
    ev, sub = item
    name = sub["benchmark_dataset_name"]
    sc = float(ev["score"])
    sid = int(sub["id"])
    if dataset_filter:
        return (sc < float(an_s)) or (sc == float(an_s) and sid < int(an_i))
    return (name > an_d) or (name == an_d and sc < float(an_s)) or (name == an_d and sc == float(an_s) and sid < int(an_i))


@app.get('/public/get_leaderboard')
def get_leaderboard():
    """Get leaderboard showing model submissions and scores.
    Supports DB if configured, otherwise returns in-memory results.

    Pagination: ``page`` + offset (default), or ``cursor`` (keyset; ignores ``page``).
    Sort: ``dataset_name`` ASC, ``score`` DESC, ``submission_id`` DESC.
    """
    dataset_filter = request.args.get("dataset")
    cursor_token = (request.args.get("cursor") or "").strip()
    page = max(1, int(request.args.get("page", 1)))
    page_size = min(100, max(1, int(request.args.get("page_size", request.args.get("limit", 25)))))
    offset = (page - 1) * page_size
    use_cursor = bool(cursor_token)
    rank_start = 1
    key_single = bool(dataset_filter)

    if use_cursor:
        cd = decode_cursor(cursor_token)
        dec = leaderboard_cursor_decode(cd) if cd else None
        if not dec:
            return jsonify({"success": False, "error": "Invalid cursor"}), 400
        key_single, an_d, an_s, an_i, rank_start = dec
        if bool(dataset_filter) != key_single:
            return jsonify({"success": False, "error": "Cursor dataset scope mismatch"}), 400
        if dataset_filter and key_single:
            an_d = ""

    conn, cursor = get_db_connection()

    def _rows_to_leaderboard(rows, r0):
        leaderboard = []
        for j, row in enumerate(rows):
            details = {}
            if row.get("evaluation_details"):
                try:
                    details = json.loads(row["evaluation_details"]) if isinstance(row["evaluation_details"], str) else row["evaluation_details"]
                except Exception:
                    details = {}
            leaderboard.append({
                "rank": r0 + j,
                "submission_id": row.get("submission_id"),
                "model_name": row["model_name"],
                "dataset_name": row["dataset_name"],
                "task_type": row.get("task_type"),
                "evaluation_metric": row.get("evaluation_metric"),
                "score": float(row["score"]),
                "submitted_by": row.get("submitted_by"),
                "metadata": details.get("metadata") if isinstance(details, dict) else None,
                "detailed_scores": details.get("detailed_scores") if isinstance(details, dict) else None,
                "primary_metric": details.get("metric") if isinstance(details, dict) else None,
                "submitted_at": row["submitted_at"].isoformat() if row.get("submitted_at") else None,
            })
        return leaderboard

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

            base_select = (
                "SELECT ms.id AS submission_id, ms.model_name, bd.name AS dataset_name, bd.task_type, bd.evaluation_metric, "
                "er.score, er.evaluation_details, ms.created AS submitted_at, "
                "ms.submitted_by, ms.model_results "
                "FROM model_submissions ms "
                "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                "JOIN evaluation_results er ON er.model_submission_id = ms.id "
            )
            order = "ORDER BY bd.name ASC, er.score DESC, ms.id DESC "

            if use_cursor:
                wk = list(params)
                if dataset_filter:
                    where_k = where + " AND ((er.score < %s) OR (er.score = %s AND ms.id < %s))"
                    wk.extend([an_s, an_s, an_i])
                else:
                    where_k = where + (
                        " AND ((bd.name > %s) OR (bd.name = %s AND er.score < %s) "
                        "OR (bd.name = %s AND er.score = %s AND ms.id < %s))"
                    )
                    wk.extend([an_d, an_d, an_s, an_d, an_s, an_i])
                query = base_select + where_k + order + "LIMIT %s"
                cursor.execute(query, tuple(wk + [page_size]))
            else:
                query = base_select + where + order + "LIMIT %s OFFSET %s"
                cursor.execute(query, tuple(params + [page_size, offset]))

            rows = cursor.fetchall()
            r0 = rank_start if use_cursor else offset + 1
            leaderboard = _rows_to_leaderboard(rows, r0)
            out = {
                "success": True,
                "leaderboard": leaderboard,
                "page": page if not use_cursor else None,
                "page_size": page_size,
                "total": total,
            }
            has_more = len(rows) == page_size and (use_cursor or offset + len(rows) < total)
            if has_more:
                last = rows[-1]
                next_r = r0 + len(rows)
                out["next_cursor"] = leaderboard_cursor_encode(
                    dataset_name=last["dataset_name"],
                    score=float(last["score"]),
                    submission_id=int(last["submission_id"]),
                    next_rank_start=next_r,
                    single_dataset=bool(dataset_filter),
                )
            return jsonify(out)
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
    mem_all.sort(key=lambda x: (x[1]["benchmark_dataset_name"], -float(x[0]["score"]), -int(x[1]["id"])))
    total = len(mem_all)

    if use_cursor:
        mem = []
        for item in mem_all:
            if not _mem_leaderboard_row_after_anchor(item, dataset_filter, key_single, an_d, an_s, an_i):
                continue
            mem.append(item)
            if len(mem) >= page_size:
                break
    else:
        mem = mem_all[offset : offset + page_size]

    leaderboard = []
    for j, (ev, sub) in enumerate(mem):
        ev_details = ev.get("evaluation_details") or {}
        if not isinstance(ev_details, dict):
            ev_details = {}
        ds_meta = next(
            (d for d in _STORE["datasets"] if d.get("name") == sub["benchmark_dataset_name"]),
            None,
        )
        leaderboard.append({
            "rank": rank_start + j if use_cursor else offset + j + 1,
            "submission_id": sub["id"],
            "model_name": sub["model_name"],
            "dataset_name": sub["benchmark_dataset_name"],
            "task_type": (ds_meta or {}).get("task_type") or "translation",
            "evaluation_metric": ev["metric"],
            "score": ev["score"],
            "submitted_by": sub.get("submitted_by"),
            "metadata": ev_details.get("metadata") if ev_details else sub.get("metadata"),
            "detailed_scores": ev_details.get("detailed_scores"),
            "primary_metric": ev_details.get("metric"),
            "submitted_at": sub["created"].isoformat(),
        })
    out = {
        "success": True,
        "leaderboard": leaderboard,
        "page": page if not use_cursor else None,
        "page_size": page_size,
        "total": total,
    }
    mem_has_more = len(mem) == page_size and (use_cursor or offset + page_size < total)
    if mem_has_more:
        last_ev, last_sub = mem[-1]
        next_r = rank_start + len(mem) if use_cursor else offset + len(mem) + 1
        out["next_cursor"] = leaderboard_cursor_encode(
            dataset_name=last_sub["benchmark_dataset_name"],
            score=float(last_ev["score"]),
            submission_id=int(last_sub["id"]),
            next_rank_start=next_r,
            single_dataset=bool(dataset_filter),
        )
    return jsonify(out)


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

    submitter_id = resolve_submitter_id(request, data)
    want_async = bool(data.get("async"))

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
                if isinstance(rd.get('ground_truth'), list) and sentence_ids:
                    gtlist = rd['ground_truth']
                    try:
                        if all(0 <= int(i) < len(gtlist) for i in sentence_ids):
                            rows = [gtlist[int(i)] for i in sentence_ids]
                            _tt = (task_type or '').lower()
                            if not reference_labels and _tt == 'text_classification':
                                reference_labels = [r.get('answer') for r in rows]
                            if not reference_entities and _tt in ('ner', 'named_entity_recognition'):
                                reference_entities = [r.get('answer') for r in rows]
                            if not reference_answers and _tt in (
                                'chatbot', 'prompting', 'qa', 'document_qa', 'line_qa',
                            ):
                                reference_answers = [r.get('answer') for r in rows]
                            if not reference_sentences and _tt in ('translation', ''):
                                reference_sentences = [r.get('answer') for r in rows]
                    except Exception:
                        pass
        except Exception:
            pass

    try:
        try:
            from eval_core.leaderboard_bridge import (  # type: ignore
                normalize_eval_metric,
                normalize_task_type,
                run_personal_eval,
            )
        except ImportError:
            from backend.eval_core.leaderboard_bridge import (  # type: ignore
                normalize_eval_metric,
                normalize_task_type,
                run_personal_eval,
            )

        task_norm = normalize_task_type(task_type)
        if task_norm == 'translation':
            if reference_sentences is None:
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
            if metric is None:
                metric = 'bertscore' if benchmark_dataset_name.endswith('_bertscore') else 'bleu'

        score, detailed_scores = run_personal_eval(
            task_type,
            metric,
            sentence_ids,
            reference_labels,
            reference_entities,
            reference_answers,
            reference_sentences,
            model_results,
        )
        metric = normalize_eval_metric(metric, task_norm)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        print(f"Evaluation failed: {e}")
        return jsonify({"success": False, "error": "Evaluation failed"}), 500

    eval_details = {"metric": metric, "metadata": metadata, "detailed_scores": detailed_scores}

    def _persist_and_build_response():
        submission_id = None
        conn, cursor = get_db_connection()
        if conn and cursor:
            try:
                cursor.execute(
                    "SELECT id FROM benchmark_datasets WHERE name = %s",
                    (benchmark_dataset_name,),
                )
                row = cursor.fetchone()
                if row:
                    dataset_id = row['id']
                else:
                    cursor.execute(
                        "INSERT INTO benchmark_datasets (name, task_type, evaluation_metric, reference_data, active) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (benchmark_dataset_name, 'translation', metric, json.dumps([]), True),
                    )
                    dataset_id = cursor.lastrowid

                try:
                    cursor.execute(
                        "INSERT INTO model_submissions (benchmark_dataset_id, model_name, submitted_by, submitter_id, model_results) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (dataset_id, model_name, submitted_by, submitter_id, json.dumps(model_results)),
                    )
                except Exception as ins_err:
                    if "submitter_id" in str(ins_err).lower() or "Unknown column" in str(ins_err):
                        cursor.execute(
                            "INSERT INTO model_submissions (benchmark_dataset_id, model_name, submitted_by, model_results) "
                            "VALUES (%s, %s, %s, %s)",
                            (dataset_id, model_name, submitted_by, json.dumps(model_results)),
                        )
                    else:
                        raise
                submission_id = cursor.lastrowid

                cursor.execute(
                    "INSERT INTO evaluation_results (model_submission_id, score, evaluation_details) "
                    "VALUES (%s, %s, %s)",
                    (submission_id, float(score), json.dumps(eval_details)),
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
            submission_id = len(_STORE["submissions"]) + 1
            _STORE["submissions"].append({
                "id": submission_id,
                "benchmark_dataset_name": benchmark_dataset_name,
                "model_name": model_name,
                "submitted_by": submitted_by,
                "submitter_id": submitter_id,
                "metadata": metadata,
                "results": model_results,
                "created": utc_now(),
            })
            _STORE["evaluations"].append({
                "submission_id": submission_id,
                "score": float(score),
                "metric": metric,
                "evaluation_details": eval_details,
                "created": utc_now(),
            })

        logger.info(
            "model_submitted",
            extra={"dataset": benchmark_dataset_name, "model": model_name, "score": float(score)},
        )
        return {
            "success": True,
            "submission_id": submission_id,
            "score": float(score),
            "metric": metric,
            "detailed_scores": detailed_scores,
        }

    if want_async:

        def _worker(job_id: str):
            try:
                out = _persist_and_build_response()
                with _EVAL_JOBS_LOCK:
                    _EVAL_JOBS[job_id] = {"status": "completed", **out}
            except Exception as e:
                with _EVAL_JOBS_LOCK:
                    _EVAL_JOBS[job_id] = {"status": "failed", "error": str(e)}

        job_id = str(uuid.uuid4())
        with _EVAL_JOBS_LOCK:
            _EVAL_JOBS[job_id] = {"status": "pending"}
        t = threading.Thread(target=_worker, args=(job_id,), daemon=True)
        t.start()
        return jsonify({"success": True, "job_id": job_id, "status": "pending"}), 202

    out = _persist_and_build_response()
    return jsonify(out)


@app.get("/public/eval_jobs/<job_id>")
def eval_job_status(job_id):
    """Poll async submit job created with ``{\"async\": true}`` on ``/public/submit_model``."""
    with _EVAL_JOBS_LOCK:
        row = _EVAL_JOBS.get(job_id)
    if not row:
        return jsonify({"success": False, "error": "Unknown job"}), 404
    return jsonify({"success": True, **row})


@app.get("/public/my_submissions")
def my_submissions():
    """List submissions for a submitter (JWT ``sub`` or ``submitter_id`` query with API key).

    Pagination: ``page`` + offset (default), or ``cursor`` (keyset on ``created DESC``, ``id DESC``; ignores ``page``).
    """
    sub = jwt_sub_from_request(request)
    if not sub:
        configured = [k.strip() for k in os.getenv("LEADERBOARD_API_KEYS", "").split(",") if k.strip()]
        require_key = os.getenv("REQUIRE_API_KEY", "").lower() in {"1", "true", "yes"} or bool(configured)
        if require_key:
            supplied = request.headers.get("X-API-Key", "")
            if supplied not in configured:
                return jsonify({"success": False, "error": "Unauthorized"}), 401
        sub = (request.args.get("submitter_id") or "").strip()
    if not sub:
        return jsonify({
            "success": False,
            "error": "Provide a valid Bearer JWT or submitter_id query parameter (with API key if required)",
        }), 400

    page = max(1, int(request.args.get("page", 1)))
    page_size = min(100, max(1, int(request.args.get("page_size", 25))))
    offset = (page - 1) * page_size
    cursor_token = (request.args.get("cursor") or "").strip()
    use_cursor = bool(cursor_token)
    anchor_c = None
    anchor_id = None
    if use_cursor:
        cd = decode_cursor(cursor_token)
        dec = my_submissions_cursor_decode(cd) if cd else None
        if not dec:
            return jsonify({"success": False, "error": "Invalid cursor"}), 400
        c_iso, anchor_id = dec
        anchor_c = _parse_iso_datetime(c_iso)
        if anchor_c is None:
            return jsonify({"success": False, "error": "Invalid cursor"}), 400

    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            try:
                cursor.execute(
                    "SELECT COUNT(*) AS n FROM model_submissions WHERE submitter_id = %s",
                    (sub,),
                )
            except Exception:
                cursor.execute(
                    "SELECT COUNT(*) AS n FROM model_submissions WHERE submitted_by = %s",
                    (sub,),
                )
            total = int((cursor.fetchone() or {}).get("n", 0))
            cur_sql = ""
            cur_params: list = []
            if use_cursor:
                cur_sql = " AND ((ms.created < %s) OR (ms.created = %s AND ms.id < %s))"
                cur_params = [anchor_c, anchor_c, anchor_id]
            try:
                if use_cursor:
                    cursor.execute(
                        "SELECT ms.id, ms.model_name, ms.submitted_by, ms.submitter_id, ms.created, "
                        "bd.name AS dataset_name, bd.task_type, er.score, er.evaluation_details "
                        "FROM model_submissions ms "
                        "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                        "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                        "WHERE ms.submitter_id = %s " + cur_sql +
                        "ORDER BY ms.created DESC, ms.id DESC LIMIT %s",
                        tuple([sub] + cur_params + [page_size]),
                    )
                else:
                    cursor.execute(
                        "SELECT ms.id, ms.model_name, ms.submitted_by, ms.submitter_id, ms.created, "
                        "bd.name AS dataset_name, bd.task_type, er.score, er.evaluation_details "
                        "FROM model_submissions ms "
                        "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                        "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                        "WHERE ms.submitter_id = %s "
                        "ORDER BY ms.created DESC, ms.id DESC LIMIT %s OFFSET %s",
                        (sub, page_size, offset),
                    )
            except Exception:
                if use_cursor:
                    cursor.execute(
                        "SELECT ms.id, ms.model_name, ms.submitted_by, ms.created, "
                        "bd.name AS dataset_name, bd.task_type, er.score, er.evaluation_details "
                        "FROM model_submissions ms "
                        "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                        "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                        "WHERE ms.submitted_by = %s " + cur_sql +
                        "ORDER BY ms.created DESC, ms.id DESC LIMIT %s",
                        tuple([sub] + cur_params + [page_size]),
                    )
                else:
                    cursor.execute(
                        "SELECT ms.id, ms.model_name, ms.submitted_by, ms.created, "
                        "bd.name AS dataset_name, bd.task_type, er.score, er.evaluation_details "
                        "FROM model_submissions ms "
                        "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                        "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                        "WHERE ms.submitted_by = %s "
                        "ORDER BY ms.created DESC, ms.id DESC LIMIT %s OFFSET %s",
                        (sub, page_size, offset),
                    )
            rows = cursor.fetchall()
            items = []
            for r in rows:
                det = {}
                if r.get("evaluation_details"):
                    try:
                        det = json.loads(r["evaluation_details"]) if isinstance(r["evaluation_details"], str) else r["evaluation_details"]
                    except Exception:
                        det = {}
                items.append({
                    "submission_id": r["id"],
                    "dataset_name": r["dataset_name"],
                    "task_type": r.get("task_type"),
                    "model_name": r["model_name"],
                    "submitted_by": r.get("submitted_by"),
                    "score": float(r["score"]),
                    "primary_metric": det.get("metric") if isinstance(det, dict) else None,
                    "detailed_scores": det.get("detailed_scores") if isinstance(det, dict) else None,
                    "submitted_at": r["created"].isoformat() if r.get("created") else None,
                })
            out = {
                "success": True,
                "submissions": items,
                "page": page if not use_cursor else None,
                "page_size": page_size,
                "total": total,
            }
            ms_more = len(rows) == page_size and (use_cursor or offset + len(rows) < total)
            if ms_more and rows:
                lr = rows[-1]
                ca = lr["created"].isoformat() if lr.get("created") else ""
                out["next_cursor"] = my_submissions_cursor_encode(ca, int(lr["id"]))
            return jsonify(out)
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

    mem_raw = []
    for ev in _STORE["evaluations"]:
        sub_row = next((s for s in _STORE["submissions"] if s["id"] == ev["submission_id"]), None)
        if not sub_row:
            continue
        sid = sub_row.get("submitter_id") or sub_row.get("submitted_by")
        if sid != sub:
            continue
        det = ev.get("evaluation_details") or {}
        if not isinstance(det, dict):
            det = {}
        mem_raw.append({
            "submission_id": sub_row["id"],
            "dataset_name": sub_row["benchmark_dataset_name"],
            "model_name": sub_row["model_name"],
            "submitted_by": sub_row.get("submitted_by"),
            "score": ev["score"],
            "primary_metric": det.get("metric"),
            "detailed_scores": det.get("detailed_scores"),
            "_created": sub_row["created"],
            "_id": sub_row["id"],
        })
    mem_raw.sort(key=lambda x: (x["_created"], x["_id"]), reverse=True)
    total = len(mem_raw)
    if use_cursor:
        page_rows = []
        for r in mem_raw:
            if (r["_created"] < anchor_c) or (r["_created"] == anchor_c and r["_id"] < anchor_id):
                page_rows.append(r)
            if len(page_rows) >= page_size:
                break
    else:
        page_rows = mem_raw[offset:offset + page_size]

    items = []
    for r in page_rows:
        items.append({
            "submission_id": r["submission_id"],
            "dataset_name": r["dataset_name"],
            "model_name": r["model_name"],
            "submitted_by": r["submitted_by"],
            "score": r["score"],
            "primary_metric": r["primary_metric"],
            "detailed_scores": r["detailed_scores"],
            "submitted_at": r["_created"].isoformat(),
        })
    out = {
        "success": True,
        "submissions": items,
        "page": page if not use_cursor else None,
        "page_size": page_size,
        "total": total,
    }
    ms_more = len(page_rows) == page_size and (use_cursor or offset + page_size < total)
    if ms_more and page_rows:
        last = page_rows[-1]
        out["next_cursor"] = my_submissions_cursor_encode(last["_created"].isoformat(), int(last["_id"]))
    return jsonify(out)


def _evaluation_snippet_and_body(det_raw, include_outputs: bool):
    """Return (snippet_str_or_none, details_dict_or_none) for admin list."""
    if det_raw is None:
        return None, None
    det = det_raw
    if isinstance(det, str):
        try:
            det = json.loads(det)
        except Exception:
            s = det.strip()
            return (s[:2000] + ("…" if len(s) > 2000 else "")), None
    if not isinstance(det, dict):
        s = str(det)
        return (s[:2000] + ("…" if len(s) > 2000 else "")), None
    if include_outputs:
        return None, det
    thin = {k: det[k] for k in ("metric", "error", "note", "warnings") if k in det}
    if "detailed_scores" in det and not include_outputs:
        thin["detailed_scores"] = det.get("detailed_scores")
    try:
        raw = json.dumps(thin, ensure_ascii=False, default=str)
    except Exception:
        raw = str(thin)
    if len(raw) > 2000:
        raw = raw[:2000] + "…"
    return raw, None


@app.get("/api/admin/submissions")
@require_admin
def admin_list_submissions():
    """List all submissions for moderation (``LEADERBOARD_ADMIN_API_KEYS``)."""
    dataset = (request.args.get("dataset") or "").strip() or None
    submitter_q = (request.args.get("submitter_id") or "").strip() or None
    raw_from = request.args.get("from")
    raw_to = request.args.get("to")
    date_from = _parse_iso_datetime(raw_from) if raw_from else None
    date_to = _parse_iso_datetime(raw_to) if raw_to else None
    include_outputs = (request.args.get("include_outputs") or "").lower() in {"1", "true", "yes"}
    page = max(1, int(request.args.get("page", 1)))
    page_size = min(200, max(1, int(request.args.get("page_size", 25))))
    offset = (page - 1) * page_size
    cursor_token = (request.args.get("cursor") or "").strip()
    use_cursor = bool(cursor_token)
    anchor_c = None
    anchor_id = None
    if use_cursor:
        cd = decode_cursor(cursor_token)
        dec = my_submissions_cursor_decode(cd) if cd else None
        if not dec:
            return jsonify({"success": False, "error": "Invalid cursor"}), 400
        c_iso, anchor_id = dec
        anchor_c = _parse_iso_datetime(c_iso)
        if anchor_c is None:
            return jsonify({"success": False, "error": "Invalid cursor"}), 400

    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            where = ["1=1"]
            params_base: list = []
            if dataset:
                where.append("bd.name = %s")
                params_base.append(dataset)
            if submitter_q:
                where.append("(ms.submitter_id = %s OR ms.submitted_by = %s)")
                params_base.extend([submitter_q, submitter_q])
            if date_from:
                where.append("ms.created >= %s")
                params_base.append(date_from)
            if date_to:
                where.append("ms.created <= %s")
                params_base.append(date_to)
            cur_sql = ""
            cur_params: list = []
            if use_cursor:
                cur_sql = " AND ((ms.created < %s) OR (ms.created = %s AND ms.id < %s))"
                cur_params = [anchor_c, anchor_c, anchor_id]
            where_sql = " AND ".join(where)

            count_q = (
                "SELECT COUNT(*) AS n FROM model_submissions ms "
                "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                f"WHERE {where_sql}"
            )
            cursor.execute(count_q, tuple(params_base))
            total = int((cursor.fetchone() or {}).get("n", 0))

            mr_col = "ms.model_results" if include_outputs else "NULL AS model_results"
            base = (
                f"SELECT ms.id, ms.model_name, ms.submitted_by, ms.submitter_id, ms.created, "
                f"bd.name AS dataset_name, bd.task_type, er.score, er.evaluation_details, {mr_col} "
                "FROM model_submissions ms "
                "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                f"WHERE {where_sql}{cur_sql} "
                "ORDER BY ms.created DESC, ms.id DESC "
            )
            lim_params: list = [page_size]
            if not use_cursor:
                base += "LIMIT %s OFFSET %s"
                lim_params.append(offset)
            else:
                base += "LIMIT %s"
            cursor.execute(base, tuple(params_base + cur_params + lim_params))
            rows = cursor.fetchall()
            items = []
            for r in rows:
                det_raw = r.get("evaluation_details")
                snip, _ = _evaluation_snippet_and_body(det_raw, include_outputs)
                row_out = {
                    "submission_id": r["id"],
                    "dataset_name": r["dataset_name"],
                    "task_type": r.get("task_type"),
                    "model_name": r["model_name"],
                    "submitted_by": r.get("submitted_by"),
                    "submitter_id": r.get("submitter_id"),
                    "score": float(r["score"]),
                    "created": r["created"].isoformat() if r.get("created") else None,
                    "evaluation_snippet": snip,
                }
                if include_outputs:
                    ed = det_raw
                    if isinstance(ed, str):
                        try:
                            ed = json.loads(ed)
                        except Exception:
                            ed = {"raw": ed}
                    row_out["evaluation_details"] = ed if isinstance(ed, dict) else {"raw": ed}
                    mr = r.get("model_results")
                    if isinstance(mr, str):
                        try:
                            mr = json.loads(mr)
                        except Exception:
                            pass
                    row_out["model_results"] = mr
                items.append(row_out)
            out = {
                "success": True,
                "submissions": items,
                "page": page if not use_cursor else None,
                "page_size": page_size,
                "total": total,
            }
            adm_more = len(rows) == page_size and (use_cursor or offset + len(rows) < total)
            if adm_more and rows:
                lr = rows[-1]
                ca = lr["created"].isoformat() if lr.get("created") else ""
                out["next_cursor"] = my_submissions_cursor_encode(ca, int(lr["id"]))
            return jsonify(out)
        except Exception as e:
            logger.exception("admin_submissions_db_failed", extra={"error": str(e)})
            return jsonify({"success": False, "error": "Database error"}), 500
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

    mem_raw = []
    for ev in _STORE["evaluations"]:
        sub_row = next((s for s in _STORE["submissions"] if s["id"] == ev["submission_id"]), None)
        if not sub_row:
            continue
        dname = sub_row["benchmark_dataset_name"]
        if dataset and dname != dataset:
            continue
        if submitter_q:
            if sub_row.get("submitter_id") != submitter_q and sub_row.get("submitted_by") != submitter_q:
                continue
        cr = sub_row["created"]
        if date_from and cr < date_from:
            continue
        if date_to and cr > date_to:
            continue
        det_raw = ev.get("evaluation_details")
        snip, _ = _evaluation_snippet_and_body(det_raw, include_outputs)
        mem_raw.append({
            "submission_id": sub_row["id"],
            "dataset_name": dname,
            "task_type": None,
            "model_name": sub_row["model_name"],
            "submitted_by": sub_row.get("submitted_by"),
            "submitter_id": sub_row.get("submitter_id"),
            "score": float(ev["score"]),
            "created": cr,
            "evaluation_snippet": snip,
            "_det_raw": det_raw,
            "_model_results": sub_row.get("model_results") if include_outputs else None,
            "_id": sub_row["id"],
        })
    mem_raw.sort(key=lambda x: (x["created"], x["_id"]), reverse=True)
    total = len(mem_raw)
    if use_cursor:
        page_rows = []
        for r in mem_raw:
            if (r["created"] < anchor_c) or (r["created"] == anchor_c and r["_id"] < anchor_id):
                page_rows.append(r)
            if len(page_rows) >= page_size:
                break
    else:
        page_rows = mem_raw[offset:offset + page_size]

    items = []
    for r in page_rows:
        o = {
            "submission_id": r["submission_id"],
            "dataset_name": r["dataset_name"],
            "task_type": r["task_type"],
            "model_name": r["model_name"],
            "submitted_by": r["submitted_by"],
            "submitter_id": r["submitter_id"],
            "score": r["score"],
            "created": r["created"].isoformat() if r.get("created") else None,
            "evaluation_snippet": r["evaluation_snippet"],
        }
        if include_outputs:
            ed = r["_det_raw"]
            if isinstance(ed, str):
                try:
                    ed = json.loads(ed)
                except Exception:
                    ed = {"raw": ed}
            o["evaluation_details"] = ed if isinstance(ed, dict) else {"raw": ed}
            o["model_results"] = r["_model_results"]
        items.append(o)
    out = {
        "success": True,
        "submissions": items,
        "page": page if not use_cursor else None,
        "page_size": page_size,
        "total": total,
    }
    adm_more = len(page_rows) == page_size and (use_cursor or offset + page_size < total)
    if adm_more and page_rows:
        last = page_rows[-1]
        out["next_cursor"] = my_submissions_cursor_encode(last["created"].isoformat(), int(last["_id"]))
    return jsonify(out)


@app.get("/public/submissions/<int:submission_id>")
def submission_detail(submission_id: int):
    """Single submission row if it belongs to the requester (JWT or submitter_id query + API key)."""
    sub = jwt_sub_from_request(request)
    if not sub:
        configured = [k.strip() for k in os.getenv("LEADERBOARD_API_KEYS", "").split(",") if k.strip()]
        require_key = os.getenv("REQUIRE_API_KEY", "").lower() in {"1", "true", "yes"} or bool(configured)
        if require_key:
            supplied = request.headers.get("X-API-Key", "")
            if supplied not in configured:
                return jsonify({"success": False, "error": "Unauthorized"}), 401
        sub = (request.args.get("submitter_id") or "").strip()
    if not sub:
        return jsonify({"success": False, "error": "JWT or submitter_id required"}), 400

    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            try:
                cursor.execute(
                    "SELECT ms.id, ms.model_name, ms.submitted_by, ms.submitter_id, ms.model_results, ms.created, "
                    "bd.name AS dataset_name, bd.task_type, bd.evaluation_metric, er.score, er.evaluation_details "
                    "FROM model_submissions ms "
                    "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                    "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                    "WHERE ms.id = %s",
                    (submission_id,),
                )
            except Exception:
                cursor.execute(
                    "SELECT ms.id, ms.model_name, ms.submitted_by, ms.model_results, ms.created, "
                    "bd.name AS dataset_name, bd.task_type, bd.evaluation_metric, er.score, er.evaluation_details "
                    "FROM model_submissions ms "
                    "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                    "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                    "WHERE ms.id = %s",
                    (submission_id,),
                )
            r = cursor.fetchone()
            if not r:
                return jsonify({"success": False, "error": "Not found"}), 404
            owner = (r.get("submitter_id") or r.get("submitted_by") or "")
            if owner != sub:
                return jsonify({"success": False, "error": "Forbidden"}), 403
            det = {}
            if r.get("evaluation_details"):
                try:
                    det = json.loads(r["evaluation_details"]) if isinstance(r["evaluation_details"], str) else r["evaluation_details"]
                except Exception:
                    det = {}
            mr = r.get("model_results")
            if isinstance(mr, str):
                try:
                    mr = json.loads(mr)
                except Exception:
                    pass
            return jsonify({
                "success": True,
                "submission": {
                    "submission_id": r["id"],
                    "dataset_name": r["dataset_name"],
                    "task_type": r.get("task_type"),
                    "evaluation_metric": r.get("evaluation_metric"),
                    "model_name": r["model_name"],
                    "submitted_by": r.get("submitted_by"),
                    "model_results": mr,
                    "score": float(r["score"]),
                    "metric": det.get("metric") if isinstance(det, dict) else None,
                    "detailed_scores": det.get("detailed_scores") if isinstance(det, dict) else None,
                    "metadata": det.get("metadata") if isinstance(det, dict) else None,
                    "submitted_at": r["created"].isoformat() if r.get("created") else None,
                },
            })
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

    sub_row = next((s for s in _STORE["submissions"] if s["id"] == submission_id), None)
    if not sub_row:
        return jsonify({"success": False, "error": "Not found"}), 404
    owner = sub_row.get("submitter_id") or sub_row.get("submitted_by")
    if owner != sub:
        return jsonify({"success": False, "error": "Forbidden"}), 403
    ev = next((e for e in _STORE["evaluations"] if e["submission_id"] == submission_id), None)
    if not ev:
        return jsonify({"success": False, "error": "Not found"}), 404
    det = ev.get("evaluation_details") or {}
    return jsonify({
        "success": True,
        "submission": {
            "submission_id": sub_row["id"],
            "dataset_name": sub_row["benchmark_dataset_name"],
            "model_name": sub_row["model_name"],
            "submitted_by": sub_row.get("submitted_by"),
            "model_results": sub_row.get("results"),
            "score": ev["score"],
            "metric": det.get("metric"),
            "detailed_scores": det.get("detailed_scores"),
            "metadata": det.get("metadata"),
            "submitted_at": sub_row["created"].isoformat(),
        },
    })


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


def _dataset_details_payload(dataset_core: dict, top_models: list) -> dict:
    """Attach normalized task type, primary metric docs, and per-task metric catalog."""
    tt = dataset_core.get("task_type") or "translation"
    em = dataset_core.get("evaluation_metric") or ""
    tn = normalize_task_type_for_metrics(tt)
    pmd = primary_metric_catalog_entry(em)
    rec = metrics_for_task(tn)
    dataset_out = {
        **dataset_core,
        "task_type_normalized": tn,
        "primary_metric_documentation": pmd,
        "recommended_metrics_for_task": rec,
    }
    return {"success": True, "dataset": dataset_out, "top_models": top_models}


@app.get('/public/dataset_details')
def dataset_details():
    """Return detailed information about a dataset, including curation meta and top models."""
    raw = request.args.get('name')
    if not raw:
        return jsonify({"success": False, "error": "Missing name"}), 400
    name = raw.strip()
    name_lower = name.lower()

    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute(
                "SELECT id, name, task_type, evaluation_metric, reference_data, created, active "
                "FROM benchmark_datasets WHERE name = %s OR LOWER(TRIM(name)) = LOWER(TRIM(%s))",
                (name, name),
            )
            ds = cursor.fetchone()
            if ds:
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

                cursor.execute(
                    "SELECT ms.model_name, er.score, ms.created as submitted_at "
                    "FROM model_submissions ms JOIN evaluation_results er ON er.model_submission_id = ms.id "
                    "WHERE ms.benchmark_dataset_id = %s ORDER BY er.score DESC LIMIT 10",
                    (ds['id'],),
                )
                rows = cursor.fetchall()
                top_models = [
                    {
                        "model": r['model_name'],
                        "score": float(r['score']),
                        "updated": r['submitted_at'].isoformat() if r.get('submitted_at') else None,
                    }
                    for r in rows
                ]
                core = {
                    "name": ds['name'],
                    "task_type": ds['task_type'],
                    "evaluation_metric": ds['evaluation_metric'],
                    **meta,
                    "size": count,
                    "examples": examples,
                }
                return jsonify(_dataset_details_payload(core, top_models))
        except Exception as e:
            logger.exception("dataset_details_db_error", extra={"error": str(e)})
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

    matched = next((d for d in LEADERBOARD_DATA if (d.get('name') or '').lower() == name_lower), None)
    stored = next((d for d in _STORE["datasets"] if (d.get("name") or "").lower() == name_lower), None)
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
    if not matched and name_lower.startswith('flores_spanish_translation'):
        matched = {
            "name": name,
            "task_type": "translation",
            "evaluation_metric": "bleu",
            "description": "FLORES-style demo",
            "url": None,
        }
    if not matched:
        return jsonify({"success": False, "error": "Dataset not found"}), 404

    mem = []
    for ev in _STORE['evaluations']:
        sub = next((s for s in _STORE['submissions'] if s['id'] == ev['submission_id']), None)
        if sub and (sub.get('benchmark_dataset_name') or '').lower() == name_lower:
            mem.append({"model": sub['model_name'], "score": ev['score'], "updated": sub['created'].isoformat()})
    mem.sort(key=lambda x: x['score'], reverse=True)
    examples = matched.get("examples") or _SPANISH_REFERENCES[:5]
    core = {
        "name": matched.get('name'),
        "task_type": matched.get('task_type', 'translation'),
        "evaluation_metric": matched.get('evaluation_metric', 'bleu'),
        "url": matched.get('url'),
        "description": matched.get('description'),
        "size": matched.get("size"),
        "examples": examples,
    }
    return jsonify(_dataset_details_payload(core, mem[:10]))


@app.get('/api/metrics')
def list_metrics():
    """Return metric metadata for UI help text and docs clients."""
    return jsonify({"success": True, "metrics": METRICS_CATALOG})


@app.get('/api/metrics/task/<task_type>')
def list_task_metrics(task_type):
    """Return recommended metrics for a specific task type."""
    nt = normalize_task_type_for_metrics(task_type)
    return jsonify({
        "success": True,
        "task_type": task_type,
        "task_type_normalized": nt,
        "metrics": metrics_for_task(task_type),
    })


@app.get("/public/auth/google/start")
def google_oauth_start():
    """Begin Google OAuth (requires ``GOOGLE_CLIENT_ID`` and Authlib)."""
    if _OAUTH is None:
        return jsonify({"success": False, "error": "OAuth not configured"}), 501
    redirect_uri = os.getenv("LEADERBOARD_OAUTH_REDIRECT_URI", "").strip()
    if not redirect_uri:
        redirect_uri = request.url_root.rstrip("/") + "/public/auth/google/callback"
    return _OAUTH.google.authorize_redirect(redirect_uri)


@app.get("/public/auth/google/callback")
def google_oauth_callback():
    """OAuth callback: mint HS256 JWT (``LEADERBOARD_JWT_SECRET``) and redirect to the SPA."""
    if _OAUTH is None:
        return jsonify({"success": False, "error": "OAuth not configured"}), 501
    secret = os.getenv("LEADERBOARD_JWT_SECRET", "").strip()
    if not secret:
        return jsonify({"success": False, "error": "LEADERBOARD_JWT_SECRET required for OAuth login"}), 500
    try:
        token = _OAUTH.google.authorize_access_token()
    except Exception as e:
        logger.warning("google_oauth_failed", extra={"error": str(e)})
        return jsonify({"success": False, "error": "OAuth authorization failed"}), 400
    try:
        ui = token.get("userinfo")
        if not ui:
            resp = _OAUTH.google.get("https://www.googleapis.com/oauth2/v3/userinfo", token=token)
            ui = resp.json()
        sub = (ui.get("email") or ui.get("sub") or "").strip()
    except Exception as e:
        logger.warning("google_userinfo_failed", extra={"error": str(e)})
        return jsonify({"success": False, "error": "Could not read Google profile"}), 400
    if not sub:
        return jsonify({"success": False, "error": "No user identifier from Google"}), 400
    try:
        import jwt as pyjwt

        body = {
            "sub": sub[:255],
            "exp": int((utc_now() + timedelta(hours=24)).timestamp()),
        }
        jwt_token = pyjwt.encode(body, secret, algorithm="HS256")
        if isinstance(jwt_token, bytes):
            jwt_token = jwt_token.decode("ascii")
    except Exception as e:
        logger.exception("jwt_issue_failed", extra={"error": str(e)})
        return jsonify({"success": False, "error": "Token issue failed"}), 500
    front = os.getenv("LEADERBOARD_FRONTEND_URL", "http://localhost:3000").rstrip("/")
    return redirect(f"{front}/oauth/callback#access_token={quote(jwt_token, safe='')}")


@app.get('/openapi.json')
def openapi_spec():
    """Small OpenAPI document for public integration endpoints."""
    submit_schema = {
        "type": "object",
        "required": ["benchmarkDatasetName", "modelName", "modelResults", "sentence_ids"],
        "properties": {
            "benchmarkDatasetName": {"type": "string"},
            "modelName": {"type": "string"},
            "submittedBy": {"type": "string"},
            "submitterId": {"type": "string", "description": "Opaque id for my_submissions when not using JWT"},
            "sentence_ids": {"type": "array", "items": {"type": "integer"}},
            "modelResults": {"type": "array", "items": {"type": "string"}},
            "metadata": {"type": "object"},
            "async": {"type": "boolean", "description": "If true, returns 202 with job_id; poll GET /public/eval_jobs/{job_id}"},
        },
    }
    return jsonify({
        "openapi": "3.0.3",
        "info": {"title": "Anote Leaderboard API", "version": "0.4.0"},
        "components": {
            "securitySchemes": {
                "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "JWT with required sub claim; HS256 (LEADERBOARD_JWT_SECRET) or JWKS (ANOTE_JWKS_URL).",
                },
                "AdminKeyAuth": {"type": "apiKey", "in": "header", "name": "X-Admin-Key"},
            }
        },
        "paths": {
            "/public/datasets": {"get": {"summary": "List public datasets"}},
            "/public/add_dataset": {"post": {"summary": "Create a public dataset", "security": [{"ApiKeyAuth": []}, {"BearerAuth": []}]}},
            "/public/import_hf_dataset": {"post": {"summary": "Import a Hugging Face dataset split", "security": [{"ApiKeyAuth": []}, {"BearerAuth": []}]}},
            "/api/datasets/ingest": {"post": {"summary": "Ingest a dataset from a configured source", "security": [{"ApiKeyAuth": []}, {"BearerAuth": []}]}},
            "/public/submission_format": {
                "get": {
                    "summary": "Expected submit_model JSON for a dataset",
                    "parameters": [{"name": "dataset", "in": "query", "required": True, "schema": {"type": "string"}}],
                }
            },
            "/public/submit_model": {
                "post": {
                    "summary": "Submit model outputs for evaluation",
                    "security": [{"ApiKeyAuth": []}, {"BearerAuth": []}],
                    "requestBody": {"content": {"application/json": {"schema": submit_schema}}},
                    "responses": {
                        "200": {"description": "Sync result", "content": {"application/json": {"schema": {"type": "object"}}}},
                        "202": {"description": "Async accepted when async=true"},
                    },
                }
            },
            "/public/eval_jobs/{job_id}": {"get": {"summary": "Poll async submit job status"}},
            "/public/my_submissions": {
                "get": {
                    "summary": "List submissions for JWT sub or submitter_id query",
                    "parameters": [
                        {"name": "submitter_id", "in": "query", "schema": {"type": "string"}},
                        {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                        {"name": "page_size", "in": "query", "schema": {"type": "integer", "default": 25}},
                        {
                            "name": "cursor",
                            "in": "query",
                            "schema": {"type": "string"},
                            "description": "Opaque keyset cursor; when set, page is ignored. Sort: created DESC, id DESC.",
                        },
                    ],
                }
            },
            "/public/submissions/{submission_id}": {
                "get": {
                    "summary": "Submission detail (owner scoped)",
                    "parameters": [{"name": "submission_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                }
            },
            "/public/get_leaderboard": {
                "get": {
                    "summary": "Get leaderboard rows",
                    "description": "Sort: dataset_name ASC, score DESC, submission_id DESC. Offset via page, or keyset via cursor (cursor ignores page).",
                    "parameters": [
                        {"name": "dataset", "in": "query", "schema": {"type": "string"}},
                        {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                        {"name": "page_size", "in": "query", "schema": {"type": "integer", "default": 25}},
                        {"name": "limit", "in": "query", "schema": {"type": "integer"}, "description": "Alias for page_size"},
                        {
                            "name": "cursor",
                            "in": "query",
                            "schema": {"type": "string"},
                            "description": "Opaque keyset cursor; response may include next_cursor",
                        },
                    ],
                }
            },
            "/public/export/leaderboard": {
                "get": {
                    "summary": "Export leaderboard rows as CSV or JSON",
                    "description": "CSV includes primary_metric and detailed_scores_json; walks all pages via cursor internally.",
                }
            },
            "/public/auth/google/start": {"get": {"summary": "Redirect to Google OAuth (optional; requires Authlib + GOOGLE_CLIENT_ID)"}},
            "/public/auth/google/callback": {"get": {"summary": "OAuth callback; redirects to LEADERBOARD_FRONTEND_URL/oauth/callback#access_token=…"}},
            "/api/admin/submissions": {
                "get": {
                    "summary": "Admin: list submissions (moderation)",
                    "security": [{"AdminKeyAuth": []}],
                    "parameters": [
                        {"name": "dataset", "in": "query", "schema": {"type": "string"}},
                        {"name": "submitter_id", "in": "query", "schema": {"type": "string"}},
                        {"name": "from", "in": "query", "schema": {"type": "string", "format": "date-time"}},
                        {"name": "to", "in": "query", "schema": {"type": "string", "format": "date-time"}},
                        {"name": "page", "in": "query", "schema": {"type": "integer"}},
                        {"name": "page_size", "in": "query", "schema": {"type": "integer"}},
                        {"name": "cursor", "in": "query", "schema": {"type": "string"}},
                        {"name": "include_outputs", "in": "query", "schema": {"type": "string"}, "description": "1/true to include full evaluation_details and model_results"},
                    ],
                }
            },
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
            leaderboard_dataset_id=data.get("leaderboard_dataset_id") or data.get("dataset_id"),
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
        "leaderboard_dataset_id": data.get("leaderboard_dataset_id") or data.get("dataset_id"),
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
    """Export leaderboard rows as CSV or JSON (follows keyset cursors until exhausted)."""
    dataset_name = request.args.get("dataset")
    export_format = (request.args.get("format") or "json").lower()
    rows = []
    next_cur = None
    while True:
        qs: dict = {"page_size": "100"}
        if dataset_name:
            qs["dataset"] = dataset_name
        if next_cur:
            qs["cursor"] = next_cur
        with app.test_request_context("/public/get_leaderboard", query_string=qs):
            payload = get_leaderboard().get_json()
        if not payload or not payload.get("success"):
            break
        chunk = payload.get("leaderboard") or []
        rows.extend(chunk)
        next_cur = payload.get("next_cursor")
        if not next_cur:
            break
    if export_format == "json":
        return jsonify(rows)
    if export_format != "csv":
        return jsonify({"success": False, "error": "format must be csv or json"}), 400

    out = StringIO()
    fieldnames = [
        "rank",
        "submission_id",
        "dataset_name",
        "model_name",
        "submitted_by",
        "score",
        "evaluation_metric",
        "primary_metric",
        "detailed_scores_json",
        "submitted_at",
    ]
    writer = csv.DictWriter(out, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        ds = row.get("detailed_scores")
        writer.writerow({
            "rank": row.get("rank"),
            "submission_id": row.get("submission_id"),
            "dataset_name": row.get("dataset_name"),
            "model_name": row.get("model_name"),
            "submitted_by": row.get("submitted_by"),
            "score": row.get("score"),
            "evaluation_metric": row.get("evaluation_metric"),
            "primary_metric": row.get("primary_metric"),
            "detailed_scores_json": json.dumps(ds, ensure_ascii=False, default=str) if ds is not None else "",
            "submitted_at": row.get("submitted_at"),
        })
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
