import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import threading
from logger import get_logger

logger = get_logger("notifications")

def send_email_sync(to_email: str, subject: str, body: str):
    """Synchronous internal function to send email or fallback to logger."""
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = os.environ.get("SMTP_PORT")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    if not all([smtp_server, smtp_port, smtp_user, smtp_pass]):
        # Fallback to logger if credentials are missing
        logger.info(f"EMAIL NOTIFICATION [MOCK]\nTo: {to_email}\nSubject: {subject}\nBody: {body}", 
                    extra={"event": "email_mock_sent", "to": to_email})
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            
        logger.info(f"Email successfully sent to {to_email}", extra={"event": "email_sent", "to": to_email})
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}", extra={"event": "email_failed", "error": str(e), "to": to_email})

def send_email(to_email: str, subject: str, body: str):
    """Asynchronously send an email without blocking the main thread."""
    if not to_email:
        return
    thread = threading.Thread(target=send_email_sync, args=(to_email, subject, body))
    thread.daemon = True
    thread.start()

def send_telegram(chat_id: str, message: str):
    """Placeholder for Telegram integration."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.info(f"TELEGRAM NOTIFICATION [MOCK]\nTo Chat: {chat_id}\nMessage: {message}", 
                    extra={"event": "telegram_mock_sent", "chat_id": chat_id})
        return
    
    # Example implementation (requires requests)
    # import requests
    # url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    # data = {"chat_id": chat_id, "text": message}
    # try:
    #     requests.post(url, json=data, timeout=5)
    # except Exception as e:
    #     logger.error("Telegram send failed", extra={"error": str(e)})
