# AGENTS.md

## Working Style

- Подвергать критике и сомнению решения, а не принимать их автоматически.
- Предлагать более верные альтернативы, если текущий путь слабый, рискованный или избыточный.
- Задавать наводящие вопросы, когда от ответа зависит архитектура, продуктовая логика или порядок работ.

## Documentation Discipline

Для проекта `D:\HRBot\hr_bot` документация в `docs/` является рабочим source of truth и должна обновляться вместе со значимыми изменениями.

Пути `D:\HRBot\...` ниже описывают текущую локальную рабочую раскладку. Если репозиторий передан или клонирован в другое место, применять те же правила относительно корня текущего checkout; не считать абсолютный путь частью продуктового контракта.

Перед созданием или обновлением docs читать:

- `D:\HRBot\hr_bot\docs\documentation-workflow.md` — практический gate, когда docs нужны, когда не нужны, и куда писать;
- `D:\HRBot\hr_bot\docs\inventory.md` — классификация live, historical и drift-prone документов;
- `D:\HRBot\hr_bot\docs\documentation-standard.md` — frontmatter, doc types и Obsidian/wiki-link rules.

Документировать нужно изменение контракта, состояния проекта или операционного процесса, а не каждый diff. Мелкие CSS/copy/refactor правки без изменения поведения, API, schema, env, deploy, bot/runtime semantics или shared UI contract обычно docs не требуют.

После значимых изменений в коде, архитектуре, процессе или статусе работ нужно:

