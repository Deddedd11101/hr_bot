---
title: Runbook деплоя HR Bot на stage
date: 2026-05-11
status: active
task_tokens:
  - HRB-DOC-02
---

# Runbook деплоя на stage

## Область покрытия и модель подтверждения фактов

Этот файл намеренно разделяет два типа фактов:

- repo-backed facts:
  - подтверждены файлами в репозитории;
- observed stage facts:
  - подтверждены предыдущим operational handoff и ручной работой на stage;
  - не хранятся в git как infrastructure code.

Если они расходятся, repo остается authoritative для application code, но server state описывает текущий stage runtime до отдельного изменения инфраструктуры.

## Deploy path, подтвержденный репозиторием

### CI workflow

Источник: `.github/workflows/ci.yml`

Текущее поведение CI:

- запускается на:
  - push в `main`;
  - все pull requests;
- ставит Python `3.12`;
- устанавливает `requirements.txt`;
- компилирует `app/`;
- запускает `ruff check --select F821 app tests`;
- запускает smoke tests:
  - `tests.test_scenario_engine_smoke`;
  - `tests.test_messaging_identity`;
  - `tests.test_employee_api_smoke`;
- smoke-imports:
  - `app.config`;
  - `app.main`;
  - `app.bot_runner`.

### Workflow Deploy Stage

Источник: `.github/workflows/deploy-stage.yml`

Текущее поведение deploy:

1. ждет successful `CI` на `main`;
2. подключается по SSH через GitHub secrets;
3. выполняет:
   - `cd "${{ secrets.STAGE_APP_DIR }}"`;
   - `git pull --ff-only origin main`;
   - `systemctl restart hr-bot-web`;
   - `systemctl restart hr-bot-worker`;
   - `systemctl is-active --quiet hr-bot-web`;
   - `systemctl is-active --quiet hr-bot-worker`.

Нужные GitHub secrets:

- `STAGE_HOST`
- `STAGE_PORT`
- `STAGE_USERNAME`
- `STAGE_PASSWORD`
- `STAGE_APP_DIR`

## Наблюдаемые факты stage

Эти факты взяты из `docs/handoffs/telegram-linking-and-scope-handoff.md`. Их надо считать live operational notes, а не repo-enforced truth.

### Текущая форма сервера

- observed stage app directory: `/opt/hr_bot`;
- observed services:
  - `hr-bot-web`;
  - `hr-bot-worker`;
- observed public stage host из предыдущего handoff: `92.51.38.32`.

### Текущая network model

- FastAPI сейчас доступен на port `8000`.
- `nginx`, `caddy` и `apache2` в referenced stage handoff наблюдались как absent или inactive.
- port `80` наблюдался как не обслуживающий app.
- практический результат:
  - URLs без `:8000` могут падать извне;
  - рабочие stage URLs наблюдались в виде:
    - `http://92.51.38.32:8000/app/employees`;
    - `http://92.51.38.32:8000/app/flows/workspace-v2`.

### Где лежит env

- stage bot token и related secrets намеренно не хранятся в git;
- observed systemd drop-in locations:
  - `/etc/systemd/system/hr-bot-web.service.d/10-stage-env.conf`;
  - `/etc/systemd/system/hr-bot-worker.service.d/10-stage-env.conf`.

Это operationally acceptable, но значит, что infrastructure truth частично находится вне репозитория.

## Процедура deploy

### Обычный путь

1. Merge нужный код в `main`.
2. Дождаться successful GitHub `CI`.
3. Дать `Deploy Stage` выполниться автоматически.
4. Подтвердить, что оба systemd services active.
5. Выполнить smoke checks против stage HTTP surface.

### Ручной SSH-путь

Использовать только если automation недоступна или если нужно осознанно выкатить на stage не-`main` branch.

```bash
cd /opt/hr_bot
git pull --ff-only origin main
systemctl restart hr-bot-web
systemctl restart hr-bot-worker
systemctl is-active --quiet hr-bot-web
systemctl is-active --quiet hr-bot-worker
```

Если на stage выкатывается branch кроме `main`, это explicit deviation от default deploy model и должно быть записано в handoff.

## Smoke-проверки

### Состояние сервисов

```bash
systemctl status hr-bot-web --no-pager
systemctl status hr-bot-worker --no-pager
```

### Локальные HTTP-проверки на сервере

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/app/flows/workspace-v2
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/app/employees
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/app/employees/1
```

Ожидаемый результат: успешный `200` или auth redirect behavior, но не connection refused.

### Проверка worker

Bot worker считается healthy, если стартует без traceback и доходит до обычной polling log line:

- `HR Telegram bot is running. Press Ctrl+C to stop.`

## Защита базы перед рискованной работой

Перед заменой stage DB, импортом local snapshots или широкими scenario edits сделать backup:

```bash
cd /opt/hr_bot
mkdir -p backups
ts=$(date +%Y%m%d-%H%M%S)
cp -a hr_bot.db "backups/hr_bot.before-change.$ts.db"
```

## Как забрать stage data локально

Скопировать текущую stage DB на локальную машину:

```powershell
scp root@92.51.38.32:/opt/hr_bot/hr_bot.db D:\HRBot\hr_bot\stage_after_analytics.db
```

Если нужны только scenarios, лучше использовать scenario portability workflow из [[features/scenario-portability]], а не копировать всю базу вслепую.

## Операционные риски и критика

- Stage deploy chain простая, но слабая:
  - password-based SSH в GitHub Actions менее надежен, чем key-based automation;
  - app и infra configuration не полностью codified в репозитории;
  - отсутствие reverse proxy делает URL shape environment-specific и легким для ошибки в коммуникации.
- На stage приложение все еще использует SQLite. Для небольшого внутреннего стенда это допустимо, но повышает цену concurrent admin edits, manual DB replacement и schema drift recovery.
- Так как schema evolution startup-driven, deploy code и deploy DB shape не разделены чисто.
