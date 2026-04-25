import pytest

from backend.app import app, LEADERBOARD_DATA, _STORE


@pytest.fixture(autouse=True)
def _clean_state():
    # reset in-memory stores before each test
    LEADERBOARD_DATA.clear()
    _STORE['submissions'].clear()
    _STORE['evaluations'].clear()
    yield


def _add_classification_dataset(client, name="test_cls"):
    """Helper: add a simple classification dataset."""
    client.post('/public/add_dataset', json={
        "name": name,
        "task_type": "text_classification",
        "evaluation_metric": "accuracy",
        "reference_data": {
            "source_texts": ["a", "b", "c"],
            "labels": ["pos", "neg", "pos"],
        },
    })


def test_submit_empty_model_name_returns_400():
    """Submitting with an empty modelName should return HTTP 400."""
    client = app.test_client()
    _add_classification_dataset(client)

    res = client.post('/public/submit_model', json={
        "benchmarkDatasetName": "test_cls",
        "modelName": "",
        "modelResults": ["pos", "neg", "pos"],
        "sentence_ids": [0, 1, 2],
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert "error" in data


def test_submit_whitespace_model_name_returns_400():
    """Submitting with a whitespace-only modelName should return HTTP 400."""
    client = app.test_client()
    _add_classification_dataset(client)

    res = client.post('/public/submit_model', json={
        "benchmarkDatasetName": "test_cls",
        "modelName": "   ",
        "modelResults": ["pos", "neg", "pos"],
        "sentence_ids": [0, 1, 2],
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False


def test_submit_empty_dataset_name_returns_400():
    """Submitting with an empty benchmarkDatasetName should return HTTP 400."""
    client = app.test_client()

    res = client.post('/public/submit_model', json={
        "benchmarkDatasetName": "",
        "modelName": "my-model",
        "modelResults": ["pos"],
        "sentence_ids": [0],
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert "error" in data


def test_submit_whitespace_dataset_name_returns_400():
    """Submitting with a whitespace-only benchmarkDatasetName should return HTTP 400."""
    client = app.test_client()

    res = client.post('/public/submit_model', json={
        "benchmarkDatasetName": "   ",
        "modelName": "my-model",
        "modelResults": ["pos"],
        "sentence_ids": [0],
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False


def test_submit_oversized_model_name_returns_400():
    """Submitting with a modelName exceeding 200 characters should return HTTP 400."""
    client = app.test_client()
    _add_classification_dataset(client)

    long_name = "m" * 201  # 201 chars — one over the limit

    res = client.post('/public/submit_model', json={
        "benchmarkDatasetName": "test_cls",
        "modelName": long_name,
        "modelResults": ["pos", "neg", "pos"],
        "sentence_ids": [0, 1, 2],
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert "error" in data


def test_submit_model_name_at_max_length_succeeds():
    """A modelName of exactly 200 characters should be accepted."""
    client = app.test_client()
    _add_classification_dataset(client)

    max_name = "m" * 200

    res = client.post('/public/submit_model', json={
        "benchmarkDatasetName": "test_cls",
        "modelName": max_name,
        "modelResults": ["pos", "neg", "pos"],
        "sentence_ids": [0, 1, 2],
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True


def test_submit_missing_required_fields_returns_400():
    """Submitting without any required fields should return HTTP 400."""
    client = app.test_client()

    res = client.post('/public/submit_model', json={})
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert "error" in data


def test_submit_missing_model_results_returns_400():
    """Submitting without modelResults should return HTTP 400."""
    client = app.test_client()

    res = client.post('/public/submit_model', json={
        "benchmarkDatasetName": "test_cls",
        "modelName": "my-model",
        "sentence_ids": [0, 1, 2],
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False


def test_submit_missing_sentence_ids_returns_400():
    """Submitting without sentence_ids should return HTTP 400."""
    client = app.test_client()

    res = client.post('/public/submit_model', json={
        "benchmarkDatasetName": "test_cls",
        "modelName": "my-model",
        "modelResults": ["pos", "neg"],
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False


def test_submit_non_list_model_results_returns_400():
    """Submitting modelResults as a string (not a list) should return HTTP 400."""
    client = app.test_client()

    res = client.post('/public/submit_model', json={
        "benchmarkDatasetName": "test_cls",
        "modelName": "my-model",
        "modelResults": "pos neg pos",
        "sentence_ids": [0, 1, 2],
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
