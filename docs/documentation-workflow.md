---
title: Workflow документирования HR Bot
date: 2026-08-05
status: active
doc_type: standard
area: docs
task_tokens:
  - HRB-DOC-03
related:
  - "[[documentation-standard]]"
  - "[[inventory]]"
  - "[[backlog]]"
  - "[[project_state]]"
source_of_truth: true
---

# Workflow документирования

Этот файл фиксирует практический gate: когда документацию надо обновлять, когда не надо, и куда именно писать. Он нужен, чтобы docs не превращались в ритуал для каждой мелкой правки.

## Базовое правило

Документировать нужно изменение контракта, состояния проекта или операционного процесса. Не нужно документировать каждый diff.

Если правка не меняет контракт и не создает новый риск, она не требует отдельной записи в `docs/`.

## Не документировать

Обычно не требуют docs:

- мелкие CSS/styling правки без изменения layout contract или shared UI API;
- исправление отступов, цвета, hover state, текста кнопки или label;
- локальный refactor без изменения public/internal behavior;
- добавление теста без изменения поведения;
- переименование локальной переменной, cleanup imports, formatter output;
- пересборка frontend assets без изменения исходного contract.

Исключение: если такая мелкая правка закрывает documented bug/risk или меняет reusable pattern, обновить соответствующий doc.

## Документировать

Обновить docs обязательно, если изменился хотя бы один пункт:

- JSON API route, payload, auth/error behavior или frontend fetch contract;
- non-JSON web route, redirect, download/export или classic fallback behavior;
- DB model, startup schema guard, migration/drift handling или storage layout;
- env variable, secret, config precedence, deploy workflow, smoke check или rollback path;
- bot identity/linking, menu targeting, scenario runtime, scheduler timing или notification semantics;
- employee/candidate lifecycle, legal/data boundary, roles/access model;
- shared UI primitive API, page composition rule, design-system baseline;
- task status, priority, blocker or accepted product/architecture decision;
- stage deploy/config/db/infra state.

## Куда писать

| Изменение | Куда обновлять |
| --- | --- |
| Runtime topology, module ownership, major subsystem boundary | [[architecture]] |
| `/api/*` contract | [[api]] |
| Browser route, classic form, redirect, download/export | [[web-surface]] |
| DB table/field/schema guard/storage | [[data-model]] |
| Env/config/secrets/defaults | [[configuration]] |
| Local run commands/checks | [[local-runbook]] |
| GitHub Actions/stage deploy/smoke/rollback | [[stage-deploy]] |
| Факт выкатки или ручного stage change | [[stage-change-log]] |
| Feature behavior | `docs/features/<feature>.md` |
| Task status/priority | [[backlog]] |
| Current risks/priorities | [[project_state]] |
| Принятое или отмененное значимое решение | `docs/decisions/<date>-<slug>.md` |
| Контекст передачи незавершенной работы | `docs/handoffs/<slug>.md` |

Не дублировать факт во всех местах. Live doc хранит контракт; `project_state` хранит только практическое состояние и риск; `backlog` хранит статус задачи.

## Решения

ADR нужен, когда выбранный путь будет важен через месяц:

- выбрали модель identity, lifecycle, data isolation, deploy, auth, UI foundation;
- отказались от альтернативы, которую могут снова предложить;
- изменили прежний подход.

ADR не нужен для “поправили баг” или “передвинули кнопку”.

## Handoff

Handoff нужен только если после работы останется контекст, который нельзя быстро восстановить из live docs и git diff:

- работа прервана на середине;
- есть важные локальные проверки, ветка, блокер, stage observation;
- есть несколько связанных change slices, которые следующий агент должен продолжить осторожно.

Handoff не является source of truth. Если в handoff появился актуальный контракт, перенести его в live doc.

## Daily

Daily notes не являются обязательным рабочим циклом.

Использовать daily только для насыщенного операционного дня, когда важно восстановить последовательность событий: stage incident, ручной repair, несколько связанных решений, анализ с внешним участником.

Для обычных доработок daily не вести. Это уже показало себя как шумный формат, который легко начать и быстро забросить.

## Google Docs Review Copies

Google Docs можно использовать как review-копию для коллег, но не как отдельный source of truth.

Правило:

1. Markdown-файл в `docs/` остается каноном.
2. Google Doc используется для комментариев, бизнес-правок и согласования формулировок.
3. В Markdown-документе можно держать ссылку на review-копию, если она реально используется командой.
4. После правок коллег документовед читает Google Doc, комментарии и при необходимости revision history.
5. Документовед переносит только подтвержденные изменения обратно в git-документ.
6. Если правка в Google Doc противоречит коду, БД, stage или live docs, она не переносится автоматически: сначала фиксируется вопрос владельцу продукта.
7. После переноса изменений в `docs/` обязательно запускается docs-check.

Не делать:

- не считать Google Doc каноном;
- не принимать массовые правки из Google Doc без сверки с кодом/БД;
- не держать разные “финальные версии” в Google Doc и git;
- не создавать отдельный Google Doc для каждой мелкой правки.

Для сценарных бизнес-документов текущая модель такая: Google Doc — место командного review, `docs/features/scenario-catalog.md` — git-backed документ, который становится source of truth только после утверждения содержания и смены `source_of_truth` на `true`.

## Stage

Если изменение выведено на stage, запись в [[stage-change-log]] обязательна независимо от размера изменения.

Если изменение не выведено на stage, нельзя писать его в [[stage-change-log]] как готовую поставку. Использовать [[backlog]], [[project_state]] или handoff, если контекст реально нужен.

## Минимальный агентский алгоритм

1. Перед работой прочитать [[project_state]], [[backlog]], [[inventory]] и нужный live doc по области.
2. После правок спросить себя: изменился ли contract из раздела “Документировать”.
3. Если нет, не создавать docs.
4. Если да, обновить ровно один основной live doc и только нужные secondary docs.
5. Если принято решение, добавить ADR.
6. Если выкатили stage, добавить [[stage-change-log]].
7. Если продолжение нетривиально, добавить handoff.

## Автоматическая проверка

После изменений в docs, API routes, config vars или SQLAlchemy models запускать:

```powershell
cd D:\HRBot\hr_bot
.\.venv\Scripts\python.exe tools\check_docs_contracts.py
```

Скрипт проверяет:

- обязательный frontmatter у Markdown-файлов в `docs/`;
- битые wiki-links;
- что ADR используют `doc_type: adr`, а handoff не являются `source_of_truth`;
- что selected `/api/*`, `/app/*`, `/documents*`, `/design-system*` routes отражены в [[api]] или [[web-surface]];
- что env vars из `app/config.py` отражены в [[configuration]] и `.env.example`;
- что SQLAlchemy tables из `app/models.py` отражены в [[data-model]].

Это sanity-check, а не замена инженерного ревью: он ловит пропуски, но не доказывает полноту описания поведения.

Финальный ответ агента должен явно пересказать результат:

- если проверка прошла: указать команду и `passed`;
- если проверка сначала падала: указать, что именно было исправлено, и что повторный запуск прошел;
- если проверка осталась красной: начать финал с `Не задеплоено:` и привести ошибки проверки или причину, почему их нельзя исправить в текущей задаче.
