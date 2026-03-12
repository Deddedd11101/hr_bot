from __future__ import annotations

from .database import SessionLocal
from .models import FlowStepTemplate


FLOW_STEPS: list[dict[str, object]] = [
    # Recruitment flow
    {
        "flow_key": "recruitment_hiring",
        "step_key": "recruitment_consent_request",
        "step_title": "Согласие на ПДн",
        "sort_order": 10,
        "default_text": (
            "Привет! Я HR‑бот. Я создал черновик вашей карточки в админке и привязал этот Telegram. "
            "HR может отредактировать данные и при необходимости привязать вас к существующей карточке.\n\n"
            "Чтобы начать наше сотрудничество, нам нужно твоё согласие на обработку персональных данных.\n"
            "Мы используем их исключительно в рамках процесса подбора"
        ),
    },
    {
        "flow_key": "recruitment_hiring",
        "step_key": "recruitment_ask_full_name",
        "step_title": "Запрос полного ФИО",
        "sort_order": 20,
        "default_text": "Отлично! Подскажи, пожалуйста, свое полное ФИО.",
    },
    {
        "flow_key": "recruitment_hiring",
        "step_key": "recruitment_ask_position",
        "step_title": "Запрос желаемой должности",
        "sort_order": 30,
        "default_text": "На какую должность ты рассматриваешься?",
    },
    {
        "flow_key": "recruitment_hiring",
        "step_key": "recruitment_ask_resume",
        "step_title": "Запрос резюме",
        "sort_order": 40,
        "default_text": "Пришли, пожалуйста, своё резюме файлом (PDF / DOC / DOCX).",
    },
    {
        "flow_key": "recruitment_hiring",
        "step_key": "recruitment_ask_salary",
        "step_title": "Запрос ожиданий по зарплате",
        "sort_order": 50,
        "default_text": "Какой уровень дохода для тебя комфортен? Можешь указать диапазон.",
    },
    {
        "flow_key": "recruitment_hiring",
        "step_key": "recruitment_primary_done",
        "step_title": "Завершение первичного сбора",
        "sort_order": 60,
        "default_text": (
            "Спасибо! Мы получили первичные данные.\n"
            "Дальше HR проверит информацию и вернётся к тебе со следующим шагом."
        ),
    },
    # First day
    {
        "flow_key": "first_day",
        "step_key": "day_start_10",
        "step_title": "10:00 старт дня",
        "sort_order": 10,
        "default_text": (
            "Доброе утро! Сегодня ваш первый рабочий день. В 10:30 вас ждёт встреча с HR. "
            "Если возникнут вопросы — смело задавайте их в этом чате."
        ),
    },
    {
        "flow_key": "first_day",
        "step_key": "fill_form_11",
        "step_title": "11:00 анкета",
        "sort_order": 20,
        "default_text": (
            "Пора заполнить анкету нового сотрудника. "
            "Пожалуйста, перейдите по ссылке и заполните форму: https://example.com/forms/new-employee"
        ),
    },
    {
        "flow_key": "first_day",
        "step_key": "documents_11_30",
        "step_title": "11:30 документы",
        "sort_order": 30,
        "default_text": (
            "Я отправил вам пакет документов для ознакомления и подписи. "
            "Проверьте, пожалуйста, вашу корпоративную почту или систему ЭДО."
        ),
    },
    {
        "flow_key": "first_day",
        "step_key": "manager_meeting_12",
        "step_title": "12:00 встреча с руководителем",
        "sort_order": 40,
        "default_text": (
            "В 12:00 запланирована встреча с вашим руководителем. "
            "Уточните, пожалуйста, формат (онлайн/офис) и подготовьте вопросы."
        ),
    },
    {
        "flow_key": "first_day",
        "step_key": "lunch_13",
        "step_title": "13:00 обед",
        "sort_order": 50,
        "default_text": "Время обеда! Вы можете познакомиться с коллегами и задать им вопросы о процессе работы.",
    },
    {
        "flow_key": "first_day",
        "step_key": "accesses_14",
        "step_title": "14:00 доступы",
        "sort_order": 60,
        "default_text": (
            "Мы подготовили для вас доступы ко всем необходимым системам. "
            "Список доступов и инструкции отправлены вам на почту."
        ),
    },
    {
        "flow_key": "first_day",
        "step_key": "structure_doc_15",
        "step_title": "15:00 структура компании",
        "sort_order": 70,
        "default_text": (
            "Отправляю документ со структурой компании: https://example.com/docs/company-structure. "
            "Ознакомьтесь, чтобы лучше понимать, как всё устроено."
        ),
    },
    {
        "flow_key": "first_day",
        "step_key": "processes_16",
        "step_title": "16:00 бизнес-процессы",
        "sort_order": 80,
        "default_text": (
            "Вот ссылка на ключевые бизнес‑процессы компании: https://example.com/docs/business-processes. "
            "Рекомендуем сохранить её в закладки."
        ),
    },
    {
        "flow_key": "first_day",
        "step_key": "day_analysis_17",
        "step_title": "17:00 анализ дня",
        "sort_order": 90,
        "default_text": (
            "Предлагаю подвести итоги первого дня. "
            "Подумайте, что понравилось, какие вопросы остались, и зафиксируйте их."
        ),
    },
    {
        "flow_key": "first_day",
        "step_key": "feedback_form_18",
        "step_title": "18:00 анкета и чек-лист",
        "sort_order": 100,
        "default_text": (
            "Спасибо за первый день! Пожалуйста, заполните короткую анкету о том, как он прошёл: "
            "https://example.com/forms/first-day-feedback. "
            "Также здесь чек‑лист, чтобы убедиться, что всё запланированное выполнено."
        ),
    },
    # Other flows
    {"flow_key": "first_week", "step_key": "first_week_info", "step_title": "Информирование о встрече", "sort_order": 10, "default_text": "Привет, {name}! Скоро мы познакомим тебя с задачами на ИС. Наша встреча запланирована на {date} в {time}."},
    {"flow_key": "first_week", "step_key": "first_week_test", "step_title": "Тест", "sort_order": 20, "default_text": "Пройди по ссылке и выполни тест в рамках твоей адаптации: {test_url}"},
    {"flow_key": "first_week", "step_key": "first_week_meeting", "step_title": "День встречи", "sort_order": 30, "default_text": "Привет, {name}! Мы подготовили для тебя задачи на испытательный срок. Можешь заранее ознакомиться с ними и задать вопросы на встрече в {time}. {tasks_url}"},
    {"flow_key": "mid_probation", "step_key": "mid_info", "step_title": "Информирование о встрече", "sort_order": 10, "default_text": "Привет, {name}! Следующая встреча в рамках твоей адаптации запланирована на {date} в {time}."},
    {"flow_key": "mid_probation", "step_key": "mid_test", "step_title": "Тест", "sort_order": 20, "default_text": "Пройди по ссылке и выполни тест в рамках твоей адаптации: {test_url}"},
    {"flow_key": "mid_probation", "step_key": "mid_practice", "step_title": "Практическое задание", "sort_order": 30, "default_text": "Пройди по ссылке и выполни практическое задание: {practice_url}"},
    {"flow_key": "mid_probation", "step_key": "mid_meeting", "step_title": "День встречи", "sort_order": 40, "default_text": "Привет, {name}! Сегодня в {time} мы обсудим промежуточные результаты выполнения задач на ИС и твоё впечатление от работы. Проверь задачи на ИС, отметь, если не получилось реализовать какие-нибудь из них. {tasks_url}"},
    {"flow_key": "end_probation", "step_key": "end_info", "step_title": "Информирование о встрече", "sort_order": 10, "default_text": "Привет, {name}! Вот и подходит к концу твой ИС. Скоро обсудим результаты. Проверь задачи на ИС, отметь прогресс. Встреча запланирована на {date} в {time}. {tasks_url}"},
    {"flow_key": "end_probation", "step_key": "end_test", "step_title": "Тест", "sort_order": 20, "default_text": "Пройди по ссылке и выполни тест в рамках твоей адаптации: {test_url}"},
    {"flow_key": "end_probation", "step_key": "end_practice", "step_title": "Практическое задание", "sort_order": 30, "default_text": "Пройди по ссылке и выполни практическое задание: {practice_url}"},
    {"flow_key": "end_probation", "step_key": "end_meeting", "step_title": "День встречи", "sort_order": 40, "default_text": "Привет, {name}! Сегодня в {time} мы обсудим итоги выполнения задач на ИС и твоё впечатление от работы. Проверь задачи на ИС, отметь прогресс. {tasks_url}"},
]


