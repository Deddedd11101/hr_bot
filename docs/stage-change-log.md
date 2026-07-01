---
title: Журнал изменений тестового стенда
date: 2026-06-16
status: active
doc_type: runbook
area: deploy
related:
  - "[[stage-deploy]]"
  - "[[project_state]]"
  - "[[backlog]]"
source_of_truth: true
---

# Журнал изменений тестового стенда

Этот файл фиксирует только то, что реально выведено на test/stage и проверено после выкладки. Он не заменяет [[backlog]], [[project_state]] или feature docs: здесь короткий operational ledger, чтобы быстро понять, какие доработки уже дошли до стенда.

## Правило ведения

Добавлять запись после каждого stage deploy, ручного stage hotfix, изменения systemd/env/VPN или правки stage DB.

Не добавлять сюда локальные эксперименты, незадеплоенные коммиты и планы. Если работа не выведена на stage, она должна быть описана в handoff/backlog, но не в этом журнале как готовая поставка.

Каждая запись должна содержать:

- дату и время по Москве;
- тип изменения: `app deploy`, `infra`, `db repair`, `config`, `docs/process`;
- краткое описание;
- что именно изменено на stage;
- локальные проверки, если были;
- stage smoke checks;
- rollback/backup, если применимо;
- открытые риски.

## Записи

### 2026-07-01 16:24 MSK - app deploy - buttons target field и скрытие design-system из навигации

- Deploy ref: `stage`.
- Deployed commit: `e7b4cab`.
- GitHub Actions run: `28520715899` -> success.
- В stage включены:
  - `codex/scenario-workspace-ui-foundation` commit `22e9caa`: React scenario workspace снова показывает `response_type=buttons` как самостоятельный тип ответа и сохраняет `target_field`, включая кейс `salary_expectation`;
  - React `/app/settings` больше не показывает старый блок HR-уведомлений, который дублировал сценарные notification rules;
  - `/app/design-system` убран из React sidebar и legacy sidebar, чтобы не торчать у админа на тестовом стенде; прямой route оставлен как внутренний dev baseline.
- Локальные проверки на объединенном `stage`:
  - `.venv\Scripts\python.exe -m compileall app tests tools`;
  - `.venv\Scripts\ruff.exe check --select F821 app tests`;
  - `.venv\Scripts\python.exe -m unittest tests.test_employee_api_smoke tests.test_messaging_identity tests.test_scenario_engine_smoke tests.test_scenario_engine_branching -v` -> 86 tests OK;
  - `npm run build` в `frontend`.
- Stage smoke checks из workflow:
  - server HEAD -> `e7b4cab`;
  - preflight compile/F821/backend smoke/frontend build/import smoke -> success;
  - `curl http://127.0.0.1:8000/app/employees` -> `303`;
  - `curl http://127.0.0.1:8000/app/flows/workspace-v2` -> `303`;
  - `curl -4 -I https://api.telegram.org/` -> `HTTP/2 302`;
  - worker log grep без свежих `TelegramNetworkError`, `Request timeout`, `Traceback`, `Unclosed client session`.
- Rollback/backup: DB не менялась; отдельный DB backup для этого app deploy не требовался.
- Открытый риск: `/app/design-system` остается доступен по прямой ссылке для разработки; если нужен полный запрет на stage, требуется отдельный env-gated route policy.

### 2026-06-16 18:26 MSK - app deploy - confirm dialogs, favicon и scenario runtime fixes

- Deploy ref: `stage`.
- Deployed commit: `bd186a9`.
- GitHub Actions run: `27628589073` -> success.
- В stage включены:
  - `codex/admin-confirm-dialog-sweep` до `f62a9e2`: React admin runtime переведен с native `window.confirm` на shared `ConfirmAction` / `AlertDialog`; dialog закрывается после подтверждения;
  - `codex/employee-confirm-dialog` через confirm sweep: удаление запланированного сценария в карточке сотрудника через shared confirm;
  - `codex/admin-favicon-logo` до `dd6feda`: добавлен `app/static/favicon.png` и подключение favicon в templates;
  - `codex/scenario-runtime-and-ui-fixes` до `d22fd93`: `launch_scenario` runtime transition, меньше сервисного шума при вложениях с кнопками, фильтрация internal follow-up jobs из launch audit, workspace scenario title/filter/disabled transition selector;
  - merge-fix `bd186a9`: regenerated `scenario-workspace.js` после merge generated bundle conflict.
