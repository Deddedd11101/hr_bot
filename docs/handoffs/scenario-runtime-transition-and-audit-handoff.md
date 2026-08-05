---
title: Handoff по transition runtime и launch audit
date: 2026-06-16
status: active
doc_type: handoff
area: scenarios
related:
  - "[[features/scenario-engine]]"
  - "[[project_state]]"
  - "[[backlog]]"
source_of_truth: false
---

# Что сделано

- Обычный step с `response_type=launch_scenario` теперь реально завершает текущий сценарий и запускает `launch_scenario_key`.
- Для шага с текстом + вложением + inline-вариантами убран лишний follow-up message `Выберите вариант ответа:`: кнопки теперь вешаются на основной текст шага.
- Из employee list/detail убраны internal follow-up jobs (`skip_step_key="__single_step__:*"`), которые раньше маскировались под operator-visible scheduled launches.
- Ручной запуск сценария из карточки сотрудника больше не создает дополнительный pending `manual` request для продолжения после первого `none` шага.
- В React workspace добавлены:
  - редактирование названия сценария в settings;
  - фильтр списка сценариев по `all / employees / candidates`;
  - disabled state для `Переход к сценарию`, если `response_type != launch_scenario`.

# Почему это важно

- Раньше пользователь видел ложную картину, будто сценарии “размножаются” в scheduled list, хотя часть записей была внутренней очередью runtime.
- Переход к другому сценарию был product-critical функцией, но фактически работал только в узком branching path.
- Manual launch path подмешивал pseudo-demo semantics (`MANUAL_STEP_MINUTES`) туда, где должны были работать обычные follow-up правила engine.

# Что осталось

- Attachment-only interactive steps все еще могут потребовать отдельное helper-message, потому что messenger transport пока не умеет captions + inline markup на file/photo.
- Пустой `launch_scenario_key` при выбранном `launch_scenario` лучше считать data-quality/editor проблемой; runtime не должен на это silently полагаться как на нормальную конфигурацию.
