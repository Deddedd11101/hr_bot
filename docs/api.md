---
title: JSON API HR Bot
date: 2026-05-11
status: active
doc_type: api
area: backend
task_tokens:
  - HRB-DOC-02
  - HRB-P1-07
related:
  - "[[web-surface]]"
  - "[[architecture]]"
  - "[[lld/classic-to-react-admin-migration]]"
source_of_truth: true
---

# JSON API

## Область покрытия

Этот документ описывает реализованную `/api/*` поверхность FastAPI-приложения.

Классические HTML form routes не переопределяются здесь как REST API.
Они описаны отдельно в [[web-surface]].

## Swagger / OpenAPI

- Swagger UI доступен на `/docs`.
- Для удобства также доступен alias `/swagger`, который редиректит на `/docs`.
- Raw OpenAPI schema доступна на `/openapi.json`.
- Схема намеренно ограничена JSON API routes с prefix `/api/*`.
- Browser surfaces, React bootstrap pages, redirects, classic form handlers, download/export routes и `/login` не включаются в Swagger; их source of truth остается [[web-surface]].
- API routes группируются по доменным тегам: `Dashboard`, `Employees`, `Flows and surveys`, `Bulk actions`, `Settings`, `Admin accounts`.
- Shared document library routes живут под `/api/documents/*`; если OpenAPI tags отстают от этого списка, считать route list ниже более точной картой.
- Swagger UI настроен на collapsed sections, включает client-side filter и сохраняет authorization state в браузере.

Это осознанная граница: Swagger должен быть контрактом для React/admin API и интеграционных проверок, а не полной картой всех HTTP URL приложения.

## Модель авторизации

- Все endpoints ниже требуют авторизованную admin session.
- Auth загружается middleware из cookie `hr_admin_auth`.
- JSON API routes вызывают `_require_api_auth()` и без авторизации возвращают:
  - `401 Unauthorized`;
  - body: `{"detail": "Требуется авторизация"}`.
- Большинство JSON routes проходят по `_require_api_auth()`.
- Account management routes дополнительно проходят `_require_api_admin()` и возвращают `403`, если текущий account не `admin`.

## Общие формы ответов

### Payload dashboard workspace

Возвращается из `GET /api/dashboard/workspace`.

- `meta`
  - `recent_days`
  - `upcoming_days`
  - `stat_upcoming_days`
  - `generated_at`
- `stats`
  - `candidates_without_channel`
  - `recent_telegram_links`
  - `recent_inbound_files`
  - `scheduled_next_7_days`
- `upcoming_events`
  - normalized individual scenario launches, mass scenario/survey launches and mass messages
- `telegram_links`
  - свежие active Telegram-привязки кандидатов
- `inbound_files`
  - свежие inbound employee files
- `attention_items`
  - записи без канала, просроченные тестовые и blocked bot state
- `module_links`
  - быстрые переходы в существующие operator modules

### Ответ списка сотрудников

Возвращается из `GET /api/employees` и частично из `POST /api/employees`.

- `meta`
  - `active_tab`
  - `list_title`
  - `empty_message`
  - `create_button_label`
  - `create_modal_title`
  - `create_intro`
  - `first_workday_label`
  - `default_employee_stage`
  - `list_kind`
  - `classic_page_url`
- `items` или `item`
  - `id`
  - `full_name`
  - `chat_id`
  - `chat_handle`
  - `chat_link`
  - `position`
  - `status_label`
  - `candidate_work_stage_label`
  - `planned_scenario_title`
  - `first_workday`
  - `first_workday_label`
  - `test_task_due_at`
  - `test_task_due_at_label`
  - `workdays`
  - `edit_url`
  - `react_edit_url`
  - `list_kind`

### Payload карточки сотрудника

Возвращается большинством `/api/employees/{employee_id}*` routes.

- `meta`
  - контекст списка и edit links
- `employee`
  - нормализованные editable fields карточки
- `options`
  - роли, stages, доступные сценарии
- `files`
  - список файлов сотрудника с download/send URLs
- `document_links`
  - текущие offer link entries
- `scheduled_launches`
  - pending scheduled flow requests
- `manual_launch_history`
  - processed manual launches