- Локальные проверки на объединенном `stage`:
  - `npm run build` в `frontend`;
  - `.venv\Scripts\python.exe -m compileall app tests tools`;
  - `.venv\Scripts\ruff.exe check --select F821 app tests`;
  - `.venv\Scripts\python.exe -m unittest tests.test_employee_api_smoke tests.test_messaging_identity tests.test_scenario_engine_smoke tests.test_scenario_engine_branching -v` -> 70 tests OK.
- Stage smoke checks:
  - server HEAD -> `bd186a9`;
  - stage worktree clean;
  - `systemctl is-active wg-quick@redshield hr-bot-web hr-bot-worker` -> all `active`;
  - `curl http://127.0.0.1:8000/app/employees` -> `303`;
  - `curl http://127.0.0.1:8000/app/flows/workspace-v2` -> `303`;
  - `curl -4 -I https://api.telegram.org/` -> `HTTP/2 302`;
  - worker logs за последние 5 минут без `TelegramNetworkError`, `Request timeout`, `Traceback`, `Unclosed client session`.
- Открытый риск: legacy fallback `scenario_edit.html?legacy=1` все еще может содержать browser confirm; это отдельный non-React cleanup.

### 2026-06-16 13:38 MSK - app deploy - scenario workspace latest выведен на stage

- Deploy ref: `stage`.
- Deployed commit: `28d4bf2`.
- В stage включены:
  - `86c1c48` frontend drag-preview для scenario/survey/root step drag;
  - `b92617e` scenario workspace blocking-step guardrails;
  - `01fb93d` fixes для `ruff F821` и rebuilt Vite assets;
  - `28d4bf2` фиксация runtime env hotfix в git: `DOTENV_OVERRIDE`, `TELEGRAM_PROXY_URL`, SQLite `timeout=30`.
- Перед deploy stage worktree был dirty из-за ручного hotfix в `app/config.py` и `app/database.py`.
- Backup перед cleanup:
  - `backups/hr_bot.before-stage-deploy.20260616-103707.db`;
  - `backups/config.before-stage-deploy.20260616-103707.py`;
  - `backups/database.before-stage-deploy.20260616-103707.py`;
  - `backups/code-diff.before-stage-deploy.20260616-103707.patch`.
- БД не заменялась и не откатывалась; cleanup затронул только tracked code-файлы `app/config.py` и `app/database.py`, после чего тот же hotfix был получен обратно из git commit `28d4bf2`.
- Локальные проверки на объединенном `stage`:
  - `.venv\Scripts\python.exe -m compileall app`;
  - `.venv\Scripts\ruff.exe check --select F821 app tests`;
  - `.venv\Scripts\python.exe -m unittest tests.test_scenario_engine_smoke tests.test_messaging_identity tests.test_employee_api_smoke -v` -> 64 tests OK;
  - `npm run build` в `frontend`.
- Stage smoke checks:
  - `systemctl is-active wg-quick@redshield hr-bot-web hr-bot-worker` -> all `active`;
  - `curl http://127.0.0.1:8000/app/employees` -> `303`;
  - `curl http://127.0.0.1:8000/app/flows/workspace-v2` -> `303`;
  - `curl http://127.0.0.1:8000/app/employees/1` -> `303`;
  - `curl -4 -I https://api.telegram.org/` -> `HTTP/2 302`;
  - `wg show redshield` -> active peer with `AllowedIPs 149.154.166.110/32`;
  - worker logs за последние 5 минут без `TelegramNetworkError`, `Request timeout`, `Traceback`, `Unclosed client session`.
- Открытый риск: deploy был выполнен вручную тем же SSH flow, потому что GitHub Actions сначала остановился на dirty worktree; после cleanup повторный workflow должен пройти обычным путем.

### 2026-06-15 17:10 MSK - infra - восстановлен Telegram delivery через RedShield

