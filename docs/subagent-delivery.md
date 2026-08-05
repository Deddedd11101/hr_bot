---
title: Правила работы субагентов и stage integration
date: 2026-06-16
status: active
doc_type: runbook
area: deploy
related:
  - "[[stage-deploy]]"
  - "[[stage-change-log]]"
  - "[[project_state]]"
source_of_truth: true
---

# Правила работы субагентов и stage integration

Этот документ фиксирует рабочий процесс, когда несколько агентов параллельно меняют backend, frontend или bot runtime.

Главный принцип: субагент работает как обычный разработчик: готовит маленький проверенный change set в отдельной ветке и передает его на review/integration. Субагент не деплоит свою feature-ветку напрямую на общий stage. Интегратор собирает только reviewed changes в `stage` и запускает один deploy выбранного ref.

## Canonical worktrees

- `D:\HRBot\hr_bot_stage_pipeline` на ветке `stage` — единственный поддерживаемый локальный integration worktree для сборки `stage` и запуска deploy. Не использовать его как обычную рабочую папку субагента для feature-разработки.
- `D:\HRBot\hr_bot` — исторический dirty/rescue worktree. Не использовать его для новых задач, пока он явно не разобран и не очищен.
- Новая задача = новый clean worktree от `origin/stage` или от явно указанной dependency branch.
- После интеграции feature worktree удаляется или архивируется rescue-снимком. Dirty worktree не должен жить дольше одного integration cycle.

## Роли

### Субагент

Отвечает за одну задачу или компактный slice.

Обязательные действия:

1. начать с `git status --short`;
2. не трогать unrelated dirty changes;
3. создать отдельную feature-ветку от актуального `origin/stage`, если явно не задана другая dependency branch;
4. внести изменения в код и документацию;
5. запустить релевантные проверки;
6. закоммитить и запушить feature-ветку;
7. для нетривиальной задачи открыть draft PR в GitHub или минимум передать PR-ready handoff;
8. передать интегратору branch name, commit hash, список изменений и проверки.

Субагенту запрещено:

- пушить в чужую feature-ветку без явного согласования;
- делать `force push`, если это может стереть чужие коммиты;
- запускать `Deploy Stage` самостоятельно при параллельной работе;
- добавлять запись в `docs/stage-change-log.md` до фактического stage deploy;
- считать отсутствие интерактивного root SSH blocker-ом, если можно подготовить pushable ref.
- работать в `D:\HRBot\hr_bot` для новых задач без отдельного разрешения интегратора;
- работать в `D:\HRBot\hr_bot_stage_pipeline` как в feature-worktree без отдельного разрешения интегратора;
- оставлять задачу в состоянии "локально поправлено, но не закоммичено" без rescue/handoff.

### Reviewer

Отвечает за независимую проверку change set до integration.

Reviewer может быть интегратором или отдельным агентом, но review должен быть явно пройден для нетривиальных изменений.

Что проверять:

- diff scope соответствует задаче и не тащит unrelated файлы;
- backend/frontend/API contracts согласованы;
- есть релевантные тесты или обоснование, почему они не нужны;
- docs обновлены там, где меняется поведение, процесс или architecture;
- нет raw secrets, `.env`, локальных БД, временных артефактов;
- feature branch создана от правильной базы и не содержит старого dependency drift;
- если ветка старая, сначала выполнить readiness check/rebuild, а не merge "как есть".

### Интегратор

Отвечает за общий stage state.

Обязательные действия:

1. проверить, какие feature-ветки готовы и reviewed;
2. отвергнуть старые толстые ветки, если их смысл уже superseded by `origin/stage`;
3. для старых веток требовать fresh rebuild/cherry-pick на актуальный `origin/stage`;
4. собрать approved changes в `stage` или временную `integration/...`;
5. разрешить конфликты;
6. прогнать проверки на объединенном ref;
7. запушить `stage`;
8. запустить GitHub Actions `Deploy Stage` с `ref=stage`;
9. проверить smoke checks;
10. добавить запись в `docs/stage-change-log.md`;
11. после успешного deploy инициировать cleanup feature branch/worktree, если она больше не нужна.

## Ветки

- `main` — стабильная default branch, где лежит workflow и принятый baseline.
- `stage` — единственная supported integration branch для деплоя на тестовый стенд.
- `feature/<scope>` или `codex/<scope>` — ветка одной задачи.
- `integration/<name>` — временная ветка, если нужно собрать несколько задач отдельно от `stage`.