- `manual_bot_message_history`
  - read-only история ручных Telegram-сообщений из карточки сотрудника

### Payload scenario workspace

Возвращается `/api/flows/workspace*` routes.

- `scenarios`
  - sidebar list с краткими данными сценариев
- `selected_scenario_id`
- `workspace`
  - `scenario`
    - `recipient_mode`
  - `root_steps`
  - `stats`
  - label dictionaries для UI rendering
  - `employee_options`
  - `available_scenarios`

### Payload settings workspace

Возвращается `/api/settings/workspace` и большинством `/api/settings/*` / `/api/accounts/*` mutations.

- `current_user`
- `role_labels`
- `hr_settings`
- `menu_sets`
  - `buttons[]`
- `available_scenarios`
- `accounts`
  - заполняется только для admin user

### Payload documents workspace

Возвращается `/api/documents/workspace` и большинством `/api/documents/*` mutations.

- `items`
  - shared document library entries;
  - `item_kind=file|link`;
  - metadata: `title`, `description`, `category`, `is_active`, `sort_order`;
  - для links: `external_url`;
  - для files: `original_filename`, `download_url`, `mime_type`, `file_size`.
- `categories`
  - active category list для scaffold/navigation UX.
- `menu_scaffold`
  - состояние generated document menu branch, если она есть.

### Payload bulk actions workspace

Возвращается `/api/bulk-actions/workspace` и bulk mutations.

- `scenarios`
- `surveys`
- `employee_options`
- `role_scope_options`
- `employee_stage_options`
- `candidate_stage_options`
- `document_tag_titles`
- `scheduled_scenario_actions`
- `manual_scenario_history`
- `scheduled_survey_actions`
- `manual_survey_history`
- `scheduled_message_actions`
- `manual_message_history`

## API dashboard workspace