- Stage server: `92.51.38.32`, app dir: `/opt/hr_bot`.
- Причина: прямой IPv4-доступ stage к `api.telegram.org:443` timeout-ился, при этом остальной outbound HTTPS работал.
- Изменение: поднят WireGuard `redshield` с selective route только для Telegram IP `149.154.166.110/32`.
- Зафиксировано: `wg-quick@redshield`, `hr-bot-web`, `hr-bot-worker` активны и включены в автозапуск.
- Важно: full tunnel запрещен; `AllowedIPs` не должен становиться `0.0.0.0/0` или `::/0`.
- Установка:
  - исходный RedShield WireGuard config был преобразован в `/etc/wireguard/redshield.conf`;
  - из конфига убраны full-tunnel `AllowedIPs`, DNS override и IPv6 route;
  - установлен пакет `wireguard-tools`;
  - web/worker получили systemd drop-ins `30-redshield-network.conf` с `Wants/After=wg-quick@redshield.service`.
- Stage checks:
  - Telegram API отвечал через VPN;
  - внешний web возвращал redirect на `/login`;
  - свежих `TelegramNetworkError`/`Request timeout` в worker logs не было.
- Дополнительно: web и worker выровнены на один Telegram bot token для `@ze_hr_bot`.
- Риск: если Telegram DNS начнет возвращать другой IPv4, selective route потребуется обновить.

### 2026-06-15 17:35 MSK - db repair - исправлена Telegram-привязка карточки `id=7`

- Причина: `/start` для `@AVstrkv` падал с `EmployeeIdentityConflictError`, потому что Telegram user id оставался в `employee_messenger_accounts` за уже удаленной карточкой `id=1`.
- Backup: создан stage DB backup `backups/hr_bot.before-identity-repair.20260615-143340.db`.
- Изменение: осиротевшая messenger account удалена, Telegram identity привязана к существующей карточке `id=7`.
- Stage checks:
  - `handle_start_command` успешно отправил ответ;
  - `employee #7` получил `telegram_user_id=461248447`, `telegram_username=AVstrkv`;
  - свежих worker errors после repair не было.
- Риск: schema-level foreign key/cascade для `employee_messenger_accounts.employee_id` все еще не оформлен; runtime-защита подготовлена локально, но должна быть выведена обычным deploy.

### 2026-06-16 - docs/process - введен отдельный stage ledger

- Изменение: создан этот журнал и добавлено правило в `AGENTS.md`, что после каждой выкатки на stage нужно фиксировать запись здесь.
- Цель: не смешивать operational delivery history с backlog, project_state и feature docs.
- Stage deploy: не требуется, потому что это правило работы и документация репозитория.

### 2026-06-16 - docs/process - stage deploy переведен на неинтерактивный GitHub Actions path

- Изменение: `.github/workflows/deploy-stage.yml` получил ручной `workflow_dispatch` с input `ref`.
- Workflow теперь перед SSH выполняет preflight checks выбранного ref: backend install, `compileall`, `ruff F821`, smoke tests, frontend `npm ci && npm run build`, smoke imports.
- Deploy job через GitHub secrets делает `git checkout -B stage-deploy <ref>`, устанавливает requirements, рестартит web/worker и выполняет stage smoke checks.
- Цель: субагентам больше не нужен интерактивный root SSH для обычного deploy; они должны готовить pushable ref и запускать `Deploy Stage`.
- Уточнение branch model: deploy отдельных feature-веток может удалить со стенда предыдущую feature-выкатку, поэтому для накопительного тестового стенда использовать `stage` или `integration/...` ref и деплоить именно его.
- Stage deploy: не требуется для самого изменения workflow до merge/push; после попадания workflow в default branch ручной deploy станет доступен из GitHub Actions.

### 2026-06-16 - docs/process - stage deploy сделан manual-only и закреплен subagent workflow

- Изменение: `Deploy Stage` больше не запускается автоматически от `main`; workflow запускается вручную и по умолчанию предлагает `ref=stage`.
- Добавлен `docs/subagent-delivery.md` с ролями субагента и интегратора, правилами feature-веток, handoff-шаблоном и запретом прямого deploy feature-веток при параллельной работе.
- Причина: auto-deploy `main` и последовательный deploy разных feature-веток могут перетереть уже выведенные на stage изменения.
- Stage deploy: не требуется для самого process-change; это настройка workflow/docs перед следующими feature deploy.

