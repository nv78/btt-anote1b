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
    app_module.LEADERBOARD_DATA.clear()
    app_module._AUTO_SEED_DONE = False


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


def test_dataset_questions_exposes_multiple_choice_options_without_answer(monkeypatch):
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()
    app_module._STORE["datasets"].append({
        "name": "public_mcq",
        "task_type": "multiple_choice_qa",
        "evaluation_metric": "accuracy",
        "reference_data": {
            "ground_truth": [
                {
                    "id": 3,
                    "question": "Which option is correct?",
                    "options": {"A": "First", "B": "Second"},
                    "answer": "B",
                },
            ],
        },
    })

    with app.test_client() as c:
        r = c.get("/public/dataset_questions?dataset=public_mcq")
        assert r.status_code == 200
        item = r.get_json()["questions"][0]
        assert item["options"] == [{"label": "A", "text": "First"}, {"label": "B", "text": "Second"}]
        assert "answer" not in item
        assert "label" not in item


def test_get_source_sentences_includes_multiple_choice_options_without_answer(monkeypatch):
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()
    app_module._STORE["datasets"].append({
        "name": "public_mcq_sources",
        "task_type": "multiple_choice_qa",
        "evaluation_metric": "accuracy",
        "reference_data": {
            "ground_truth": [
                {
                    "id": 4,
                    "question": "Pick the best answer.",
                    "choices": ["Alpha", "Beta", "Gamma"],
                    "answer": "C",
                },
            ],
        },
    })

    with app.test_client() as c:
        r = c.get("/public/get_source_sentences?dataset_name=public_mcq_sources&count=1")
        assert r.status_code == 200
        item = r.get_json()["questions"][0]
        assert item["options"] == [
            {"label": "A", "text": "Alpha"},
            {"label": "B", "text": "Beta"},
            {"label": "C", "text": "Gamma"},
        ]
        assert "answer" not in item
        assert "label" not in item


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
        quota_before = c.get("/public/submission_quota?submitter_id=quota-user")
        assert quota_before.status_code == 200
        assert quota_before.get_json()["daily_limit"] == 2
        assert quota_before.get_json()["used_today"] == 0
        assert quota_before.get_json()["remaining"] == 2

        r1 = c.post("/public/submit_model", json=payload)
        assert r1.status_code == 200
        assert r1.headers["X-Submissions-Remaining"] == "1"

        quota_after_one = c.get("/public/submission_quota?submitter_id=quota-user")
        assert quota_after_one.status_code == 200
        assert quota_after_one.get_json()["used_today"] == 1
        assert quota_after_one.get_json()["remaining"] == 1

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


def test_submit_model_daily_quota_uses_sqlite_db_counter(monkeypatch, tmp_path):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("DAILY_SUBMISSION_LIMIT", "2")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "quota.db"))
    for key in ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME", "DB_PORT"):
        monkeypatch.delenv(key, raising=False)
    reset_store()
    conn, cursor = app_module.get_db_connection()
    cursor.execute(
        "INSERT INTO benchmark_datasets (name, task_type, evaluation_metric, reference_data, active) VALUES (%s, %s, %s, %s, TRUE)",
        (
            "quota_db_classification",
            "text_classification",
            "accuracy",
            '{"source_texts": ["hello"], "labels": ["yes"]}',
        ),
    )
    conn.commit()
    cursor.close()
    conn.close()
    payload = {
        "benchmarkDatasetName": "quota_db_classification",
        "modelName": "quota-db-model",
        "modelResults": ["yes"],
        "sentence_ids": [0],
        "submitterId": "quota-db-user",
    }

    with app.test_client() as c:
        r1 = c.post("/public/submit_model", json=payload)
        assert r1.status_code == 200

        quota_after_one = c.get("/public/submission_quota?submitter_id=quota-db-user")
        assert quota_after_one.status_code == 200
        assert quota_after_one.get_json()["used_today"] == 1
        assert app_module._STORE.setdefault("submission_counts", {}) == {}

        payload2 = {**payload, "modelName": "quota-db-model-2"}
        r2 = c.post("/public/submit_model", json=payload2)
        assert r2.status_code == 200, r2.get_data(as_text=True)

        payload3 = {**payload, "modelName": "quota-db-model-3"}
        r3 = c.post("/public/submit_model", json=payload3)
        assert r3.status_code == 429
        assert r3.get_json()["error"] == "Daily submission limit reached"


def test_rate_limit_uses_sqlite_db_counter(monkeypatch, tmp_path):
    monkeypatch.delenv("DISABLE_RATE_LIMIT", raising=False)
    monkeypatch.setenv("QUOTA_RATE_LIMIT", "2/minute")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "rate.db"))
    for key in ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME", "DB_PORT"):
        monkeypatch.delenv(key, raising=False)
    reset_store()

    with app.test_client() as c:
        r1 = c.get("/public/submission_quota?submitter_id=rate-db-user")
        assert r1.status_code == 200
        r2 = c.get("/public/submission_quota?submitter_id=rate-db-user")
        assert r2.status_code == 200
        r3 = c.get("/public/submission_quota?submitter_id=rate-db-user")
        assert r3.status_code == 429
        assert r3.get_json()["error"] == "Rate limit exceeded"


