---
title: Модель данных HR Bot
date: 2026-05-12
status: active
doc_type: data
area: data
task_tokens:
  - HRB-DOC-02
  - HRB-DISC-04
  - HRB-P2-07
related:
  - "[[backlog]]"
  - "[[project_state]]"
  - "[[roadmap-2026-05-12]]"
source_of_truth: true
---

# Модель данных

## Каноническое правило

Для HR Bot документация схемы данных строится как **code-first плюс tracking observed drift**:

- основной source of truth:
  - `app/models.py`;
  - `app/database.py`;
  - особенно `_ensure_sqlite_schema()`;
- вторичный observational source:
  - live SQLite-файлы вроде `hr_bot.db`;
- если live SQLite содержит объекты без поддержки в коде, они документируются как drift, а не как подтвержденный product contract.

Это правило нужно, потому что в проекте сейчас есть SQLAlchemy-модели, но нет надежной migration chain.

## Что приложение реально делает при startup

`init_db()` выполняет три разные задачи:

1. `Base.metadata.create_all(bind=engine)`
2. `_ensure_sqlite_schema()` для SQLite compatibility patching
3. seed routines для admin accounts и встроенных flow templates

Значит, schema evolution не является чисто декларативной. Runtime может менять форму базы при запуске.

## Критика перед списком таблиц

- Эта модель удобна для demo и stage recovery.
- Но она хрупкая:
  - schema changes не имеют durable migration history;
  - startup может менять production data structures;
  - drift между кодом и live DB уже возможен и уже наблюдается.
- Referential integrity слабая:
  - большинство связей хранится integer ids без formal foreign keys;
  - application layer несет основную нагрузку integrity rules.

## Основные таблицы, поддержанные кодом

### Люди, identity и access

| Таблица | Назначение | Ключевые поля | Связи и примечания |
| --- | --- | --- | --- |
| `employees` | Единая запись для candidates и employees | `full_name`, `first_workday`, `employee_stage`, `candidate_work_stage`, legacy Telegram fields, HR profile fields, consent flags, `is_bot_blocked` | Центральная запись, на нее ссылается большинство runtime tables |
| `employee_assignment_history` | Аудит назначений руководителя и наставников | `subject_employee_id`, `assigned_employee_id`, `assignment_role`, `started_at`, `ended_at`, `assigned_by_account_id` | Не заменяет текущие поля `employees.*_employee_id`; хранит только историю изменений назначений |
| `employee_manual_bot_messages` | Аудит ручных Telegram-сообщений из карточки сотрудника | `employee_id`, `sender_account_id`, `message_text`, `status`, `error_text`, `sent_at`, `created_at` | Не влияет на `scenario_progress` и `flow_launch_requests`; хранит операторские sends и ошибки доставки |
| `positions` | Управляемый справочник должностей | `title`, `slug`, `is_active`, `sort_order`, timestamps | Используется settings UI, employee forms, scenario role scope и targeting; `employees.desired_position` пока остается строкой для backward compatibility |
| `employee_messenger_accounts` | Channel-specific communication identities | `employee_id`, `channel`, `external_user_id`, `external_username`, `is_primary`, `is_active` | Один employee может иметь несколько channel identities; текущий runtime использует `telegram` |
| `admin_accounts` | Пользователи админки | `login`, `password_hash`, `role`, `is_active` | Используется browser session auth |

### Редактирование и выполнение сценариев

