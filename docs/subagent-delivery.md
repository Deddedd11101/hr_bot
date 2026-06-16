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

Главный принцип: субагент не деплоит свою feature-ветку напрямую на общий stage. Он готовит проверенную ветку. Интегратор собирает нужные ветки в `stage` и запускает один deploy выбранного ref.

## Роли

### Субагент

Отвечает за одну задачу или компактный slice.

Обязательные действия:

1. начать с `git status --short`;
2. не трогать unrelated dirty changes;
3. создать отдельную feature-ветку;
4. внести изменения в код и документацию;
5. запустить релевантные проверки;
6. закоммитить и запушить feature-ветку;
7. передать интегратору branch name, commit hash, список изменений и проверки.

Субагенту запрещено:

- пушить в чужую feature-ветку без явного согласования;
- делать `force push`, если это может стереть чужие коммиты;
- запускать `Deploy Stage` самостоятельно при параллельной работе;
- добавлять запись в `docs/stage-change-log.md` до фактического stage deploy;
- считать отсутствие интерактивного root SSH blocker-ом, если можно подготовить pushable ref.

### Интегратор

Отвечает за общий stage state.

Обязательные действия:

1. проверить, какие feature-ветки готовы;
2. собрать их в `stage` или `integration/...`;
3. разрешить конфликты;
4. прогнать проверки на объединенном ref;
5. запушить `stage`;
6. запустить GitHub Actions `Deploy Stage` с `ref=stage`;
7. проверить smoke checks;
8. добавить запись в `docs/stage-change-log.md`.

## Ветки

- `main` — стабильная default branch, где лежит workflow и принятый baseline.
- `stage` — накопительная ветка тестового стенда.
- `feature/<scope>` или `codex/<scope>` — ветка одной задачи.
- `integration/<name>` — временная ветка, если нужно собрать несколько задач отдельно от `stage`.

Не использовать одну и ту же feature-ветку для двух независимых агентов. Если два агента случайно работают в одной ветке, новый push может скрыть или перетереть работу другого.

## Откуда создавать ветку

Если задача не зависит от текущих незадеплоенных stage-изменений:

```bash
git fetch origin
git checkout -b feature/my-task origin/stage
```

Если задача зависит от другой feature-ветки:

```bash
git fetch origin
git checkout -b feature/my-task origin/feature/required-task
```

Перед финальным push желательно подтянуть актуальный `stage`:

```bash
git fetch origin
git merge origin/stage
```

Если merge создает конфликт, не угадывать. Разобрать конфликт по смыслу контракта backend/frontend и отметить это в handoff.

## Что субагент пишет в конце

Шаблон:

```text
Не задеплоено: по параллельному workflow stage deploy не запускал.

branch: <branch>
commit: <short-or-full-sha>

Изменено:
- ...

Проверки:
- ...

Важно:
- unrelated dirty changes: <нет / список>
- conflicts/blockers: <нет / описание>
- docs updated: <список>
```

Фраза `Не задеплоено:` здесь не ошибка. Она означает, что субагент выполнил свою фазу и не стал ломать общий stage прямым deploy своей ветки.

## Как интегратор собирает stage

```bash
git fetch origin
git checkout stage
git pull --ff-only origin stage
git merge --no-ff origin/feature/backend-task
git merge --no-ff origin/feature/frontend-task
```

После merge:

```bash
python -m compileall app
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