def test_seed_real_benchmarks_persist_in_sqlite(monkeypatch, tmp_path):
    from scripts.seed_real_benchmarks import DATASETS, detailed_scores

    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "leaderboard.db"))
    for key in ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME", "DB_PORT"):
        monkeypatch.delenv(key, raising=False)
    reset_store()
    app_module.LEADERBOARD_DATA.clear()

    with app.test_client() as c:
        for dataset in DATASETS:
            r = c.post("/api/leaderboard/add_dataset", json={
                "name": dataset["name"],
                "task_type": dataset["task_type"],
                "evaluation_metric": dataset["evaluation_metric"],
                "url": dataset["url"],
                "description": f"Seeded benchmark card for {dataset['name']}.",
            })
            assert r.status_code == 200, r.get_data(as_text=True)
            for model in dataset["models"]:
                r = c.post("/api/leaderboard/add_model", json={
                    **model,
                    "dataset_name": dataset["name"],
                    "detailed_scores": detailed_scores(
                        dataset["task_type"],
                        dataset["evaluation_metric"],
                        float(model["score"]),
                    ),
                })
                assert r.status_code == 200, r.get_data(as_text=True)

    reset_store()
    app_module.LEADERBOARD_DATA.clear()

    with app.test_client() as restarted:
        r = restarted.get("/public/get_leaderboard?page_size=100")
        assert r.status_code == 200
        data = r.get_json()
        assert data["success"] is True
        rows = data["leaderboard"]
        seeded_names = {dataset["name"] for dataset in DATASETS if dataset.get("models")}
        assert len(rows) == sum(len(dataset["models"]) for dataset in DATASETS)
        assert seeded_names <= {row["dataset_name"] for row in rows}


def test_run_hf_model_route_with_mocked_predictions(monkeypatch, tmp_path):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "leaderboard.db"))
    for key in ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME", "DB_PORT"):
        monkeypatch.delenv(key, raising=False)
    reset_store()
    app_module.LEADERBOARD_DATA.clear()

    def fake_predictions(model_id, task_type, items, batch_size, reference_data):
        return ["positive" for _ in items]

    monkeypatch.setattr(app_module, "_run_hf_predictions", fake_predictions)

    with app.test_client() as c:
        r = c.post("/public/add_dataset", json={
            "name": "hf_runner_mock",
            "task_type": "text_classification",
            "evaluation_metric": "accuracy",
            "reference_data": {"source_texts": ["great"], "labels": ["positive"]},
        })
        assert r.status_code == 200
        r = c.post("/public/run_hf_model", json={
            "dataset_name": "hf_runner_mock",
            "model_id": "mock/model",
            "batch_size": 16,
            "async": False,
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data["success"] is True
        assert data["score"] == 1.0
    assert data["submission_id"] >= 1


def test_leaderboard_includes_leaderboard_data_entries_alias(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_API_KEYS", "k")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        r = c.post(
            "/api/leaderboard/add_dataset",
            headers={"X-API-Key": "k"},
            json={
                "name": "curated-only",
                "task_type": "text_classification",
                "evaluation_metric": "accuracy",
            },
        )
        assert r.status_code == 200
        r = c.post(
            "/api/leaderboard/add_model",
            headers={"X-API-Key": "k"},
            json={
                "dataset_name": "curated-only",
                "rank": 1,
                "model": "curated-model",
                "score": 0.91,
                "updated": "May 2026",
                "detailed_scores": {"accuracy": 0.91, "f1": 0.9},
            },
        )
        assert r.status_code == 200

        app_module._STORE["submissions"].clear()
        app_module._STORE["evaluations"].clear()

        r = c.get("/public/get_leaderboard")
        assert r.status_code == 200
        data = r.get_json()
        assert len(data["entries"]) >= 1
        row = data["entries"][0]
        assert row["dataset_name"] == "curated-only"
        assert row["model_name"] == "curated-model"
        assert row["detailed_scores"]["accuracy"] == 0.91


def test_admin_seed_route_populates_leaderboard(monkeypatch):
    from scripts.seed_real_benchmarks import DATASETS

    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_ADMIN_API_KEYS", "admin")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        r = c.post("/api/leaderboard/seed", headers={"X-Admin-Key": "admin"})
        assert r.status_code == 200
        data = r.get_json()
        assert data["seeded"] == len(DATASETS)
        assert data["models_added"] == sum(len(dataset["models"]) for dataset in DATASETS)

        r = c.get("/public/get_leaderboard?page_size=100")
        assert r.status_code == 200
        rows = r.get_json()["entries"]
        assert len(rows) >= data["models_added"]


def test_auto_seed_once_on_first_request(monkeypatch):
    from scripts.seed_real_benchmarks import DATASETS

    monkeypatch.setenv("LEADERBOARD_AUTO_SEED_IN_TESTS", "1")
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        r = c.get("/health")
        assert r.status_code == 200
        seeded_count = sum(len(dataset["models"]) for dataset in DATASETS)
        assert len(app_module.LEADERBOARD_DATA) == len(DATASETS)
        assert sum(len(ds.get("models", [])) for ds in app_module.LEADERBOARD_DATA) == seeded_count

        r = c.get("/health")
        assert r.status_code == 200
        assert sum(len(ds.get("models", [])) for ds in app_module.LEADERBOARD_DATA) == seeded_count
