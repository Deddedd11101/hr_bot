# HR Bot

HR Bot - сервис для HR-коммуникаций через административную панель и Telegram-бота.

Проект объединяет карточки кандидатов и сотрудников, сценарии сообщений, опросы, массовые действия, доставку сообщений в Telegram и stage-first процесс поставки.

## Текущее Состояние

- Backend: FastAPI-приложение с SQLAlchemy-моделями, scheduler jobs и web/API routes.
- Bot: Aiogram worker для Telegram delivery, ответов, файлов и навигации по меню.
- Frontend: операторские React/Vite-экраны. Vite build output коммитится в `app/static/workspace_v2`.
- Data: по умолчанию SQLite плюс локальное файловое хранилище в `storage/`.
- Delivery: integration/stage workflow через GitHub Actions `Deploy Stage`; ручной SSH не является нормальным deploy path.
- Documentation: `docs/` является source of truth проекта. Начинать с `docs/documentation-guide.md`.

Classic HTML surfaces еще существуют как fallback/legacy paths, пока React-экраны продолжают заменять старую админку. Не считать старые classic templates предпочтительным UI, если релевантные docs явно не говорят, что route все еще намеренно legacy.

## Стек

| Область | Стек |
| --- | --- |
| Backend | FastAPI, SQLAlchemy, Jinja2 |
| Bot | Aiogram |
| Scheduler | APScheduler |
| Database | SQLite by default |
| Storage | Local filesystem storage |
| Frontend | React 18, Vite, Tailwind v4, Base UI, selected Radix/shadcn wrappers |
| CI/CD | GitHub Actions |

## Структура Репозитория

| Путь | Назначение |
| --- | --- |
| `app/` | FastAPI app, bot runtime, web routes, messaging, static assets и templates. |
| `frontend/` | React/Vite source для операторских экранов. |
| `app/static/workspace_v2/` | Собранные Vite assets, которые использует FastAPI app. Это generated output, но сейчас он часть deploy contract. |
| `docs/` | Live-документация, decisions, runbooks, maps и historical handoffs. |
| `tests/` | Backend smoke и contract tests. |
| `tools/` | Operational scripts, diagnostics и portability tools. |
| `storage/` | Локальные runtime-файлы. Не коммитить и не удалять вслепую. |
| `backups/` | Локальные/stage backup-и базы. Не чистить без retention policy. |

## Локальный Запуск

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Открыть:

```text
http://127.0.0.1:8000
```

Telegram bot worker запускать отдельно, когда он нужен:

```powershell
.\.venv\Scripts\python.exe -m app.bot_runner
```

Актуальный runbook: `docs/local-runbook.md`.

## Frontend Assets

Установить frontend-зависимости и собрать assets:

```powershell
cd frontend
npm install
npm run build
```

Vite output попадает сюда:

```text
app/static/workspace_v2
```

Для parity с CI/deploy использовать `npm ci` перед `npm run build`.

## Окружение

Создать `.env` из `.env.example`.

Минимально полезные локальные переменные:

```env
TELEGRAM_BOT_TOKEN=replace-with-your-bot-token
DATABASE_URL=sqlite:///./hr_bot.db
ADMIN_SESSION_SECRET=change-me-admin-session-secret
```

Для быстрого локального demo `.env.example` содержит:

```env
DEMO_MODE=true
DEMO_STEP_MINUTES=1
MANUAL_STEP_MINUTES=1
```

Demo mode меняет timing scheduler-а. Не использовать его как доказательство нормального runtime-поведения.

## Проверки

Backend smoke checks, которые использует CI:

```powershell
.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe -m ruff check --select F821 app tests
.\.venv\Scripts\python.exe -m unittest tests.test_scenario_engine_smoke tests.test_messaging_identity tests.test_employee_api_smoke -v
```

Если менялся frontend source:

```powershell
cd frontend
npm run build
```

Если менялись docs, API routes, config vars или SQLAlchemy models и в worktree есть `tools/check_docs_contracts.py`:

```powershell
.\.venv\Scripts\python.exe tools\check_docs_contracts.py
```

## Документация

Сначала читать:

| Документ | Назначение |
| --- | --- |
| `docs/documentation-guide.md` | Как читать и поддерживать docs; live docs vs history. |
| `docs/project_state.md` | Текущее состояние системы, риски и приоритеты. |
| `docs/backlog.md` | Канонические задачи и статусы. |
| `docs/stage-change-log.md` | Что фактически попало на stage. |
| `docs/architecture.md` | Runtime topology и границы подсистем. |
| `docs/local-runbook.md` | Команды локального запуска. |
| `docs/stage-deploy.md` | Stage deploy runbook и smoke checks. |
| `docs/subagent-delivery.md` | Правила веток, integration и handoff для параллельных агентов. |

Historical docs вроде `docs/handoffs/*`, `docs/daily/*`, roadmap snapshots и demo briefs - это контекст, а не текущий contract.

## Delivery И Stage

Stage deploy выполняется через GitHub Actions `Deploy Stage`.

Текущая модель:

- обычный deploy ref - `stage` или согласованный integration ref;
- workflow запускается вручную с выбранным `ref`;
- preflight запускает backend checks и frontend build;
- stage deploy отказывается работать с dirty server worktree;
- перед checkout/restart создается и проверяется SQLite backup;
- после restart проверяются web, worker, WireGuard и HTTP smoke.

Не использовать ручной root SSH как нормальный deploy path. См. `docs/stage-deploy.md` и `docs/subagent-delivery.md`.

## Рабочие Правила

- Для новых задач использовать clean worktree. Historical dirty `D:\HRBot\hr_bot` worktree - rescue context, а не рабочее место по умолчанию.
- Не перетирать unrelated dirty changes.
- Значимые изменения кода, архитектуры, deploy, API, schema или процесса должны обновлять релевантные docs в той же работе.
- Не удалять `storage/*`, `backups/*`, `stage_snapshots/*` или database backups без явной retention policy.
- Не удалять `app/static/workspace_v2` как "generated trash": сейчас это часть runtime delivery.

## Runtime Data И Secrets

Никогда не коммитить реальные secrets или локальные runtime data:

- `.env`
- `hr_bot.db`
- `ci.db`
- `storage/*`
- `backups/*`
- `stage_snapshots/*`
- browser/test/debug artifacts вроде `.edge-debug/` и `.codex-artifacts/`

Точная ignore policy живет в `.gitignore`.