| Method | Path | Назначение | Основные inputs | Response | Side effects | Частые errors |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/dashboard/workspace` | Вернуть read-only payload главного оперативного дашборда. | Нет | Dashboard workspace payload | Нет | `401` |

## API списка и карточки сотрудников

| Method | Path | Назначение | Основные inputs | Response | Side effects | Частые errors |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/employees` | Вернуть React-list сотрудников или кандидатов. | Query: `list_kind=employees|candidates` | Employee list response с `items[]` | Нет | `401` |
| `POST` | `/api/employees` | Создать карточку сотрудника или кандидата. | JSON: `full_name`, `chat_id`, `chat_handle`, `first_workday`, `employee_stage`, `candidate_work_stage`, `list_kind` | Employee list response с созданным `item` | Создает `employees`, sync messenger identity, создает pending `flow_launch_requests` для `recruitment_hiring` | `401`, `409` при messenger identity conflict, не нормализованный `500` при malformed date |
| `GET` | `/api/employees/{employee_id}` | Вернуть полный employee detail payload. | Path: `employee_id` | Employee detail payload с `assignment_history[]` read-only rows (`assignment_role`, `role_label`, `assigned_employee_id`, `assigned_employee_name`, `started_at`, `ended_at`, `is_active`, optional `assigned_by_account_id`) | Нет | `401`, `404` если employee не найден |
| `POST` | `/api/employees/{employee_id}` | Обновить карточку сотрудника или кандидата из React. | JSON fields: `full_name`, `chat_id`, `chat_handle`, `first_workday`, `desired_position`, `birth_date`, `work_email`, `work_hours`, `manager_employee_id`, `mentor_adaptation_employee_id`, `mentor_ipr_employee_id`, `adaptation_tasks_url`, `adaptation_feedback_url`, `adaptation_midpoint`, `adaptation_end`, `employee_stage`, `candidate_work_stage`, `salary_expectation`, `personal_data_consent`, `employee_data_consent`, `is_bot_blocked`, `test_task_due_at`, `notes` | Employee detail payload | Обновляет `employees`, sync messenger identity и legacy manager/mentor chat ids из выбранных staff relations | `401`, `404`, `409` при messenger identity conflict, `400` при invalid staff relation/date |
| `POST` | `/api/employees/{employee_id}/bot-message` | Отправить ручное Telegram-сообщение прямо из карточки сотрудника и записать audit history. | JSON: `text` | Employee detail payload | Пишет строку в `employee_manual_bot_messages` со статусом `sent` или `failed`, отправляет текст в Telegram через primary chat id сотрудника | `401`, `404`, `400` при пустом тексте/отсутствии chat id/token/ошибке Telegram, `409` если `is_bot_blocked=true` |
| `POST` | `/api/employees/{employee_id}/promote-to-adaptation` | Явно перевести кандидата в адаптацию через HR-действие. | Path: `employee_id` | Employee detail payload | Меняет `employee_stage` c `candidate` на `adaptation`, очищает `candidate_work_stage`, seed-ит `adaptation_midpoint` / `adaptation_end` от `first_workday`, сбрасывает `current_menu_set_id` | `401`, `404`, `400` если employee не candidate или не указан `first_workday` |
| `POST` | `/api/employees/{employee_id}/document-links` | Создать или обновить offer link сотрудника. | JSON: `url` | `{ item, payload }`, где `payload` — employee detail payload | Создает или обновляет `employee_document_links` с title `Оффер` | `401`, `404`, `400` если URL пустой |
| `DELETE` | `/api/employees/{employee_id}/document-links/{link_id}` | Удалить offer link entry. | Path: `employee_id`, `link_id` | Employee detail payload | Удаляет одну строку `employee_document_links` | `401`, `404` |
| `POST` | `/api/employees/{employee_id}/schedule` | Поставить будущий запуск сценария в очередь. | JSON: `flow_key`, `requested_at` в формате `%Y-%m-%dT%H:%M` | Employee detail payload | Создает `flow_launch_requests` с `launch_type="scheduled"` | `401`, `404`, `400` если bot blocked, scenario missing, role mismatch, missing/invalid datetime |
| `DELETE` | `/api/employees/{employee_id}/schedule/{launch_request_id}` | Удалить pending scheduled launch. | Path: `employee_id`, `launch_request_id` | Employee detail payload | Удаляет одну scheduled `flow_launch_requests` строку | `401`, `404` |
| `POST` | `/api/employees/{employee_id}/launch` | Запустить сценарий сразу. | JSON: `flow_key` | Employee detail payload | Отправляет первый шаг сценария, пишет processed manual `flow_launch_requests`, может создать pending manual request для продолжения шагов | `401`, `404`, `400` если bot blocked, no chat id, non-numeric chat id, missing token, no steps, Telegram send failure |
| `POST` | `/api/employees/{employee_id}/files` | Загрузить outbound HR-файл для сотрудника. | Multipart: `upload`, optional `category`, optional `send_to_channel=true|false` | Employee detail payload | Пишет файл в storage, создает `employee_files`, может сразу отправить файл в Telegram | `401`, `404` |
| `POST` | `/api/employees/{employee_id}/files/{file_id}/send` | Отправить существующий stored file в канал сотрудника. | Path: `employee_id`, `file_id` | Employee detail payload | Отправляет файл в Telegram, если file path существует | `401`, `404`, `400` если нет configured channel или bot token |
| `DELETE` | `/api/employees/{employee_id}` | Удалить карточку сотрудника или кандидата. | Path: `employee_id` | `{ "redirect_url": "/employees" | "/candidates" }` | Удаляет employee row, files, offer links и employee storage directory | `401`, `404` |
| `POST` | `/api/employees/{employee_id}/bot-link/reset` | Сбросить Telegram/runtime-привязку карточки для повторного тестового linking. | Path: `employee_id` | Employee detail payload | Очищает Telegram identity/menu/progress и pending launch requests для карточки | `401`, `404` |
| `POST` | `/api/employees/{employee_id}/document-slots/offer/file` | Загрузить file-backed offer slot. | Multipart: `upload`, optional title/category | Employee detail payload | Создает `employee_files` и `employee_document_links` со `slot_key=offer`, `item_kind=file` | `401`, `404`, `400` |

## API scenario/survey workspace

Один workspace API обслуживает сценарии и опросы. Default режим — `kind=scenario`; режим опросов включается через `kind=survey`. Отдельного `/api/surveys/*` workspace API нет, чтобы не дублировать контракт редактора поверх тех же `scenario_templates` и `flow_step_templates`.

