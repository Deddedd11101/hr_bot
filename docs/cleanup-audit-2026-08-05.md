---
title: Cleanup audit 2026-08-05
status: active
doc_type: audit
area: operations
task_tokens: []
related:
  - "[[project_state]]"
  - "[[inventory]]"
  - "[[documentation-workflow]]"
source_of_truth: false
---

# Cleanup audit 2026-08-05

Цель ревизии: найти лишние файлы и папки, которые утяжеляют рабочую копию или создают шум, но ничего не удалять без отдельного подтверждения.

## Короткий вывод

Главный cleanup-кандидат сейчас не код, а локальные артефакты проверок:

- `.edge-debug/` - около 438 MB, локальный профиль Edge/браузерный cache, уже игнорируется git.
- `.codex-artifacts/` - около 14.8 MB, не отслеживается git и не игнорируется явно; почти целиком состоит из visual QA/watchdog screenshots.
- временные базы, логи и скриншоты в корне - небольшие, но шумят в рабочей копии и в будущих ревизиях.

Важный анти-кандидат: `app/static/workspace_v2/` выглядит как generated output, но сейчас это часть текущего deploy/runtime contract. `frontend/vite.config.ts` собирает Vite build прямо туда, templates и smoke tests проверяют эти файлы. Удалять эту папку как мусор нельзя, пока не изменена схема сборки/deploy.

Удалять все одним проходом не стоит. В проекте рядом лежат три разных типа файлов:

- воспроизводимый cache/debug output, который можно убрать сразу;
- локальные smoke/test артефакты, которые лучше сначала заигнорировать, потом удалить;
- runtime/user/stage data, где нужен отдельный retention policy.

Практичный порядок: сначала `.gitignore` hardening, потом safe cleanup, потом отдельный data cleanup. Это даст быстрый выигрыш по весу рабочей копии и не смешает безобидную чистку с риском потерять полезный snapshot.

## Safe cleanup candidates

Эти элементы можно удалить локально после подтверждения. Они не должны попадать в commit.

| Path | Size | Git status | Почему кандидат |
| --- | ---: | --- | --- |
| `.edge-debug/` | ~438 MB | ignored | Локальный профиль браузера, cache, DB/WAL/логи. Не является runtime data проекта. |
| `.codex-artifacts/visual-qa*` | ~14.2 MB | untracked | Датированные screenshots/contact sheets старого visual QA/watchdog. Пользователь подтвердил, что watchdog отключен и screenshots не несут ценности. |
| `tmp_bulk_desktop.png`, `tmp_bulk_tablet.png` | ~0.2 MB | ignored | Разовые screenshots. |
| `tmp_*uvicorn*.log`, `bot*.log`, `local_bot*.log` | ~0.2 MB | ignored | Локальные логи запусков, не source of truth. |
| `.tmp_pycache/` | ~1 MB | ignored | Перенаправленный Python bytecode cache, воспроизводим. |
| `.ruff_cache/` | ~0.13 MB | untracked/ignored by tool convention, but not covered in `.gitignore` | Cache линтера. Лучше игнорировать явно. |

Рекомендуемое техническое действие перед удалением: добавить в `.gitignore` явные правила для `.codex-artifacts/`, `.ruff_cache/`, `ci.db`, `*.db-wal`, `*.db-shm`, `*.db-journal`.

Эти файлы можно чистить батчем A. Ожидаемый эффект: примерно 454 MB сразу, почти весь выигрыш по размеру.

## Review before delete

Эти элементы могут быть лишними, но удалять их без решения по данным рискованно.

