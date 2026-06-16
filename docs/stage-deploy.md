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

1. автоматически ждет successful `CI` на `main` или запускается вручную через `workflow_dispatch`;
2. для ручного запуска принимает `ref` — branch, tag или commit SHA;
3. перед SSH выполняет preflight на выбранном ref:
   - `python -m pip install -r requirements.txt`;
   - `python -m compileall app`;
   - `ruff check --select F821 app tests`;
   - backend smoke tests;
   - `npm ci && npm run build` в `frontend`;
   - smoke imports;
4. подключается по SSH через GitHub secrets;
5. отказывается деплоить, если stage worktree грязный;
6. выполняет:
   - `cd "${{ secrets.STAGE_APP_DIR }}"`;
   - `git fetch --prune origin`;
   - `git checkout -B stage-deploy <ref>`;
   - `.venv/bin/python -m pip install -r requirements.txt`;
   - `systemctl restart hr-bot-web`;
   - `systemctl restart hr-bot-worker`;
   - `systemctl is-active --quiet hr-bot-web`;
   - `systemctl is-active --quiet hr-bot-worker`;
   - `systemctl is-active --quiet wg-quick@redshield`;
   - HTTP smoke checks;
   - Telegram API reachability check;
   - worker log check на свежие Telegram/network tracebacks.

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

Важно:

- stage не должен полагаться на `.env` внутри `/opt/hr_bot` для scheduler flags;
- `DEMO_MODE` на stage должен быть задан явно как `false` в systemd env/drop-ins или отсутствовать в stage `.env`;
- после изменения `app/config.py` runtime env имеет приоритет над `.env`, но это не отменяет необходимости держать stage `.env` безопасным.

## Процедура deploy

### Branch model для stage

Stage deploy выкатывает весь выбранный git ref целиком. Это значит, что deploy одной feature-ветки может убрать со стенда изменения из другой feature-ветки, если они не смержены в один ref.

Правило:

- `feature/...` — ветка конкретной задачи или субагента;
- `stage` — накопительная ветка тестового стенда;
- `integration/...` — временная накопительная ветка, если нужно собрать несколько зависимых задач без загрязнения `stage`;
- `Deploy Stage` по умолчанию запускать с `ref=stage`, если цель — сохранить уже выведенные на стенд изменения.

Типовой порядок:

```bash
git fetch origin
git checkout stage
git pull --ff-only origin stage
git merge --no-ff feature/backend-fix
git push origin stage
```

Затем в GitHub Actions запустить `Deploy Stage` с `ref=stage`.

Если после этого нужна frontend-доработка:

```bash
git fetch origin
git checkout feature/frontend-fix
git merge origin/stage
# resolve conflicts, run checks
git checkout stage
git pull --ff-only origin stage
git merge --no-ff feature/frontend-fix
git push origin stage
```

И снова запускать `Deploy Stage` с `ref=stage`.

Не запускать подряд `Deploy Stage` для `feature/backend-fix`, а затем для `feature/frontend-fix`, если frontend-ветка не содержит backend-fix. Последний deploy заменит весь код стенда выбранным ref.

### Обычный путь

1. Merge нужный код в `main`.
2. Дождаться successful GitHub `CI`.
3. Дать `Deploy Stage` выполниться автоматически.
4. Подтвердить, что оба systemd services active.
5. Выполнить smoke checks против stage HTTP surface.

### Ручной GitHub Actions deploy

Использовать, когда надо выкатить `stage`, `integration/...` или другой согласованный ref без интерактивного SSH:

1. убедиться, что изменения закоммичены в отдельную ветку или доступны как commit SHA;
2. если нужно сохранить уже выведенные изменения, влить feature-ветку в `stage` или integration branch;
3. push ref в GitHub;
4. открыть GitHub Actions;
5. выбрать workflow `Deploy Stage`;
6. нажать `Run workflow`;
7. указать `ref`, например:
   - `main`;
   - `stage`;
   - `integration/sprint-YYYY-MM-DD`;
   - commit SHA;
8. дождаться successful preflight и deploy jobs;
9. добавить запись в [[stage-change-log]].

