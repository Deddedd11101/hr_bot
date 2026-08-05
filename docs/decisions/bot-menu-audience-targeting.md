---
title: Bot menu audience targeting
date: 2026-06-08
status: accepted
doc_type: adr
area: bot
task_tokens:
  - HRB-P1-07
related:
  - "[[project_state]]"
  - "[[architecture]]"
  - "[[handoffs/frontend-structure-reset-handoff]]"
source_of_truth: true
---

# Контекст

В проекте уже существовали multiple `BotMenuSet`, но до этого это была слабая закладка на будущее:

- оператор мог создать несколько наборов;
- бот выбирал набор только по `employee.current_menu_set_id` или global default;
- runtime не понимал, какой набор подходит кандидату, а какой сотруднику в штате;
- `open_set` позволял открыть любой target menu без audience-check.

Это делало menu sets визуальной настройкой без реального продуктового смысла.

# Решение

Принят единый backend-first contract audience targeting для `BotMenuSet`.

Каждый набор меню теперь может таргетироваться по:

- `employee_scope`: `all | employees | candidates`
- `role_scope`: role/position scope
- `target_employee_ids`: explicit список сотрудников/кандидатов

Runtime Telegram-бота обязан:

- выбирать только compatible menu sets;
- автоматически сбрасывать `current_menu_set_id`, если набор перестал подходить сотруднику;
- блокировать `open_set`, если target menu не подходит пользователю.

Settings UI/API обязан:

- позволять редактировать эти audience fields для каждого menu set;
- отдавать нужные labels/options для role scope, employee scope и employee/candidate list;
- не позволять одному и тому же сотруднику/кандидату сидеть одновременно в двух разных explicit menu sets.

# Уточнение

Первый вариант audience-targeting включал `target_employee_stages` и `target_candidate_stages`, но это оказалось избыточным и плохо объяснимым оператору.

Текущая целевая модель упрощена:

- broad targeting идет через `employee_scope` и `role_scope`;
- точечный targeting идет через `target_employee_ids`;
- если explicit target list заполнен, набор считается точечным, а не комбинируется со stage-фильтрами.

# Почему не принято другое

## Почему не два бота

Два Telegram-бота для кандидатов и сотрудников сейчас усложняют процесс:

- две точки входа;
- тяжелее переход candidate -> employee;
- выше риск дублирования menu logic и сценариев;
- выше операционная путаница для HR.

Пока это не два отдельных продукта, один бот с audience segmentation сильнее.

## Почему не только скрытие кнопок во frontend

Скрытие кнопок без runtime-guard слабое:

- deep links и прямые actions остаются доступны;
- menu drift возвращается при любом refactor;
- mini app потом будет невозможно безопасно ограничивать той же моделью.

Поэтому audience должен жить в backend/runtime contract.

# Последствия

- `BotMenuSet` становится реальной частью access-layer бота, а не декоративной настройкой.
- Следующие candidate-only / employee-only / mini-app surfaces нужно строить поверх этого contract или поверх его явного расширения.
- Если позже понадобится более сложная persona-модель (`candidate`, `employee`, `manager` и т.д.), ее нужно строить как следующий слой поверх этого audience targeting, а не параллельно ему.
