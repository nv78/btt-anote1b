try:
    import app as app_module
    from blueprints import auth as auth_module
except ImportError:  # pragma: no cover
    import backend.app as app_module  # type: ignore
    from backend.blueprints import auth as auth_module  # type: ignore


app = app_module.app


def reset_state():
    app_module._STORE["submissions"].clear()
    app_module._STORE["evaluations"].clear()
    app_module._STORE["datasets"].clear()
    app_module._STORE.setdefault("submission_counts", {}).clear()
    app_module.LEADERBOARD_DATA.clear()
    app_module._AUTO_SEED_DONE = False


def test_get_leaderboard_rejects_malformed_page(monkeypatch):
    reset_state()
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))

    with app.test_client() as client:
        response = client.get("/public/get_leaderboard?page=abc")

    assert response.status_code == 400
    assert response.is_json
    assert response.get_json()["error"] == "page must be an integer"


def test_run_csv_benchmarks_rejects_malformed_sample_size(monkeypatch):
    reset_state()
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))

    with app.test_client() as client:
        response = client.post(
            "/public/run_csv_benchmarks",
            json={"models": [{"name": "echo", "provider": "echo"}], "sample_size": "bad"},
        )

    assert response.status_code == 400
    assert response.is_json
    assert response.get_json()["error"] == "sample_size must be an integer"


def test_submit_model_db_write_failure_does_not_fallback_to_memory(monkeypatch):
    reset_state()
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    app_module._STORE["datasets"].append({
        "name": "audit_classification",
        "task_type": "text_classification",
        "evaluation_metric": "accuracy",
        "reference_data": {
            "source_texts": ["great"],
            "labels": ["positive"],
            "ground_truth": [{"id": 0, "question": "great", "answer": "positive"}],
        },
    })

    class FakeConn:
        def __init__(self):
            self.rolled_back = False

        def commit(self):
            pass

        def rollback(self):
            self.rolled_back = True

        def close(self):
            pass

    class FakeCursor:
        def __init__(self):
            self._row = None
            self.lastrowid = None

        def execute(self, query, params=()):
            if "SELECT id FROM benchmark_datasets" in query:
                self._row = {"id": 1}
                return self
            if "INSERT INTO model_submissions" in query:
                raise RuntimeError("simulated insert failure")
            return self

        def fetchone(self):
            return self._row

        def close(self):
            pass

    calls = {"n": 0}

    def fake_get_db_connection():
        calls["n"] += 1
        if calls["n"] == 1:
            return None, None
        return FakeConn(), FakeCursor()

    monkeypatch.setattr(app_module, "get_db_connection", fake_get_db_connection)

    with app.test_client() as client:
        response = client.post(
            "/public/submit_model",
            json={
                "benchmarkDatasetName": "audit_classification",
                "modelName": "audit-model",
                "modelResults": ["positive"],
            },
        )

    assert response.status_code == 500
    assert response.is_json
    assert response.get_json()["error"] == "Database write failed"
    assert app_module._STORE["submissions"] == []
    assert app_module._STORE["evaluations"] == []


def test_google_oauth_start_stores_allowed_frontend_origin(monkeypatch):
    reset_state()
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)

    class FakeGoogle:
        def authorize_redirect(self, redirect_uri):
            from flask import redirect

            return redirect("https://accounts.google.test")

    class FakeOAuth:
        google = FakeGoogle()

    monkeypatch.setattr(auth_module, "_OAUTH", FakeOAuth())

    with app.test_client() as client:
        response = client.get("/public/auth/google/start?frontend_url=http%3A%2F%2F127.0.0.1%3A3001")
        assert response.status_code == 302
        with client.session_transaction() as sess:
            assert sess["leaderboard_frontend_url"] == "http://127.0.0.1:3001"
