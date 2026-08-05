---
title: Принятие Obsidian vault
date: 2026-05-06
status: accepted
doc_type: adr
area: docs
task_tokens:
  - HRB-DOC-01
related:
  - "[[README]]"
  - "[[documentation-standard]]"
source_of_truth: true
---

# Принятие Obsidian vault

Принято решение использовать `docs/` внутри основного репозитория как documentation vault HR Bot. Obsidian считается reader/editor для тех же Markdown-файлов, которые версионируются в git.

## Контекст

- Project knowledge уже частично хранился в Markdown под `docs/`.
- Команде нужна versioned documentation, удобная для Obsidian.
- Основная аудитория — рабочая пара developer плюс AI assistant, поэтому fast context recovery важнее polished publishing.
- Отдельный Obsidian-only vault ослабил бы history, review и code-to-doc traceability.

## Выбранная модель

- Держать один набор Markdown-файлов в `docs/`.
- Делить docs на:
  - live source-of-truth documents;
  - dated historical documents.
- Использовать stable task tokens вроде `HRB-P0-01` в backlog, decisions, handoffs и feature notes.
- Не делать Obsidian configuration частью canonical contract; docs должны оставаться usable без Obsidian.

## Последствия

### Плюсы

- Документация получила нормальную git history и может обновляться вместе с кодом.
- Те же файлы доступны людям, tools и AI без export steps.
- Context recovery становится предсказуемым через `README`, `backlog`, `project_state` и dated handoffs.

### Компромиссы

- Команда должна держать live docs актуальными после meaningful changes.
- Obsidian-specific workflows не должны становиться обязательными для понимания проекта.
- Daily notes и handoffs должны оставаться lightweight, иначе vault станет шумным.

## Следующие шаги

- Backlog status changes держать в [[backlog]].
- Обновлять [[project_state]], когда меняется operating reality.
- Добавлять новые decision records только для реальных решений, а не для каждой мысли.
