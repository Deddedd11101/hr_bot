import React from "react";

import {
    buildEmployeeUpdatePayload,
    buildWorkHoursValue,
    parseWorkHours,
    updatePayloadState,
} from "./helpers";
import {
    EmployeeDetailError,
    EmployeeDetailHeader,
    EmployeeDetailLoading,
    EmployeeOperationsSection,
    EmployeeProfileSection,
} from "./sections";

export type EmployeeDetailPageProps = {
    apiUrl: string;
    saveUrl: string;
    classicUrl: string;
    listUrl: string;
};

export function EmployeeDetailPage(props: EmployeeDetailPageProps) {
    const { apiUrl, saveUrl, classicUrl, listUrl } = props;

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
    const [offerUrl, setOfferUrl] = React.useState("");
    const [scheduleForm, setScheduleForm] = React.useState({
        flow_key: "",
        requested_at: "",
    });
    const [launchFlowKey, setLaunchFlowKey] = React.useState("");
    const [fileForm, setFileForm] = React.useState({
        upload: null as File | null,
        send_to_channel: false,
    });

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
    }, [apiUrl]);

    function setOperationMessage(message: string, isError: boolean) {
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
                setOfferUrl(payload.item ? payload.item.url : offerUrl);
                setOperationMessage("Ссылка на оффер сохранена", false);
            })
            .catch(function (error) {
                setOperationMessage(error.message || "Не удалось сохранить оффер", true);
            });
    }

    function handleOfferDelete(linkId: number) {
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
            subtitle: file.direction + " · " + file.created_at_label,
            link: file.download_url,
            linkLabel: "Скачать",
            extraAction: file.can_send_to_channel ? function () { handleSendFile(file.id); } : null,
            extraActionLabel: file.can_send_to_channel ? "Отправить в мессенджер" : null,
        };
    });

    const documentItems = payload.document_links.map(function (item: any) {
        return {
            id: item.id,
            title: item.title,
            subtitle: item.scenario_tag,
            link: item.url,
            linkLabel: "Открыть",
        };
    });

    const launchItems = payload.scheduled_launches.map(function (item: any) {
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

    return (
        <div className="react-detail-page">
            <EmployeeDetailHeader meta={meta} classicUrl={classicUrl} />
            <section className="react-detail-card">
                <div className="react-detail-card-head">
                    <div>
                        <h2>{form.full_name || "Сотрудник #" + form.id}</h2>
                        <div className="react-overview-row">
                            <span className="react-overview-pill">{meta.status_label || "Без статуса"}</span>
                            {isCandidate ? (
                                <span className="react-overview-pill">
                                    {meta.candidate_work_stage_label || "Без этапа"}
                                </span>
                            ) : (
                                <span className="react-overview-pill">{"Стаж: " + meta.tenure_years + " лет"}</span>
                            )}
                        </div>
                    </div>
                </div>
                <div className="react-detail-grid">
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
                        payload={payload}
                        scheduleForm={scheduleForm}
                        setScheduleForm={setScheduleForm}
                        launchFlowKey={launchFlowKey}
                        setLaunchFlowKey={setLaunchFlowKey}
                        fileForm={fileForm}
                        setFileForm={setFileForm}
                        handleOfferSubmit={handleOfferSubmit}
                        handleOfferDelete={handleOfferDelete}
                        handleScheduleSubmit={handleScheduleSubmit}
                        handleLaunchSubmit={handleLaunchSubmit}
                        handleFileSubmit={handleFileSubmit}
                        handleDeleteEmployee={handleDeleteEmployee}
                        fileItems={fileItems}
                        documentItems={documentItems}
                        launchItems={launchItems}
                    />
                </div>
            </section>
        </div>
    );
}
