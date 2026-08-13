from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Index, Integer, String, UniqueConstraint
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
    telegram_username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Публичный username Telegram без @ для построения ссылки на профиль.",
    )
    current_menu_set_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Текущий набор кнопок чат-бота, показанный пользователю.",
    )
    current_menu_path: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
        doc="Стек открытых наборов меню чат-бота для навигации назад.",
    )
    first_workday: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        doc="Дата первого рабочего дня (день, в который запускается флоу).",
    )
    birth_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        doc="Дата рождения сотрудника.",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_flow_scheduled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, doc="Запланирован ли флоу первого дня."
    )
    is_bot_blocked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, doc="Заблокирован ли доступ сотрудника к чат-боту."
    )
    desired_position: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Желаемая должность (из ранних этапов флоу кандидата).",
    )
    work_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Рабочая почта сотрудника.",
    )
    work_hours: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Рабочие часы сотрудника.",
    )
    is_manager: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Может ли сотрудник выступать руководителем для других сотрудников.",
    )
    is_mentor: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Может ли сотрудник выступать наставником для других сотрудников.",
    )
    profile_photo_path: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
        doc="Абсолютный путь к фото сотрудника для карточки.",
    )
    profile_photo_filename: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Имя файла фото сотрудника для карточки.",
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
    candidate_work_stage: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        doc="Текущий этап работы с кандидатом, который указывает HR вручную.",
    )
    employee_stage: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        doc="Статус записи: candidate | adaptation | ipr | staff.",
    )
    manager_employee_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="ID руководителя сотрудника в базе сотрудников.",
    )
    mentor_adaptation_employee_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="ID наставника по адаптации в базе сотрудников.",
    )
    mentor_ipr_employee_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="ID наставника по ИПР в базе сотрудников.",
    )
    manager_telegram_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        doc="Telegram ID руководителя сотрудника.",
    )
    mentor_adaptation_telegram_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        doc="Telegram ID наставника по адаптации.",
    )
    mentor_ipr_telegram_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        doc="Telegram ID наставника по ИПР.",
    )
    adaptation_tasks_url: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
        doc="Ссылка на файл с задачами на испытательный срок.",
    )
    adaptation_feedback_url: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
        doc="Ссылка на файл обратной связи по адаптации.",
    )
    adaptation_midpoint: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        doc="Дата середины адаптации.",
    )
    adaptation_end: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        doc="Дата завершения адаптации.",
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