### 2026-06-16 02:07 MSK - app deploy/config - остановлен demo-loop и снижен риск повторных отправок в боте

- Причина: на stage бот отправлял авто-шаги `first_day`/`first_week`/`mid_probation`/`end_probation` минутной очередью поверх ручного сценария, а часть сообщений повторялась.
- Диагностика:
  - stage runtime подхватывал `/opt/hr_bot/.env` с `DEMO_MODE=true`;
  - worker scheduler работал с `interval[0:00:10]`, что соответствует demo mode;
  - в `journalctl -u hr-bot-worker` были `sqlite3.OperationalError: database is locked` на `INSERT INTO onboarding_events` после фактической отправки Telegram-сообщения.
- Что изменено в приложении:
  - `app/config.py`: `.env` больше не перекрывает runtime env по умолчанию; для локального принудительного override теперь нужен `DOTENV_OVERRIDE=true`;
  - `app/database.py`: для SQLite добавлен `timeout=30` в SQLAlchemy `connect_args`.
- Что изменено на stage:
  - вручную загружены только `app/config.py` и `app/database.py` в `/opt/hr_bot`;
  - в `/etc/systemd/system/hr-bot-web.service.d/10-stage-env.conf` и `/etc/systemd/system/hr-bot-worker.service.d/10-stage-env.conf` явно добавлены:
    - `Environment="DEMO_MODE=false"`
    - `Environment="DOTENV_OVERRIDE=false"`
  - `/opt/hr_bot/.env` тоже нормализован до `DEMO_MODE=false` и `DOTENV_OVERRIDE=false`, чтобы ручной запуск вне systemd не возвращал demo semantics;
  - выполнены `systemctl daemon-reload` и restart `hr-bot-web` / `hr-bot-worker`.
- Локальные проверки:
  - `.\.venv\Scripts\python.exe -m compileall app`
  - `.\.venv\Scripts\python.exe -m unittest tests.test_scenario_engine_smoke tests.test_messaging_identity tests.test_employee_api_smoke -v`
  - smoke imports `app.config`, `app.main`, `app.bot_runner`
  - `ruff` в локальном `.venv` отсутствовал как модуль, поэтому этот шаг не был выполнен автоматически.
- Stage smoke checks:
  - `systemctl status hr-bot-web --no-pager` -> active
  - `systemctl status hr-bot-worker --no-pager` -> active
  - `systemctl is-active wg-quick@redshield hr-bot-web hr-bot-worker` -> all `active`
  - `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/app/employees` -> `303`
  - `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/app/flows/workspace-v2` -> `303`
  - `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/app/employees/1` -> `303`
  - `curl -4 -I --connect-timeout 10 https://api.telegram.org/` -> HTTP response received
  - `wg show redshield` -> handshake present
  - worker process env подтвержден через `/proc/<pid>/environ`: `DEMO_MODE=false`, `DOTENV_OVERRIDE=false`
  - повторная проверка через 70 секунд: число `onboarding_events` для employee `#7` не выросло (`76 -> 76`), loop остановлен.
- Rollback/backup:
  - backup БД не делался, потому что изменение не затрагивало schema/data repair;
  - rollback path: вернуть старые `app/config.py`, `app/database.py` и убрать `DEMO_MODE=false` / `DOTENV_OVERRIDE=false` из systemd drop-ins.
- Открытые риски:
  - SQLite все еще остается источником write-lock риска; `timeout=30` смягчает симптом, но не заменяет более надежную delivery/outbox стратегию.

### 2026-06-17 00:13 MSK - app deploy - выведены UI polish, select scroll policy и scenario runtime triggers

- Deploy ref: `stage`.
- Deployed commit: `230779c`.
- GitHub Actions run: `27648456932`.
- Влитые feature-ветки:
  - `codex/select-scroll-policy` -> `2bd5851`;
  - `codex/admin-ui-polish-pass` -> `a26c529`;
  - `codex/scenario-runtime-and-ui-fixes` -> `1f52589` вместе с `129fb33`.
