from datetime import date, datetime
from typing import Optional

from sqlalchemy import Integer, String, Date, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Employee(Base):
    """Сотрудник, для которого запускается флоу первого дня."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telegram_user_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        doc="Telegram user_id или username (для простого демо).",
    )
    first_workday: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        doc="Дата первого рабочего дня (день, в который запускается флоу).",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_flow_scheduled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, doc="Запланирован ли флоу первого дня."
    )
    desired_position: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Желаемая должность (из ранних этапов флоу кандидата).",
    )
    salary_expectation: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Ожидания кандидата по зарплате.",
    )
    candidate_status: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        doc="Статус кандидата/сотрудника в процессе (new, invited, offer_sent и т.д.).",
    )
    personal_data_consent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Согласие на обработку персональных данных (этап кандидата).",
    )
    employee_data_consent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Повторное согласие на ПДн для оформления сотрудника.",
    )
    test_task_link: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
        doc="Ссылка на тестовое задание.",
    )
    test_task_due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        doc="Дедлайн тестового задания.",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        String(2048),
        nullable=True,
        doc="Свободные заметки HR по сотруднику.",
    )


class OnboardingEvent(Base):
    """Лог отправленных событий онбординга."""

    __tablename__ = "onboarding_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    event_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Ключ события (start_day, fill_form, manager_meeting и т.д.)",
    )
    message: Mapped[str] = mapped_column(String(2048), nullable=False)


class FlowLaunchRequest(Base):
    """Запрос на ручной запуск флоу из админки."""

    __tablename__ = "flow_launch_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    flow_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Ключ флоу (first_day, first_week, mid_probation, end_probation и т.д.)",
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class EmployeeFile(Base):
    """Файлы кандидата/сотрудника: входящие и исходящие."""

    __tablename__ = "employee_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    direction: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        doc="inbound | outbound",
    )
    category: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="resume, inn, snils, offer, sign_docs, candidate_file и т.д.",
    )
    telegram_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telegram_file_unique_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        doc="Абсолютный путь к файлу на диске.",
    )
    mime_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class HrSettings(Base):
    """Настройки HR для получения уведомлений."""

    __tablename__ = "hr_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    hr_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telegram_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class FlowStepTemplate(Base):
    """Редактируемые шаблоны шагов флоу."""

    __tablename__ = "flow_step_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    flow_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    step_title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    default_text: Mapped[str] = mapped_column(String(4096), nullable=False)
    custom_text: Mapped[Optional[str]] = mapped_column(String(4096), nullable=True)