class EmployeeAssignmentHistory(Base):
    """История назначений руководителей и наставников по сотруднику."""

    __tablename__ = "employee_assignment_history"
    __table_args__ = (
        Index("ix_employee_assignment_history_subject_role_active", "subject_employee_id", "assignment_role", "ended_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    subject_employee_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    assigned_employee_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    assignment_role: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Роль назначения: manager | mentor_adaptation | mentor_ipr.",
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assigned_by_account_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EmployeeManualBotMessage(Base):
    """История ручных Telegram-сообщений из карточки сотрудника."""

    __tablename__ = "employee_manual_bot_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sender_account_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    message_text: Mapped[str] = mapped_column(String(4096), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="sent | failed",
    )
    error_text: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Position(Base):
    """Управляемый справочник должностей."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EmployeeMessengerAccount(Base):
    """Канал связи сотрудника в конкретном мессенджере."""

    __tablename__ = "employee_messenger_accounts"
    __table_args__ = (
        UniqueConstraint("channel", "external_user_id", name="uq_employee_messenger_accounts_channel_user"),
        Index("ix_employee_messenger_accounts_employee_channel", "employee_id", "channel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="Канал связи: telegram, max и т.д.",
    )
    external_user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Идентификатор пользователя в канале.",
    )
    external_username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Публичный username/handle пользователя в канале.",
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Основной канал сотрудника для исходящих сообщений.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Активен ли этот канал связи.",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


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
    launch_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="manual",
        doc="manual | scheduled | status_transition",
    )
    skip_step_key: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        doc="Шаг, который уже был отправлен вручную и должен быть пропущен планировщиком.",
    )


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


class EmployeeDocumentLink(Base):
    """Ссылки на персональные документы сотрудника."""

    __tablename__ = "employee_document_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    slot_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    item_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="link")
    employee_file_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DocumentLibraryItem(Base):
    """Общая библиотека документов и ссылок для меню бота."""

    __tablename__ = "document_library_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    item_kind: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="file",
        doc="file | link",
    )
    external_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stored_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class HrSettings(Base):
    """Настройки HR для получения уведомлений."""

    __tablename__ = "hr_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    hr_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telegram_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    notification_recipient_ids: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    notify_scenario_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_test_task_received: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_user_actions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_menu_set_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    default_employee_menu_set_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    default_candidate_menu_set_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class BotMenuSet(Base):
    """Набор кнопок меню чат-бота."""

    __tablename__ = "bot_menu_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    role_scope: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="all",
        doc="Роль/должность, для которой доступен набор меню.",
    )
    employee_scope: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="all",
        doc="Аудитория набора: all | employees | candidates.",
    )
    target_employee_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Точечная привязка к конкретному сотруднику/кандидату.",
    )
    target_employee_ids: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
        doc="CSV-список id сотрудников/кандидатов для точечного таргетинга набора меню.",
    )
    target_employee_stages: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="CSV-список employee_stage значений для таргетинга.",
    )
    target_candidate_stages: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="CSV-список candidate_work_stage значений для таргетинга.",
    )
    system_tag: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Служебный тег для системно-сгенерированных наборов меню.",
    )


class BotMenuButton(Base):
    """Кнопка внутри набора меню чат-бота."""

    __tablename__ = "bot_menu_buttons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    menu_set_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    action_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="inactive",
        doc="inactive | launch_scenario | open_set | send_document",
    )
    scenario_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_menu_set_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    document_item_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class MassScenarioAction(Base):
    """Массовый запуск сценария по группе сотрудников."""

    __tablename__ = "mass_scenario_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    flow_key: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="scenario")
    requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    launch_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    target_all: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    target_statuses: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_employee_stages: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_candidate_stages: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_role_scope: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_employee_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class MassMessageAction(Base):
    """Массовая отправка сообщения по группе сотрудников."""

    __tablename__ = "mass_message_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    message_text: Mapped[str] = mapped_column(String(4096), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    launch_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    target_all: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    target_statuses: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_employee_stages: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_candidate_stages: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_role_scope: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_employee_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AdminAccount(Base):
    """Пользователь админки."""

    __tablename__ = "admin_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    login: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="hr",
        doc="admin | hr",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ScenarioTemplate(Base):
    """Редактируемый сценарий с метаданными."""

    __tablename__ = "scenario_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scenario_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scenario_kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="scenario",
        doc="scenario | survey",
    )
    role_scope: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="all",
        doc="designer | project_manager | analyst | all",
    )
    employee_scope: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="all",
        doc="all | employees | candidates",
    )
    trigger_mode: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="manual_only",
        doc="manual_only | bot_registration | scenario_transition | candidate_hr_stage | first_workday | first_week_friday | mid_probation | end_probation",
    )
    candidate_work_stage_trigger: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        doc="Опциональный HR-статус кандидата, который запускает сценарий при trigger_mode=candidate_hr_stage.",
    )
    recipient_mode: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="self",
        doc="Кому отправлять шаги сценария: self | manager | mentor_adaptation | mentor_ipr | hr.",
    )
    target_employee_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Опциональная привязка сценария/опроса к конкретному сотруднику.",
    )
    description: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)


class FlowStepTemplate(Base):
    """Редактируемые шаблоны шагов сценария."""

    __tablename__ = "flow_step_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    flow_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    parent_step_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    branch_option_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    step_title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    default_text: Mapped[str] = mapped_column(String(4096), nullable=False)
    custom_text: Mapped[Optional[str]] = mapped_column(String(4096), nullable=True)
    response_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="none",
        doc="none | text | file | buttons",
    )
    button_options: Mapped[Optional[str]] = mapped_column(
        String(4096),
        nullable=True,
        doc="Кнопки через перевод строки, если response_type=buttons.",
    )
    send_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="immediate",
        doc="immediate | specific_time",
    )
    send_time: Mapped[Optional[str]] = mapped_column(
        String(16),
        nullable=True,
        doc="HH:MM, если send_mode=specific_time.",
    )
    day_offset_workdays: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Смещение в рабочих днях относительно даты запуска сценария.",
    )
    target_field: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        doc="Куда сохранять ответ сотрудника: full_name, desired_position, salary_expectation, personal_data_consent, resume и т.д.",
    )
    launch_scenario_key: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        doc="Какой сценарий запускать для перехода из ветки.",
    )
    return_to_step_key: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        doc="Ключ root-step того же сценария, к которому ветка должна вернуться после завершения.",
    )
    attachment_path: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
        doc="Абсолютный путь к документу, прикрепленному к шагу.",
    )
    attachment_filename: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Оригинальное имя прикрепленного к шагу файла.",
    )
    send_employee_card: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Нужно ли отправлять карточку сотрудника как изображение на этом шаге.",
    )
    notify_on_send_text: Mapped[Optional[str]] = mapped_column(
        String(4096),
        nullable=True,
        doc="Текст уведомления, которое отправляется при показе этого шага.",
    )
    notify_on_send_recipient_ids: Mapped[Optional[str]] = mapped_column(
        String(2048),
        nullable=True,
        doc="Список Telegram ID получателей уведомления через запятую или с новой строки.",
    )
    notify_on_send_recipient_scope: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Связанные адресаты из карточки сотрудника: manager, mentor_adaptation, mentor_ipr.",
    )


class StepButtonNotification(Base):
    """Уведомление, которое отправляется при выборе конкретной кнопки шага."""

    __tablename__ = "step_button_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    flow_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    option_index: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message_text: Mapped[Optional[str]] = mapped_column(String(4096), nullable=True)
    recipient_ids: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    recipient_scope: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Связанные адресаты из карточки сотрудника: manager, mentor_adaptation, mentor_ipr.",
    )


class StepSendNotification(Base):
    """Уведомление, которое отправляется при показе конкретного шага."""

    __tablename__ = "step_send_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    flow_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    rule_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message_text: Mapped[Optional[str]] = mapped_column(String(4096), nullable=True)
    recipient_ids: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    recipient_scope: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Связанные адресаты из карточки сотрудника: manager, mentor_adaptation, mentor_ipr.",
    )


class ScenarioProgress(Base):
    """Текущее состояние сценария для сотрудника."""

    __tablename__ = "scenario_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    scenario_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    recipient_mode: Mapped[str] = mapped_column(String(64), nullable=False, default="self")
    recipient_employee_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    recipient_chat_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    current_step_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    step_history: Mapped[Optional[str]] = mapped_column(
        String(4096),
        nullable=True,
        doc="История интерактивных шагов через перевод строки для отката назад.",
    )
    response_undo_history: Mapped[Optional[str]] = mapped_column(
        String(16384),
        nullable=True,
        doc="JSON-стек снимков последнего подтвержденного ответа для rollback по кнопке назад.",
    )
    waiting_for_response: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_delivery_error: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
        doc="Последняя ошибка доставки шага сценария адресату.",
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SurveyAnswer(Base):
    """Ответ пользователя на вопрос опроса."""

    __tablename__ = "survey_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    scenario_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    answer_value: Mapped[Optional[str]] = mapped_column(String(4096), nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    answered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
