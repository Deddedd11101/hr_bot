---
title: Состояние проекта HR Bot
date: 2026-05-14
status: active
doc_type: state
area: core
task_tokens:
  - HRB-DOC-01
  - HRB-DOC-02
  - HRB-DOC-03
  - HRB-DOC-04
  - HRB-P0-01
  - HRB-P0-02
  - HRB-P0-03
  - HRB-P0-04
  - HRB-P0-05
  - HRB-P0-06
  - HRB-P1-06
  - HRB-P1-07
  - HRB-P2-06
  - HRB-P2-07
  - HRB-P2-08
  - HRB-DISC-03
  - HRB-DISC-04
related:
  - "[[README]]"
  - "[[backlog]]"
  - "[[architecture]]"
  - "[[documentation-standard]]"
  - "[[local-runbook]]"
  - "[[roadmap-2026-05-12]]"
  - "[[demo-day-brief-2026-05-12]]"
source_of_truth: true
---

# Состояние проекта

## Текущий snapshot

- Stack: FastAPI admin + Aiogram Telegram bot + APScheduler + SQLite + React/Vite admin surfaces.
- Production model: classic admin pages остаются рабочими fallback-экранами, пока новые React-экраны развиваются параллельно.
- Documentation model: `docs/` — git-backed project vault; live runtime truth разделен по architecture, API, web surface, data model, stage deploy и configuration docs.
- Documentation standard: введен легкий формат docs, templates и maps; Obsidian используется как navigation/properties/templates layer, а canonical truth остается Markdown в git.
- Local run model: рабочая команда запуска админки зафиксирована в [[local-runbook]]; запуск без `--reload` является основной командой.
- UI migration model: принят LLD-подход для перевода classic admin UI на React default с сохранением classic direct routes как временного rollback.

## Что работает

- Карточки сотрудников и кандидатов есть и в classic, и в React admin surfaces.
- Scenario templates, step templates, branching, chain steps и manual launches уже реализованы.
- Telegram bot умеет отправлять шаги, собирать text/files/button responses и писать progress в SQLite.
- Mass actions, onboarding scheduler и scenario portability tooling уже есть в коде.
- Unknown Telegram users больше не создают candidate records автоматически.
- Bot access можно заблокировать per employee через `is_bot_blocked`.
- Incoming Telegram photos обрабатываются как first-class inbound files вместе с documents.
- Mass actions могут target employee stages и candidate stages отдельно.
- В репозитории теперь есть explicit live docs для JSON API, operator web routes, schema behavior, env/config и текущего stage deploy path.
- Для новых и существенно обновленных docs зафиксирован frontmatter contract, doc types, LLD/ADR/runbook rules и Obsidian practices.
- Есть LLD для миграции classic admin UI на React, включая приоритет страниц и карту form routes, которые нужно заменить JSON API.
- React default entry включен для root/login/sidebar; `/app/settings`, `/app/bulk-actions` и `/app/surveys/workspace` реализованы как React slices/workspace modes с JSON API и classic fallback.
- Sidebar упрощен: отдельная ссылка `Кандидаты` убрана, сотрудники и кандидаты остаются внутри общей React employees surface.
- В `frontend` инициализирован shadcn `components.json`, добавлен широкий набор shadcn `ui/*` компонентов и локальный `time-picker`; основной акцент в light/dark теме зафиксирован как `#93EB05`, тени отключены глобально.
- Текущий frontend UI stack фактически Base UI first (`base-nova`, `@base-ui/react`), но часть legacy wrappers еще остается на Radix (`Popover`, `ScrollArea`); это нужно выровнять отдельным проходом.
- Попытка закрепить отдельную `/app/ui-kit` страницу как reference route отменена: она не уменьшила хаос в создании страниц и была удалена из runtime.
- Главная frontend-проблема сейчас не отсутствие витрины компонентов, а отсутствие жесткой композиции экранов: часть страниц перегружена в `main.tsx` или крупных page-файлах. `employee detail` уже переехал в Vite-стек и прошел первый structural split (`main.tsx + page.tsx + sections.tsx + helpers.ts`), но это еще не финальная нормализация shared/UI API.
- `frontend/src/employees-list/` уже разрезан по новой схеме (`main.tsx` + `page.tsx` + `components.tsx` + `data.ts` + `types.ts`) и теперь служит первым живым шаблоном для следующих React-экранов.
- `frontend/src/scenario-workspace/` уже прошел первый structural pass: `main.tsx` стал bootstrap-only, экран вынесен в `page.tsx`, а model helpers и picker-компоненты вынесены в отдельные файлы. Сам экран все еще слишком большой, но слой mount и часть технической мешанины уже отделены.
- `frontend/src/scenario-workspace/page.tsx` уже дополнительно разрезан по крупным visual sections: sidebar и центральная колонка вынесены в `sections.tsx`. Основной remaining hotspot теперь detail-pane и его form logic.
- Detail-pane `scenario-workspace` тоже вынесен из `page.tsx` в отдельный section-компонент внутри `sections.tsx`; `employee detail` вслед за ним уже прошел через `helpers.ts` и `sections.tsx`. Основной remaining hotspot теперь не сама файловая структура, а cleanup legacy visual/API drift и безопасное выключение classic fallback routes.

