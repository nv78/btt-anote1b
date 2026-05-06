import os

# Local dev: load Leaderboard/backend/.env when python-dotenv is installed.
try:
    from pathlib import Path

    from dotenv import load_dotenv

    _bd = Path(__file__).resolve().parent
    load_dotenv(_bd / ".env")
    # Monorepo root .env (e.g. Anote/.env when path is …/Anote/Leaderboard/backend/app.py)
    _root = _bd.parent.parent
    if (_root / ".env").is_file() and (_root / "Leaderboard" / "backend" / "app.py").is_file():
        load_dotenv(_root / ".env", override=True)
except ImportError:
    pass

import json
import csv
import logging
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from functools import wraps
from io import StringIO
from pathlib import Path
import sqlite3
from time import time
from typing import Any
from urllib.parse import quote

from flask import Response, current_app, request, jsonify, redirect
import uuid
import threading

try:
    from auth_helpers import jwt_sub_from_request, resolve_submitter_id
except ImportError:
    from backend.auth_helpers import jwt_sub_from_request, resolve_submitter_id

try:
    from ui_fallback_dataset_catalog import UI_FALLBACK_DATASETS_BY_LOWER_NAME
except ImportError:
    try:
        from backend.ui_fallback_dataset_catalog import UI_FALLBACK_DATASETS_BY_LOWER_NAME
    except ImportError:
        UI_FALLBACK_DATASETS_BY_LOWER_NAME = {}

try:
    from composite_score import enrich_leaderboard_list
except ImportError:
    try:
        from backend.composite_score import enrich_leaderboard_list
    except ImportError:
        def enrich_leaderboard_list(entries):  # type: ignore
            return entries

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

class SQLiteCursorAdapter:
    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor

    @property
    def lastrowid(self) -> Any:
        return self._cursor.lastrowid

    def execute(self, query: str, params: tuple | list = ()) -> "SQLiteCursorAdapter":
        query = query.replace("%s", "?")
        self._cursor.execute(query, tuple(params or ()))
        return self

    def fetchone(self) -> dict[str, Any] | None:
        row = self._cursor.fetchone()
        return _sqlite_row_to_dict(row) if row is not None else None

    def fetchall(self) -> list[dict[str, Any]]:
        return [_sqlite_row_to_dict(row) for row in self._cursor.fetchall()]

    def close(self) -> None:
        self._cursor.close()


def _sqlite_row_to_dict(row: Any) -> dict[str, Any]:
    out = dict(row)
    for key in ("created", "submitted_at"):
        value = out.get(key)
        if isinstance(value, str):
            parsed = _parse_iso_datetime(value.replace(" ", "T"))
            if parsed is not None:
                out[key] = parsed
    return out


def _sqlite_db_path() -> Path:
    return Path(os.getenv("SQLITE_DB_PATH", "./leaderboard.db")).expanduser()


def _open_sqlite_connection() -> tuple[Any, SQLiteCursorAdapter]:
    db_path = _sqlite_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_sqlite_schema(conn)
    return conn, SQLiteCursorAdapter(conn.cursor())


def _ensure_sqlite_schema(conn: Any) -> None:
    schema_path = Path(__file__).resolve().parent / "database" / "schema_leaderboard.sql"
    conn.executescript(schema_path.read_text())
    conn.commit()


def _mysql_connection_configured() -> bool:
    return any(os.getenv(k) for k in ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME", "DB_PORT"))


def get_db_connection() -> tuple[Any | None, Any | None]:
    if _mysql_connection_configured():
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
            logger.warning("mysql_connection_unavailable_using_sqlite", extra={"error": str(e)})
    try:
        return _open_sqlite_connection()
    except Exception as e:
        logger.warning("sqlite_connection_unavailable", extra={"error": str(e)})
        return None, None



LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("leaderboard")

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


_OAUTH = None

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


def daily_submission_limit() -> int:
    try:
        return max(0, int(os.getenv("DAILY_SUBMISSION_LIMIT", "5")))
    except ValueError:
        return 5


def _consume_submission_quota(submitter_id: str) -> tuple[bool, int, str]:
    now = utc_now()
    day = now.date().isoformat()
    limit = daily_submission_limit()
    key = f"{submitter_id}:{day}"
    counts = _STORE.setdefault("submission_counts", {})
    used = int(counts.get(key, 0))
    resets_at = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=1)
    if limit > 0 and used >= limit:
        return False, 0, resets_at.isoformat()
    counts[key] = used + 1
    remaining = max(0, limit - int(counts[key]))
    return True, remaining, resets_at.isoformat()


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


# In-memory fallback storage when DB is not available
_STORE = {
    "submissions": [],  # {id, benchmark_dataset_name, model_name, submitter_id?, results, created}
    "evaluations": [],  # {submission_id, score, metric, evaluation_details?, created}
    "datasets": [],  # {name, task_type, evaluation_metric, reference_data}
    "submission_counts": {},  # {"submitter_id:YYYY-MM-DD": count}
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


__all__ = [name for name in globals() if not name.startswith("__")]
