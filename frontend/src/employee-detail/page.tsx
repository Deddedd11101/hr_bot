import React from "react";

import { Badge } from "@/components/ui/badge";
import {
    buildEmployeeUpdatePayload,
    buildWorkHoursValue,
    parseWorkHours,
    updatePayloadState,
} from "./helpers";
import {
    EmployeeDetailError,
    EmployeeFlashNotice,
    EmployeeDetailHeader,
    EmployeeDetailLoading,
    EmployeeOperationsSection,
    EmployeeProfileSection,
} from "./sections";

export type EmployeeDetailPageProps = {
    apiUrl: string;
    saveUrl: string;
    listUrl: string;
    flashMessage: string;
    flashType: string;
};

export function EmployeeDetailPage(props: EmployeeDetailPageProps) {
    const { apiUrl, saveUrl, listUrl, flashMessage, flashType } = props;

    const [state, setState] = React.useState({
        loading: true,
        error: "",
        payload: null as any,
    });
    const [form, setForm] = React.useState<any>(null);
    const [saveState, setSaveState] = React.useState({
        saving: false,
        message: "",
        error: false,
    });
    const [opsState, setOpsState] = React.useState({
        message: "",
        error: false,
        working: false,
    });
    const [flashState, setFlashState] = React.useState({
        message: flashMessage || "",
        error: flashType === "error",
    });
    const [offerUrl, setOfferUrl] = React.useState("");
    const [scheduleForm, setScheduleForm] = React.useState({
        flow_key: "",
        requested_at: "",
    });
    const [launchFlowKey, setLaunchFlowKey] = React.useState("");
    const [fileForm, setFileForm] = React.useState({
        upload: null as File | null,
    });
    const [offerFile, setOfferFile] = React.useState<File | null>(null);

    React.useEffect(function () {
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
                const normalizedPayload = Object.assign({}, payload, {
                    options: Object.assign(
                        {
                            employee_role_values: [],
                            employee_stage_values: [],
                            candidate_work_stage_values: [],
                            staff_employee_values: [],
                            manager_employee_values: [],
                            mentor_employee_values: [],
                            scenarios: [],
                        },
                        payload.options || {},
                    ),
                });
                setState({
                    loading: false,
                    error: "",
                    payload: normalizedPayload,
                });
                setForm(normalizedPayload.employee);
                setOfferUrl("");
                setLaunchFlowKey(
                    normalizedPayload.options.scenarios.length ? normalizedPayload.options.scenarios[0].value : "",
                );
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
    }, [apiUrl]);

    function setOperationMessage(message: string, isError: boolean) {
        setFlashState({
            message: "",
            error: false,
        });
        setOpsState({
            message: message,
            error: !!isError,
            working: false,
        });
    }

    function handleChange(event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) {
        const target = event.target;
        const value = target instanceof HTMLInputElement && target.type === "checkbox" ? target.checked : target.value;
        setForm(function (prev: any) {
            return Object.assign({}, prev, {
                [target.name]: value,
            });
        });
    }

    function handleWorkHoursChange(part: "start" | "end", value: string) {
        setForm(function (prev: any) {
            return Object.assign({}, prev, {
                work_hours: buildWorkHoursValue(prev ? prev.work_hours : "", part, value),
            });
        });
    }

    function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
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
            body: JSON.stringify(buildEmployeeUpdatePayload(form)),
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

    function handleOfferSubmit(event: React.FormEvent<HTMLFormElement>) {
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
                setOfferUrl("");
                setOperationMessage("Ссылка на оффер сохранена", false);
            })
            .catch(function (error) {
                setOperationMessage(error.message || "Не удалось сохранить оффер", true);
            });
    }

    function handleOfferDelete(linkId: number) {
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
                setOfferFile(null);
                setOperationMessage("Оффер удален из карточки", false);
            })
            .catch(function (error) {
                setOperationMessage(error.message || "Не удалось удалить ссылку", true);
            });
    }

    function handleOfferFileSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!offerFile) {
            setOperationMessage("Выбери файл оффера", true);
            return;
        }
        setOpsState({ message: "", error: false, working: true });
        const formData = new FormData();
        formData.append("upload", offerFile);
        fetch(apiUrl + "/document-slots/offer/file", {
            method: "POST",
            credentials: "same-origin",
            body: formData,
        })
            .then(function (response) {
                if (!response.ok) {
                    return response.json().catch(function () { return {}; }).then(function (payload) {
                        throw new Error(payload.detail || "Не удалось загрузить оффер");
                    });
                }
                return response.json();
            })
            .then(function (payload) {
                updatePayloadState(setState, setForm, payload.payload);
                setOfferFile(null);
                const fileInput = document.getElementById("react-offer-file-input") as HTMLInputElement | null;
                if (fileInput) {
                    fileInput.value = "";
                }
                setOperationMessage("Оффер загружен", false);
            })
            .catch(function (error) {
                setOperationMessage(error.message || "Не удалось загрузить оффер", true);
            });
    }

    function handleScheduleSubmit(event: React.FormEvent<HTMLFormElement>) {
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

    function handleLaunchSubmit(event: React.FormEvent<HTMLFormElement>) {
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

    function handleScheduledDelete(launchRequestId: number) {
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

    function handleFileSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!fileForm.upload) {
            setOperationMessage("Выбери файл для загрузки", true);
            return;
        }
        setOpsState({ message: "", error: false, working: true });
        const body = new FormData();
        body.append("upload", fileForm.upload);
        body.append("category", "hr_file");
        body.append("send_to_channel", "false");
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
                setFileForm({ upload: null });
                const fileInput = document.getElementById("react-file-input") as HTMLInputElement | null;
                if (fileInput) {
                    fileInput.value = "";
                }
                setOperationMessage("Файл загружен", false);
            })
            .catch(function (error) {
                setOperationMessage(error.message || "Не удалось загрузить файл", true);
            });
    }

    function handleSendFile(fileId: number) {
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

    function handleDeleteFile(fileId: number) {
        setOpsState({ message: "", error: false, working: true });
        fetch(apiUrl + "/files/" + fileId, {
            method: "DELETE",
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        })
            .then(function (response) {
                if (!response.ok) {
                    return response.json().catch(function () { return {}; }).then(function (payload) {
                        throw new Error(payload.detail || "Не удалось удалить файл");
                    });
                }
                return response.json();
            })
            .then(function (payload) {
                updatePayloadState(setState, setForm, payload);
                setOperationMessage("Файл удален", false);
            })
            .catch(function (error) {
                setOperationMessage(error.message || "Не удалось удалить файл", true);
            });
    }

    function handleDeleteEmployee() {
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

    function handleResetBotLinkage() {
        if (!window.confirm("Сбросить привязку к боту и очистить активные сценарии и ожидающие отправки?")) {
            return;
        }
        setOpsState({ message: "", error: false, working: true });
        fetch(apiUrl + "/bot-link/reset", {
            method: "POST",
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        })
            .then(function (response) {
                if (!response.ok) {
                    return response.json().catch(function () { return {}; }).then(function (payload) {
                        throw new Error(payload.detail || "Не удалось сбросить привязку к боту");
                    });
                }
                return response.json();
            })
            .then(function (payload) {
                updatePayloadState(setState, setForm, payload);
                setLaunchFlowKey(
                    payload.options && payload.options.scenarios && payload.options.scenarios.length
                        ? payload.options.scenarios[0].value
                        : "",
                );
                setOperationMessage("Привязка к боту сброшена", false);
            })
            .catch(function (error) {
                setOperationMessage(error.message || "Не удалось сбросить привязку к боту", true);
            });
    }

    function handlePromoteToAdaptation() {
        setOpsState({ message: "", error: false, working: true });
        fetch(apiUrl + "/promote-to-adaptation", {
            method: "POST",
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        })
            .then(function (response) {
                if (!response.ok) {
                    return response.json().catch(function () { return {}; }).then(function (payload) {
                        throw new Error(payload.detail || "Не удалось перевести кандидата в адаптацию");
                    });
                }
                return response.json();
            })
            .then(function (payload) {
                updatePayloadState(setState, setForm, payload);
                setOperationMessage("Кандидат переведен в адаптацию", false);
            })
            .catch(function (error) {
                setOperationMessage(error.message || "Не удалось перевести кандидата в адаптацию", true);
            });
    }

    if (state.loading || !form) {
        return <EmployeeDetailLoading />;
    }

    if (state.error || !state.payload) {
        return <EmployeeDetailError message={state.error} listUrl={listUrl} />;
    }

    const payload = state.payload;
    const meta = payload.meta;
    const isCandidate = !!meta.is_candidate;
    const workHoursParts = parseWorkHours(form.work_hours);

    const fileItems = payload.files.map(function (file: any) {
        return {
            id: file.id,
            title: file.original_filename || "Файл",
            subtitle: (file.direction === "inbound" ? "От сотрудника" : "От HR") + " · " + file.created_at_label,
            direction: file.direction,
            link: file.download_url,
            linkLabel: "Скачать",
            extraAction: file.can_send_to_channel ? function () { handleSendFile(file.id); } : null,
            extraActionLabel: file.can_send_to_channel ? "Отправить в мессенджер" : null,
            deleteAction: function () { handleDeleteFile(file.id); },
            deleteActionLabel: "Удалить файл",
            deleteConfirmTitle: "Удалить файл?",
            deleteConfirmDescription: "Файл будет удален из карточки сотрудника.",
            deleteConfirmLabel: "Удалить",
        };
    });
    const employeeFileItems = fileItems.filter(function (file: any) {
        return file.direction === "inbound";
    });
    const hrFileItems = fileItems.filter(function (file: any) {
        return file.direction !== "inbound";
    });

    const offerDocumentItem = payload.offer_document
        ? {
            id: payload.offer_document.id,
            title: payload.offer_document.title,
            subtitle: payload.offer_document.item_kind === "file"
                ? "Файл оффера"
                : payload.offer_document.scenario_tag,
            link: payload.offer_document.url,
            linkLabel: payload.offer_document.item_kind === "file" ? "Скачать" : "Открыть",
            deleteAction: function () { handleOfferDelete(payload.offer_document.id); },
            deleteActionLabel: "Удалить",
            deleteConfirmTitle: "Удалить оффер?",
            deleteConfirmDescription: "Оффер будет удален из карточки сотрудника.",
            deleteConfirmLabel: "Удалить",
        }
        : null;

    const launchItems = payload.scheduled_launches.map(function (item: any) {
        return {
            id: "scheduled-" + item.id,
            title: item.scenario_title,
            subtitle: "Отправка: " + item.requested_at_label,
            link: item.scenario_url,
            linkLabel: "Сценарий",
            extraAction: function () { handleScheduledDelete(item.id); },
            extraActionLabel: "Удалить",
            extraActionConfirmTitle: "Удалить запланированную отправку?",
            extraActionConfirmDescription: "Сценарий будет удален из расписания этого сотрудника.",
            extraActionConfirmLabel: "Удалить",
        };
    });
    const manualLaunchItems = payload.manual_launch_history.map(function (item: any) {
        return {
            id: "manual-" + item.id,
            title: item.scenario_title,
            subtitle: item.processed_at_label && item.processed_at_label !== "—"
                ? "Запущен: " + item.processed_at_label
                : "Запрошен: " + item.requested_at_label,
            link: item.scenario_url,
            linkLabel: "Сценарий",
        };
    });

    return (
        <div className="react-detail-page">
            <EmployeeDetailHeader meta={meta} />
            <EmployeeFlashNotice message={flashState.message} error={flashState.error} />
            <section className="employee-detail-hero">
                <div>
                    <h1>{form.full_name || "Сотрудник #" + form.id}</h1>
                    <div className="employee-detail-badges">
                        <Badge variant="secondary">{meta.status_label || "Без статуса"}</Badge>
                        {isCandidate ? (
                            <Badge variant="outline">
                                {meta.candidate_work_stage_label || "Без этапа"}
                            </Badge>
                        ) : (
                            <Badge variant="outline">{"Стаж: " + meta.tenure_years + " лет"}</Badge>
                        )}
                    </div>
                </div>
            </section>
            <section className="employee-detail-grid">
                <EmployeeProfileSection
                    form={form}
                    isCandidate={isCandidate}
                    meta={meta}
                    options={payload.options}
                    workHoursParts={workHoursParts}
                    handleChange={handleChange}
                    handleWorkHoursChange={handleWorkHoursChange}
                    handleSubmit={handleSubmit}
                    saveState={saveState}
                />
                <EmployeeOperationsSection
                    opsState={opsState}
                    offerUrl={offerUrl}
                    setOfferUrl={setOfferUrl}
                    offerFile={offerFile}
                    setOfferFile={setOfferFile}
                    offerDocumentItem={offerDocumentItem}
                    payload={payload}
                    form={form}
                    scheduleForm={scheduleForm}
                    setScheduleForm={setScheduleForm}
                    launchFlowKey={launchFlowKey}
                    setLaunchFlowKey={setLaunchFlowKey}
                    fileForm={fileForm}
                    setFileForm={setFileForm}
                    handleOfferSubmit={handleOfferSubmit}
                    handleOfferFileSubmit={handleOfferFileSubmit}
                    handleOfferDelete={handleOfferDelete}
                    handleScheduleSubmit={handleScheduleSubmit}
                    handleLaunchSubmit={handleLaunchSubmit}
                    handleFileSubmit={handleFileSubmit}
                    handlePromoteToAdaptation={handlePromoteToAdaptation}
                    handleResetBotLinkage={handleResetBotLinkage}
                    handleDeleteEmployee={handleDeleteEmployee}
                    employeeFileItems={employeeFileItems}
                    hrFileItems={hrFileItems}
                    launchItems={launchItems}
                    manualLaunchItems={manualLaunchItems}
                    isCandidate={isCandidate}
                />
            </section>
        </div>
    );
}
