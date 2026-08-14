---
title: Движок сценариев
date: 2026-05-06
status: active
doc_type: feature
area: bot
task_tokens:
  - HRB-P1-02
  - HRB-P1-03
  - HRB-P1-04
related:
  - "[[architecture]]"
  - "[[features/notifications]]"
  - "[[features/employee-lifecycle]]"
  - "[[features/bot-identity]]"
source_of_truth: true
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

## Audience targeting

- `employee_scope` продолжает отвечать за coarse split `кандидаты / сотрудники / все`.
- `role_scope` теперь допускает не одну должность, а нормализованный набор ролей в одном поле `scenario_templates.role_scope`.
- Для MVP набор хранится как CSV (`designer,analyst`), но API workspace отдает и raw `role_scope`, и нормализованный массив `role_scopes`.
- Значение `all` остается взаимоисключающим shorthand: если выбрано оно, остальные роли игнорируются.

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
3. Разделить subject и recipient:
   - `context employee` / `subject employee` — по чьей карточке идет процесс;
   - `recipient employee` — кто реально получает шаг в Telegram.
4. Отправить text, optional employee card, optional attachment и optional buttons уже по resolved recipient.
4. Если в тексте есть `{doc:...}`, runtime резолвит персональный document slot сотрудника:
   - для link-based slot подставляет кликабельную ссылку в текст;
   - для file-based slot оставляет human-readable title в тексте и дополнительно отправляет сам файл в чат.
5. Сохранить progress в `scenario_progress`, включая короткую историю предыдущих интерактивных шагов и resolved recipient (`recipient_mode`, `recipient_employee_id`, `recipient_chat_id`).
6. Если user response не нужен, auto-advance к следующему step или schedule follow-up delivery.
7. Если response нужен, ждать text/file/button input от resolved recipient и применить result к employee state context employee.
8. Для активного интерактивного шага runtime поддерживает default `Назад`: для text/file это reply button, для button/branching — inline button. Откат возвращает только на предыдущий интерактивный шаг в рамках текущего незавершенного сценария.

## Recipient model

- `scenario_templates.recipient_mode` определяет, кому доставлять шаги:
  - `self`;
  - `manager`;
  - `mentor_adaptation`;
  - `mentor_ipr`;
  - `hr`.
- Backward compatibility:
  - старые сценарии по умолчанию остаются `self`;
  - `trigger_mode=manager_assigned_adaptation` при legacy `recipient_mode=self` runtime трактует как `manager`, чтобы старые trigger-сценарии не слали шаги самому адаптируемому сотруднику.
- Runtime не меняет subject progress:
  - `ScenarioProgress.employee_id` всегда остается context employee;
  - recipient хранится отдельно, чтобы ответы руководителя или наставника продолжали тот же progress, а не создавали новый на их карточке.

## Semantics of `FlowLaunchRequest`

- `FlowLaunchRequest` не делает snapshot recipient-а на момент постановки события.
- Сознательное текущее правило:
  - request хранит только subject employee и `flow_key`;
  - recipient вычисляется заново в момент фактической обработки и отправки шага.
- Практический смысл:
  - если после события HR сменил руководителя или наставника до обработки очереди, сообщение уйдет уже актуальному назначенному адресату.
- Это особенно важно для `manager_assigned_adaptation`:
  - queue строится по адаптируемому сотруднику;
  - runtime решает, кто его текущий руководитель на момент отправки.
- Если продукту когда-нибудь понадобится жесткий snapshot “кому именно должно было уйти на момент события”, это уже другая модель:
  - отдельные recipient snapshot fields в launch queue или отдельная delivery/outbox table;
  - сейчас такую модель не вводим без отдельного согласования.
- Delivery lifecycle:
  - `processing_status=pending` — request ждет due-time;
  - scheduler claim-ит request через conditional `UPDATE ... WHERE processed_at IS NULL AND processing_status = 'pending'`;
  - успешный claim переводит request в `processing`, увеличивает `processing_attempts`, ставит `claimed_at` и коммитит claim до Telegram side effects;
  - успешная обработка ставит `processing_status=processed`, `processed_at` и `completed_at`;
  - exception во время обработки ставит `processing_status=failed`, `failed_at` и `last_error`.
- Перед polling pending queue scheduler переводит stale `processing` requests старше 15 минут в terminal `failed` с `last_error=Stale processing request expired before completion`; это закрывает crash-after-claim-before-side-effects, когда request иначе завис бы в `processing` навсегда.
- `failed` сейчас terminal для автоматического scheduler loop: такой request не подхватывается повторно, чтобы не дублировать уже потенциально отправленное сообщение после частичного сбоя.
- Failed/stale requests остаются диагностически видимыми в employee detail API как `failed_launch_history`; это read-only audit surface, не обычная pending queue.
- `queue_followup_step()` не создает второй active request для той же пары `employee_id + flow_key + skip_step_key`; это защищает timed follow-up от размножения при повторном проходе engine.

## Delivery failure behavior

- Если recipient не назначен или не привязан к Telegram, runtime не отправляет шаг молча в пустоту.
- В этом случае:
  - `ScenarioProgress.last_delivery_error` получает причину;
  - worker/web logs пишут warning;
  - `FlowLaunchRequest` получает `processed`, если runtime корректно дошел до контролируемого delivery failure внутри scenario engine;
  - `FlowLaunchRequest` получает `failed`, если сам scheduler request упал exception-ом до корректного завершения обработки.
- Автоматического retry после исправления карточки сейчас нет.
- Текущая operational модель:
  - после исправления менеджера/наставника/Telegram binding нужен manual relaunch;
  - либо в будущем нужна отдельная retry-модель с явной семантикой повторной доставки.

## Incoming answer routing

- Текст, файл и команда `Назад` резолвятся по effective recipient:
  - сначала `ScenarioProgress.recipient_employee_id`;
  - legacy/self progress без recipient хранит ожидание на `ScenarioProgress.employee_id`.
- Если для одного recipient есть ровно один active `waiting_for_response`, ответ применяется к нему.
- Если active waiting progress больше одного, runtime fail-closed:
  - не выбирает newest progress молча;
  - не применяет ответ к карточке;
  - проставляет `last_delivery_error` на конфликтующих progress;
  - отправляет пользователю сообщение, что бот не может безопасно определить сценарий и нужно обратиться к HR или перезапустить нужный сценарий.

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
