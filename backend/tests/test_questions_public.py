"""Tests for the questions_public flag: admin toggle and visibility enforcement."""
from __future__ import annotations

import os
import pytest

try:
    import app as app_module
except ImportError:
    import backend.app as app_module  # type: ignore

app = app_module.app
DATASET = "SST-2 Sentiment (Sample)"
ADMIN_KEY = "test-admin-key-123"


def reset_store() -> None:
    app_module._STORE["submissions"].clear()
    app_module._STORE["evaluations"].clear()
    app_module._STORE["datasets"].clear()
    app_module._STORE.setdefault("submission_counts", {}).clear()
    app_module.LEADERBOARD_DATA.clear()
    app_module._AUTO_SEED_DONE = False


def get_dataset(store):
    return next((d for d in app_module._STORE["datasets"] if d["name"] == DATASET), None)


# ── questions_public visibility ────────────────────────────────────────────

def test_questions_public_by_default(monkeypatch):
    """Questions are public by default — endpoint returns full text."""
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_AUTO_SEED_IN_TESTS", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        c.get("/health")
        r = c.get("/public/dataset_questions", query_string={"dataset": DATASET})
        assert r.status_code == 200
        body = r.get_json()
        assert body["success"] is True
        assert len(body["questions"]) > 0
        assert body["questions"][0]["input"]  # text is present


def test_hidden_questions_return_200_with_count(monkeypatch):
    """When questions_public=False, GET /dataset_questions returns 200 with metadata but no text."""
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_AUTO_SEED_IN_TESTS", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        c.get("/health")
        # Directly flip the in-memory flag
        ds = get_dataset(app_module._STORE)
        assert ds is not None
        ds["questions_public"] = False

        r = c.get("/public/dataset_questions", query_string={"dataset": DATASET})
        assert r.status_code == 200
        body = r.get_json()
        assert body["success"] is True
        assert body.get("questions_public") is False
        assert "question_count" in body or "questions" not in body


# ── Admin endpoint ─────────────────────────────────────────────────────────

def test_admin_toggle_requires_key(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_AUTO_SEED_IN_TESTS", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        c.get("/health")
        r = c.patch(
            f"/api/admin/datasets/{DATASET}/questions_public",
            json={"questions_public": False},
        )
        # No admin key → 503 (not configured) or 401
        assert r.status_code in (401, 503)


def test_admin_toggle_with_valid_key(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_AUTO_SEED_IN_TESTS", "1")
    monkeypatch.setenv("LEADERBOARD_ADMIN_API_KEYS", ADMIN_KEY)
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        c.get("/health")

        # Hide questions
        r = c.patch(
            f"/api/admin/datasets/{DATASET}/questions_public",
            json={"questions_public": False},
            headers={"X-Admin-Key": ADMIN_KEY},
        )
        assert r.status_code == 200
        body = r.get_json()
        assert body["success"] is True
        assert body["questions_public"] is False

        # Verify questions are now hidden (200 but questions_public=False, no text)
        r2 = c.get("/public/dataset_questions", query_string={"dataset": DATASET})
        assert r2.status_code == 200
        assert r2.get_json().get("questions_public") is False

        # Show questions again
        r3 = c.patch(
            f"/api/admin/datasets/{DATASET}/questions_public",
            json={"questions_public": True},
            headers={"X-Admin-Key": ADMIN_KEY},
        )
        assert r3.status_code == 200
        assert r3.get_json()["questions_public"] is True

        # Questions visible again
        r4 = c.get("/public/dataset_questions", query_string={"dataset": DATASET})
        assert r4.status_code == 200


def test_admin_toggle_with_wrong_key(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_ADMIN_API_KEYS", ADMIN_KEY)
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        r = c.patch(
            f"/api/admin/datasets/{DATASET}/questions_public",
            json={"questions_public": False},
            headers={"X-Admin-Key": "wrong-key"},
        )
        assert r.status_code == 401
