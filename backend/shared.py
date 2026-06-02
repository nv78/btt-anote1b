import os
import hmac
import hashlib

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

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

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


def api_key_matches(supplied: str | None, configured: list[str]) -> bool:
    supplied_key = (supplied or "").strip()
    return bool(supplied_key) and any(hmac.compare_digest(supplied_key, key) for key in configured)


def parse_bounded_int(
    value: Any,
    field: str,
    default: int,
    *,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    if value in (None, ""):
        out = default
    else:
        try:
            out = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be an integer") from exc
    if min_value is not None:
        out = max(min_value, out)
    if max_value is not None:
        out = min(max_value, out)
    return out


def _consume_submission_quota(submitter_id: str) -> tuple[bool, int, str]:
    now = utc_now()
    day = now.date().isoformat()
    limit = daily_submission_limit()
    key = f"{submitter_id}:{day}"
    resets_at = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=1)
    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS daily_submission_usage ("
                "submitter_id VARCHAR(255) NOT NULL, "
                "usage_day VARCHAR(10) NOT NULL, "
                "used_count INTEGER NOT NULL DEFAULT 0, "
                "updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                "PRIMARY KEY (submitter_id, usage_day)"
                ")"
            )
            conn.commit()
            is_sqlite = isinstance(cursor, SQLiteCursorAdapter)
            if is_sqlite:
                conn.execute("BEGIN IMMEDIATE")
                cursor.execute(
                    "SELECT used_count FROM daily_submission_usage WHERE submitter_id = %s AND usage_day = %s",
                    (submitter_id, day),
                )
            else:
                try:
                    conn.start_transaction()
                except Exception:
                    cursor.execute("START TRANSACTION")
                cursor.execute(
                    "SELECT used_count FROM daily_submission_usage WHERE submitter_id = %s AND usage_day = %s FOR UPDATE",
                    (submitter_id, day),
                )
            row = cursor.fetchone()
            used = int((row or {}).get("used_count", 0))
            if limit > 0 and used >= limit:
                conn.rollback()
                return False, 0, resets_at.isoformat()
            next_used = used + 1
            if row:
                cursor.execute(
                    "UPDATE daily_submission_usage SET used_count = %s, updated_at = CURRENT_TIMESTAMP "
                    "WHERE submitter_id = %s AND usage_day = %s",
                    (next_used, submitter_id, day),
                )
            else:
                cursor.execute(
                    "INSERT INTO daily_submission_usage (submitter_id, usage_day, used_count) VALUES (%s, %s, %s)",
                    (submitter_id, day, next_used),
                )
            conn.commit()
            return True, max(0, limit - next_used), resets_at.isoformat()
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.exception("submission_quota_db_failed", extra={"error": str(exc)})
            return False, 0, resets_at.isoformat()
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass
    with _QUOTA_LOCK:
        counts = _STORE.setdefault("submission_counts", {})
        used = int(counts.get(key, 0))
        if limit > 0 and used >= limit:
            return False, 0, resets_at.isoformat()
        counts[key] = used + 1
        remaining = max(0, limit - counts[key])
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
        if api_key_matches(supplied, configured):
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
        supplied = request.headers.get("X-Admin-Key") or request.headers.get("X-API-Key")
        authed = api_key_matches(supplied, keys)
        if not authed:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return fn(*args, **kwargs)

    return wrapper


_RATE_WINDOWS = defaultdict(deque)


def _consume_db_rate_limit(rate_key: str, window_start: int, max_calls: int) -> bool | None:
    conn, cursor = get_db_connection()
    if not conn or not cursor:
        return None
    try:
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS request_rate_usage ("
            "rate_key VARCHAR(255) NOT NULL, "
            "window_start INTEGER NOT NULL, "
            "used_count INTEGER NOT NULL DEFAULT 0, "
            "updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "PRIMARY KEY (rate_key, window_start)"
            ")"
        )
        conn.commit()
        is_sqlite = isinstance(cursor, SQLiteCursorAdapter)
        if is_sqlite:
            conn.execute("BEGIN IMMEDIATE")
            cursor.execute(
                "SELECT used_count FROM request_rate_usage WHERE rate_key = %s AND window_start = %s",
                (rate_key, window_start),
            )
        else:
            try:
                conn.start_transaction()
            except Exception:
                cursor.execute("START TRANSACTION")
            cursor.execute(
                "SELECT used_count FROM request_rate_usage WHERE rate_key = %s AND window_start = %s FOR UPDATE",
                (rate_key, window_start),
            )
        row = cursor.fetchone()
        used = int((row or {}).get("used_count", 0))
        if used >= max_calls:
            conn.rollback()
            return False
        next_used = used + 1
        if row:
            cursor.execute(
                "UPDATE request_rate_usage SET used_count = %s, updated_at = CURRENT_TIMESTAMP "
                "WHERE rate_key = %s AND window_start = %s",
                (next_used, rate_key, window_start),
            )
        else:
            cursor.execute(
                "INSERT INTO request_rate_usage (rate_key, window_start, used_count) VALUES (%s, %s, %s)",
                (rate_key, window_start, next_used),
            )
        cutoff = window_start - 3600
        cursor.execute("DELETE FROM request_rate_usage WHERE window_start < %s", (cutoff,))
        conn.commit()
        return True
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("request_rate_limit_db_failed", extra={"error": str(exc)})
        return False
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


def rate_limit(env_name, default_limit):
    """Shared per-minute limiter for write/evaluation endpoints.

    Uses the configured DB when available; falls back to in-process storage only when no DB can be opened.
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
            raw_key = f"{request.remote_addr or 'unknown'}:{request.path}"
            db_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
            db_allowed = _consume_db_rate_limit(db_key, int(now // 60) * 60, max_calls)
            if db_allowed is False:
                return jsonify({"success": False, "error": "Rate limit exceeded"}), 429
            if db_allowed is True:
                return fn(*args, **kwargs)
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

# Quota counter lock — prevents concurrent requests from the same user bypassing daily limit.
_QUOTA_LOCK = threading.Lock()

# UI-oriented datasets store (for add_dataset/add_model endpoints)
LEADERBOARD_DATA = []  # list of dicts with fields per README
_LD_LOCK = threading.RLock()  # protects LEADERBOARD_DATA mutations


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
