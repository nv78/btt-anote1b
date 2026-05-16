import os
import sys
import types

from flask import Flask, jsonify
from flask_cors import CORS

import shared
from blueprints import admin as _admin
from blueprints import auth as _auth
from blueprints import dataset_requests as _dataset_requests
from blueprints import eval as _eval
from blueprints import leaderboard as _leaderboard
from blueprints import metrics as _metrics
from blueprints import submissions as _submissions


_BLUEPRINT_MODULES = [_leaderboard, _submissions, _eval, _auth, _admin, _metrics, _dataset_requests]


def _allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS")
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    if os.getenv("FLASK_ENV", "development").lower() == "development":
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ]
    raise RuntimeError("ALLOWED_ORIGINS must be set outside development")


def create_app() -> Flask:
    flask_app = Flask(__name__)
    flask_app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-insecure-change-me")
    flask_app.config["JSON_SORT_KEYS"] = False
    CORS(flask_app, resources={r"/*": {"origins": _allowed_origins()}})

    oauth = shared._init_google_oauth(flask_app)
    shared._OAUTH = oauth
    _auth._OAUTH = oauth
    flask_app.after_request(shared.add_compatible_response_envelope)
    for mod in _BLUEPRINT_MODULES:
        flask_app.register_blueprint(mod.bp)
    return flask_app


app = create_app()


@app.before_request
def _auto_seed_once_for_app_routes() -> None:
    _leaderboard._auto_seed_once()


@app.get("/")
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
            "/public/submission_quota",
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


@app.get("/health")
def health():
    return jsonify({"ok": True, "time": shared.utc_now().isoformat()})


@app.get("/openapi.json")
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
            "/public/run_hf_model": {"post": {"summary": "Run a Hugging Face model on an imported dataset", "security": [{"ApiKeyAuth": []}, {"BearerAuth": []}]}},
            "/api/datasets/ingest": {"post": {"summary": "Ingest a dataset from a configured source", "security": [{"ApiKeyAuth": []}, {"BearerAuth": []}]}},
            "/public/submission_format": {
                "get": {
                    "summary": "Expected submit_model JSON for a dataset",
                    "parameters": [{"name": "dataset", "in": "query", "required": True, "schema": {"type": "string"}}],
                }
            },
            "/public/dataset_questions": {
                "get": {
                    "summary": "Dataset inputs/questions without labels",
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
            "/public/submission_quota": {
                "get": {
                    "summary": "Return today's submission quota usage",
                    "parameters": [{"name": "submitter_id", "in": "query", "schema": {"type": "string"}}],
                }
            },
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
            "/api/leaderboard/seed": {"post": {"summary": "Admin: seed the 10 built-in benchmark datasets", "security": [{"AdminKeyAuth": []}]}},
            "/api/metrics": {"get": {"summary": "List metric metadata"}},
            "/api/metrics/task/{task_type}": {"get": {"summary": "List metrics for a task type"}},
        },
    })

# Backward-compatible exports used by tests and local scripts.
_STORE = shared._STORE
LEADERBOARD_DATA = shared.LEADERBOARD_DATA
_EVAL_JOBS = shared._EVAL_JOBS
_EVAL_JOBS_LOCK = shared._EVAL_JOBS_LOCK

utc_now = shared.utc_now
get_db_connection = shared.get_db_connection
require_api_key = shared.require_api_key
require_admin = shared.require_admin
rate_limit = shared.rate_limit
logger = shared.logger
_run_hf_predictions = _eval._run_hf_predictions
_AUTO_SEED_DONE = _leaderboard._AUTO_SEED_DONE


class _CompatModule(types.ModuleType):
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        for mod in [shared, *_BLUEPRINT_MODULES]:
            if hasattr(mod, name):
                setattr(mod, name, value)


sys.modules[__name__].__class__ = _CompatModule


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_ENV") == "development")
