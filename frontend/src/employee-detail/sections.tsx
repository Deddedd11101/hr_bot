import React from "react";

function Field(props: any) {
    return (
        <label className="react-field">
            <span>{props.label}</span>
            {props.children}
        </label>
    );
}

function OverviewList(props: any) {
    return (
        <section className="react-section">
            <h4>{props.title}</h4>
            {props.items.length ? (
                <div className="react-overview-list">
                    {props.items.map(function (item: any) {
                        return (
                            <article key={item.id} className="react-overview-item">
                                <div className="react-overview-item-head">
                                    <div>
                                        <strong>{item.title}</strong>
                                        {item.subtitle ? <p className="muted">{item.subtitle}</p> : null}
                                    </div>
                                    <div className="react-inline-actions">
                                        {item.link ? (
                                            <a href={item.link} className="react-overview-link">
                                                {item.linkLabel || "Открыть"}
                                            </a>
                                        ) : null}
                                        {item.extraAction ? (
                                            <button
                                                type="button"
                                                className="btn-secondary"
                                                onClick={item.extraAction}
                                            >
                                                {item.extraActionLabel || "Действие"}
                                            </button>
                                        ) : null}
                                    </div>
                                </div>
                            </article>
                        );
                    })}
                </div>
            ) : (
                <div className="react-overview-empty">{props.emptyText}</div>
            )}
        </section>
    );
}

export function EmployeeDetailLoading() {
    return <div className="react-loading-state react-detail-card">Загружаю карточку сотрудника...</div>;
}

export function EmployeeDetailError(props: any) {
    return (
        <div className="react-error-state react-detail-card">
            <p>{props.message || "Не удалось загрузить карточку сотрудника"}</p>
            <a href={props.listUrl} className="btn-secondary">
                Вернуться к списку
            </a>
        </div>
    );
}

export function EmployeeDetailHeader(props: any) {
    const { meta, classicUrl } = props;
    return (
        <div className="react-detail-header">
            <a href={meta.list_url} className="react-detail-back">
                {"← " + meta.list_title}
            </a>
            <a href={classicUrl} className="btn-secondary">
                Классическая карточка
            </a>
        </div>
    );
}

