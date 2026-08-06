---
title: Архитектура HR Bot
date: 2026-05-14
status: active
doc_type: architecture
area: core
task_tokens:
  - HRB-DOC-02
  - HRB-P1-07
related:
  - "[[api]]"
  - "[[web-surface]]"
  - "[[data-model]]"
  - "[[lld/classic-to-react-admin-migration]]"
source_of_truth: true
---

# Архитектура

## Обзор

HR Bot — приложение в одном репозитории с несколькими runtime-поверхностями:

- FastAPI-админка для HR-операторов;
- React/Vite-экраны админки, которые открываются через FastAPI;
- Telegram-бот на Aiogram long polling;
- APScheduler внутри процесса Telegram worker;
- SQLite-база и локальное файловое хранилище.

Этот файл фиксирует верхнеуровневую топологию. Детальные контракты вынесены отдельно:

- [[api]]
- [[web-surface]]
- [[data-model]]
- [[stage-deploy]]
- [[configuration]]

## Runtime-топология

### FastAPI-админка

- Точка входа: `app.main:app`
- Отвечает за:
  - сессионную авторизацию админки;
  - классические HTML-страницы и form actions;
  - JSON API для React-списка сотрудников и конструктора сценариев;
  - загрузку и скачивание файлов;
  - сценарии, опросы, настройки и массовые действия для операторов.
- Важное текущее ограничение:
  - `app/main.py` уже сжат до composition-root уровня и в основном держит startup, middleware, login/session pages и `include_router(...)`;
  - но classic fallback surfaces еще живы как продуктовые/операционные хвосты, поэтому следующий риск теперь не в монолите `main.py`, а в решении, какие legacy pages действительно можно удалять без rollback gap.

### React-экраны админки

- Исходники: `frontend/`
- Собранные ассеты отдаются из `app/static/workspace_v2/`
- Текущие страницы:
  - `/app/dashboard`
  - `/app/employees`
  - `/app/employees?list_kind=candidates`
  - `/app/employees/{employee_id}`
  - `/app/flows/workspace-v2`
  - `/app/surveys/workspace`
  - `/app/bot-menu`
  - `/app/documents`
  - `/app/settings`
  - `/app/bulk-actions`
- Default entry для авторизованного оператора сейчас ведет на `/app/dashboard`; бренд в sidebar тоже ведет на dashboard, без отдельного пункта “Главная” в primary nav.
- React templates больше не обязаны наследовать legacy `base.html`: для React surfaces введен отдельный `react_base.html` с `app/static/react_shell.css` и общим Vite `app.css`, чтобы shell/layout не зависел от classic `app/static/styles.css`.
- Граница ответственности:
  - React отвечает за клиентский рендеринг и локальное состояние;
  - FastAPI остается владельцем авторизации, хранения и всех write-операций.
- Правило для новых React-страниц:
  - `main.tsx` только bootstrap и mount;
  - экран живет в `page.tsx` или `screen.tsx`;
  - крупные page-only блоки выносятся в локальный `components/`;
  - статические схемы и конфиг не держатся в entrypoint, а уходят в `data.ts` или `config.ts`.

### Telegram worker

- Точка входа: `app.bot_runner`
- Отвечает за:
  - `/start` и привязку Telegram-чата к сотруднику;
  - входящий текст, документы и фото;
  - callback-кнопки для ветвлений сценариев;
  - меню через messaging abstraction.
- Важная текущая модель меню:
  - бот больше не держится только за `current_menu_set_id` и global default;
  - `BotMenuSet` теперь проходит audience-check по `employee_scope`, `role_scope` и explicit `target_employee_ids`;
  - если текущий набор перестал подходить сотруднику, runtime сам выбирает следующий совместимый набор;
  - `open_set` не дает открыть меню, которое не подходит пользователю по audience contract.

### Scheduler loop

- Основной модуль: `app.scheduler`
- Где работает: в том же процессе, что и Telegram-бот
- Отвечает за:
  - скан pending `flow_launch_requests`;
  - планирование шагов сценариев по датам;
  - обработку scheduled mass actions;
  - запуск onboarding/probation-сценариев по metadata сценариев.

### Хранилище

- Реляционное состояние: SQLite через SQLAlchemy.
- Файлы:
  - файлы сотрудников в `FILE_STORAGE_DIR`;
  - вложения шагов сценариев в `storage/scenario_step_files/`;
  - shared document library files в `storage/document_library/`;
  - фото профиля в `storage/profile_photos/`.
- Важное ограничение:
  - в проекте есть SQLAlchemy-модели, но нет нормального migration workflow;
  - startup-код в `app.database._ensure_sqlite_schema()` изменяет SQLite-схему на месте.

