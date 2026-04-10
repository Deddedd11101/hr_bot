(function () {
    const rootElement = document.getElementById("react-employee-edit-root");
    if (!rootElement || !window.React || !window.ReactDOM) {
        return;
    }

    const e = window.React.createElement;
    const apiUrl = rootElement.dataset.apiUrl;
    const saveUrl = rootElement.dataset.saveUrl;
    const classicUrl = rootElement.dataset.classicUrl;
    const listUrl = rootElement.dataset.listUrl;

    function Field(props) {
        return e(
            "label",
            { className: "react-field" },
            e("span", null, props.label),
            props.children
        );
    }

    function OverviewList(props) {
        return e(
            "section",
            { className: "react-section" },
            e("h4", null, props.title),
            props.items.length
                ? e(
                    "div",
                    { className: "react-overview-list" },
                    props.items.map(function (item) {
                        return e(
                            "article",
                            { key: item.id, className: "react-overview-item" },
                            e(
                                "div",
                                { className: "react-overview-item-head" },
                                e(
                                    "div",
                                    null,
                                    e("strong", null, item.title),
                                    item.subtitle ? e("p", { className: "muted" }, item.subtitle) : null
                                ),
                                e(
                                    "div",
                                    { className: "react-inline-actions" },
                                    item.link
                                        ? e(
                                            "a",
                                            { href: item.link, className: "react-overview-link" },
                                            item.linkLabel || "Открыть"
                                        )
                                        : null,
                                    item.extraAction
                                        ? e(
                                            "button",
                                            {
                                                type: "button",
                                                className: "btn-secondary",
                                                onClick: item.extraAction,
                                            },
                                            item.extraActionLabel || "Действие"
                                        )
                                        : null
                                )
                            )
                        );
                    })
                )
                : e("div", { className: "react-overview-empty" }, props.emptyText)
        );
    }

    function updatePayloadState(setState, setForm, payload) {
        setState({
            loading: false,
            error: "",
            payload: payload,
        });
        setForm(payload.employee);
    }

    function EmployeeEditApp() {
        const [state, setState] = window.React.useState({
            loading: true,
            error: "",
            payload: null,
        });
        const [form, setForm] = window.React.useState(null);
        const [saveState, setSaveState] = window.React.useState({
            saving: false,
            message: "",
            error: false,
        });
        const [opsState, setOpsState] = window.React.useState({
            message: "",
            error: false,
            working: false,
        });
        const [offerUrl, setOfferUrl] = window.React.useState("");
        const [scheduleForm, setScheduleForm] = window.React.useState({
            flow_key: "",
            requested_at: "",
        });
        const [launchFlowKey, setLaunchFlowKey] = window.React.useState("");
        const [fileForm, setFileForm] = window.React.useState({
            upload: null,
            send_to_channel: false,
        });

        window.React.useEffect(function () {
            let isMounted = true;

            fetch(apiUrl, {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("Не удалось загрузить карточку сотрудника");
                    }
                    return response.json();
                })
                .then(function (payload) {
                    if (!isMounted) {
                        return;
                    }
                    setState({
                        loading: false,
                        error: "",
                        payload: payload,
                    });
                    setForm(payload.employee);
                    setOfferUrl(payload.document_links.length ? (payload.document_links[0].url || "") : "");
                    setLaunchFlowKey(payload.options.scenarios.length ? payload.options.scenarios[0].value : "");
                })
                .catch(function (error) {
                    if (!isMounted) {
                        return;
                    }
                    setState({
                        loading: false,
                        error: error.message || "Не удалось загрузить карточку сотрудника",
                        payload: null,
                    });
                });

            return function () {
                isMounted = false;
            };
        }, []);

        function setOperationMessage(message, isError) {
            setOpsState({
                message: message,
                error: !!isError,
                working: false,
            });
        }

        function handleChange(event) {
            const target = event.target;
            const value = target.type === "checkbox" ? target.checked : target.value;
            setForm(function (prev) {
                return Object.assign({}, prev, {
                    [target.name]: value,
                });
            });
        }

        function handleSubmit(event) {
            event.preventDefault();
            setSaveState({
                saving: true,
                message: "",
                error: false,
            });

            fetch(saveUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "application/json",
                },
                body: JSON.stringify(form),
            })
                .then(function (response) {
                    if (!response.ok) {
                        return response.json().catch(function () { return {}; }).then(function (payload) {
                            throw new Error(payload.detail || "Не удалось сохранить изменения");
                        });
                    }
                    return response.json();
                })
                .then(function (payload) {
                    updatePayloadState(setState, setForm, payload);
                    setSaveState({
                        saving: false,
                        message: "Изменения сохранены",
                        error: false,
                    });
                })
                .catch(function (error) {
                    setSaveState({
                        saving: false,
                        message: error.message || "Не удалось сохранить изменения",
                        error: true,
                    });
                });
        }

        function handleOfferSubmit(event) {
            event.preventDefault();
            setOpsState({ message: "", error: false, working: true });
            fetch(apiUrl + "/document-links", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "application/json",
                },
                body: JSON.stringify({ url: offerUrl }),
            })
                .then(function (response) {
                    if (!response.ok) {
                        return response.json().catch(function () { return {}; }).then(function (payload) {
                            throw new Error(payload.detail || "Не удалось сохранить оффер");
                        });
                    }
                    return response.json();
                })
                .then(function (payload) {
                    updatePayloadState(setState, setForm, payload.payload);
                    setOfferUrl(payload.item ? payload.item.url : offerUrl);
                    setOperationMessage("Ссылка на оффер сохранена", false);
                })
                .catch(function (error) {
                    setOperationMessage(error.message || "Не удалось сохранить оффер", true);
                });
        }

        function handleOfferDelete(linkId) {
            if (!window.confirm("Удалить ссылку на оффер?")) {
                return;
            }
            setOpsState({ message: "", error: false, working: true });
            fetch(apiUrl + "/document-links/" + linkId, {
                method: "DELETE",
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            })
                .then(function (response) {
                    if (!response.ok) {
                        return response.json().catch(function () { return {}; }).then(function (payload) {
                            throw new Error(payload.detail || "Не удалось удалить ссылку");
                        });
                    }
                    return response.json();
                })
                .then(function (payload) {
                    updatePayloadState(setState, setForm, payload);
                    setOfferUrl("");
                    setOperationMessage("Ссылка на оффер удалена", false);
                })
                .catch(function (error) {
                    setOperationMessage(error.message || "Не удалось удалить ссылку", true);
                });
        }

        function handleScheduleSubmit(event) {
            event.preventDefault();
            setOpsState({ message: "", error: false, working: true });
            fetch(apiUrl + "/schedule", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "application/json",
                },
                body: JSON.stringify(scheduleForm),
            })
                .then(function (response) {
                    if (!response.ok) {
                        return response.json().catch(function () { return {}; }).then(function (payload) {
                            throw new Error(payload.detail || "Не удалось запланировать сценарий");
                        });
                    }
                    return response.json();
                })
                .then(function (payload) {
                    updatePayloadState(setState, setForm, payload);
                    setOperationMessage("Сценарий запланирован", false);
                })
                .catch(function (error) {
                    setOperationMessage(error.message || "Не удалось запланировать сценарий", true);
                });
        }

        function handleLaunchSubmit(event) {
            event.preventDefault();
            setOpsState({ message: "", error: false, working: true });
            fetch(apiUrl + "/launch", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "application/json",
                },
                body: JSON.stringify({ flow_key: launchFlowKey }),
            })
                .then(function (response) {
                    if (!response.ok) {
                        return response.json().catch(function () { return {}; }).then(function (payload) {
                            throw new Error(payload.detail || "Не удалось запустить сценарий");
                        });
                    }
                    return response.json();
                })
                .then(function (payload) {
                    updatePayloadState(setState, setForm, payload);
                    setOperationMessage("Сценарий запущен", false);
                })
                .catch(function (error) {
                    setOperationMessage(error.message || "Не удалось запустить сценарий", true);
                });
        }

        function handleScheduledDelete(launchRequestId) {
            if (!window.confirm("Удалить запланированную отправку?")) {
                return;
            }
            setOpsState({ message: "", error: false, working: true });
            fetch(apiUrl + "/schedule/" + launchRequestId, {
                method: "DELETE",
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            })
                .then(function (response) {
                    if (!response.ok) {
                        return response.json().catch(function () { return {}; }).then(function (payload) {
                            throw new Error(payload.detail || "Не удалось удалить отправку");
                        });
                    }
                    return response.json();
                })
                .then(function (payload) {
                    updatePayloadState(setState, setForm, payload);
                    setOperationMessage("Запланированная отправка удалена", false);
                })
                .catch(function (error) {
                    setOperationMessage(error.message || "Не удалось удалить отправку", true);
                });
        }

        function handleFileSubmit(event) {
            event.preventDefault();
            if (!fileForm.upload) {
                setOperationMessage("Выбери файл для загрузки", true);
                return;
            }
            setOpsState({ message: "", error: false, working: true });
            const body = new FormData();
            body.append("upload", fileForm.upload);
            body.append("category", "hr_file");
            body.append("send_to_channel", fileForm.send_to_channel ? "true" : "false");
            fetch(apiUrl + "/files", {
                method: "POST",
                credentials: "same-origin",
                body: body,
            })
                .then(function (response) {
                    if (!response.ok) {
                        return response.json().catch(function () { return {}; }).then(function (payload) {
                            throw new Error(payload.detail || "Не удалось загрузить файл");
                        });
                    }
                    return response.json();
                })
                .then(function (payload) {
                    updatePayloadState(setState, setForm, payload);
                    setFileForm({ upload: null, send_to_channel: false });
                    const fileInput = document.getElementById("react-file-input");
                    if (fileInput) {
                        fileInput.value = "";
                    }
                    setOperationMessage("Файл загружен", false);
                })
                .catch(function (error) {
                    setOperationMessage(error.message || "Не удалось загрузить файл", true);
                });
        }

        function handleSendFile(fileId) {
            setOpsState({ message: "", error: false, working: true });
            fetch(apiUrl + "/files/" + fileId + "/send", {
                method: "POST",
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            })
                .then(function (response) {
                    if (!response.ok) {
                        return response.json().catch(function () { return {}; }).then(function (payload) {
                            throw new Error(payload.detail || "Не удалось отправить файл");
                        });
                    }
                    return response.json();
                })
                .then(function (payload) {
                    updatePayloadState(setState, setForm, payload);
                    setOperationMessage("Файл отправлен в мессенджер", false);
                })
                .catch(function (error) {
                    setOperationMessage(error.message || "Не удалось отправить файл", true);
                });
        }

        function handleDeleteEmployee() {
            if (!window.confirm("Удалить этого сотрудника?")) {
                return;
            }
            setOpsState({ message: "", error: false, working: true });
            fetch(apiUrl, {
                method: "DELETE",
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            })
                .then(function (response) {
                    if (!response.ok) {
                        return response.json().catch(function () { return {}; }).then(function (payload) {
                            throw new Error(payload.detail || "Не удалось удалить сотрудника");
                        });
                    }
                    return response.json();
                })
                .then(function (payload) {
                    window.location.href = payload.redirect_url || listUrl;
                })
                .catch(function (error) {
                    setOperationMessage(error.message || "Не удалось удалить сотрудника", true);
                });
        }

        if (state.loading || !form) {
            return e("div", { className: "react-loading-state react-detail-card" }, "Загружаю карточку сотрудника...");
        }

        if (state.error || !state.payload) {
            return e(
                "div",
                { className: "react-error-state react-detail-card" },
                e("p", null, state.error || "Не удалось загрузить карточку сотрудника"),
                e("a", { href: listUrl, className: "btn-secondary" }, "Вернуться к списку")
            );
        }

        const payload = state.payload;
        const meta = payload.meta;
        const options = payload.options;
        const isCandidate = !!meta.is_candidate;

        const fileItems = payload.files.map(function (file) {
            return {
                id: file.id,
                title: file.original_filename || "Файл",
                subtitle: file.direction + " · " + file.created_at_label,
                link: file.download_url,
                linkLabel: "Скачать",
                extraAction: file.can_send_to_channel ? function () { handleSendFile(file.id); } : null,
                extraActionLabel: file.can_send_to_channel ? "Отправить в мессенджер" : null,
            };
        });

        const documentItems = payload.document_links.map(function (item) {
            return {
                id: item.id,
                title: item.title,
                subtitle: item.scenario_tag,
                link: item.url,
                linkLabel: "Открыть",
            };
        });

        const launchItems = payload.scheduled_launches.map(function (item) {
            return {
                id: "scheduled-" + item.id,
                title: item.scenario_title,
                subtitle: "Отправка: " + item.requested_at_label,
                link: item.scenario_url,
                linkLabel: "Сценарий",
                extraAction: function () { handleScheduledDelete(item.id); },
                extraActionLabel: "Удалить",
            };
        });

        return e(
            "div",
            { className: "react-detail-page" },
            e(
                "div",
                { className: "react-detail-header" },
                e("a", { href: meta.list_url, className: "react-detail-back" }, "← " + meta.list_title),
                e("a", { href: classicUrl, className: "btn-secondary" }, "Классическая карточка")
            ),
            e(
                "section",
                { className: "react-detail-card" },
                e(
                    "div",
                    { className: "react-detail-card-head" },
                    e(
                        "div",
                        null,
                        e("p", { className: "react-page-eyebrow" }, isCandidate ? "Candidate Profile" : "Employee Profile"),
                        e("h2", null, form.full_name || ("Сотрудник #" + form.id)),
                        e(
                            "p",
                            { className: "muted" },
                            isCandidate
                                ? "Рабочая React-версия карточки кандидата с основными действиями и обзором файлов, оффера и сценариев."
                                : "Рабочая React-версия карточки сотрудника с редактированием основных данных и быстрыми операциями."
                        ),
                        e(
                            "div",
                            { className: "react-overview-row" },
                            e("span", { className: "react-overview-pill" }, meta.status_label || "Без статуса"),
                            isCandidate
                                ? e("span", { className: "react-overview-pill" }, meta.candidate_work_stage_label || "Без этапа")
                                : e("span", { className: "react-overview-pill" }, "Стаж: " + meta.tenure_years + " лет")
                        )
                    )
                    ),
                e(
                    "div",
                    { className: "react-detail-grid" },
                    e(
                        "div",
                        { className: "react-detail-main" },
                        e(
                            "section",
                            { className: "react-section" },
                            e("h3", null, isCandidate ? "Редактировать кандидата" : "Редактировать сотрудника"),
                            e(
                                "form",
                                { className: "react-detail-form", onSubmit: handleSubmit },
                                e(
                                    "div",
                                    { className: "react-form-section" },
                                    e("h4", null, "Основное"),
                                    e(
                                        "div",
                                        { className: "react-detail-form-grid" },
                                        e(
                                            Field,
                                            { label: "ФИО" },
                                            e("input", {
                                                type: "text",
                                                name: "full_name",
                                                value: form.full_name,
                                                onChange: handleChange,
                                            })
                                        ),
                                        e(
                                            Field,
                                            { label: "ID пользователя в канале" },
                                            e("input", {
                                                type: "text",
                                                name: "chat_id",
                                                value: form.chat_id,
                                                onChange: handleChange,
                                            })
                                        ),
                                        e(
                                            Field,
                                            { label: "Публичный Telegram @username" },
                                            e("input", {
                                                type: "text",
                                                name: "chat_handle",
                                                value: form.chat_handle || "",
                                                onChange: handleChange,
                                                placeholder: "@username",
                                            })
                                        ),
                                        e(
                                            Field,
                                            { label: isCandidate ? "Предварительная дата выхода на работу" : "Дата выхода на работу" },
                                            e("input", {
                                                type: "date",
                                                name: "first_workday",
                                                value: form.first_workday,
                                                onChange: handleChange,
                                            })
                                        ),
                                        e(
                                            Field,
                                            { label: isCandidate ? "Желаемая должность" : "Должность" },
                                            e(
                                                "select",
                                                {
                                                    name: "desired_position",
                                                    value: form.desired_position,
                                                    onChange: handleChange,
                                                },
                                                e("option", { value: "" }, "Не указана"),
                                                options.employee_role_values.map(function (role) {
                                                    return e("option", { key: role, value: role }, role);
                                                })
                                            )
                                        )
                                    )
                                ),
                                isCandidate
                                    ? e(
                                        "div",
                                        { className: "react-form-section" },
                                        e("h4", null, "Этап найма"),
                                        e(
                                            "div",
                                            { className: "react-detail-form-grid" },
                                            e(
                                                Field,
                                                { label: "Текущий этап работы" },
                                                e(
                                                    "select",
                                                    {
                                                        name: "candidate_work_stage",
                                                        value: form.candidate_work_stage,
                                                        onChange: handleChange,
                                                    },
                                                    e("option", { value: "" }, "Не указан"),
                                                    options.candidate_work_stage_values.map(function (option) {
                                                        return e("option", { key: option.value, value: option.value }, option.label);
                                                    })
                                                )
                                            ),
                                            e(
                                                Field,
                                                { label: "Ожидания по зарплате" },
                                                e("input", {
                                                    type: "text",
                                                    name: "salary_expectation",
                                                    value: form.salary_expectation,
                                                    onChange: handleChange,
                                                })
                                            ),
                                            e(
                                                Field,
                                                { label: "Дедлайн тестового задания" },
                                                e("input", {
                                                    type: "datetime-local",
                                                    name: "test_task_due_at",
                                                    value: form.test_task_due_at,
                                                    onChange: handleChange,
                                                })
                                            )
                                        ),
                                        e(
                                            "label",
                                            { className: "react-checkbox" },
                                            e("input", {
                                                type: "checkbox",
                                                name: "personal_data_consent",
                                                checked: !!form.personal_data_consent,
                                                onChange: handleChange,
                                            }),
                                            e("span", null, "Согласие на ПДн (кандидат)")
                                        )
                                    )
                                    : e(
                                        window.React.Fragment,
                                        null,
                                        e(
                                            "div",
                                            { className: "react-form-section" },
                                            e("h4", null, "Профиль сотрудника"),
                                            e(
                                                "div",
                                                { className: "react-detail-form-grid" },
                                                e(
                                                    Field,
                                                    { label: "Дата рождения" },
                                                    e("input", {
                                                        type: "date",
                                                        name: "birth_date",
                                                        value: form.birth_date,
                                                        onChange: handleChange,
                                                    })
                                                ),
                                                e(
                                                    Field,
                                                    { label: "Рабочая почта" },
                                                    e("input", {
                                                        type: "text",
                                                        name: "work_email",
                                                        value: form.work_email,
                                                        onChange: handleChange,
                                                    })
                                                ),
                                                e(
                                                    Field,
                                                    { label: "Рабочие часы" },
                                                    e("input", {
                                                        type: "text",
                                                        name: "work_hours",
                                                        value: form.work_hours,
                                                        onChange: handleChange,
                                                    })
                                                ),
                                                e(
                                                    Field,
                                                    { label: "Статус" },
                                                    e(
                                                        "select",
                                                        {
                                                            name: "employee_stage",
                                                            value: form.employee_stage,
                                                            onChange: handleChange,
                                                        },
                                                        e("option", { value: "" }, "Не указан"),
                                                        options.employee_stage_values.map(function (option) {
                                                            return e("option", { key: option.value, value: option.value }, option.label);
                                                        })
                                                    )
                                                )
                                            )
                                        ),
                                        e(
                                            "div",
                                            { className: "react-form-section" },
                                            e("h4", null, "Роли и сопровождение"),
                                            e(
                                                "div",
                                                { className: "react-detail-form-grid" },
                                                e(
                                                    Field,
                                                    { label: "Руководитель сотрудника" },
                                                    e("input", {
                                                        type: "text",
                                                        name: "manager_chat_id",
                                                        value: form.manager_chat_id,
                                                        onChange: handleChange,
                                                    })
                                                ),
                                                e(
                                                    Field,
                                                    { label: "Наставник (адаптация)" },
                                                    e("input", {
                                                        type: "text",
                                                        name: "mentor_adaptation_chat_id",
                                                        value: form.mentor_adaptation_chat_id,
                                                        onChange: handleChange,
                                                    })
                                                ),
                                                e(
                                                    Field,
                                                    { label: "Наставник (ИПР)" },
                                                    e("input", {
                                                        type: "text",
                                                        name: "mentor_ipr_chat_id",
                                                        value: form.mentor_ipr_chat_id,
                                                        onChange: handleChange,
                                                    })
                                                )
                                            )
                                        ),
                                        e(
                                            "label",
                                            { className: "react-checkbox" },
                                            e("input", {
                                                type: "checkbox",
                                                name: "employee_data_consent",
                                                checked: !!form.employee_data_consent,
                                                onChange: handleChange,
                                            }),
                                            e("span", null, "Согласие на ПДн (сотрудник)")
                                        )
                                    ),
                                e(
                                    "div",
                                    { className: "react-form-section" },
                                    e("h4", null, "Заметки"),
                                    e(
                                        Field,
                                        { label: "Заметки HR" },
                                        e("textarea", {
                                            name: "notes",
                                            value: form.notes,
                                            onChange: handleChange,
                                            rows: 5,
                                        })
                                    )
                                ),
                                e(
                                    "div",
                                    { className: "react-form-actions" },
                                    e(
                                        "span",
                                        {
                                            className: saveState.error
                                                ? "react-save-state is-error"
                                                : "react-save-state",
                                        },
                                        saveState.message || " "
                                    ),
                                    e(
                                        "button",
                                        {
                                            type: "submit",
                                            className: "btn-primary",
                                            disabled: saveState.saving,
                                        },
                                        saveState.saving ? "Сохраняю..." : "Сохранить"
                                    )
                                )
                            )
                        )
                    ),
                    e(
                        "div",
                        { className: "react-detail-side" },
                        e(
                            "section",
                            { className: "react-section" },
                            e("h4", null, "Операции"),
                            e(
                                "div",
                                {
                                    className: opsState.error
                                        ? "react-inline-message is-error"
                                        : "react-inline-message",
                                },
                                opsState.message || (opsState.working ? "Выполняю действие..." : " ")
                            ),
                            e(
                                "form",
                                { className: "react-inline-form", onSubmit: handleOfferSubmit },
                                e(
                                    Field,
                                    { label: "Ссылка на оффер" },
                                    e("input", {
                                        type: "text",
                                        value: offerUrl,
                                        onChange: function (event) { setOfferUrl(event.target.value); },
                                        placeholder: "https://docs.google.com/...",
                                    })
                                ),
                                e(
                                    "div",
                                    { className: "react-inline-actions" },
                                    e("button", { type: "submit", className: "btn-primary" }, "Сохранить оффер"),
                                    payload.document_links.length
                                        ? e(
                                            "button",
                                            {
                                                type: "button",
                                                className: "btn-secondary",
                                                onClick: function () { handleOfferDelete(payload.document_links[0].id); },
                                            },
                                            "Удалить ссылку"
                                        )
                                        : null
                                )
                            ),
                            e(
                                "form",
                                { className: "react-inline-form", onSubmit: handleScheduleSubmit },
                                e(
                                    Field,
                                    { label: "Запланировать сценарий" },
                                    e(
                                        "select",
                                        {
                                            value: scheduleForm.flow_key,
                                            onChange: function (event) {
                                                setScheduleForm(function (prev) {
                                                    return Object.assign({}, prev, { flow_key: event.target.value });
                                                });
                                            },
                                        },
                                        e("option", { value: "" }, "Выберите сценарий"),
                                        options.scenarios.map(function (scenario) {
                                            return e("option", { key: scenario.value, value: scenario.value }, scenario.label);
                                        })
                                    )
                                ),
                                e(
                                    Field,
                                    { label: "Время отправки" },
                                    e("input", {
                                        type: "datetime-local",
                                        value: scheduleForm.requested_at,
                                        onChange: function (event) {
                                            setScheduleForm(function (prev) {
                                                return Object.assign({}, prev, { requested_at: event.target.value });
                                            });
                                        },
                                    })
                                ),
                                e("button", { type: "submit", className: "btn-primary" }, "Запланировать")
                            ),
                            e(
                                "form",
                                { className: "react-inline-form", onSubmit: handleLaunchSubmit },
                                e(
                                    Field,
                                    { label: "Запустить сценарий сейчас" },
                                    e(
                                        "select",
                                        {
                                            value: launchFlowKey,
                                            onChange: function (event) { setLaunchFlowKey(event.target.value); },
                                        },
                                        e("option", { value: "" }, "Выберите сценарий"),
                                        options.scenarios.map(function (scenario) {
                                            return e("option", { key: scenario.value, value: scenario.value }, scenario.label);
                                        })
                                    )
                                ),
                                e("button", { type: "submit", className: "btn-primary" }, "Запустить")
                            ),
                            e(
                                "form",
                                { className: "react-inline-form", onSubmit: handleFileSubmit },
                                e(
                                    Field,
                                    { label: "Загрузить файл" },
                                    e("input", {
                                        id: "react-file-input",
                                        type: "file",
                                        onChange: function (event) {
                                            const file = event.target.files && event.target.files[0] ? event.target.files[0] : null;
                                            setFileForm(function (prev) {
                                                return Object.assign({}, prev, { upload: file });
                                            });
                                        },
                                    })
                                ),
                                e(
                                    "label",
                                    { className: "react-checkbox" },
                                    e("input", {
                                        type: "checkbox",
                                        checked: !!fileForm.send_to_channel,
                                        onChange: function (event) {
                                            setFileForm(function (prev) {
                                                return Object.assign({}, prev, { send_to_channel: event.target.checked });
                                            });
                                        },
                                    }),
                                    e("span", null, "Сразу отправить в мессенджер")
                                ),
                                e("button", { type: "submit", className: "btn-primary" }, "Загрузить файл")
                            )
                        ),
                        e(OverviewList, {
                            title: "Файлы",
                            items: fileItems,
                            emptyText: "Файлов пока нет",
                        }),
                        e(OverviewList, {
                            title: "Оффер",
                            items: documentItems,
                            emptyText: "Ссылка на оффер пока не добавлена",
                        }),
                        e(OverviewList, {
                            title: "Запланированные сценарии",
                            items: launchItems,
                            emptyText: "Запланированных сценариев пока нет",
                        }),
                        e(
                            "section",
                            { className: "react-section react-section-danger" },
                            e("h4", null, "Редкие действия"),
                            e(
                                "p",
                                { className: "muted" },
                                "Используй только если карточку действительно нужно убрать из системы."
                            ),
                            e(
                                "button",
                                {
                                    type: "button",
                                    className: "btn-danger",
                                    onClick: handleDeleteEmployee,
                                },
                                "Удалить сотрудника"
                            )
                        )
                    )
                )
            )
        );
    }

    window.ReactDOM.createRoot(rootElement).render(e(EmployeeEditApp));
})();
