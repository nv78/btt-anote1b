import os
import pytest

# Disable the in-process rate limiter for all tests so validation tests
# receive the expected 400 instead of 429.
os.environ.setdefault("DISABLE_RATE_LIMIT", "1")


@pytest.fixture(autouse=True)
def _mock_db(monkeypatch):
    """Patch get_db_connection so these tests never touch the real SQLite DB.

    Uses the _CompatModule propagation on app: setting an attribute on `app`
    propagates it to shared and all blueprint modules automatically.
    """
    try:
        import app as app_module
    except ImportError:
        import backend.app as app_module  # type: ignore

    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
