
# HR Bot

Сервис для работы с кандидатами и сотрудниками через FastAPI-админку и Telegram-бота.

В проекте два основных процесса:
- админка на FastAPI;
- Telegram-бот с APScheduler.

Данные по умолчанию хранятся в SQLite `hr_bot.db`, а файлы сохраняются локально в `storage/`.

## Стек

- FastAPI
- SQLAlchemy
- SQLite
- Aiogram
- APScheduler
- Jinja2

## Что важно для переноса проекта

Проект должен запускаться одинаково на Windows и macOS/Linux:
- зависимости ставятся из `requirements.txt`;
- настройки берутся из `.env`;
- локальные артефакты не должны попадать в git;
- админка и бот запускаются отдельными командами.

Для передачи проекта новому разработчику достаточно:
- склонировать репозиторий;
- создать `.env` из `.env.example`;
- поднять виртуальное окружение;
- установить зависимости;
- запустить админку и бота.

## Переменные окружения

Скопируйте `.env.example` в `.env` и заполните реальные значения:

```bash
cp .env.example .env
```

На Windows можно просто создать `.env` рядом с `.env.example`.

Минимально обязательное:

```env
TELEGRAM_BOT_TOKEN=your-real-bot-token
```

Остальные переменные уже имеют безопасные дефолты для локальной разработки.

## Локальный запуск на Windows

### 1. Создать окружение

```powershell
python -m venv .venv
```

Если `python` ещё не появился в PATH, можно использовать полный путь к установленному Python.

### 2. Установить зависимости

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Запустить админку

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Админка будет доступна по адресу `http://127.0.0.1:8000`.

### 4. Запустить Telegram-бота

Во втором терминале:

```powershell
.\.venv\Scripts\python.exe -m app.bot_runner
```

## Локальный запуск на macOS / Linux

### 1. Создать окружение

```bash
python3 -m venv .venv
```

### 2. Установить зависимости

```bash
.venv/bin/python -m pip install -r requirements.txt
```

### 3. Запустить админку

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Запустить Telegram-бота

Во втором терминале:

```bash
.venv/bin/python -m app.bot_runner
```

## Демо-режим

Для быстрого локального прогона можно включить demo mode:

```env
DEMO_MODE=true
DEMO_STEP_MINUTES=1
MANUAL_STEP_MINUTES=1
```

В этом режиме шаги сценариев идут быстро, без ожидания реальных дат и часов.

## Структура запуска

- `app.main:app` отвечает за веб-админку и HTML-страницы.
- `app.bot_runner` отвечает за Telegram-бота и периодический запуск планировщика.
- `app/config.py` читает `.env`.
- `app/database.py` поднимает БД и стартовую инициализацию.

## Где что хранится

- База данных: `hr_bot.db`
- Локальные файлы сотрудников: `storage/employee_files/`
- Файлы шагов сценариев: `storage/scenario_step_files/`
- Переменные окружения: `.env`
- Пример настроек: `.env.example`

## Дефолтные логины админки

Если не переопределять через `.env`, при инициализации создаются:

- `admin / admin123`
- `hr / hr123`

Для тестового и боевого стенда эти значения нужно заменить.

## Типичные проблемы

### На Windows не находится `python`

Используйте явный путь:

```powershell
.\.venv\Scripts\python.exe
```

Или откройте новый терминал после добавления Python в PATH.

### Бот запускается, но не отвечает

Проверьте:
- корректность `TELEGRAM_BOT_TOKEN`;
- доступ к `api.telegram.org`;
- нет ли блокировки со стороны сети, VPN, прокси или фаервола.

### Админка работает, бот падает по сети

Это не обязательно ошибка проекта. Часто это проблема соединения с Telegram API. В код уже добавлено автоматическое переподключение при временных сетевых ошибках.

## CI/CD

В репозитории настроены два GitHub Actions workflow:

- `CI`:
  - ставит зависимости;
  - компилирует Python-код;
  - делает базовый smoke import основных модулей.
- `Deploy Stage`:
  - запускается после успешного `CI` для ветки `main`;
  - подключается к stage-серверу по SSH;
  - делает `git pull --ff-only origin main`;
  - перезапускает `hr-bot-web` и `hr-bot-worker`.

Для автодеплоя на stage нужно добавить в GitHub Secrets:

- `STAGE_HOST`
- `STAGE_PORT`
- `STAGE_USERNAME`
- `STAGE_PASSWORD`
- `STAGE_APP_DIR`

Для текущего stage это обычно:

- `STAGE_HOST=92.51.38.32`
- `STAGE_PORT=22`
- `STAGE_USERNAME=root`
- `STAGE_APP_DIR=/opt/hr_bot`

Пароль сервера лучше хранить только в GitHub Secrets и не коммитить в репозиторий.
