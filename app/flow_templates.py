from __future__ import annotations

from typing import Optional

from .database import SessionLocal
from .models import FlowStepTemplate, ScenarioTemplate


ROLE_SCOPE_ALL = "all"
ROLE_SCOPE_DESIGNER = "designer"
ROLE_SCOPE_PROJECT_MANAGER = "project_manager"
ROLE_SCOPE_ANALYST = "analyst"

ROLE_SCOPE_LABELS = {
    ROLE_SCOPE_ALL: "Для всех ролей",
    ROLE_SCOPE_DESIGNER: "Дизайнер",
    ROLE_SCOPE_PROJECT_MANAGER: "Project manager",
    ROLE_SCOPE_ANALYST: "Аналитик",
}

TRIGGER_MODE_LABELS = {
    "manual_only": "Только вручную",
    "bot_registration": "Сразу после регистрации в боте",
    "scenario_transition": "При переходе из другого сценария",
    "first_workday": "В первый рабочий день",
    "first_week_friday": "В пятницу первой рабочей недели",
    "mid_probation": "В середине испытательного срока",
    "end_probation": "В конце испытательного срока",
}

RESPONSE_TYPE_LABELS = {
    "none": "Без ответа",
    "text": "Текстовый ответ",
    "file": "Загрузка файла",
    "buttons": "Выбор кнопками",
    "branching": "Ветвление",
}

SEND_MODE_LABELS = {
    "immediate": "Сразу после ответа на предыдущее сообщение",
    "specific_time": "В конкретное время",
}

TARGET_FIELD_LABELS = {
    "": "Не сохранять в поле сотрудника",
    "full_name": "ФИО",
    "desired_position": "Желаемая должность",
    "salary_expectation": "Ожидания по доходу",
    "personal_data_consent": "Согласие на ПДн кандидата",
    "employee_data_consent": "Согласие на ПДн сотрудника",
    "candidate_status": "Статус кандидата",
    "resume": "Резюме (файл)",
    "candidate_file": "Файл кандидата",
}

NOTIFICATION_RECIPIENT_SCOPE_LABELS = {
    "": "Не добавлять адресатов из карточки",
    "manager": "Руководитель сотрудника",
    "mentor_adaptation": "Наставник (адаптация)",
    "mentor_ipr": "Наставник (ИПР)",
    "manager,mentor_adaptation": "Руководитель + наставник (адаптация)",
    "manager,mentor_ipr": "Руководитель + наставник (ИПР)",
    "mentor_adaptation,mentor_ipr": "Оба наставника",
    "manager,mentor_adaptation,mentor_ipr": "Все связанные сотрудники",
}

EMPLOYEE_ROLE_VALUES = [
    "Дизайнер",
    "Project manager",
    "Аналитик",
]