| Method | Path | Назначение | Основные inputs | Response | Side effects | Частые errors |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/flows/workspace` | Вернуть sidebar сценариев/опросов и payload выбранного item. | Optional query: `scenario_id`, `kind=scenario\|survey` | Workspace payload with `kind`, `item_label`, `scenarios[]`, optional `workspace` | Нет | `401` |
| `POST` | `/api/flows/workspace/scenarios` | Создать новый scenario/survey shell. | JSON: optional `title`, optional `description`, optional `kind=scenario\|survey` | `{ message, scenario_id, payload }` | Inserts `scenario_templates` через direct SQL и current schema introspection | `401`, `409`, `500` если DB содержит required unsupported columns |
| `POST` | `/api/flows/workspace/scenarios/{scenario_id}/settings` | Обновить item-level metadata. | JSON: `description`, `role_scope`, `employee_scope`, `recipient_mode`, `trigger_mode`, `target_employee_id` | `{ message, payload }` | Обновляет одну строку `scenario_templates`; `recipient_mode` управляет адресатом runtime-шага, а progress все равно остается на context employee | `401`, `404` |
| `POST` | `/api/flows/workspace/scenarios/reorder` | Сохранить sidebar order сценариев/опросов. | JSON: `scenario_ids[]`, optional `kind=scenario\|survey` | `{ message, payload }` | Перезаписывает `sort_order` выбранных items внутри kind | `401`, `400` если список пустой |
| `POST` | `/api/flows/workspace/scenarios/bulk-copy` | Скопировать один или несколько scenarios/surveys. | JSON: `scenario_ids[]`, optional `kind=scenario\|survey` | `{ message, payload }` | Дублирует items и step trees внутри kind | `401`, `400`, `404` |
| `POST` | `/api/flows/workspace/scenarios/bulk-delete` | Удалить один или несколько scenarios/surveys. | JSON: `scenario_ids[]`, optional `kind=scenario\|survey` | `{ message, payload }` | Удаляет items и dependent step trees внутри kind | `401`, `400`, `404` |
| `POST` | `/api/flows/workspace/steps/{step_id}` | Обновить один workspace node. | JSON fields: `title`, `text`, `response_type`, `button_options`, `send_mode`, `send_time`, `target_field`, `launch_scenario_key`, `send_employee_card`, `notify_on_send_text`, `notify_on_send_recipient_ids`, `notify_on_send_recipient_scope`, `step_send_notifications[]`, `button_notifications[]`; для notification recipients supported tokens only: `hr`, `manager`, `mentor_adaptation`, `mentor_ipr` | `{ message, payload, step_id }` | Обновляет одну `flow_step_templates` строку и related notification fields; новые сохранения нормализуют recipients в role-only contract, legacy `employee:{id}` допускается только как runtime fallback для старых DB rows | `401`, `404` |
| `POST` | `/api/flows/workspace/scenarios/{scenario_id}/steps` | Создать новый root step. | JSON: optional `title` | `{ message, payload, step_id }` | Inserts root `flow_step_templates` row | `401`, `404` |
| `POST` | `/api/flows/workspace/scenarios/{scenario_id}/steps/reorder` | Сохранить root-step order. | JSON: `step_ids[]` | `{ message, payload }` | Перезаписывает `sort_order` root steps | `401`, `404`, `400` |
| `POST` | `/api/flows/workspace/steps/{step_id}/branches` | Создать branch step для branching node. | JSON: `option_index` | `{ message, payload, step_id }` | Inserts branch child step, если его еще нет | `401`, `404`, `400` если parent не branching или option invalid |
| `POST` | `/api/flows/workspace/steps/{step_id}/chain` | Создать chain step под branch node с response type `chain`. | JSON: optional `title` | `{ message, payload, step_id }` | Inserts chain child step | `401`, `404`, `400` если parent не chain-capable branch node |
| `POST` | `/api/flows/workspace/steps/{step_id}/delete` | Удалить step subtree. | Path: `step_id` | `{ message, payload, deleted_kind }` | Удаляет выбранный step и descendants | `401`, `404` |
| `POST` | `/api/flows/workspace/steps/{step_id}/attachment` | Загрузить file attachment для step. | Multipart: `upload` | `{ message, payload, step_id }` | Сохраняет attachment на диск и обновляет `attachment_path` / `attachment_filename` | `401`, `404` |
| `POST` | `/api/flows/workspace/steps/{step_id}/attachment/delete` | Удалить step attachment. | Path: `step_id` | `{ message, payload, step_id }` | Удаляет attachment file и очищает attachment fields | `401`, `404` |

## API settings workspace

Этот API добавлен для React settings page и пока живет рядом с classic `/settings` form routes.

| Method | Path | Назначение | Основные inputs | Response | Side effects | Частые errors |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/settings/workspace` | Вернуть HR settings, menu sets/buttons, scenarios и admin accounts для React settings. | Нет | Settings workspace payload | Создает default `hr_settings` row, если его нет | `401` |
| `POST` | `/api/settings/hr` | Обновить HR notification settings. | JSON: `hr_name`, `telegram_user_id`, `notification_recipient_ids`, `default_menu_set_id`, notification booleans | Settings workspace payload | Обновляет `hr_settings` | `401` |
| `POST` | `/api/settings/menu-sets` | Создать menu set. | JSON: `title`, optional `description` | Settings workspace payload | Создает `bot_menu_sets` | `401` |
| `POST` | `/api/settings/menu-sets/{menu_set_id}` | Обновить menu set. | JSON: `title`, `description` | Settings workspace payload | Обновляет `bot_menu_sets` | `401`, `404` |
| `DELETE` | `/api/settings/menu-sets/{menu_set_id}` | Удалить menu set. | Path: `menu_set_id` | Settings workspace payload | Удаляет buttons внутри set, отвязывает переходы на set, очищает `employees.current_menu_set_id` и default menu setting | `401`, `404` |
| `POST` | `/api/settings/menu-sets/{menu_set_id}/buttons` | Создать menu button. | JSON: `label`, `action_type`, optional `scenario_key`, optional `target_menu_set_id` | Settings workspace payload | Создает `bot_menu_buttons` | `401`, `404` |
| `POST` | `/api/settings/menu-buttons/{button_id}` | Обновить menu button. | JSON: `label`, `action_type`, optional `scenario_key`, optional `target_menu_set_id` | Settings workspace payload | Обновляет `bot_menu_buttons` | `401`, `404` |
| `POST` | `/api/settings/menu-buttons/bulk` | Bulk update menu buttons. | JSON: `buttons[]` с `id`, `label`, `action_type`, `scenario_key`, `target_menu_set_id` | Settings workspace payload | Обновляет несколько `bot_menu_buttons` | `401` |
| `DELETE` | `/api/settings/menu-buttons/{button_id}` | Удалить menu button. | Path: `button_id` | Settings workspace payload | Удаляет одну `bot_menu_buttons` строку | `401`, `404` |
| `POST` | `/api/settings/bot-menu/broadcast` | Переотправить главное меню всем связанным незаблокированным пользователям. | Нет | `{ workspace, refreshed_count }` | Отправляет Telegram menu через bot messenger | `401`, `400` если bot token не настроен |
| `GET` | `/api/settings/positions` | Вернуть каталог должностей. | Нет | `{ positions[] }` | Нет | `401` |
| `POST` | `/api/settings/positions` | Создать должность. | JSON: `title`, optional `slug`, `is_active`, `sort_order` | `{ positions[] }` | Создает или активирует position row | `401`, `400`, `409` |
| `POST` | `/api/settings/positions/{position_id}` | Обновить должность. | Path: `position_id`; JSON: `title`, `is_active`, `sort_order` | `{ positions[] }` | Обновляет position row | `401`, `404`, `409` |
| `PATCH` | `/api/settings/positions/{position_id}` | Частично обновить должность. | Path: `position_id`; JSON subset fields | `{ positions[] }` | Обновляет position row | `401`, `404`, `409` |
| `DELETE` | `/api/settings/positions/{position_id}` | Деактивировать должность. | Path: `position_id` | `{ positions[] }` | Ставит `is_active=false`, физически не удаляет row | `401`, `404` |

