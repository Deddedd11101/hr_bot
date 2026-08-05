---
title: Управляемый каталог должностей без жесткой миграции employee.desired_position
date: 2026-07-22
status: accepted
doc_type: adr
area: data
related:
  - "[[backlog]]"
  - "[[data-model]]"
  - "[[project_state]]"
  - "[[features/scenario-engine]]"
source_of_truth: true
---

# Контекст

В системе роли/должности были размазаны по hardcoded константам и string comparisons:

- `app/flow_templates.py`
- `app/mass_targeting.py`
- `app/scenario_engine.py`
- payload employee detail / settings workspace

Это ломало расширяемость: новая должность требовала backend-правок вместо работы через settings/admin.

# Решение

Принят промежуточный, но управляемый вариант:

1. Добавить таблицу `positions` как code-backed справочник.
2. Оставить `employees.desired_position` строковым полем на этом этапе.
3. Считать `scenario.role_scope`, `bot_menu_set.role_scope` и `mass_*_action.target_role_scope` значением `positions.slug`.
4. Матчинг employee к scope делать через общий normalizer `title/slug -> canonical scope key`.
5. При startup seed-ить default catalog:
   - `designer` / `Дизайнер`
   - `project_manager` / `Project manager`
   - `analyst` / `Аналитик`
6. Legacy строковые `desired_position` автоматически подхватывать в catalog, а не терять и не переписывать destructive migration.

# Почему не сделали foreign key сразу

Прямой перевод `employees.desired_position` в `position_id` сейчас выглядел бы красивее на бумаге, но это слабое решение для текущего проекта:

- SQLite schema уже живет через startup compatibility patching, а не через нормальную migration chain;
- stage и локальные БД содержат legacy строки;
- в нескольких runtime paths position использовалась как свободный текст;
- жесткая миграция увеличила бы риск сломать существующие сценарии и таргетинг в параллельной веточной работе.

То есть сначала нужен единый catalog и единый resolver. Foreign key migration — отдельный следующий шаг, если catalog начнет нести richer metadata и stricter integrity.

# Последствия

Плюсы:

- новые должности можно заводить через settings API;
- scenario matching, bot menu targeting и bulk targeting больше не ограничены тремя hardcoded ролями;
- legacy employees не теряют данные.

Минусы:

- `employees.desired_position` пока не нормализован до FK;
- integrity между employee row и catalog остается application-level, а не schema-level;
- если появятся дубликаты похожих должностей, cleanup придется делать product/admin слоем.

# Следующий логичный шаг

Не начинать FK-миграцию автоматически. Сначала определить:

- нужны ли metadata у должности кроме title/slug/sort/is_active;
- требуется ли multi-select по должностям;
- нужно ли хранить position history у сотрудника;
- готов ли проект к нормальной миграционной цепочке вместо startup patching.
