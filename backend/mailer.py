"""
Email delivery module for AccountIQ report notifications.

Phase 5 uses smtplib for SMTP delivery.
Phase 6 swaps send_report_ready_email() to use Resend without changing this signature.

IMPORTANT: This module is named email.py which shadows stdlib's email package when
the backend/ directory is on sys.path. To prevent smtplib from failing with
ModuleNotFoundError when it tries to import email.utils, we temporarily restore the
real stdlib email package in sys.modules before importing smtplib.

Required .env variables:
  SMTP_HOST      — e.g. smtp.gmail.com
  SMTP_PORT      — e.g. 587 (TLS) or 465 (SSL)
  SMTP_USER      — SMTP login username
  SMTP_PASSWORD  — SMTP login password or app password
  FROM_EMAIL     — sender address (defaults to SMTP_USER)
  APP_BASE_URL   — base URL of the app (defaults to http://localhost:8765)
"""
from __future__ import annotations

import os
import sys
import importlib
import asyncio


def _send_smtp(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    from_email: str,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str,
) -> None:
    """
    Send email via SMTP using smtplib with STARTTLS (port 587) or SSL (port 465).
    This function runs in a thread executor to keep the async event loop unblocked.

    STDLIB SHADOWING WORKAROUND: Before importing smtplib (which does `import email.utils`),
    we temporarily swap out this module from sys.modules so the stdlib email package is
    discoverable. We restore sys.modules after import to avoid leaking state.
    """
    # --- Workaround: stdlib email package is shadowed by this file ---
    _this_module = sys.modules.get("email")
    # Remove our module from sys.modules so stdlib importers find the real package
    sys.modules.pop("email", None)
    # Clear any cached sub-module references that may have been partially loaded
    for key in list(sys.modules.keys()):
        if key.startswith("email."):
            sys.modules.pop(key, None)

    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
    finally:
        # Restore this module back into sys.modules
        if _this_module is not None:
            sys.modules["email"] = _this_module

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, [to_email], msg.as_string())
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, [to_email], msg.as_string())


async def send_report_ready_email(
    user_email: str,
    user_name: str,
    report_type: str,
    report_id: int,
) -> None:
    """
    Send a "report ready" notification email to user_email via smtplib.
    Silently logs and returns if SMTP is not configured (development tolerance).
    Runs SMTP I/O in a thread executor to avoid blocking the event loop.

    Phase 6: replace _send_smtp() body with Resend API call; keep this signature unchanged.

    Parameters
    ----------
    user_email : str
        Recipient email address.
    user_name : str
        Display name for the recipient (used in greeting).
    report_type : str
        Report type key (e.g. 'valuation_advisory').
    report_id : int
        DB id of the completed report — included in the link URL.
    """
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("FROM_EMAIL", smtp_user)
    base_url = os.getenv("APP_BASE_URL", "http://localhost:8765")

    if not smtp_host or not smtp_user:
        print(
            f"[EMAIL] SMTP not configured — skipping email for report_id={report_id} "
            f"(user: {user_email})"
        )
        return

    report_type_display = report_type.replace("_", " ").title()
    subject = f"Your {report_type_display} is ready — AccountIQ"
    # Phase 7 will implement the viewer and update this link format
    report_link = f"{base_url}/app"

    greeting = f"Hi {user_name or user_email},"

    body_text = (
        f"{greeting}\n\n"
        f"Your {report_type_display} (Report #{report_id}) has been generated "
        f"and is ready to view.\n\n"
        f"Access it at: {report_link}\n\n"
        "This report is indicative only and does not constitute financial advice. "
        "Please seek independent professional advice before making any financial decision.\n\n"
        "— The AccountIQ Team"
    )

    body_html = f"""\
<html>
  <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
    <p>{greeting}</p>
    <p>
      Your <strong>{report_type_display}</strong> (Report #{report_id}) has been generated
      and is ready to view.
    </p>
    <p style="margin: 24px 0;">
      <a href="{report_link}"
         style="background: #2563eb; color: #fff; padding: 12px 24px;
                text-decoration: none; border-radius: 6px; font-weight: bold;">
        View Report
      </a>
    </p>
    <p style="font-size: 12px; color: #666; border-top: 1px solid #eee;
              padding-top: 12px; margin-top: 24px;">
      <em>This report is indicative only and does not constitute financial advice.
      Please seek independent professional advice before making any financial decision.</em>
    </p>
    <p style="font-size: 12px; color: #999;">— The AccountIQ Team</p>
  </body>
</html>"""

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            _send_smtp,
            smtp_host, smtp_port, smtp_user, smtp_pass,
            from_email, user_email, subject, body_text, body_html,
        )
        print(
            f"[EMAIL] Sent report-ready email to {user_email} "
            f"(report_id={report_id}, type={report_type})"
        )
    except Exception as exc:
        # Log but do not propagate — email failure must NOT mark the report as failed
        print(f"[EMAIL] Failed to send email for report_id={report_id}: {exc}")