## Границы подсистем

### HTML и классическая админка

- Модель доступа: browser session cookie, redirect на `/login` без авторизации.
- Потребители: HR-операторы.
- Контракт: server-rendered HTML, form posts и redirects.
- Подробная карта: [[web-surface]]

### Web support layer

- Модуль: `app/web/support.py`
- Отвечает за:
  - template rendering wrapper с общим `request/current_user/role_labels` контекстом;
  - login redirect helper;
  - auth/admin guards для HTML и JSON surfaces.
- Этот слой был первым безопасным seam для последующего выноса `employees`, `bulk-actions`, `settings` и `scenario/surveys` из `app/main.py`; сейчас это уже не план, а факт, на котором держится новый composition root.

### Auth и роли админки

- Модель входа: `/login` проверяет `admin_accounts.login/password_hash` и ставит подписанную cookie `hr_admin_auth`.
- Cookie содержит signed session token `account_id.issued_at.signature`; middleware принимает только валидную HMAC-подпись через `ADMIN_SESSION_SECRET`, проверяет TTL и заново читает active account из БД.
- Текущие роли: `admin` и `hr`.
- Seed defaults: `DEFAULT_ADMIN_LOGIN/DEFAULT_ADMIN_PASSWORD` и `DEFAULT_HR_LOGIN/DEFAULT_HR_PASSWORD` создают или нормализуют две базовые записи.
- Реальная граница прав сейчас узкая:
  - любая авторизованная роль получает доступ к основным operator surfaces и JSON API;
  - `admin` дополнительно видит список аккаунтов и может создавать, менять, отключать и удалять accounts;
  - `hr` не видит account management payload и получает `403` на `/api/accounts*`.
- Ограничение текущей модели: роль `admin` смешивает operational-доступ директора с техническим управлением доступами. Для продукта это слабая граница, если директору нужно только подменять HR на время отсутствия.
- Оставшийся риск hardening: browser session все еще stateless и не имеет server-side revoke list; отключение account блокирует следующий request, но отдельного audit/session management слоя пока нет.

### Employee support layer

- Модуль: `app/web/employees.py`
- Сейчас отвечает за:
  - employee list/detail serialization;
  - employee identity error formatting;
  - employee create/update/delete/schedule/send helper logic;
  - employee-stage dictionaries и related labels.
- Важная граница:
  - helper-слой больше не живет рядом с route handlers в `app/main.py`;
  - employee-specific logic собрана в support module, а route ownership вынесен в `app/web/employee_routes.py`.

### Employee route layer

- Модуль: `app/web/employee_routes.py`
- Отвечает за:
  - `/candidates` и `/employees` redirect entrypoints;
  - `/app/employees` и `/app/employees/{employee_id}` React bootstrap routes;
  - `/api/employees*` JSON API для employee list/detail/files/document-links/launch scheduling;
  - classic employee edit/file/document/profile-photo routes.
- Это первый полноценный vertical route slice, вынесенный из `app/main.py` через `APIRouter`.
- Employee detail contract:
  - руководитель, наставник адаптации и наставник ИПР хранятся как связи на других сотрудников (`*_employee_id`), а не как сырой ввод `telegram_id`;
  - для runtime-совместимости карточка по-прежнему синхронизирует legacy `*_telegram_id`, но они больше не являются операторским source of truth;
  - `mid_probation` и `end_probation` сценарные триггеры теперь сначала смотрят в явные поля `adaptation_midpoint` и `adaptation_end`, и только потом fallback-ятся к расчету от `first_workday`.
  - переход `candidate -> adaptation` пока не автоматизирован по Telegram-ответу; вместо этого есть явный HR cutover endpoint `/api/employees/{employee_id}/promote-to-adaptation`, который требует `first_workday`, очищает candidate-only stage и seed-ит adaptation dates.

### Dashboard support layer

- Модуль: `app/web/dashboard.py`
- Отвечает за read-only operational dashboard payload:
  - ближайшие individual и mass scheduled actions;
  - свежие Telegram-привязки кандидатов;
  - входящие файлы сотрудников/кандидатов;
  - attention items для записей без канала, просроченных тестовых и blocked bot state;
  - module links для существующих operator surfaces.

### Dashboard route layer

- Модуль: `app/web/dashboard_routes.py`
- Отвечает за:
  - `/app/dashboard` React bootstrap route;
  - `/api/dashboard/workspace` JSON API для оперативной главной.
- Важная граница:
  - dashboard не выполняет write/destructive actions;
  - подробные операции остаются в employee detail, bulk actions, scenario/survey workspace и settings.

