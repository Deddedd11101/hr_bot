import React from "react";

import { Badge } from "@/components/ui/badge";
import {
    buildEmployeeUpdatePayload,
    buildWorkHoursValue,
    parseWorkHours,
    updatePayloadState,
} from "./helpers";
import { PageDetailHeader } from "@/components/ui/page-header";
import {
    AssignmentHistorySection,
    EmployeeDetailError,
    EmployeeFlashNotice,
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
    const [resumeFile, setResumeFile] = React.useState<File | null>(null);
    const [manualBotMessageText, setManualBotMessageText] = React.useState("");
    const [hrNoteDraft, setHrNoteDraft] = React.useState("");
    const [manualBotMessageState, setManualBotMessageState] = React.useState({
        sending: false,
        message: "",
        error: false,
    });

    function applyEmployeePayload(payload: any) {
        const normalizedPayload = Object.assign({}, payload, {
            assignment_history: Array.isArray(payload.assignment_history) ? payload.assignment_history : [],
            manual_bot_message_history: Array.isArray(payload.manual_bot_message_history)
                ? payload.manual_bot_message_history
                : [],
            hr_notes_history: Array.isArray(payload.hr_notes_history) ? payload.hr_notes_history : [],
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
        return normalizedPayload;
    }

    function refetchEmployeeDetail() {
        return fetch(apiUrl, {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Не удалось обновить карточку сотрудника");
                }
                return response.json();
            })
            .then(function (payload) {
                return applyEmployeePayload(payload);
            });
    }

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
                const normalizedPayload = applyEmployeePayload(payload);
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

    function saveEmployeeForm(
        nextForm: any,
        successMessage: string,
        options: { noteDraft?: string; onSuccess?: () => void } = {},
    ) {
        const noteDraft = String(options.noteDraft || "").trim();
        const payloadForm = noteDraft ? Object.assign({}, nextForm, { notes: noteDraft }) : nextForm;

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
            body: JSON.stringify(buildEmployeeUpdatePayload(payloadForm)),
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
                if (options.onSuccess) {
                    options.onSuccess();
                }
                setSaveState({
                    saving: false,
                    message: successMessage,
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

    function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const noteDraft = hrNoteDraft.trim();
        saveEmployeeForm(
            form,
            noteDraft ? "Заметка добавлена" : "Изменения сохранены",
            noteDraft ? { noteDraft, onSuccess: function () { setHrNoteDraft(""); } } : {},
        );
    }

    function handleFirstWorkdayChange(value: string) {
        const nextForm = Object.assign({}, form, { first_workday: value });
        setForm(nextForm);
        if (!value && form.first_workday) {
            saveEmployeeForm(nextForm, "Дата очищена");
        }
    }

    function handleHrNoteDraftChange(event: React.ChangeEvent<HTMLTextAreaElement>) {
        setHrNoteDraft(event.target.value);
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

    function handleResumeFileSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!resumeFile) {
            setOperationMessage("Выбери файл резюме", true);
            return;
        }
        setOpsState({ message: "", error: false, working: true });
        const formData = new FormData();
        formData.append("upload", resumeFile);
        fetch(apiUrl + "/document-slots/resume/file", {
            method: "POST",
            credentials: "same-origin",
            body: formData,
        })
            .then(function (response) {
                if (!response.ok) {
                    return response.json().catch(function () { return {}; }).then(function (payload) {
                        throw new Error(payload.detail || "Не удалось загрузить резюме");
                    });
                }
                return response.json();
            })
            .then(function (payload) {
                updatePayloadState(setState, setForm, payload.payload);
                setResumeFile(null);
                const fileInput = document.getElementById("react-resume-file-input") as HTMLInputElement | null;
                if (fileInput) {
                    fileInput.value = "";
                }
                setOperationMessage("Резюме загружено", false);
            })
            .catch(function (error) {
                setOperationMessage(error.message || "Не удалось загрузить резюме", true);
            });
    }

    function handleResumeClear() {
        setOpsState({ message: "", error: false, working: true });
        fetch(apiUrl + "/document-slots/resume", {
            method: "DELETE",
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        })
            .then(function (response) {
                if (!response.ok) {
                    return response.json().catch(function () { return {}; }).then(function (payload) {
                        throw new Error(payload.detail || "Не удалось очистить резюме");
                    });
                }
                return response.json();
            })
            .then(function (payload) {
                updatePayloadState(setState, setForm, payload);
                setResumeFile(null);
                const fileInput = document.getElementById("react-resume-file-input") as HTMLInputElement | null;
                if (fileInput) {
                    fileInput.value = "";
                }
                setOperationMessage("Резюме очищено из карточки", false);
            })
            .catch(function (error) {
                setOperationMessage(error.message || "Не удалось очистить резюме", true);
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

    function handleManualBotMessageSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const messageText = manualBotMessageText.trim();
        if (!messageText) {
            setManualBotMessageState({
                sending: false,
                message: "Введите текст сообщения",
                error: true,
            });
            return;
        }
        setFlashState({ message: "", error: false });
        setManualBotMessageState({ sending: true, message: "", error: false });
        fetch(apiUrl + "/bot-message", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/json",
            },
            body: JSON.stringify({ text: messageText }),
        })
            .then(function (response) {
                if (!response.ok) {
                    return response.json().catch(function () { return {}; }).then(function (payload) {
                        throw new Error(payload.detail || "Не удалось отправить сообщение");
                    });
                }
                return response.json();
            })
            .then(function (payload) {
                updatePayloadState(setState, setForm, payload);
                setManualBotMessageText("");
                setManualBotMessageState({
                    sending: false,
                    message: "Сообщение отправлено",
                    error: false,
                });
            })
            .catch(function (error) {
                refetchEmployeeDetail().catch(function () { return null; }).finally(function () {
                    setManualBotMessageState({
                        sending: false,
                        message: error.message || "Не удалось отправить сообщение",
                        error: true,
                    });
                });
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
    const assignmentHistory = Array.isArray(payload.assignment_history) ? payload.assignment_history : [];
    const manualBotMessageHistory = Array.isArray(payload.manual_bot_message_history)
        ? payload.manual_bot_message_history
        : [];
    const hrNotesHistory = Array.isArray(payload.hr_notes_history) ? payload.hr_notes_history : [];

    function buildDocumentItem(document: any, fallbackTitle: string, fallbackSubtitle: string, deleteAction?: () => void) {
        const kind = String(document.kind || document.item_kind || "").trim();
        const downloadUrl = document.download_url || "";
        const openUrl = document.open_url || document.url || downloadUrl || "";
        const isFileLike = kind === "file" || kind === "video" || kind === "photo" || !!downloadUrl;
        const title = document.original_filename || document.filename || document.label || document.title || fallbackTitle;
        const metaParts = [
            document.created_at_label || document.created_at || "",
            document.file_size_label || document.size_label || (
                document.file_size || document.size ? String(document.file_size || document.size) : ""
            ),
            document.source === "legacy_file" ? "старый файл" : "",
        ].filter(Boolean);

        return {
            id: document.id || document.employee_file_id || fallbackTitle,
            title: title,
            subtitle: metaParts.length ? metaParts.join(" · ") : fallbackSubtitle,
            link: openUrl,
            linkLabel: isFileLike ? "Скачать" : "Открыть",
            downloadLink: downloadUrl && downloadUrl !== openUrl ? downloadUrl : null,
            downloadLabel: "Скачать",
            deleteAction: deleteAction || null,
            deleteActionLabel: deleteAction ? "Очистить" : null,
            deleteConfirmTitle: deleteAction ? `Очистить ${fallbackTitle.toLowerCase()}?` : null,
            deleteConfirmDescription: deleteAction ? "Документ будет убран из карточки. Физический файл не удаляется." : null,
            deleteConfirmLabel: deleteAction ? "Очистить" : null,
        };
    }

    const fileItems = payload.files.map(function (file: any) {
        return {
            id: file.id,
            title: file.original_filename || "Файл",
            subtitle: (file.direction === "inbound" ? "От сотрудника" : "От HR") + " · " + file.created_at_label,
            direction: file.direction,
            link: file.download_url,
            linkLabel: "Скачать",
            deleteAction: function () { handleDeleteFile(file.id); },
            deleteActionLabel: "Удалить файл",
            deleteConfirmTitle: "Удалить файл?",
            deleteConfirmDescription: "Файл будет удален из карточки сотрудника.",
            deleteConfirmLabel: "Удалить",
        };
    });
    const hrFileItems = fileItems.filter(function (file: any) {
        return file.direction !== "inbound";
    });

    const offerDocumentItem = payload.offer_document
        ? Object.assign(
            buildDocumentItem(payload.offer_document, "Оффер", "Оффер"),
            {
                deleteAction: function () { handleOfferDelete(payload.offer_document.id); },
                deleteActionLabel: "Удалить",
                deleteConfirmTitle: "Удалить оффер?",
                deleteConfirmDescription: "Оффер будет удален из карточки сотрудника.",
                deleteConfirmLabel: "Удалить",
            },
        )
        : null;

    const resumeDocument = payload.resume_document;
    const resumeDocumentItem = resumeDocument
        ? Object.assign(
            buildDocumentItem(resumeDocument, "Резюме", "Актуальное резюме"),
            {
                deleteAction: handleResumeClear,
                deleteActionLabel: "Очистить резюме",
                deleteConfirmTitle: "Очистить резюме?",
                deleteConfirmDescription: "Актуальное резюме будет убрано из карточки. Физический файл не удаляется.",
                deleteConfirmLabel: "Очистить",
            },
        )
        : null;
    const testAssignmentDocument = payload.test_assignment_answer || payload.test_task_result;
    const testAssignmentDocumentItem = testAssignmentDocument
        ? buildDocumentItem(testAssignmentDocument, "Тестовое задание / ответ кандидата", "Ответ кандидата")
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
            {/*
              Статус и этап — свойства записи, а не действия, но полоса
              заголовка — единственное место, где они видны без прокрутки;
              компактные бейджи в слоте действий разрешены самой полосой.
            */}
            <PageDetailHeader
                title={form.full_name || "Сотрудник #" + form.id}
                sectionTitle={meta.list_title || (isCandidate ? "Кандидаты" : "Сотрудники")}
                backHref={meta.list_url || listUrl}
                actions={
                    <>
                        <Badge variant="secondary">{meta.status_label || "Без статуса"}</Badge>
                        {isCandidate ? (
                            <Badge variant="outline">{meta.candidate_work_stage_label || "Без этапа"}</Badge>
                        ) : (
                            <Badge variant="outline">{"Стаж: " + meta.tenure_years + " лет"}</Badge>
                        )}
                    </>
                }
            />
            <EmployeeFlashNotice message={flashState.message} error={flashState.error} />
            <section className="employee-detail-grid">
                <div className="employee-detail-main">
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
                        hrNoteDraft={hrNoteDraft}
                        hrNotesHistory={hrNotesHistory}
                        onHrNoteDraftChange={handleHrNoteDraftChange}
                        onFirstWorkdayChange={handleFirstWorkdayChange}
                    />
                    <AssignmentHistorySection items={assignmentHistory} />
                </div>
                <EmployeeOperationsSection
                    opsState={opsState}
                    offerUrl={offerUrl}
                    setOfferUrl={setOfferUrl}
                    offerFile={offerFile}
                    setOfferFile={setOfferFile}
                    offerDocumentItem={offerDocumentItem}
                    resumeFile={resumeFile}
                    setResumeFile={setResumeFile}
                    resumeDocumentItem={resumeDocumentItem}
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
                    handleResumeFileSubmit={handleResumeFileSubmit}
                    handleScheduleSubmit={handleScheduleSubmit}
                    handleLaunchSubmit={handleLaunchSubmit}
                    handleFileSubmit={handleFileSubmit}
                    handlePromoteToAdaptation={handlePromoteToAdaptation}
                    handleResetBotLinkage={handleResetBotLinkage}
                    handleDeleteEmployee={handleDeleteEmployee}
                    hrFileItems={hrFileItems}
                    testAssignmentDocumentItem={testAssignmentDocumentItem}
                    launchItems={launchItems}
                    manualLaunchItems={manualLaunchItems}
                    manualBotMessageText={manualBotMessageText}
                    manualBotMessageState={manualBotMessageState}
                    setManualBotMessageText={setManualBotMessageText}
                    handleManualBotMessageSubmit={handleManualBotMessageSubmit}
                    manualBotMessageHistory={manualBotMessageHistory}
                    isCandidate={isCandidate}
                />
            </section>
        </div>
    );
}