| Path | Size | Почему не удалять сразу |
| --- | ---: | --- |
| `stage_snapshots/20260506-114634/` | ~1.65 MB | Содержит `storage.tar.gz` и `hr_bot.db`. Это старый stage snapshot; можно удалить только если rollback/forensics уже не нужны. |
| `backups/*.db` | ~1.03 MB | Старые DB backups. Нужна retention policy: например хранить последние N или только последние 30/60 дней. |
| `hr_bot.before_clean_runtime_20260411_005258.db` | ~0.30 MB | Старый local backup в корне. Кандидат на удаление или перенос в `backups/`, но сначала подтвердить, что он не нужен. |
| `stage_copy.db`, `stage_copy.before_employee_cleanup_20260411_000200.db` | ~0.49 MB | Stage copies могут быть полезны для сравнения миграций и payload. Удалять только после подтверждения, что текущий stage analysis завершен. |
| `ci.db` | ~0.31 MB | Test DB, скорее всего удаляемый артефакт. Но сейчас он не игнорируется, поэтому лучше сначала добавить ignore. |
| `.codex-artifacts/verification/*.db` | ~0.53 MB | Test DB внутри verification. Можно удалить вместе с `.codex-artifacts/`, если не нужен недавний smoke context. |
| `exports/saved_scenarios_20260506/` | ~0.26 MB | Экспорт сценариев. Это может быть seed/backup material, не просто cache. |
| `storage/media_library/` | ~1 MB | Runtime media. Часть файлов похожа на тестовые картинки, но сама папка является продуктовым storage. |
| `storage/scenario_step_files/` | ~0.66 MB | Runtime files сценариев, завязаны на DB records. Нельзя чистить файлово без проверки ссылок из базы. |
| `storage/employee_files/` | ~1.58 MB | Документы сотрудников/кандидатов. Не cleanup-кандидат без отдельной data retention задачи. |

Эти файлы нельзя смешивать с батчем A. Для них нужен батч B/C:

- батч B: старые локальные DB/snapshots после подтверждения, что rollback/history не нужны;
- батч C: storage retention только через проверку ссылок из DB или отдельное продуктовое решение, какие вложения считаются disposable.

## Not cleanup candidates

Эти вещи могут быть крупными или шумными, но сейчас считаются живой частью проекта.

| Path | Evidence |
| --- | --- |
| `app/static/workspace_v2/` | `frontend/vite.config.ts` использует `outDir: ../app/static/workspace_v2`; templates грузят `/static/workspace_v2/*.js`; tests проверяют наличие этих ссылок. |
| `app/templates/scenario_edit.html` | Большой legacy template, но route еще рендерит его как explicit `?legacy=1` fallback. Удалять только после закрытия remaining nested update parity. |
| `app/templates/react_*.html`, `react_base.html`, `login.html`, `base.html` | Все имеют живые route references или template inheritance. |
| `frontend/package-lock.json` | Нужен для воспроизводимой установки frontend dependencies. |
| `docs/handoffs/frontend-structure-reset-handoff.md` | Большой исторический handoff, содержит устаревшие screenshot/check notes, но уже классифицирован как history, не current contract. Можно позже архивировать/сжать, но не удалять как мусор. |
| `docs/.obsidian/` | Локальная Obsidian конфигурация, уже ignored. Можно удалить локально, если Obsidian не используется, но это не repo cleanup. |

## Documentation cleanup candidates

Документация уже разделена на live source of truth и history. Поэтому cleanup здесь должен быть не удалением фактов, а снижением шума:

- `docs/daily/` не вести как обязательный ритуал. Старые daily оставить как history.
- `docs/templates/daily-template.md` оставить, но считать optional-only. Он уже говорит, что daily нужен только для насыщенного operational day.
- `docs/handoffs/frontend-structure-reset-handoff.md` слишком большой и содержит много step-by-step проверок. Позже можно пометить как archived/history и вынести актуальные факты только в live docs, если такие еще остались.
- `docs/demo-day-brief-2026-05-12.md` и `docs/roadmap-2026-05-12.md` оставить как dated snapshots. Не использовать как текущий план.

Удалять historical docs сейчас не рекомендую. С точки зрения веса они почти ничего не дают: весь `docs/` без `.obsidian` маленький по сравнению с `.edge-debug/`. С точки зрения риска удаление handoff/history может ухудшить восстановление контекста. Здесь полезнее маркировка и дисциплина чтения: live docs первичны, handoffs/daily только история.

## Batch strategy

Рекомендуемая разбивка:

