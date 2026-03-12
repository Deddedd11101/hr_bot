from __future__ import annotations

from datetime import datetime, time, timedelta, date
from typing import Iterable, Sequence

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone as tz_get
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal
from .flow_templates import get_step_text
from .models import Employee, FlowLaunchRequest, OnboardingEvent
from .notifications import notify_hr_stage
from .recruitment_flow import (
    ASK_FULL_NAME_MESSAGE,
    CONSENT_MESSAGE,
    RECRUITMENT_FLOW_KEY,
    STATUS_WAIT_CONSENT,
    STATUS_WAIT_FULL_NAME,
    recruitment_consent_keyboard,
)


FIRST_DAY_EVENTS = [
    # (key, hour, minute, message)
    (
        "day_start_10",
        10,
        0,
        "Доброе утро! Сегодня ваш первый рабочий день. В 10:30 вас ждёт встреча с HR. "
        "Если возникнут вопросы — смело задавайте их в этом чате.",
    ),
    (
        "fill_form_11",
        11,
        0,
        "Пора заполнить анкету нового сотрудника. "
        "Пожалуйста, перейдите по ссылке и заполните форму: https://example.com/forms/new-employee",
    ),
    (
        "documents_11_30",
        11,
        30,
        "Я отправил вам пакет документов для ознакомления и подписи. "
        "Проверьте, пожалуйста, вашу корпоративную почту или систему ЭДО.",
    ),
    (
        "manager_meeting_12",
        12,
        0,
        "В 12:00 запланирована встреча с вашим руководителем. "
        "Уточните, пожалуйста, формат (онлайн/офис) и подготовьте вопросы.",
    ),
    (
        "lunch_13",
        13,
        0,
        "Время обеда! Вы можете познакомиться с коллегами и задать им вопросы о процессе работы.",
    ),
    (
        "accesses_14",
        14,
        0,
        "Мы подготовили для вас доступы ко всем необходимым системам. "
        "Список доступов и инструкции отправлены вам на почту.",
    ),
    (
        "structure_doc_15",
        15,
        0,
        "Отправляю документ со структурой компании: https://example.com/docs/company-structure. "
        "Ознакомьтесь, чтобы лучше понимать, как всё устроено.",
    ),
    (
        "processes_16",
        16,
        0,
        "Вот ссылка на ключевые бизнес‑процессы компании: https://example.com/docs/business-processes. "
        "Рекомендуем сохранить её в закладки.",
    ),
    (
        "day_analysis_17",
        17,
        0,
        "Предлагаю подвести итоги первого дня. "
        "Подумайте, что понравилось, какие вопросы остались, и зафиксируйте их.",
    ),
    (
        "feedback_form_18",
        18,
        0,
        "Спасибо за первый день! Пожалуйста, заполните короткую анкету о том, как он прошёл: "
        "https://example.com/forms/first-day-feedback. "
        "Также здесь чек‑лист, чтобы убедиться, что всё запланированное выполнено.",
    ),
]

FIRST_DAY_FLOW_EVENTS = [
    (key, 0, hour, minute, message) for key, hour, minute, message in FIRST_DAY_EVENTS
]


def _get_tz():
    return tz_get(settings.TIMEZONE)


def _combine_date_time(d: date, h: int, m: int) -> datetime:
    tz = _get_tz()
    naive = datetime.combine(d, time(hour=h, minute=m))
    return tz.localize(naive)


def plan_first_day_datetimes(first_day: date) -> Iterable[tuple[str, datetime, str]]:
    """
    Возвращает список (key, datetime, message) для флоу первого дня.

    В обычном режиме:
        — жёстко привязывается к часам 10:00, 11:00, ... текущей таймзоны.

    В DEMO_MODE:
        — все события запускаются относительно текущего момента
          через N минут друг за другом (N = DEMO_STEP_MINUTES).
    """
    tz = _get_tz()

    if settings.DEMO_MODE:
        now = datetime.now(tz)
        step = timedelta(minutes=settings.DEMO_STEP_MINUTES)
        current_time = now + step  # первое событие — через один шаг от «сейчас»
        for key, _hour, _minute, message in FIRST_DAY_EVENTS:
            yield key, current_time, message
            current_time = current_time + step
        return

    # Обычный режим по часам
    for key, hour, minute, message in FIRST_DAY_EVENTS:
        yield key, _combine_date_time(first_day, hour, minute), message


