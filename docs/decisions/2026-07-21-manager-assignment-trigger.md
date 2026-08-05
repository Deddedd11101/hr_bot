---
title: Manager assignment trigger for adaptation scenarios
date: 2026-07-21
status: accepted
doc_type: adr
area: product
related:
  - "[[backlog]]"
  - "[[project_state]]"
  - "[[features/employee-lifecycle]]"
source_of_truth: true
---

# Manager assignment trigger for adaptation scenarios

## Context

Для адаптации нужен не просто выбор руководителя в карточке сотрудника, а автоматический запуск отдельного сценария у самого руководителя в момент, когда он назначен на сотрудника в адаптации.

Попытка решить это через `employee_stage` была бы плохой моделью:

- руководитель и наставник не являются жизненными этапами сотрудника;
- один и тот же человек может быть одновременно штатным сотрудником, руководителем и наставником;
- смешивание role semantics с lifecycle semantics быстро ломает фильтры, меню и триггеры.

## Decision

Принять следующую модель:

1. Роль руководителя и наставника хранится как flags на карточке сотрудника:
   - `is_manager`
   - `is_mentor`
2. Выбор руководителя сотрудника разрешен только из сотрудников с `is_manager=true`.
3. Выбор наставников разрешен только из сотрудников с `is_mentor=true`.
4. Автозапуск сценария руководителя реализуется не через scheduler anchor-date, а через event trigger при сохранении карточки сотрудника.
5. Для этого вводится отдельный trigger mode сценария:
   - `manager_assigned_adaptation`

## Runtime semantics

Trigger создается, если выполняется одно из условий:

- сотрудник уже в `adaptation` и у него впервые назначили или изменили `manager_employee_id`;
- сотрудника перевели в `adaptation`, и у него уже задан `manager_employee_id`.

В ответ backend создает `FlowLaunchRequest` с `launch_type=trigger` для карточки руководителя. Дальше worker/scheduler подхватывает этот request штатным runtime-механизмом.

## Why this is better

- Нет прямого Telegram/network side effect внутри web-save handler.
- Trigger остается явным и расширяемым, а не размазанным по случайным `if` в карточке.
- Модель легко продолжить на будущие события вроде `mentor_assigned_adaptation`.

## Deferred

- Автозапуск по наставнику пока не включен, хотя role flag и filtered selects уже подготовлены.
- Если product захочет несколько разных mentor roles, generic `is_mentor` может потребовать дальнейшей детализации.