| Batch | Что делать | Риск | Можно ли за раз |
| --- | --- | --- | --- |
| A: local generated cleanup | Удалить `.edge-debug/`, `.codex-artifacts/visual-qa*`, temp screenshots/logs/cache | Низкий | Да |
| A0: ignore hardening | Обновить `.gitignore` для будущих артефактов | Низкий | Да, лучше перед A |
| B: old DB/snapshot cleanup | Разобрать `backups/`, `stage_snapshots/`, `stage_copy*.db`, старые root DB backups | Средний | Нет, нужен список и retention rule |
| C: storage cleanup | Проверять `storage/media_library`, `storage/scenario_step_files`, `storage/employee_files` по DB-ссылкам и продуктовой ценности | Высокий | Нет |
| D: code cleanup | Снимать legacy `scenario_edit.html` и связанные routes/tests только после React parity | Высокий | Нет, отдельная feature task |
| E: docs cleanup | Не удалять history; при необходимости архивировать/сжимать большой handoff | Низкий/средний | Можно позже отдельным docs PR |

Мой выбор: сделать A0 + A одним проходом, а B/C/D не трогать в этой итерации. Причина простая: A0+A убирает почти весь лишний вес без затрагивания данных и поведения приложения.

## `.gitignore` hardening

Текущий `.gitignore` уже покрывает часть локального шума: `.edge-debug/`, `.tmp_pycache/`, `tmp_*.png`, `tmp_*.db`, `*.log`, `backups/`, `exports/`, `stage_snapshots/`, runtime storage folders.

Пробелы:

- `.codex-artifacts/` не игнорируется, поэтому screenshots/watchdog output висит как untracked noise;
- `.ruff_cache/` не игнорируется явно;
- `ci.db` не покрывается правилом `tmp_*.db`, хотя CI smoke docs предлагают `DATABASE_URL=sqlite:///./ci.db`;
- SQLite sidecar files `*.db-wal`, `*.db-shm`, `*.db-journal` не покрыты полностью;
- если кто-то заведет `local.db` или `test.db`, они не будут пойманы, но blanket `*.db` опасен: можно случайно скрыть seed/demo DB, если ее когда-то решат хранить в git.

Рекомендованный patch:

```gitignore
# Local agent/test artifacts
.codex-artifacts/
.ruff_cache/
ci.db

# SQLite sidecar files
*.db-wal
*.db-shm
*.db-journal
```

Почему не `*.db`: сейчас repo уже осознанно игнорирует конкретные runtime DB (`hr_bot.db`, `stage_copy.db`, `tmp_*.db`, `*.before_*.db`). Широкое правило `*.db` проще, но оно может спрятать будущий intentional fixture/seed DB. Лучше расширять точечно.

## Recommended cleanup pipeline

1. Сделать маленький non-runtime patch с `.gitignore` hardening:
   - `.codex-artifacts/`
   - `.ruff_cache/`
   - `ci.db`
   - `*.db-wal`
   - `*.db-shm`
   - `*.db-journal`
2. После подтверждения удалить safe local artifacts одним батчем:
   - `.edge-debug/`
   - `.codex-artifacts/visual-qa*`
   - `.codex-artifacts/verification/`, если старые smoke DB больше не нужны
   - `tmp_*.png`
   - `tmp_*.log`, `bot*.log`, `local_bot*.log`
   - `.tmp_pycache/`
   - `.ruff_cache/`
3. Отдельно решить retention policy для DB/snapshot data:
   - хранить только последние N backups;
   - старые stage snapshots переносить во внешний архив или удалять;
   - не трогать `storage/employee_files` без data retention задачи.
4. Для code cleanup завести отдельную задачу по `scenario_edit.html`:
   - перечислить legacy-only update paths;
   - закрыть parity в React workspace;
   - удалить template/route/tests только после этого.

## Commands used

- `git status --short`
- `Get-ChildItem ... | Measure-Object Length -Sum` для размеров директорий
- `Get-ChildItem -Recurse -Include *.db,*.log,tmp_*` для runtime artifacts
- `rg` по templates, docs и routes
- `git check-ignore -v` для проверки ignore coverage