def seed_flow_templates() -> None:
    with SessionLocal() as db:
        existing = {row.step_key: row for row in db.query(FlowStepTemplate).all()}
        changed = False
        for item in FLOW_STEPS:
            step_key = item["step_key"]  # type: ignore[assignment]
            row = existing.get(step_key)  # type: ignore[arg-type]
            if not row:
                db.add(
                    FlowStepTemplate(
                        flow_key=item["flow_key"],  # type: ignore[arg-type]
                        step_key=step_key,  # type: ignore[arg-type]
                        step_title=item["step_title"],  # type: ignore[arg-type]
                        sort_order=item["sort_order"],  # type: ignore[arg-type]
                        default_text=item["default_text"],  # type: ignore[arg-type]
                        custom_text=None,
                    )
                )
                changed = True
                continue

            # Update metadata/defaults without overwriting custom_text.
            if row.flow_key != item["flow_key"]:
                row.flow_key = item["flow_key"]  # type: ignore[assignment]
                changed = True
            if row.step_title != item["step_title"]:
                row.step_title = item["step_title"]  # type: ignore[assignment]
                changed = True
            if row.sort_order != item["sort_order"]:
                row.sort_order = item["sort_order"]  # type: ignore[assignment]
                changed = True
            if row.default_text != item["default_text"]:
                row.default_text = item["default_text"]  # type: ignore[assignment]
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
