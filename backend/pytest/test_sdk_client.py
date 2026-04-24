from backend.sdk.leaderboard_sdk import LeaderboardClient


class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_sdk_add_dataset(monkeypatch):
    calls = {}

    def fake_request(method, url, json=None, headers=None, timeout=None):
        calls['method'] = method
        calls['url'] = url
        calls['json'] = json
        return _Resp(200, {"success": True, "message": "Dataset added"})

    import requests
    monkeypatch.setattr(requests, 'request', fake_request)

    client = LeaderboardClient(base_url="http://test")
    res = client.add_dataset_public(
        name="Demo",
        task_type="translation",
        evaluation_metric="bleu",
        reference_data={"url": "http://x", "description": "demo"}
    )
    assert res["success"] is True
    assert calls['method'] == 'POST'
    assert calls['url'].endswith('/public/add_dataset')
    assert calls['json']["name"] == "Demo"
    assert calls['json']["task_type"] == "translation"
    assert calls['json']["evaluation_metric"] == "bleu"
    assert calls['json']["reference_data"]["url"] == "http://x"


def test_sdk_list_public_datasets(monkeypatch):
    def fake_request(method, url, json=None, headers=None, timeout=None):
        return _Resp(200, {"success": True, "datasets": [{"name": "flores_spanish_translation", "task_type": "translation", "evaluation_metric": "bleu"}]})

    import requests
    monkeypatch.setattr(requests, 'request', fake_request)

    client = LeaderboardClient(base_url="http://test")
    res = client.list_public_datasets()
    assert res["success"] is True
    assert isinstance(res["datasets"], list)
    assert res["datasets"][0]["name"] == "flores_spanish_translation"


def test_sdk_submit_model(monkeypatch):
    def fake_request(method, url, json=None, headers=None, timeout=None):
        assert json["benchmarkDatasetName"] == "flores_spanish_translation"
        assert json["modelName"] == "my-model"
        assert isinstance(json["modelResults"], list)
        assert isinstance(json["sentence_ids"], list)
        return _Resp(200, {"success": True, "score": 0.42})

    import requests
    monkeypatch.setattr(requests, 'request', fake_request)

    client = LeaderboardClient(base_url="http://test")
    res = client.submit_model(
        benchmark_dataset_name="flores_spanish_translation",
        model_name="my-model",
        model_results=["a", "b"],
        sentence_ids=[0, 1],
    )
    assert res["success"] is True
    assert 0 <= res["score"] <= 1
