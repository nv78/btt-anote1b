"""Tests for GET /public/compare_models and GET /public/model_names."""
from __future__ import annotations

import pytest

try:
    import app as app_module
except ImportError:
    import backend.app as app_module  # type: ignore

app = app_module.app
DATASET = "SST-2 Sentiment (Sample)"


def reset_store() -> None:
    app_module._STORE["submissions"].clear()
    app_module._STORE["evaluations"].clear()
    app_module._STORE["datasets"].clear()
    app_module._STORE.setdefault("submission_counts", {}).clear()
    app_module.LEADERBOARD_DATA.clear()
    app_module._AUTO_SEED_DONE = False


def seed_two_models(c):
    """Submit two models to SST-2 and return their scores."""
    c.get("/health")  # triggers auto-seed
    labels = ["0", "1", "0", "1", "0", "0", "1", "0", "0", "1",
              "1", "1", "0", "0", "1", "1", "0", "1", "1", "1"]
    r1 = c.post("/public/submit_model", json={
        "benchmarkDatasetName": DATASET,
        "modelName": "ModelAlpha",
        "modelResults": labels,
        "submitterId": "tester",
    })
    r2 = c.post("/public/submit_model", json={
        "benchmarkDatasetName": DATASET,
        "modelName": "ModelBeta",
        "modelResults": ["0"] * 20,  # all-negative
        "submitterId": "tester",
    })
    return r1.get_json(), r2.get_json()


def test_model_names_returns_list(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_AUTO_SEED_IN_TESTS", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        seed_two_models(c)
        r = c.get("/public/model_names")
        assert r.status_code == 200
        body = r.get_json()
        assert body["success"] is True
        assert isinstance(body["models"], list)
        assert "ModelAlpha" in body["models"]
        assert "ModelBeta" in body["models"]


def test_compare_requires_at_least_two_models(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        r = c.get("/public/compare_models?models=OnlyOne")
        assert r.status_code == 400
        assert r.get_json()["success"] is False


def test_compare_rejects_more_than_ten_models(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        models = ",".join([f"M{i}" for i in range(11)])
        r = c.get(f"/public/compare_models?models={models}")
        assert r.status_code == 400


def test_compare_returns_shared_datasets(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_AUTO_SEED_IN_TESTS", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        seed_two_models(c)
        r = c.get("/public/compare_models?models=ModelAlpha,ModelBeta")
        assert r.status_code == 200
        body = r.get_json()
        assert body["success"] is True
        assert set(body["models"]) == {"ModelAlpha", "ModelBeta"}
        assert len(body["comparisons"]) >= 1
        comp = body["comparisons"][0]
        assert "dataset_name" in comp
        assert "scores" in comp
        assert "ModelAlpha" in comp["scores"]
        assert "ModelBeta" in comp["scores"]


def test_compare_no_shared_datasets(monkeypatch):
    """Models that don't share any dataset return empty comparisons (not an error)."""
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        r = c.get("/public/compare_models?models=Ghost1,Ghost2")
        assert r.status_code == 200
        body = r.get_json()
        assert body["success"] is True
        assert body["comparisons"] == []


def test_compare_scores_are_correct(monkeypatch):
    """ModelAlpha (perfect) should score higher than ModelBeta (all-negative)."""
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_AUTO_SEED_IN_TESTS", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        seed_two_models(c)
        r = c.get("/public/compare_models?models=ModelAlpha,ModelBeta")
        body = r.get_json()
        comp = next(c for c in body["comparisons"] if c["dataset_name"] == DATASET)
        alpha_score = comp["scores"]["ModelAlpha"]["score"]
        beta_score = comp["scores"]["ModelBeta"]["score"]
        assert alpha_score > beta_score