| Таблица | Назначение | Ключевые поля | Связи и примечания |
| --- | --- | --- | --- |
| `scenario_templates` | Metadata сценариев и опросов | `scenario_key`, `title`, `scenario_kind`, `role_scope`, `employee_scope`, `recipient_mode`, `trigger_mode`, `target_employee_id`, `description`, `sort_order` | Parent entity для steps и runtime launches; `role_scope` хранит `all` или CSV position slug'ов для multi-position targeting; `recipient_mode` отделяет context employee от фактического Telegram-получателя |
| `flow_step_templates` | Step definitions | `flow_key`, `step_key`, `parent_step_id`, `branch_option_index`, `response_type`, `button_options`, scheduling fields, target field, `return_to_step_key`, `is_terminal`, `attachment_path`, `attachment_filename`, `attachment_document_item_id`, notification fields | Root steps имеют `parent_step_id = NULL`; branches и chains вложены через `parent_step_id`; `is_terminal` явно завершает сценарий на этом шаге; `attachment_document_item_id` ссылается на shared `document_library_items` |
| `step_button_notifications` | Notification overrides для button options | `flow_key`, `step_id`, `option_index`, `message_text`, recipient fields | Дополнительная notification model для конкретной button option |
| `step_send_notifications` | Notification rules при показе шага | `flow_key`, `step_id`, `rule_index`, `message_text`, recipient fields | Новая множественная модель step-level notifications; legacy `notify_on_send_*` остается compatibility seam |
| `scenario_progress` | Runtime position сценария по context employee | `employee_id`, `scenario_key`, `recipient_mode`, `recipient_employee_id`, `recipient_chat_id`, `current_step_key`, `waiting_for_response`, `is_completed`, `last_delivery_error`, timestamps | Tracks active/completed scenario state и отдельно хранит resolved recipient для reply-flow и audit |
| `flow_launch_requests` | Launch queue/audit для manual, scheduled, status-triggered и system work | `employee_id`, `flow_key`, `requested_at`, `processed_at`, `launch_type`, `skip_step_key` | `launch_type=manual` означает операторский запуск; `status_transition` — автозапуск по HR-статусу; `registration`/`bot_registration`/`trigger`/`system` — системные/регистрационные события |
| `survey_answers` | Сохраненные ответы на survey-like steps | `employee_id`, `scenario_key`, `step_key`, `answer_value`, `file_name`, `answered_at` | Отдельно от `scenario_progress`, потому что answers can accumulate |
| `onboarding_events` | Исторический лог onboarding sends | `employee_id`, `scheduled_at`, `sent_at`, `event_key`, `message` | Используется scheduled onboarding logic |

### HR settings, menus и bulk actions

| Таблица | Назначение | Ключевые поля | Связи и примечания |
| --- | --- | --- | --- |
| `hr_settings` | Глобальные HR notification settings и default menu | recipient ids, notification flags, `default_menu_set_id`, `default_employee_menu_set_id`, `default_candidate_menu_set_id` | По сути singleton-style configuration |
| `bot_menu_sets` | Employee-facing bot menu groups | `title`, `description`, `sort_order`, `employee_scope`, `role_scope`, explicit target fields, `system_tag` | Parent table для menu buttons; `system_tag` маркирует generated document menu branches |
| `bot_menu_buttons` | Кнопки меню | `menu_set_id`, `label`, `action_type`, `scenario_key`, `target_menu_set_id`, `document_item_id` | Используется inbound text menu handling; `action_type=send_document` ссылается на `document_library_items` |
| `mass_scenario_actions` | Очередь bulk scenario launches | flow key, scenario kind, targeting fields, `launch_type`, `recipient_count` | Разрешается и обрабатывается scheduler |
| `mass_message_actions` | Очередь bulk free-text sends | message text, targeting fields, `launch_type`, `recipient_count` | Разрешается и обрабатывается scheduler |

### Files и documents

| Таблица | Назначение | Ключевые поля | Связи и примечания |
| --- | --- | --- | --- |
| `employee_files` | Inbound и outbound employee files | `employee_id`, `direction`, `category`, Telegram file ids, `stored_path`, `mime_type`, `file_size` | Backed by local filesystem storage |
| `employee_document_links` | Per-employee document slots/links | `employee_id`, `slot_key`, `title`, `url`, `item_kind`, `employee_file_id` | Offer, resume и test-result slots могут быть link-backed или file-backed через `employee_files`; generic payload исключает semantic slots |
| `document_library_items` | Shared library documents for bot menu and scenario steps | `title`, `description`, `category`, `item_kind`, `external_url`, stored file metadata, `is_active`, `sort_order` | Общие материалы для `/app/documents`, `send_document` menu buttons и reusable вложений шагов сценария |

## Важные runtime rules

### Employee document slots

- `employee_document_links.slot_key=resume` — единственная актуальная связь резюме в карточке кандидата/сотрудника.
- Replace/upload резюме создает новый `employee_files.category=resume` и переносит `resume` slot на новый файл.
- Очистка resume slot удаляет только связь в `employee_document_links`; старые `employee_files.category=resume` и физические файлы остаются для аудита/legacy fallback.
- `resume` slot не должен попадать в generic `document_links` payload, чтобы UI не показывал destructive generic delete рядом с резюме.
- Даже если старый клиент напрямую вызовет generic document-link delete для `slot_key=resume`, backend удаляет только link row и сохраняет `EmployeeFile` плюс физический файл.
- Если `resume` slot пустой, runtime/API может использовать последний `employee_files.category=resume` как совместимый fallback.
- `employee_document_links.slot_key=test_task_result` — актуальная связь ответа на тестовое; если slot отсутствует или невалиден, карточка может показать последний legacy `employee_files.category=test_result`.
- Generic employee detail payload исключает semantic file categories `resume`, `test_result`, `offer_document`, чтобы карточка не смешивала текущие продуктовые документы с общими файлами.

