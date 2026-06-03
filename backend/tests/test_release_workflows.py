from __future__ import annotations

import time

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


def make_jwt(sub: str) -> str:
    import jwt as pyjwt

    return pyjwt.encode({"sub": sub}, "dev-secret", algorithm="HS256")


def auth_headers(sub: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_jwt(sub)}"}


def seed_classification_dataset(name: str = "workflow_classification") -> None:
    app_module._STORE["datasets"].append({
        "name": name,
        "task_type": "text_classification",
        "evaluation_metric": "accuracy",
        "reference_data": {
            "source_texts": ["great", "bad"],
            "labels": ["positive", "negative"],
            "label_names": ["positive", "negative"],
        },
    })


def test_async_submit_job_completes_and_is_owner_scoped(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_JWT_SECRET", "dev-secret")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()
    seed_classification_dataset()

    with app.test_client() as c:
        response = c.post("/public/submit_model", json={
            "benchmarkDatasetName": "workflow_classification",
            "modelName": "async-model",
            "modelResults": ["positive", "negative"],
            "sentence_ids": [0, 1],
            "async": True,
        }, headers=auth_headers("async-owner"))
        assert response.status_code == 202
        job_id = response.get_json()["job_id"]

        other_user = c.get(f"/public/eval_jobs/{job_id}", headers=auth_headers("other-user"))
        assert other_user.status_code == 404

        final_body = None
        for _ in range(40):
            poll = c.get(f"/public/eval_jobs/{job_id}", headers=auth_headers("async-owner"))
            assert poll.status_code == 200
            final_body = poll.get_json()
            if final_body["status"] == "completed":
                break
            time.sleep(0.05)

        assert final_body["status"] == "completed"
        assert final_body["success"] is True
        assert final_body["score"] == 1.0
        assert final_body["submission_id"] >= 1


def test_my_submissions_rejects_malformed_cursor_without_crashing(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_API_KEYS", "workflow-key")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        response = c.get(
            "/public/my_submissions?submitter_id=user-one&cursor=not-a-valid-cursor",
            headers={"X-API-Key": "workflow-key"},
        )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"] == "Invalid cursor"


def test_private_submission_detail_requires_owner(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_JWT_SECRET", "dev-secret")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()
    seed_classification_dataset()

    with app.test_client() as c:
        submitted = c.post("/public/submit_model", json={
            "benchmarkDatasetName": "workflow_classification",
            "modelName": "private-model",
            "modelResults": ["positive", "negative"],
            "sentence_ids": [0, 1],
            "is_public": False,
        }, headers=auth_headers("private-owner"))
        assert submitted.status_code == 200
        submission_id = submitted.get_json()["submission_id"]

        anonymous = c.get(f"/public/submissions/{submission_id}")
        assert anonymous.status_code == 401

        other_user = c.get(f"/public/submissions/{submission_id}", headers=auth_headers("other-user"))
        assert other_user.status_code == 403

        owner = c.get(f"/public/submissions/{submission_id}", headers=auth_headers("private-owner"))
        assert owner.status_code == 200
        body = owner.get_json()
        assert body["success"] is True
        assert body["submission"]["model_results"] == ["positive", "negative"]


def test_my_submissions_memory_response_includes_visibility(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_JWT_SECRET", "dev-secret")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()
    seed_classification_dataset()

    with app.test_client() as c:
        submitted = c.post("/public/submit_model", json={
            "benchmarkDatasetName": "workflow_classification",
            "modelName": "private-row",
            "modelResults": ["positive", "negative"],
            "sentence_ids": [0, 1],
            "is_public": False,
        }, headers=auth_headers("row-owner"))
        assert submitted.status_code == 200

        mine = c.get("/public/my_submissions", headers=auth_headers("row-owner"))
        assert mine.status_code == 200
        rows = mine.get_json()["submissions"]
        assert rows[0]["model_name"] == "private-row"
        assert rows[0]["is_public"] is False


def test_submission_format_exposes_allowed_outputs_without_answers(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()
    app_module._STORE["datasets"].append({
        "name": "workflow_mcq",
        "task_type": "multiple_choice_qa",
        "evaluation_metric": "accuracy",
        "reference_data": {
            "ground_truth": [
                {"id": 0, "question": "Pick one", "options": {"A": "Alpha", "B": "Beta"}, "answer": "B"},
            ],
        },
    })

    with app.test_client() as c:
        response = c.get("/public/submission_format?dataset=workflow_mcq")

    assert response.status_code == 200
    body = response.get_json()
    assert body["task_type_normalized"] == "multiple_choice_qa"
    assert body["allowed_outputs"] == ["A", "B"]
    assert body["submit_model_body"]["modelResults"] == ["A"]


def test_run_llm_submission_validates_dataset_and_provider_failure(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()
    seed_classification_dataset("llm_workflow")

    with app.test_client() as c:
        missing = c.post("/public/run_llm_submission", json={
            "benchmarkDatasetName": "missing",
            "modelName": "llm",
            "provider": "not-a-provider",
        })
        assert missing.status_code == 404

        bad_provider = c.post("/public/run_llm_submission", json={
            "benchmarkDatasetName": "llm_workflow",
            "modelName": "llm",
            "provider": "not-a-provider",
            "batch_size": 1,
        })
        assert bad_provider.status_code == 202
        job_id = bad_provider.get_json()["job_id"]
        final_body = None
        for _ in range(40):
            poll = c.get(f"/public/eval_jobs/{job_id}")
            assert poll.status_code == 200
            final_body = poll.get_json()
            if final_body["status"] == "failed":
                break
            time.sleep(0.05)
        assert final_body["status"] == "failed"
        assert "Unknown provider" in final_body["error"]