### Bulk actions support layer

- Модуль: `app/web/bulk_actions.py`
- Отвечает за:
  - target scope resolution и human-readable recipient labels;
  - bulk workspace payload serialization;
  - preview/schedule/launch helper logic для React/API слоя;
  - shared helpers, которые еще нужны classic bulk form routes.

### Bulk actions route layer

- Модуль: `app/web/bulk_action_routes.py`
- Отвечает за:
  - `/bulk-actions` redirect entrypoint;
  - `/app/bulk-actions` React bootstrap route;
  - `/api/bulk-actions*` JSON API для preview/schedule/launch/delete;
  - classic bulk form routes для schedule/launch/send/delete.
- Важная граница:
  - `bulk-actions` уже отделен и на React/API surface, и на classic operator form surface;
  - remaining cleanup теперь не внутри bulk, а в settings и old scenario/survey editor tails.

### Settings support layer

- Модуль: `app/web/settings.py`
- Отвечает за:
  - HR settings serialization и bootstrap;
  - menu sets/buttons serialization и payload application;
  - audience targeting для menu sets: аудитория, роль и explicit список сотрудников/кандидатов;
  - settings workspace payload для React surface;
  - shared helpers, которые еще нужны classic settings form routes.

### Settings route layer

- Модуль: `app/web/settings_routes.py`
- Отвечает за:
  - `/settings` redirect entrypoint;
  - `/app/settings` React bootstrap route;
  - `/bot-menu` redirect entrypoint;
  - `/app/bot-menu` React bootstrap route;
  - `/api/settings*` и `/api/accounts*` JSON API;
  - classic settings/account form routes.
- Важная граница:
  - `settings` уже отделен и на React/API surface, и на classic operator form surface;
  - `/app/settings` больше не является владельцем menu-set редактора: системные HR/account settings и bot-menu configuration теперь разнесены по разным React surfaces;
  - remaining cleanup теперь не внутри settings, а в old scenario/survey editor tails и в cleanup duplicated helpers между `settings` и `bot-menu`.

### Shared documents support layer

- Модуль: `app/web/documents.py`
- Отвечает за:
  - serialization общей библиотеки документов;
  - нормализацию `file | link` contract;
  - delete-helper для shared stored files;
  - document options для привязки к `bot-menu`.
- Важная граница:
  - `DocumentLibraryItem` не является employee-specific файлом и не должен смешиваться с `employee_files`;
  - это общий каталог материалов для menu/runtime, а не вложение карточки сотрудника.

### Shared documents route layer

- Модуль: `app/web/document_routes.py`
- Отвечает за:
  - `/documents` redirect entrypoint;
  - `/app/documents` React bootstrap route;
  - `/api/documents/workspace`, создание shared links/files, update/delete;
  - `/api/documents/menu-scaffold` для автоматической сборки и controlled rebuild `menu sets` из категорий документов;
  - authenticated download route `/documents/{id}/download`.
- Важная граница:
  - bot menu не хранит raw file paths или URLs в кнопках;
  - `BotMenuButton` с `action_type=send_document` ссылается на `DocumentLibraryItem`, а не дублирует document payload внутри menu button.
  - category navigation для документов не реализуется как special runtime mode; scaffold создает обычные `open_set`/`send_document` menu sets поверх уже существующей архитектуры меню.
  - generated document-menu ветки маркируются `BotMenuSet.system_tag`, чтобы rebuild обновлял только их и не затрагивал ручные menu sets.

### Scenario workspace support layer

- Модуль: `app/web/scenarios.py`
- Отвечает за:
  - workspace payload serialization для scenario/survey React surfaces;
  - step tree helpers, branch/chain serialization и response labels;
  - notification rules для кнопок и для отправки самого шага;
  - attachment helpers для step files;
  - template copy/delete helpers, которые уже нужны и React/API workspace, и remaining classic editor tails.
- Важная текущая граница:
  - button notifications живут в `StepButtonNotification`;
  - step-level notifications больше не должны держаться только на legacy `notify_on_send_*` полях и вынесены в `StepSendNotification`;
  - legacy `notify_on_send_*` остаются compatibility seam, чтобы classic fallback и старые payloads не ломались мгновенно, но source of truth для новых множественных правил уже отдельная таблица.
  - scenario metadata теперь несет еще и `recipient_mode`: workspace описывает не только “по какой карточке идет процесс”, но и “кому бот доставляет шаги”.
  - survey flow поверх тех же `FlowStepTemplate` теперь принудительно нормализуется иначе, чем scenario flow: вопрос сохраняется как единый `title/text`, ответ считается текстовым по умолчанию, optional `button_options` работают как готовые варианты текстового ответа без branching, а `send_mode`, `launch_scenario`, `target_field` и step notifications для survey-step не являются допустимой конфигурацией.

