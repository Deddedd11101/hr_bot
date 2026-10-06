from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import settings


class MailDeliveryError(RuntimeError):
    pass


def send_staff_code(to_email: str, code: str) -> None:
    if not all((settings.SMTP_HOST, settings.SMTP_USERNAME, settings.SMTP_PASSWORD, settings.SMTP_FROM_EMAIL)):
        raise MailDeliveryError("SMTP is not configured")
    message = EmailMessage()
    message["Subject"] = "Код входа в HR-бота"
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = to_email
    message.set_content(
        f"Код подтверждения Telegram для HR-бота: {code}\n"
        "Он действует 10 минут. Если вы не запрашивали код, проигнорируйте письмо.\n"
    )
    try:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise MailDeliveryError("SMTP delivery failed") from exc
