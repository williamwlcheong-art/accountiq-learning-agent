"""
Email delivery for AccountIQ report notifications.

Phase 5 implementation uses Python smtplib.
Phase 6 will swap to Resend without changing the function signature.

Required .env variables:
  SMTP_HOST      — e.g. smtp.gmail.com
  SMTP_PORT      — e.g. 587 (TLS) or 465 (SSL)
  SMTP_USER      — SMTP login username (usually an email address)
  SMTP_PASSWORD  — SMTP login password or app password
  FROM_EMAIL     — sender address shown in the email (defaults to SMTP_USER)
  APP_BASE_URL   — base URL of the deployed app (defaults to http://localhost:8765)
"""

import asyncio
import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Report-type display labels (keep in sync with frontend copy and section schemas)
# ---------------------------------------------------------------------------

REPORT_TYPE_LABELS: dict[str, str] = {
    "valuation_advisory":   "Valuation Advisory",
    "bank_credit_paper":    "Bank Credit Paper",
    "financial_forecast":   "Financial Forecast",
    "capital_raising":      "Capital Raising Document",
    "information_memorandum": "Information Memorandum",
}


def _send_smtp_blocking(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    from_email: str,
    user_email: str,
    msg_string: str,
) -> None:
    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, [user_email], msg_string)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, [user_email], msg_string)


async def send_report_ready_email(
    user_email: str,
    user_name: str,
    report_type: str,
    report_id: int,
) -> None:
    """
    Send a "your report is ready" notification email.

    This is a fire-and-forget call — any SMTP exception is logged but not
    re-raised so a delivery failure never marks the report as failed.

    Parameters
    ----------
    user_email : str
        Recipient email address.
    user_name : str
        Display name for the recipient (used in greeting).
    report_type : str
        One of the REPORT_TYPE_LABELS keys (e.g. 'valuation').
    report_id : int
        DB id of the completed report — included in the link URL.
    """
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port_str = os.getenv("SMTP_PORT", "587")
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("FROM_EMAIL", smtp_user)
    base_url = os.getenv("APP_BASE_URL", "http://localhost:8765")

    # Gracefully skip sending when SMTP is not configured (development mode).
    if not smtp_host or not smtp_user or not smtp_password:
        print(
            f"[EMAIL] SMTP not configured — skipping email to {user_email} "
            f"for report {report_id} ({report_type})"
        )
        return

    try:
        smtp_port = int(smtp_port_str)
    except ValueError:
        smtp_port = 587

    report_label = REPORT_TYPE_LABELS.get(report_type, report_type.replace("_", " ").title())
    # Phase 5: link points to /app — Phase 7 will update to /app/reports/{report_id}
    report_link = f"{base_url}/app"

    greeting = f"Hi {user_name}," if user_name else "Hello,"
    subject = f"Your {report_label} is ready — AccountIQ"

    text_body = (
        f"{greeting}\n\n"
        f"Your {report_label} (Report #{report_id}) has been generated and is ready to view.\n\n"
        f"You can access it at: {report_link}\n\n"
        "This report is indicative only and does not constitute financial advice. "
        "Please consult a qualified financial adviser before making any decisions.\n\n"
        "— The AccountIQ Team"
    )

    html_body = f"""\
<html>
  <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
    <p>{greeting}</p>
    <p>
      Your <strong>{report_label}</strong> (Report #{report_id}) has been generated
      and is ready to view.
    </p>
    <p style="margin: 24px 0;">
      <a href="{report_link}"
         style="background: #2563eb; color: #fff; padding: 12px 24px;
                text-decoration: none; border-radius: 6px; font-weight: bold;">
        View Report
      </a>
    </p>
    <p style="font-size: 12px; color: #666; border-top: 1px solid #eee; padding-top: 12px; margin-top: 24px;">
      <em>This report is indicative only and does not constitute financial advice.
      Please consult a qualified financial adviser before making any decisions.</em>
    </p>
    <p style="font-size: 12px; color: #999;">— The AccountIQ Team</p>
  </body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = user_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            _send_smtp_blocking,
            smtp_host, smtp_port, smtp_user, smtp_password,
            from_email, user_email, msg.as_string(),
        )
        print(
            f"[EMAIL] Sent '{subject}' to {user_email} "
            f"(report_id={report_id}, type={report_type})"
        )
    except Exception as exc:
        # Log but do not propagate — email failure must not mark the report failed
        logger.error(
            "Failed to send report-ready email to %s for report %d: %s",
            user_email, report_id, exc,
        )
        print(f"[EMAIL ERROR] Could not send email to {user_email}: {exc}")