export function EmployeeProfileSection(props: any) {
    const {
        form,
        isCandidate,
        meta,
        options,
        workHoursParts,
        handleChange,
        handleWorkHoursChange,
        handleSubmit,
        saveState,
    } = props;

    return (
        <div className="react-detail-main">
            <section className="react-section">
                <h3>{isCandidate ? "Редактировать кандидата" : "Редактировать сотрудника"}</h3>
                <form className="react-detail-form" onSubmit={handleSubmit}>
                    <div className="react-form-section">
                        <h4>Основное</h4>
                        <div className="react-detail-form-grid">
                            <Field label="ФИО">
                                <input type="text" name="full_name" value={form.full_name} onChange={handleChange} />
                            </Field>
                            <Field label="Telegram-привязка">
                                <div className="react-readonly-field">
                                    {form.chat_id
                                        ? "Привязан к боту"
                                        : "Не привязан. Сотрудник должен открыть бота и нажать Start."}
                                </div>
                            </Field>
                            <Field label="Публичный Telegram @username">
                                <input
                                    type="text"
                                    name="chat_handle"
                                    value={form.chat_handle || ""}
                                    onChange={handleChange}
                                    placeholder="@username"
                                />
                            </Field>
                            <Field label={isCandidate ? "Предварительная дата выхода на работу" : "Дата выхода на работу"}>
                                <input type="date" name="first_workday" value={form.first_workday} onChange={handleChange} />
                            </Field>
                            <Field label={isCandidate ? "Желаемая должность" : "Должность"}>
                                <select name="desired_position" value={form.desired_position} onChange={handleChange}>
                                    <option value="">Не указана</option>
                                    {options.employee_role_values.map(function (role: string) {
                                        return (
                                            <option key={role} value={role}>
                                                {role}
                                            </option>
                                        );
                                    })}
                                </select>
                            </Field>
                            <Field label={isCandidate ? "Ожидания по зарплате" : "Доход / зарплата"}>
                                <input
                                    type="text"
                                    name="salary_expectation"
                                    value={form.salary_expectation}
                                    onChange={handleChange}
                                />
                            </Field>
                        </div>
                    </div>

                    {isCandidate ? (
                        <div className="react-form-section">
                            <h4>Этап найма</h4>
                            <div className="react-detail-form-grid">
                                <Field label="Текущий этап работы">
                                    <select
                                        name="candidate_work_stage"
                                        value={form.candidate_work_stage}
                                        onChange={handleChange}
                                    >
                                        <option value="">Не указан</option>
                                        {options.candidate_work_stage_values.map(function (option: any) {
                                            return (
                                                <option key={option.value} value={option.value}>
                                                    {option.label}
                                                </option>
                                            );
                                        })}
                                    </select>
                                </Field>
                                <Field label="Дедлайн тестового задания">
                                    <input
                                        type="datetime-local"
                                        name="test_task_due_at"
                                        value={form.test_task_due_at}
                                        onChange={handleChange}
                                    />
                                </Field>
                            </div>
                            <label className="react-checkbox">
                                <input
                                    type="checkbox"
                                    name="personal_data_consent"
                                    checked={!!form.personal_data_consent}
                                    onChange={handleChange}
                                />
                                <span>Согласие на ПДн (кандидат)</span>
                            </label>
                        </div>
                    ) : (
                        <React.Fragment>
                            <div className="react-form-section">
                                <h4>Профиль сотрудника</h4>
                                <div className="react-detail-form-grid">
                                    <Field label="Дата рождения">
                                        <input type="date" name="birth_date" value={form.birth_date} onChange={handleChange} />
                                    </Field>
                                    <Field label="Рабочая почта">
                                        <input
                                            type="email"
                                            inputMode="email"
                                            autoComplete="email"
                                            name="work_email"
                                            value={form.work_email}
                                            onChange={handleChange}
                                        />
                                    </Field>
                                    <Field label="Рабочие часы">
                                        <div className="react-time-range">
                                            <input
                                                type="time"
                                                value={workHoursParts.start}
                                                onChange={function (event) {
                                                    handleWorkHoursChange("start", event.target.value);
                                                }}
                                                aria-label="Начало рабочего дня"
                                            />
                                            <span className="react-time-range-separator">-</span>
                                            <input
                                                type="time"
                                                value={workHoursParts.end}
                                                onChange={function (event) {
                                                    handleWorkHoursChange("end", event.target.value);
                                                }}
                                                aria-label="Конец рабочего дня"
                                            />
                                        </div>
                                    </Field>
                                    <Field label="Статус">
                                        <select name="employee_stage" value={form.employee_stage} onChange={handleChange}>
                                            <option value="">Не указан</option>
                                            {options.employee_stage_values.map(function (option: any) {
                                                return (
                                                    <option key={option.value} value={option.value}>
                                                        {option.label}
                                                    </option>
                                                );
                                            })}
                                        </select>
                                    </Field>
                                </div>
                            </div>
                            <div className="react-form-section">
                                <h4>Роли и сопровождение</h4>
                                <div className="react-detail-form-grid">
                                    <Field label="Руководитель сотрудника">
                                        <input
                                            type="text"
                                            name="manager_chat_id"
                                            value={form.manager_chat_id}
                                            onChange={handleChange}
                                        />
                                    </Field>
                                    <Field label="Наставник (адаптация)">
                                        <input
                                            type="text"
                                            name="mentor_adaptation_chat_id"
                                            value={form.mentor_adaptation_chat_id}
                                            onChange={handleChange}
                                        />
                                    </Field>
                                    <Field label="Наставник (ИПР)">
                                        <input
                                            type="text"
                                            name="mentor_ipr_chat_id"
                                            value={form.mentor_ipr_chat_id}
                                            onChange={handleChange}
                                        />
                                    </Field>
                                </div>
                            </div>
                            <label className="react-checkbox">
                                <input
                                    type="checkbox"
                                    name="employee_data_consent"
                                    checked={!!form.employee_data_consent}
                                    onChange={handleChange}
                                />
                                <span>Согласие на ПДн (сотрудник)</span>
                            </label>
                        </React.Fragment>
                    )}

                    <div className="react-form-section">
                        <h4>Заметки</h4>
                        <Field label="Заметки HR">
                            <textarea name="notes" value={form.notes} onChange={handleChange} rows={5} />
                        </Field>
                        <label className="react-checkbox">
                            <input
                                type="checkbox"
                                name="is_bot_blocked"
                                checked={!!form.is_bot_blocked}
                                onChange={handleChange}
                            />
                            <span>Заблокировать доступ к чат-боту</span>
                        </label>
                    </div>

                    <div className="react-form-actions">
                        <span className={saveState.error ? "react-save-state is-error" : "react-save-state"}>
                            {saveState.message || " "}
                        </span>
                        <button type="submit" className="btn-primary" disabled={saveState.saving}>
                            {saveState.saving ? "Сохраняю..." : "Сохранить"}
                        </button>
                    </div>
                </form>
            </section>
        </div>
    );
}

