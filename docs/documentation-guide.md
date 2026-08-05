---
title: Руководство по документации HR Bot
date: 2026-08-05
status: active
doc_type: standard
area: docs
task_tokens:
  - HRB-DOC-04
related:
  - "[[README]]"
  - "[[documentation-standard]]"
  - "[[maps/start-here]]"
  - "[[project_state]]"
  - "[[backlog]]"
source_of_truth: true
---

# Руководство по документации HR Bot

Этот документ объясняет, как читать и поддерживать `docs/`, чтобы новый человек или агент быстро понял, где текущая правда, где история, а где рабочий шум.

## Принцип

`docs/` - рабочий source of truth проекта, но не каждый файл в `docs/` является текущим контрактом.

Главное правило: сначала читать live docs, потом maps, потом history. Handoff/daily/dated snapshots помогают восстановить контекст, но не должны спорить с live docs.

## Быстрый вход за 2 минуты

1. [[project_state]] - что сейчас происходит, какие риски и ближайшие приоритеты.
2. [[backlog]] - какие задачи живые, закрытые или отложенные.
3. [[stage-change-log]] - что реально выведено на stage.
4. [[architecture]] - как устроен runtime и границы подсистем.
5. [[maps/engineering-map]] или [[maps/product-map]] - куда идти по конкретной теме.

Если времени совсем мало, читать только [[project_state]], [[backlog]] и [[stage-change-log]].

## Классы документов

| Класс | Где лежит | Как читать |
| --- | --- | --- |
| Live source of truth | `project_state.md`, `backlog.md`, `architecture.md`, `api.md`, `web-surface.md`, `data-model.md`, `configuration.md`, `stage-deploy.md`, `stage-change-log.md`, `subagent-delivery.md`, `features/*` | Считать текущим контрактом, пока код или stage не докажут обратное. |
| Navigation | `README.md`, `maps/*` | Использовать как карту ссылок. Не хранить здесь уникальные факты. |
| Decisions | `decisions/*` | Читать как историю решений и trade-offs. Новое решение не переписывает старое, а добавляет новую запись или явно supersedes прежнюю. |
| Designs | `lld/*` | Читать как дизайн конкретной подсистемы/изменения. Проверять `status`. |
| Handoffs | `handoffs/*` | Исторический контекст передачи. Не использовать как текущий контракт без сверки с live docs и кодом. |
| Daily/snapshots | `daily/*`, `roadmap-*`, `demo-day-*` | Журнал и dated context. Не текущий план. |
| Templates/standard | `templates/*`, `documentation-standard.md`, этот документ | Правила формата и процесса. |

## Что обновлять при изменениях

| Изменение | Обязательные docs |
| --- | --- |
| Изменился статус задачи, появился новый work item | [[backlog]] |
| Изменились риски, текущее состояние, ближайшие приоритеты | [[project_state]] |
| Изменился runtime, границы подсистем, data flow | [[architecture]] или релевантный `features/*` |
| Изменился JSON API | [[api]] |
| Изменился classic/web surface, redirects, form actions, downloads | [[web-surface]] |
| Изменилась schema, migration, DB drift, storage contract | [[data-model]] |
| Изменились env vars, secrets placement, config precedence | [[configuration]] |
| Изменился deploy path, stage smoke, rollback, server behavior | [[stage-deploy]] |
| Изменение реально выведено и проверено на stage | [[stage-change-log]] |
| Принято значимое продуктовое/архитектурное решение | новый файл в `decisions/` |
| После работы нужен устойчивый контекст продолжения | новый или обновленный файл в `handoffs/` |

## Когда docs не трогать

Не нужно обновлять документацию для:

- чисто локального эксперимента, который не попал в код или stage;
- косметической правки текста/стиля без изменения поведения или процесса;
- временного debug output, screenshots, local cache;
- исправления, которое не меняет контракт и уже очевидно покрыто существующим описанием.

Если сомневаешься, обновлять ли docs, проверь вопрос: "Следующему агенту через неделю это знание нужно, чтобы не ошибиться?" Если да - обновить live doc или handoff.

## Как сверять актуальность

Перед тем как считать документ правдой:

1. Проверить frontmatter: `status`, `doc_type`, `source_of_truth`.
2. Если это handoff/daily/snapshot, найти соответствующий live doc.
3. Если документ описывает API/schema/runtime, сверить с кодом.
4. Если документ описывает stage, сверить со [[stage-change-log]] и [[stage-deploy]].
5. Если есть противоречие, приоритет такой: код/stage факт -> live doc -> ADR/design -> handoff/daily.

## Правила для новых агентов

Перед началом задачи:

1. Читать [[project_state]] и [[backlog]].
2. Для frontend/backend/runtime задач открыть [[architecture]] и релевантный `features/*`.
3. Для deploy/stage/bot задач открыть [[stage-deploy]], [[configuration]] и [[subagent-delivery]].
4. Проверить `git status --short` в рабочем дереве и не затирать чужие изменения.

Перед handoff:

1. Обновить live docs, если изменился контракт.
2. Обновить [[backlog]] и [[project_state]], если изменились статус/риски.
3. Если был stage deploy, добавить запись в [[stage-change-log]].
4. Если продолжение нетривиально, добавить handoff.
5. Не писать daily по инерции: daily нужен только для насыщенного operational day.

## Как заводить новый документ

1. Выбрать тип: `feature`, `lld`, `adr`, `runbook`, `handoff`, `daily`.
2. Взять шаблон из `templates/`.
3. Заполнить frontmatter.
4. Добавить `related` ссылки на live docs.
5. Если документ становится текущим контрактом, поставить `source_of_truth: true`; для handoff/daily почти всегда `false`.
6. Добавить ссылку из карты или live doc только если документ действительно нужен для навигации.

## Что считать долгом документации

- Факт есть только в handoff, но влияет на текущую работу.
- `stage-change-log` описывает deploy, которого нет в фактической stage history.
- Backlog говорит `doing`, но `project_state` описывает задачу как закрытую.
- ADR отменен по факту, но нет новой decision note.
- Feature doc описывает поведение, которого уже нет в коде.
- Map содержит уникальный факт, которого нет в live doc.

Такой долг исправлять не массовым rewrite, а маленькими точечными правками: перенести факт в live doc, оставить historical file как историю и добавить ссылку.

