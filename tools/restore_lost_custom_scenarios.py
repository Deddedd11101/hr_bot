from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


DB_PATH = Path("/opt/hr_bot/hr_bot.db")


@dataclass
class StepDef:
    step_key: str
    title: str
    text: str
    response_type: str = "none"
    button_options: str | None = None
    send_mode: str = "immediate"
    send_time: str | None = None
    day_offset_workdays: int = 0
    target_field: str | None = None
    launch_scenario_key: str | None = None
    branch_option_index: int | None = None
    children: list["StepDef"] = field(default_factory=list)


RESTORE_BY_TITLE: dict[str, list[StepDef]] = {
    "Тестовое задание (дизайнер)": [
        StepDef(
            step_key="designer_test_intro",
            title="Готовность выполнить тестовое задание",
            text="{name}, привет! Поздравляем с успешным прохождением собеседования с руководителем! На следующем этапе мы попросим тебя выполнить тестовое задание, чтобы оценить твои практические навыки. Готов ли ты выполнить тестовое задание?",
            response_type="branching",
            button_options="Да, готов\nНе готов",
            children=[
                StepDef(
                    step_key="designer_test_intro__branch_yes",
                    title="Ветка: согласен выполнить",
                    text="",
                    branch_option_index=0,
                ),
                StepDef(
                    step_key="designer_test_intro__branch_no",
                    title="Ветка: сомневается",
                    text="{name}, выполнение тестового задания является очень важным этапом собеседования, который позволит нам понять уровень твоих навыков, а тебе на практике познакомиться с предстоящими задачами. Ну что, уговорил я тебя выполнить тестовое практическое задание?",
                    response_type="buttons",
                    button_options="Да, готов",
                    branch_option_index=1,
                ),
            ],
        ),
        StepDef(
            step_key="designer_test_send_task",
            title="Отправка тестового задания",
            text="Лови тестовое задание! Срок для выполнения - 4 дня. Желаем удачи! https://drive.google.com/file/d/10Fg0rMXXqiSuGDPbbzT8fQwtgQwYAD0l/view?usp=sharing",
        ),
        StepDef(
            step_key="designer_test_wait_ready",
            title="Ожидание готовности",
            text='После выполнения задания нажми "Готово".',
            response_type="buttons",
            button_options="Готово",
        ),
        StepDef(
            step_key="designer_test_upload",
            title="Загрузка выполненного задания",
            text="Ура! Не терпится взглянуть! Загрузи файл с выполненным тестовым заданием в формате docx, pdf.",
            response_type="file",
            target_field="candidate_file",
        ),
        StepDef(
            step_key="designer_test_done",
            title="Подтверждение получения",
            text="Спасибо! Мы в ближайшее время оценим результат и вернемся с обратной связью.",
        ),
    ],
    "Стартовый": [
        StepDef(
            step_key="starter_intro",
            title="Приветствие",
            text="Привет! Я - Зефирный чат-бот. Помогаю соискателям и сотрудникам Зефира. И тебе помогу, не сомневайся!",
        ),
        StepDef(
            step_key="starter_pd_consent",
            title="Согласие на ПДн",
            text="Небольшая формальность: для дальнейшего общения нам необходимо твое согласие на обработку персональных данных. Ознакомься, пожалуйста, с документом по ссылке: (вставить ссылку)",
            response_type="branching",
            button_options="Ознакомлен, согласен\nНе согласен",
            target_field="personal_data_consent",
            children=[
                StepDef(
                    step_key="starter_pd_consent__branch_yes",
                    title="Ветка: согласие получено",
                    text="",
                    branch_option_index=0,
                ),
                StepDef(
                    step_key="starter_pd_consent__branch_no",
                    title="Ветка: отказ от ПДн",
                    text="К сожалению мы не сможем продолжить дальнейшее общение через чат-бота.",
                    branch_option_index=1,
                ),
            ],
        ),
        StepDef(
            step_key="starter_role_choice",
            title="Определение типа пользователя",
            text="Супер! Расскажи, ты являешься соискателем или уже работаешь в нашей команде?",
            response_type="branching",
            button_options="Я - кандидат\nЯ - сотрудник",
            children=[
                StepDef(
                    step_key="starter_role_choice__branch_candidate",
                    title="Ветка: кандидат",
                    text="",
                    response_type="launch_scenario",
                    launch_scenario_key="recruitment_hiring",
                    branch_option_index=0,
                ),
                StepDef(
                    step_key="starter_role_choice__branch_employee",
                    title="Ветка: сотрудник",
                    text="",
                    response_type="launch_scenario",
                    launch_scenario_key="first_day",
                    branch_option_index=1,
                ),
            ],
        ),
    ],
    "Оффер": [
        StepDef(
            step_key="offer_congrats",
            title="Поздравление",
            text="{name}, поздравляем тебя с успешным выполнением тестового задания!",
        ),
        StepDef(
            step_key="offer_interest",
            title="Интерес к офферу",
            text="Скажи, готов ли ты рассмотреть наше предложение?",
            response_type="branching",
            button_options="Да, готов\nНет, не готов",
            children=[
                StepDef(
                    step_key="offer_interest__branch_yes",
                    title="Ветка: готов рассмотреть",
                    text="Круто! Лови наш оффер!",
                    branch_option_index=0,
                ),
                StepDef(
                    step_key="offer_interest__branch_no",
                    title="Ветка: отказ от оффера",
                    text="Спасибо за честный ответ. Если ситуация изменится, будем рады вернуться к общению.",
                    response_type="launch_scenario",
                    launch_scenario_key="custom_scenario_1774855216",
                    branch_option_index=1,
                ),
            ],
        ),
        StepDef(
            step_key="offer_review",
            title="Ожидание ответа по офферу",
            text="Изучи наше предложение и возвращайся с ответом! Мы ждем ответ 2 рабочих дня.",
            response_type="buttons",
            button_options="Принимаю оффер",
        ),
        StepDef(
            step_key="offer_start_date",
            title="Дата выхода",
            text="{name}, с какого числа ты будешь готов стать частью команды Зефира?",
            response_type="text",
        ),
        StepDef(
            step_key="offer_finish",
            title="Финальное подтверждение",
            text="Отлично! Договорились! За день до даты выхода отправлю тебе список документов для трудоустройства. До встречи в Зефире!",
        ),
    ],
    "Преонбординг": [
        StepDef(
            step_key="preonboarding_intro",
            title="Подготовка документов",
            text="{name}, привет! Не терпится увидеть тебя в составе команды Зефира! Осталось совсем чуть-чуть - для трудоустройства нам понадобятся сканы документов, перечисленных в файле.",
        ),
        StepDef(
            step_key="preonboarding_upload_link",
            title="Ссылка для загрузки документов",
            text="Подготовленные документы загрузи по ссылке: (указать ссылку)",
        ),
        StepDef(
            step_key="preonboarding_ready",
            title="Подтверждение отправки документов",
            text='Постарайся сделать это до конца текущего дня, чтобы мы могли все проверить до твоего выхода. После загрузки документов нажми "Отправил документы".',
            response_type="buttons",
            button_options="Отправил документы",
        ),
    ],
    "Отклонение кандидата": [
        StepDef(
            step_key="candidate_rejection_message",
            title="Сообщение об отклонении",
            text="Спасибо за обратную связь. Понимаем и уважаем твое решение. Если ситуация изменится, будем рады вернуться к общению.",
        ),
    ],
}


