from __future__ import annotations

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


def test_dataset_questions_never_exposes_labels(monkeypatch):
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()
    app_module._STORE["datasets"].append({
        "name": "private_labels",
        "task_type": "text_classification",
        "evaluation_metric": "accuracy",
        "reference_data": {
            "ground_truth": [
                {"id": 7, "question": "What is the sentiment?", "context": "A glowing review.", "answer": "positive", "label": "positive"},
            ],
            "labels": ["positive"],
        },
    })

    with app.test_client() as c:
        r = c.get("/public/dataset_questions?dataset=private_labels")
        assert r.status_code == 200
        data = r.get_json()
        assert data["success"] is True
        assert data["questions"] == [{"id": 7, "input": "What is the sentiment?", "context": "A glowing review."}]
        assert "label" not in data["questions"][0]
        assert "answer" not in data["questions"][0]
        assert "labels" not in data


def test_submit_model_daily_quota(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("DAILY_SUBMISSION_LIMIT", "2")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()
    app_module._STORE["datasets"].append({
        "name": "quota_classification",
        "task_type": "text_classification",
        "evaluation_metric": "accuracy",
        "reference_data": {"source_texts": ["hello"], "labels": ["yes"]},
    })
    payload = {
        "benchmarkDatasetName": "quota_classification",
        "modelName": "quota-model",
        "modelResults": ["yes"],
        "sentence_ids": [0],
        "submitterId": "quota-user",
    }

    with app.test_client() as c:
        r1 = c.post("/public/submit_model", json=payload)
        assert r1.status_code == 200
        assert r1.headers["X-Submissions-Remaining"] == "1"

        r2 = c.post("/public/submit_model", json=payload)
        assert r2.status_code == 200
        assert r2.headers["X-Submissions-Remaining"] == "0"

        r3 = c.post("/public/submit_model", json=payload)
        assert r3.status_code == 429
        data = r3.get_json()
        assert data["error"] == "Daily submission limit reached"
        assert data["limit"] == 2
        assert data["resets_at"].endswith("+00:00")
        assert r3.headers["X-Submissions-Remaining"] == "0"