FIRST_WEEK_EVENTS = [
    (
        "first_week_info",
        -1,
        10,
        0,
        "Привет, {name}! Скоро мы познакомим тебя с задачами на ИС. "
        "Наша встреча запланирована на {date} в {time}.",
    ),
    (
        "first_week_test",
        -1,
        12,
        0,
        "Пройди по ссылке и выполни тест в рамках твоей адаптации: {test_url}",
    ),
    (
        "first_week_meeting",
        0,
        10,
        0,
        "Привет, {name}! Мы подготовили для тебя задачи на испытательный срок. "
        "Можешь заранее ознакомиться с ними и задать вопросы на встрече в {time}. "
        "{tasks_url}",
    ),
]

MID_PROBATION_EVENTS = [
    (
        "mid_info",
        -1,
        10,
        0,
        "Привет, {name}! Следующая встреча в рамках твоей адаптации запланирована на {date} в {time}.",
    ),
    (
        "mid_test",
        -1,
        12,
        0,
        "Пройди по ссылке и выполни тест в рамках твоей адаптации: {test_url}",
    ),
    (
        "mid_practice",
        -1,
        14,
        0,
        "Пройди по ссылке и выполни практическое задание: {practice_url}",
    ),
    (
        "mid_meeting",
        0,
        10,
        0,
        "Привет, {name}! Сегодня в {time} мы обсудим промежуточные результаты выполнения задач на ИС "
        "и твоё впечатление от работы. Проверь задачи на ИС, отметь, если не получилось реализовать "
        "какие-нибудь из них. {tasks_url}",
    ),
]

END_PROBATION_EVENTS = [
    (
        "end_info",
        -1,
        10,
        0,
        "Привет, {name}! Вот и подходит к концу твой ИС. Скоро обсудим результаты. "
        "Проверь задачи на ИС, отметь прогресс. Встреча запланирована на {date} в {time}. "
        "{tasks_url}",
    ),
    (
        "end_test",
        -1,
        12,
        0,
        "Пройди по ссылке и выполни тест в рамках твоей адаптации: {test_url}",
    ),
    (
        "end_practice",
        -1,
        14,
        0,
        "Пройди по ссылке и выполни практическое задание: {practice_url}",
    ),
    (
        "end_meeting",
        0,
        10,
        0,
        "Привет, {name}! Сегодня в {time} мы обсудим итоги выполнения задач на ИС и твоё впечатление "
        "от работы. Проверь задачи на ИС, отметь прогресс. {tasks_url}",
    ),
]

MANUAL_ONLY_EVENTS = {
    "mid_feedback": [
        (
            "mid_feedback",
            0,
            16,
            0,
            "Собрали обратную связь от коллег, с которыми тебе удалось поработать. "
            "Предлагаем тебе ознакомиться. {feedback_url}",
        ),
    ],
    "end_feedback": [
        (
            "end_feedback",
            0,
            16,
            0,
            "Собрали обратную связь от коллег, с которыми тебе удалось поработать. "
            "Предлагаем тебе ознакомиться. {feedback_url}",
        ),
    ],
    "end_summary": [
        (
            "end_summary",
            0,
            18,
            0,
            "Поздравляем с успешным завершением ИС! Теперь ты полноценный член команды! "
            "Пришли видео-визитку с рассказом о себе и мы добавим тебя во внутренний чат.",
        ),
    ],
}

FLOW_DEFINITIONS = {
    "first_day": FIRST_DAY_FLOW_EVENTS,
    "first_week": FIRST_WEEK_EVENTS,
    "mid_probation": MID_PROBATION_EVENTS,
    "end_probation": END_PROBATION_EVENTS,
    RECRUITMENT_FLOW_KEY: [("recruitment_consent_request", 0, 10, 0, CONSENT_MESSAGE)],
}


def _is_workday(d: date) -> bool:
    return d.weekday() < 5


def _add_workdays(start: date, days: int) -> date:
    if days == 0:
        return start
    current = start
    step = 1 if days > 0 else -1
    remaining = abs(days)
    while remaining > 0:
        current = current + timedelta(days=step)
        if _is_workday(current):
            remaining -= 1
    return current


def _next_friday(d: date) -> date:
    # Friday is weekday 4
    days_ahead = (4 - d.weekday()) % 7
    return d + timedelta(days=days_ahead)


