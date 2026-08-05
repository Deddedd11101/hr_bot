---
title: Конфигурация HR Bot
date: 2026-05-11
status: active
doc_type: runbook
area: deploy
task_tokens:
  - HRB-DOC-02
related:
  - "[[stage-deploy]]"
  - "[[architecture]]"
  - "[[local-runbook]]"
source_of_truth: true
---

# Конфигурация


Конфигурация задается в:

- `app/config.py`;
- `.env.example`.

Приложение загружает `.env` через `load_dotenv(...)`, но по умолчанию **runtime environment важнее локального `.env`**.

Текущее правило:

- если `DOTENV_OVERRIDE=false` или переменная не задана, `.env` только дополняет отсутствующие значения;
- если `DOTENV_OVERRIDE=true`, `.env` может перекрывать shell/systemd env и подходит только для локального демо.

Это сделано намеренно: stage/systemd secrets не должны тихо ломаться из-за случайного `.env` в рабочей директории.

## Поддержанные переменные окружения

| Переменная               | Default                          | Назначение                                        | Примечания                                            |
| ------------------------ | -------------------------------- | ------------------------------------------------- | ----------------------------------------------------- |
| `DATABASE_URL`           | `sqlite:///./hr_bot.db`          | SQLAlchemy database URL                           | SQLite сейчас основной и наиболее проверенный путь    |
| `DOTENV_OVERRIDE`        | `false`                          | Разрешить `.env` перекрывать runtime env          | Нормально только для локального демо                  |
| `TELEGRAM_BOT_TOKEN`     | пусто                            | Telegram bot token                                | Обязателен для bot worker и любых отправок в Telegram |
| `TELEGRAM_PROXY_URL`     | пусто                            | HTTP/SOCKS proxy для Telegram API                  | Использовать, если stage-сеть не имеет прямого доступа к `api.telegram.org:443` |
| `TIMEZONE`               | `Europe/Moscow`                  | Таймзона scheduler                                | Используется APScheduler и date-based scenario timing |
| `DEMO_MODE`              | `false`                          | Ускоренный режим расписания для демо              | Существенно меняет semantics scheduler                |
| `DEMO_STEP_MINUTES`      | `1`                              | Интервал шагов в demo mode                        | Используется только при `DEMO_MODE=true`              |
| `MANUAL_STEP_MINUTES`    | `1`                              | Задержка между шагами manually launched сценариев | Используется для staged same-day follow-ups           |
| `PROBATION_WORKDAYS`     | `40`                             | Длина испытательного срока в рабочих днях         | Используется scheduler-triggered flows                |
| `TEST_URL`               | `https://example.com/test`       | Ссылка для test-related сообщений                 | На реальном стенде надо заменить                      |
| `PRACTICE_URL`           | `https://example.com/practice`   | Ссылка на practice materials                      | На реальном стенде надо заменить                      |
| `TASKS_URL`              | `https://example.com/tasks`      | Ссылка на task materials                          | На реальном стенде надо заменить                      |
| `FEEDBACK_URL`           | `https://example.com/feedback`   | Ссылка на feedback forms                          | На реальном стенде надо заменить                      |
| `FILE_STORAGE_DIR`       | `./storage/employee_files`       | Базовая директория файлов сотрудников             | На stage должна указывать на durable writable storage |
| `ADMIN_SESSION_SECRET`   | `change-me-admin-session-secret` | Секрет сессий админки                             | Обязательно заменить вне локального демо              |
| `ADMIN_SESSION_MAX_AGE_SECONDS` | `43200`                   | TTL signed session cookie                         | Для stage менять только осознанно                     |
| `ADMIN_SESSION_COOKIE_SECURE` | `false`                     | Ставить cookie только через HTTPS                 | На HTTPS stage должно быть `true`                     |
| `DEFAULT_ADMIN_LOGIN`    | `admin`                          | Bootstrap admin login                             | Используется startup seeding                          |
| `DEFAULT_ADMIN_PASSWORD` | `admin123`                       | Bootstrap admin password                          | Небезопасно вне локального bootstrap                  |
| `DEFAULT_HR_LOGIN`       | `hr`                             | Bootstrap HR login                                | Используется startup seeding                          |
| `DEFAULT_HR_PASSWORD`    | `hr123`                          | Bootstrap HR password                             | Небезопасно вне локального bootstrap                  |

## Группы конфигурации

### Обязательно для реального stage

- `TELEGRAM_BOT_TOKEN`
- `ADMIN_SESSION_SECRET`
- `ADMIN_SESSION_COOKIE_SECURE=true`, если stage открыт через HTTPS

Без них:

- bot worker не сможет нормально стартовать;
- signed admin sessions не являются production-safe при дефолтном секрете;
- browser может отправить session cookie по HTTP, если HTTPS уже есть, но `ADMIN_SESSION_COOKIE_SECURE` не включен.

### Runtime и расписание

- `TIMEZONE`
- `DOTENV_OVERRIDE`
- `DEMO_MODE`
- `DEMO_STEP_MINUTES`
- `MANUAL_STEP_MINUTES`
- `PROBATION_WORKDAYS`

Эти переменные меняют timing model продукта. Это не косметика.

### Контентные ссылки

- `TEST_URL`
- `PRACTICE_URL`
- `TASKS_URL`
- `FEEDBACK_URL`

Это зависимости message templates. Оставить example URLs в реальном окружении — контентная ошибка, а не мелкая настройка.

### Хранилище и persistence

- `DATABASE_URL`
- `FILE_STORAGE_DIR`

На stage эти значения определяют, где приложение хранит durable state. Их надо менять вместе с backup policy, а не случайно.

### Bootstrap-аккаунты

- `DEFAULT_ADMIN_LOGIN`
- `DEFAULT_ADMIN_PASSWORD`
- `DEFAULT_HR_LOGIN`
- `DEFAULT_HR_PASSWORD`

Это seed defaults, а не нормальная steady-state identity strategy.

## Правила для stage

### Можно хранить в git

- `.env.example`;
- non-secret defaults;
- документацию с именами переменных и их назначением.

### Нельзя коммитить

- реальный Telegram bot token;
- реальный admin session secret;
- любые server-specific secret values;
- скопированный stage `.env`.

### Наблюдаемое размещение stage-секретов

По текущему stage handoff реальные env values живут в systemd drop-ins, а не в git:

- `/etc/systemd/system/hr-bot-web.service.d/10-stage-env.conf`;
- `/etc/systemd/system/hr-bot-worker.service.d/10-stage-env.conf`.

## Практическая критика

- `DOTENV_OVERRIDE=true` допустим только локально. На stage/systemd это опасно: `.env` в app directory может перебить bot token, DATABASE_URL или scheduler flags.
- Default admin credentials в кодовом пути допустимы только как bootstrap. Если они остаются неизменными на реальном stage, это operational failure.
- `DEMO_MODE` не безобидный toggle. Он существенно меняет доставку сценариев и может скрыть timing bugs.
- Для SQLite current runtime использует `timeout=30` в SQLAlchemy connect args, чтобы переживать короткие write-lock конфликты между web и worker. Это не заменяет нормальную migration/DB strategy, но уменьшает ложные повторные доставки из-за transient lock.