- обновлять `D:\HRBot\hr_bot\docs\backlog.md`, если изменилась задача, ее статус или приоритет;
- обновлять `D:\HRBot\hr_bot\docs\project_state.md`, если изменилось текущее состояние системы, риски или ближайшие приоритеты;
- обновлять `D:\HRBot\hr_bot\docs\architecture.md`, `docs\api.md`, `docs\web-surface.md`, `docs\data-model.md`, `docs\configuration.md`, `docs\stage-deploy.md` или нужный файл в `D:\HRBot\hr_bot\docs\features\`, если изменился соответствующий contract;
- обновлять `D:\HRBot\hr_bot\docs\stage-change-log.md`, если изменение выведено на тестовый/stage стенд;
- добавлять запись в `D:\HRBot\hr_bot\docs\decisions\`, если принято, изменено или отменено значимое решение;
- обновлять или добавлять файл в `D:\HRBot\hr_bot\docs\handoffs\` только если после работы нужен устойчивый контекст для продолжения beyond live docs and git diff.

Daily notes не являются обязательным процессом. Использовать `docs\daily\` только для насыщенного operational day: stage incident, ручной repair, несколько связанных решений или внешний operational context.

После изменений в docs, API routes, config vars или SQLAlchemy models запускать:

```powershell
cd D:\HRBot\hr_bot
.\.venv\Scripts\python.exe tools\check_docs_contracts.py
```

Если `.venv` недоступен и скрипт не требует зависимостей, допустимо временно использовать `python tools\check_docs_contracts.py`, но в финальном ответе указать фактическую команду.

Финальный ответ агента после таких изменений обязан явно указать результат docs-check:

- если проверка прошла: `Docs check: .\.venv\Scripts\python.exe tools\check_docs_contracts.py — passed`;
- если проверка сначала падала, но была исправлена: кратко указать причину первого падения, что обновлено, и что повторный запуск прошел;
- если проверка не прошла к концу работы: финальный ответ начинать с `Не задеплоено:` и привести ошибки проверки или причину, почему агент не смог их исправить.

Не считать обновление документации необязательной финальной косметикой. Если изменение заметное и проходит gate из `documentation-workflow.md`, документация должна быть приведена в актуальное состояние в рамках той же работы.

## Delivery Discipline

Новая рабочая модель: доработки не копить только локально и не считать завершенными после локального git-состояния. Если задача предполагает изменение приложения, конечная точка работы — проверенная выкладка на тестовый/stage стенд через неинтерактивный deploy path или явная фиксация блокера, почему выкладка невозможна.

Перед началом работы:

- выбрать правильный worktree:
  - `D:\HRBot\hr_bot_stage_pipeline` использовать только для integration/stage-сборки и deploy;
  - `D:\HRBot\hr_bot` считать historical dirty/rescue worktree и не использовать для новых задач без отдельного разрешения интегратора;
  - обычную новую задачу начинать в отдельном clean worktree от `origin/stage` или от явно указанной dependency branch;
- в выбранном worktree выполнить `git status --short`;
- не затирать и не откатывать чужие изменения;
- если в рабочем дереве есть unrelated changes, не трогать их и явно отметить в ответе;
- прочитать актуальный operational context в docs выбранного worktree: `docs\project_state.md`, `docs\backlog.md` и, если затронут stage/deploy/bot, `docs\stage-deploy.md`.

Стандартный цикл для доработки:

1. Внести минимальные изменения в код и документацию.
2. Запустить релевантные локальные проверки.
3. Если проверки прошли и работа не параллелится с другими feature-ветками, выкатить изменение на тестовый/stage стенд через GitHub Actions `Deploy Stage`.
4. После выкладки выполнить stage smoke checks.
5. Добавить запись в `D:\HRBot\hr_bot\docs\stage-change-log.md`.
6. Только после этого сообщать, что задача готова.

Субагенты не должны деплоить через интерактивный root SSH или просить пароль. Нормальный deploy path:

- подготовить отдельную ветку/commit только со своими изменениями;
- push ветки в GitHub;
- при параллельной работе остановиться на feature-ветке и передать branch/commit/checks интегратору;
- интегратор вливает изменения в общую накопительную ветку `stage` или согласованную `integration/...` ветку;
- интегратор запускает GitHub Actions workflow `Deploy Stage` с `ref=stage` или другим согласованным integration ref; workflow сам выполнит preflight checks перед SSH;
- дождаться успешных smoke checks в workflow.

Фактическое repo-backed поведение `Deploy Stage`, которое нельзя игнорировать в рассуждениях:

- deploy job перед checkout останавливается, если stage worktree грязный; это не обходить `git reset --hard` без отдельного разбора источника drift;
- при `workflow_dispatch` `ref` может быть branch, tag или commit SHA;
- на сервере workflow сначала делает `git fetch --prune origin`, затем если существует `origin/<ref>`, checkout идет именно в `origin/<ref>`, иначе используется переданный raw ref.

`Deploy Stage` не должен auto-deploy `main`. Обычный ref для тестового стенда — `stage`. `main` хранит baseline и workflow, но не является автоматическим deploy ref при параллельной работе.

TODO: repo-backed reality на 2026-06-29 пока другая: `.github/workflows/deploy-stage.yml` все еще автозапускает `Deploy Stage` после успешного `CI` на `main`, а ручной `workflow_dispatch` по умолчанию подставляет `ref=main`. До отдельного изменения workflow это считать фактическим поведением и не предполагать, что stage-only deploy уже enforced кодом.

Не деплоить на общий stage разрозненные feature-ветки одну за другой, если нужно сохранить предыдущие изменения. Stage переключается на весь выбранный git ref целиком: deploy `feature/frontend-x` после deploy `feature/backend-y` уберет backend-y со стенда, если frontend-x не содержит этот commit.

Правило накопления:

- `feature/...` ветка — место работы конкретного агента;
- `stage` или `integration/...` ветка — единственный ref для последовательных выкаток на тестовый стенд;
- `D:\HRBot\hr_bot_stage_pipeline` не является рабочей папкой субагента для feature-разработки; это локальный integration worktree;
- `D:\HRBot\hr_bot` не является рабочей папкой для новых задач, пока dirty/rescue состояние явно не разобрано;
- нельзя давать двум независимым субагентам одну feature-ветку; новая задача должна получать новую ветку от `origin/stage` или от явно указанной dependency branch;
- перед deploy следующей доработки нужно merge/rebase актуальный `stage` в feature или merge feature в `stage`;
- если frontend и backend меняют общий API/static contract, деплоить только integration branch, где обе стороны уже вместе.

Commit messages должны следовать формату из `docs\subagent-delivery.md`: `<type>(<scope>): <сообщение>`, где `type` один из `feat`, `fix`, `refactor`, `docs`, `style`, `test`, `chore`, `perf`, `ci`, `revert`; сообщение на русском, в повелительном наклонении, без точки в конце. Не смешивать unrelated изменения в одном коммите.

Если рабочее дерево грязное и содержит чужие изменения, нельзя катить весь diff на stage без ревью. Нужно изолировать свои изменения в отдельную ветку/commit, влить их в `stage`/integration ref либо явно остановиться с `Не задеплоено:`.

Отсутствие интерактивного SSH-доступа у субагента не является блокером, если GitHub Actions deploy доступен. Блокером считается только невозможность подготовить/push ref или недоступность workflow/secrets.

Минимальные локальные проверки:

- backend: `python -m compileall app`;
- backend smoke: `python -m unittest tests.test_scenario_engine_smoke tests.test_messaging_identity tests.test_employee_api_smoke -v`;
- если менялся frontend: из `D:\HRBot\hr_bot\frontend` выполнить `npm run build`;
- если менялись docs/API routes/config/models: `.\.venv\Scripts\python.exe tools\check_docs_contracts.py`;
- если менялся бот, Telegram identity, scenario runtime или delivery, дополнительно смотреть worker logs и Telegram delivery на stage.

Минимальные stage smoke checks после deploy:

- `systemctl status hr-bot-web --no-pager`;
- `systemctl status hr-bot-worker --no-pager`;
- `systemctl is-active wg-quick@redshield hr-bot-web hr-bot-worker`;
- `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/app/employees`;
- `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/app/flows/workspace-v2`.

Если затронут Telegram:

- проверить `curl -4 -I --connect-timeout 10 https://api.telegram.org/`;
- если есть timeout при живом `curl -4`, дополнительно проверить `curl -6 -I --connect-timeout 10 https://api.telegram.org/` и `getent ahosts api.telegram.org`;
- проверить `wg show redshield`;
- при диагностике selective route дополнительно проверить `ip route get 149.154.166.110`;
- проверить `journalctl -u hr-bot-worker --since "5 minutes ago" --no-pager -n 100`;
- убедиться, что нет свежих `TelegramNetworkError`, `Request timeout`, `Traceback`, `Unclosed client session`.

