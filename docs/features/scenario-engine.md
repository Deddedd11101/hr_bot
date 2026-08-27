---
title: Движок сценариев
date: 2026-05-06
status: active
doc_type: feature
area: bot
task_tokens:
  - HRB-P1-02
  - HRB-P1-03
  - HRB-P1-04
related:
  - "[[architecture]]"
  - "[[features/notifications]]"
  - "[[features/employee-lifecycle]]"
  - "[[features/bot-identity]]"
source_of_truth: true
---

# Движок сценариев

## Назначение

Scenario engine превращает scenario templates плюс employee state в реальные bot communications и progress tracking.

Основной код находится в `app.scenario_engine`.

## Текущие входные данные

- `scenario_templates` — scenario-level metadata.
- `flow_step_templates` — step definitions.
- `scenario_progress` — runtime state.
- `employees` — personalization и field updates.
- `flow_launch_requests` — delayed или manual launches.
- `employee_document_links` / `employee_files` — персональные document slots для тегов вида `{doc:...}` и актуального resume slot.
- `document_library_items` — shared documents из `/app/documents`, которые можно переиспользовать как вложение шага.

## Audience targeting

- `employee_scope` продолжает отвечать за coarse split `кандидаты / сотрудники / все`.
- `role_scope` теперь допускает не одну должность, а нормализованный набор ролей в одном поле `scenario_templates.role_scope`.
- Для MVP набор хранится как CSV (`designer,analyst`), но API workspace отдает и raw `role_scope`, и нормализованный массив `role_scopes`.
- Пустое значение или только `all` означает все должности.
- Если backend получает смешанный payload вроде `all,designer`, `all` отбрасывается и остаются конкретные должности (`designer`); UI должен по возможности не давать смешивать `all` с конкретными ролями, но API нормализует такой ввод безопасно.
- Runtime matching трактует CSV как OR: сценарий подходит, если нормализованная должность сотрудника или кандидата входит в выбранный набор.
- Legacy одиночные значения (`designer`, `analyst` и т.д.) остаются валидными и парсятся как набор из одного элемента.
- `trigger_mode=candidate_hr_stage` / `status_transition` не меняет эту семантику: trigger сначала должен совпасть по HR-статусу кандидата, а затем пройти обычные `employee_scope` и `role_scope` фильтры.

## Текущие типы шагов

- `none` — информационный шаг без user response.
- `text` — ждет text input.
- `file` — ждет file upload.
- `buttons` / `branching` — ждет один из configured button options.
- `chain` — nested chain structure.
- `launch_scenario` — launch-oriented behavior, который сейчас перегружен в модели.

## Runtime-поведение

1. Найти scenario и первый step.
2. Отрендерить step text с employee context.
3. Разделить subject и recipient:
   - `context employee` / `subject employee` — по чьей карточке идет процесс;
   - `recipient employee` — кто реально получает шаг в Telegram.
4. Отправить text, optional employee card, optional attachment и optional buttons уже по resolved recipient.
5. Если в тексте есть `{doc:...}`, runtime резолвит персональный document slot сотрудника:
   - для link-based slot подставляет кликабельную ссылку в текст;
   - для file-based slot оставляет human-readable title в тексте и дополнительно отправляет сам файл в чат.
6. Сохранить progress в `scenario_progress`, включая короткую историю предыдущих интерактивных шагов и resolved recipient (`recipient_mode`, `recipient_employee_id`, `recipient_chat_id`).
7. Если user response не нужен, auto-advance к следующему step или schedule follow-up delivery.
8. Если response нужен, ждать text/file/button input от resolved recipient и применить result к employee state context employee.
9. Для активного интерактивного шага runtime поддерживает default `Назад`: для text/file это reply button, для button/branching — inline button. Откат возвращает только на предыдущий интерактивный шаг в рамках текущего незавершенного сценария.

## Scenario Notifications

- Сценарные уведомления ответственным отправляются только по явно настроенным правилам шага или кнопки.
- Runtime больше не отправляет legacy HR notification вида “прошел этап: `scenario_key/step_key`” при завершении шага или сценария.
- Технические `scenario_key` / `step_key` остаются только diagnostic/audit identifiers и не должны попадать в Telegram-текст для пользователей.
- Allowed recipient tokens для scenario notifications: `hr`, `manager`, `mentor_adaptation`, `mentor_ipr`.
- `hr` резолвится через `HrSettings.telegram_user_id`; если он не задан, HR notification пропускается без остановки сценария.
- `notification_recipient_ids` из HR settings не расширяет scenario notification token `hr`; это legacy/additional recipients для глобального notification layer.
- Runtime-only backward compatibility для старых строк БД `employee:{id}` сохраняется, но raw chat ids и произвольные recipient ids больше не резолвятся.

