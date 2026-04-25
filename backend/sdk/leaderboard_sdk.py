"""
Lightweight Python SDK for the Anote Leaderboard API.

Usage:
    from backend.sdk.leaderboard_sdk import LeaderboardClient
    client = LeaderboardClient(base_url="http://localhost:5001")
    client.add_dataset(name="My Dataset", task_type="text_classification")
    client.add_model(dataset_name="My Dataset", model="MyModel", rank=1, score=0.95, updated="Sep 2024")
    print(client.list_datasets())
"""

from __future__ import annotations
import os
import requests
from typing import Any, Dict, Optional


class LeaderboardClient:
    def __init__(self, base_url: Optional[str] = None, timeout: int = 20, api_key: Optional[str] = None):
        self.base_url = base_url or os.getenv("LEADERBOARD_API_BASE", "http://localhost:5001")
        self.timeout = timeout
        self.api_key = api_key or os.getenv("LEADERBOARD_API_KEY")

    def _request(self, method: str, path: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {"X-API-Key": self.api_key} if self.api_key else None
        r = requests.request(method, url, json=json, headers=headers, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # Curated leaderboard
    def add_dataset(self, name: str, task_type: str, url: Optional[str] = None, description: Optional[str] = None, models: Optional[list] = None) -> Dict[str, Any]:
        payload = {"name": name, "task_type": task_type}
        if url:
            payload["url"] = url
        if description:
            payload["description"] = description
        if models:
            payload["models"] = models
        return self._request("POST", "/api/leaderboard/add_dataset", json=payload)

    def add_model(self, dataset_name: str, model: str, rank: Optional[int], score: Optional[float], updated: str, ci: Optional[str] = None) -> Dict[str, Any]:
        payload = {"dataset_name": dataset_name, "model": model, "rank": rank, "score": score, "updated": updated}
        if ci is not None:
            payload["ci"] = ci
        return self._request("POST", "/api/leaderboard/add_model", json=payload)

    def list_datasets(self) -> Dict[str, Any]:
        return self._request("GET", "/api/leaderboard/list")

    # Public dataset endpoints
    def list_public_datasets(self) -> Dict[str, Any]:
        return self._request("GET", "/public/datasets")

    def add_dataset_public(self, name: str, task_type: str, evaluation_metric: str, reference_data: Optional[dict] = None) -> Dict[str, Any]:
        payload = {"name": name, "task_type": task_type, "evaluation_metric": evaluation_metric}
        if reference_data is not None:
            payload["reference_data"] = reference_data
        return self._request("POST", "/public/add_dataset", json=payload)

    # Evaluation endpoints (optional)
    def get_leaderboard(self, dataset: Optional[str] = None, page: int = 1, page_size: int = 25) -> Dict[str, Any]:
        import urllib.parse as _u

        params = {"page": page, "page_size": page_size}
        if dataset:
            params["dataset"] = dataset
        return self._request("GET", f"/public/get_leaderboard?{_u.urlencode(params)}")

    def get_source_sentences(self, dataset_name: str = "flores_spanish_translation", count: int = 3, start_idx: int = 0) -> Dict[str, Any]:
        import urllib.parse as _u
        qs = _u.urlencode({"dataset_name": dataset_name, "count": count, "start_idx": start_idx})
        return self._request("GET", f"/public/get_source_sentences?{qs}")

    def submit_model(
        self,
        benchmark_dataset_name: str,
        model_name: str,
        model_results: list[str],
        sentence_ids: list[int],
        metadata: Optional[dict] = None,
    ) -> Dict[str, Any]:
        payload = {
            "benchmarkDatasetName": benchmark_dataset_name,
            "modelName": model_name,
            "modelResults": model_results,
            "sentence_ids": sentence_ids,
        }
        if metadata:
            payload["metadata"] = metadata
        return self._request("POST", "/public/submit_model", json=payload)

    def import_hf_dataset(self, dataset_name: str, split: str = "test", limit: int = 100, **kwargs) -> Dict[str, Any]:
        payload = {"dataset_name": dataset_name, "split": split, "limit": limit, **kwargs}
        return self._request("POST", "/public/import_hf_dataset", json=payload)

    def export_leaderboard(self, dataset: Optional[str] = None, format: str = "json") -> Dict[str, Any]:
        import urllib.parse as _u

        params = {"format": format}
        if dataset:
            params["dataset"] = dataset
        return self._request("GET", f"/public/export/leaderboard?{_u.urlencode(params)}")

    # CSV benchmarks
    def list_benchmark_csvs(self) -> Dict[str, Any]:
        return self._request("GET", "/public/benchmark_csvs")

    def run_csv_benchmarks(self, models: list[dict], datasets: Optional[list[str]] = None, sample_size: int = 25) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"models": models, "sample_size": sample_size}
        if datasets:
            payload["datasets"] = datasets
        return self._request("POST", "/public/run_csv_benchmarks", json=payload)


__all__ = ["LeaderboardClient"]