Stage-specific правила:

- Stage server: `root@92.51.38.32`, app dir: `/opt/hr_bot`.
- Telegram на stage зависит от WireGuard selective route `wg-quick@redshield`.
- Не отключать `wg-quick@redshield` без явной причины.
- Не менять WireGuard `AllowedIPs` на `0.0.0.0/0` или `::/0`; full tunnel может сломать SSH и публичный web.
- Перед рискованными изменениями базы делать backup: `cd /opt/hr_bot && mkdir -p backups && cp -a hr_bot.db "backups/hr_bot.before-change.$(date +%Y%m%d-%H%M%S).db"`.
- Web и worker должны использовать один и тот же Telegram bot token.
- Не менять Telegram token, root credentials, WireGuard config или systemd secrets без явной причины и без фиксации в operational docs.
- Не использовать root password как обычный deploy mechanism для субагентов. SSH-доступ к stage должен идти через GitHub Actions secrets или заранее настроенный неинтерактивный ключ.

Финальный ответ субагента:

- если stage deploy сделан: указать, что изменено, какие локальные проверки прошли, что именно выкачено на stage, результаты stage smoke checks и запись в `stage-change-log.md`;
- если stage deploy не сделан: начать ответ с `Не задеплоено:` и явно указать причину, оставшиеся команды/действия и риск для пользователя;
- если запускался `tools\check_docs_contracts.py`: явно указать команду и итог проверки; при failure привести ошибки или объяснить, что было исправлено перед повторным successful run.

## Verified Local Workflows