SCENARIO_DEFINITIONS = [
    {
        "scenario_key": "recruitment_hiring",
        "title": "Подбор и найм",
        "role_scope": ROLE_SCOPE_ALL,
        "trigger_mode": "bot_registration",
        "description": "Первичный сценарий кандидата от согласия до сбора ключевых данных.",
        "steps": [
            {
                "step_key": "recruitment_consent_request",
                "step_title": "Согласие на ПДн",
                "sort_order": 10,
                "default_text": (
                    "Привет! Я HR-бот. Я создал черновик вашей карточки в админке и привязал этот Telegram. "
                    "HR может отредактировать данные и при необходимости привязать вас к существующей карточке.\n\n"
                    "Чтобы начать наше сотрудничество, нам нужно твое согласие на обработку персональных данных.\n"
                    "Мы используем их исключительно в рамках процесса подбора"
                ),
                "response_type": "buttons",
                "button_options": "Да, согласен\nНет",
                "send_mode": "immediate",
                "send_time": None,
                "day_offset_workdays": 0,
                "target_field": "personal_data_consent",
            },
            {
                "step_key": "recruitment_ask_full_name",
                "step_title": "Запрос полного ФИО",
                "sort_order": 20,
                "default_text": "Отлично! Подскажи, пожалуйста, свое полное ФИО.",
                "response_type": "text",
                "button_options": None,
                "send_mode": "immediate",
                "send_time": None,
                "day_offset_workdays": 0,
                "target_field": "full_name",
            },
            {
                "step_key": "recruitment_ask_position",
                "step_title": "Запрос желаемой должности",
                "sort_order": 30,
                "default_text": "На какую должность ты рассматриваешься?",
                "response_type": "buttons",
                "button_options": "Дизайнер\nProject manager\nАналитик",
                "send_mode": "immediate",
                "send_time": None,
                "day_offset_workdays": 0,
                "target_field": "desired_position",
            },
            {
                "step_key": "recruitment_ask_resume",
                "step_title": "Запрос резюме",
                "sort_order": 40,
                "default_text": "Пришли, пожалуйста, свое резюме файлом (PDF / DOC / DOCX).",
                "response_type": "file",
                "button_options": None,
                "send_mode": "immediate",
                "send_time": None,
                "day_offset_workdays": 0,
                "target_field": "resume",
            },
            {
                "step_key": "recruitment_ask_salary",
                "step_title": "Запрос ожиданий по зарплате",
                "sort_order": 50,
                "default_text": "Какой уровень дохода для тебя комфортен? Можешь указать диапазон.",
                "response_type": "text",
                "button_options": None,
                "send_mode": "immediate",
                "send_time": None,
                "day_offset_workdays": 0,
                "target_field": "salary_expectation",
            },
            {
                "step_key": "recruitment_primary_done",
                "step_title": "Завершение первичного сбора",
                "sort_order": 60,
                "default_text": (
                    "Спасибо! Мы получили первичные данные. "
                    "Дальше HR проверит информацию и вернется к тебе со следующим шагом."
                ),
                "response_type": "none",
                "button_options": None,
                "send_mode": "immediate",
                "send_time": None,
                "day_offset_workdays": 0,
                "target_field": None,
            },
        ],
    },
    {
        "scenario_key": "first_day",
        "title": "Первый рабочий день",
        "role_scope": ROLE_SCOPE_ALL,
        "trigger_mode": "first_workday",
        "description": "Сценарий первого рабочего дня сотрудника.",
        "steps": [
            {"step_key": "day_start_10", "step_title": "10:00 старт дня", "sort_order": 10, "default_text": "Доброе утро! Сегодня ваш первый рабочий день. В 10:30 вас ждет встреча с HR. Если возникнут вопросы - смело задавайте их в этом чате.", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "10:00", "day_offset_workdays": 0, "target_field": None},
            {"step_key": "fill_form_11", "step_title": "11:00 анкета", "sort_order": 20, "default_text": "Пора заполнить анкету нового сотрудника. Пожалуйста, перейдите по ссылке и заполните форму: https://example.com/forms/new-employee", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "11:00", "day_offset_workdays": 0, "target_field": None},
            {"step_key": "documents_11_30", "step_title": "11:30 документы", "sort_order": 30, "default_text": "Я отправил вам пакет документов для ознакомления и подписи. Проверьте, пожалуйста, вашу корпоративную почту или систему ЭДО.", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "11:30", "day_offset_workdays": 0, "target_field": None},
            {"step_key": "manager_meeting_12", "step_title": "12:00 встреча с руководителем", "sort_order": 40, "default_text": "В 12:00 запланирована встреча с вашим руководителем. Уточните, пожалуйста, формат (онлайн/офис) и подготовьте вопросы.", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "12:00", "day_offset_workdays": 0, "target_field": None},
            {"step_key": "lunch_13", "step_title": "13:00 обед", "sort_order": 50, "default_text": "Время обеда! Вы можете познакомиться с коллегами и задать им вопросы о процессе работы.", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "13:00", "day_offset_workdays": 0, "target_field": None},
            {"step_key": "accesses_14", "step_title": "14:00 доступы", "sort_order": 60, "default_text": "Мы подготовили для вас доступы ко всем необходимым системам. Список доступов и инструкции отправлены вам на почту.", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "14:00", "day_offset_workdays": 0, "target_field": None},
            {"step_key": "structure_doc_15", "step_title": "15:00 структура компании", "sort_order": 70, "default_text": "Отправляю документ со структурой компании: https://example.com/docs/company-structure. Ознакомьтесь, чтобы лучше понимать, как все устроено.", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "15:00", "day_offset_workdays": 0, "target_field": None},
            {"step_key": "processes_16", "step_title": "16:00 бизнес-процессы", "sort_order": 80, "default_text": "Вот ссылка на ключевые бизнес-процессы компании: https://example.com/docs/business-processes. Рекомендуем сохранить ее в закладки.", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "16:00", "day_offset_workdays": 0, "target_field": None},
            {"step_key": "day_analysis_17", "step_title": "17:00 анализ дня", "sort_order": 90, "default_text": "Предлагаю подвести итоги первого дня. Подумайте, что понравилось, какие вопросы остались, и зафиксируйте их.", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "17:00", "day_offset_workdays": 0, "target_field": None},
            {"step_key": "feedback_form_18", "step_title": "18:00 анкета и чек-лист", "sort_order": 100, "default_text": "Спасибо за первый день! Пожалуйста, заполните короткую анкету о том, как он прошел: https://example.com/forms/first-day-feedback. Также здесь чек-лист, чтобы убедиться, что все запланированное выполнено.", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "18:00", "day_offset_workdays": 0, "target_field": None},
        ],
    },
    {
        "scenario_key": "first_week",
        "title": "Конец первой недели",
        "role_scope": ROLE_SCOPE_ALL,
        "trigger_mode": "first_week_friday",
        "description": "Сценарий адаптации к концу первой рабочей недели.",
        "steps": [
            {"step_key": "first_week_info", "step_title": "Информирование о встрече", "sort_order": 10, "default_text": "Привет, {name}! Скоро мы познакомим тебя с задачами на ИС. Наша встреча запланирована на {date} в {time}.", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "10:00", "day_offset_workdays": -1, "target_field": None},
            {"step_key": "first_week_test", "step_title": "Тест", "sort_order": 20, "default_text": "Пройди по ссылке и выполни тест в рамках твоей адаптации: {test_url}", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "12:00", "day_offset_workdays": -1, "target_field": None},
            {"step_key": "first_week_meeting", "step_title": "День встречи", "sort_order": 30, "default_text": "Привет, {name}! Мы подготовили для тебя задачи на испытательный срок. Можешь заранее ознакомиться с ними и задать вопросы на встрече в {time}. {tasks_url}", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "10:00", "day_offset_workdays": 0, "target_field": None},
        ],
    },
    {
        "scenario_key": "mid_probation",
        "title": "Середина испытательного срока",
        "role_scope": ROLE_SCOPE_ALL,
        "trigger_mode": "mid_probation",
        "description": "Сценарий середины испытательного срока.",
        "steps": [
            {"step_key": "mid_info", "step_title": "Информирование о встрече", "sort_order": 10, "default_text": "Привет, {name}! Следующая встреча в рамках твоей адаптации запланирована на {date} в {time}.", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "10:00", "day_offset_workdays": -1, "target_field": None},
            {"step_key": "mid_test", "step_title": "Тест", "sort_order": 20, "default_text": "Пройди по ссылке и выполни тест в рамках твоей адаптации: {test_url}", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "12:00", "day_offset_workdays": -1, "target_field": None},
            {"step_key": "mid_practice", "step_title": "Практическое задание", "sort_order": 30, "default_text": "Пройди по ссылке и выполни практическое задание: {practice_url}", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "14:00", "day_offset_workdays": -1, "target_field": None},
            {"step_key": "mid_meeting", "step_title": "День встречи", "sort_order": 40, "default_text": "Привет, {name}! Сегодня в {time} мы обсудим промежуточные результаты выполнения задач на ИС и твое впечатление от работы. Проверь задачи на ИС, отметь, если не получилось реализовать какие-нибудь из них. {tasks_url}", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "10:00", "day_offset_workdays": 0, "target_field": None},
        ],
    },
    {
        "scenario_key": "end_probation",
        "title": "Завершение испытательного срока",
        "role_scope": ROLE_SCOPE_ALL,
        "trigger_mode": "end_probation",
        "description": "Сценарий завершения испытательного срока.",
        "steps": [
            {"step_key": "end_info", "step_title": "Информирование о встрече", "sort_order": 10, "default_text": "Привет, {name}! Вот и подходит к концу твой ИС. Скоро обсудим результаты. Проверь задачи на ИС, отметь прогресс. Встреча запланирована на {date} в {time}. {tasks_url}", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "10:00", "day_offset_workdays": -1, "target_field": None},
            {"step_key": "end_test", "step_title": "Тест", "sort_order": 20, "default_text": "Пройди по ссылке и выполни тест в рамках твоей адаптации: {test_url}", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "12:00", "day_offset_workdays": -1, "target_field": None},
            {"step_key": "end_practice", "step_title": "Практическое задание", "sort_order": 30, "default_text": "Пройди по ссылке и выполни практическое задание: {practice_url}", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "14:00", "day_offset_workdays": -1, "target_field": None},
            {"step_key": "end_meeting", "step_title": "День встречи", "sort_order": 40, "default_text": "Привет, {name}! Сегодня в {time} мы обсудим итоги выполнения задач на ИС и твое впечатление от работы. Проверь задачи на ИС, отметь прогресс. {tasks_url}", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "10:00", "day_offset_workdays": 0, "target_field": None},
        ],
    },
    {
        "scenario_key": "mid_feedback",
        "title": "ОС от коллег (середина ИС)",
        "role_scope": ROLE_SCOPE_ALL,
        "trigger_mode": "manual_only",
        "description": "Ручная отправка обратной связи от коллег на середине ИС.",
        "steps": [
            {"step_key": "mid_feedback", "step_title": "ОС от коллег", "sort_order": 10, "default_text": "Собрали обратную связь от коллег, с которыми тебе удалось поработать. Предлагаем тебе ознакомиться. {feedback_url}", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "16:00", "day_offset_workdays": 0, "target_field": None},
        ],
    },
    {
        "scenario_key": "end_feedback",
        "title": "ОС от коллег (конец ИС)",
        "role_scope": ROLE_SCOPE_ALL,
        "trigger_mode": "manual_only",
        "description": "Ручная отправка обратной связи от коллег в конце ИС.",
        "steps": [
            {"step_key": "end_feedback", "step_title": "ОС от коллег", "sort_order": 10, "default_text": "Собрали обратную связь от коллег, с которыми тебе удалось поработать. Предлагаем тебе ознакомиться. {feedback_url}", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "16:00", "day_offset_workdays": 0, "target_field": None},
        ],
    },
    {
        "scenario_key": "end_summary",
        "title": "Итог испытательного срока",
        "role_scope": ROLE_SCOPE_ALL,
        "trigger_mode": "manual_only",
        "description": "Ручное итоговое сообщение по завершению ИС.",
        "steps": [
            {"step_key": "end_summary", "step_title": "Подведение итога", "sort_order": 10, "default_text": "Поздравляем с успешным завершением ИС! Теперь ты полноценный член команды! Пришли видео-визитку с рассказом о себе и мы добавим тебя во внутренний чат.", "response_type": "none", "button_options": None, "send_mode": "specific_time", "send_time": "18:00", "day_offset_workdays": 0, "target_field": None},
        ],
    },
]