## Scenario recipient contract

- `scenario_templates.recipient_mode` определяет, кто получает шаги runtime:
  - `self` — сам context employee;
  - `manager` — `manager_employee_id`;
  - `mentor_adaptation` — `mentor_adaptation_employee_id`;
  - `mentor_ipr` — `mentor_ipr_employee_id`;
  - `hr` — `HrSettings.telegram_user_id`.
- `context employee` не меняется:
  - launch request, progress, survey answers, employee field updates и message templating продолжают работать по `ScenarioProgress.employee_id`.
- `recipient employee` меняется:
  - runtime отправляет шаги по resolved recipient chat id;
  - `scenario_progress` хранит `recipient_mode`, `recipient_employee_id`, `recipient_chat_id`, чтобы reply-flow шел по адресату, а не по subject employee.
- Failure behavior не silent:
  - если related recipient не назначен или у него нет Telegram binding, шаг не отправляется;
  - `scenario_progress.last_delivery_error` получает причину, а worker/web logs пишут warning.
- Ограничение для `hr`:
  - send-only шаги поддерживаются через `HrSettings.telegram_user_id`;
  - interactive шаги требуют, чтобы этот Telegram уже был связан с `Employee`, иначе runtime фиксирует delivery error и не уходит в “ожидание ответа в пустоту”.
