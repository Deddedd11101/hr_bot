---
title: Manager trigger scenarios handoff
date: 2026-07-21
status: active
doc_type: handoff
area: employee-lifecycle
related:
  - "[[decisions/2026-07-21-manager-assignment-trigger]]"
  - "[[project_state]]"
source_of_truth: false
---

# Manager trigger scenarios handoff

## Что сделано

- В employee model добавлены role flags:
  - `is_manager`
  - `is_mentor`
- Employee detail API и React form теперь умеют читать и сохранять эти флаги.
- Селект руководителя фильтруется по `is_manager`.
- Селекты наставников фильтруются по `is_mentor`.
- Для сценариев добавлен trigger mode `manager_assigned_adaptation`.
- При сохранении карточки сотрудника backend создает `FlowLaunchRequest` с `launch_type=trigger`, если:
  - сотрудник уже в `adaptation` и ему назначили/сменили руководителя;
  - либо сотрудника перевели в `adaptation`, когда руководитель уже указан.

## Что важно

- Это не прямой Telegram-send из web route. Trigger уходит через штатный launch-request pipeline.
- Автозапуск по наставнику пока не включен. Подготовлены только role flag и filtered select.
- Если руководитель не привязан к боту (`chat_id` нет), trigger request останется pending до появления канала.

## Следующий логичный шаг

- Добавить явный mentor-trigger только после product-решения, какой именно event нужен.
- Не плодить новые assignment triggers ad hoc; сначала составить карту lifecycle/assignment events.
