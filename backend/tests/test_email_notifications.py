"""Tests for email_notifications.send_submission_receipt."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

try:
    import email_notifications as en
except ImportError:
    import backend.email_notifications as en  # type: ignore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COMMON_KWARGS = dict(
    model_name="MyModel",
    dataset_name="SST-2 Sentiment (Sample)",
    score=0.8750,
    metric="accuracy",
    ci_low=0.80,
    ci_high=0.95,
    submission_id=42,
)


def _smtp_env(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "noreply@anote.ai")
    monkeypatch.setenv("LEADERBOARD_URL", "https://leaderboard.anote.ai")


# ---------------------------------------------------------------------------
# Skip when no email address
# ---------------------------------------------------------------------------

def test_skips_when_no_at_sign(monkeypatch):
    """submitted_by without '@' → no thread started, no error raised."""
    _smtp_env(monkeypatch)
    with patch("threading.Thread") as mock_thread:
        en.send_submission_receipt("not-an-email", **_COMMON_KWARGS)
        mock_thread.assert_not_called()


def test_skips_when_empty_email(monkeypatch):
    _smtp_env(monkeypatch)
    with patch("threading.Thread") as mock_thread:
        en.send_submission_receipt("", **_COMMON_KWARGS)
        mock_thread.assert_not_called()


# ---------------------------------------------------------------------------
# Skip when SMTP not configured
# ---------------------------------------------------------------------------

def test_skips_when_smtp_not_configured(monkeypatch):
    """No SMTP_HOST → _send_async returns early without spawning a thread."""
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)

    with patch("threading.Thread") as mock_thread:
        en.send_submission_receipt("user@example.com", **_COMMON_KWARGS)
        mock_thread.assert_not_called()


def test_skips_when_smtp_password_missing(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.setenv("SMTP_FROM", "noreply@anote.ai")

    with patch("threading.Thread") as mock_thread:
        en.send_submission_receipt("user@example.com", **_COMMON_KWARGS)
        mock_thread.assert_not_called()


# ---------------------------------------------------------------------------
# Thread spawned when everything is configured
# ---------------------------------------------------------------------------

def test_spawns_thread_when_configured(monkeypatch):
    _smtp_env(monkeypatch)

    mock_thread = MagicMock()
    with patch("threading.Thread", return_value=mock_thread) as mock_cls:
        en.send_submission_receipt("user@example.com", **_COMMON_KWARGS)
        mock_cls.assert_called_once()
        mock_thread.start.assert_called_once()
        # Must be a daemon thread
        assert mock_cls.call_args.kwargs.get("daemon") is True


# ---------------------------------------------------------------------------
# Subject line content
# ---------------------------------------------------------------------------

def test_subject_contains_model_name(monkeypatch):
    _smtp_env(monkeypatch)
    captured = {}

    def fake_thread(target, args, daemon):
        captured["args"] = args
        m = MagicMock()
        m.start = lambda: None
        return m

    with patch("threading.Thread", side_effect=fake_thread):
        en.send_submission_receipt("user@example.com", **_COMMON_KWARGS)

    subject = captured["args"][1]
    assert "MyModel" in subject


def test_subject_contains_score(monkeypatch):
    _smtp_env(monkeypatch)
    captured = {}

    def fake_thread(target, args, daemon):
        captured["args"] = args
        m = MagicMock()
        m.start = lambda: None
        return m

    with patch("threading.Thread", side_effect=fake_thread):
        en.send_submission_receipt("user@example.com", **_COMMON_KWARGS)

    subject = captured["args"][1]
    assert "0.8750" in subject


# ---------------------------------------------------------------------------
# HTML body content
# ---------------------------------------------------------------------------

def test_html_contains_score(monkeypatch):
    html = en._submission_receipt_html(
        "MyModel", "SST-2", 0.8750, "accuracy", 0.80, 0.95, 42,
        "https://leaderboard.anote.ai",
    )
    assert "0.8750" in html


def test_html_contains_view_link(monkeypatch):
    html = en._submission_receipt_html(
        "MyModel", "SST-2", 0.8750, "accuracy", None, None, None,
        "https://leaderboard.anote.ai",
    )
    assert "my-submissions" in html
    assert "View My Submissions" in html


def test_html_contains_ci_range(monkeypatch):
    html = en._submission_receipt_html(
        "MyModel", "SST-2", 0.8750, "accuracy", 0.80, 0.95, 42,
        "https://leaderboard.anote.ai",
    )
    assert "0.8000" in html
    assert "0.9500" in html


def test_html_omits_ci_when_none(monkeypatch):
    html = en._submission_receipt_html(
        "MyModel", "SST-2", 0.8750, "accuracy", None, None, None,
        "https://leaderboard.anote.ai",
    )
    assert "95% CI" not in html


# ---------------------------------------------------------------------------
# Plain-text fallback content
# ---------------------------------------------------------------------------

def test_text_contains_model_and_score(monkeypatch):
    text = en._submission_receipt_text(
        "MyModel", "SST-2", 0.8750, "accuracy", 0.80, 0.95, 42,
        "https://leaderboard.anote.ai",
    )
    assert "MyModel" in text
    assert "0.8750" in text
    assert "my-submissions" in text


# ---------------------------------------------------------------------------
# SMTP send (integration-style, mocking smtplib)
# ---------------------------------------------------------------------------

def test_send_email_uses_starttls_on_port_587(monkeypatch):
    _smtp_env(monkeypatch)

    mock_server = MagicMock()
    with patch("smtplib.SMTP", return_value=mock_server) as mock_smtp:
        mock_smtp.return_value.__enter__ = lambda s: mock_server
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
        en._send_email("user@example.com", "Subject", "<p>html</p>", "text")
        mock_server.starttls.assert_called_once()
        mock_server.sendmail.assert_called_once()


def test_send_email_uses_smtp_ssl_on_port_465(monkeypatch):
    _smtp_env(monkeypatch)
    monkeypatch.setenv("SMTP_PORT", "465")

    mock_server = MagicMock()
    with patch("smtplib.SMTP_SSL", return_value=mock_server) as mock_ssl:
        mock_ssl.return_value.__enter__ = lambda s: mock_server
        mock_ssl.return_value.__exit__ = MagicMock(return_value=False)
        en._send_email("user@example.com", "Subject", "<p>html</p>", "text")
        mock_server.sendmail.assert_called_once()
