"""Contract: submission_format submit_model_body matches submit_model required fields."""

REQUIRED_FIELDS = frozenset({"benchmarkDatasetName", "modelName", "modelResults", "sentence_ids"})


def test_submit_model_body_has_required_keys():
    from eval_core.leaderboard_bridge import submission_format_for_dataset

    rd = {"source_texts": ["a", "b"], "labels": ["x", "y"]}
    out = submission_format_for_dataset("ds_contract", "text_classification", "accuracy", rd)
    body = out["submit_model_body"]
    assert REQUIRED_FIELDS <= body.keys()
    assert len(body["modelResults"]) == len(body["sentence_ids"])


def test_openapi_spec_returns_json():
    try:
        from app import app
    except ImportError:
        from backend.app import app  # type: ignore

    with app.test_client() as c:
        r = c.get("/openapi.json")
        assert r.status_code == 200
        data = r.get_json()
        assert data.get("openapi")
        assert "/public/submit_model" in (data.get("paths") or {})
