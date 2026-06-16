---
title: Движок сценариев
date: 2026-05-06
status: active
task_tokens:
  - HRB-P1-02
  - HRB-P1-03
  - HRB-P1-04
---

# Движок сценариев

## Назначение

Scenario engine превращает scenario templates плюс employee state в реальные bot communications и progress tracking.

Основной код находится в `app.scenario_engine`.

## Текущие входные данные

- `scenario_templates` — scenario-level metadata.
- `flow_step_templates` — step definitions.
- `scenario_progress` — runtime state.
- `employees` — personalization и field updates.
- `flow_launch_requests` — delayed или manual launches.

## Текущие типы шагов

- `none` — информационный шаг без user response.
- `text` — ждет text input.
- `file` — ждет file upload.
- `buttons` / `branching` — ждет один из configured button options.
- `chain` — nested chain structure.
- `launch_scenario` — launch-oriented behavior, который сейчас перегружен в модели.

## Runtime-поведение

1. Найти scenario и первый step.
2. Отрендерить step text с employee context.
3. Отправить text, optional employee card, optional attachment и optional buttons.
4. Сохранить progress в `scenario_progress`, включая короткую историю предыдущих интерактивных шагов.
5. Если user response не нужен, auto-advance к следующему step или schedule follow-up delivery.
6. Если response нужен, ждать text/file/button input и применить result к employee state.
7. Для активного интерактивного шага runtime поддерживает default `Назад`: для text/file это reply button, для button/branching — inline button. Откат возвращает только на предыдущий интерактивный шаг в рамках текущего незавершенного сценария.

## Editor guardrails

- В React scenario workspace тип ответа теперь явно показывает, блокирует ли шаг поток.
- `text`, `file`, `buttons` и `branching` считаются интерактивными: после отправки такого шага бот ждет ответ и не переходит дальше автоматически.
- `none` не блокирует сценарий и должен использоваться для чисто информационных шагов, файлов и текстов, после которых не нужен ответ.

## Известные ограничения

- Transition model к другому scenario еще не semantically clean.
- Step notifications прикреплены на уровне step, button notifications — отдельно.
- Empty или placeholder step content может утечь в user dialog, если templates смоделированы неаккуратно.
- Candidate и employee behavior все еще используют один engine и data model. Это удобно, но продуктово нечисто.
- `Назад` пока не является полноценным time-travel: он не откатывает уже совершенные side effects и не resurrect'ит сценарий, который уже был terminally completed ответом вроде отказа на consent step.

## Связанная работа

- `HRB-P1-02` transition semantics
- `HRB-P1-03` notification unification
- `HRB-P1-04` removal of empty and system messages

## Связанные документы

- [[features/notifications]]
- [[features/employee-lifecycle]]
- [[features/bot-identity]]