## Step attachments

- Шаг может использовать legacy uploaded attachment (`attachment_path` / `attachment_filename`) как раньше.
- Дополнительно шаг может ссылаться на shared document library через `flow_step_templates.attachment_document_item_id`.
- Если указаны оба источника, shared document library item имеет приоритет, а uploaded attachment остается fallback.
- Для `document_library_items.item_kind=file` runtime отправляет файл или фото из `storage/document_library`.
- Для `document_library_items.item_kind=link` runtime отправляет отдельное текстовое сообщение с названием, описанием и ссылкой.
- Если выбранный shared document неактивен, удален или не содержит пригодный file/link payload, runtime пробует старый uploaded attachment и не ломает старые шаги.
- Если shared document attachment был единственным отправляемым содержимым шага и не может быть доставлен, `send_step` возвращает `False`, пишет warning log и сохраняет причину в `ScenarioProgress.last_delivery_error`.
- Bot menu `send_document` использует тот же shared document library, но это отдельная action model; выбор вложения шага не меняет menu sets/buttons.

## Message template tags

- Тексты шагов сценария и scenario notifications проходят через общий TelegramSafeHTML renderer.
- Storage не меняется: поля текста остаются `TEXT`, а старые plain text сообщения остаются валидными.
- Runtime отправляет сообщения в Telegram HTML parse mode, но принимает только ограниченный safe subset:
  - `<b>`, `<strong>`, `<i>`, `<em>`, `<u>`, `<s>`, `<code>`, `<pre>`;
  - `<a href="...">` только с `http://`, `https://` или `mailto:`.
- Unknown tags, опасные attributes и ссылки с небезопасным protocol не уходят в Telegram как HTML.
- Broken HTML не должен ломать отправку сценария: renderer закрывает незакрытые разрешенные tags или деградирует в escaped text.
- Template values из карточки всегда HTML-escape'ятся перед подстановкой: ФИО, должность, даты, резюме и URL settings не могут вставить произвольный HTML.
- Stable template keys для UI-кнопок тегов:
  - `{employee_full_name}` — ФИО из карточки; fallback `Employee #id`, если ФИО пустое.
  - `{position}` — должность из карточки; fallback `не указана`.
  - `{first_workday}` — дата первого рабочего дня в формате `ДД.ММ.ГГГГ`; fallback `не указана`.
  - `{resume}` — имя файла из актуального `employee_document_links.slot_key=resume`; если slot пустой, fallback на последний `employee_files.category=resume`; если данных нет, fallback `резюме не загружено`.
- В UI эти теги могут называться по-русски: `ФИО`, `Должность`, `Дата первого рабочего дня`, `Резюме`.
- `{resume}` сейчас намеренно возвращает только human-readable имя файла или текстовый fallback, а не локальный storage path и не временную ссылку. Отправка/скачивание файла резюме остается отдельным file delivery contract.
- File-response step с `target_field=resume` делает загруженный файл новым актуальным resume slot; кнопка `Назад` откатывает этот slot вместе с file record, созданным последним ответом.
- File-response step принимает входящие Telegram media как `EmployeeFile`: обычный `document`, `photo`, `video` и `video_note`. Видео, отправленное как Telegram document, тоже проходит через тот же contract.
- Для `video` runtime сохраняет Telegram `file_id` / `file_unique_id`, filename или fallback `<file_unique_id>.mp4`, mime type и file size; для `video_note` используется fallback filename `<file_unique_id>.mp4` и `video/mp4`.
- Если caption содержит “тест”, входящий media сохраняется как `category=test_result` и продолжает запускать отдельное HR-уведомление о полученном тестовом задании; без такого caption это обычный `candidate_file`.
- Персональные document tags вида `{doc:Оффер}` остаются отдельной механикой: link-backed slot подставляется как ссылка, file-backed slot дополнительно отправляется файлом.

## Recipient model

- `scenario_templates.recipient_mode` определяет, кому доставлять шаги:
  - `self`;
  - `manager`;
  - `mentor_adaptation`;
  - `mentor_ipr`;
  - `hr`.
- Backward compatibility:
  - старые сценарии по умолчанию остаются `self`;
  - `trigger_mode=manager_assigned_adaptation` при legacy `recipient_mode=self` runtime трактует как `manager`, чтобы старые trigger-сценарии не слали шаги самому адаптируемому сотруднику.
