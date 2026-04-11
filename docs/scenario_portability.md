# Scenario Portability

Этот документ фиксирует безопасный способ сохранить сценарии, созданные или изменённые на тестовом стенде, и перенести их в локальную среду или обратно.

## Зачем это нужно

Сценарии живут не только в коде.

Для корректного переноса нужно сохранять:

- `scenario_templates`
- `flow_step_templates`
- `step_button_notifications`
- вложения шагов из `storage/scenario_step_files`, если они использовались

Просто `git push` кодовой ветки не переносит сценарии, которые аналитик создал через UI на стенде.

## Инструмент

Для этого в проекте есть утилита:

- `tools/scenario_portability.py`

Она умеет:

- экспортировать выбранные сценарии в переносимый пакет;
- импортировать пакет обратно в SQLite-базу;
- переносить шаги, branch/chain-структуру и уведомления кнопок;
- копировать вложения шагов в пакет `assets/` и восстанавливать их при импорте.

Ключевая привязка переноса:

- по `scenario_key`, а не по `id`

Это важно, потому что `id` в разных базах могут отличаться.

## Формат пакета

Экспорт создаёт папку с:

- `manifest.json`
- `assets/`

`manifest.json` содержит:

- метаданные сценария;
- аудиторию сценария `employee_scope`:
  - `all`;
  - `employees`;
  - `candidates`;
- список шагов;
- parent/child связи шагов через `parent_step_key`;
- button notifications;
- сведения о вложениях шагов.

## Экспорт сценариев

Пример для одного сценария:

```powershell
cd D:\HRBot\hr_bot
.\.venv\Scripts\python.exe tools\scenario_portability.py export --db stage_copy.db --out exports\first_day_pkg --scenario-key first_day
```

Пример для нескольких сценариев:

```powershell
cd D:\HRBot\hr_bot
.\.venv\Scripts\python.exe tools\scenario_portability.py export --db stage_copy.db --out exports\analyst_pkg --scenario-key first_day --scenario-key first_week --scenario-key custom_scenario_1775198172
```

Также можно передавать несколько ключей через запятую в одном аргументе, но безопаснее использовать несколько `--scenario-key`.

## Импорт сценариев

Импорт в локальную базу:

```powershell
cd D:\HRBot\hr_bot
.\.venv\Scripts\python.exe tools\scenario_portability.py import --db hr_bot.db --in exports\analyst_pkg --storage-root storage\scenario_step_files
```

Импорт в копию stage-базы для проверки:

```powershell
cd D:\HRBot\hr_bot
.\.venv\Scripts\python.exe tools\scenario_portability.py import --db stage_copy.db --in exports\analyst_pkg --storage-root storage\scenario_step_files
```

## Что делает импорт

Импорт:

- обновляет или создаёт запись сценария по `scenario_key`;
- переносит `employee_scope`, чтобы не терять настройку `Для всех сотрудников` / `Для всех кандидатов`;
- для старых пакетов без `employee_scope` использует безопасное значение `all`;
- удаляет старые шаги и button notifications только у импортируемого сценария;
- заново создаёт шаги в правильном порядке;
- восстанавливает parent/branch-связи по `step_key`;
- переносит вложения шагов в `storage/scenario_step_files/<scenario_key>/...`.

То есть импорт работает как controlled replace для конкретного сценария.

## Рекомендуемый рабочий процесс

Если аналитик работает на тестовом стенде:

1. Дать ему редактировать сценарии на тестовом стенде.
2. После окончания работы снять копию SQLite со стенда.
3. Локально экспортировать только нужные `scenario_key`.
4. Импортировать пакет в локальную базу.
5. Проверить сценарии локально.
6. После проверки перенести изменения в целевую среду тем же пакетом.

## Как скачать stage-БД после работы аналитиков

Если нужно сохранить всё состояние тестового стенда после аналитиков, сначала на сервере зафиксируй backup:

```bash
cd /opt/hr_bot
mkdir -p backups
ts=$(date +%Y%m%d-%H%M%S)
cp -a hr_bot.db "backups/hr_bot.after-analytics.$ts.db"
```

Потом локально в PowerShell скачай SQLite-базу:

```powershell
scp root@92.51.38.32:/opt/hr_bot/hr_bot.db D:\HRBot\hr_bot\stage_after_analytics.db
```

Эта БД будет локальной копией всего stage-состояния: сотрудники, кандидаты, сценарии, прогресс, настройки.

## Как вытащить из stage-БД только сценарии

После скачивания `stage_after_analytics.db` можно собрать переносимый пакет сценариев:

```powershell
cd D:\HRBot\hr_bot
.\.venv\Scripts\python.exe tools\scenario_portability.py export --db stage_after_analytics.db --out exports\analytics_pkg --scenario-key first_day --scenario-key custom_scenario_1775198172
```

Затем импортировать пакет в локальную рабочую базу:

```powershell
cd D:\HRBot\hr_bot
.\.venv\Scripts\python.exe tools\scenario_portability.py import --db hr_bot.db --in exports\analytics_pkg --storage-root storage\scenario_step_files
```

Если надо сохранить все изменения аналитиков без разбора, проще временно хранить `stage_after_analytics.db` как полный snapshot. Если надо перенести только сценарии в будущую боевую/локальную БД, использовать export/import по `scenario_key`.

## Что не стоит делать

Не стоит:

- переносить всю SQLite-базу целиком только ради пары сценариев;
- ориентироваться на `id` шагов или сценариев между средами;
- рассчитывать, что изменения сценариев сохранятся в git сами по себе;
- редактировать сценарии на стенде без последующего export, если важно сохранить результат.

## Полезные замечания

- если сценарий использует вложения, пакет экспорта должен ехать вместе с папкой `assets/`;
- если нужно сохранить только часть сценариев аналитика, экспортируй только нужные `scenario_key`;
- после импорта сценариев с автозапуском надо проверить `employee_scope`, иначе кандидатовский сценарий может быть доступен сотрудникам или наоборот;
- перед массовым импортом лучше держать резервную копию целевой SQLite-базы.
