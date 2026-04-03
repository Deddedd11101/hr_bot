(function () {
    const rootElement = document.getElementById("react-scenario-builder-root");
    if (!rootElement || !window.React || !window.ReactDOM) {
        return;
    }

    const e = window.React.createElement;
    const apiUrl = rootElement.dataset.apiUrl;
    const classicUrl = rootElement.dataset.classicUrl;
    const listUrl = rootElement.dataset.listUrl;

    function NodeCard(props) {
        const node = props.node;
        const className = props.selected
            ? "scenario-flow-node is-selected"
            : "scenario-flow-node";

        return e(
            "button",
            {
                type: "button",
                className: className,
                onClick: function () { props.onSelect(node.id); },
            },
            e(
                "div",
                { className: "scenario-flow-node-head" },
                e(
                    "div",
                    null,
                    e("h4", null, node.title || "Без названия"),
                    e("p", { className: "scenario-flow-node-key" }, node.step_key || "Шаг")
                ),
                e("span", { className: "scenario-flow-badge" }, node.kind)
            ),
            e(
                "div",
                { className: "scenario-flow-copy" },
                e("p", { className: "scenario-flow-muted" }, node.response_label || "Без ответа"),
                e("p", null, (node.text || "Сообщение не заполнено").slice(0, 120))
            ),
            e(
                "div",
                { className: "scenario-flow-actions" },
                node.has_attachment ? e("span", { className: "scenario-flow-mini-pill" }, "Вложение") : null,
                node.send_employee_card ? e("span", { className: "scenario-flow-mini-pill" }, "Карточка") : null,
                node.button_options.length ? e("span", { className: "scenario-flow-mini-pill" }, "Кнопок: " + node.button_options.length) : null
            )
        );
    }

    function ScenarioBuilderApp() {
        const [state, setState] = window.React.useState({
            loading: true,
            error: "",
            payload: null,
            selectedNodeId: null,
        });

        window.React.useEffect(function () {
            let isMounted = true;
            fetch(apiUrl, {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("Не удалось загрузить visual-редактор сценария");
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
                        selectedNodeId: payload.nodes.length ? payload.nodes[0].id : null,
                    });
                })
                .catch(function (error) {
                    if (!isMounted) {
                        return;
                    }
                    setState({
                        loading: false,
                        error: error.message || "Не удалось загрузить visual-редактор сценария",
                        payload: null,
                        selectedNodeId: null,
                    });
                });

            return function () {
                isMounted = false;
            };
        }, []);

        function selectNode(nodeId) {
            setState(function (prev) {
                return Object.assign({}, prev, { selectedNodeId: nodeId });
            });
        }

        if (state.loading) {
            return e("div", { className: "scenario-builder-empty scenario-builder-card" }, "Собираю visual-редактор...");
        }

        if (state.error || !state.payload) {
            return e(
                "div",
                { className: "scenario-builder-empty scenario-builder-card" },
                e("p", null, state.error || "Не удалось загрузить visual-редактор."),
                e("a", { href: classicUrl, className: "btn-secondary" }, "Открыть классическую версию")
            );
        }

        const payload = state.payload;
        const nodesById = {};
        payload.nodes.forEach(function (node) {
            nodesById[node.id] = node;
        });

        const topLevelNodes = payload.nodes.filter(function (node) {
            return node.kind === "step";
        });

        const selectedNode = nodesById[state.selectedNodeId] || topLevelNodes[0] || null;

        function childChains(parentId) {
            return payload.nodes.filter(function (node) {
                return node.parent_id === parentId && node.kind === "chain";
            });
        }

        function childBranches(parentId) {
            return payload.nodes
                .filter(function (node) {
                    return node.parent_id === parentId && node.kind === "branch";
                })
                .sort(function (a, b) {
                    return (a.branch_option_index || 0) - (b.branch_option_index || 0);
                });
        }

        function renderSubtree(parentNode) {
            const chains = childChains(parentNode.id);
            const branches = childBranches(parentNode.id);
            if (!chains.length && !branches.length) {
                return null;
            }
            return e(
                "div",
                { className: "scenario-flow-subtree" },
                chains.length
                    ? e(
                        "div",
                        { className: "scenario-flow-column" },
                        e("div", { className: "scenario-flow-label" }, "Цепочка"),
                        chains.map(function (node) {
                            return e(
                                window.React.Fragment,
                                { key: "chain-" + node.id },
                                e(NodeCard, {
                                    node: node,
                                    selected: selectedNode && selectedNode.id === node.id,
                                    onSelect: selectNode,
                                }),
                                renderSubtree(node)
                            );
                        })
                    )
                    : null,
                branches.length
                    ? e(
                        "div",
                        { className: "scenario-flow-branches" },
                        e("div", { className: "scenario-flow-label" }, "Ветки"),
                        branches.map(function (node) {
                            const buttonLabel = parentNode.button_options[node.branch_option_index || 0] || ("Ветка " + ((node.branch_option_index || 0) + 1));
                            return e(
                                "div",
                                { key: "branch-" + node.id, className: "scenario-flow-branch" },
                                e("div", { className: "scenario-flow-label" }, buttonLabel),
                                e(NodeCard, {
                                    node: node,
                                    selected: selectedNode && selectedNode.id === node.id,
                                    onSelect: selectNode,
                                }),
                                renderSubtree(node)
                            );
                        })
                    )
                    : null
            );
        }

        return e(
            "div",
            { className: "scenario-builder-page" },
            e(
                "div",
                { className: "scenario-builder-head" },
                e("a", { href: payload.meta.list_url, className: "scenario-builder-back" }, "← " + payload.meta.list_title),
                e("a", { href: classicUrl, className: "btn-secondary" }, "Классический редактор")
            ),
            e(
                "section",
                { className: "scenario-builder-card" },
                e(
                    "div",
                    { className: "scenario-builder-summary" },
                    e("p", { className: "react-page-eyebrow" }, "Visual Scenario Builder"),
                    e("h2", null, payload.scenario.title),
                    e(
                        "p",
                        { className: "muted" },
                        payload.scenario.description || "Новая visual-версия редактора сценария: основной поток, ветки и цепочки видны как единая схема."
                    ),
                    e(
                        "div",
                        { className: "scenario-builder-pills" },
                        e("span", { className: "scenario-builder-pill" }, payload.scenario.role_scope_label),
                        e("span", { className: "scenario-builder-pill" }, payload.scenario.trigger_mode_label),
                        e("span", { className: "scenario-builder-pill" }, "Нод: " + payload.meta.nodes_count)
                    )
                ),
                e(
                    "div",
                    { className: "scenario-builder-canvas" },
                    e(
                        "div",
                        { className: "scenario-builder-shell" },
                        e(
                            "div",
                            { className: "scenario-builder-card scenario-flow-board" },
                            e(
                                "div",
                                { className: "scenario-builder-summary" },
                                e("h3", null, "Поток сценария"),
                                e("p", { className: "muted" }, "Главные шаги идут слева направо. Ветки и цепочки раскрываются под родительской нодой.")
                            ),
                            e(
                                "div",
                                { className: "scenario-builder-canvas" },
                                e(
                                    "div",
                                    { className: "scenario-flow-track" },
                                    topLevelNodes.map(function (node) {
                                        return e(
                                            "div",
                                            { key: node.id, className: "scenario-flow-column" },
                                            e(NodeCard, {
                                                node: node,
                                                selected: selectedNode && selectedNode.id === node.id,
                                                onSelect: selectNode,
                                            }),
                                            renderSubtree(node)
                                        );
                                    })
                                )
                            )
                        ),
                        e(
                            "div",
                            { className: "scenario-inspector" },
                            e(
                                "section",
                                { className: "scenario-builder-card scenario-inspector-card" },
                                selectedNode
                                    ? e(
                                        window.React.Fragment,
                                        null,
                                        e("p", { className: "react-page-eyebrow" }, "Inspector"),
                                        e("h3", null, selectedNode.title || "Без названия"),
                                        e(
                                            "div",
                                            { className: "scenario-builder-pills" },
                                            e("span", { className: "scenario-builder-pill" }, selectedNode.kind),
                                            e("span", { className: "scenario-builder-pill" }, selectedNode.response_label)
                                        ),
                                        e(
                                            "div",
                                            { className: "scenario-inspector-grid" },
                                            e(
                                                "div",
                                                { className: "scenario-inspector-row" },
                                                e("strong", null, "Ключ шага"),
                                                e("span", { className: "muted" }, selectedNode.step_key || "—")
                                            ),
                                            e(
                                                "div",
                                                { className: "scenario-inspector-row" },
                                                e("strong", null, "Текст"),
                                                e("span", { className: "muted" }, selectedNode.text || "Сообщение не заполнено")
                                            ),
                                            e(
                                                "div",
                                                { className: "scenario-inspector-row" },
                                                e("strong", null, "Отправка"),
                                                e("span", { className: "muted" }, selectedNode.send_mode === "specific_time"
                                                    ? "По времени " + (selectedNode.send_time || "")
                                                    : "Сразу")
                                            ),
                                            e(
                                                "div",
                                                { className: "scenario-inspector-row" },
                                                e("strong", null, "Смещение по рабочим дням"),
                                                e("span", { className: "muted" }, String(selectedNode.day_offset_workdays || 0))
                                            ),
                                            selectedNode.button_options.length
                                                ? e(
                                                    "div",
                                                    { className: "scenario-inspector-row" },
                                                    e("strong", null, "Кнопки"),
                                                    e(
                                                        "ul",
                                                        { className: "scenario-inspector-list" },
                                                        selectedNode.button_options.map(function (item, index) {
                                                            return e("li", { key: index }, item);
                                                        })
                                                    )
                                                )
                                                : null,
                                            selectedNode.launch_scenario_key
                                                ? e(
                                                    "div",
                                                    { className: "scenario-inspector-row" },
                                                    e("strong", null, "Переход к сценарию"),
                                                    e("span", { className: "muted" }, selectedNode.launch_scenario_key)
                                                )
                                                : null
                                        )
                                    )
                                    : e("p", { className: "muted" }, "Выбери ноду на схеме, чтобы посмотреть детали.")
                            ),
                            e(
                                "section",
                                { className: "scenario-builder-card scenario-inspector-card" },
                                e("h4", null, "Что дальше"),
                                e(
                                    "ul",
                                    { className: "scenario-inspector-list" },
                                    e("li", null, "Подключить редактирование ноды прямо из inspector."),
                                    e("li", null, "Добавить создание новых шагов и веток с canvas-кнопок."),
                                    e("li", null, "Перенести сохранение в JSON-формат без громоздких form-arrays.")
                                )
                            )
                        )
                    )
                )
            )
        );
    }

    window.ReactDOM.createRoot(rootElement).render(e(ScenarioBuilderApp));
})();
