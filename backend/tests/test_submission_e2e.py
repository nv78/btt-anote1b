from __future__ import annotations

import pytest

try:
    import app as app_module
except ImportError:
    import backend.app as app_module  # type: ignore


app = app_module.app
DATASET_NAME = "SST-2 Sentiment (Sample)"
SOURCE_TEXTS = [
    "hide new secretions from the parental units",
    "contains no wit , only labored gags",
    "that loves its characters and communicates something rather beautiful about human nature",
    "remains utterly satisfied to remain the same throughout",
    "on the worst revenge-of-the-nerds clichés the filmmakers could dredge up",
    "a depressed fifteen-year-old 's suicidal poetry",
    "demonstrates that the director of such hollywood blockbusters as patriot games can still turn out a small , personal film with an emotional wallop .",
    "the film quickly drags on becoming boring and predictable .",
    "rule of thumb : any film where the director shows up for a cameo is a bad film .",
    "a feast for the eyes and a film that will leave you with a warm glow in your heart",
    "an enormously entertaining and funny film .",
    "a nearly perfect film .",
    "it 's a bit disappointing to see a film that had such potential simply not pan out .",
    "this is the sort of film that makes you want to check your brain at the door .",
    "the film is a pleasant enough diversion .",
    "it 's a lovely , funny , moving film .",
    "watching it is like being caught in a bad dream from which there 's no escape .",
    "the movie is a disaster .",
    "a dazzling , engrossing film .",
    "the kind of film that makes you feel glad to be alive .",
]
GROUND_TRUTH = [0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 1, 1, 0, 0, 1, 1, 0, 1, 1, 1]


def reset_store() -> None:
    app_module._STORE["submissions"].clear()
    app_module._STORE["evaluations"].clear()
    app_module._STORE["datasets"].clear()
    app_module._STORE.setdefault("submission_counts", {}).clear()
    app_module.LEADERBOARD_DATA.clear()
    app_module._AUTO_SEED_DONE = False


def test_seeded_sst2_questions_do_not_expose_labels(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_AUTO_SEED_IN_TESTS", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        r = c.get("/public/dataset_questions", query_string={"dataset": DATASET_NAME})
        assert r.status_code == 200
        data = r.get_json()
        assert data["success"] is True
        assert data["dataset"] == DATASET_NAME
        assert data["task_type"] == "text_classification"
        assert data["questions"] == [
            {"id": idx, "input": text, "context": None}
            for idx, text in enumerate(SOURCE_TEXTS)
        ]
        assert len(data["questions"]) == 20
        for item in data["questions"]:
            assert "label" not in item
            assert "answer" not in item
        assert "ground_truth" not in data
        assert "labels" not in data


def test_seeded_sst2_submission_scores_all_positive_and_perfect(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_AUTO_SEED_IN_TESTS", "1")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    ids = list(range(20))

    with app.test_client() as c:
        c.get("/health")
        all_positive = c.post("/public/submit_model", json={
            "benchmarkDatasetName": DATASET_NAME,
            "modelName": "all-positive",
            "modelResults": ["1"] * 20,
            "sentence_ids": ids,
            "submitterId": "sst2-all-positive",
        })
        assert all_positive.status_code == 200
        all_positive_body = all_positive.get_json()
        assert all_positive_body["success"] is True
        assert all_positive_body["score"] == pytest.approx(0.5)
        assert all_positive_body["detailed_scores"]["accuracy"] == pytest.approx(0.5)

        perfect = c.post("/public/submit_model", json={
            "benchmarkDatasetName": DATASET_NAME,
            "modelName": "perfect-sst2",
            "modelResults": [str(label) for label in GROUND_TRUTH],
            "sentence_ids": ids,
            "submitterId": "sst2-perfect",
        })
        assert perfect.status_code == 200
        perfect_body = perfect.get_json()
        assert perfect_body["success"] is True
        assert perfect_body["score"] == pytest.approx(1.0)
        assert perfect_body["detailed_scores"]["accuracy"] == pytest.approx(1.0)
