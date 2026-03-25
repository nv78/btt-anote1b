import json
import pytest

from backend.app import app, LEADERBOARD_DATA, _STORE


@pytest.fixture(autouse=True)
def _clean_state():
    # reset in-memory stores before each test
    LEADERBOARD_DATA.clear()
    _STORE['submissions'].clear()
    _STORE['evaluations'].clear()
    yield


def _add_classification_dataset(client, name="cls_dataset"):
    """Helper: add a simple classification dataset and return its name."""
    client.post('/public/add_dataset', json={
        "name": name,
        "task_type": "text_classification",
        "evaluation_metric": "accuracy",
        "reference_data": {
            "source_texts": ["a", "b", "c"],
            "labels": ["pos", "neg", "pos"],
        },
    })
    return name


def _submit_model(client, dataset_name="cls_dataset", model_name="test-model",
                  results=None, sentence_ids=None):
    """Helper: submit a model and return the response."""
    if results is None:
        results = ["pos", "neg", "pos"]
    if sentence_ids is None:
        sentence_ids = [0, 1, 2]
    return client.post('/public/submit_model', json={
        "benchmarkDatasetName": dataset_name,
        "modelName": model_name,
        "modelResults": results,
        "sentence_ids": sentence_ids,
    })


def test_leaderboard_returns_results_list():
    """GET /public/get_leaderboard must return a list under 'results' or 'leaderboard' key."""
    client = app.test_client()
    _add_classification_dataset(client)
    _submit_model(client)

    res = client.get('/public/get_leaderboard')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    # The response must contain either 'results' or 'leaderboard' as a list
    has_results = isinstance(data.get("results"), list)
    has_leaderboard = isinstance(data.get("leaderboard"), list)
    assert has_results or has_leaderboard, (
        "Response must contain a 'results' or 'leaderboard' list key"
    )


def test_leaderboard_empty_when_no_submissions():
    """GET /public/get_leaderboard should return an empty list when no models have been submitted."""
    client = app.test_client()

    res = client.get('/public/get_leaderboard')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    results = data.get("results") or data.get("leaderboard") or []
    assert isinstance(results, list)
    assert len(results) == 0


def test_submit_with_wrong_predictions_count_returns_400():
    """Submitting modelResults and sentence_ids of different lengths should return HTTP 400."""
    client = app.test_client()
    _add_classification_dataset(client)

    res = client.post('/public/submit_model', json={
        "benchmarkDatasetName": "cls_dataset",
        "modelName": "bad-model",
        "modelResults": ["pos", "neg", "pos"],   # 3 results
        "sentence_ids": [0, 1],                  # only 2 ids — mismatch
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert "error" in data


def test_submit_with_extra_predictions_count_returns_400():
    """More sentence_ids than modelResults should also return HTTP 400."""
    client = app.test_client()
    _add_classification_dataset(client)

    res = client.post('/public/submit_model', json={
        "benchmarkDatasetName": "cls_dataset",
        "modelName": "bad-model",
        "modelResults": ["pos"],               # 1 result
        "sentence_ids": [0, 1, 2],            # 3 ids — mismatch
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False


def test_export_leaderboard_csv_format():
    """GET /public/export/leaderboard?format=csv should return CSV content."""
    client = app.test_client()
    _add_classification_dataset(client)
    _submit_model(client)

    res = client.get('/public/export/leaderboard?format=csv')
    assert res.status_code == 200

    content_type = res.content_type or ''
    assert 'text/csv' in content_type, (
        f"Expected 'text/csv' content-type, got: {content_type}"
    )

    # Should contain a CSV header row
    body = res.data.decode('utf-8')
    assert 'model_name' in body or 'rank' in body, (
        "CSV export should contain header fields"
    )


def test_export_leaderboard_csv_contains_submitted_model():
    """Exported CSV should include models that have been submitted."""
    client = app.test_client()
    _add_classification_dataset(client)
    _submit_model(client, model_name="csv-export-model")

    res = client.get('/public/export/leaderboard?format=csv')
    assert res.status_code == 200

    body = res.data.decode('utf-8')
    assert 'csv-export-model' in body


def test_export_leaderboard_json_format():
    """GET /public/export/leaderboard?format=json should return valid JSON array."""
    client = app.test_client()
    _add_classification_dataset(client)
    _submit_model(client, model_name="json-export-model")

    res = client.get('/public/export/leaderboard?format=json')
    assert res.status_code == 200

    content_type = res.content_type or ''
    assert 'application/json' in content_type, (
        f"Expected 'application/json' content-type, got: {content_type}"
    )

    body = json.loads(res.data.decode('utf-8'))
    assert isinstance(body, list), "JSON export should be a list"

    # Confirm the submitted model appears in the export
    model_names = [entry.get("model_name") for entry in body]
    assert "json-export-model" in model_names


def test_export_leaderboard_json_entry_structure():
    """Each entry in the JSON export should contain expected keys."""
    client = app.test_client()
    _add_classification_dataset(client)
    _submit_model(client)

    res = client.get('/public/export/leaderboard?format=json')
    assert res.status_code == 200

    body = json.loads(res.data.decode('utf-8'))
    assert len(body) > 0, "Export should contain at least one entry"

    entry = body[0]
    for key in ("rank", "model_name", "score"):
        assert key in entry, f"Expected key '{key}' in export entry"


def test_export_leaderboard_invalid_format_returns_400():
    """GET /public/export/leaderboard?format=xml should return HTTP 400."""
    client = app.test_client()

    res = client.get('/public/export/leaderboard?format=xml')
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert "error" in data


def test_export_leaderboard_default_format_is_json():
    """GET /public/export/leaderboard with no format param should default to JSON."""
    client = app.test_client()
    _add_classification_dataset(client)
    _submit_model(client)

    res = client.get('/public/export/leaderboard')
    assert res.status_code == 200

    content_type = res.content_type or ''
    assert 'application/json' in content_type


def test_export_leaderboard_dataset_filter():
    """Exporting with ?dataset= filter should only include entries for that dataset."""
    client = app.test_client()
    _add_classification_dataset(client, name="dataset_a")
    _add_classification_dataset(client, name="dataset_b")
    _submit_model(client, dataset_name="dataset_a", model_name="model-a")
    _submit_model(client, dataset_name="dataset_b", model_name="model-b")

    res = client.get('/public/export/leaderboard?format=json&dataset=dataset_a')
    assert res.status_code == 200

    body = json.loads(res.data.decode('utf-8'))
    for entry in body:
        assert entry.get("dataset_name") == "dataset_a", (
            "Filtered export should only include entries for the specified dataset"
        )