def seed_flow_templates() -> None:
    with SessionLocal() as db:
        existing_scenarios = {row.scenario_key: row for row in db.query(ScenarioTemplate).all()}
        existing_steps = {row.step_key: row for row in db.query(FlowStepTemplate).all()}
        changed = False

        for scenario in SCENARIO_DEFINITIONS:
            scenario_key = str(scenario["scenario_key"])
            scenario_row = existing_scenarios.get(scenario_key)
            if not scenario_row:
                scenario_row = ScenarioTemplate(
                    scenario_key=scenario_key,
                    title=str(scenario["title"]),
                    role_scope=str(scenario["role_scope"]),
                    trigger_mode=str(scenario["trigger_mode"]),
                    description=str(scenario.get("description") or ""),
                )
                db.add(scenario_row)
                existing_scenarios[scenario_key] = scenario_row
                changed = True

            for step in scenario["steps"]:
                step_key = str(step["step_key"])
                step_row = existing_steps.get(step_key)
                if not step_row:
                    step_row = FlowStepTemplate(
                        flow_key=scenario_key,
                        step_key=step_key,
                        step_title=str(step["step_title"]),
                        sort_order=int(step["sort_order"]),
                        default_text=str(step["default_text"]),
                        custom_text=None,
                        response_type=str(step["response_type"]),
                        button_options=step["button_options"],
                        send_mode=str(step["send_mode"]),
                        send_time=step["send_time"],
                        day_offset_workdays=int(step.get("day_offset_workdays") or 0),
                        target_field=step.get("target_field"),
                    )
                    db.add(step_row)
                    existing_steps[step_key] = step_row
                    changed = True

        if changed:
            db.commit()


def get_step_text(step_key: str, fallback: str) -> str:
    with SessionLocal() as db:
        row = (
            db.query(FlowStepTemplate.custom_text, FlowStepTemplate.default_text)
            .filter(FlowStepTemplate.step_key == step_key)
            .first()
        )
    if not row:
        return fallback
    custom_text, default_text = row
    if custom_text and custom_text.strip():
        return custom_text
    return default_text or fallback


def get_step_config(step_key: str) -> Optional[FlowStepTemplate]:
    with SessionLocal() as db:
        return db.query(FlowStepTemplate).filter(FlowStepTemplate.step_key == step_key).first()


def get_step_buttons(step: FlowStepTemplate) -> list[str]:
    if step.response_type not in {"buttons", "branching"} or not step.button_options:
        return []
    return [item.strip() for item in step.button_options.splitlines() if item.strip()]


def get_button_options(step_key: str, fallback: list[str]) -> list[str]:
    step = get_step_config(step_key)
    buttons = get_step_buttons(step) if step else []
    return buttons or fallback


def get_scenario_config(scenario_key: str) -> Optional[ScenarioTemplate]:
    with SessionLocal() as db:
        return db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == scenario_key).first()
