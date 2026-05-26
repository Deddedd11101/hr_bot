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
  - `app/main.py` все еще совмещает composition root и часть classic route tails;
  - но React/API slices уже начали выноситься в `app/web/*`, поэтому основной remaining risk теперь не в workspace routes, а в legacy form/editor flows.

### React-экраны админки

- Исходники: `frontend/`
- Собранные ассеты отдаются из `app/static/workspace_v2/`
- Текущие страницы:
  - `/app/employees`
  - `/app/employees?list_kind=candidates`
  - `/app/employees/{employee_id}`
  - `/app/flows/workspace-v2`
  - `/app/surveys/workspace`
  - `/app/settings`
  - `/app/bulk-actions`
- Default entry для авторизованного оператора сейчас ведет на React candidate list; classic `/employees` и `/candidates` сохранены как direct fallback routes.
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
- Это не финальная router decomposition, а первый безопасный seam для последующего выноса `employees`, `bulk-actions`, `settings` и `scenario/surveys` из `app/main.py`.

### Employee support layer

- Модуль: `app/web/employees.py`
- Сейчас отвечает за:
  - employee list/detail serialization;
  - employee identity error formatting;
  - employee create/update/delete/schedule/send helper logic;
  - employee-stage dictionaries и related labels.
- Важная граница:
  - classic employee form handlers пока еще остаются в `app/main.py`;
  - но React/API employee routes уже вынесены в отдельный router module.

### Employee route layer

- Модуль: `app/web/employee_routes.py`
- Отвечает за:
  - `/candidates` и `/employees` redirect entrypoints;
  - `/app/employees` и `/app/employees/{employee_id}` React bootstrap routes;
  - `/api/employees*` JSON API для employee list/detail/files/document-links/launch scheduling;
  - classic employee edit/file/document/profile-photo routes.
- Это первый полноценный vertical route slice, вынесенный из `app/main.py` через `APIRouter`.

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
  - settings workspace payload для React surface;
  - shared helpers, которые еще нужны classic settings form routes.

### Settings route layer

- Модуль: `app/web/settings_routes.py`
- Отвечает за:
  - `/settings` redirect entrypoint;
  - `/app/settings` React bootstrap route;
  - `/api/settings*` и `/api/accounts*` JSON API.
- Важная граница:
  - classic settings form handlers и bulk-save формы пока еще остаются в `app/main.py`;
  - значит `settings` отделен на React/API surface, но legacy cleanup для form routes еще впереди.

### Scenario workspace support layer

- Модуль: `app/web/scenarios.py`
- Отвечает за:
  - workspace payload serialization для scenario/survey React surfaces;
  - step tree helpers, branch/chain serialization и response labels;
  - attachment helpers для step files;
  - template copy/delete helpers, которые уже нужны и React/API workspace, и remaining classic editor tails.

### Scenario workspace route layer

- Модуль: `app/web/scenario_routes.py`
- Отвечает за:
  - `/flows` и `/surveys` redirect entrypoints;
  - `/app/flows/workspace-v2`, `/app/surveys/workspace` и legacy redirect `/app/flows/workspace`;
  - `/api/flows/workspace*` JSON API для React scenario/survey workspace.
- Важная граница:
  - classic editor routes `/flows/{scenario_id}`, `/surveys/{scenario_id}`, classic form POST update/copy/delete и survey export пока еще остаются в `app/main.py`;
  - значит `scenario/surveys` отделен на React/API workspace surface, но legacy editor cleanup еще впереди.

### JSON API

- Prefix: `/api/*`
- Модель доступа: browser session cookie, `401` без авторизации.
- Потребители:
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
3. Бот и scheduler читают эти таблицы напрямую в runtime.

### Выполнение сценария

1. Сценарий стартует вручную, через scheduled launch request или через trigger mode, который обрабатывает scheduler.
2. Engine отправляет текущий шаг, вложения, опциональную карточку сотрудника и опциональные уведомления.
3. Ответы пользователя обновляют employee data, файлы, survey answers и `scenario_progress`.

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
