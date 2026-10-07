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
    TELEGRAM_BOT_USERNAME: str = os.getenv("TELEGRAM_BOT_USERNAME", "")
    TELEGRAM_PROXY_URL: str = os.getenv("TELEGRAM_PROXY_URL", "")

    # Employee email verification is opt-in until SMTP is configured on stage.
    STAFF_EMAIL_OTP_ENABLED: bool = os.getenv("STAFF_EMAIL_OTP_ENABLED", "false").lower() in {"1", "true", "yes"}
    STAFF_EMAIL_DOMAIN: str = os.getenv("STAFF_EMAIL_DOMAIN", "ze.studio")
    STAFF_EMAIL_FROM: str = os.getenv("STAFF_EMAIL_FROM", "info@ze.studio")
    STAFF_EMAIL_SMTP_HOST: str = os.getenv("STAFF_EMAIL_SMTP_HOST", "smtp.yandex.ru")
    STAFF_EMAIL_SMTP_PORT: int = int(os.getenv("STAFF_EMAIL_SMTP_PORT", "465"))
    STAFF_EMAIL_SMTP_USERNAME: str = os.getenv("STAFF_EMAIL_SMTP_USERNAME", "info@ze.studio")
    STAFF_EMAIL_SMTP_PASSWORD: str = os.getenv("STAFF_EMAIL_SMTP_PASSWORD", "")

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

    # Сессии админки
    ADMIN_SESSION_SECRET: str = os.getenv("ADMIN_SESSION_SECRET", "change-me-admin-session-secret")
    ADMIN_SESSION_MAX_AGE_SECONDS: int = int(os.getenv("ADMIN_SESSION_MAX_AGE_SECONDS", str(60 * 60 * 12)))
    ADMIN_SESSION_COOKIE_SECURE: bool = os.getenv("ADMIN_SESSION_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}

    # Интеграция с Pulse: bearer-токен для read-only экспорта сотрудников.
    # Пусто = endpoint отключён (503).
    PULSE_SYNC_TOKEN: str = os.getenv("PULSE_SYNC_TOKEN", "")

    # Базовые аккаунты админки
    DEFAULT_ADMIN_LOGIN: str = os.getenv("DEFAULT_ADMIN_LOGIN", "admin")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
    DEFAULT_HR_LOGIN: str = os.getenv("DEFAULT_HR_LOGIN", "hr")
    DEFAULT_HR_PASSWORD: str = os.getenv("DEFAULT_HR_PASSWORD", "hr123")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
