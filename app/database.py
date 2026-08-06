from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session

from .config import settings


class Base(DeclarativeBase):
    """Базовый класс для моделей SQLAlchemy."""


engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30} if settings.DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Создаёт таблицы в БД (для демо — без миграций)."""
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_schema()
    from .auth import seed_admin_accounts
    from .flow_templates import seed_flow_templates
    from .positions import seed_positions_catalog

    seed_admin_accounts()
    seed_flow_templates()
    seed_positions_catalog()


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
            "telegram_username": "TEXT",
            "current_menu_set_id": "INTEGER",
            "current_menu_path": "TEXT",
            "desired_position": "TEXT",
            "work_email": "TEXT",
            "work_hours": "TEXT",
            "is_manager": "BOOLEAN NOT NULL DEFAULT 0",
            "is_mentor": "BOOLEAN NOT NULL DEFAULT 0",
            "profile_photo_path": "TEXT",
            "profile_photo_filename": "TEXT",
            "salary_expectation": "TEXT",
            "candidate_status": "TEXT",
            "candidate_work_stage": "TEXT",
            "employee_stage": "TEXT",
            "manager_employee_id": "INTEGER",
            "mentor_adaptation_employee_id": "INTEGER",
            "mentor_ipr_employee_id": "INTEGER",
            "is_bot_blocked": "BOOLEAN NOT NULL DEFAULT 0",
            "birth_date": "DATE",
            "manager_telegram_id": "TEXT",
            "mentor_adaptation_telegram_id": "TEXT",
            "mentor_ipr_telegram_id": "TEXT",
            "adaptation_tasks_url": "TEXT",
            "adaptation_feedback_url": "TEXT",
            "adaptation_midpoint": "DATE",
            "adaptation_end": "DATE",
            "personal_data_consent": "BOOLEAN NOT NULL DEFAULT 0",
            "employee_data_consent": "BOOLEAN NOT NULL DEFAULT 0",
            "test_task_link": "TEXT",
            "test_task_due_at": "DATETIME",
            "notes": "TEXT",
        }
        for col, ddl in required.items():
            if col not in columns:
                conn.execute(text(f"ALTER TABLE employees ADD COLUMN {col} {ddl}"))

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    slug VARCHAR(128) NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL,
                    PRIMARY KEY (id)
                )
                """
            )
        )
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_positions_slug ON positions (slug)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_positions_id ON positions (id)"))

        employee_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(employees)")).fetchall()}
        if "desired_position" in employee_columns:
            conn.execute(
                text(
                    """
                    UPDATE employees
                    SET desired_position = CASE
                        WHEN desired_position IN ('Дизайнер', 'Project manager', 'Аналитик') THEN desired_position
                        WHEN desired_position IN ('Project Manager', 'PM', 'РМ', 'Product Manager') THEN 'Project manager'
                        ELSE desired_position
                    END
                    """
                )
            )
        if "employee_stage" in employee_columns:
            conn.execute(
                text(
                    """
                    UPDATE employees
                    SET employee_stage = CASE
                        WHEN employee_stage = 'employee' THEN 'staff'
                        WHEN employee_stage IN ('first_day', 'probation') THEN 'adaptation'
                        ELSE employee_stage
                    END
                    """
                )
            )

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
                        telegram_username TEXT,
                        current_menu_set_id INTEGER,
                        current_menu_path TEXT,
                        first_workday DATE,
                        birth_date DATE,
                        created_at DATETIME NOT NULL,
                        is_flow_scheduled BOOLEAN NOT NULL,
                        is_bot_blocked BOOLEAN NOT NULL DEFAULT 0,
                        desired_position TEXT,
                        work_email TEXT,
                        work_hours TEXT,
                        is_manager BOOLEAN NOT NULL DEFAULT 0,
                        is_mentor BOOLEAN NOT NULL DEFAULT 0,
                        profile_photo_path TEXT,
                        profile_photo_filename TEXT,
                        salary_expectation TEXT,
                        candidate_status TEXT,
                        candidate_work_stage TEXT,
                        employee_stage TEXT,
                        manager_employee_id INTEGER,
                        mentor_adaptation_employee_id INTEGER,
                        mentor_ipr_employee_id INTEGER,
                        manager_telegram_id TEXT,
                        mentor_adaptation_telegram_id TEXT,
                        mentor_ipr_telegram_id TEXT,
                        adaptation_tasks_url TEXT,
                        adaptation_feedback_url TEXT,
                        adaptation_midpoint DATE,
                        adaptation_end DATE,
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
                        telegram_username,
                        current_menu_set_id,
                        current_menu_path,
                        first_workday,
                        birth_date,
                        created_at,
                        is_flow_scheduled,
                        is_bot_blocked,
                        desired_position,
                        work_email,
                        work_hours,
                        is_manager,
                        is_mentor,
                        profile_photo_path,
                        profile_photo_filename,
                        salary_expectation,
                        candidate_status,
                        candidate_work_stage,
                        employee_stage,
                        manager_employee_id,
                        mentor_adaptation_employee_id,
                        mentor_ipr_employee_id,
                        manager_telegram_id,
                        mentor_adaptation_telegram_id,
                        mentor_ipr_telegram_id,
                        adaptation_tasks_url,
                        adaptation_feedback_url,
                        adaptation_midpoint,
                        adaptation_end,
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
                        telegram_username,
                        current_menu_set_id,
                        NULL,
                        first_workday,
                        NULL,
                        created_at,
                        is_flow_scheduled,
                        0,
                        desired_position,
                        NULL,
                        NULL,
                        0,
                        0,
                        NULL,
                        NULL,
                        salary_expectation,
                        candidate_status,
                        NULL,
                        employee_stage,
                        NULL,
                        NULL,
                        NULL,
                        NULL,
                        NULL,
                        NULL,
                        NULL,
                        NULL,
                        NULL,
                        NULL,
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

        scenario_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(flow_step_templates)")).fetchall()}
        scenario_required = {
            "parent_step_id": "INTEGER",
            "branch_option_index": "INTEGER",
            "response_type": "TEXT NOT NULL DEFAULT 'none'",
            "button_options": "TEXT",
            "send_mode": "TEXT NOT NULL DEFAULT 'immediate'",
            "send_time": "TEXT",
            "day_offset_workdays": "INTEGER NOT NULL DEFAULT 0",
            "target_field": "TEXT",
            "launch_scenario_key": "TEXT",
            "return_to_step_key": "TEXT",
            "attachment_path": "TEXT",
            "attachment_filename": "TEXT",
            "send_employee_card": "BOOLEAN NOT NULL DEFAULT 0",
            "notify_on_send_text": "TEXT",
            "notify_on_send_recipient_ids": "TEXT",
            "notify_on_send_recipient_scope": "TEXT",
        }
        for col, ddl in scenario_required.items():
            if col not in scenario_columns:
                conn.execute(text(f"ALTER TABLE flow_step_templates ADD COLUMN {col} {ddl}"))

        button_notification_columns = conn.execute(text("PRAGMA table_info(step_button_notifications)")).fetchall()
        if not button_notification_columns:
            conn.execute(
                text(
                    """
                    CREATE TABLE step_button_notifications (
                        id INTEGER NOT NULL,
                        flow_key VARCHAR(64) NOT NULL,
                        step_id INTEGER NOT NULL,
                        option_index INTEGER NOT NULL,
                        rule_index INTEGER NOT NULL DEFAULT 0,
                        message_text VARCHAR(4096),
                        recipient_ids VARCHAR(2048),
                        recipient_scope VARCHAR(255),
                        PRIMARY KEY (id)
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_step_button_notifications_id ON step_button_notifications (id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_step_button_notifications_flow_key ON step_button_notifications (flow_key)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_step_button_notifications_step_id ON step_button_notifications (step_id)"))
        else:
            button_notification_column_names = {row[1] for row in button_notification_columns}
            if "rule_index" not in button_notification_column_names:
                conn.execute(text("ALTER TABLE step_button_notifications ADD COLUMN rule_index INTEGER NOT NULL DEFAULT 0"))
                conn.execute(text("UPDATE step_button_notifications SET rule_index = 0 WHERE rule_index IS NULL"))

        step_send_notification_columns = conn.execute(text("PRAGMA table_info(step_send_notifications)")).fetchall()
        if not step_send_notification_columns:
            conn.execute(
                text(
                    """
                    CREATE TABLE step_send_notifications (
                        id INTEGER NOT NULL,
                        flow_key VARCHAR(64) NOT NULL,
                        step_id INTEGER NOT NULL,
                        rule_index INTEGER NOT NULL DEFAULT 0,
                        message_text VARCHAR(4096),
                        recipient_ids VARCHAR(2048),
                        recipient_scope VARCHAR(255),
                        PRIMARY KEY (id)
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_step_send_notifications_id ON step_send_notifications (id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_step_send_notifications_flow_key ON step_send_notifications (flow_key)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_step_send_notifications_step_id ON step_send_notifications (step_id)"))

        scenario_table_columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(scenario_templates)")).fetchall()
        }
        if scenario_table_columns and "trigger_mode" not in scenario_table_columns:
            conn.execute(
                text(
                    "ALTER TABLE scenario_templates ADD COLUMN trigger_mode TEXT NOT NULL DEFAULT 'manual_only'"
                )
            )
        if scenario_table_columns and "scenario_kind" not in scenario_table_columns:
            conn.execute(
                text(
                    "ALTER TABLE scenario_templates ADD COLUMN scenario_kind TEXT NOT NULL DEFAULT 'scenario'"
                )
            )
        if scenario_table_columns and "sort_order" not in scenario_table_columns:
            conn.execute(
                text(
                    "ALTER TABLE scenario_templates ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"
                )
            )
        if scenario_table_columns and "target_employee_id" not in scenario_table_columns:
            conn.execute(
                text(
                    "ALTER TABLE scenario_templates ADD COLUMN target_employee_id INTEGER"
                )
            )
        if scenario_table_columns and "employee_scope" not in scenario_table_columns:
            conn.execute(
                text(
                    "ALTER TABLE scenario_templates ADD COLUMN employee_scope TEXT NOT NULL DEFAULT 'all'"
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE scenario_templates
                    SET employee_scope = 'candidates'
                    WHERE scenario_key = 'recruitment_hiring'
                    """
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE scenario_templates
                    SET employee_scope = 'employees'
                    WHERE scenario_key IN (
                        'first_day',
                        'first_week',
                        'mid_probation',
                        'end_probation',
                        'mid_feedback',
                        'end_feedback',
                        'end_summary'
                    )
                    """
                )
            )
        if scenario_table_columns and "candidate_work_stage_trigger" not in scenario_table_columns:
            conn.execute(text("ALTER TABLE scenario_templates ADD COLUMN candidate_work_stage_trigger TEXT"))
        if scenario_table_columns and "recipient_mode" not in scenario_table_columns:
            conn.execute(
                text(
                    "ALTER TABLE scenario_templates ADD COLUMN recipient_mode TEXT NOT NULL DEFAULT 'self'"
                )
            )
        if scenario_table_columns and "sort_order" in {row[1] for row in conn.execute(text("PRAGMA table_info(scenario_templates)")).fetchall()}:
            conn.execute(
                text(
                    """
                    UPDATE scenario_templates
                    SET sort_order = id * 10
                    WHERE sort_order IS NULL OR sort_order = 0
                    """
                )
            )

        progress_table_info = conn.execute(text("PRAGMA table_info(scenario_progress)")).fetchall()
        if not progress_table_info:
            conn.execute(
                text(
                    """
                    CREATE TABLE scenario_progress (
                        id INTEGER NOT NULL,
                        employee_id INTEGER NOT NULL,
                        scenario_key VARCHAR(64) NOT NULL,
                        recipient_mode TEXT NOT NULL DEFAULT 'self',
                        recipient_employee_id INTEGER,
                        recipient_chat_id TEXT,
                        current_step_key VARCHAR(128),
                        step_history TEXT,
                        response_undo_history TEXT,
                        waiting_for_response BOOLEAN NOT NULL DEFAULT 0,
                        is_completed BOOLEAN NOT NULL DEFAULT 0,
                        last_delivery_error TEXT,
                        started_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        completed_at DATETIME,
                        PRIMARY KEY (id)
                    )
                    """
                )
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_scenario_progress_id ON scenario_progress (id)")
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_scenario_progress_employee_id ON scenario_progress (employee_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_scenario_progress_scenario_key ON scenario_progress (scenario_key)"
                )
            )
        else:
            progress_columns = {row[1] for row in progress_table_info}
            if "recipient_mode" not in progress_columns:
                conn.execute(text("ALTER TABLE scenario_progress ADD COLUMN recipient_mode TEXT NOT NULL DEFAULT 'self'"))
            if "recipient_employee_id" not in progress_columns:
                conn.execute(text("ALTER TABLE scenario_progress ADD COLUMN recipient_employee_id INTEGER"))
            if "recipient_chat_id" not in progress_columns:
                conn.execute(text("ALTER TABLE scenario_progress ADD COLUMN recipient_chat_id TEXT"))
            if "step_history" not in progress_columns:
                conn.execute(text("ALTER TABLE scenario_progress ADD COLUMN step_history TEXT"))
            if "response_undo_history" not in progress_columns:
                conn.execute(text("ALTER TABLE scenario_progress ADD COLUMN response_undo_history TEXT"))
            if "last_delivery_error" not in progress_columns:
                conn.execute(text("ALTER TABLE scenario_progress ADD COLUMN last_delivery_error TEXT"))

        employee_document_link_columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(employee_document_links)")).fetchall()
        }
        if employee_document_link_columns:
            if "slot_key" not in employee_document_link_columns:
                conn.execute(text("ALTER TABLE employee_document_links ADD COLUMN slot_key TEXT"))
                conn.execute(
                    text(
                        """
                        UPDATE employee_document_links
                        SET slot_key = 'offer'
                        WHERE title = 'Оффер' AND (slot_key IS NULL OR slot_key = '')
                        """
                    )
                )
            if "item_kind" not in employee_document_link_columns:
                conn.execute(text("ALTER TABLE employee_document_links ADD COLUMN item_kind TEXT NOT NULL DEFAULT 'link'"))
            if "employee_file_id" not in employee_document_link_columns:
                conn.execute(text("ALTER TABLE employee_document_links ADD COLUMN employee_file_id INTEGER"))

        survey_answers_info = conn.execute(text("PRAGMA table_info(survey_answers)")).fetchall()
        if not survey_answers_info:
            conn.execute(
                text(
                    """
                    CREATE TABLE survey_answers (
                        id INTEGER NOT NULL,
                        employee_id INTEGER NOT NULL,
                        scenario_key VARCHAR(64) NOT NULL,
                        step_key VARCHAR(128) NOT NULL,
                        answer_value VARCHAR(4096),
                        file_name VARCHAR(255),
                        answered_at DATETIME NOT NULL,
                        PRIMARY KEY (id)
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_survey_answers_id ON survey_answers (id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_survey_answers_employee_id ON survey_answers (employee_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_survey_answers_scenario_key ON survey_answers (scenario_key)"))

        admin_accounts_info = conn.execute(text("PRAGMA table_info(admin_accounts)")).fetchall()
        if not admin_accounts_info:
            conn.execute(
                text(
                    """
                    CREATE TABLE admin_accounts (
                        id INTEGER NOT NULL,
                        login VARCHAR(64) NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        role VARCHAR(32) NOT NULL,
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        PRIMARY KEY (id)
                    )
                    """
                )
            )
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_admin_accounts_login ON admin_accounts (login)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_admin_accounts_id ON admin_accounts (id)"))

        flow_launch_columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(flow_launch_requests)")).fetchall()
        }
        if flow_launch_columns and "skip_step_key" not in flow_launch_columns:
            conn.execute(text("ALTER TABLE flow_launch_requests ADD COLUMN skip_step_key TEXT"))
        if flow_launch_columns and "launch_type" not in flow_launch_columns:
            conn.execute(text("ALTER TABLE flow_launch_requests ADD COLUMN launch_type TEXT NOT NULL DEFAULT 'manual'"))

        hr_settings_columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(hr_settings)")).fetchall()
        }
        hr_settings_required = {
            "notification_recipient_ids": "TEXT",
            "notify_scenario_completed": "BOOLEAN NOT NULL DEFAULT 1",
            "notify_test_task_received": "BOOLEAN NOT NULL DEFAULT 1",
            "notify_user_actions": "BOOLEAN NOT NULL DEFAULT 1",
            "default_menu_set_id": "INTEGER",
            "default_employee_menu_set_id": "INTEGER",
            "default_candidate_menu_set_id": "INTEGER",
        }
        for col, ddl in hr_settings_required.items():
            if hr_settings_columns and col not in hr_settings_columns:
                conn.execute(text(f"ALTER TABLE hr_settings ADD COLUMN {col} {ddl}"))

        menu_sets_info = conn.execute(text("PRAGMA table_info(bot_menu_sets)")).fetchall()
        if not menu_sets_info:
            conn.execute(
                text(
                    """
                    CREATE TABLE bot_menu_sets (
                        id INTEGER NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        description VARCHAR(1024),
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        role_scope VARCHAR(64) NOT NULL DEFAULT 'all',
                        employee_scope VARCHAR(64) NOT NULL DEFAULT 'all',
                        target_employee_id INTEGER,
                        target_employee_ids VARCHAR(1024),
                        target_employee_stages VARCHAR(255),
                        target_candidate_stages VARCHAR(255),
                        PRIMARY KEY (id)
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_bot_menu_sets_id ON bot_menu_sets (id)"))
        else:
            menu_sets_columns = {row[1] for row in menu_sets_info}
            menu_sets_required = {
                "role_scope": "VARCHAR(64) NOT NULL DEFAULT 'all'",
                "employee_scope": "VARCHAR(64) NOT NULL DEFAULT 'all'",
                "target_employee_id": "INTEGER",
                "target_employee_ids": "VARCHAR(1024)",
                "target_employee_stages": "VARCHAR(255)",
                "target_candidate_stages": "VARCHAR(255)",
                "system_tag": "VARCHAR(255)",
            }
            for col, ddl in menu_sets_required.items():
                if col not in menu_sets_columns:
                    conn.execute(text(f"ALTER TABLE bot_menu_sets ADD COLUMN {col} {ddl}"))

        menu_buttons_info = conn.execute(text("PRAGMA table_info(bot_menu_buttons)")).fetchall()
        if not menu_buttons_info:
            conn.execute(
                text(
                    """
                    CREATE TABLE bot_menu_buttons (
                        id INTEGER NOT NULL,
                        menu_set_id INTEGER NOT NULL,
                        label VARCHAR(255) NOT NULL,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        action_type VARCHAR(32) NOT NULL DEFAULT 'inactive',
                        scenario_key VARCHAR(64),
                        target_menu_set_id INTEGER,
                        document_item_id INTEGER,
                        PRIMARY KEY (id)
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_bot_menu_buttons_id ON bot_menu_buttons (id)"))
        else:
            menu_buttons_columns = {row[1] for row in menu_buttons_info}
            if "document_item_id" not in menu_buttons_columns:
                conn.execute(text("ALTER TABLE bot_menu_buttons ADD COLUMN document_item_id INTEGER"))

        document_library_info = conn.execute(text("PRAGMA table_info(document_library_items)")).fetchall()
        if not document_library_info:
            conn.execute(
                text(
                    """
                    CREATE TABLE document_library_items (
                        id INTEGER NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        description VARCHAR(1024),
                        category VARCHAR(255),
                        item_kind VARCHAR(16) NOT NULL DEFAULT 'file',
                        external_url VARCHAR(2048),
                        original_filename VARCHAR(255),
                        stored_path VARCHAR(1024),
                        mime_type VARCHAR(128),
                        file_size INTEGER,
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        PRIMARY KEY (id)
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_document_library_items_id ON document_library_items (id)"))

        mass_scenario_columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(mass_scenario_actions)")).fetchall()
        }
        if mass_scenario_columns and "target_employee_id" not in mass_scenario_columns:
            conn.execute(text("ALTER TABLE mass_scenario_actions ADD COLUMN target_employee_id INTEGER"))
        if mass_scenario_columns and "target_role_scope" not in mass_scenario_columns:
            conn.execute(text("ALTER TABLE mass_scenario_actions ADD COLUMN target_role_scope TEXT"))
        if mass_scenario_columns and "target_employee_stages" not in mass_scenario_columns:
            conn.execute(text("ALTER TABLE mass_scenario_actions ADD COLUMN target_employee_stages TEXT"))
        if mass_scenario_columns and "target_candidate_stages" not in mass_scenario_columns:
            conn.execute(text("ALTER TABLE mass_scenario_actions ADD COLUMN target_candidate_stages TEXT"))

        mass_message_columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(mass_message_actions)")).fetchall()
        }
        if mass_message_columns and "target_employee_id" not in mass_message_columns:
            conn.execute(text("ALTER TABLE mass_message_actions ADD COLUMN target_employee_id INTEGER"))
        if mass_message_columns and "target_role_scope" not in mass_message_columns:
            conn.execute(text("ALTER TABLE mass_message_actions ADD COLUMN target_role_scope TEXT"))
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_bot_menu_buttons_menu_set_id ON bot_menu_buttons (menu_set_id)")
            )
        if mass_message_columns and "target_employee_stages" not in mass_message_columns:
            conn.execute(text("ALTER TABLE mass_message_actions ADD COLUMN target_employee_stages TEXT"))
        if mass_message_columns and "target_candidate_stages" not in mass_message_columns:
            conn.execute(text("ALTER TABLE mass_message_actions ADD COLUMN target_candidate_stages TEXT"))

        mass_scenario_actions_info = conn.execute(text("PRAGMA table_info(mass_scenario_actions)")).fetchall()
        if not mass_scenario_actions_info:
            conn.execute(
                text(
                    """
                    CREATE TABLE mass_scenario_actions (
                        id INTEGER NOT NULL,
                        flow_key VARCHAR(64) NOT NULL,
                        scenario_kind VARCHAR(32) NOT NULL DEFAULT 'scenario',
                        requested_at DATETIME NOT NULL,
                        processed_at DATETIME,
                        launch_type VARCHAR(32) NOT NULL DEFAULT 'manual',
                        target_all BOOLEAN NOT NULL DEFAULT 0,
                        target_statuses VARCHAR(255),
                        target_employee_stages VARCHAR(255),
                        target_candidate_stages VARCHAR(255),
                        recipient_count INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL,
                        PRIMARY KEY (id)
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_mass_scenario_actions_id ON mass_scenario_actions (id)"))
        elif "scenario_kind" not in {row[1] for row in mass_scenario_actions_info}:
            conn.execute(
                text("ALTER TABLE mass_scenario_actions ADD COLUMN scenario_kind TEXT NOT NULL DEFAULT 'scenario'")
            )

        mass_message_actions_info = conn.execute(text("PRAGMA table_info(mass_message_actions)")).fetchall()
        if not mass_message_actions_info:
            conn.execute(
                text(
                    """
                    CREATE TABLE mass_message_actions (
                        id INTEGER NOT NULL,
                        message_text VARCHAR(4096) NOT NULL,
                        requested_at DATETIME NOT NULL,
                        processed_at DATETIME,
                        launch_type VARCHAR(32) NOT NULL DEFAULT 'manual',
                        target_all BOOLEAN NOT NULL DEFAULT 0,
                        target_statuses VARCHAR(255),
                        target_employee_stages VARCHAR(255),
                        target_candidate_stages VARCHAR(255),
                        recipient_count INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL,
                        PRIMARY KEY (id)
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_mass_message_actions_id ON mass_message_actions (id)"))

        messenger_accounts_info = conn.execute(text("PRAGMA table_info(employee_messenger_accounts)")).fetchall()
        if not messenger_accounts_info:
            conn.execute(
                text(
                    """
                    CREATE TABLE employee_messenger_accounts (
                        id INTEGER NOT NULL,
                        employee_id INTEGER NOT NULL,
                        channel VARCHAR(32) NOT NULL,
                        external_user_id VARCHAR(255) NOT NULL,
                        external_username VARCHAR(255),
                        is_primary BOOLEAN NOT NULL DEFAULT 0,
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        PRIMARY KEY (id)
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_employee_messenger_accounts_id ON employee_messenger_accounts (id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_employee_messenger_accounts_employee_id ON employee_messenger_accounts (employee_id)"))
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_employee_messenger_accounts_channel_user ON employee_messenger_accounts (channel, external_user_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_employee_messenger_accounts_employee_channel ON employee_messenger_accounts (employee_id, channel)"
                )
            )

        employee_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(employees)")).fetchall()}
        if messenger_accounts_info or conn.execute(text("PRAGMA table_info(employee_messenger_accounts)")).fetchall():
            if {"telegram_user_id", "telegram_username"} <= employee_columns:
                conn.execute(
                    text(
                        """
                        INSERT OR IGNORE INTO employee_messenger_accounts (
                            employee_id,
                            channel,
                            external_user_id,
                            external_username,
                            is_primary,
                            is_active,
                            created_at,
                            updated_at
                        )
                        SELECT
                            e.id,
                            'telegram',
                            TRIM(e.telegram_user_id),
                            NULLIF(TRIM(COALESCE(e.telegram_username, '')), ''),
                            1,
                            1,
                            COALESCE(e.created_at, CURRENT_TIMESTAMP),
                            CURRENT_TIMESTAMP
                        FROM employees e
                        WHERE NULLIF(TRIM(COALESCE(e.telegram_user_id, '')), '') IS NOT NULL
                          AND NOT EXISTS (
                              SELECT 1
                              FROM employee_messenger_accounts a
                              WHERE a.channel = 'telegram'
                                AND a.external_user_id = TRIM(e.telegram_user_id)
                          )
                        """
                    )
                )
