"""
Email notifications for the Anote Leaderboard.

Transport (first configured wins):
  AWS SES  — set AWS_SES_FROM (e.g. noreply@anote.ai); uses boto3 + ambient AWS credentials
             Optional: AWS_SES_REGION (default us-east-1)
  SMTP     — set SMTP_HOST + SMTP_PASSWORD + SMTP_FROM
             SMTP_PORT  : 587 (STARTTLS, default) or 465 (SSL)
             SMTP_USER  : e.g. apikey (SendGrid) or your Gmail address

Other:
    LEADERBOARD_URL        — public frontend URL (default http://localhost:3000)
    LEADERBOARD_ADMIN_EMAIL — comma-separated admin email(s) for internal alerts
"""

import logging
import os
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _cfg(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _ses_configured() -> bool:
    return bool(_cfg("AWS_SES_FROM"))


def _smtp_configured() -> bool:
    return bool(_cfg("SMTP_HOST") and _cfg("SMTP_PASSWORD") and _cfg("SMTP_FROM"))


def _email_configured() -> bool:
    return _ses_configured() or _smtp_configured()


def _frontend_url() -> str:
    return _cfg("LEADERBOARD_URL", "http://localhost:3000")


def _admin_emails() -> list[str]:
    raw = _cfg("LEADERBOARD_ADMIN_EMAIL")
    return [e.strip() for e in raw.split(",") if "@" in e.strip()]


# ---------------------------------------------------------------------------
# Low-level send
# ---------------------------------------------------------------------------

def _send_email(to: str, subject: str, html: str, text: str) -> None:
    """Blocking SMTP send. Called from a daemon thread so failures don't block the request."""
    host = _cfg("SMTP_HOST")
    port = int(_cfg("SMTP_PORT", "587"))
    user = _cfg("SMTP_USER")
    password = _cfg("SMTP_PASSWORD")
    from_addr = _cfg("SMTP_FROM")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port) as server:
                if user:
                    server.login(user, password)
                server.sendmail(from_addr, [to], msg.as_string())
        else:
            with smtplib.SMTP(host, port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                if user:
                    server.login(user, password)
                server.sendmail(from_addr, [to], msg.as_string())
        logger.info("email_sent", extra={"to": to, "subject": subject})
    except Exception as exc:
        logger.warning("email_send_failed", extra={"to": to, "error": str(exc)})


def _send_ses(to: str, subject: str, html: str, text: str) -> None:
    """Send via AWS SES using boto3. Caller must run in a daemon thread."""
    try:
        import boto3  # type: ignore
    except ImportError:
        logger.warning("ses_send_failed_no_boto3", extra={"to": to})
        return

    from_addr = _cfg("AWS_SES_FROM")
    region = _cfg("AWS_SES_REGION", "us-east-1")
    try:
        client = boto3.client("ses", region_name=region)
        client.send_email(
            Source=from_addr,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": text, "Charset": "UTF-8"},
                    "Html": {"Data": html, "Charset": "UTF-8"},
                },
            },
        )
        logger.info("ses_email_sent", extra={"to": to, "subject": subject})
    except Exception as exc:
        logger.warning("ses_send_failed", extra={"to": to, "error": str(exc)})


def _send_async(to: str, subject: str, html: str, text: str) -> None:
    """Fire-and-forget: send in a daemon thread so the API response isn't delayed.

    Prefers AWS SES if configured (AWS_SES_FROM set), otherwise falls back to SMTP.
    """
    if not _email_configured():
        logger.debug("email_skipped_not_configured", extra={"to": to})
        return
    transport = _send_ses if _ses_configured() else _send_email
    t = threading.Thread(target=transport, args=(to, subject, html, text), daemon=True)
    t.start()