- Канонический локальный integration worktree: `D:\HRBot\hr_bot_stage_pipeline`.
- Historical dirty/rescue worktree: `D:\HRBot\hr_bot`; не использовать для новых задач без отдельного решения интегратора.
- Feature-разработку вести в отдельном clean worktree, обычно под `D:\HRBot\worktrees\<task-name>`, созданном от `origin/stage` или от явно указанной dependency branch.
- Для первичного локального bootstrap backend-окружения: `python -m venv .venv`.
- После создания `.venv` ставить backend-зависимости командой `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
- Для первичного локального bootstrap frontend-зависимостей переходить в `D:\HRBot\hr_bot\frontend` и выполнять `npm install`.
- Базовый запуск админки: `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
- После backend-изменений не полагаться на уже запущенный локальный `uvicorn`: сначала перезапускать процесс, иначе старый backend может принимать новый frontend payload по старому contract и создавать ложные UI-регрессии.
- Отдельный запуск bot worker: `.\.venv\Scripts\python.exe -m app.bot_runner`.
- Для быстрого локального демо допустимо включать `DEMO_MODE=true`, `DEMO_STEP_MINUTES=1`, `MANUAL_STEP_MINUTES=1`, но не считать этот режим обычной проверкой: он меняет semantics scheduler и может скрывать timing bugs.
- Если менялся `frontend/src`, пересобирать frontend из `D:\HRBot\hr_bot\frontend` командой `npm run build`; для обычной проверки админки Vite dev server поднимать не нужно. Если build падает только на unrelated import errors внутри `frontend/src/design-system/*`, фиксировать это как cross-track blocker, а не приписывать автоматически измененному feature slice.
- Если работа затрагивает shared UI, shadcn-компоненты или page composition, перед правками из `D:\HRBot\hr_bot\frontend` сначала выполнять `npx shadcn@latest info --json`, затем `npx shadcn@latest docs <component>`, сверять локальный `frontend/src/components/ui/*`, и только потом менять live page. Если нужного компонента нет или есть сомнение по diff, сначала использовать `npx shadcn@latest search <query>`, затем `npx shadcn@latest add <component> --dry-run`, и только потом `--diff` или реальное обновление.
- `--reload` для uvicorn не считать основной командой проекта; использовать только как optional dev-mode, если он стабилен в текущем окружении.
- Если менялся backend-код, минимальная локальная проверка, совпадающая с текущим CI: `python -m compileall app`, `ruff check --select F821 app tests`, `python -m unittest tests.test_scenario_engine_smoke tests.test_messaging_identity tests.test_employee_api_smoke -v`.
- Для точного локального повтора backend smoke/import checks из GitHub Actions использовать те же env-переменные, что и в workflow: `TELEGRAM_BOT_TOKEN=ci-dummy-token`, `DATABASE_URL=sqlite:///./ci.db`, `ADMIN_SESSION_SECRET=ci-admin-session-secret`.
- Если работа затрагивает scenario workspace, Telegram linking или ветвление сценариев, использовать расширенную локальную проверку: `python -m compileall app tests tools`, `python -m unittest tests.test_employee_api_smoke tests.test_messaging_identity tests.test_scenario_engine_smoke tests.test_scenario_engine_branching -v`, `npm run build` в `D:\HRBot\hr_bot\frontend`.
- Если нужно повторить frontend-часть preflight именно как в `Deploy Stage`, использовать в `D:\HRBot\hr_bot\frontend` команду `npm ci`, затем `npm run build`, а не считать локальный `npm install` эквивалентом CI/deploy проверки.
- Если нужно локально воспроизвести deploy checkout semantics для stage, не придумывать свои git-шаги: workflow на сервере делает `git fetch --prune origin`, затем проверяет `origin/<ref>` и выполняет `git checkout -B stage-deploy <target_ref>`.
- Если нужно локально воспроизвести именно HTTP stage smoke из `Deploy Stage`, использовать `curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 http://127.0.0.1:8000/app/employees` и `curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 http://127.0.0.1:8000/app/flows/workspace-v2`; ожидать `200` или `303`, а не только `200`.
- Если работа затрагивает перенос сценариев между локальной/stage SQLite-базой, использовать `.\.venv\Scripts\python.exe tools\scenario_portability.py export --db <source.db> --out <export_dir> --scenario-key <scenario_key>` и `.\.venv\Scripts\python.exe tools\scenario_portability.py import --db <target.db> --in <export_dir> --storage-root storage\scenario_step_files`; переносить сценарии по `scenario_key`, а не через замену всей БД.
- Перед ручным импортом stage SQLite-базы, заменой `hr_bot.db` или массовыми scenario edits на stage сначала делать backup на сервере: `cd /opt/hr_bot`, `mkdir -p backups`, `ts=$(date +%Y%m%d-%H%M%S)`, `cp -a hr_bot.db "backups/hr_bot.before-change.$ts.db"`.
- Для локальной диагностики stage-состояния сначала забирать копию базы командой `scp root@92.51.38.32:/opt/hr_bot/hr_bot.db D:\HRBot\hr_bot\stage_after_analytics.db`; если нужны только сценарии, предпочитать scenario portability workflow вместо полной замены локальной БД.
- После stage deploy, ручного stage restart или рискованных stage-изменений проверять сервисы командами `systemctl status hr-bot-web --no-pager` и `systemctl status hr-bot-worker --no-pager`, а затем делать HTTP smoke check на сервере: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/app/flows/workspace-v2`, `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/app/employees`, `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/app/employees/1`; ожидать `200` или auth redirect, а не connection refused.
- Если переустанавливался или перенастраивался WireGuard route к Telegram, после restart дополнительно проверять `systemctl is-enabled wg-quick@redshield hr-bot-web hr-bot-worker` и `ip route get 149.154.166.110`.
- Если `GET /api/employees/{id}` падает на локальной или stage-копии SQLite-базы, сначала проверять совместимость схемы и payload через `.\.venv\Scripts\python.exe tools\check_employee_detail_db.py --database-url sqlite:///./hr_bot.db --probe-payload`; при точечной диагностике добавлять `--employee-id <id>`.
- Для полного повтора backend-checks из текущего CI отдельно прогонять smoke import: `python -c "from app.config import settings; assert settings.TIMEZONE"`, `python -c "from app.main import app; assert app is not None"`, `python -c "from app.bot_runner import main; assert main is not None"`.
- Для автоматической проверки документации запускать `.\.venv\Scripts\python.exe tools\check_docs_contracts.py`; скрипт проверяет обязательный frontmatter, wiki-links, отсутствие `doc_type: decision`, что handoff не являются source of truth, покрытие выбранных routes в `api.md`/`web-surface.md`, config vars в `configuration.md`/`.env.example` и SQLAlchemy tables в `data-model.md`.