- Специальный compatibility rule:
  - `trigger_mode=manager_assigned_adaptation` при старом `recipient_mode=self` runtime трактует как `manager`, чтобы старые trigger-сценарии не продолжали ошибочно писать самому адаптируемому сотруднику.

## API shared documents workspace

Этот API обслуживает `/app/documents`: общую библиотеку документов и ссылок, которые можно отправлять через bot menu action `send_document`.

| Method | Path | Назначение | Основные inputs | Response | Side effects | Частые errors |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/documents/workspace` | Вернуть shared document library payload. | Нет | Documents workspace payload | Нет | `401` |
| `POST` | `/api/documents/links` | Создать shared link document. | JSON: `title`, `external_url`, optional `description`, `category`, `is_active` | Documents workspace payload | Создает `document_library_items` с `item_kind=link` | `401`, `400` |
| `POST` | `/api/documents/files` | Загрузить shared file document. | Multipart: `upload`, optional `title`, `description`, `category`, `is_active` | Documents workspace payload | Пишет файл в `storage/document_library`, создает `document_library_items` с `item_kind=file` | `401`, `400` |
| `POST` | `/api/documents/{item_id}` | Обновить metadata shared document. | JSON: `title`, `item_kind`, `external_url`, `description`, `category`, `is_active` | Documents workspace payload | Обновляет `document_library_items`; при переводе file -> link удаляет stored file | `401`, `404`, `400` |
| `DELETE` | `/api/documents/{item_id}` | Удалить shared document. | Path: `item_id` | Documents workspace payload | Удаляет row и stored file, если item был file-backed | `401`, `404` |
| `POST` | `/api/documents/menu-scaffold` | Создать или пересобрать document menu branch из категорий. | JSON: optional `root_title`, `mode=create|rebuild` | `{ workspace, created_root_menu_set_id, created_root_menu_title, bot_menu_url }` | Создает/пересобирает generated `bot_menu_sets` с `system_tag` и `send_document` buttons | `401`, `400` |

## API admin accounts

Routes ниже требуют role `admin`.

| Method | Path | Назначение | Основные inputs | Response | Side effects | Частые errors |
| --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/api/accounts` | Создать admin account. | JSON: `login`, `password`, `role`, `is_active` | Settings workspace payload | Создает `admin_accounts` с password hash | `401`, `403`, `400`, `409` |
| `POST` | `/api/accounts/{account_id}` | Обновить admin account. | JSON: `login`, optional `password`, `role`, `is_active` | Settings workspace payload | Обновляет login/role/is_active и password hash, если пароль передан | `401`, `403`, `404`, `409` |
| `DELETE` | `/api/accounts/{account_id}` | Удалить admin account. | Path: `account_id` | Settings workspace payload | Удаляет account, кроме текущего пользователя | `401`, `403`, `400`, `404` |

## API bulk actions workspace

Этот API добавлен для React bulk actions page. Classic `/bulk-actions` form routes пока сохранены как fallback.

