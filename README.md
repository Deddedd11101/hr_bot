# HR Bot

HR Bot - сервис для HR-коммуникаций через административную панель и Telegram-бота.

Проект объединяет карточки кандидатов и сотрудников, сценарии сообщений, опросы, массовые действия, Telegram delivery и stage-first процесс поставки.

## Current Status

- Backend: FastAPI application with SQLAlchemy models, scheduler jobs and web/API routes.
- Bot: Aiogram worker for Telegram delivery, responses, files and menu navigation.
- Frontend: React/Vite operator surfaces. Vite build output is committed under `app/static/workspace_v2`.
- Data: SQLite by default plus local file storage under `storage/`.
- Delivery: integration/stage workflow through GitHub Actions `Deploy Stage`; manual SSH is not the normal deploy path.
- Documentation: `docs/` is the project source of truth. Start with `docs/documentation-guide.md`.

Classic HTML surfaces still exist as fallback/legacy paths while React operator screens continue to replace them. Do not treat old classic templates as the preferred UI unless the relevant docs say the route is still intentionally legacy.

## Stack

| Area | Stack |
| --- | --- |
| Backend | FastAPI, SQLAlchemy, Jinja2 |
| Bot | Aiogram |
| Scheduler | APScheduler |
| Database | SQLite by default |
| Storage | Local filesystem storage |
| Frontend | React 18, Vite, Tailwind v4, Base UI, selected Radix/shadcn wrappers |
| CI/CD | GitHub Actions |

## Repository Layout

| Path | Purpose |
| --- | --- |
| `app/` | FastAPI app, bot runtime, web routes, messaging, static assets and templates. |
| `frontend/` | React/Vite source for operator surfaces. |
| `app/static/workspace_v2/` | Built Vite assets used by the FastAPI app. This is generated, but currently part of the deploy contract. |
| `docs/` | Live documentation, decisions, runbooks, maps and historical handoffs. |
| `tests/` | Backend smoke and contract tests. |
| `tools/` | Operational scripts, diagnostics and portability tools. |
| `storage/` | Local runtime files. Do not commit or delete blindly. |
| `backups/` | Local/stage database backups. Do not clean without retention policy. |

## Local Start

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

Run the Telegram bot worker separately when needed:

```powershell
.\.venv\Scripts\python.exe -m app.bot_runner
```

See the current runbook: `docs/local-runbook.md`.

## Frontend Assets

Install frontend dependencies and build assets:

```powershell
cd frontend
npm install
npm run build
```

The Vite output goes to:

```text
app/static/workspace_v2
```

For CI/deploy parity use `npm ci` before `npm run build`.

## Environment

Create `.env` from `.env.example`.

Minimum useful local variables:

```env
TELEGRAM_BOT_TOKEN=replace-with-your-bot-token
DATABASE_URL=sqlite:///./hr_bot.db
ADMIN_SESSION_SECRET=change-me-admin-session-secret
```

For a quick local demo, `.env.example` includes:

```env
DEMO_MODE=true
DEMO_STEP_MINUTES=1
MANUAL_STEP_MINUTES=1
```

Demo mode changes scheduler timing. Do not use it as proof of normal runtime behavior.

## Checks

Backend smoke checks used by CI:

```powershell
.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe -m ruff check --select F821 app tests
.\.venv\Scripts\python.exe -m unittest tests.test_scenario_engine_smoke tests.test_messaging_identity tests.test_employee_api_smoke -v
```

If frontend source changed:

```powershell
cd frontend
npm run build
```

If docs, API routes, config vars or SQLAlchemy models changed and `tools/check_docs_contracts.py` exists in the worktree:

```powershell
.\.venv\Scripts\python.exe tools\check_docs_contracts.py
```

## Documentation

Read these first:

| Document | Purpose |
| --- | --- |
| `docs/documentation-guide.md` | How to read and maintain docs; live docs vs history. |
| `docs/project_state.md` | Current system state, risks and priorities. |
| `docs/backlog.md` | Canonical tasks and statuses. |
| `docs/stage-change-log.md` | What actually reached stage. |
| `docs/architecture.md` | Runtime topology and subsystem boundaries. |
| `docs/local-runbook.md` | Local run commands. |
| `docs/stage-deploy.md` | Stage deploy runbook and smoke checks. |
| `docs/subagent-delivery.md` | Branching, integration and handoff rules for parallel agents. |

Historical docs such as `docs/handoffs/*`, `docs/daily/*`, roadmap snapshots and demo briefs are context, not current contract.

## Delivery And Stage

Stage deploy is handled through GitHub Actions `Deploy Stage`.

Current model:

- normal deploy ref is `stage` or an agreed integration ref;
- workflow is manually dispatched with a `ref`;
- preflight runs backend checks and frontend build;
- stage deploy refuses dirty server worktrees;
- SQLite backup is created and verified before checkout/restart;
- web, worker, WireGuard and HTTP smoke checks run after restart.

Do not use manual root SSH as the normal deploy path. See `docs/stage-deploy.md` and `docs/subagent-delivery.md`.

## Working Rules

- Use a clean worktree for new tasks. The historical dirty `D:\HRBot\hr_bot` worktree is rescue context, not the default place for new work.
- Do not overwrite unrelated dirty changes.
- Significant code, architecture, deploy, API, schema or process changes must update the relevant docs in the same work.
- Do not delete `storage/*`, `backups/*`, `stage_snapshots/*` or database backups without an explicit retention policy.
- Do not delete `app/static/workspace_v2` as "generated trash"; it is currently part of runtime delivery.

## Runtime Data And Secrets

Never commit real secrets or local runtime data:

- `.env`
- `hr_bot.db`
- `ci.db`
- `storage/*`
- `backups/*`
- `stage_snapshots/*`
- browser/test/debug artifacts such as `.edge-debug/` and `.codex-artifacts/`

The exact ignore policy lives in `.gitignore`.
