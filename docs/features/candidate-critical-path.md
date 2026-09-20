---
title: Критический путь кандидата
date: 2026-09-20
status: active
doc_type: feature
area: bot
task_tokens:
  - HRB-P1-01
  - HRB-P1-04
related:
  - "[[features/scenario-engine]]"
  - "[[features/employee-lifecycle]]"
  - "[[features/bot-identity]]"
  - "[[stage-deploy]]"
source_of_truth: true
---

# Критический путь кандидата

Три места, которые несколько раз возвращались как регрессии. Здесь зафиксировано
ожидаемое поведение, какой автотест его держит, и как прогнать путь на стенде
руками. Главный критерий: путь проходит без ручного вмешательства, данные
сохраняются, сообщения не дублируются.

Сквозной автотест: `tests/test_candidate_flow_regression.py`. Он идёт через
реальные точки входа — `POST /api/employees/{id}` (карточка), тик планировщика
`schedule_all_employees`, обработчики бота `on_photo` / `on_video` /
`handle_text_event` — и считает сообщения по чату кандидата. Запускается в CI и
в preflight `Deploy Stage` вместе со всем набором тестов.

## 1. Смена HR-статуса запускает сценарий

| Ожидание | Где в коде | Тест |
| --- | --- | --- |
| Сохранение карточки с новым `candidate_work_stage` ставит один `FlowLaunchRequest(launch_type=status_transition)` на каждый сценарий с `trigger_mode=candidate_hr_stage` и совпадающим триггером | `app/web/employees.py::_queue_candidate_stage_transition_launches` | `test_employee_api_smoke::test_candidate_stage_update_queues_status_transition_launch_once` |
| Повторное сохранение с тем же статусом не ставит второй запрос | там же (`previous == next` → выход) | тот же + `test_candidate_flow_regression::test_status_change_launches_scenario_exactly_once` |
| Тик планировщика стартует сценарий ровно один раз: первый шаг и все `immediate`-шаги до первого ожидающего ответа доставляются, запрос помечается `processed_at`; следующий тик ничего не шлёт | `app/scheduler.py::schedule_all_employees` → `start_scenario` | `test_candidate_flow_regression::test_status_change_launches_scenario_exactly_once` |
| Если статус сменили ещё раз до тика, устаревший запрос отбрасывается без отправки | `app/scheduler.py` (сравнение триггера с текущим `candidate_work_stage`) | `test_scheduler_smoke::test_pending_candidate_hr_stage_request_skips_stale_status`, `test_candidate_flow_regression::test_status_flip_before_tick_starts_only_the_current_stage_scenario` |
| Заблокированному кандидату (`is_bot_blocked`) сценарий не уходит | `schedule_all_employees` / `start_scenario` | `test_candidate_flow_regression::test_blocked_candidate_does_not_receive_scenario` |
| Повторный вход в тот же статус — осознанный перезапуск: шаги приходят снова, но один раз | `start_scenario` → `reset_progress` | `test_candidate_flow_regression::test_returning_to_stage_restarts_scenario_once` |

Границы по дизайну, не баги:

- триггер срабатывает только при **изменении** статуса через сохранение карточки;
  создание карточки сразу с нужным статусом сценарий не запускает;
- запрос без `first_workday` обрабатывается (immediate trigger), см.
  `test_scheduler_smoke::test_pending_candidate_hr_stage_request_starts_without_first_workday`.

Важно для клиентов API: `POST /api/employees/{id}` с пустым `chat_id` **снимает
Telegram-привязку**. React-карточка всегда шлёт текущее значение; любой другой
клиент обязан делать так же, иначе сценарий уйдёт в «У получателя не привязан
Telegram».

## 2. Ответ на тестовое: файл / видео / ссылка

Шаг с `response_type=file` и `target_field=test_task_result`.