def _short_name(full_name: str) -> str:
    parts = (full_name or "").strip().split()
    return parts[0] if parts else "коллега"


def _format_message(template: str, employee: Employee, meeting_date: date, meeting_time: time) -> str:
    return template.format(
        name=_short_name(employee.full_name),
        date=meeting_date.strftime("%d.%m.%Y"),
        time=meeting_time.strftime("%H:%M"),
        test_url=settings.TEST_URL,
        practice_url=settings.PRACTICE_URL,
        tasks_url=settings.TASKS_URL,
        feedback_url=settings.FEEDBACK_URL,
    )


def _plan_flow_events(
    flow_events: Sequence[tuple[str, int, int, int, str]],
    employee: Employee,
    meeting_date: date,
    manual: bool,
) -> Iterable[tuple[str, datetime, str]]:
    tz = _get_tz()
    if settings.DEMO_MODE:
        now = datetime.now(tz)
        step = timedelta(minutes=settings.DEMO_STEP_MINUTES)
        current_time = now + step
        for key, _day_offset, _hour, _minute, template in flow_events:
            message_tpl = get_step_text(key, template)
            message = _format_message(message_tpl, employee, meeting_date, time(hour=10, minute=0))
            yield key, current_time, message
            current_time = current_time + step
        return

    if manual:
        now = datetime.now(tz)
        step = timedelta(minutes=settings.MANUAL_STEP_MINUTES)
        current_time = now + step
        for key, _day_offset, _hour, _minute, template in flow_events:
            message_tpl = get_step_text(key, template)
            message = _format_message(message_tpl, employee, meeting_date, time(hour=10, minute=0))
            yield key, current_time, message
            current_time = current_time + step
        return

    for key, day_offset, hour, minute, template in flow_events:
        event_date = _add_workdays(meeting_date, day_offset)
        when = _combine_date_time(event_date, hour, minute)
        message_tpl = get_step_text(key, template)
        message = _format_message(message_tpl, employee, meeting_date, time(hour=hour, minute=minute))
        yield key, when, message


async def send_onboarding_message(
    bot,
    employee_id: int,
    event_key: str,
    when: datetime,
    message: str,
) -> None:
    """
    Отправляет сообщение сотруднику и пишет лог в БД.

    В задачу передаём только employee_id, а актуальный telegram_user_id читаем
    из БД на момент отправки, чтобы:
    - не получать DetachedInstanceError;
    - корректно отрабатывать, если Telegram ID изменился после планирования
      (например, после нажатия /start).
    """
    with SessionLocal() as db:
        employee = db.get(Employee, employee_id)
        if not employee or not employee.telegram_user_id:
            # Сотрудник удалён или ещё не привязан к Telegram — просто пропускаем
            return

        telegram_user_id = employee.telegram_user_id

        # Отправка в Telegram
        if event_key == "recruitment_consent_request":
            await bot.send_message(
                chat_id=telegram_user_id,
                text=message,
                reply_markup=recruitment_consent_keyboard(),
            )
            employee.candidate_status = STATUS_WAIT_CONSENT
        elif event_key == "recruitment_ask_full_name":
            await bot.send_message(chat_id=telegram_user_id, text=message)
            employee.candidate_status = STATUS_WAIT_FULL_NAME
        else:
            await bot.send_message(chat_id=telegram_user_id, text=message)

        # Лог в БД
        db_event = OnboardingEvent(
            employee_id=employee_id,
            scheduled_at=when,
            sent_at=datetime.utcnow(),
            event_key=event_key,
            message=message,
        )
        db.add(db_event)
        db.commit()
        try:
            await notify_hr_stage(bot, employee, event_key)
        except Exception:
            # HR-оповещения не должны ломать основной флоу сотрудника.
            pass


def _load_all_employees(db: Session) -> list[Employee]:
    return list(db.query(Employee).all())


def _load_pending_flow_requests(db: Session) -> list[FlowLaunchRequest]:
    return list(db.query(FlowLaunchRequest).filter(FlowLaunchRequest.processed_at.is_(None)).all())


def _load_sent_event_keys(db: Session, employee_id: int) -> set[str]:
    events = db.query(OnboardingEvent.event_key).filter(OnboardingEvent.employee_id == employee_id).all()
    return {row[0] for row in events}


