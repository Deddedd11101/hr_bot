---
title: Product map
date: 2026-05-12
status: active
doc_type: map
area: product
task_tokens:
  - HRB-DOC-03
related:
  - "[[README]]"
  - "[[roadmap-2026-05-12]]"
  - "[[features/employee-lifecycle]]"
  - "[[features/bot-identity]]"
  - "[[features/scenario-engine]]"
source_of_truth: false
---

# Product map

Навигация по продуктовым и операционным вопросам. Эта карта не хранит канонические правила поведения.

## Lifecycle

- [[features/employee-lifecycle]] — candidate stages, employee stages, перевод кандидата в сотрудника и gaps.
- [[features/bot-identity]] — как Telegram user связывается с employee/candidate record.
- [[backlog]] — актуальные продуктовые discovery tasks: `HRB-DISC-01`, `HRB-DISC-02`, `HRB-DISC-03`, `HRB-DISC-04`.

## Roadmap snapshots

- [[roadmap-2026-05-12]] — показываемый roadmap: стабилизация, отпуска, разделение данных двух ИП и Telegram Mini Apps.
- [[demo-day-brief-2026-05-12]] — личная шпаргалка демо-дня, не source of truth.

## Scenario behavior

- [[features/scenario-engine]] — типы шагов, ветвления, ручные запуски, progress.
- [[business-logic-audit-2026-08-05]] — черновой BA-аудит сценариев, lifecycle-пересечений и нарушений логики; не source of truth.
- [[features/scenario-catalog]] — draft-каталог бизнес-сценариев и карточек по DB-снимку; использовать для согласования, не как утвержденный регламент.
- [[api]] — JSON endpoints для scenario workspace.
- [[web-surface]] — classic operator actions для сценариев.

## Notifications

- [[features/notifications]] — текущие уведомления и P1 gap по унификации.
- [[backlog]] — `HRB-P1-03` как canonical task для notification model.

## Operator workflow

- [[web-surface]] — HTML/admin pages и form actions.
- [[features/ui-design-guidelines]] — принципы новой React admin surface.
- [[project_state]] — какие ограничения сейчас важны для business continuity.
- [[data-model]] — текущая схема данных и future constraint по раздельному хранению двух ИП.

## Где нужен LLD

Перед крупными изменениями стоит создать LLD по шаблону [[templates/lld-template]] для:

- bot identity;
- employee lifecycle;
- notification model;
- scenario engine semantics;
- React scenario workspace;
- разделение данных и UI-контуров для двух ИП.