| Ожидание | Где в коде | Тест |
| --- | --- | --- |
| Документ, фото, видео, видео-заметка сохраняются как `EmployeeFile(category=test_result)` и записываются в актуальный слот `EmployeeDocumentLink(slot_key=test_task_result)` | `app/messaging/service.py::save_incoming_file` → `handle_saved_document` → `scenario_engine.handle_file_response` | `test_p0_behaviour::test_test_task_{document,photo,video,video_note}_answer_*` |
| `http://` / `https://` ссылка текстом засчитывается как ответ и пишет слот | `handle_text_response` (ветка test-task) | `test_p0_behaviour::test_test_task_http_link_answer_saves_slot_and_counts_as_response`, `test_candidate_flow_regression::test_link_answer_saves_slot_and_finishes_scenario` |
| Обычный текст без ссылки получает подсказку и **не** двигает сценарий | там же (`TEST_TASK_RESULT_TEXT_PROMPT`) | `test_p0_behaviour::test_test_task_non_link_text_answer_prompts_and_keeps_waiting`, `test_candidate_flow_regression::test_plain_text_on_task_step_prompts_and_keeps_waiting` |
| После валидного ответа следующий шаг доставляется ровно один раз | `advance_after_response` | `test_candidate_flow_regression::test_{photo,video,link}_answer_saves_slot_and_finishes_scenario` |
| Файл от неизвестного или заблокированного пользователя не сохраняется | `resolve_inbound_access` | `test_p0_behaviour::test_save_incoming_file_rejects_unknown_user`, `test_resolve_inbound_access_marks_unknown_and_blocked` |

## 3. Финальный шаг: одно сообщение и завершение

| Ожидание | Где в коде | Тест |
| --- | --- | --- |
| Шаг с `is_terminal` отправляется один раз, `scenario_progress.is_completed=True`, следующий root-шаг не отправляется | `resolve_followup_step` (terminal → `None`), `send_step` | `test_scenario_engine_smoke::test_terminal_*`, `test_candidate_flow_regression::test_terminal_step_ends_scenario_and_bot_stays_silent` |
| Terminal `branching`/`chain` сначала доставляет выбранную ветку, потом завершает | там же | `test_scenario_engine_smoke::test_terminal_branch_chain_stops_after_last_child_without_root_fallthrough` |
| После завершения тик планировщика, лишний текст и повторный файл ничего не шлют | `get_waiting_progress` (нет ожидающего progress), `handle_text_event` → `ignored` | `test_candidate_flow_regression::test_terminal_step_ends_scenario_and_bot_stays_silent`, `test_p0_behaviour::test_handle_text_event_ignores_stray_text_for_known_employee` |
| Технического «этап пройден» HR не получает; только явные notification rules | `send_step` / notifications | `test_employee_api_smoke::test_scenario_completion_does_not_send_technical_hr_stage_message` |

## Ручной прогон на стенде

Нужен тестовый кандидат, привязанный к боту с реального Telegram-аккаунта
(другие карточки не трогать). Перед прогоном интегратор читает
`flow_launch_requests`, `scenario_progress`, `onboarding_events` по этому
`employee_id` на копии базы или через API карточки, после каждого шага — снова.

1. Сценарий-фикстура на стенде: `trigger_mode=candidate_hr_stage`, триггер
   «Тестирование», шаги: текст (immediate) → тестовое (`file`,
   `test_task_result`) → финал (`is_terminal`) → контрольный шаг после финала.
2. В карточке кандидата поставить «Тестирование», сохранить. Ожидание: один
   pending `flow_launch_requests`; в Telegram в течение интервала планировщика
   приходят интро и вопрос про тестовое — по одному разу; запрос
   `processed_at` заполнен.
3. Сохранить карточку ещё раз без изменений. Ожидание: новых запросов и
   сообщений нет.
4. Отправить боту обычный текст. Ожидание: подсказка «пришлите файл или
   ссылку», сценарий остаётся на шаге тестового.
5. Отправить фото (или видео/документ/ссылку). Ожидание: в карточке появился
   ответ на тестовое; пришёл финальный текст — один раз; контрольный шаг не
   пришёл; `scenario_progress.is_completed=1`.
6. Написать боту ещё раз и отправить ещё один файл. Ожидание: тишина в ответ
   на текст; файл сохраняется в карточку как обычный файл, сценарий не
   перезапускается.
7. Вернуть статус на предыдущий и снова на «Тестирование». Ожидание: интро и
   вопрос приходят снова ровно один раз.

Результат прогона фиксируется в [[stage-change-log]] отдельно от автотестов:
«сценарий проверен» только после пунктов 2–7 в реальном Telegram.
