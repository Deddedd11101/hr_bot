"""Демонстрационные опросы для разбора интерфейса.

Пустая база показывает вёрстку пустоты, а не рабочий экран: на пустом
каталоге опросов не видно ни сетки карточек, ни поведения фильтров, ни того,
что вообще происходит в разделе. Скрипт наполняет базу набором опросов,
на котором экран можно разбирать.

Данные подобраны не «поровну и покрасивее», а так, чтобы ломать вёрстку:
есть опрос с именем в 68 символов, есть вовсе без описания, есть из одного
шага и из четырёх, есть на сотрудников, на кандидатов и на всех сразу.
Именно на таких значениях вылезают обрезки, переносы и пустые места.

Скрипт идемпотентен: опрос с уже существующим scenario_key пропускается,
ничего не удаляется и не перезаписывается.

Запуск:  .venv/Scripts/python.exe tools/seed_demo_surveys.py
Откат:   .venv/Scripts/python.exe tools/seed_demo_surveys.py --remove
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.database import SessionLocal
from app.models import FlowStepTemplate, ScenarioTemplate

ПРЕФИКС = "demo_survey_"

ОПРОСЫ: list[dict] = [
    {
        "scenario_key": ПРЕФИКС + "onboarding_week1",
        "title": "Как прошла первая неделя",
        "description": "Короткий пульс новичка в конце первой рабочей недели.",
        "employee_scope": "employees",
        "trigger_mode": "first_week_friday",
        "role_scope": "all",
        "steps": [
            {
                "step_key": "week1_mood",
                "step_title": "Общее ощущение",
                "default_text": "Привет, {name}! Первая неделя позади. Как ощущения?",
                "response_type": "buttons",
                "button_options": "Отлично\nНормально\nБыло тяжело",
                "send_mode": "specific_time",
                "send_time": "16:00",
            },
            {
                "step_key": "week1_blockers",
                "step_title": "Что мешало",
                "default_text": "Что мешало работать на этой неделе? Ответь одним сообщением, разберём.",
                "response_type": "text",
            },
            {
                "step_key": "week1_contact",
                "step_title": "Хватает ли контакта",
                "default_text": "Хватает ли общения с руководителем и наставником?",
                "response_type": "buttons",
                "button_options": "Да, хватает\nХотелось бы чаще\nПочти не общались",
            },
        ],
    },
    {
        "scenario_key": ПРЕФИКС + "mid_probation",
        "title": "Середина испытательного срока",
        "description": "Сверка ожиданий на середине испытательного срока: задачи, обратная связь, риски.",
        "employee_scope": "employees",
        "trigger_mode": "mid_probation",
        "role_scope": "all",
        "steps": [
            {
                "step_key": "mid_clarity",
                "step_title": "Понятны ли задачи",
                "default_text": "{name}, насколько тебе сейчас понятно, чего от тебя ждут?",
                "response_type": "buttons",
                "button_options": "Полностью понятно\nЕсть вопросы\nСовсем непонятно",
                "send_mode": "specific_time",
                "send_time": "11:00",
            },
            {
                "step_key": "mid_feedback",
                "step_title": "Обратная связь",
                "default_text": "Получаешь ли ты обратную связь по работе?",
                "response_type": "buttons",
                "button_options": "Регулярно\nИногда\nНе получаю",
            },
            {
                "step_key": "mid_workload",
                "step_title": "Нагрузка",
                "default_text": "Как оцениваешь нагрузку?",
                "response_type": "buttons",
                "button_options": "Низкая — могу больше\nВ самый раз\nПеребор",
            },
            {
                "step_key": "mid_comment",
                "step_title": "Свободный комментарий",
                "default_text": "Что хочешь передать HR? Ответ увидит только HR.",
                "response_type": "text",
            },
        ],
    },
    {
        # Без описания: проверяем, как карточка выглядит с пропуском.
        "scenario_key": ПРЕФИКС + "end_probation",
        "title": "Итоги испытательного срока",
        "description": None,
        "employee_scope": "employees",
        "trigger_mode": "end_probation",
        "role_scope": "all",
        "steps": [
            {
                "step_key": "end_result",
                "step_title": "Итог",
                "default_text": "{name}, испытательный срок завершается. Хочешь продолжать работу в компании?",
                "response_type": "buttons",
                "button_options": "Да, остаюсь\nСомневаюсь\nНет",
                "send_mode": "specific_time",
                "send_time": "10:00",
            },
            {
                "step_key": "end_why",
                "step_title": "Почему",
                "default_text": "Коротко: что повлияло на твой ответ?",
                "response_type": "text",
            },
        ],
    },
    {
        # Очень длинное имя: на нём видно обрезку в карточке и в полосе заголовка.
        "scenario_key": ПРЕФИКС + "candidate_after_reject",
        "title": "Обратная связь кандидата после отказа на этапе технического интервью",
        "description": (
            "Отправляется вручную кандидатам, получившим отказ. Помогает понять, "
            "где процесс подбора теряет людей и что в нём читается как неуважение."
        ),
        "employee_scope": "candidates",
        "trigger_mode": "manual_only",
        "role_scope": "all",
        "steps": [
            {
                "step_key": "reject_clarity",
                "step_title": "Понятность процесса",
                "default_text": "Спасибо за участие! Был ли процесс отбора понятным?",
                "response_type": "buttons",
                "button_options": "Да\nЧастично\nНет",
            },
            {
                "step_key": "reject_speed",
                "step_title": "Скорость ответов",
                "default_text": "Устраивала ли скорость наших ответов?",
                "response_type": "buttons",
                "button_options": "Да\nБыло долго",
            },
            {
                "step_key": "reject_comment",
                "step_title": "Что улучшить",
                "default_text": "Что нам стоит улучшить в процессе подбора?",
                "response_type": "text",
            },
        ],
    },
    {
        # Один шаг: самый короткий возможный опрос.
        "scenario_key": ПРЕФИКС + "enps",
        "title": "eNPS",
        "description": "Один вопрос раз в квартал.",
        "employee_scope": "all",
        "trigger_mode": "manual_only",
        "role_scope": "all",
        "steps": [
            {
                "step_key": "enps_score",
                "step_title": "Оценка",
                "default_text": "Насколько вероятно, что порекомендуешь компанию как место работы?",
                "response_type": "buttons",
                "button_options": "0\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10",
            },
        ],
    },
]


def добавить() -> None:
    session = SessionLocal()
    добавлено = 0
    пропущено = 0
    try:
        максимум = session.execute(
            select(ScenarioTemplate.sort_order).order_by(ScenarioTemplate.sort_order.desc())
        ).scalars().first() or 0

        for сдвиг, опрос in enumerate(ОПРОСЫ, start=1):
            уже_есть = session.execute(
                select(ScenarioTemplate).where(ScenarioTemplate.scenario_key == опрос["scenario_key"])
            ).scalar_one_or_none()
            if уже_есть is not None:
                пропущено += 1
                continue

            session.add(
                ScenarioTemplate(
                    scenario_key=опрос["scenario_key"],
                    title=опрос["title"],
                    description=опрос["description"],
                    scenario_kind="survey",
                    role_scope=опрос["role_scope"],
                    employee_scope=опрос["employee_scope"],
                    trigger_mode=опрос["trigger_mode"],
                    sort_order=максимум + сдвиг * 10,
                )
            )

            for номер, шаг in enumerate(опрос["steps"], start=1):
                session.add(
                    FlowStepTemplate(
                        flow_key=опрос["scenario_key"],
                        step_key=шаг["step_key"],
                        step_title=шаг["step_title"],
                        sort_order=номер * 10,
                        default_text=шаг["default_text"],
                        response_type=шаг.get("response_type", "none"),
                        button_options=шаг.get("button_options"),
                        send_mode=шаг.get("send_mode", "immediate"),
                        send_time=шаг.get("send_time"),
                        day_offset_workdays=шаг.get("day_offset_workdays", 0),
                    )
                )
            добавлено += 1

        session.commit()
    finally:
        session.close()

    print(f"Добавлено опросов: {добавлено}, пропущено (уже были): {пропущено}")


def удалить() -> None:
    """Убирает только то, что добавил этот скрипт, по префиксу ключа."""
    session = SessionLocal()
    try:
        опросы = session.execute(
            select(ScenarioTemplate).where(ScenarioTemplate.scenario_key.like(ПРЕФИКС + "%"))
        ).scalars().all()
        ключи = [о.scenario_key for о in опросы]

        шаги = session.execute(
            select(FlowStepTemplate).where(FlowStepTemplate.flow_key.in_(ключи))
        ).scalars().all() if ключи else []

        for шаг in шаги:
            session.delete(шаг)
        for опрос in опросы:
            session.delete(опрос)
        session.commit()
    finally:
        session.close()

    print(f"Удалено демо-опросов: {len(опросы)}, шагов: {len(шаги)}")


if __name__ == "__main__":
    парсер = argparse.ArgumentParser(description=__doc__)
    парсер.add_argument("--remove", action="store_true", help="убрать демо-опросы")
    аргументы = парсер.parse_args()
    удалить() if аргументы.remove else добавить()
