"""Optional JWT (HS256) + submitter identity for Leaderboard writes and history."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from flask import Request


def decode_leaderboard_bearer_token(token: str) -> Optional[Dict[str, Any]]:
    """Validate Bearer JWT and return claims.

    Order: if ``ANOTE_JWKS_URL`` is set, try RS256/ES256 via JWKS (optional ``ANOTE_ISSUER``, ``ANOTE_AUDIENCE``).
    Else if ``LEADERBOARD_JWT_SECRET`` is set, try HS256 (e.g. OAuth callback–issued tokens).

    A non-empty ``sub`` claim is required.
    """
    if not token or not isinstance(token, str):
        return None
    try:
        import jwt  # PyJWT
    except ImportError:
        return None
    jwks_url = os.getenv("ANOTE_JWKS_URL", "").strip()
    issuer = os.getenv("ANOTE_ISSUER", "").strip()
    audience = os.getenv("ANOTE_AUDIENCE", "").strip()
    if jwks_url:
        try:
            from jwt import PyJWKClient

            jwks = PyJWKClient(jwks_url)
            signing_key = jwks.get_signing_key_from_jwt(token)
            kwargs: Dict[str, Any] = {
                "algorithms": ["RS256", "ES256"],
                "options": {"require": ["sub"]},
            }
            if issuer:
                kwargs["issuer"] = issuer
            if audience:
                kwargs["audience"] = audience
            return jwt.decode(token, signing_key.key, **kwargs)
        except Exception:
            pass
    secret = os.getenv("LEADERBOARD_JWT_SECRET", "").strip()
    if secret:
        try:
            return jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"require": ["sub"]},
            )
        except Exception:
            return None
    return None


def jwt_sub_from_request(request: Request) -> Optional[str]:
    """Validate Bearer token (JWKS or HS256) and return ``sub``."""
    auth = request.headers.get("Authorization", "") or ""
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    payload = decode_leaderboard_bearer_token(token)
    if not payload:
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    s = str(sub).strip()
    return s[:255] if s else None


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