def schedule_employee_first_day(
    scheduler: AsyncIOScheduler,
    bot,
    employee: Employee,
    sent_keys: set[str],
) -> None:
    """Планирует все события первого дня для конкретного сотрудника."""
    if not employee.first_workday:
        return
    now = datetime.now(_get_tz())
    for key, when, message in plan_first_day_datetimes(employee.first_workday):
        if key in sent_keys:
            continue
        # Если время уже прошло — пропускаем для простоты демо
        if when < now - timedelta(minutes=1):
            continue
        job_id = f"employee-{employee.id}-{key}"
        if scheduler.get_job(job_id):
            continue

        scheduler.add_job(
            send_onboarding_message,
            "date",
            run_date=when,
            args=[bot, employee.id, key, when, message],
            id=job_id,
            replace_existing=False,
        )


def schedule_employee_flow(
    scheduler: AsyncIOScheduler,
    bot,
    employee: Employee,
    flow_key: str,
    sent_keys: set[str],
    manual: bool,
) -> None:
    if manual:
        sent_keys = set()
    if flow_key in FLOW_DEFINITIONS:
        if flow_key == "first_day":
            if not employee.first_workday:
                return
            meeting_date = employee.first_workday
        elif flow_key == RECRUITMENT_FLOW_KEY:
            meeting_date = datetime.now(_get_tz()).date()
        elif flow_key == "first_week":
            if not employee.first_workday:
                return
            meeting_date = _next_friday(employee.first_workday)
        elif flow_key == "mid_probation":
            if not employee.first_workday:
                return
            meeting_date = _add_workdays(employee.first_workday, settings.PROBATION_WORKDAYS // 2)
        elif flow_key == "end_probation":
            if not employee.first_workday:
                return
            meeting_date = _add_workdays(employee.first_workday, settings.PROBATION_WORKDAYS)
        else:
            return

        flow_events = FLOW_DEFINITIONS[flow_key]
    elif flow_key in MANUAL_ONLY_EVENTS:
        meeting_date = employee.first_workday
        flow_events = MANUAL_ONLY_EVENTS[flow_key]
    else:
        return

    if manual and flow_key in FLOW_DEFINITIONS:
        meeting_date = datetime.now(_get_tz()).date()
        if flow_key == RECRUITMENT_FLOW_KEY:
            employee.personal_data_consent = False
            employee.candidate_status = STATUS_WAIT_CONSENT

    now = datetime.now(_get_tz())
    for key, when, message in _plan_flow_events(flow_events, employee, meeting_date, manual=manual):
        if key in sent_keys:
            continue
        if when < now - timedelta(minutes=1):
            continue
        job_id = f"employee-{employee.id}-{key}"
        if not manual and scheduler.get_job(job_id):
            continue
        scheduler.add_job(
            send_onboarding_message,
            "date",
            run_date=when,
            args=[bot, employee.id, key, when, message],
            id=job_id,
            replace_existing=manual,
        )


def schedule_all_employees(scheduler: AsyncIOScheduler, bot) -> None:
    """Планирует флоу для всех сотрудников и обрабатывает ручные запросы."""
    with SessionLocal() as db:
        employees = _load_all_employees(db)
        for emp in employees:
            sent_keys = _load_sent_event_keys(db, emp.id)
            schedule_employee_first_day(scheduler, bot, emp, sent_keys)
            schedule_employee_flow(scheduler, bot, emp, "first_week", sent_keys, manual=False)
            schedule_employee_flow(scheduler, bot, emp, "mid_probation", sent_keys, manual=False)
            schedule_employee_flow(scheduler, bot, emp, "end_probation", sent_keys, manual=False)
            if not emp.is_flow_scheduled:
                emp.is_flow_scheduled = True

        # Обработка ручных запросов
        pending_requests = _load_pending_flow_requests(db)
        for req in pending_requests:
            employee = db.get(Employee, req.employee_id)
            if not employee:
                req.processed_at = datetime.utcnow()
                continue
            if not employee.telegram_user_id:
                # Ждём привязку Telegram и не закрываем запрос.
                continue
            sent_keys = _load_sent_event_keys(db, employee.id)
            schedule_employee_flow(
                scheduler,
                bot,
                employee,
                req.flow_key,
                sent_keys,
                manual=True,
            )
            req.processed_at = datetime.utcnow()

        if employees or pending_requests:
            db.commit()