- Runtime не меняет subject progress:
  - `ScenarioProgress.employee_id` всегда остается context employee;
  - recipient хранится отдельно, чтобы ответы руководителя или наставника продолжали тот же progress, а не создавали новый на их карточке.

## Semantics of `FlowLaunchRequest`

- `FlowLaunchRequest` не делает snapshot recipient-а на момент постановки события.
- Сознательное текущее правило:
  - request хранит только subject employee и `flow_key`;
  - recipient вычисляется заново в момент фактической обработки и отправки шага.
- Для `trigger_mode=candidate_hr_stage` карточка кандидата ставит `launch_type=status_transition` только при реальном изменении `candidate_work_stage`; повторное сохранение того же статуса не создает новый pending request.
- `candidate_hr_stage` является immediate trigger: обработка `status_transition` не требует `first_workday` и не проходит через date-anchor guard.
- Перед запуском `status_transition` worker заново сверяет текущий `candidate_work_stage` карточки с `scenario_templates.candidate_work_stage_trigger`; stale request после последующей смены статуса помечается обработанным без отправки.
- Backend нормализует ключи и человекочитаемые labels HR-статусов кандидата для сохранения и matching trigger settings, но каноническое значение в БД остается stage key (`offer`, `testing`, `preonboarding` и т.д.).
- Практический смысл:
  - если после события HR сменил руководителя или наставника до обработки очереди, сообщение уйдет уже актуальному назначенному адресату.
- Это особенно важно для `manager_assigned_adaptation`:
  - queue строится по адаптируемому сотруднику;
  - runtime решает, кто его текущий руководитель на момент отправки.
- Если продукту когда-нибудь понадобится жесткий snapshot “кому именно должно было уйти на момент события”, это уже другая модель:
  - отдельные recipient snapshot fields в launch queue или отдельная delivery/outbox table;
  - сейчас такую модель не вводим без отдельного согласования.

## Delivery failure behavior

- Если recipient не назначен или не привязан к Telegram, runtime не отправляет шаг молча в пустоту.
- В этом случае:
  - `ScenarioProgress.last_delivery_error` получает причину;
  - worker/web logs пишут warning;
  - pending `FlowLaunchRequest` все равно считается обработанным, если уже прошел через scheduler queue.
- Автоматического retry после исправления карточки сейчас нет.
- Текущая operational модель:
  - после исправления менеджера/наставника/Telegram binding нужен manual relaunch;
  - либо в будущем нужна отдельная retry-модель с явной семантикой повторной доставки.

Для time-based сценариев есть дополнительное правило:

- если сценарий активировали в тот же день, но время первого шага уже прошло, scheduler обязан отправить первый непройденный шаг немедленно, а не перескакивать к следующему time slot;
- если timed step был вызван самим scheduler, `send_step` не должен самостоятельно queue'ить следующий `specific_time` шаг через `FlowLaunchRequest`: дальнейшее расписание в этом режиме принадлежит scheduler, иначе возникают дубли и late-start skips.
- перед фактической отправкой scheduler обязан повторно проверить, что сценарий все еще совместим с текущим состоянием карточки; stale jobs и pending requests после смены `employee_stage` / даты-якоря должны silently отбрасываться, а не утекать в чат.

## Editor guardrails

- В React scenario workspace тип ответа теперь явно показывает, блокирует ли шаг поток.
- `text`, `file`, `buttons` и `branching` считаются интерактивными: после отправки такого шага бот ждет ответ и не переходит дальше автоматически.
- `none` не блокирует сценарий и должен использоваться для чисто информационных шагов, файлов и текстов, после которых не нужен ответ.
- Новые scenario-шаги, branch-шаги и chain-шаги не должны сохранять декоративный default text. Поле сообщения остается пустым, а подсказка показывается только как UI placeholder.

## Известные ограничения

- Transition model к другому scenario еще не semantically clean.
- Step notifications прикреплены на уровне step, button notifications — отдельно.
- Empty step content все еще требует отдельной runtime/UI-валидации: новые шаги больше не получают placeholder text, но полностью пустые сценарные сообщения пока остаются допустимым состоянием модели.
- Candidate и employee behavior все еще используют один engine и data model. Это удобно, но продуктово нечисто.
- `Назад` пока не является полноценным time-travel: он не откатывает уже совершенные side effects и не resurrect'ит сценарий, который уже был terminally completed ответом вроде отказа на consent step.

## Связанная работа

- `HRB-P1-02` transition semantics
- `HRB-P1-03` notification unification
- `HRB-P1-04` removal of empty and system messages

## Связанные документы

- [[features/notifications]]
- [[features/employee-lifecycle]]
- [[features/bot-identity]]
