import os
from functools import lru_cache

from dotenv import load_dotenv


# .env имеет приоритет над переменными окружения shell, чтобы удобно было демить
load_dotenv(override=True)


class Settings:
    """Глобальные настройки приложения."""

    # БД
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./hr_bot.db")

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

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


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
