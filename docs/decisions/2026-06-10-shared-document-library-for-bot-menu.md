---
title: Shared document library for bot menu
date: 2026-06-10
status: accepted
doc_type: decision
area: bot-menu
task_tokens:
  - HRB-P1-07
related:
  - "[[../architecture]]"
  - "[[../project_state]]"
  - "[[../handoffs/frontend-structure-reset-handoff]]"
source_of_truth: true
---

# Контекст

Меню бота уже умеет открывать submenu через `open_set` и запускать сценарии через `launch_scenario`, но для shared материалов не было нормальной модели:

- employee-specific `employee_files` не подходят как общая библиотека;
- хранить raw `url` или `stored_path` прямо в `BotMenuButton` значило бы превращать menu buttons в свалку document payload;
- документов и ссылок ожидается много, значит оператору нужен отдельный каталог материалов и нормальная навигация по разделам.

# Решение

Принята отдельная shared document library:

- новая сущность `DocumentLibraryItem` хранит `file | link`;
- для operator UI выделена отдельная страница `/app/documents`;
- для menu runtime добавлен новый button action `send_document`;
- `BotMenuButton` ссылается на `DocumentLibraryItem` по `document_item_id`, а не хранит document payload внутри себя;
- навигация по документам в боте строится не отдельным спец-механизмом, а через уже существующие `menu sets` и `open_set`.

# Почему так

Этот вариант лучше, чем direct fields в `bot_menu_buttons`, потому что:

- переиспользование документов становится нормальным: один документ можно повесить в несколько мест меню;
- UI управления материалами отделен от UI настройки menu targeting;
- storage/download logic живет рядом с document library, а не размазан по bot menu runtime;
- submenu документов не создает вторую параллельную навигационную систему внутри бота.

# Последствия

Положительные:

- bot-menu остается owner только навигации и ссылок на действия;
- shared files и shared links получили отдельный lifecycle;
- дальнейшая категоризация документов делается через menu taxonomy, а не через усложнение `bot-menu`.

Отрицательные и ограничения:

- появляется еще одна operator surface `/app/documents`, которую нужно поддерживать;
- без product cleanup документов можно все равно сделать хаос, просто уже на уровне menu-set структуры;
- текущий MVP страницы документов еще не покрывает advanced operations вроде bulk upload, reorder UX, replace-file flow и search/filter.
