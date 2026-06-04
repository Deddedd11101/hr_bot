---
title: Легкий стандарт документации и Obsidian как navigation layer
date: 2026-05-11
status: accepted
doc_type: adr
area: docs
task_tokens:
  - HRB-DOC-03
related:
  - "[[documentation-standard]]"
  - "[[README]]"
  - "[[maps/start-here]]"
source_of_truth: true
---

# Легкий стандарт документации и Obsidian как navigation layer

## Контекст

После расширения runtime docs появились отдельные live-документы по architecture, API, web surface, data model, stage deploy и configuration. Это полезнее одного большого overview, но без общего формата документация начнет расходиться по структуре, Properties и назначению файлов.

Полный LLD-first подход для всего проекта сейчас избыточен: он замедлит работу и быстро превратится в бюрократию. При этом для значимых изменений подсистемы, API, схемы, deploy или bot behavior LLD нужен, иначе важные trade-offs останутся только в чатах.

## Решение

Принят легкий стандарт документации:

- все новые и существенно обновленные docs используют общий frontmatter contract;
- типы документов фиксируются через `doc_type`;
- live docs отделяются от historical context;
- LLD создается только для значимых изменений подсистемы или контракта;
- ADR фиксирует решения и trade-offs;
- Obsidian используется для Properties, backlinks, graph, templates, canvas и bookmarks;
- canonical content остается Markdown в git.

## Почему так

Этот вариант сохраняет скорость разработки и дает достаточно структуры для onboarding, аудита решений и поддержки stage. Он также снижает риск, что Obsidian станет отдельной закрытой системой поверх репозитория.

Отклоненные варианты:

- LLD для каждого изменения: слишком дорого для текущего размера проекта.
- Только README/backlog без стандарта: быстро приводит к разнородным документам.
- Kanban/Canvas как source of truth: создает параллельный backlog и параллельную архитектуру.

## Последствия

Положительные:

- новые документы проще создавать через templates;
- Properties позволяют фильтровать docs по типу, области и актуальности;
- maps улучшают навигацию без дублирования фактов;
- LLD появляется там, где он реально снижает риск.

Риски:

- старые документы не сразу будут приведены к полному frontmatter contract;
- Obsidian Graph/Canvas/Kanban могут начать использоваться как параллельная правда, если не соблюдать стандарт;
- легкий стандарт требует дисциплины: live docs нужно обновлять вместе с изменениями, а не постфактум.

## Связанные документы

- [[documentation-standard]]
- [[README]]
- [[backlog]]
- [[project_state]]