- Что изменено:
  - унифицирован scroll policy для select-компонентов;
  - выровнены мелкие admin UI-паттерны;
  - добавлена сортировка sidebar сценариев;
  - добавлены scenario triggers для HR-статусов кандидатов;
  - пересобраны `app/static/workspace_v2` после объединения фронтовых веток.
- Локальные проверки перед deploy:
  - `npm run build`;
  - `.\.venv\Scripts\python.exe -m compileall app tests tools`;
  - `.\.venv\Scripts\ruff.exe check --select F821 app tests`;
  - `.\.venv\Scripts\python.exe -m unittest tests.test_employee_api_smoke tests.test_messaging_identity tests.test_scenario_engine_smoke tests.test_scenario_engine_branching -v` -> 71 tests OK.
- GitHub Actions preflight:
  - backend dependencies install;
  - `compileall`;
  - `ruff F821`;
  - backend smoke tests;
  - frontend build;
  - smoke imports.
- Stage smoke checks:
  - `hr-bot-web`, `hr-bot-worker` и `wg-quick@redshield` active;
  - `/app/employees` -> `303`;
  - `/app/flows/workspace-v2` -> `303`;
  - `curl -4 -I --connect-timeout 10 https://api.telegram.org/` -> `HTTP/2 302`;
  - свежих `TelegramNetworkError`, `Request timeout`, `Traceback`, `Unclosed client session` в worker logs не найдено.
- Backup БД не делался: deploy шел через git/systemd restart и не требовал ручной замены `hr_bot.db`.

### 2026-06-17 12:09 MSK - app deploy - branch return flow и read-only схема сценария

- Deploy ref: `stage`.
- Deployed commit: `8e0ddb4`.
- GitHub Actions run: `27678177804`.
- Влитые feature-ветки:
  - `codex/scenario-runtime-and-ui-fixes` -> `9f8e8fd` вместе с `7a1a52f` и `1c4dfef`;
  - `codex/admin-ui-polish-pass` -> `dc2159a`.
- Что изменено:
  - branch step получил узкий возврат в root-step того же сценария через `return_to_step_key`;
  - добавлены rollback snapshots для сценарного Back action;
  - workspace API начал отдавать read-only graph payload для режима `Схема`;
  - scenario workspace получил read-only граф на React Flow + ELK с синхронизацией выбранной node и правой панели;
  - пересобраны `app/static/workspace_v2` после объединения runtime/UI веток.
- Локальные проверки перед deploy:
  - `npm install` для новых frontend-зависимостей;
  - `npm run build`;
  - `.\.venv\Scripts\python.exe -m compileall app tests tools`;
  - `.\.venv\Scripts\ruff.exe check --select F821 app tests`;
  - `.\.venv\Scripts\python.exe -m unittest tests.test_employee_api_smoke tests.test_messaging_identity tests.test_scenario_engine_smoke tests.test_scenario_engine_branching -v` -> 77 tests OK.
- GitHub Actions preflight:
  - backend dependencies install;
  - `compileall`;
  - `ruff F821`;
  - backend smoke tests;
  - frontend build;
  - smoke imports.
- Stage smoke checks:
  - `/app/employees` -> `303`;
  - `/app/flows/workspace-v2` -> `303`;
  - `curl -4 -I --connect-timeout 10 https://api.telegram.org/` -> `HTTP/2 302`;
  - deploy job завершился успешно и вывел `8e0ddb4`.
- Backup БД не делался: deploy шел через git/systemd restart и не требовал ручной замены `hr_bot.db`.
- Открытые риски:
  - `graph-view` bundle после React Flow + ELK около `1.6 MB`; режим `Схема` стоит вынести в lazy chunk.
  - GitHub Actions выдал warning про Node.js 20 deprecation для `actions/checkout@v4` и `actions/setup-python@v5`; deploy успешен, но workflow нужно обновить планово.

### 2026-06-17 16:22 MSK - app deploy - сброс привязки карточки к Telegram-боту

- Deploy ref: `stage`.
- Deployed commit: `8ff5ce4`.
- GitHub Actions run: `27692014859`.
- Влитая feature-ветка:
  - `codex/scenario-runtime-and-ui-fixes` -> `8c848e7`.
