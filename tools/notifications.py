import requests
import os
import threading
from logger import get_logger

logger = get_logger("notifications")

def send_email_sync(to_email: str, subject: str, body: str):
    """Synchronous internal function to send email via Resend API or fallback to logger."""
    api_key = os.environ.get("RESEND_API_KEY")

    if not api_key:
        # Fallback to logger if API key is missing
        logger.info(f"EMAIL NOTIFICATION [MOCK]\nTo: {to_email}\nSubject: {subject}\nBody: {body}", 
                    extra={"event": "email_mock_sent", "to": to_email})
        return

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    # Using 'onboarding@resend.dev' as the default 'from' for the free tier
    data = {
        "from": "Support <onboarding@resend.dev>",
        "to": [to_email],
        "subject": subject,
        "text": body
    }

    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)
        if response.status_code == 201 or response.status_code == 200:
            logger.info(f"Email successfully sent to {to_email} via Resend", extra={"event": "email_sent", "to": to_email})
        else:
            logger.error(f"Resend API error: {response.status_code} - {response.text}", 
                         extra={"event": "email_api_error", "status": response.status_code, "to": to_email})
    except Exception as e:
        logger.error(f"Failed to send email to {to_email} via Resend", 
                     extra={"event": "email_failed", "error": str(e), "to": to_email})

def send_email(to_email: str, subject: str, body: str):
    """Asynchronously send an email without blocking the main thread."""
    if not to_email:
        return
    thread = threading.Thread(target=send_email_sync, args=(to_email, subject, body))
    thread.daemon = True
    thread.start()

def send_telegram_sync(chat_id: str, message: str):
    """Synchronous internal function to send Telegram message or fallback to logger."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    
    if not bot_token:
        logger.info(f"TELEGRAM NOTIFICATION [MOCK]\nTo Chat: {chat_id}\nMessage: {message}", 
                    extra={"event": "telegram_mock_sent", "chat_id": chat_id})
        return
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": message}
    
    try:
        response = requests.post(url, json=data, timeout=15)
        response.raise_for_status()
        logger.info(f"Telegram message sent to {chat_id}", extra={"event": "telegram_sent", "chat_id": chat_id})
    except Exception as e:
        logger.error(f"Failed to send Telegram message to {chat_id}", 
                     extra={"event": "telegram_failed", "error": str(e), "chat_id": chat_id})

def send_telegram(chat_id: str, message: str):
    """Asynchronously send a Telegram message without blocking the main thread."""
    if not chat_id:
        return
    thread = threading.Thread(target=send_telegram_sync, args=(chat_id, message))
    thread.daemon = True
    thread.start()
