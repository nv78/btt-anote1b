"""Tests for Bug #8 fix: eval job ownership check on GET /public/eval_jobs/<job_id>."""
from __future__ import annotations

import pytest

try:
    import app as app_module
except ImportError:
    import backend.app as app_module  # type: ignore

app = app_module.app


def reset_store() -> None:
    app_module._STORE["submissions"].clear()
    app_module._STORE["evaluations"].clear()
    app_module._STORE["datasets"].clear()
    app_module._STORE.setdefault("submission_counts", {}).clear()
    app_module.LEADERBOARD_DATA.clear()
    app_module._AUTO_SEED_DONE = False


def reset_jobs() -> None:
    from blueprints.submissions import _EVAL_JOBS
    _EVAL_JOBS.clear()


def test_owner_can_poll_job(monkeypatch):
    """The client that created a job can poll its status."""
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()
    reset_jobs()

    from blueprints.submissions import _EVAL_JOBS
    import uuid, time

    job_id = str(uuid.uuid4())
    _EVAL_JOBS[job_id] = {
        "status": "completed",
        "_created": time.time(),
        "_owner": "127.0.0.1",
        "score": 0.9,
        "metric": "accuracy",
    }

    with app.test_client() as c:
        r = c.get(f"/public/eval_jobs/{job_id}", environ_base={"REMOTE_ADDR": "127.0.0.1"})
        assert r.status_code == 200
        body = r.get_json()
        assert body["success"] is True
        assert body["score"] == pytest.approx(0.9)
        # Private fields must be stripped from response
        assert "_owner" not in body
        assert "_created" not in body


def test_other_ip_cannot_poll_job(monkeypatch):
    """A different IP receives 404 (not 403) to avoid leaking job existence."""
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()
    reset_jobs()

    from blueprints.submissions import _EVAL_JOBS
    import uuid, time

    job_id = str(uuid.uuid4())
    _EVAL_JOBS[job_id] = {
        "status": "completed",
        "_created": time.time(),
        "_owner": "10.0.0.1",
        "score": 0.5,
    }

    with app.test_client() as c:
        r = c.get(f"/public/eval_jobs/{job_id}", environ_base={"REMOTE_ADDR": "10.0.0.2"})
        assert r.status_code == 404
        assert r.get_json()["success"] is False


def test_missing_job_returns_404(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()
    reset_jobs()

    with app.test_client() as c:
        r = c.get("/public/eval_jobs/nonexistent-job-id")
        assert r.status_code == 404


def test_private_fields_stripped_from_response(monkeypatch):
    """_owner and _created must never appear in the API response."""
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()
    reset_jobs()

    from blueprints.submissions import _EVAL_JOBS
    import uuid, time

    job_id = str(uuid.uuid4())
    ip = "192.168.1.50"
    _EVAL_JOBS[job_id] = {
        "status": "pending",
        "_created": time.time(),
        "_owner": ip,
        "batches_done": 0,
        "total_batches": 5,
    }

    with app.test_client() as c:
        r = c.get(f"/public/eval_jobs/{job_id}", environ_base={"REMOTE_ADDR": ip})
        assert r.status_code == 200
        body = r.get_json()
        for key in body:
            assert not key.startswith("_"), f"Private field '{key}' leaked in response"