export function EmployeeOperationsSection(props: any) {
    const {
        opsState,
        offerUrl,
        setOfferUrl,
        payload,
        scheduleForm,
        setScheduleForm,
        launchFlowKey,
        setLaunchFlowKey,
        fileForm,
        setFileForm,
        handleOfferSubmit,
        handleOfferDelete,
        handleScheduleSubmit,
        handleLaunchSubmit,
        handleFileSubmit,
        handleDeleteEmployee,
        fileItems,
        documentItems,
        launchItems,
    } = props;

    return (
        <div className="react-detail-side">
            <section className="react-section">
                <h4>Операции</h4>
                <div className={opsState.error ? "react-inline-message is-error" : "react-inline-message"}>
                    {opsState.message || (opsState.working ? "Выполняю действие..." : " ")}
                </div>
                <form className="react-inline-form" onSubmit={handleOfferSubmit}>
                    <Field label="Ссылка на оффер">
                        <input
                            type="text"
                            value={offerUrl}
                            onChange={function (event) {
                                setOfferUrl(event.target.value);
                            }}
                            placeholder="https://docs.google.com/..."
                        />
                    </Field>
                    <div className="react-inline-actions">
                        <button type="submit" className="btn-primary">
                            Сохранить оффер
                        </button>
                        {payload.document_links.length ? (
                            <button
                                type="button"
                                className="btn-secondary"
                                onClick={function () {
                                    handleOfferDelete(payload.document_links[0].id);
                                }}
                            >
                                Удалить ссылку
                            </button>
                        ) : null}
                    </div>
                </form>
                <form className="react-inline-form" onSubmit={handleScheduleSubmit}>
                    <Field label="Запланировать сценарий">
                        <select
                            value={scheduleForm.flow_key}
                            onChange={function (event) {
                                setScheduleForm(function (prev: any) {
                                    return Object.assign({}, prev, { flow_key: event.target.value });
                                });
                            }}
                        >
                            <option value="">Выберите сценарий</option>
                            {payload.options.scenarios.map(function (scenario: any) {
                                return (
                                    <option key={scenario.value} value={scenario.value}>
                                        {scenario.label}
                                    </option>
                                );
                            })}
                        </select>
                    </Field>
                    <Field label="Время отправки">
                        <input
                            type="datetime-local"
                            value={scheduleForm.requested_at}
                            onChange={function (event) {
                                setScheduleForm(function (prev: any) {
                                    return Object.assign({}, prev, { requested_at: event.target.value });
                                });
                            }}
                        />
                    </Field>
                    <button type="submit" className="btn-primary">
                        Запланировать
                    </button>
                </form>
                <form className="react-inline-form" onSubmit={handleLaunchSubmit}>
                    <Field label="Запустить сценарий сейчас">
                        <select
                            value={launchFlowKey}
                            onChange={function (event) {
                                setLaunchFlowKey(event.target.value);
                            }}
                        >
                            <option value="">Выберите сценарий</option>
                            {payload.options.scenarios.map(function (scenario: any) {
                                return (
                                    <option key={scenario.value} value={scenario.value}>
                                        {scenario.label}
                                    </option>
                                );
                            })}
                        </select>
                    </Field>
                    <button type="submit" className="btn-primary">
                        Запустить
                    </button>
                </form>
                <form className="react-inline-form" onSubmit={handleFileSubmit}>
                    <Field label="Загрузить файл">
                        <input
                            id="react-file-input"
                            type="file"
                            onChange={function (event) {
                                const file = event.target.files && event.target.files[0] ? event.target.files[0] : null;
                                setFileForm(function (prev: any) {
                                    return Object.assign({}, prev, { upload: file });
                                });
                            }}
                        />
                    </Field>
                    <label className="react-checkbox">
                        <input
                            type="checkbox"
                            checked={!!fileForm.send_to_channel}
                            onChange={function (event) {
                                setFileForm(function (prev: any) {
                                    return Object.assign({}, prev, { send_to_channel: event.target.checked });
                                });
                            }}
                        />
                        <span>Сразу отправить в мессенджер</span>
                    </label>
                    <button type="submit" className="btn-primary">
                        Загрузить файл
                    </button>
                </form>
            </section>
            <OverviewList title="Файлы" items={fileItems} emptyText="Файлов пока нет" />
            <OverviewList title="Оффер" items={documentItems} emptyText="Ссылка на оффер пока не добавлена" />
            <OverviewList
                title="Запланированные сценарии"
                items={launchItems}
                emptyText="Запланированных сценариев пока нет"
            />
            <section className="react-section react-section-danger">
                <h4>Редкие действия</h4>
                <p className="muted">Используй только если карточку действительно нужно убрать из системы.</p>
                <button type="button" className="btn-danger" onClick={handleDeleteEmployee}>
                    Удалить сотрудника
                </button>
            </section>
        </div>
    );
}
