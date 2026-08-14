"""
Notification Provider Interface — GCP-Ready
============================================
Switch between email providers using the EMAIL_PROVIDER environment variable:

  EMAIL_PROVIDER=resend   → Uses Resend API (default, Hugging Face)
  EMAIL_PROVIDER=gmail    → Uses Gmail SMTP + App Password (GCP production)

Required env vars per provider:
  Resend : RESEND_API_KEY
  Gmail  : GMAIL_SENDER_EMAIL, GMAIL_APP_PASSWORD
"""

import os
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from logger import get_logger

logger = get_logger("notifications")


# ─────────────────────────────────────────────
# EMAIL PROVIDER INTERFACE
# ─────────────────────────────────────────────


class EmailProvider:
    """Base interface — all providers must implement send()."""

    def send(self, to_email: str, subject: str, body: str) -> bool:
        raise NotImplementedError


class ResendProvider(EmailProvider):
    """Send emails via the Resend API (current Hugging Face provider)."""

    def send(self, to_email: str, subject: str, body: str) -> bool:
        api_key = os.environ.get("RESEND_API_KEY")
        if not api_key:
            logger.info(
                f"EMAIL [MOCK/RESEND]\nTo: {to_email}\nSubject: {subject}\nBody: {body}",
                extra={"event": "email_mock_sent", "provider": "resend", "to": to_email},
            )
            return True

        try:
            response = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"from": "Support <onboarding@resend.dev>", "to": [to_email], "subject": subject, "text": body},
                timeout=10,
            )
            if response.status_code in (200, 201):
                logger.info(
                    f"Email sent via Resend to {to_email}",
                    extra={"event": "email_sent", "provider": "resend", "to": to_email},
                )
                return True
            else:
                logger.error(
                    f"Resend error {response.status_code}: {response.text}",
                    extra={
                        "event": "email_api_error",
                        "provider": "resend",
                        "status": response.status_code,
                        "to": to_email,
                    },
                )
                return False
        except Exception as e:
            logger.error(
                f"Resend request failed: {e}", extra={"event": "email_failed", "provider": "resend", "to": to_email}
            )
            return False


class GmailProvider(EmailProvider):
    """
    Send emails via Gmail SMTP using an App Password.

    Setup (one-time, 5 minutes):
    1. Go to https://myaccount.google.com/security
    2. Enable 2-Step Verification
    3. Search "App passwords" → Create one → Copy the 16-char password
    4. Set env vars:
         GMAIL_SENDER_EMAIL=youremail@gmail.com
         GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

    This lets you send to ANY email address — no domain verification needed.
    """

    def send(self, to_email: str, subject: str, body: str) -> bool:
        sender_email = os.environ.get("GMAIL_SENDER_EMAIL")
        app_password = os.environ.get("GMAIL_APP_PASSWORD")

        if not sender_email or not app_password:
            logger.info(
                f"EMAIL [MOCK/GMAIL]\nTo: {to_email}\nSubject: {subject}\nBody: {body}",
                extra={"event": "email_mock_sent", "provider": "gmail", "to": to_email},
            )
            return True

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"E-Commerce Support <{sender_email}>"
            msg["To"] = to_email
            msg["Reply-To"] = sender_email

            # Attach plain text
            msg.attach(MIMEText(body, "plain"))

            # Attach HTML version for spam protection and clean presentation
            html_body = body.replace("\n", "<br>")
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #1e293b;">
              <div style="max-width: 600px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px; background-color: #ffffff;">
                <h2 style="color: #2563eb; margin-top: 0;">E-Commerce Support Notification</h2>
                <div style="background-color: #f8fafc; padding: 16px; border-radius: 6px; border-left: 4px solid #2563eb; font-size: 15px;">
                  {html_body}
                </div>
                <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0 16px 0;" />
                <p style="font-size: 12px; color: #64748b; margin: 0;">This is an automated confirmation from E-Commerce Support Agent.</p>
              </div>
            </body>
            </html>
            """
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender_email, app_password)
                server.sendmail(sender_email, to_email, msg.as_string())

            logger.info(
                f"Email sent via Gmail SMTP to {to_email}",
                extra={"event": "email_sent", "provider": "gmail", "to": to_email},
            )
            return True
        except smtplib.SMTPAuthenticationError:
            logger.error(
                "Gmail SMTP authentication failed. Check GMAIL_APP_PASSWORD.",
                extra={"event": "email_auth_error", "provider": "gmail"},
            )
            return False
        except Exception as e:
            logger.error(f"Gmail SMTP error: {e}", extra={"event": "email_failed", "provider": "gmail", "to": to_email})
            return False


def get_email_provider() -> EmailProvider:
    """
    Factory: return the correct email provider based on EMAIL_PROVIDER env var.
    Default: 'resend' (backward-compatible with Hugging Face).
    """
    provider_name = os.environ.get("EMAIL_PROVIDER", "resend").lower().strip()
    if provider_name == "gmail":
        logger.info("Email provider: Gmail SMTP", extra={"event": "provider_selected", "provider": "gmail"})
        return GmailProvider()
    logger.info("Email provider: Resend API", extra={"event": "provider_selected", "provider": "resend"})
    return ResendProvider()


def send_email(to_email: str, subject: str, body: str):
    """
    Public API: send email asynchronously (non-blocking).
    Provider is auto-selected from EMAIL_PROVIDER env var.
    """
    if not to_email:
        return

    def _send_task():
        try:
            provider = get_email_provider()
            provider.send(to_email, subject, body)
        except Exception as e:
            logger.error(f"Async email task failed: {e}")

    thread = threading.Thread(target=_send_task)
    thread.daemon = True
    thread.start()


# ─────────────────────────────────────────────
# TELEGRAM (unchanged — provider-agnostic)
# ─────────────────────────────────────────────


def send_telegram_sync(chat_id: str, message: str):
    """Synchronous Telegram send with 3-attempt retry."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")

    if not bot_token:
        logger.info(
            f"TELEGRAM [MOCK]\nTo: {chat_id}\nMessage: {message}",
            extra={"event": "telegram_mock_sent", "chat_id": chat_id},
        )
        return

    masked_token = f"{bot_token[:5]}...{bot_token[-5:]}" if len(bot_token) > 10 else "SHORT_TOKEN"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    headers = {"User-Agent": "Mozilla/5.0"}
    data = {"chat_id": chat_id, "text": message}

    for attempt in range(3):
        try:
            logger.info(
                f"Telegram attempt {attempt + 1}/3 to {chat_id}",
                extra={"event": "telegram_attempt", "attempt": attempt + 1},
            )
            response = requests.post(url, json=data, headers=headers, timeout=20)
            response.raise_for_status()
            logger.info(f"Telegram message sent to {chat_id}", extra={"event": "telegram_sent", "chat_id": chat_id})
            return
        except Exception as e:
            if attempt < 2:
                import time

                time.sleep(2)
            else:
                logger.error(
                    f"Telegram failed after 3 attempts: {e}",
                    extra={
                        "event": "telegram_failed",
                        "error": str(e),
                        "chat_id": chat_id,
                        "token_check": masked_token,
                    },
                )


def send_telegram(chat_id: str, message: str):
    """Public API: send Telegram message asynchronously (non-blocking)."""
    if not chat_id:
        return
    thread = threading.Thread(target=send_telegram_sync, args=(chat_id, message))
    thread.daemon = True
    thread.start()