Immediate endpoints требуют `confirmed=true`; без него возвращают `400`, чтобы React не мог случайно отправить массовое действие без явного подтверждения оператора.

| Method | Path | Назначение | Основные inputs | Response | Side effects | Частые errors |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/bulk-actions/workspace` | Вернуть сценарии, опросы, target options, scheduled actions и history. | Нет | Bulk actions workspace payload | Нет | `401` |
| `POST` | `/api/bulk-actions/preview` | Посчитать получателей для выбранной аудитории. | JSON target fields: `target_role_scope`, `target_employee_id`, `target_employee_stages[]`, `target_candidate_stages[]` | `{ recipient_count, recipient_scope }` | Нет | `401` |
| `POST` | `/api/bulk-actions/scenarios/schedule` | Запланировать массовый запуск сценария. | JSON: `flow_key`, `requested_at`, target fields | `{ message, payload }` | Создает `mass_scenario_actions` scheduled row | `401`, `400`, `404` |
| `POST` | `/api/bulk-actions/scenarios/launch` | Немедленно запустить сценарий. | JSON: `flow_key`, target fields, `confirmed=true` | `{ message, payload }` | Отправляет сценарий через Telegram messenger, пишет manual `mass_scenario_actions` row | `401`, `400`, `404` |
| `POST` | `/api/bulk-actions/surveys/schedule` | Запланировать массовый запуск опроса. | JSON: `flow_key`, `requested_at`, target fields | `{ message, payload }` | Создает `mass_scenario_actions` scheduled row с `scenario_kind="survey"` | `401`, `400`, `404` |
| `POST` | `/api/bulk-actions/surveys/launch` | Немедленно запустить опрос. | JSON: `flow_key`, target fields, `confirmed=true` | `{ message, payload }` | Отправляет опрос через Telegram messenger, пишет manual `mass_scenario_actions` row | `401`, `400`, `404` |
| `POST` | `/api/bulk-actions/messages/schedule` | Запланировать массовое сообщение. | JSON: `message_text`, `requested_at`, target fields | `{ message, payload }` | Создает `mass_message_actions` scheduled row | `401`, `400` |
| `POST` | `/api/bulk-actions/messages/send` | Немедленно отправить массовое сообщение. | JSON: `message_text`, target fields, `confirmed=true` | `{ message, payload }` | Отправляет Telegram messages, пишет manual `mass_message_actions` row | `401`, `400` |
| `DELETE` | `/api/bulk-actions/scenarios/{action_id}` | Удалить scheduled scenario/survey action. | Path: `action_id` | `{ message, payload }` | Удаляет pending `mass_scenario_actions` row | `401`, `404` |
| `DELETE` | `/api/bulk-actions/surveys/{action_id}` | Удалить scheduled survey action. | Path: `action_id` | `{ message, payload }` | Удаляет pending `mass_scenario_actions` row с `scenario_kind="survey"` | `401`, `404` |
| `DELETE` | `/api/bulk-actions/messages/{action_id}` | Удалить scheduled message action. | Path: `action_id` | `{ message, payload }` | Удаляет pending `mass_message_actions` row | `401`, `404` |

## Важные поведенческие заметки

- `POST /api/employees` автоматически ставит `recruitment_hiring` в очередь для каждой созданной записи. Это implementation choice, а не generic employee-create primitive.
- `POST /api/employees/{employee_id}` работает по-разному для candidates и non-candidates:
  - candidates обновляют `candidate_work_stage`, `personal_data_consent`, `test_task_due_at`;
  - employees обновляют `birth_date`, work contact fields, manager/mentor chat ids, `employee_stage`, `employee_data_consent`.
- Date parsing errors в create/update employee не нормализованы в friendly `400`. Сейчас это code smell, не осознанный API contract.
- Workspace scenario creation зависит от schema shape. Endpoint introspects SQLite columns перед insert, поэтому поведение API зависит от live table shape.
- Settings JSON API сохраняет поведение classic form routes и возвращает full workspace payload после mutations, чтобы React page мог перерисоваться без отдельного refetch.
- Bulk actions JSON API намеренно строже classic form routes для immediate side effects: React должен сначала вызвать preview и отправить `confirmed=true`.
