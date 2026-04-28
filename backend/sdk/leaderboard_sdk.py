"""
Lightweight Python SDK for the Anote Leaderboard API.

Usage:
    from backend.sdk.leaderboard_sdk import LeaderboardClient
    client = LeaderboardClient(base_url="http://localhost:5001", api_key="...")
    client.get_submission_format("my_dataset")
    client.submit_model(..., submitter_id="user-1")
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests


class LeaderboardClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 20,
        api_key: Optional[str] = None,
        bearer_token: Optional[str] = None,
    ):
        self.base_url = (base_url or os.getenv("LEADERBOARD_API_BASE", "http://localhost:5001")).rstrip("/")
        self.timeout = timeout
        self.api_key = api_key or os.getenv("LEADERBOARD_API_KEY")
        self.bearer_token = bearer_token or os.getenv("LEADERBOARD_JWT")

    def _headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {}
        if self.api_key:
            h["X-API-Key"] = self.api_key
        if self.bearer_token:
            h["Authorization"] = f"Bearer {self.bearer_token}"
        return h

    def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        r = requests.request(
            method,
            url,
            json=json,
            params=params,
            headers=self._headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    # Curated leaderboard
    def add_dataset(
        self,
        name: str,
        task_type: str,
        url: Optional[str] = None,
        description: Optional[str] = None,
        models: Optional[list] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"name": name, "task_type": task_type}
        if url:
            payload["url"] = url
        if description:
            payload["description"] = description
        if models:
            payload["models"] = models
        return self._request("POST", "/api/leaderboard/add_dataset", json=payload)

    def add_model(
        self,
        dataset_name: str,
        model: str,
        rank: Optional[int],
        score: Optional[float],
        updated: str,
        ci: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "dataset_name": dataset_name,
            "model": model,
            "rank": rank,
            "score": score,
            "updated": updated,
        }
        if ci is not None:
            payload["ci"] = ci
        return self._request("POST", "/api/leaderboard/add_model", json=payload)

    def list_datasets(self) -> Dict[str, Any]:
        return self._request("GET", "/api/leaderboard/list")

    def list_public_datasets(self) -> Dict[str, Any]:
        return self._request("GET", "/public/datasets")

    def add_dataset_public(
        self,
        name: str,
        task_type: str,
        evaluation_metric: str,
        reference_data: Optional[dict] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "name": name,
            "task_type": task_type,
            "evaluation_metric": evaluation_metric,
        }
        if reference_data is not None:
            payload["reference_data"] = reference_data
        return self._request("POST", "/public/add_dataset", json=payload)

    def get_submission_format(self, dataset_name: str) -> Dict[str, Any]:
        import urllib.parse as _u

        qs = _u.urlencode({"dataset": dataset_name})
        return self._request("GET", f"/public/submission_format?{qs}")

    def get_leaderboard(
        self,
        dataset: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if dataset:
            params["dataset"] = dataset
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/public/get_leaderboard", params=params)

    def get_source_sentences(
        self,
        dataset_name: str = "flores_spanish_translation",
        count: int = 3,
        start_idx: int = 0,
    ) -> Dict[str, Any]:
        import urllib.parse as _u

        qs = _u.urlencode(
            {"dataset_name": dataset_name, "count": count, "start_idx": start_idx}
        )
        return self._request("GET", f"/public/get_source_sentences?{qs}")

    def submit_model(
        self,
        benchmark_dataset_name: str,
        model_name: str,
        model_results: List[str],
        sentence_ids: List[int],
        metadata: Optional[dict] = None,
        submitted_by: Optional[str] = None,
        submitter_id: Optional[str] = None,
        async_run: bool = False,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "benchmarkDatasetName": benchmark_dataset_name,
            "modelName": model_name,
            "modelResults": model_results,
            "sentence_ids": sentence_ids,
        }
        if metadata:
            payload["metadata"] = metadata
        if submitted_by:
            payload["submittedBy"] = submitted_by
        if submitter_id:
            payload["submitterId"] = submitter_id
        if async_run:
            payload["async"] = True
        url = f"{self.base_url}/public/submit_model"
        r = requests.post(
            url,
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def eval_job(self, job_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/public/eval_jobs/{job_id}")

    def my_submissions(
        self,
        submitter_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if submitter_id:
            params["submitter_id"] = submitter_id
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/public/my_submissions", params=params)

    def admin_submissions(
        self,
        admin_key: str,
        *,
        dataset: Optional[str] = None,
        submitter_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
        cursor: Optional[str] = None,
        include_outputs: bool = False,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if dataset:
            params["dataset"] = dataset
        if submitter_id:
            params["submitter_id"] = submitter_id
        if date_from:
            params["from"] = date_from
        if date_to:
            params["to"] = date_to
        if cursor:
            params["cursor"] = cursor
        if include_outputs:
            params["include_outputs"] = "1"
        url = f"{self.base_url}/api/admin/submissions"
        r = requests.get(
            url,
            params=params,
            headers={**self._headers(), "X-Admin-Key": admin_key},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def submission_detail(self, submission_id: int, submitter_id: Optional[str] = None) -> Dict[str, Any]:
        import urllib.parse as _u

        q = _u.urlencode({"submitter_id": submitter_id}) if submitter_id else ""
        path = f"/public/submissions/{submission_id}"
        if q:
            path = f"{path}?{q}"
        return self._request("GET", path)

    def import_hf_dataset(self, dataset_name: str, split: str = "test", limit: int = 100, **kwargs) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"dataset_name": dataset_name, "split": split, "limit": limit, **kwargs}
        return self._request("POST", "/public/import_hf_dataset", json=payload)

    def export_leaderboard(self, dataset: Optional[str] = None, format: str = "json") -> Dict[str, Any]:
        params: Dict[str, Any] = {"format": format}
        if dataset:
            params["dataset"] = dataset
        return self._request("GET", "/public/export/leaderboard", params=params)

    def list_benchmark_csvs(self) -> Dict[str, Any]:
        return self._request("GET", "/public/benchmark_csvs")

    def run_csv_benchmarks(
        self,
        models: List[dict],
        datasets: Optional[List[str]] = None,
        sample_size: int = 25,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"models": models, "sample_size": sample_size}
        if datasets:
            payload["datasets"] = datasets
        return self._request("POST", "/public/run_csv_benchmarks", json=payload)


__all__ = ["LeaderboardClient"]
