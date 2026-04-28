"""Optional JWT (HS256) + submitter identity for Leaderboard writes and history."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from flask import Request


def jwt_sub_from_request(request: Request) -> Optional[str]:
    """If LEADERBOARD_JWT_SECRET is set, validate Bearer token and return ``sub`` claim."""
    secret = os.getenv("LEADERBOARD_JWT_SECRET", "").strip()
    if not secret:
        return None
    auth = request.headers.get("Authorization", "") or ""
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    try:
        import jwt  # PyJWT
    except ImportError:
        return None
    try:
        payload: Dict[str, Any] = jwt.decode(token, secret, algorithms=["HS256"])
        sub = payload.get("sub")
        if sub is None:
            return None
        s = str(sub).strip()
        return s[:255] if s else None
    except Exception:
        return None


def resolve_submitter_id(request: Request, body: Optional[dict]) -> Optional[str]:
    """Prefer JWT ``sub``; else optional JSON ``submitterId`` (integrators)."""
    sub = jwt_sub_from_request(request)
    if sub:
        return sub
    if not isinstance(body, dict):
        return None
    sid = body.get("submitterId")
    if isinstance(sid, str) and sid.strip():
        return sid.strip()[:255]
    return None


def api_key_configured() -> bool:
    keys = [k.strip() for k in os.getenv("LEADERBOARD_API_KEYS", "").split(",") if k.strip()]
    return bool(keys) or os.getenv("REQUIRE_API_KEY", "").lower() in {"1", "true", "yes"}
