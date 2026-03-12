from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session

from .config import settings


class Base(DeclarativeBase):
    """Базовый класс для моделей SQLAlchemy."""


engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Создаёт таблицы в БД (для демо — без миграций)."""
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_schema()
    from .flow_templates import seed_flow_templates

    seed_flow_templates()


@contextmanager
def get_session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_sqlite_schema() -> None:
    """
    Минимальная совместимость схемы для существующего SQLite без Alembic.

    Добавляет отсутствующие колонки в employees и таблицу employee_files.
    """
    if not str(settings.DATABASE_URL).startswith("sqlite"):
        return

    with engine.begin() as conn:
        table_info = conn.execute(text("PRAGMA table_info(employees)")).fetchall()
        columns = {row[1] for row in table_info}
        required = {
            "desired_position": "TEXT",
            "salary_expectation": "TEXT",
            "candidate_status": "TEXT",
            "personal_data_consent": "BOOLEAN NOT NULL DEFAULT 0",
            "employee_data_consent": "BOOLEAN NOT NULL DEFAULT 0",
            "test_task_link": "TEXT",
            "test_task_due_at": "DATETIME",
            "notes": "TEXT",
        }
        for col, ddl in required.items():
            if col not in columns:
                conn.execute(text(f"ALTER TABLE employees ADD COLUMN {col} {ddl}"))

        # Для новой логики карточки сотрудника ключевые поля должны быть nullable.
        # В SQLite это требует пересоздания таблицы.
        notnull_map = {row[1]: int(row[3]) for row in conn.execute(text("PRAGMA table_info(employees)")).fetchall()}
        need_relax = (
            notnull_map.get("full_name", 0) == 1
            or notnull_map.get("telegram_user_id", 0) == 1
            or notnull_map.get("first_workday", 0) == 1
        )
        if need_relax:
            conn.execute(text("ALTER TABLE employees RENAME TO employees_old"))
            conn.execute(
                text(
                    """
                    CREATE TABLE employees (
                        id INTEGER NOT NULL,
                        full_name VARCHAR(255),
                        telegram_user_id VARCHAR(64),
                        first_workday DATE,
                        created_at DATETIME NOT NULL,
                        is_flow_scheduled BOOLEAN NOT NULL,
                        desired_position TEXT,
                        salary_expectation TEXT,
                        candidate_status TEXT,
                        personal_data_consent BOOLEAN NOT NULL DEFAULT 0,
                        employee_data_consent BOOLEAN NOT NULL DEFAULT 0,
                        test_task_link TEXT,
                        test_task_due_at DATETIME,
                        notes TEXT,
                        PRIMARY KEY (id)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO employees (
                        id,
                        full_name,
                        telegram_user_id,
                        first_workday,
                        created_at,
                        is_flow_scheduled,
                        desired_position,
                        salary_expectation,
                        candidate_status,
                        personal_data_consent,
                        employee_data_consent,
                        test_task_link,
                        test_task_due_at,
                        notes
                    )
                    SELECT
                        id,
                        NULLIF(full_name, ''),
                        NULLIF(telegram_user_id, ''),
                        first_workday,
                        created_at,
                        is_flow_scheduled,
                        desired_position,
                        salary_expectation,
                        candidate_status,
                        personal_data_consent,
                        employee_data_consent,
                        test_task_link,
                        test_task_due_at,
                        notes
                    FROM employees_old
                    """
                )
            )
            conn.execute(text("DROP TABLE employees_old"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_employees_id ON employees (id)"))