def insert_step(
    cur: sqlite3.Cursor,
    flow_key: str,
    step: StepDef,
    sort_order: int,
    parent_step_id: int | None = None,
) -> int:
    cur.execute(
        """
        insert into flow_step_templates (
            flow_key, step_key, parent_step_id, branch_option_index, step_title,
            sort_order, default_text, custom_text, response_type, button_options,
            send_mode, send_time, day_offset_workdays, target_field, launch_scenario_key,
            attachment_path, attachment_filename
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            flow_key,
            step.step_key,
            parent_step_id,
            step.branch_option_index,
            step.title,
            sort_order,
            step.text,
            None,
            step.response_type,
            step.button_options,
            step.send_mode,
            step.send_time,
            step.day_offset_workdays,
            step.target_field,
            step.launch_scenario_key,
            None,
            None,
        ),
    )
    step_id = int(cur.lastrowid)
    for index, child in enumerate(step.children):
        child_sort = sort_order * 100 + index + 1
        insert_step(cur, flow_key, child, child_sort, parent_step_id=step_id)
    return step_id


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    scenarios = cur.execute(
        "select id, title, scenario_key from scenario_templates where title in ({}) order by id".format(
            ",".join("?" for _ in RESTORE_BY_TITLE)
        ),
        tuple(RESTORE_BY_TITLE.keys()),
    ).fetchall()
    scenario_map = {title: scenario_key for _, title, scenario_key in scenarios}

    missing = [title for title in RESTORE_BY_TITLE if title not in scenario_map]
    if missing:
        raise RuntimeError(f"Scenarios not found in DB: {missing}")

    restored: list[tuple[str, int]] = []
    for title, steps in RESTORE_BY_TITLE.items():
        flow_key = scenario_map[title]
        cur.execute("delete from flow_step_templates where flow_key = ?", (flow_key,))
        for index, step in enumerate(steps):
            insert_step(cur, flow_key, step, (index + 1) * 10)
        restored.append((title, len(steps)))

    conn.commit()
    for title, count in restored:
        print(f"{title}: restored {count} top-level steps")


if __name__ == "__main__":
    main()
