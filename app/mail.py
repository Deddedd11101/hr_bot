from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import settings


class MailDeliveryError(RuntimeError):
    pass


def send_email(*, to_email: str, subject: str, text: str) -> None:
    smtp_host = settings.SMTP_HOST.strip()
    smtp_username = settings.SMTP_USERNAME.strip()
    smtp_password = settings.SMTP_PASSWORD.strip()
    from_email = settings.SMTP_FROM_EMAIL.strip()
    if not smtp_host or not smtp_username or not smtp_password or not from_email:
        raise MailDeliveryError("SMTP для OTP не настроен.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.SMTP_FROM_NAME} <{from_email}>" if settings.SMTP_FROM_NAME.strip() else from_email
    message["To"] = to_email
    message.set_content(text)

    try:
        if settings.SMTP_USE_SSL:
            with smtplib.SMTP_SSL(smtp_host, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_SECONDS) as smtp:
                smtp.login(smtp_username, smtp_password)
                smtp.send_message(message)
                return

        with smtplib.SMTP(smtp_host, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_SECONDS) as smtp:
            smtp.ehlo()
            if settings.SMTP_USE_STARTTLS:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(smtp_username, smtp_password)
            smtp.send_message(message)
    except Exception as exc:  # pragma: no cover - exact SMTP failure depends on env
        raise MailDeliveryError(f"Не удалось отправить OTP на почту: {exc}") from exc