- Что изменено:
  - добавлен endpoint `POST /api/employees/{employee_id}/bot-link/reset`;
  - в карточке сотрудника/кандидата добавлено отдельное действие `Сбросить привязку к боту`;
  - reset очищает `telegram_user_id`, `telegram_username`, `current_menu_set_id`, `is_flow_scheduled`;
  - reset удаляет `employee_messenger_accounts`, активный `scenario_progress` и только pending `flow_launch_requests`;
  - удаление карточки осталось отдельным destructive action с confirm dialog.
- Локальные проверки перед deploy:
  - `npm run build`;
  - `.\.venv\Scripts\python.exe -m compileall app tests tools`;
  - `.\.venv\Scripts\ruff.exe check --select F821 app tests`;
  - `.\.venv\Scripts\python.exe -m unittest tests.test_employee_api_smoke tests.test_messaging_identity tests.test_scenario_engine_smoke tests.test_scenario_engine_branching -v` -> 78 tests OK.
- GitHub Actions preflight:
  - backend dependencies install;
  - `compileall`;
  - `ruff F821`;
  - backend smoke tests;
  - frontend build;
  - smoke imports.
- Stage smoke checks:
  - `/app/employees` -> `303`;
  - `/app/flows/workspace-v2` -> `303`;
  - `curl -4 -I --connect-timeout 10 https://api.telegram.org/` -> `HTTP/2 302`;
  - deploy job завершился успешно и вывел `8ff5ce4`.
- Backup БД не делался: deploy шел через git/systemd restart и не требовал ручной замены `hr_bot.db`.
- Открытые риски:
  - `graph-view` bundle warning остается из предыдущего deploy;
  - GitHub Actions warning про Node.js 20 deprecation остается плановым workflow-долгом.

### 2026-06-17 16:39 MSK - app deploy - порядок сообщений шага с вложением и кнопками

- Deploy ref: `stage`.
- Deployed commit: `d9c842f`.
- GitHub Actions run: `27693049551`.
- Влитая feature-ветка:
  - `codex/step-attachment-button-order` -> `e926d26`.
- Что изменено:
  - runtime отправки шага сценария теперь отправляет `текст -> карточка/вложение -> отдельное сообщение с inline-кнопками`;
  - кнопки больше не цепляются к первому текстовому сообщению перед вложением;
  - добавлен smoke-тест `test_send_step_sends_buttons_after_attachment_when_text_exists`.
- Локальные проверки перед deploy:
  - `.\.venv\Scripts\python.exe -m compileall app tests`;
  - `.\.venv\Scripts\ruff.exe check --select F821 app tests`;
  - `.\.venv\Scripts\python.exe -m unittest tests.test_scenario_engine_smoke tests.test_scenario_engine_branching -v` -> 17 tests OK;
  - `.\.venv\Scripts\python.exe -m unittest tests.test_employee_api_smoke tests.test_messaging_identity tests.test_scenario_engine_smoke tests.test_scenario_engine_branching -v` -> 78 tests OK.
- GitHub Actions preflight:
  - backend dependencies install;
  - `compileall`;
  - `ruff F821`;
  - backend smoke tests;
  - frontend build;
  - smoke imports.
- Stage smoke checks:
  - `/app/employees` -> `303`;
  - `/app/flows/workspace-v2` -> `303`;
  - `curl -4 -I --connect-timeout 10 https://api.telegram.org/` -> `HTTP/2 302`;
  - deploy job завершился успешно и вывел `d9c842f`.
- Backup БД не делался: deploy шел через git/systemd restart и не требовал ручной замены `hr_bot.db`.
- Открытые риски:
  - UX-компромисс: inline-кнопки приходят отдельным сообщением после вложения, потому что Telegram не позволяет одновременно иметь отдельный текст, вложение и кнопки без дополнительного button-message.

### 2026-06-17 17:11 MSK - app deploy - кнопки media-шагов без технического текста

- Deploy ref: `stage`.
- Deployed commit: `9443d61`.
- GitHub Actions run: `27695175484`.
- Влитая feature-ветка:
  - `codex/remove-technical-button-prompts` -> `96401a2`.