Не использовать одну и ту же feature-ветку для двух независимых агентов. Если два агента случайно работают в одной ветке, новый push может скрыть или перетереть работу другого.

`main` не является обычной deploy target для stage. В `main` должны попадать workflow/process/baseline изменения только после отдельной проверки. Красный `main` CI чинится маленьким отдельным change set, а не в составе feature cleanup.

## Откуда создавать ветку

Если задача не зависит от текущих незадеплоенных stage-изменений:

```bash
git fetch origin
git worktree add D:\HRBot\worktrees\my-task -b feature/my-task origin/stage
```

Если задача зависит от другой feature-ветки:

```bash
git fetch origin
git worktree add D:\HRBot\worktrees\my-task -b feature/my-task origin/feature/required-task
```

Перед финальным push желательно подтянуть актуальный `stage`:

```bash
git fetch origin
git merge origin/stage
```

Если merge создает конфликт, не угадывать. Разобрать конфликт по смыслу контракта backend/frontend и отметить это в handoff.

## PR-ready handoff

Шаблон:

```text
Не задеплоено: по параллельному workflow stage deploy не запускал.

branch: <branch>
commit: <short-or-full-sha>
PR: <draft PR URL or "не открыт">

Изменено:
- ...

Проверки:
- ...

Важно:
- unrelated dirty changes: <нет / список>
- conflicts/blockers: <нет / описание>
- docs updated: <список>
- base branch: <origin/stage / dependency>
- cleanup after merge: <worktree/branch можно удалить / оставить>
```

Фраза `Не задеплоено:` здесь не ошибка. Она означает, что субагент выполнил свою фазу и не стал ломать общий stage прямым deploy своей ветки.

## Review gate

Перед integration должно быть одно из двух:

- draft PR reviewed in GitHub;
- текстовый handoff reviewed интегратором или отдельным review-агентом.

Для маленьких правок интегратор может совмещать review и integration, но должен явно проверить diff scope и тесты.

Для старых веток из исторического стека запрещен прямой merge. Сначала:

1. classify branch: live / superseded / needs rebuild;
2. если live, rebuild from current `origin/stage`;
3. только потом review/integration.

## Как интегратор собирает stage

```bash
git fetch origin
git checkout stage
git pull --ff-only origin stage
git merge --no-ff origin/feature/task
```

Если feature branch старая или содержит лишнюю историю, вместо merge использовать fresh branch/cherry-pick конкретных commits или ручной rebuild.

После merge:

```bash
python -m compileall app tests tools
ruff check --select F821 app tests
python -m unittest tests.test_scenario_engine_smoke tests.test_messaging_identity tests.test_employee_api_smoke -v
cd frontend
npm run build
```

Затем:

```bash
git push origin stage
```

В GitHub Actions:

- `Use workflow from`: `main`
- `Git ref to deploy to stage`: `stage`

## Почему нельзя деплоить feature-ветки по очереди

Stage deploy переключает сервер на весь выбранный git ref. Если сначала выкатить `feature/backend-task`, а потом `feature/frontend-task`, второй deploy заменит сервер на код frontend-ветки. Backend-изменения останутся только если frontend-ветка уже содержит backend commit.

Поэтому общий stage ref должен быть один: `stage` или согласованный `integration/...`.

## Когда можно деплоить не `stage`

Только осознанно:

- срочная диагностика конкретного commit SHA;
- временный `integration/...` ref для крупного связанного изменения;
- rollback на известный commit.

В таком случае в `docs/stage-change-log.md` нужно явно написать, какой ref был выведен и почему это не `stage`.

## Cleanup after deploy

После successful deploy:

1. убедиться, что feature содержательно в `origin/stage`;
2. если feature больше не нужна, удалить clean feature worktree;
3. удалить local branch;
4. после подтверждения удалить remote branch;
5. не удалять dirty worktree без rescue snapshot;
6. не удалять ветки с живыми идеями, если они ждут отдельного rebuild/decision.

Фича считается завершенной не после локального diff, а после:

- reviewed branch/commit;
- integration в `stage`;
- successful `Deploy Stage`;
- smoke checks;
- запись в `docs/stage-change-log.md`;
- cleanup/decision по feature branch.
