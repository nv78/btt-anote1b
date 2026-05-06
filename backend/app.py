import os
import sys
import types

from flask import Flask
from flask_cors import CORS

from blueprints import leaderboard as _leaderboard


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

    _leaderboard._OAUTH = _leaderboard._init_google_oauth(flask_app)
    flask_app.register_blueprint(_leaderboard.bp)
    return flask_app


app = create_app()

# Backward-compatible exports used by tests and local scripts.
_STORE = _leaderboard._STORE
LEADERBOARD_DATA = _leaderboard.LEADERBOARD_DATA
_EVAL_JOBS = _leaderboard._EVAL_JOBS
_EVAL_JOBS_LOCK = _leaderboard._EVAL_JOBS_LOCK

utc_now = _leaderboard.utc_now
get_db_connection = _leaderboard.get_db_connection
require_api_key = _leaderboard.require_api_key
require_admin = _leaderboard.require_admin
rate_limit = _leaderboard.rate_limit
logger = _leaderboard.logger
_run_hf_predictions = _leaderboard._run_hf_predictions
_AUTO_SEED_DONE = _leaderboard._AUTO_SEED_DONE


class _CompatModule(types.ModuleType):
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if hasattr(_leaderboard, name):
            setattr(_leaderboard, name, value)


sys.modules[__name__].__class__ = _CompatModule


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_ENV") == "development")
