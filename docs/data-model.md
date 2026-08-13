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
| `scenario_templates` | Metadata сценариев и опросов | `scenario_key`, `title`, `scenario_kind`, `role_scope`, `employee_scope`, `recipient_mode`, `trigger_mode`, `target_employee_id`, `description`, `sort_order` | Parent entity для steps и runtime launches; `recipient_mode` отделяет context employee от фактического Telegram-получателя |
| `flow_step_templates` | Step definitions | `flow_key`, `step_key`, `parent_step_id`, `branch_option_index`, `response_type`, `button_options`, scheduling fields, target field, attachment fields, notification fields | Root steps имеют `parent_step_id = NULL`; branches и chains вложены через `parent_step_id` |
| `step_button_notifications` | Notification overrides для button options | `flow_key`, `step_id`, `option_index`, `message_text`, recipient fields | Дополнительная notification model для конкретной button option |
| `step_send_notifications` | Notification rules при показе шага | `flow_key`, `step_id`, `rule_index`, `message_text`, recipient fields | Новая множественная модель step-level notifications; legacy `notify_on_send_*` остается compatibility seam |
| `scenario_progress` | Runtime position сценария по context employee | `employee_id`, `scenario_key`, `recipient_mode`, `recipient_employee_id`, `recipient_chat_id`, `current_step_key`, `waiting_for_response`, `is_completed`, `last_delivery_error`, timestamps | Tracks active/completed scenario state и отдельно хранит resolved recipient для reply-flow и audit |
| `flow_launch_requests` | Launch queue для manual и scheduled work | `employee_id`, `flow_key`, `requested_at`, `processed_at`, `launch_type`, `skip_step_key` | Используется для будущих запусков и follow-up continuation steps |
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
| `employee_document_links` | Per-employee document slots/links | `employee_id`, `slot_key`, `title`, `url`, `item_kind`, `employee_file_id` | Offer slot может быть link-backed или file-backed через `employee_files` |
| `document_library_items` | Shared library documents for bot menu | `title`, `description`, `category`, `item_kind`, `external_url`, stored file metadata, `is_active`, `sort_order` | Общие материалы для `/app/documents` и `send_document` menu buttons |

## Важные runtime rules

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

## Что добавляет или нормализует `_ensure_sqlite_schema()`

SQLite schema guard делает больше, чем “создать таблицы, если их нет”. Важное поведение:

- добавляет missing columns в `employees`, `scenario_templates`, `flow_step_templates`, `hr_settings`, mass action tables и launch tables;
- отдельный новый recipient-sensitive участок schema patching:
  - `scenario_templates.recipient_mode`;
  - `scenario_progress.recipient_mode`;
  - `scenario_progress.recipient_employee_id`;
  - `scenario_progress.recipient_chat_id`;
  - `scenario_progress.last_delivery_error`;
- создает целые таблицы, если они отсутствуют:
  - `employee_assignment_history`;
  - `employee_manual_bot_messages`;
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
