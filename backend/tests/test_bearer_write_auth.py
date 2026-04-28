"""Bearer JWT must include sub for protected writes when API keys are required."""

from __future__ import annotations

from datetime import timedelta

try:
    import app as app_module
except ImportError:
    import backend.app as app_module  # type: ignore

app = app_module.app


def test_bearer_without_sub_rejected_on_write(monkeypatch):
    monkeypatch.setenv("LEADERBOARD_API_KEYS", "k1")
    monkeypatch.setenv("LEADERBOARD_JWT_SECRET", "unit-test-secret")
    import jwt as pyjwt

    tok = pyjwt.encode(
        {"exp": int((app_module.utc_now() + timedelta(hours=1)).timestamp())},
        "unit-test-secret",
        algorithm="HS256",
    )
    if isinstance(tok, bytes):
        tok = tok.decode("ascii")
    with app.test_client() as c:
        r = c.post(
            "/public/submit_model",
            headers={"Authorization": f"Bearer {tok}"},
            json={},
        )
        assert r.status_code == 401


def test_bearer_with_sub_passes_auth_layer(monkeypatch):
    monkeypatch.setenv("LEADERBOARD_API_KEYS", "k1")
    monkeypatch.setenv("LEADERBOARD_JWT_SECRET", "unit-test-secret")
    import jwt as pyjwt

    tok = pyjwt.encode(
        {
            "sub": "contributor-1",
            "exp": int((app_module.utc_now() + timedelta(hours=1)).timestamp()),
        },
        "unit-test-secret",
        algorithm="HS256",
    )
    if isinstance(tok, bytes):
        tok = tok.decode("ascii")
    with app.test_client() as c:
        r = c.post(
            "/public/submit_model",
            headers={"Authorization": f"Bearer {tok}"},
            json={},
        )
        assert r.status_code == 400
        data = r.get_json()
        assert data.get("success") is False


def test_decode_leaderboard_bearer_requires_sub(monkeypatch):
    monkeypatch.setenv("LEADERBOARD_JWT_SECRET", "s")
    try:
        from auth_helpers import decode_leaderboard_bearer_token
    except ImportError:
        from backend.auth_helpers import decode_leaderboard_bearer_token  # type: ignore

    import jwt as pyjwt

    bare = pyjwt.encode(
        {"exp": int((app_module.utc_now() + timedelta(hours=1)).timestamp())},
        "s",
        algorithm="HS256",
    )
    if isinstance(bare, bytes):
        bare = bare.decode("ascii")
    assert decode_leaderboard_bearer_token(bare) is None
