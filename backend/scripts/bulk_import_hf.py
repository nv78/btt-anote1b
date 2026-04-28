#!/usr/bin/env python3
"""Bulk-import Hugging Face datasets from a JSON manifest (list of objects for POST /public/import_hf_dataset)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import requests

BASE = os.environ.get("LEADERBOARD_API_BASE", "http://127.0.0.1:5001").rstrip("/")
API_KEY = os.environ.get("LEADERBOARD_API_KEY", "")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest", help="Path to JSON array (see backend/examples/hf_bulk_manifest.sample.json)")
    p.add_argument("--preview-only", action="store_true", help="Pass preview_only to each import")
    args = p.parse_args()
    with open(args.manifest, encoding="utf-8") as f:
        items = json.load(f)
    if not isinstance(items, list):
        print("Manifest must be a JSON array", file=sys.stderr)
        sys.exit(1)
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        body = dict(item)
        if args.preview_only:
            body["preview_only"] = True
        r = requests.post(f"{BASE}/public/import_hf_dataset", json=body, headers=headers, timeout=600)
        name = body.get("display_name") or body.get("dataset_name") or f"item_{i}"
        print(f"{name}: {r.status_code}")
        if r.ok:
            try:
                print(json.dumps(r.json(), indent=2)[:800])
            except Exception:
                print(r.text[:800])
        else:
            print(r.text[:500])
        time.sleep(0.15)


if __name__ == "__main__":
    main()