Субагентам нельзя считать интерактивный SSH обязательным или нормальным deploy path. Если workflow `Deploy Stage` доступен, отсутствие root SSH у субагента не является блокером: он должен подготовить pushable ref, влить его в `stage`/integration branch и запустить/запросить запуск workflow.

Если workflow падает на `Stage worktree is dirty`, не делать `git reset --hard` вслепую. Сначала проверить, какие ручные изменения есть на сервере, и решить, что из них надо сохранить.

### Настройка GitHub для deploy

Один раз проверить в GitHub repository settings:

1. `Settings -> Secrets and variables -> Actions -> Repository secrets`.
2. Должны быть secrets:
   - `STAGE_HOST` = `92.51.38.32`;
   - `STAGE_PORT` = SSH port, обычно `22`;
   - `STAGE_USERNAME` = SSH user, сейчас `root`;
   - `STAGE_PASSWORD` = текущий SSH password или заменить на key-based secret в будущем;
   - `STAGE_APP_DIR` = `/opt/hr_bot`.
3. `Settings -> Actions -> General`:
   - Actions enabled;
   - Workflow permissions достаточно `Read repository contents` для текущего workflow;
   - если появится workflow, который сам пушит commits/tags, тогда отдельно включать write permissions, но текущему deploy это не нужно.
4. Вкладка `Actions` должна показывать workflow `Deploy Stage` после того, как `.github/workflows/deploy-stage.yml` попал в default branch.

Как запустить вручную:

1. открыть `Actions`;
2. выбрать `Deploy Stage`;
3. нажать `Run workflow`;
4. выбрать branch, где лежит workflow file, обычно `main`;
5. в input `ref` указать `stage` или нужный integration ref;
6. нажать `Run workflow`;
7. открыть run и дождаться двух jobs:
   - `preflight`;
   - `deploy`.

Если workflow не виден:

- проверить, что `.github/workflows/deploy-stage.yml` уже есть в default branch;
- проверить, что Actions включены для репозитория;
- проверить синтаксис YAML в GitHub Actions UI.

Если deploy job падает на SSH:

- проверить `STAGE_HOST`, `STAGE_PORT`, `STAGE_USERNAME`, `STAGE_PASSWORD`, `STAGE_APP_DIR`;
- отдельно проверить, что GitHub Actions runner может подключаться к серверу по этому credential;
- не раздавать root password субагентам как workaround.

### Ручной SSH-путь

Использовать только если automation недоступна или если нужно осознанно выкатить на stage не-`main` branch.

