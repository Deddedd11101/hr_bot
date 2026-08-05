---
title: Handoff по ветке positions catalog
date: 2026-07-22
status: active
doc_type: handoff
area: data
related:
  - "[[backlog]]"
  - "[[project_state]]"
  - "[[data-model]]"
  - "[[decisions/2026-07-22-managed-positions-catalog]]"
source_of_truth: false
---

# Что сделано

- Добавлена модель `Position` в `app/models.py`.
- Добавлен runtime/catalog helper `app/positions.py`.
- `app/database.py` теперь:
  - создает `positions` в SQLite compatibility path;
  - вызывает seed/compatibility routine для каталога должностей.
- Employee detail больше не берет `employee_role_values` из hardcoded списка; options строятся из БД плюс текущий legacy value сотрудника.
- Сохранение карточки сотрудника/кандидата умеет принимать catalog position по `slug`, `id` или `title` и сохраняет canonical `title`.
- Scenario role matching, bulk targeting и bot-menu audience targeting используют общий position resolver, а не map из трех ролей.
- Settings API получил CRUD:
  - `GET /api/settings/positions`
  - `POST /api/settings/positions`
  - `POST/PATCH /api/settings/positions/{id}`
  - `DELETE /api/settings/positions/{id}` как deactivate

# Что сознательно не делали

- Не переводили `employees.desired_position` на foreign key.
- Не делали stage deploy.
- Не строили отдельный frontend editor для positions. Сейчас API и workspace payload уже готовы, фронт может подключиться отдельно.

# Контракты, которые теперь важны фронту

- settings workspace payload теперь включает `positions`.
- `menu_role_scope_labels` больше строится из `positions`, а не из жесткого enum.
- employee detail payload продолжает отдавать `options.employee_role_values` как массив строк, но источник теперь catalog-backed.
- Для сохранения employee detail можно отправлять:
  - `desired_position = "<slug>"`
  - `desired_position = "<title>"`
  - `desired_position = "<position id>"`

# Риски и следующий шаг

- Пока `desired_position` строка, админ все еще может развести похожие должности смыслово, если не будет UI-ограничений и cleanup policy.
- Если фронт будет делать полноценный editor должностей, ему нужен:
  - список `positions` из workspace или `GET /api/settings/positions`;
  - формы create/update/deactivate;
  - явный UX для inactive позиций и предупреждение, если они уже используются в сценариях/menu sets.
