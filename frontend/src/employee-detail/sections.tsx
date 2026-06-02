import React from "react";
import {
    ArrowLeft,
    CalendarClock,
    Download,
    ExternalLink,
    FileText,
    Link2,
    Play,
    Send,
    ShieldAlert,
    Trash2,
    Upload,
} from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardFooter,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import {
    Empty,
    EmptyHeader,
    EmptyMedia,
    EmptyTitle,
} from "@/components/ui/empty";
import {
    Field,
    FieldContent,
    FieldGroup,
    FieldLabel,
    FieldSet,
    FieldTitle,
} from "@/components/ui/field";
import { Checkbox } from "@/components/ui/checkbox";
import { DatePicker, DateTimePicker, TimeSelect } from "@/components/ui/date-picker";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectGroup,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type DetailItem = {
    id: string | number;
    title: string;
    subtitle?: string;
    link?: string | null;
    linkLabel?: string | null;
    extraAction?: (() => void) | null;
    extraActionLabel?: string | null;
};

const EMPTY_SELECT_VALUE = "__empty__";

function changeFieldValue(handleChange: any, name: string, value: string) {
    handleChange({ target: { name, value } });
}

function changeCheckboxValue(handleChange: any, name: string, checked: boolean) {
    handleChange({
        target: {
            name,
            value: checked,
            checked,
            type: "checkbox",
        },
    });
}

function SelectField(props: {
    name: string;
    value: string;
    onChange: any;
    placeholder: string;
    options: Array<{ value: string; label: string }> | string[];
}) {
    const normalizedOptions = props.options.map(function (item) {
        return typeof item === "string" ? { value: item, label: item } : item;
    });
    const selectItems = [{ value: EMPTY_SELECT_VALUE, label: props.placeholder }].concat(normalizedOptions);

    return (
        <Select
            items={selectItems}
            value={props.value || EMPTY_SELECT_VALUE}
            onValueChange={function (value) {
                changeFieldValue(props.onChange, props.name, value === EMPTY_SELECT_VALUE ? "" : value);
            }}
        >
            <SelectTrigger className="w-full">
                <SelectValue placeholder={props.placeholder} />
            </SelectTrigger>
            <SelectContent>
                <SelectGroup>
                    {selectItems.map(function (option) {
                        return (
                            <SelectItem value={option.value} key={option.value}>
                                {option.label}
                            </SelectItem>
                        );
                    })}
                </SelectGroup>
            </SelectContent>
        </Select>
    );
}

function DetailCard(props: React.ComponentProps<typeof Card>) {
    const { className, ...rest } = props;
    return <Card className={cn("employee-detail-card shadow-none ring-0", className)} {...rest} />;
}

function PlannedField(props: {
    label: string;
    value?: string;
    placeholder?: string;
    kind?: "input" | "date" | "link" | "select";
}) {
    const { label, value, placeholder, kind = "input" } = props;
    return (
        <Field data-disabled>
            <FieldLabel>{label}</FieldLabel>
            {kind === "select" ? (
                <Select
                    value={EMPTY_SELECT_VALUE}
                    items={[{ value: EMPTY_SELECT_VALUE, label: placeholder || "Не настроено" }]}
                >
                    <SelectTrigger className="w-full" disabled>
                        <SelectValue placeholder={placeholder || "Не настроено"} />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectGroup>
                            <SelectItem value={EMPTY_SELECT_VALUE}>
                                {placeholder || "Не настроено"}
                            </SelectItem>
                        </SelectGroup>
                    </SelectContent>
                </Select>
            ) : kind === "date" ? (
                <DatePicker disabled value={value || ""} onValueChange={function () {}} />
            ) : (
                <Input
                    disabled
                    type="text"
                    value={value || ""}
                    placeholder={placeholder || "Не настроено"}
                    readOnly
                />
            )}
        </Field>
    );
}

function CheckboxField(props: {
    name: string;
    checked: boolean;
    onChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
    title: string;
}) {
    return (
        <Field orientation="horizontal" className="employee-check-field">
            <Checkbox
                checked={props.checked}
                onCheckedChange={function (value) {
                    changeCheckboxValue(props.onChange, props.name, Boolean(value));
                }}
            />
            <FieldContent>
                <FieldTitle>{props.title}</FieldTitle>
            </FieldContent>
        </Field>
    );
}

