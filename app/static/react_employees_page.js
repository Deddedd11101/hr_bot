(function () {
    const rootElement = document.getElementById("react-employees-root");
    if (!rootElement || !window.React || !window.ReactDOM) {
        return;
    }

    const e = window.React.createElement;
    const apiUrl = rootElement.dataset.apiUrl;
    const createUrl = rootElement.dataset.createUrl;
    const classicUrl = rootElement.dataset.classicUrl;
    const defaultListKind = rootElement.dataset.defaultListKind || "employees";

    function listMeta(kind) {
        if (kind === "candidates") {
            return {
                list_title: "Кандидаты",
                create_button_label: "Добавить кандидата",
                create_modal_title: "Новый кандидат",
                create_intro: "Добавьте кандидата, чтобы начать работу с подбором и наймом.",
                empty_message: "Кандидатов пока нет. Нажмите «Добавить кандидата».",
                first_workday_label: "Предварительная дата выхода на работу",
                default_employee_stage: "candidate",
                classic_page_url: "/candidates",
            };
        }
        return {
            list_title: "Сотрудники",
            create_button_label: "Добавить сотрудника",
            create_modal_title: "Новый сотрудник",
            create_intro: "Добавьте сотрудника, чтобы запустить сценарий онбординга.",
            empty_message: "Сотрудников пока нет. Нажмите «Добавить сотрудника».",
            first_workday_label: "Дата выхода на работу",
            default_employee_stage: "staff",
            classic_page_url: "/employees",
        };
    }

    function CreateEmployeeModal(props) {
        if (!props.isOpen) {
            return null;
        }

        const meta = listMeta(props.listKind);

        function onOverlayClick(event) {
            if (event.target === event.currentTarget) {
                props.onClose();
            }
        }

        return e(
            "div",
            { className: "react-modal-overlay", onClick: onOverlayClick },
            e(
                "div",
                { className: "react-modal-card" },
                e(
                    "div",
                    { className: "react-modal-header" },
                    e(
                        "div",
                        null,
                        e("h3", null, meta.create_modal_title),
                        e("p", { className: "muted" }, meta.create_intro)
                    ),
                    e(
                        "button",
                        {
                            type: "button",
                            className: "react-modal-close",
                            onClick: props.onClose,
                            "aria-label": "Закрыть",
                        },
                        "×"
                    )
                ),
                e(
                    "form",
                    {
                        className: "react-form-grid",
                        onSubmit: props.onSubmit,
                    },
                    e(
                        "label",
                        { className: "react-field" },
                        e("span", null, "ФИО"),
                        e("input", {
                            type: "text",
                            name: "full_name",
                            value: props.form.full_name,
                            onChange: props.onChange,
                            placeholder: "Можно заполнить позже",
                        })
                    ),
                    e(
                        "label",
                        { className: "react-field" },
                        e("span", null, "ID пользователя в канале или @username"),
                        e("input", {
                            type: "text",
                            name: "chat_id",
                            value: props.form.chat_id,
                            onChange: props.onChange,
                            placeholder: "Можно заполнить позже",
                        })
                    ),
                    e(
                        "label",
                        { className: "react-field" },
                        e("span", null, meta.first_workday_label),
                        e("input", {
                            type: "date",
                            name: "first_workday",
                            value: props.form.first_workday,
                            onChange: props.onChange,
                        })
                    ),
                    props.listKind === "employees"
                        ? e(
                            "label",
                            { className: "react-field" },
                            e("span", null, "Статус сотрудника"),
                            e(
                                "select",
                                {
                                    name: "employee_stage",
                                    value: props.form.employee_stage,
                                    onChange: props.onChange,
                                },
                                e("option", { value: "staff" }, "В штате"),
                                e("option", { value: "adaptation" }, "Адаптация"),
                                e("option", { value: "ipr" }, "ИПР")
                            )
                        )
                        : null,
                    props.error
                        ? e("div", { className: "react-form-error" }, props.error)
                        : null,
                    e(
                        "div",
                        { className: "react-form-actions" },
                        e(
                            "button",
                            {
                                type: "button",
                                className: "btn-secondary",
                                onClick: props.onClose,
                            },
                            "Отмена"
                        ),
                        e(
                            "button",
                            {
                                type: "submit",
                                className: "btn-primary",
                                disabled: props.submitting,
                            },
                            props.submitting ? "Сохраняю..." : meta.create_button_label
                        )
                    )
                )
            )
        );
    }

    function MetaBlock(props) {
        return e(
            "div",
            { className: "react-employee-meta" },
            e("div", { className: "react-employee-label" }, props.label),
            e("div", { className: "react-employee-value" }, props.value || "—")
        );
    }

    function EmployeeRow(props) {
        const item = props.item;
        const channelValue = item.chat_id || item.chat_handle || "—";
        const isCandidate = item.list_kind === "candidates";
        const statePill = isCandidate ? (item.candidate_work_stage_label || "Без этапа") : (item.status_label || "Без статуса");
        const channelNode = item.chat_link
            ? e(
                "a",
                {
                    href: item.chat_link,
                    target: "_blank",
                    rel: "noreferrer noopener",
                    className: "react-employee-value",
                },
                channelValue
            )
            : e("div", { className: "react-employee-value" }, channelValue);

        return e(
            "article",
            { className: "react-employee-row" },
            e(
                "div",
                { className: "react-employee-main" },
                e(
                    "div",
                    { className: "react-employee-head" },
                    e("h3", { className: "react-employee-name" }, item.full_name || "Без имени"),
                    e("span", { className: "react-employee-pill" }, statePill)
                ),
                e(
                    "div",
                    { className: "react-employee-subline" },
                    e("span", null, "ID " + item.id),
                    !isCandidate && item.first_workday_label && item.first_workday_label !== "—"
                        ? e("span", null, "Выход: " + item.first_workday_label)
                        : null,
                    isCandidate && item.test_task_due_at_label && item.test_task_due_at_label !== "—"
                        ? e("span", null, "Тестовое до: " + item.test_task_due_at_label)
                        : null
                )
            ),
            e(
                "div",
                { className: "react-employee-facts" },
                e(
                    "div",
                    { className: "react-employee-meta" },
                    e("div", { className: "react-employee-label" }, "Канал связи"),
                    channelNode
                ),
                e(MetaBlock, {
                    label: "Должность",
                    value: item.position || "—",
                }),
                e(MetaBlock, {
                    label: isCandidate ? "Этап кандидата" : "Статус",
                    value: isCandidate ? (item.candidate_work_stage_label || "—") : (item.status_label || "—"),
                }),
                e(MetaBlock, {
                    label: "Сценарий",
                    value: item.planned_scenario_title || "—",
                })
            ),
            e(
                "div",
                { className: "react-employee-actions" },
                item.chat_link
                    ? e(
                        "a",
                        {
                            href: item.chat_link,
                            target: "_blank",
                            rel: "noreferrer noopener",
                            className: "react-link-button is-ghost",
                        },
                        "Чат"
                    )
                    : null,
                e(
                    "a",
                    {
                        href: item.edit_url,
                        className: "react-link-button",
                    },
                    "Открыть"
                )
            )
        );
    }

    function EmployeesApp() {
        const [state, setState] = window.React.useState({
            loading: true,
            error: "",
            meta: null,
            items: [],
        });
        const [listKind, setListKind] = window.React.useState(defaultListKind);
        const [search, setSearch] = window.React.useState("");
        const [statusFilter, setStatusFilter] = window.React.useState("all");
        const [sortMode, setSortMode] = window.React.useState("id_desc");
        const [isModalOpen, setIsModalOpen] = window.React.useState(false);
        const [submitError, setSubmitError] = window.React.useState("");
        const [isSubmitting, setIsSubmitting] = window.React.useState(false);
        const [form, setForm] = window.React.useState({
            full_name: "",
            chat_id: "",
            first_workday: "",
            employee_stage: "staff",
        });

        window.React.useEffect(function () {
            let isMounted = true;
            const url = "/api/employees?list_kind=" + encodeURIComponent(listKind);

            setState(function (prev) {
                return {
                    loading: true,
                    error: "",
                    meta: prev.meta,
                    items: prev.items,
                };
            });

            fetch(url, {
                credentials: "same-origin",
                headers: {
                    Accept: "application/json",
                },
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("Не удалось загрузить сотрудников");
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
                        meta: payload.meta || null,
                        items: payload.items || [],
                    });
                })
                .catch(function (error) {
                    if (!isMounted) {
                        return;
                    }
                    setState({
                        loading: false,
                        error: error.message || "Не удалось загрузить сотрудников",
                        meta: null,
                        items: [],
                    });
                });

            return function () {
                isMounted = false;
            };
        }, [listKind]);

        window.React.useEffect(function () {
            setStatusFilter("all");
            setSearch("");
        }, [listKind]);

        const statusOptions = window.React.useMemo(function () {
            const source = listKind === "candidates"
                ? ["Тестирование", "Оффер", "Отказ кандидата", "Наш отказ", "Преонбординг", "Заключение договора"]
                : ["Адаптация", "ИПР", "В штате", "Кандидат"];
            return ["all"].concat(source);
        }, [listKind]);

        let filteredItems = state.items.filter(function (item) {
            const needle = search.trim().toLowerCase();
            if (!needle) {
                return statusFilter === "all"
                    || (listKind === "candidates"
                        ? (item.candidate_work_stage_label || "—") === statusFilter
                        : (item.status_label || "—") === statusFilter);
            }
            const matchesSearch = [
                item.full_name,
                item.chat_id,
                item.chat_handle,
                item.position,
                item.status_label,
                item.candidate_work_stage_label,
                item.planned_scenario_title,
            ]
                .filter(Boolean)
                .join(" ")
                .toLowerCase()
                .includes(needle);
            const currentStatus = listKind === "candidates" ? (item.candidate_work_stage_label || "—") : (item.status_label || "—");
            const matchesStatus = statusFilter === "all" || currentStatus === statusFilter;
            return matchesSearch && matchesStatus;
        });

        filteredItems = filteredItems.slice().sort(function (left, right) {
            if (sortMode === "name_asc") {
                return (left.full_name || "").localeCompare((right.full_name || ""), "ru");
            }
            if (sortMode === "name_desc") {
                return (right.full_name || "").localeCompare((left.full_name || ""), "ru");
            }
            if (sortMode === "workday_asc") {
                return (left.first_workday || "9999-12-31").localeCompare(right.first_workday || "9999-12-31");
            }
            if (sortMode === "workday_desc") {
                return (right.first_workday || "").localeCompare(left.first_workday || "");
            }
            return (right.id || 0) - (left.id || 0);
        });

        function openCreateModal() {
            const meta = listMeta(listKind);
            setForm({
                full_name: "",
                chat_id: "",
                first_workday: "",
                employee_stage: meta.default_employee_stage,
            });
            setSubmitError("");
            setIsModalOpen(true);
        }

        function closeCreateModal() {
            setIsModalOpen(false);
            setSubmitError("");
            setIsSubmitting(false);
        }

        function handleFormChange(event) {
            const target = event.target;
            setForm(function (prev) {
                return Object.assign({}, prev, {
                    [target.name]: target.value,
                });
            });
        }

        function handleCreateSubmit(event) {
            event.preventDefault();
            setIsSubmitting(true);
            setSubmitError("");

            fetch(createUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "application/json",
                },
                body: JSON.stringify({
                    list_kind: listKind,
                    full_name: form.full_name,
                    chat_id: form.chat_id,
                    first_workday: form.first_workday,
                    employee_stage: form.employee_stage,
                }),
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("Не удалось создать запись");
                    }
                    return response.json();
                })
                .then(function (payload) {
                    const createdItem = payload.item;
                    setState(function (prev) {
                        return {
                            loading: false,
                            error: "",
                            meta: payload.meta || prev.meta,
                            items: createdItem ? [createdItem].concat(prev.items) : prev.items,
                        };
                    });
                    closeCreateModal();
                })
                .catch(function (error) {
                    setIsSubmitting(false);
                    setSubmitError(error.message || "Не удалось создать запись");
                });
        }

        if (state.loading) {
            return e("div", { className: "react-loading-state react-employees-card" }, "Загружаю список сотрудников...");
        }

        if (state.error) {
            return e(
                "div",
                { className: "react-error-state react-employees-card" },
                e("p", null, state.error),
                e(
                    "p",
                    null,
                    e("a", { href: classicUrl, className: "react-link-button" }, "Вернуться к классической странице")
                )
            );
        }

        return e(
            "div",
            { className: "react-employees-shell" },
            e(
                "section",
                { className: "react-employees-card" },
                e(
                    "div",
                    { className: "react-employees-toolbar" },
                        e(
                            "div",
                            null,
                            e("h3", null, (state.meta && state.meta.list_title) || listMeta(listKind).list_title),
                            e(
                                "p",
                                { className: "muted" },
                                "Параллельный React-экран поверх текущего backend API"
                            )
                        ),
                    e("div", { className: "react-employees-badge" }, String(filteredItems.length))
                ),
                e(
                    "div",
                    { className: "react-employees-controls" },
                    e(
                        "div",
                        { className: "react-segmented" },
                        e(
                            "button",
                            {
                                type: "button",
                                className: listKind === "employees" ? "is-active" : "",
                                onClick: function () { setListKind("employees"); },
                            },
                            "Сотрудники"
                        ),
                        e(
                            "button",
                            {
                                type: "button",
                                className: listKind === "candidates" ? "is-active" : "",
                                onClick: function () { setListKind("candidates"); },
                            },
                            "Кандидаты"
                        )
                    ),
                    e(
                        "label",
                        { className: "react-search" },
                        e("input", {
                            type: "search",
                            value: search,
                            onChange: function (event) { setSearch(event.target.value); },
                            placeholder: "Поиск по имени, каналу, должности, сценарию",
                        })
                    ),
                    e(
                        "select",
                        {
                            className: "react-filter-select",
                            value: statusFilter,
                            onChange: function (event) { setStatusFilter(event.target.value); },
                        },
                        statusOptions.map(function (option) {
                            return e(
                                "option",
                                { key: option, value: option },
                                option === "all" ? "Все статусы" : option
                            );
                        })
                    ),
                    e(
                        "select",
                        {
                            className: "react-filter-select",
                            value: sortMode,
                            onChange: function (event) { setSortMode(event.target.value); },
                        },
                        e("option", { value: "id_desc" }, "Сначала новые"),
                        e("option", { value: "name_asc" }, "Имя: А-Я"),
                        e("option", { value: "name_desc" }, "Имя: Я-А"),
                        e("option", { value: "workday_asc" }, "Ближайшая дата выхода"),
                        e("option", { value: "workday_desc" }, "Поздняя дата выхода")
                    ),
                    e(
                        "div",
                        { className: "react-toolbar-actions" },
                        e(
                            "button",
                            {
                                type: "button",
                                className: "btn-primary",
                                onClick: openCreateModal,
                            },
                            listMeta(listKind).create_button_label
                        ),
                        e(
                            "a",
                            {
                                href: (state.meta && state.meta.classic_page_url) || listMeta(listKind).classic_page_url || classicUrl,
                                className: "btn-secondary",
                            },
                            "Открыть классическую страницу"
                        )
                    )
                ),
                filteredItems.length
                    ? e(
                        "div",
                        { className: "react-employees-grid" },
                        filteredItems.map(function (item) {
                            return e(EmployeeRow, { key: item.id, item: item });
                        })
                    )
                    : e(
                        "div",
                        { className: "react-empty-state" },
                        search.trim()
                            ? "По запросу ничего не найдено"
                            : ((state.meta && state.meta.empty_message) || listMeta(listKind).empty_message)
                    ),
                e(CreateEmployeeModal, {
                    isOpen: isModalOpen,
                    listKind: listKind,
                    form: form,
                    error: submitError,
                    submitting: isSubmitting,
                    onChange: handleFormChange,
                    onSubmit: handleCreateSubmit,
                    onClose: closeCreateModal,
                })
            )
        );
    }

    window.ReactDOM.createRoot(rootElement).render(e(EmployeesApp));
})();
