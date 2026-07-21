import os
from functools import lru_cache

from dotenv import load_dotenv


# По умолчанию runtime env (systemd, shell, CI secrets) важнее локального .env.
# Для локального демо можно явно включить DOTENV_OVERRIDE=true.
load_dotenv(override=os.getenv("DOTENV_OVERRIDE", "false").lower() in {"1", "true", "yes"})


class Settings:
    """Глобальные настройки приложения."""

    # БД
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./hr_bot.db")

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_PROXY_URL: str = os.getenv("TELEGRAM_PROXY_URL", "")
    TELEGRAM_LINK_OTP_TTL_MINUTES: int = int(os.getenv("TELEGRAM_LINK_OTP_TTL_MINUTES", "10"))
    TELEGRAM_LINK_OTP_MAX_ATTEMPTS: int = int(os.getenv("TELEGRAM_LINK_OTP_MAX_ATTEMPTS", "5"))
    TELEGRAM_LINK_OTP_RESEND_COOLDOWN_SECONDS: int = int(os.getenv("TELEGRAM_LINK_OTP_RESEND_COOLDOWN_SECONDS", "60"))

    # Таймзона для расписания (для простоты — системная)
    TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Moscow")

    # Демо‑режим: вместо реальных часов (10–18) события идут подряд через короткие интервалы
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() in {"1", "true", "yes"}
    DEMO_STEP_MINUTES: int = int(os.getenv("DEMO_STEP_MINUTES", "1"))

    # Ручной запуск: шаг между сообщениями (минуты), чтобы уложиться "в течение дня"
    MANUAL_STEP_MINUTES: int = int(os.getenv("MANUAL_STEP_MINUTES", "1"))

    # Испытательный срок (рабочие дни)
    PROBATION_WORKDAYS: int = int(os.getenv("PROBATION_WORKDAYS", "40"))

    # Ссылки в сообщениях (можно переопределить через .env)
    TEST_URL: str = os.getenv("TEST_URL", "https://example.com/test")
    PRACTICE_URL: str = os.getenv("PRACTICE_URL", "https://example.com/practice")
    TASKS_URL: str = os.getenv("TASKS_URL", "https://example.com/tasks")
    FEEDBACK_URL: str = os.getenv("FEEDBACK_URL", "https://example.com/feedback")

    # Локальное хранение файлов кандидатов/сотрудников
    FILE_STORAGE_DIR: str = os.getenv("FILE_STORAGE_DIR", "./storage/employee_files")

    # SMTP для OTP-писем сотрудникам
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "HR Bot")
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "true").lower() in {"1", "true", "yes"}
    SMTP_USE_STARTTLS: bool = os.getenv("SMTP_USE_STARTTLS", "false").lower() in {"1", "true", "yes"}
    SMTP_TIMEOUT_SECONDS: int = int(os.getenv("SMTP_TIMEOUT_SECONDS", "15"))

    # Сессии админки
    ADMIN_SESSION_SECRET: str = os.getenv("ADMIN_SESSION_SECRET", "change-me-admin-session-secret")
    ADMIN_SESSION_MAX_AGE_SECONDS: int = int(os.getenv("ADMIN_SESSION_MAX_AGE_SECONDS", str(60 * 60 * 12)))
    ADMIN_SESSION_COOKIE_SECURE: bool = os.getenv("ADMIN_SESSION_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}

    # Базовые аккаунты админки
    DEFAULT_ADMIN_LOGIN: str = os.getenv("DEFAULT_ADMIN_LOGIN", "admin")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
    DEFAULT_HR_LOGIN: str = os.getenv("DEFAULT_HR_LOGIN", "hr")
    DEFAULT_HR_PASSWORD: str = os.getenv("DEFAULT_HR_PASSWORD", "hr123")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
