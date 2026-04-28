#!/usr/bin/env python3
"""Seed a simple baseline submission via the public API (echo source as translation for BLEU demo).

Requires the dataset to exist and (if configured) LEADERBOARD_API_KEY.

Usage:
  LEADERBOARD_API_BASE=http://127.0.0.1:5001 LEADERBOARD_API_KEY=... python backend/scripts/seed_baselines.py
"""
from __future__ import annotations

import os
import sys

import requests

BASE = os.environ.get("LEADERBOARD_API_BASE", "http://127.0.0.1:5001").rstrip("/")
API_KEY = os.environ.get("LEADERBOARD_API_KEY", "")


def main() -> None:
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    dataset = os.environ.get("SEED_DATASET_NAME", "flores_spanish_translation")
    r = requests.get(
        f"{BASE}/public/get_source_sentences",
        params={"dataset_name": dataset, "count": 5, "start_idx": 0},
        timeout=60,
    )
    if not r.ok:
        print("get_source_sentences failed:", r.status_code, r.text[:300], file=sys.stderr)
        sys.exit(1)
    d = r.json()
    if d.get("success") is not True:
        print("unexpected:", d, file=sys.stderr)
        sys.exit(1)
    body = {
        "benchmarkDatasetName": dataset,
        "modelName": os.environ.get("SEED_MODEL_NAME", "baseline-echo-seed"),
        "modelResults": d["source_sentences"],
        "sentence_ids": d["sentence_ids"],
        "submittedBy": "seed_baselines@anote.ai",
        "submitterId": "seed-baseline-script",
    }
    sr = requests.post(f"{BASE}/public/submit_model", json=body, headers=headers, timeout=120)
    print(sr.status_code, sr.text[:500])


if __name__ == "__main__":
    main()