def _send_async_multi(recipients: list[str], subject: str, html: str, text: str) -> None:
    """Send the same email to multiple recipients, one thread per address."""
    for addr in recipients:
        if "@" in addr:
            _send_async(addr, subject, html, text)


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_BASE_STYLE = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #111827; color: #e5e7eb; margin: 0; padding: 0; }
.wrap { max-width: 560px; margin: 40px auto; background: #0d1421;
        border: 1px solid #374151; border-radius: 12px; overflow: hidden; }
.header { background: #0d1421; padding: 28px 32px 20px;
          border-bottom: 1px solid #374151; }
.logo { font-size: 18px; font-weight: 800; color: #defe47; letter-spacing: -0.5px; }
.body { padding: 28px 32px; }
h2 { color: #ffffff; font-size: 20px; margin: 0 0 12px; }
p { color: #9ca3af; font-size: 14px; line-height: 1.6; margin: 0 0 12px; }
.score-box { background: #111827; border: 1px solid #374151; border-radius: 8px;
             padding: 16px 20px; margin: 20px 0; }
.score-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em;
               color: #6b7280; margin-bottom: 4px; }
.score-value { font-size: 32px; font-weight: 800; color: #defe47; line-height: 1; }
.score-metric { font-size: 12px; color: #6b7280; margin-top: 4px; }
.ci { font-size: 12px; color: #6b7280; margin-top: 2px; }
.btn { display: inline-block; margin-top: 20px; padding: 12px 24px;
       background: #defe47; color: #000; font-weight: 700; font-size: 14px;
       text-decoration: none; border-radius: 8px; }
.footer { padding: 16px 32px; border-top: 1px solid #1f2937;
          font-size: 11px; color: #4b5563; }
"""


def _submission_receipt_html(
    model_name: str,
    dataset_name: str,
    score: float,
    metric: str,
    ci_low: float | None,
    ci_high: float | None,
    submission_id: int | None,
    frontend_url: str,
) -> str:
    score_str = f"{score:.4f}" if score < 1 else f"{score:.2f}"
    ci_str = (
        f'<div class="ci">95% CI [{ci_low:.4f} – {ci_high:.4f}]</div>'
        if ci_low is not None and ci_high is not None
        else ""
    )
    sub_label = f"Submission #{submission_id} · " if submission_id else ""
    my_submissions_url = f"{frontend_url}/my-submissions"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>{_BASE_STYLE}</style></head>
<body>
<div class="wrap">
  <div class="header"><span class="logo">Anote Leaderboard</span></div>
  <div class="body">
    <h2>Submission scored!</h2>
    <p>
      <strong style="color:#fff">{model_name}</strong> was evaluated on
      <strong style="color:#fff">{dataset_name}</strong>.
      {sub_label}Here are your results:
    </p>
    <div class="score-box">
      <div class="score-label">{metric.upper().replace("_", " ")}</div>
      <div class="score-value">{score_str}</div>
      {ci_str}
    </div>
    <p>
      Your submission is now on the leaderboard. You can make it public or private,
      view the full metrics breakdown, and compare against other models from your
      submissions page.
    </p>
    <a href="{my_submissions_url}" class="btn">View My Submissions</a>
  </div>
  <div class="footer">
    Anote AI · You received this because you submitted to the leaderboard.<br>
    <a href="{frontend_url}" style="color:#6b7280">leaderboard.anote.ai</a>
  </div>
</div>
</body>
</html>"""


def _submission_receipt_text(
    model_name: str,
    dataset_name: str,
    score: float,
    metric: str,
    ci_low: float | None,
    ci_high: float | None,
    submission_id: int | None,
    frontend_url: str,
) -> str:
    score_str = f"{score:.4f}" if score < 1 else f"{score:.2f}"
    ci_str = (
        f"95% CI [{ci_low:.4f} – {ci_high:.4f}]\n"
        if ci_low is not None and ci_high is not None
        else ""
    )
    sub_label = f"Submission #{submission_id} | " if submission_id else ""
    return (
        f"Anote Leaderboard — Submission Scored\n"
        f"{'=' * 40}\n\n"
        f"{sub_label}{model_name} on {dataset_name}\n\n"
        f"{metric.upper().replace('_', ' ')}: {score_str}\n"
        f"{ci_str}\n"
        f"View your submission: {frontend_url}/my-submissions\n\n"
        f"Anote AI · {frontend_url}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _dataset_request_confirmation_html(
    dataset_name: str,
    task_type: str,
    request_id: int | None,
    frontend_url: str,
) -> str:
    req_label = f"Request #{request_id} · " if request_id else ""
    admin_url = f"{frontend_url}/leaderboard/admin/dataset-requests"
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>{_BASE_STYLE}</style></head>
<body>
<div class="wrap">
  <div class="header"><span class="logo">Anote Leaderboard</span></div>
  <div class="body">
    <h2>Dataset request received!</h2>
    <p>
      {req_label}We've received your request to add
      <strong style="color:#fff">{dataset_name}</strong>
      (task: {task_type}) to the Anote Leaderboard.
    </p>
    <p>
      Our team will review it and reach out when it's approved or if we have questions.
      New datasets typically go live within 1–3 business days.
    </p>
    <a href="{frontend_url}/leaderboard" class="btn">Go to Leaderboard</a>
  </div>
  <div class="footer">
    Anote AI · You received this because you submitted a dataset request.<br>
    <a href="{frontend_url}" style="color:#6b7280">leaderboard.anote.ai</a>
  </div>
</div>
</body>
</html>"""


def _dataset_request_confirmation_text(
    dataset_name: str, task_type: str, request_id: int | None, frontend_url: str
) -> str:
    req_label = f"Request #{request_id} | " if request_id else ""
    return (
        f"Anote Leaderboard — Dataset Request Received\n"
        f"{'=' * 42}\n\n"
        f"{req_label}{dataset_name} ({task_type})\n\n"
        f"We'll review your request and notify you when it's approved.\n"
        f"Typical turnaround: 1–3 business days.\n\n"
        f"Leaderboard: {frontend_url}/leaderboard\n\n"
        f"Anote AI · {frontend_url}"
    )


def _dataset_request_admin_html(
    dataset_name: str,
    task_type: str,
    requested_by: str,
    description: str,
    request_id: int | None,
    frontend_url: str,
) -> str:
    req_label = f"#{request_id} " if request_id else ""
    admin_url = f"{frontend_url}/leaderboard/admin/dataset-requests"
    desc_html = description.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>{_BASE_STYLE}
.meta {{ font-size:13px; color:#9ca3af; margin-bottom:6px; }}
.meta strong {{ color:#e5e7eb; }}
.desc {{ font-size:13px; color:#9ca3af; background:#1f2937; border-radius:6px; padding:10px 14px; margin-top:12px; white-space:pre-wrap; }}
</style></head>
<body>
<div class="wrap">
  <div class="header"><span class="logo">Anote Admin Alert</span></div>
  <div class="body">
    <h2>New dataset request {req_label}— action needed</h2>
    <div class="meta"><strong>Dataset:</strong> {dataset_name}</div>
    <div class="meta"><strong>Task type:</strong> {task_type}</div>
    <div class="meta"><strong>Requested by:</strong> {requested_by}</div>
    {f'<div class="desc">{desc_html}</div>' if description else ''}
    <a href="{admin_url}" class="btn" style="margin-top:24px;">Review in Admin Panel</a>
  </div>
  <div class="footer">Anote AI internal alert · <a href="{frontend_url}" style="color:#6b7280">leaderboard.anote.ai</a></div>
</div>
</body>
</html>"""


def _dataset_request_admin_text(
    dataset_name: str,
    task_type: str,
    requested_by: str,
    description: str,
    request_id: int | None,
    frontend_url: str,
) -> str:
    req_label = f"#{request_id} " if request_id else ""
    return (
        f"[Anote Admin] New dataset request {req_label}\n"
        f"{'=' * 40}\n\n"
        f"Dataset:      {dataset_name}\n"
        f"Task type:    {task_type}\n"
        f"Requested by: {requested_by}\n"
        + (f"\nDescription:\n{description}\n" if description else "")
        + f"\nReview: {frontend_url}/leaderboard/admin/dataset-requests\n\n"
        f"Anote AI · {frontend_url}"
    )


# ---------------------------------------------------------------------------
# Public API — dataset request emails
# ---------------------------------------------------------------------------

def send_dataset_request_confirmation(
    to_email: str,
    *,
    dataset_name: str,
    task_type: str,
    description: str = "",
    request_id: int | None = None,
) -> None:
    """Confirm to the requester that their dataset request was received."""
    if not to_email or "@" not in to_email:
        return
    url = _frontend_url()
    subject = f"[Anote] Dataset request received: {dataset_name}"
    html = _dataset_request_confirmation_html(dataset_name, task_type, request_id, url)
    text = _dataset_request_confirmation_text(dataset_name, task_type, request_id, url)
    _send_async(to_email, subject, html, text)


def send_dataset_request_admin_alert(
    *,
    dataset_name: str,
    task_type: str,
    requested_by: str,
    description: str = "",
    request_id: int | None = None,
) -> None:
    """Alert admin(s) that a new dataset was requested. Uses LEADERBOARD_ADMIN_EMAIL."""
    admins = _admin_emails()
    if not admins:
        return
    url = _frontend_url()
    subject = f"[Anote Admin] New dataset request: {dataset_name}"
    html = _dataset_request_admin_html(dataset_name, task_type, requested_by, description, request_id, url)
    text = _dataset_request_admin_text(dataset_name, task_type, requested_by, description, request_id, url)
    _send_async_multi(admins, subject, html, text)


def send_submission_receipt(
    to_email: str,
    *,
    model_name: str,
    dataset_name: str,
    score: float,
    metric: str,
    ci_low: float | None = None,
    ci_high: float | None = None,
    submission_id: int | None = None,
) -> None:
    """
    Fire-and-forget email sent after a successful submission is scored.

    Args:
        to_email:      Recipient address (from submitted_by field if it's an email).
        model_name:    Model/run identifier shown on the leaderboard.
        dataset_name:  Benchmark dataset name.
        score:         Primary metric score (0–1 or 0–100 depending on metric).
        metric:        Metric name string, e.g. "accuracy", "f1", "bleu".
        ci_low/high:   Bootstrap 95% confidence interval bounds, if available.
        submission_id: DB row id for the submission.
    """
    if not to_email or "@" not in to_email:
        return  # submitted_by is not always an email; skip silently

    url = _frontend_url()
    subject = f"[Anote] {model_name} scored {score:.4f} on {dataset_name}"
    html = _submission_receipt_html(model_name, dataset_name, score, metric, ci_low, ci_high, submission_id, url)
    text = _submission_receipt_text(model_name, dataset_name, score, metric, ci_low, ci_high, submission_id, url)
    _send_async(to_email, subject, html, text)
