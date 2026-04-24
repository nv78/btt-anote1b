import json
import pytest

from backend.app import app, LEADERBOARD_DATA, _STORE


@pytest.fixture(autouse=True)
def _clean_state():
    # reset in-memory stores before each test
    LEADERBOARD_DATA.clear()
    _STORE['submissions'].clear()
    _STORE['evaluations'].clear()
    _STORE['datasets'].clear()
    yield


def test_add_and_list_public_datasets():
    client = app.test_client()

    # Add dataset
    payload = {
        "name": "demo_classification",
        "task_type": "text_classification",
        "evaluation_metric": "accuracy",
        "reference_data": {
            "url": "http://example.com",
            "description": "demo",
            "source_texts": ["a", "b", "c"],
            "labels": ["pos", "neg", "pos"]
        }
    }
    res = client.post('/public/add_dataset', json=payload)
    assert res.status_code in (200, 201)
    data = res.get_json()
    assert data["success"] is True

    # List
    res = client.get('/public/datasets')
    assert res.status_code == 200
    listed = res.get_json()
    assert listed["success"] is True
    names = [d["name"] for d in listed["datasets"]]
    assert "demo_classification" in names

    # Details
    res = client.get('/public/dataset_details?name=demo_classification')
    assert res.status_code == 200
    details = res.get_json()
    assert details["success"] is True
    assert details["dataset"]["name"] == "demo_classification"
    assert details["dataset"]["task_type"] == "text_classification"
    assert details["dataset"]["evaluation_metric"] == "accuracy"


def test_classification_submit_and_leaderboard():
    client = app.test_client()
    # Create dataset
    client.post('/public/add_dataset', json={
        "name": "demo_classification",
        "task_type": "text_classification",
        "evaluation_metric": "accuracy",
        "reference_data": {"source_texts": ["a","b","c"], "labels": ["x","y","x"]}
    })

    # Submit predictions
    res = client.post('/public/submit_model', json={
        "benchmarkDatasetName": "demo_classification",
        "modelName": "m1",
        "modelResults": ["x","y","z"],
        "sentence_ids": [0,1,2]
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert 0 <= data["score"] <= 1

    # Leaderboard contains the entry
    res = client.get('/public/get_leaderboard')
    assert res.status_code == 200
    lb = res.get_json()
    assert lb["success"] is True
    assert any(e["model_name"] == "m1" and e["dataset_name"] == "demo_classification" for e in lb["leaderboard"])


def test_ner_and_qa_flows():
    client = app.test_client()
    # NER dataset: entities are per-sentence lists of strings
    client.post('/public/add_dataset', json={
        "name": "demo_ner",
        "task_type": "ner",
        "evaluation_metric": "f1",
        "reference_data": {"source_texts": ["Acme hired John"], "entities": [["Acme","John"]]}
    })
    res = client.post('/public/submit_model', json={
        "benchmarkDatasetName": "demo_ner",
        "modelName": "ner-model",
        "modelResults": ["Acme; John"],
        "sentence_ids": [0]
    })
    assert res.status_code == 200
    assert res.get_json()["success"] is True

    # QA dataset: exact or F1
    client.post('/public/add_dataset', json={
        "name": "demo_qa",
        "task_type": "prompting",
        "evaluation_metric": "exact",
        "reference_data": {"source_texts": ["Q1"], "answers": ["Paris"]}
    })
    res = client.post('/public/submit_model', json={
        "benchmarkDatasetName": "demo_qa",
        "modelName": "qa-model",
        "modelResults": ["paris"],
        "sentence_ids": [0]
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert 0.9 <= data["score"] <= 1.0


def test_metrics_catalog_endpoints():
    client = app.test_client()

    res = client.get('/api/metrics')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "accuracy" in data["metrics"]

    res = client.get('/api/metrics/task/text_classification')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "accuracy" in data["metrics"]


def test_in_memory_dataset_reference_data_scores_classification():
    client = app.test_client()
    client.post('/public/add_dataset', json={
        "name": "stored_classification",
        "task_type": "text_classification",
        "evaluation_metric": "accuracy",
        "reference_data": {"source_texts": ["a", "b"], "labels": ["yes", "no"]}
    })

    res = client.post('/public/submit_model', json={
        "benchmarkDatasetName": "stored_classification",
        "modelName": "classifier",
        "modelResults": ["yes", "wrong"],
        "sentence_ids": [0, 1]
    })

    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["score"] == 0.5