function DocumentList(props: {
    title: string;
    items: DetailItem[];
    emptyTitle: string;
    children?: React.ReactNode;
}) {
    const { title, items, emptyTitle, children } = props;
    return (
        <DetailCard>
            <CardHeader>
                <CardTitle>{title}</CardTitle>
            </CardHeader>
            <CardContent>
                {children ? <div className="employee-document-tools">{children}</div> : null}
                {items.length ? (
                    <div className="employee-document-list">
                        {items.map(function (item) {
                            return (
                                <div className="employee-document-row" key={item.id}>
                                    <div className="employee-document-icon">
                                        <FileText />
                                    </div>
                                    <div className="employee-document-meta">
                                        <div className="employee-document-title">{item.title}</div>
                                        {item.subtitle ? (
                                            <div className="employee-document-subtitle">{item.subtitle}</div>
                                        ) : null}
                                    </div>
                                    <div className="employee-document-actions">
                                        {item.link ? (
                                            <a
                                                href={item.link}
                                                className={buttonVariants({
                                                    variant: "outline",
                                                    size: item.linkLabel === "Скачать" ? "icon-sm" : "sm",
                                                })}
                                                aria-label={item.linkLabel || "Открыть"}
                                                title={item.linkLabel || "Открыть"}
                                            >
                                                {item.linkLabel === "Скачать" ? (
                                                    <Download />
                                                ) : (
                                                    <ExternalLink data-icon="inline-start" />
                                                )}
                                                {item.linkLabel === "Скачать" ? null : item.linkLabel || "Открыть"}
                                            </a>
                                        ) : null}
                                        {item.extraAction ? (
                                            <Button
                                                type="button"
                                                variant="secondary"
                                                size={item.extraActionLabel === "Отправить в мессенджер" ? "icon-sm" : "sm"}
                                                onClick={item.extraAction}
                                                aria-label={item.extraActionLabel || "Отправить"}
                                                title={item.extraActionLabel || "Отправить"}
                                            >
                                                <Send data-icon={item.extraActionLabel === "Отправить в мессенджер" ? undefined : "inline-start"} />
                                                {item.extraActionLabel === "Отправить в мессенджер"
                                                    ? null
                                                    : item.extraActionLabel || "Отправить"}
                                            </Button>
                                        ) : null}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                ) : (
                    <Empty className="employee-empty-state">
                        <EmptyHeader>
                            <EmptyMedia variant="icon">
                                <FileText />
                            </EmptyMedia>
                            <EmptyTitle>{emptyTitle}</EmptyTitle>
                        </EmptyHeader>
                    </Empty>
                )}
            </CardContent>
        </DetailCard>
    );
}

function ScenarioList(props: { items: DetailItem[] }) {
    if (!props.items.length) {
        return (
            <Empty className="employee-empty-state">
                <EmptyHeader>
                    <EmptyMedia variant="icon">
                        <CalendarClock />
                    </EmptyMedia>
                    <EmptyTitle>Запусков нет</EmptyTitle>
                </EmptyHeader>
            </Empty>
        );
    }

    return (
        <div className="employee-document-list">
            {props.items.map(function (item) {
                return (
                    <div className="employee-document-row" key={item.id}>
                        <div className="employee-document-icon">
                            <CalendarClock />
                        </div>
                        <div className="employee-document-meta">
                            <div className="employee-document-title">{item.title}</div>
                            <div className="employee-document-subtitle">{item.subtitle}</div>
                        </div>
                        <div className="employee-document-actions">
                            {item.link ? (
                                <a
                                    href={item.link}
                                    className={buttonVariants({ variant: "outline", size: "icon-sm" })}
                                    aria-label={item.linkLabel || "Открыть"}
                                    title={item.linkLabel || "Открыть"}
                                >
                                    <ExternalLink />
                                </a>
                            ) : null}
                            {item.extraAction ? (
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon-sm"
                                    onClick={item.extraAction}
                                    aria-label={item.extraActionLabel || "Удалить"}
                                    title={item.extraActionLabel || "Удалить"}
                                >
                                    <Trash2 />
                                </Button>
                            ) : null}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

export function EmployeeDetailLoading() {
    return (
        <DetailCard className="employee-detail-loading">
            <CardContent>Загружаю карточку сотрудника...</CardContent>
        </DetailCard>
    );
}

export function EmployeeDetailError(props: { message: string; listUrl: string }) {
    return (
        <DetailCard>
            <CardHeader>
                <CardTitle>Карточка не загрузилась</CardTitle>
            </CardHeader>
            <CardContent>{props.message || "Не удалось загрузить карточку сотрудника"}</CardContent>
            <CardFooter>
                <a href={props.listUrl} className={buttonVariants({ variant: "outline" })}>
                    <ArrowLeft data-icon="inline-start" />
                    Вернуться к списку
                </a>
            </CardFooter>
        </DetailCard>
    );
}

export function EmployeeFlashNotice(props: { message: string; error: boolean }) {
    if (!props.message) {
        return null;
    }
    return (
        <Alert variant={props.error ? "destructive" : "default"}>
            <AlertDescription>{props.message}</AlertDescription>
        </Alert>
    );
}

export function EmployeeDetailHeader(props: { meta: any }) {
    const { meta } = props;
    return (
        <div className="employee-detail-topline">
            <a href={meta.list_url} className={buttonVariants({ variant: "ghost", size: "sm" })}>
                <ArrowLeft data-icon="inline-start" />
                {meta.list_title}
            </a>
        </div>
    );
}

export function EmployeeProfileSection(props: any) {
    const {
        form,
        isCandidate,
        options,
        workHoursParts,
        handleChange,
        handleWorkHoursChange,
        handleSubmit,
        saveState,
    } = props;
    return (
        <form className="employee-profile-form" onSubmit={handleSubmit}>
            <div className="employee-section-label">Профиль</div>
            <DetailCard>
                <CardHeader>
                    <CardTitle>{isCandidate ? "Профиль кандидата" : "Профиль сотрудника"}</CardTitle>
                </CardHeader>
                <CardContent>
                    <FieldGroup className="employee-field-grid">
                        <Field>
                            <FieldLabel htmlFor="employee-full-name">ФИО</FieldLabel>
                            <Input
                                id="employee-full-name"
                                type="text"
                                name="full_name"
                                value={form.full_name}
                                onChange={handleChange}
                            />
                        </Field>
                        <Field>
                            <FieldLabel htmlFor="employee-chat-handle">Telegram username</FieldLabel>
                            <Input
                                id="employee-chat-handle"
                                type="text"
                                name="chat_handle"
                                value={form.chat_handle || ""}
                                onChange={handleChange}
                                placeholder="@username"
                            />
                        </Field>
                        <Field>
                            <FieldLabel>{isCandidate ? "Плановая дата выхода" : "Первый день сотрудника"}</FieldLabel>
                            <DatePicker
                                value={form.first_workday}
                                onValueChange={function (value) {
                                    changeFieldValue(handleChange, "first_workday", value);
                                }}
                            />
                        </Field>
                        <Field>
                            <FieldLabel htmlFor="employee-position">
                                {isCandidate ? "Желаемая должность" : "Должность"}
                            </FieldLabel>
                            <SelectField
                                name="desired_position"
                                value={form.desired_position}
                                onChange={handleChange}
                                placeholder="Не указана"
                                options={options.employee_role_values}
                            />
                        </Field>
                        <Field>
                            <FieldLabel>Доход / ожидания</FieldLabel>
                            <Input
                                type="text"
                                name="salary_expectation"
                                value={form.salary_expectation}
                                onChange={handleChange}
                            />
                        </Field>
                        <Field>
                            <FieldLabel>Telegram-привязка</FieldLabel>
                            <div className="employee-readonly-field">
                                {form.chat_id ? "Привязан к боту" : "Не привязан. Нужен Start в боте."}
                            </div>
                        </Field>
                    </FieldGroup>
                </CardContent>
            </DetailCard>

            {isCandidate ? (
                <>
                    <div className="employee-section-label">Найм</div>
                    <DetailCard>
                        <CardHeader>
                            <CardTitle>Найм</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <FieldGroup className="employee-field-grid">
                                <Field>
                                    <FieldLabel>Текущий этап</FieldLabel>
                                    <SelectField
                                        name="candidate_work_stage"
                                        value={form.candidate_work_stage}
                                        onChange={handleChange}
                                        placeholder="Не указан"
                                        options={options.candidate_work_stage_values}
                                    />
                                </Field>
                                <Field>
                                    <FieldLabel>Дедлайн тестового задания</FieldLabel>
                                    <DateTimePicker
                                        value={form.test_task_due_at}
                                        onValueChange={function (value) {
                                            changeFieldValue(handleChange, "test_task_due_at", value);
                                        }}
                                    />
                                </Field>
                            </FieldGroup>
                            <CheckboxField
                                name="personal_data_consent"
                                checked={!!form.personal_data_consent}
                                onChange={handleChange}
                                title="Согласие на ПДн"
                            />
                        </CardContent>
                    </DetailCard>
                </>
            ) : (
                <>
                    <div className="employee-section-label">Работа</div>
                    <DetailCard>
                        <CardHeader>
                            <CardTitle>Рабочий профиль</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <FieldGroup className="employee-field-grid">
                                <Field>
                                    <FieldLabel>Дата рождения</FieldLabel>
                                    <DatePicker
                                        value={form.birth_date}
                                        onValueChange={function (value) {
                                            changeFieldValue(handleChange, "birth_date", value);
                                        }}
                                    />
                                </Field>
                                <Field>
                                    <FieldLabel>Рабочая почта</FieldLabel>
                                    <Input
                                        type="email"
                                        inputMode="email"
                                        autoComplete="email"
                                        name="work_email"
                                        value={form.work_email}
                                        onChange={handleChange}
                                    />
                                </Field>
                                <Field>
                                    <FieldLabel>Рабочие часы</FieldLabel>
                                    <div className="employee-time-range">
                                        <TimeSelect
                                            value={workHoursParts.start}
                                            onValueChange={function (value) {
                                                handleWorkHoursChange("start", value);
                                            }}
                                        />
                                        <span>до</span>
                                        <TimeSelect
                                            value={workHoursParts.end}
                                            onValueChange={function (value) {
                                                handleWorkHoursChange("end", value);
                                            }}
                                        />
                                    </div>
                                </Field>
                                <Field>
                                    <FieldLabel>Статус сотрудника</FieldLabel>
                                    <SelectField
                                        name="employee_stage"
                                        value={form.employee_stage}
                                        onChange={handleChange}
                                        placeholder="Не указан"
                                        options={options.employee_stage_values}
                                    />
                                </Field>
                            </FieldGroup>
                        </CardContent>
                    </DetailCard>

                    <div className="employee-section-label">Адаптация</div>
                    <DetailCard>
                        <CardHeader>
                            <CardTitle>Сопровождение</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <FieldGroup className="employee-field-grid">
                                <Field>
                                    <FieldLabel>Руководитель сотрудника</FieldLabel>
                                    <Input
                                        type="text"
                                        name="manager_chat_id"
                                        value={form.manager_chat_id}
                                        onChange={handleChange}
                                        placeholder="Telegram id"
                                    />
                                </Field>
                                <Field>
                                    <FieldLabel>Наставник адаптации</FieldLabel>
                                    <Input
                                        type="text"
                                        name="mentor_adaptation_chat_id"
                                        value={form.mentor_adaptation_chat_id}
                                        onChange={handleChange}
                                        placeholder="Telegram id"
                                    />
                                </Field>
                                <Field>
                                    <FieldLabel>Наставник ИПР</FieldLabel>
                                    <Input
                                        type="text"
                                        name="mentor_ipr_chat_id"
                                        value={form.mentor_ipr_chat_id}
                                        onChange={handleChange}
                                        placeholder="Telegram id"
                                    />
                                </Field>
                                <PlannedField
                                    label="Наставник"
                                    kind="select"
                                    placeholder="Выбор сотрудника из списка"
                                />
                                <PlannedField label="Задачи на ИС" kind="link" placeholder="Ссылка на файл" />
                                <PlannedField label="Обратная связь" kind="link" placeholder="Ссылка на файл" />
                                <PlannedField label="Середина адаптации" kind="date" />
                                <PlannedField label="Конец адаптации" kind="date" />
                                <PlannedField
                                    label="Должность руководителя"
                                    placeholder="Показывать только для руководителя"
                                />
                            </FieldGroup>
                            <CheckboxField
                                name="employee_data_consent"
                                checked={!!form.employee_data_consent}
                                onChange={handleChange}
                                title="Согласие на ПДн"
                            />
                        </CardContent>
                    </DetailCard>
                </>
            )}

            <div className="employee-section-label">Заметки</div>
            <DetailCard>
                <CardHeader>
                    <CardTitle>Заметки и доступ</CardTitle>
                </CardHeader>
                <CardContent>
                    <FieldSet>
                        <Field>
                            <FieldLabel>Заметки HR</FieldLabel>
                            <Textarea name="notes" value={form.notes} onChange={handleChange} rows={5} />
                        </Field>
                        <CheckboxField
                            name="is_bot_blocked"
                            checked={!!form.is_bot_blocked}
                            onChange={handleChange}
                            title="Заблокировать доступ к чат-боту"
                        />
                    </FieldSet>
                </CardContent>
                <CardFooter className="employee-save-footer">
                    <span className={cn("employee-save-state", saveState.error && "is-error")}>
                        {saveState.message || " "}
                    </span>
                    <Button type="submit" disabled={saveState.saving}>
                        {saveState.saving ? "Сохраняю..." : "Сохранить"}
                    </Button>
                </CardFooter>
            </DetailCard>
        </form>
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
        employeeFileItems,
        hrFileItems,
        documentItems,
        launchItems,
    } = props;
    const scenarioItems = [{ value: EMPTY_SELECT_VALUE, label: "Выберите сценарий" }].concat(
        payload.options.scenarios.map(function (item: any) {
            return { value: item.value, label: item.label };
        }),
    );

    return (
        <div className="employee-detail-side">
            {opsState.message || opsState.working ? (
                <Alert variant={opsState.error ? "destructive" : "default"}>
                    <AlertDescription>
                        {opsState.message || (opsState.working ? "Выполняю действие..." : "")}
                    </AlertDescription>
                </Alert>
            ) : null}

            <div className="employee-section-label">Сценарии</div>
            <DetailCard>
                <CardHeader>
                    <CardTitle>Сценарии</CardTitle>
                </CardHeader>
                <CardContent className="employee-ops-stack">
                    <form className="employee-inline-form" onSubmit={handleLaunchSubmit}>
                        <FieldGroup>
                            <Field>
                                <FieldLabel>Запустить сейчас</FieldLabel>
                                <Select
                                    items={scenarioItems}
                                    value={launchFlowKey || EMPTY_SELECT_VALUE}
                                    onValueChange={function (value) {
                                        setLaunchFlowKey(value === EMPTY_SELECT_VALUE ? "" : value);
                                    }}
                                >
                                    <SelectTrigger className="w-full">
                                        <SelectValue placeholder="Выберите сценарий" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectGroup>
                                            {scenarioItems.map(function (item: any) {
                                                return (
                                                    <SelectItem value={item.value} key={item.value}>
                                                        {item.label}
                                                    </SelectItem>
                                                );
                                            })}
                                        </SelectGroup>
                                    </SelectContent>
                                </Select>
                            </Field>
                            <Button type="submit" variant="secondary">
                                <Play data-icon="inline-start" />
                                Запустить
                            </Button>
                        </FieldGroup>
                    </form>

                    <form className="employee-inline-form" onSubmit={handleScheduleSubmit}>
                        <FieldGroup>
                            <Field>
                                <FieldLabel>Запланировать</FieldLabel>
                                <Select
                                    items={scenarioItems}
                                    value={scheduleForm.flow_key || EMPTY_SELECT_VALUE}
                                    onValueChange={function (value) {
                                        setScheduleForm(function (prev: any) {
                                            return Object.assign({}, prev, {
                                                flow_key: value === EMPTY_SELECT_VALUE ? "" : value,
                                            });
                                        });
                                    }}
                                >
                                    <SelectTrigger className="w-full">
                                        <SelectValue placeholder="Выберите сценарий" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectGroup>
                                            {scenarioItems.map(function (item: any) {
                                                return (
                                                    <SelectItem value={item.value} key={item.value}>
                                                        {item.label}
                                                    </SelectItem>
                                                );
                                            })}
                                        </SelectGroup>
                                    </SelectContent>
                                </Select>
                            </Field>
                            <Field>
                                <FieldLabel>Время отправки</FieldLabel>
                                <DateTimePicker
                                    value={scheduleForm.requested_at}
                                    onValueChange={function (value) {
                                        setScheduleForm(function (prev: any) {
                                            return Object.assign({}, prev, { requested_at: value });
                                        });
                                    }}
                                />
                            </Field>
                            <Button type="submit" variant="outline">
                                <CalendarClock data-icon="inline-start" />
                                Запланировать
                            </Button>
                        </FieldGroup>
                    </form>
                </CardContent>
            </DetailCard>

            <div className="employee-section-label">Документы</div>
            <DocumentList
                title="Файлы HR"
                items={hrFileItems}
                emptyTitle="HR-файлов нет"
            >
                    <form className="employee-inline-form" onSubmit={handleFileSubmit}>
                        <FieldGroup>
                            <Field>
                                <FieldLabel>Загрузить файл HR</FieldLabel>
                                <Input
                                    id="react-file-input"
                                    className="employee-file-native"
                                    type="file"
                                    onChange={function (event) {
                                        const file = event.target.files && event.target.files[0] ? event.target.files[0] : null;
                                        setFileForm(function (prev: any) {
                                            return Object.assign({}, prev, { upload: file });
                                        });
                                    }}
                                />
                                <div className="employee-file-picker">
                                    <label
                                        htmlFor="react-file-input"
                                        className={buttonVariants({ variant: "outline", size: "sm" })}
                                    >
                                        <Upload data-icon="inline-start" />
                                        Выбрать файл
                                    </label>
                                    <span>{fileForm.upload ? fileForm.upload.name : "Файл не выбран"}</span>
                                </div>
                            </Field>
                            <Button type="submit" variant="secondary">
                                <Upload data-icon="inline-start" />
                                Загрузить
                            </Button>
                        </FieldGroup>
                    </form>
            </DocumentList>

            <DocumentList
                title="Документы сотрудника"
                items={employeeFileItems}
                emptyTitle="Входящих документов нет"
            />

            <DocumentList
                title="Ссылки HR"
                items={documentItems}
                emptyTitle="Ссылок нет"
            >
                    <form className="employee-inline-form" onSubmit={handleOfferSubmit}>
                        <FieldGroup>
                            <Field>
                                <FieldLabel>Новая ссылка</FieldLabel>
                                <Input
                                    type="url"
                                    value={offerUrl}
                                    onChange={function (event) {
                                        setOfferUrl(event.target.value);
                                    }}
                                    placeholder="https://docs.google.com/..."
                                />
                            </Field>
                            <div className="employee-action-row">
                                <Button type="submit" variant="outline">
                                    <Link2 data-icon="inline-start" />
                                    Добавить ссылку
                                </Button>
                                {payload.document_links.length ? (
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        onClick={function () {
                                            handleOfferDelete(payload.document_links[0].id);
                                        }}
                                    >
                                        <Trash2 data-icon="inline-start" />
                                        Удалить
                                    </Button>
                                ) : null}
                            </div>
                        </FieldGroup>
                    </form>
            </DocumentList>

            <div className="employee-section-label">Очередь</div>
            <DetailCard>
                <CardHeader>
                    <CardTitle>Запланированные сценарии</CardTitle>
                </CardHeader>
                <CardContent>
                    <ScenarioList items={launchItems} />
                </CardContent>
            </DetailCard>

            <div className="employee-section-label">Опасная зона</div>
            <DetailCard className="employee-danger-card">
                <CardHeader>
                    <CardTitle>
                        <ShieldAlert data-icon="inline-start" />
                        Редкие действия
                    </CardTitle>
                </CardHeader>
                <CardFooter>
                    <Button type="button" variant="destructive" onClick={handleDeleteEmployee}>
                        <Trash2 data-icon="inline-start" />
                        Удалить сотрудника
                    </Button>
                </CardFooter>
            </DetailCard>
        </div>
    );
}
