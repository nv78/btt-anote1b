"""Tests for submission visibility toggle and delete (user privacy controls)."""
from __future__ import annotations

import pytest

try:
    import app as app_module
except ImportError:
    import backend.app as app_module  # type: ignore

app = app_module.app
DATASET = "SST-2 Sentiment (Sample)"
LABELS = ["0", "1", "0", "1", "0", "0", "1", "0", "0", "1",
          "1", "1", "0", "0", "1", "1", "0", "1", "1", "1"]


def reset_store() -> None:
    app_module._STORE["submissions"].clear()
    app_module._STORE["evaluations"].clear()
    app_module._STORE["datasets"].clear()
    app_module._STORE.setdefault("submission_counts", {}).clear()
    app_module.LEADERBOARD_DATA.clear()
    app_module._AUTO_SEED_DONE = False


def submit_model(c, model_name="TestModel", submitter="test-user-sub", is_public=True):
    c.get("/health")
    r = c.post("/public/submit_model", json={
        "benchmarkDatasetName": DATASET,
        "modelName": model_name,
        "modelResults": LABELS,
        "submitterId": submitter,
        "is_public": is_public,
    })
    assert r.status_code == 200
    return r.get_json()["submission_id"]


def make_jwt(sub: str) -> str:
    """Create a minimal HS256 JWT signed with the dev secret."""
    import jwt as pyjwt
    import os
    secret = os.getenv("LEADERBOARD_JWT_SECRET", "dev-secret")
    return pyjwt.encode({"sub": sub}, secret, algorithm="HS256")


def auth_headers(sub: str) -> dict:
    return {"Authorization": f"Bearer {make_jwt(sub)}"}


# ── Visibility toggle ──────────────────────────────────────────────────────

def test_submission_defaults_to_public(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_AUTO_SEED_IN_TESTS", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        sub_id = submit_model(c)
        # Filter by dataset so we don't get lost in seeded models from other datasets
        lb = c.get(f"/public/get_leaderboard?dataset={DATASET}").get_json()
        names = [e["model_name"] for e in lb.get("leaderboard", [])]
        assert "TestModel" in names


def test_private_submission_hidden_from_leaderboard(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_AUTO_SEED_IN_TESTS", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        submit_model(c, model_name="SecretModel", is_public=False)
        lb = c.get(f"/public/get_leaderboard?dataset={DATASET}").get_json()
        names = [e["model_name"] for e in lb.get("leaderboard", [])]
        assert "SecretModel" not in names


def test_toggle_visibility_requires_auth(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_AUTO_SEED_IN_TESTS", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        sub_id = submit_model(c)
        r = c.patch(f"/public/submissions/{sub_id}/visibility",
                    json={"is_public": False})
        assert r.status_code == 401


def test_owner_can_toggle_visibility(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_AUTO_SEED_IN_TESTS", "1")
    monkeypatch.setenv("LEADERBOARD_JWT_SECRET", "dev-secret")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    owner_sub = "user-toggle-test"
    with app.test_client() as c:
        c.get("/health")
        # Submit as owner
        r = c.post("/public/submit_model", json={
            "benchmarkDatasetName": DATASET,
            "modelName": "ToggleModel",
            "modelResults": LABELS,
        }, headers=auth_headers(owner_sub))
        assert r.status_code == 200
        sub_id = r.get_json()["submission_id"]

        # Toggle to private
        patch = c.patch(f"/public/submissions/{sub_id}/visibility",
                        json={"is_public": False},
                        headers=auth_headers(owner_sub))
        assert patch.status_code == 200
        assert patch.get_json()["is_public"] is False

        # Not on leaderboard anymore
        lb = c.get(f"/public/get_leaderboard?dataset={DATASET}").get_json()
        names = [e["model_name"] for e in lb.get("leaderboard", [])]
        assert "ToggleModel" not in names

        # Toggle back to public
        patch2 = c.patch(f"/public/submissions/{sub_id}/visibility",
                         json={"is_public": True},
                         headers=auth_headers(owner_sub))
        assert patch2.status_code == 200
        assert patch2.get_json()["is_public"] is True


# ── Delete ──────────────────────────────────────────────────────────────────

def test_delete_requires_auth(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_AUTO_SEED_IN_TESTS", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        sub_id = submit_model(c)
        r = c.delete(f"/public/submissions/{sub_id}")
        assert r.status_code == 401


def test_owner_can_delete_submission(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_AUTO_SEED_IN_TESTS", "1")
    monkeypatch.setenv("LEADERBOARD_JWT_SECRET", "dev-secret")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    owner_sub = "user-delete-test"
    with app.test_client() as c:
        c.get("/health")
        r = c.post("/public/submit_model", json={
            "benchmarkDatasetName": DATASET,
            "modelName": "DeleteMe",
            "modelResults": LABELS,
        }, headers=auth_headers(owner_sub))
        assert r.status_code == 200
        sub_id = r.get_json()["submission_id"]

        delete = c.delete(f"/public/submissions/{sub_id}",
                          headers=auth_headers(owner_sub))
        assert delete.status_code == 200
        assert delete.get_json()["success"] is True

        # No longer on leaderboard
        lb = c.get(f"/public/get_leaderboard?dataset={DATASET}").get_json()
        names = [e["model_name"] for e in lb.get("leaderboard", [])]
        assert "DeleteMe" not in names


def test_other_user_cannot_delete_submission(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_AUTO_SEED_IN_TESTS", "1")
    monkeypatch.setenv("LEADERBOARD_JWT_SECRET", "dev-secret")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    owner_sub = "real-owner"
    attacker_sub = "attacker"
    with app.test_client() as c:
        c.get("/health")
        r = c.post("/public/submit_model", json={
            "benchmarkDatasetName": DATASET,
            "modelName": "VictimModel",
            "modelResults": LABELS,
        }, headers=auth_headers(owner_sub))
        assert r.status_code == 200
        sub_id = r.get_json()["submission_id"]

        delete = c.delete(f"/public/submissions/{sub_id}",
                          headers=auth_headers(attacker_sub))
        assert delete.status_code in (401, 403, 404)
