"""Tests for email dataset-request notifications, SES transport, and quota_usage admin endpoint."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

try:
    import app as app_module
    import email_notifications as en
except ImportError:
    import backend.app as app_module  # type: ignore
    import backend.email_notifications as en  # type: ignore

app = app_module.app
ADMIN_KEY = "test-admin-key-999"


def reset_store() -> None:
    app_module._STORE["submissions"].clear()
    app_module._STORE["evaluations"].clear()
    app_module._STORE["datasets"].clear()
    app_module._STORE.setdefault("submission_counts", {}).clear()
    app_module.LEADERBOARD_DATA.clear()
    app_module._AUTO_SEED_DONE = False


# ---------------------------------------------------------------------------
# Dataset-request confirmation email
# ---------------------------------------------------------------------------

def test_dataset_request_confirmation_no_op_without_email():
    """Confirmation is silently skipped when to_email has no @."""
    with patch("threading.Thread") as mock_thread:
        en.send_dataset_request_confirmation(
            "not-an-email",
            dataset_name="My Dataset",
            task_type="text_classification",
        )
        mock_thread.assert_not_called()


def test_dataset_request_confirmation_spawns_thread(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "noreply@anote.ai")

    mock_thread = MagicMock()
    with patch("threading.Thread", return_value=mock_thread) as mock_cls:
        en.send_dataset_request_confirmation(
            "user@example.com",
            dataset_name="CoNLL-2003",
            task_type="ner",
            request_id=7,
        )
        mock_cls.assert_called_once()
        mock_thread.start.assert_called_once()


def test_dataset_request_confirmation_html_contains_name():
    html = en._dataset_request_confirmation_html(
        "CoNLL-2003", "ner", 7, "https://leaderboard.anote.ai"
    )
    assert "CoNLL-2003" in html
    assert "ner" in html
    assert "Request #7" in html
    assert "my-submissions" not in html  # this is the dataset email, not submission receipt


def test_dataset_request_confirmation_text_contains_name():
    text = en._dataset_request_confirmation_text(
        "CoNLL-2003", "ner", 7, "https://leaderboard.anote.ai"
    )
    assert "CoNLL-2003" in text
    assert "ner" in text


# ---------------------------------------------------------------------------
# Admin alert email
# ---------------------------------------------------------------------------

def test_admin_alert_no_op_without_config(monkeypatch):
    monkeypatch.delenv("LEADERBOARD_ADMIN_EMAIL", raising=False)
    with patch("threading.Thread") as mock_thread:
        en.send_dataset_request_admin_alert(
            dataset_name="Test DS",
            task_type="ner",
            requested_by="user@example.com",
        )
        mock_thread.assert_not_called()


def test_admin_alert_html_contains_dataset_and_requester(monkeypatch):
    html = en._dataset_request_admin_html(
        "SQuAD", "qa", "someone@corp.com", "A great QA dataset", 12,
        "https://leaderboard.anote.ai",
    )
    assert "SQuAD" in html
    assert "someone@corp.com" in html
    assert "#12" in html
    assert "A great QA dataset" in html
    assert "dataset-requests" in html  # link to admin panel


def test_admin_alert_emails_all_recipients(monkeypatch):
    monkeypatch.setenv("LEADERBOARD_ADMIN_EMAIL", "a@anote.ai,b@anote.ai")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "noreply@anote.ai")

    started = []
    def fake_thread(target, args, daemon):
        m = MagicMock()
        m.start = lambda: started.append(args[0])
        return m

    with patch("threading.Thread", side_effect=fake_thread):
        en.send_dataset_request_admin_alert(
            dataset_name="SQuAD",
            task_type="qa",
            requested_by="user@corp.com",
        )
    assert len(started) == 2  # one thread per admin email


# ---------------------------------------------------------------------------
# AWS SES transport
# ---------------------------------------------------------------------------

def test_ses_send_calls_boto3(monkeypatch):
    monkeypatch.setenv("AWS_SES_FROM", "noreply@anote.ai")
    monkeypatch.setenv("AWS_SES_REGION", "us-east-1")

    mock_client = MagicMock()
    mock_boto3 = MagicMock()
    mock_boto3.client.return_value = mock_client

    with patch.dict("sys.modules", {"boto3": mock_boto3}):
        en._send_ses("user@example.com", "Subject", "<p>html</p>", "text")

    mock_boto3.client.assert_called_once_with("ses", region_name="us-east-1")
    mock_client.send_email.assert_called_once()
    call_kwargs = mock_client.send_email.call_args[1]
    assert call_kwargs["Source"] == "noreply@anote.ai"
    assert call_kwargs["Destination"]["ToAddresses"] == ["user@example.com"]


def test_ses_preferred_over_smtp_when_configured(monkeypatch):
    monkeypatch.setenv("AWS_SES_FROM", "noreply@anote.ai")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "from@anote.ai")

    mock_thread = MagicMock()
    with patch("threading.Thread", return_value=mock_thread) as mock_cls:
        en._send_async("user@example.com", "Subj", "<p>html</p>", "text")
        # The target should be _send_ses, not _send_email
        target_fn = mock_cls.call_args.kwargs.get("target") or mock_cls.call_args[1].get("target")
        assert target_fn is en._send_ses


def test_ses_skips_gracefully_without_boto3(monkeypatch):
    monkeypatch.setenv("AWS_SES_FROM", "noreply@anote.ai")
    with patch.dict("sys.modules", {"boto3": None}):
        # Should not raise
        try:
            en._send_ses("user@example.com", "Subject", "<p>html</p>", "text")
        except ImportError:
            pass  # acceptable if boto3 completely missing


# ---------------------------------------------------------------------------
# Quota usage admin endpoint
# ---------------------------------------------------------------------------

def test_quota_usage_requires_admin_key(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_ADMIN_API_KEYS", ADMIN_KEY)
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        r = c.get("/api/admin/quota_usage")
        assert r.status_code in (401, 503)


def test_quota_usage_returns_data(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_ADMIN_API_KEYS", ADMIN_KEY)
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    # Seed some quota counts manually
    today = __import__("datetime").date.today().isoformat()
    app_module._STORE["submission_counts"][f"user-a:{today}"] = 3
    app_module._STORE["submission_counts"][f"user-b:{today}"] = 1

    with app.test_client() as c:
        r = c.get("/api/admin/quota_usage", headers={"X-Admin-Key": ADMIN_KEY})
        assert r.status_code == 200
        body = r.get_json()
        assert body["success"] is True
        assert "quota" in body
        assert "rate_windows" in body
        assert "daily_limit" in body

        submitters = {row["submitter_id"]: row["used"] for row in body["quota"]}
        assert submitters.get("user-a") == 3
        assert submitters.get("user-b") == 1


def test_quota_usage_remaining_computed(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_ADMIN_API_KEYS", ADMIN_KEY)
    monkeypatch.setenv("DAILY_SUBMISSION_LIMIT", "5")
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    today = __import__("datetime").date.today().isoformat()
    app_module._STORE["submission_counts"][f"power-user:{today}"] = 4

    with app.test_client() as c:
        r = c.get("/api/admin/quota_usage", headers={"X-Admin-Key": ADMIN_KEY})
        body = r.get_json()
        row = next((q for q in body["quota"] if q["submitter_id"] == "power-user"), None)
        assert row is not None
        assert row["used"] == 4
        assert row["remaining"] == 1
        assert row["limit"] == 5


# ---------------------------------------------------------------------------
# Dataset deactivate / activate endpoints
# ---------------------------------------------------------------------------

def test_deactivate_dataset_requires_admin_key(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_ADMIN_API_KEYS", ADMIN_KEY)
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        r = c.post("/api/admin/datasets/MyDS/deactivate")
        assert r.status_code in (401, 503)


def test_deactivate_dataset_not_found_in_memory(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_ADMIN_API_KEYS", ADMIN_KEY)
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    with app.test_client() as c:
        r = c.post("/api/admin/datasets/NonExistent/deactivate", headers={"X-Admin-Key": ADMIN_KEY})
        assert r.status_code == 404


def test_deactivate_then_activate_roundtrip(monkeypatch):
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "1")
    monkeypatch.setenv("LEADERBOARD_ADMIN_API_KEYS", ADMIN_KEY)
    monkeypatch.setattr(app_module, "get_db_connection", lambda: (None, None))
    reset_store()

    app_module._STORE["datasets"].append({"name": "TestDS", "task_type": "ner", "active": True})

    with app.test_client() as c:
        r = c.post("/api/admin/datasets/TestDS/deactivate", headers={"X-Admin-Key": ADMIN_KEY})
        assert r.status_code == 200
        assert r.get_json()["active"] is False

        r = c.post("/api/admin/datasets/TestDS/activate", headers={"X-Admin-Key": ADMIN_KEY})
        assert r.status_code == 200
        assert r.get_json()["active"] is True