## Активные проблемы

- Новый scenario workspace функционально богатый, но тяжелый и с лагами.
- Candidate-to-employee transition и identity linking для existing employees все еще нерешенные продуктовые решения.
- Classic и React employee cards все еще требуют broader correctness pass beyond fixed shared fields.
- Classic UI все еще содержит часть legacy employee/scenario form actions. Classic `/settings`, `/bulk-actions` и `/surveys/*` сохранены как fallback после появления React routes; survey export остается non-JSON download route.
- Нормального migration layer все еще нет; SQLite schema может меняться на startup через `_ensure_sqlite_schema()`.
- Inspected live SQLite уже показывает unresolved schema drift (`media_assets`, `flow_step_templates.media_asset_id`) без поддержки в текущем коде.
- Stage infrastructure truth все еще частично вне репозитория, потому что systemd env и service definitions не codified здесь.
- Для двух ИП требуется отдельное решение по legal/data boundary: вероятнее всего, раздельные БД/контуры хранения и явное отображение текущего ИП в UI; это нужно подтвердить юридически и оформить в LLD до реализации.
- Security/compliance слой пока не выделен отдельной реализацией: роли, аудит, защита файлов/персональных данных, секреты, backup policy, CSRF/session/rate-limit hardening требуют отдельного прохода после стабилизации основных модулей.
- Obsidian Kanban/Canvas/Graph полезны как views и навигация, но остаются риском, если начнут использоваться как параллельные source of truth вместо [[backlog]], [[architecture]] и live docs.
- Legacy global CSS все еще присутствует, но React runtime уже частично отрезан от него: React templates переведены на отдельный `react_base.html` и `app/static/react_shell.css` вместо прямого наследования `base.html`. Следующий cleanup — убрать remaining visual/API drift и не тащить legacy selectors обратно в новые React pages.

## Ближайшие приоритеты

- `HRB-P1-01` запускать сценарии из HR status changes вместо manual operator workarounds.
- `HRB-P1-02` привести scenario-to-scenario transition semantics в новом admin к нормальной модели.
- `HRB-P1-03` унифицировать notifications, чтобы new admin мог безопасно заменить old one.
- `HRB-P1-06` уменьшить workspace lag до broader UX work.
- `HRB-P1-07` продолжить перенос classic-only хвостов: legacy employee/card form actions, old flow pages и stage parity-smoke после React survey workspace.
- Для `HRB-P1-07` ближайший frontend-шаг теперь не новая reference page, а cleanup после структурной миграции: React shell уже отделен от legacy `styles.css`, теперь нужно пройтись по classic fallback routes и критичным write-операциям.
- После структурных pass по `employees-list`, `scenario-workspace` и `employee detail` следующий frontend-шаг уже не очередной split файлов, а parity-pass и последовательное удаление classic-only хвостов без rollback gap.
- `HRB-DISC-01` выбрать long-term identity-linking flow для existing employees.
- После текущей стабилизации следующий продуктовый модуль — `HRB-P2-06` отпуска MVP; Telegram Mini Apps не начинать как отдельный frontend до решения `HRB-DISC-03` по scope/auth/API boundaries.
- `HRB-DISC-04` определить модель раздельного хранения данных для двух ИП; `HRB-P2-07` не начинать без LLD, потому что это влияет на БД, deploy/runbook, backup и UI context.
- `HRB-P2-08` запланировать security/compliance hardening после стабилизации ключевых модулей; auth, identity и data isolation учитывать уже в LLD для двух ИП и Mini Apps.
- Первые LLD-кандидаты после стандарта: scenario engine, bot identity, employee lifecycle, notification model, schema/migration strategy и React scenario workspace.

## Операционные ограничения

- Classic admin остается fallback source для business continuity и не должен ломаться, пока React screens улучшаются.
- Scenario logic и HR-facing behavior разделены между backend templates, React frontend и bot runtime; изменения требуют cross-surface checks.
- Локальный repo сейчас содержит runtime databases и snapshots outside git; docs должны описывать behavior, а не предполагать чистоту runtime data.
- Для schema questions source of truth — code плюс startup schema guard, а не raw SQLite inspection alone.
- Для docs questions source of truth — [[documentation-standard]]; старые документы можно мигрировать к frontmatter contract постепенно при следующих изменениях.

## Правило документации

Обновлять этот файл, когда:

- меняются priorities;
- major risk снят или добавлен;
- chosen implementation model подсистемы меняется;
- завершенная задача меняет practical operating state проекта.
- меняется формат документации, Obsidian workflow или границы source of truth.