### `employees`

- Candidates и employees живут в одной таблице.
- Практический split application-level:
  - candidates обычно имеют `employee_stage = "candidate"`;
  - non-candidates используют stages вроде `adaptation`, `ipr`, `staff`.
- Это просто, но продуктово грязно. Один row type растянут на recruiting, onboarding и staff communication.

### `employee_assignment_history`

- Таблица хранит только аудит изменений полей:
  - `manager_employee_id`;
  - `mentor_adaptation_employee_id`;
  - `mentor_ipr_employee_id`.
- Current source of truth для актуального состояния остается в `employees`.
- При сохранении карточки сотрудника runtime делает ровно такую sync-semantics:
  - если значение роли не изменилось, history не трогается;
  - если активное назначение этой роли меняется или очищается, старая запись закрывается через `ended_at`;
  - если появляется новое значение, создается новая активная запись;
  - дубль активной записи для одной и той же пары `subject + role + assigned` не создается.
- `assigned_by_account_id` сейчас best-effort:
  - JSON API и classic card save пробрасывают текущий admin account id;
  - nullable сохраняется как fallback, если update path не знает текущего аккаунта.

### `employee_manual_bot_messages`

- Таблица фиксирует только прямые операторские сообщения из employee detail.
- Это отдельный audit seam, а не часть сценарного runtime:
  - не двигает `scenario_progress`;
  - не создает `flow_launch_requests`;
  - не заменяет массовые сообщения.
- Поведение записи:
  - пустой текст отклоняется validation-слоем и не логируется;
  - blocked employee, missing/non-numeric chat id, missing token и Telegram exception пишутся как `status=failed`;
  - успешная отправка пишет `status=sent` и `sent_at`.

### `employee_hr_notes`

- Таблица хранит append-only историю непустых изменений HR-заметок из карточки.
- `employees.notes` остается текущим editable значением для совместимости с существующим UI/API.
- Повторное сохранение того же текста не создает дубль history row.
- `author_account_id` best-effort и nullable: JSON/API path передает текущий admin account, старые или системные paths могут оставить пустым.

### `employee_messenger_accounts`

- Это реальная uniqueness boundary для Telegram identity.
- Unique constraint:
  - `(channel, external_user_id)`
- Legacy fields `employees.telegram_user_id` и `employees.telegram_username` все еще существуют и активно синхронизируются.
- Значит, identity сейчас живет в двух местах. App старается держать их aligned, но модель transitional.

### `scenario_progress`

- `employee_id` здесь означает не “кому ушло сообщение”, а context employee, по которому идет процесс.
- `recipient_employee_id` и `recipient_chat_id` фиксируют фактического Telegram-получателя текущего шага.
- Это нужно, чтобы:
  - reply-flow руководителя или наставника не создавал ложный progress на самом руководителе;
  - runtime мог обновлять карточку subject employee по ответу другого участника;
  - missing recipient не превращался в silent drop.
- `last_delivery_error` — минимальный code-backed audit seam:
  - если recipient не назначен или у него нет Telegram binding, progress сохраняет причину последней неудачной доставки;
  - это не полноценный outbox, но уже не беззвучная потеря шага.

### `scenario_templates` и `flow_step_templates`

- Scenario authoring table-driven.
- `role_scope` остается одним storage field для обратной совместимости:
  - `all` или пустой normalized набор означает все должности;
  - одиночный legacy slug остается валидным;
  - несколько должностей хранятся как CSV slug'ов, например `designer,analyst`.
- У scenario теперь есть отдельный recipient layer:
  - `employee_id` в launch/progress остается subject/context employee;
  - `recipient_mode` определяет фактического получателя шага;
  - templating сообщения продолжает подставлять данные именно context employee, а не recipient employee.
- Steps могут представлять:
  - обычные send-only nodes;
  - text/file/button response nodes;
  - branch parents;
  - branch child nodes;
  - chain nodes;
  - launch-another-scenario nodes.
- Nested structure кодируется через `parent_step_id` и `branch_option_index`, а не через отдельную graph model.
- `is_terminal=true` на step является явной runtime-остановкой:
  - send-only step закрывает progress после отправки;
  - interactive step закрывает progress после валидного ответа;
  - follow-up и следующий root/chain step не запускаются.
- Вложения шага имеют два совместимых источника:
  - legacy uploaded file через `attachment_path` / `attachment_filename`;
  - reusable shared document через nullable `attachment_document_item_id`.