### Scenario workspace route layer

- Модуль: `app/web/scenario_routes.py`
- Отвечает за:
  - `/flows` и `/surveys` redirect entrypoints;
  - `/app/flows/workspace-v2`, `/app/surveys/workspace` и legacy redirect `/app/flows/workspace`;
  - `/api/flows/workspace*` JSON API для React scenario/survey workspace.
- Важная граница:
  - один и тот же route module теперь владеет и React/API workspace surface, и classic scenario/survey editor tails;
  - следующий cleanup уже не про перенос ownership, а про осознанное удаление или сохранение fallback surfaces.

### JSON API

- Prefix: `/api/*`
- Модель доступа: browser session cookie, `401` без авторизации.
- Потребители:
  - React operational dashboard;
  - React-список и карточка сотрудников;
  - React-конструктор сценариев.
- Контракт: JSON payloads и несколько multipart upload endpoints.
- Подробный контракт: [[api]]

### Bot ingress

- Транспорт: Telegram long polling.
- Входы:
  - `/start`;
  - обычный текст;
  - документы;
  - фото;
  - callback-кнопки.
- Побочные эффекты:
  - синхронизация identity сотрудника;
  - сохранение файлов;
  - обновление scenario progress.

### Scheduled jobs

- Модель запуска:
  - interval scan в worker;
  - delayed per-step jobs в APScheduler.
- Записи:
  - `flow_launch_requests`;
  - `scenario_progress`;
  - `mass_*_actions`;
  - `onboarding_events`.

## Основные потоки данных

### Редактирование карточки сотрудника

1. HR открывает классическую форму или React-экран сотрудника.
2. FastAPI читает и пишет общий `employees` record, связанные файлы, ссылки и messenger identity rows.
3. Telegram identity helpers синхронизируют `employee_messenger_accounts` с legacy Telegram-полями в `employees`.

### Редактирование сценариев

1. HR редактирует сценарии в классическом интерфейсе или React workspace.
2. FastAPI сохраняет `scenario_templates`, `flow_step_templates` и `step_button_notifications`.
3. Для button-step notifications модель больше не однослотовая: одна кнопка может иметь несколько rules, различаемых по `rule_index`.
4. React workspace хранит explicit recipients как `employee:{id}` tokens, а runtime уже резолвит их в реальные chat ids при отправке уведомлений.
5. Бот и scheduler читают эти таблицы напрямую в runtime.

### Выполнение сценария

1. Сценарий стартует вручную, через scheduled launch request или через trigger mode, который обрабатывает scheduler.
2. Engine держит два слоя адресации:
   - `context employee`/subject employee — по кому идет процесс и чьими данными рендерится сообщение;
   - `recipient employee` — кто реально получает шаг в Telegram по `recipient_mode`.
3. Engine отправляет текущий шаг, вложения, опциональную карточку сотрудника и опциональные уведомления уже по resolved recipient.
4. Ответы пользователя продолжают один и тот же `scenario_progress`, даже если отвечает руководитель или наставник, а обновляются данные именно context employee.
5. Если recipient не назначен или не привязан к Telegram, runtime не шлет шаг молча в пустоту: progress получает `last_delivery_error`, а worker пишет warning в logs.

### Массовая коммуникация

1. HR создает mass scenario action или mass message action.
2. Scheduler определяет получателей по stage и role filters.
3. Каждый подходящий сотрудник получает сценарий или сообщение через messaging layer.

## Текущие ограничения и риски

- Классическая и React-админка живут параллельно. Это сохраняет рабочий fallback, но повышает риск расхождения поведения.
- Часть React-экранов уже перегружена в большие page-файлы. `employee detail` больше не живет в отдельном legacy JS/CSS runtime и уже разрезан на bootstrap/page/sections/helpers внутри Vite-стека, а React shell отделен от classic `styles.css`. Следующий риск теперь не packaging, а visual/API drift между новыми React surfaces, shared wrappers и еще живыми classic fallback routes.
- Candidate и employee lifecycle используют одну таблицу `employees`. Это упрощает код, но ослабляет продуктовую модель и targeting semantics.
- Schema evolution хрупкая. `_ensure_sqlite_schema()` помогает переживать старые SQLite-файлы, но также означает, что production schema может меняться при startup без migration history.
- Referential integrity в основном application-level. Большинство связей хранится integer-полями без явных foreign keys.
- Stage deploy truth разделен между repo-backed workflows и server-side systemd config вне git. См. [[stage-deploy]].
