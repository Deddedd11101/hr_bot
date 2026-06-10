---
title: Survey flow separation from scenario flow
date: 2026-06-09
status: accepted
doc_type: decision
area: surveys
related:
  - "[[project_state]]"
  - "[[backlog]]"
  - "[[architecture]]"
  - "[[handoffs/frontend-structure-reset-handoff]]"
source_of_truth: true
---

# Контекст

React workspace для `/app/surveys/workspace` наследовал почти весь step-contract от сценариев. В итоге опросы предлагали оператору настраивать то, что для них продуктово бессмысленно:

- типы ответа кроме текстового;
- переход к сценарию;
- сохранение ответа в поле карточки;
- кастомный режим отправки;
- step-level notifications.

Это делало survey UX перегруженным и поддерживало ложное ощущение, будто опрос это просто “сценарий поменьше”.

# Решение

Зафиксировать survey flow как отдельный режим поверх тех же таблиц, но с более жестким контрактом:

- survey-step описывает один вопрос;
- `title` и `text` в UI считаются одной сущностью и синхронизируются;
- ответ для survey считается текстовым по умолчанию;
- `button_options` в survey означают только готовые варианты текстового ответа, а не branching;
- `send_mode` для survey-step всегда `immediate`;
- `target_field`, `launch_scenario_key`, `send_employee_card`, step notifications и button notifications для survey-step не являются допустимой конфигурацией и очищаются при сохранении;
- Excel-экспорт результатов опроса строится как плоский список строк `Пользователь ФИО / Вопрос / Ответ`, а не как широкая матрица по колонкам-вопросам.

# Почему так

- Опросы и сценарии решают разные задачи: сценарий описывает логику переходов и действий, опрос описывает сбор ответов.
- Поддержка лишних сценарных полей в survey не дает гибкости, а только порождает невалидные комбинации и ложные ожидания от UI.
- Плоский Excel-экспорт устойчивее к изменению структуры опроса и проще для последующей фильтрации, сортировки и загрузки в другие инструменты.

# Последствия

- Survey workspace стал заметно проще, но код пока еще живет в общем bundle и route layer со scenario workspace.
- Runtime получил дополнительное правило: текстовый survey-question может показывать option buttons и принимать ответ и через кнопку, и как текстовую сущность.
- Legacy editor еще не отражает этот новый UX как полноценный source of truth; default ownership survey уже остается за React workspace.
