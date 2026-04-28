"""Opaque cursor helpers for keyset pagination (leaderboard + my_submissions)."""
from __future__ import annotations

import base64
import json
from typing import Any, Dict, Optional, Tuple

CURSOR_VERSION = 1


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def encode_cursor(payload: Dict[str, Any]) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _b64encode(body)


def decode_cursor(token: str) -> Optional[Dict[str, Any]]:
    if not token or not isinstance(token, str):
        return None
    try:
        data = json.loads(_b64decode(token.strip()).decode("utf-8"))
        if not isinstance(data, dict) or data.get("v") != CURSOR_VERSION:
            return None
        return data
    except Exception:
        return None


def leaderboard_cursor_encode(
    *,
    dataset_name: str,
    score: float,
    submission_id: int,
    next_rank_start: int,
    single_dataset: bool,
) -> str:
    if single_dataset:
        p = {
            "v": CURSOR_VERSION,
            "t": "lbf",
            "s": float(score),
            "i": int(submission_id),
            "r": int(next_rank_start),
        }
    else:
        p = {
            "v": CURSOR_VERSION,
            "t": "lb",
            "d": str(dataset_name),
            "s": float(score),
            "i": int(submission_id),
            "r": int(next_rank_start),
        }
    return encode_cursor(p)


def leaderboard_cursor_decode(c: Dict[str, Any]) -> Optional[Tuple[bool, str, float, int, int]]:
    """Return (single_dataset, dataset_name, score, submission_id, next_rank_start)."""
    t = c.get("t")
    r = int(c["r"])
    sid = int(c["i"])
    sc = float(c["s"])
    if t == "lbf":
        return True, "", sc, sid, r
    if t == "lb":
        return False, str(c.get("d", "")), sc, sid, r
    return None


def my_submissions_cursor_encode(created_iso: str, submission_id: int) -> str:
    p = {"v": CURSOR_VERSION, "t": "ms", "c": created_iso, "i": int(submission_id)}
    return encode_cursor(p)


def my_submissions_cursor_decode(c: Dict[str, Any]) -> Optional[Tuple[str, int]]:
    if c.get("t") != "ms":
        return None
    return str(c["c"]), int(c["i"])