- Runtime сначала пытается отправить active `document_library_items` из `attachment_document_item_id`:
  - `item_kind=file` отправляется как файл или фото из `storage/document_library`;
  - `item_kind=link` отправляется как текст со ссылкой.
- Если shared document отсутствует, неактивен или не может быть отправлен, старый uploaded attachment остается fallback, поэтому существующие шаги с `attachment_path` не ломаются.
- Если broken shared document был единственным содержимым шага, delivery failure виден через `scenario_progress.last_delivery_error`.

## Что добавляет или нормализует `_ensure_sqlite_schema()`

SQLite schema guard делает больше, чем “создать таблицы, если их нет”. Важное поведение:

- добавляет missing columns в `employees`, `scenario_templates`, `flow_step_templates`, `hr_settings`, mass action tables и launch tables;
- отдельный новый recipient-sensitive участок schema patching:
  - `scenario_templates.recipient_mode`;
  - `scenario_progress.recipient_mode`;
  - `scenario_progress.recipient_employee_id`;
  - `scenario_progress.recipient_chat_id`;
  - `scenario_progress.last_delivery_error`;
- добавляет `flow_step_templates.attachment_document_item_id` и index `ix_flow_step_templates_attachment_document_item_id` для reusable вложений из shared document library;
- добавляет `flow_step_templates.is_terminal` для explicit terminal steps;
- создает целые таблицы, если они отсутствуют:
  - `employee_assignment_history`;
  - `employee_manual_bot_messages`;
  - `employee_hr_notes`;
  - `step_button_notifications`;
  - `step_send_notifications`;
  - `scenario_progress`;
  - `survey_answers`;
  - `admin_accounts`;
  - `bot_menu_sets`;
  - `bot_menu_buttons`;
  - `document_library_items`;
  - `mass_scenario_actions`;
  - `mass_message_actions`;
  - `employee_messenger_accounts`;
- нормализует legacy values на месте:
  - `desired_position`;
  - `employee_stage`;
- пересоздает `employees` в SQLite, если старые файлы еще держат obsolete `NOT NULL` constraints;
- backfill `employee_messenger_accounts` из legacy employee Telegram fields.

Именно поэтому data-model docs нельзя строить только по `models.py`.

## Наблюдаемый live SQLite drift

Инспекция локального `hr_bot.db` показывает schema objects, которые не объясняются текущим application code:

- таблица `media_assets`;
- колонка `flow_step_templates.media_asset_id`.

Текущее состояние evidence:

- эти объекты есть в inspected SQLite file;
- `rg` по `app/`, `tests/`, `tools/` и `docs/` не нашел active code references для `media_assets` или `media_asset_id`;
- `app/models.py` не определяет `MediaAsset` model или `media_asset_id` на `FlowStepTemplate`;
- `_ensure_sqlite_schema()` в текущем коде не создает и не обслуживает эту table/column.

Вывод:

- считать `media_assets` unresolved database drift, а не supported subsystem;
- не строить новые features поверх него до выяснения ownership и runtime behavior;
- если эта подсистема все еще нужна, ее надо вернуть как code-backed model и явно задокументировать.

## Будущее ограничение: два ИП и раздельное хранение

Текущее бизнес-требование: для двух ИП нужно предусмотреть раздельное хранение данных и явно показать юридический контур в UI. Практически это может означать две отдельные SQLite DB, два deployment-контура или другую модель изоляции, но это нельзя решать добавлением одного поля без LLD.

Статус:

- `HRB-DISC-04` должен подтвердить legal/data requirement и выбрать модель изоляции;
- `HRB-P2-07` должен реализовать выбранную модель в backend, UI, deploy/runbook и backup flow;
- до решения `HRB-DISC-04` текущая canonical schema остается single-database/single-tenant.

Минимальные вопросы для LLD:

- какие данные обязаны быть изолированы: сотрудники, кандидаты, сценарии, файлы, survey answers, admin accounts, audit/history;
- должен ли оператор видеть оба ИП в одной админке или переключаться между контурами;
- можно ли переиспользовать сценарии/опросы между ИП или они тоже должны быть отдельными;
- как делать backup/export/restore, чтобы не смешать данные разных юридических контуров;
- как массовые действия должны блокировать отправки через границу ИП.

## Практический порядок source of truth

Когда code и live SQLite расходятся, использовать такой порядок:

1. текущий application code
2. startup schema guard behavior
3. tests, которые доказывают live usage
4. observed database drift notes

Если в пункте 4 есть важные business data, это warning sign, а не причина молча расширять official model.
