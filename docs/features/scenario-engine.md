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
- `candidate_work_stage` changes в employee detail — отдельный trigger source для HR-driven candidate lifecycle.

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
4. Сохранить progress в `scenario_progress`, включая короткую историю предыдущих интерактивных шагов и undo-снимок последнего подтвержденного ответа.
5. Если user response не нужен, auto-advance к следующему step или schedule follow-up delivery.
6. Если response нужен, ждать text/file/button input и применить result к employee state.
7. Для активного интерактивного шага runtime поддерживает default `Назад`: для text/file это reply button, для button/branching — inline button. Откат возвращает на предыдущий интерактивный шаг в рамках текущего незавершенного сценария и откатывает последний подтвержденный ответ: целевое поле карточки, `candidate_status`, survey answer и загруженный file record, если именно этот ответ их создал/изменил.
8. Если step имеет `response_type=launch_scenario`, runtime теперь завершает текущий progress и сразу вызывает `start_scenario(...)` для `launch_scenario_key`. Раньше это работало только в branch-specific path и ломалось для обычных шагов.

## Launch audit и follow-up jobs

- `flow_launch_requests` используются в двух разных смыслах:
  - operator-visible scheduled/manual launches;
  - internal follow-up jobs для отложенного шага внутри уже идущего сценария.
- Добавлен третий тип `launch_type=status_transition`: это backend-queue для сценариев, которые запускаются от смены HR-статуса кандидата, а не вручную и не по scheduler anchor.
- Internal follow-up job маркируется `skip_step_key="__single_step__:<step_key>"`.
- Эти internal jobs не должны показываться в employee list/detail как отдельные planned launches.
- Ручной запуск сценария из карточки сотрудника больше не должен создавать дополнительный pending `manual` request ради продолжения после первого `none` step: сам `send_step(...)` уже умеет либо auto-follow, либо queue next step по normal semantics.

## HR-статус как trigger

- Scenario metadata теперь поддерживает `trigger_mode=candidate_hr_stage`.
- Для такого trigger сценарий хранит явный `candidate_work_stage_trigger`.
- При реальном изменении `employees.candidate_work_stage` из admin backend ставит `flow_launch_requests` с `launch_type=status_transition`.
- Scheduler/worker забирает этот request и вызывает обычный `start_scenario(...)`.
- Повторное сохранение того же самого статуса не должно создавать новый launch request.

## Возврат ветки в основной поток

- Branch step теперь может хранить `return_to_step_key`.
- Это не “прыжок на любой step”, а только возврат в root-step того же сценария.
- Модель нужна для fork-then-merge случаев: ветка решает локальную задачу и потом возвращает пользователя в общий mainline.
- Защита от очевидной петли включена: ветка не должна возвращаться в тот же root-step, из которого она выросла.
- Если `return_to_step_key` не задан, поведение остается прежним: после ветки runtime идет к следующему root-step после точки ветвления.

## Editor guardrails

- В React scenario workspace тип ответа теперь явно показывает, блокирует ли шаг поток.
- `text`, `file`, `buttons` и `branching` считаются интерактивными: после отправки такого шага бот ждет ответ и не переходит дальше автоматически.
- `none` не блокирует сценарий и должен использоваться для чисто информационных шагов, файлов и текстов, после которых не нужен ответ.
- Новые scenario-шаги, branch-шаги и chain-шаги не должны сохранять декоративный default text. Поле сообщения остается пустым, а подсказка показывается только как UI placeholder.
- `buttons` и `branching` могут сохранять выбранный вариант в `target_field`, включая `salary_expectation`; editor не должен сбрасывать это поле при сохранении branching step.

## Сценарные уведомления

- Explicit recipients в сценарных уведомлениях хранятся как tokens.
- `employee:<id>` резолвится в основной Telegram chat id выбранного сотрудника/кандидата.
- `hr` резолвится через singleton `HrSettings.telegram_user_id`.
- React workspace строит список получателей из отдельного `notification_recipient_options`: сначала системный HR, если у него задан Telegram ID, затем сотрудники/кандидаты.
- HR не должен создаваться как фейковая запись `employees` только ради выбора в уведомлениях.

## Read-only graph contract

- Workspace API теперь дополнительно отдает `workspace.graph` для read-only overview режима.
- Graph не является отдельным источником истины и не должен жить по своей семантике: он строится из тех же step trees и follow-up rules, что и runtime/list view.
- `nodes` включают реальные steps плюс служебные placeholder nodes:
  - `branch_slot` для пустой ветки;
  - `launch_target` для перехода в другой сценарий.
- `edges` отражают runtime-переходы:
  - `next` — обычный следующий шаг;
  - `branch_option` — выбор кнопки в branching step;
  - `chain` — вход или продолжение вложенной цепочки;
  - `return_to_root` — merge branch обратно в root flow;
  - `launch_scenario` — переход в другой сценарий.
- Layout координаты backend не отдает намеренно: фронт сам раскладывает graph, чтобы не смешивать domain contract и presentation.

## Известные ограничения

- Transition model к другому scenario еще не semantically clean.
- `launch_scenario` больше не зависает молча, но продуктовое правило для пустого `launch_scenario_key` все еще стоит считать editor/data-quality проблемой, а не “легальной” runtime-ситуацией.
- Step notifications прикреплены на уровне step, button notifications — отдельно.
- Empty step content все еще требует отдельной runtime/UI-валидации: новые шаги больше не получают placeholder text, но полностью пустые сценарные сообщения пока остаются допустимым состоянием модели.
- Attachment-only interactive steps все еще могут потребовать отдельное helper-message, потому что messenger transport пока не умеет captions + inline markup для file/photo delivery.
- Candidate и employee behavior все еще используют один engine и data model. Это удобно, но продуктово нечисто.
- `Назад` теперь умеет откатывать только последний подтвержденный ответ внутри живого progress. Это не глобальный time-travel: он не раскатывает цепочку из нескольких уже завершенных сценариев и не обещает undo для внешних side effects вне текущего runtime-контракта.

## Связанная работа

- `HRB-P1-02` transition semantics
- `HRB-P1-03` notification unification
- `HRB-P1-04` removal of empty and system messages

## Связанные документы

- [[features/notifications]]
- [[features/employee-lifecycle]]
- [[features/bot-identity]]