```bash
cd /opt/hr_bot
git fetch --prune origin
git checkout -B stage-deploy origin/main
.venv/bin/python -m pip install -r requirements.txt
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

Одного `systemctl is-active hr-bot-worker` недостаточно: worker может оставаться `active`, получать updates через long polling, но не отправлять ответы из-за timeout новых HTTPS-соединений к Telegram API.

После restart дополнительно:

1. отправить боту `/start`;
2. проверить отсутствие свежих `TelegramNetworkError`, `Request timeout error` и `Unclosed client session`;
3. при timeout проверить IPv4/IPv6-маршрут с stage:

```bash
curl -4 -I --connect-timeout 10 https://api.telegram.org
curl -6 -I --connect-timeout 10 https://api.telegram.org
getent ahosts api.telegram.org
journalctl -u hr-bot-worker --since "5 minutes ago" --no-pager -n 200
```

Интерпретация:

- работает только `curl -4` — проблема IPv6-маршрута;
- не работают оба варианта — проблема outbound route/firewall/provider до Telegram;
- curl работает, но worker получает timeout — проверять connection/session lifecycle приложения и effective systemd environment.

Если провайдер не восстанавливает прямой маршрут к Telegram, web и worker должны использовать один proxy через systemd drop-ins:

```ini
[Service]
Environment="TELEGRAM_PROXY_URL=socks5://user:password@proxy-host:proxy-port"
```

После изменения:

```bash
cd /opt/hr_bot
.venv/bin/python -m pip install -r requirements.txt
systemctl daemon-reload
systemctl restart hr-bot-web hr-bot-worker
journalctl -u hr-bot-worker --since "2 minutes ago" --no-pager -n 200
```

Proxy нужен обоим сервисам: worker отвечает на входящие updates, а web отправляет Telegram-сообщения при ручном запуске сценариев и массовых действиях.

### Текущий stage workaround через WireGuard

На stage прямой маршрут к Telegram API может быть недоступен при рабочем остальном outbound HTTPS. Текущий безопасный обход — WireGuard-интерфейс `redshield`, через который направлен только Telegram IP:

```ini
AllowedIPs = 149.154.166.110/32
```

Не заменять это значение на `0.0.0.0/0`: full-tunnel может нарушить SSH и публичную доступность web.

Проверка:

```bash
systemctl is-active wg-quick@redshield hr-bot-web hr-bot-worker
ip route get 149.154.166.110
wg show redshield
curl -4 -I --connect-timeout 10 https://api.telegram.org/
```

Ожидается маршрут через `redshield`, свежий WireGuard handshake и HTTP-ответ Telegram без timeout. Если DNS Telegram начнет возвращать другой IPv4, selective route потребуется обновить.

### Как был установлен RedShield WireGuard

Исходный RedShield config был получен как WireGuard `.conf` для Linux. Его нельзя ставить на сервер без изменений, если в нем указано:

```ini
AllowedIPs = 0.0.0.0/0, ::/0
```

Такой full-tunnel может увести SSH, web и весь outbound сервера через VPN. Для stage был подготовлен отдельный конфиг `/etc/wireguard/redshield.conf` с selective route только до Telegram API:

```ini
[Interface]
Address = <redshield_ipv4>/32
PrivateKey = <secret>
MTU = 1280

[Peer]
PublicKey = <redshield_public_key>
AllowedIPs = 149.154.166.110/32
Endpoint = <redshield_endpoint>:10001
PersistentKeepalive = 20
```

Что намеренно убрано из исходного конфига:

- `DNS = ...`, чтобы не менять DNS всего сервера;
- IPv6 address, потому что на stage нет default IPv6 route;
- `AllowedIPs = 0.0.0.0/0, ::/0`, чтобы не включать full-tunnel.

Команды установки:

```bash
apt-get update -qq
apt-get install -y wireguard-tools
install -d -m 700 /etc/wireguard
install -m 600 /tmp/redshield.conf /etc/wireguard/redshield.conf
wg-quick up redshield
```

После успешной проверки:

```bash
systemctl enable wg-quick@redshield
mkdir -p /etc/systemd/system/hr-bot-web.service.d
mkdir -p /etc/systemd/system/hr-bot-worker.service.d
```

Для `hr-bot-web` и `hr-bot-worker` добавлен drop-in `30-redshield-network.conf`:

```ini
[Unit]
Wants=wg-quick@redshield.service
After=wg-quick@redshield.service
```

Затем:

```bash
systemctl daemon-reload
systemctl restart hr-bot-web hr-bot-worker
```

Проверки после установки:

```bash
systemctl is-active wg-quick@redshield hr-bot-web hr-bot-worker
systemctl is-enabled wg-quick@redshield hr-bot-web hr-bot-worker
ip route get 149.154.166.110
wg show redshield
curl -4 -I --connect-timeout 10 https://api.telegram.org/
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/app/employees
journalctl -u hr-bot-worker --since "5 minutes ago" --no-pager -n 100
```

Откат WireGuard, если VPN ломает Telegram или сеть:

```bash
systemctl disable --now wg-quick@redshield
wg-quick down redshield || true
rm -f /etc/systemd/system/hr-bot-web.service.d/30-redshield-network.conf
rm -f /etc/systemd/system/hr-bot-worker.service.d/30-redshield-network.conf
systemctl daemon-reload
systemctl restart hr-bot-web hr-bot-worker
```

Перед удалением `/etc/wireguard/redshield.conf` убедиться, что есть рабочий альтернативный маршрут к Telegram или приватный proxy. Файл содержит secret key и не должен попадать в git, чат или логи.

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