- Что изменено:
  - убран технический текст `Выберите вариант ответа:` для media-шагов с inline-кнопками;
  - если у шага есть картинка/документ и inline-кнопки, кнопки крепятся прямо к media-сообщению;
  - для кейса `текст + картинка + кнопка` порядок стал `текст -> картинка с кнопкой`;
  - для кейса `картинка + кнопка` отдельное сервисное сообщение больше не отправляется;
  - messaging contract расширен под `reply_markup` и `caption` для photo/document send.
- Локальные проверки перед deploy:
  - `.\.venv\Scripts\python.exe -m compileall app tests`;
  - `.\.venv\Scripts\ruff.exe check --select F821 app tests`;
  - `.\.venv\Scripts\python.exe -m unittest tests.test_scenario_engine_smoke tests.test_scenario_engine_branching tests.test_employee_api_smoke -v` -> 76 tests OK;
  - `.\.venv\Scripts\python.exe -m unittest tests.test_employee_api_smoke tests.test_messaging_identity tests.test_scenario_engine_smoke tests.test_scenario_engine_branching -v` -> 79 tests OK.
- GitHub Actions preflight:
  - backend dependencies install;
  - `compileall`;
  - `ruff F821`;
  - backend smoke tests;
  - frontend build;
  - smoke imports.
- Stage smoke checks:
  - `/app/employees` -> `303`;
  - `/app/flows/workspace-v2` -> `303`;
  - `curl -4 -I --connect-timeout 10 https://api.telegram.org/` -> `HTTP/2 302`;
  - deploy job завершился успешно и вывел `9443d61`.
- Backup БД не делался: deploy шел через git/systemd restart и не требовал ручной замены `hr_bot.db`.
- Открытые риски:
  - Telegram media-сообщение теперь несет inline-кнопки; если Telegram API отклонит конкретный тип media/caption/markup, смотреть worker logs и fallback path.

### 2026-06-29 17:03 MSK - app deploy - фиксы scenario workspace select/target fields

- Deploy ref: `stage`.
- Deployed commit: `0b166ca`.
- GitHub Actions run: `28377727578`.
- Влитые feature-ветки:
  - `codex/fix-step-target-field-persistence` -> `4267ce0`;
  - `codex/fix-branch-return-select` -> `10b9610`.
- Что изменено:
  - `buttons`-шаги в scenario workspace снова сохраняют target field;
  - `SingleSelectPicker` больше не держит несуществующее текущее значение и дедуплицирует options;
  - список `Вернуться в основной сценарий` исключает текущий root-шаг ветвления, который backend все равно очистил бы при сохранении;
  - пересобран `app/static/workspace_v2/scenario-workspace.js`.
- Локальные проверки перед deploy:
  - `npm run build`;
  - `.\.venv\Scripts\python.exe -m compileall app tests tools`;
  - `.\.venv\Scripts\ruff.exe check --select F821 app tests`;
  - `.\.venv\Scripts\python.exe -m unittest tests.test_employee_api_smoke tests.test_messaging_identity tests.test_scenario_engine_smoke tests.test_scenario_engine_branching -v` -> 81 tests OK.
- GitHub Actions preflight:
  - backend dependencies install;
  - `compileall`;
  - `ruff F821`;
  - backend smoke tests;
  - frontend build;
  - smoke imports.
- Stage smoke checks:
  - `/app/employees` -> `303`;
  - `/app/flows/workspace-v2` -> `303`;
  - `curl -4 -I --connect-timeout 10 https://api.telegram.org/` -> `HTTP/2 302`;
  - deploy job завершился успешно и вывел `0b166ca`.
- Backup БД не делался: deploy шел через git/systemd restart и не требовал ручной замены `hr_bot.db`.
- Открытые риски:
  - browser может держать cached `scenario-workspace.js?v=1`; при ручной проверке нужен hard refresh.

### 2026-07-01 12:03 MSK - app deploy - navigation contract для меню бота

