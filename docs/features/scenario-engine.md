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
- `employee_document_links` / `employee_files` — персональные document slots для тегов вида `{doc:...}`.

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
4. Если в тексте есть `{doc:...}`, runtime резолвит персональный document slot сотрудника:
   - для link-based slot подставляет кликабельную ссылку в текст;
   - для file-based slot оставляет human-readable title в тексте и дополнительно отправляет сам файл в чат.
5. Сохранить progress в `scenario_progress`, включая короткую историю предыдущих интерактивных шагов.
6. Если user response не нужен, auto-advance к следующему step или schedule follow-up delivery.
7. Если response нужен, ждать text/file/button input и применить result к employee state.
8. Для активного интерактивного шага runtime поддерживает default `Назад`: для text/file это reply button, для button/branching — inline button. Откат возвращает только на предыдущий интерактивный шаг в рамках текущего незавершенного сценария.

Для time-based сценариев есть дополнительное правило:

- если сценарий активировали в тот же день, но время первого шага уже прошло, scheduler обязан отправить первый непройденный шаг немедленно, а не перескакивать к следующему time slot;
- если timed step был вызван самим scheduler, `send_step` не должен самостоятельно queue'ить следующий `specific_time` шаг через `FlowLaunchRequest`: дальнейшее расписание в этом режиме принадлежит scheduler, иначе возникают дубли и late-start skips.
- перед фактической отправкой scheduler обязан повторно проверить, что сценарий все еще совместим с текущим состоянием карточки; stale jobs и pending requests после смены `employee_stage` / даты-якоря должны silently отбрасываться, а не утекать в чат.

## Editor guardrails

- В React scenario workspace тип ответа теперь явно показывает, блокирует ли шаг поток.
- `text`, `file`, `buttons` и `branching` считаются интерактивными: после отправки такого шага бот ждет ответ и не переходит дальше автоматически.
- `none` не блокирует сценарий и должен использоваться для чисто информационных шагов, файлов и текстов, после которых не нужен ответ.
- Новые scenario-шаги, branch-шаги и chain-шаги не должны сохранять декоративный default text. Поле сообщения остается пустым, а подсказка показывается только как UI placeholder.

## Известные ограничения

- Transition model к другому scenario еще не semantically clean.
- Step notifications прикреплены на уровне step, button notifications — отдельно.
- Empty step content все еще требует отдельной runtime/UI-валидации: новые шаги больше не получают placeholder text, но полностью пустые сценарные сообщения пока остаются допустимым состоянием модели.
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