- Deploy ref: `stage`.
- Deployed commit: `c5c201c`.
- GitHub Actions run: `28506038067`.
- Что изменено:
  - добавлен явный root menu contract для Telegram-меню: `/start` возвращает пользователя в главный набор;
  - добавлен стек подменю `Employee.current_menu_path`, runtime-кнопки `Назад` и `Главное меню`;
  - пользовательские кнопки с названиями `Назад` и `Главное меню` теперь запрещены, чтобы не конфликтовать с навигацией;
  - на `/app/bot-menu` добавлен выбор главного набора и действие `Разослать главное меню`;
  - добавлен API `POST /api/settings/bot-menu/broadcast` для отправки root menu уже привязанным пользователям;
  - SQLite schema compatibility добавляет `employees.current_menu_path`.
- Локальные проверки перед deploy:
  - `.\.venv\Scripts\python.exe -m compileall app tests tools`;
  - `.\.venv\Scripts\ruff.exe check --select F821 app tests`;
  - `.\.venv\Scripts\python.exe -m unittest tests.test_employee_api_smoke tests.test_messaging_identity tests.test_scenario_engine_smoke tests.test_scenario_engine_branching -v` -> 85 tests OK;
  - `npm run build`.
- GitHub Actions preflight:
  - backend dependencies install;
  - `compileall`;
  - `ruff F821`;
  - backend smoke tests;
  - frontend build;
  - smoke imports.
- Stage smoke checks:
  - `/app/employees` -> `303`;
  - `/app/flows/workspace-v2` -> `303`;
  - `curl -4 -I --connect-timeout 10 https://api.telegram.org/` -> `HTTP/2 302`;
  - `hr-bot-web`, `hr-bot-worker` и `wg-quick@redshield` прошли `systemctl is-active`;
  - worker log grep не нашел свежие `TelegramNetworkError`, `Request timeout`, `Traceback`, `Unclosed client session`;
  - deploy job завершился успешно и вывел `c5c201c`.
- Backup БД не делался: deploy шел через git/systemd restart и schema compatibility добавляет колонку без ручной замены `hr_bot.db`.
- Открытые риски:
  - операторам нужно явно выбрать главный набор на `/app/bot-menu`, если текущий первый/targeted fallback не соответствует ожидаемому root UX.

### 2026-07-01 12:08 MSK - manual stage maintenance - очистка сотрудников и кандидатов

- Тип изменения: ручная maintenance-операция на stage SQLite DB без deploy кода.
- Stage app dir: `/opt/hr_bot`.
- App commit на сервере во время операции: `c5c201c`.
- Backup перед очисткой:
  - DB: `/opt/hr_bot/backups/hr_bot.before-clean-employees.20260701-090739.db`;
  - employee files: `/opt/hr_bot/backups/employee_files.before-clean-employees.20260701-090739.tgz`.
- Что очищено:
  - `employees`;
  - `employee_messenger_accounts`;
  - `employee_files`;
  - `employee_document_links`;
  - `scenario_progress`;
  - `survey_answers`;
  - `flow_launch_requests`;
  - `mass_scenario_actions`;
  - `mass_message_actions`;
  - filesystem: `storage/employee_files`.
- Что сохранено:
  - scenario templates и scenario step files;
  - bot menu sets;
  - HR/system settings;
  - document/scenario storage outside `storage/employee_files`.
- Дополнительно очищены stale references:
  - `bot_menu_sets.target_employee_id`;
  - `bot_menu_sets.target_employee_ids`;
  - `scenario_templates.target_employee_id`.
- Проверка после очистки:
  - `employees` -> `0`;
  - `employee_messenger_accounts` -> `0`;
  - `employee_files` -> `0`;
  - `employee_document_links` -> `0`;
  - `scenario_progress` -> `0`;
  - `survey_answers` -> `0`;
  - `flow_launch_requests` -> `0`;
  - `mass_scenario_actions` -> `0`;
  - `mass_message_actions` -> `0`;
  - `storage/employee_files` -> `0 files`;
  - `storage/scenario_step_files` сохранен: `6 files`;
  - `hr-bot-web`, `hr-bot-worker`, `wg-quick@redshield` active;
  - `/app/employees` -> `303`;
  - `/app/flows/workspace-v2` -> `303`;
  - worker log grep не нашел свежие `TelegramNetworkError`, `Request timeout`, `Traceback`, `Unclosed client session`.
- Открытые риски:
  - если на тестовом стенде нужны demo employees/candidates, их нужно создать заново через UI или seed/script; старые карточки восстановимы из backup DB.
