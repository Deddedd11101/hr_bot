import React from "react";
import { Download, Link2, Plus, Save, Trash2, Upload } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmAction } from "@/components/ui/confirm-action";
import { Field, FieldContent, FieldGroup, FieldLabel, FieldTitle } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type DocumentItem = {
  id: number;
  title: string;
  description: string;
  category: string;
  item_kind: string;
  item_kind_label: string;
  external_url: string;
  original_filename: string;
  mime_type: string;
  file_size: number | null;
  is_active: boolean;
  sort_order: number;
  download_url: string;
  created_at_label: string;
  updated_at_label: string;
};

type Workspace = {
  document_kind_labels: Record<string, string>;
  items: DocumentItem[];
};

type DocumentsPageProps = {
  apiUrl: string;
};

async function requestJson<T>(path: string, options: RequestInit = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "Запрос не выполнен");
  }
  return response.json() as Promise<T>;
}

function StatusAlert({ message, type }: { message: string; type: "success" | "error" }) {
  if (!message) return null;
  return (
    <Alert variant={type === "error" ? "destructive" : "default"} className={type === "success" ? "border-primary/30 bg-primary/5" : undefined}>
      <AlertTitle>{type === "success" ? "Сохранено" : "Ошибка"}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}

function formatFileSize(bytes: number | null) {
  if (!bytes || bytes <= 0) return "—";
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

export function DocumentsPage({ apiUrl }: DocumentsPageProps) {
  const [workspace, setWorkspace] = React.useState<Workspace | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [message, setMessage] = React.useState("");
  const [error, setError] = React.useState("");
  const [linkDraft, setLinkDraft] = React.useState({
    title: "",
    description: "",
    category: "",
    external_url: "",
    is_active: true,
  });
  const [fileDraft, setFileDraft] = React.useState({
    title: "",
    description: "",
    category: "",
    is_active: true,
    upload: null as File | null,
  });
  const [menuScaffoldTitle, setMenuScaffoldTitle] = React.useState("Документы");
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  React.useEffect(() => {
    requestJson<Workspace>(apiUrl)
      .then((payload) => setWorkspace(payload))
      .catch((err) => setError(err instanceof Error ? err.message : "Не удалось загрузить документы"))
      .finally(() => setLoading(false));
  }, [apiUrl]);

  const refreshFromApi = async (promise: Promise<Workspace>, successMessage: string) => {
    setError("");
    setMessage("");
    try {
      const payload = await promise;
      setWorkspace(payload);
      setMessage(successMessage);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Операция не выполнена");
    }
  };

  if (loading) {
    return (
      <Card className="admin-page-shell border border-border/80 bg-card shadow-none ring-0">
        <CardContent className="p-8 text-sm text-muted-foreground">Загружаю библиотеку документов...</CardContent>
      </Card>
    );
  }

  if (!workspace) {
    return <StatusAlert type="error" message={error || "Библиотека документов не загружена"} />;
  }

  return (
    <div className="admin-page-stack gap-5">
      <header className="admin-page-surface border border-border/80 bg-card p-5 shadow-none ring-0">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">Документы</h1>
          </div>
          <div className="grid gap-3 rounded-xl border border-border bg-muted/30 p-3 xl:min-w-[420px] xl:grid-cols-[minmax(0,1fr)_auto]">
            <Field>
              <FieldLabel>Собрать раздел меню бота</FieldLabel>
              <Input value={menuScaffoldTitle} onChange={(event) => setMenuScaffoldTitle(event.target.value)} autoComplete="off" />
            </Field>
            <div className="flex gap-2 xl:self-end">
              <Button
                variant="secondary"
                onClick={() =>
                  refreshFromApi(
                    requestJson<{ workspace: Workspace }>("/api/documents/menu-scaffold", {
                      method: "POST",
                      body: JSON.stringify({ root_title: menuScaffoldTitle, mode: "create" }),
                    }).then((result) => result.workspace),
                    "Раздел меню бота собран из категорий документов",
                  )
                }
              >
                <Plus data-icon="inline-start" />
                Собрать
              </Button>
              <Button
                onClick={() =>
                  refreshFromApi(
                    requestJson<{ workspace: Workspace }>("/api/documents/menu-scaffold", {
                      method: "POST",
                      body: JSON.stringify({ root_title: menuScaffoldTitle, mode: "rebuild" }),
                    }).then((result) => result.workspace),
                    "Сгенерированный раздел меню пересобран",
                  )
                }
              >
                <Save data-icon="inline-start" />
                Пересобрать
              </Button>
            </div>
          </div>
        </div>
      </header>

      <StatusAlert type="success" message={message} />
      <StatusAlert type="error" message={error} />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <Card className="border border-border/80 bg-card shadow-none ring-0">
          <CardHeader className="border-b border-border/70 pb-4">
            <CardTitle className="text-base font-semibold">Добавить ссылку</CardTitle>
            <CardDescription>Справочники, порталы, таблицы, внешние документы.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 pt-5">
            <FieldGroup className="grid gap-4 md:grid-cols-2">
              <Field>
                <FieldLabel>Название</FieldLabel>
                <Input value={linkDraft.title} onChange={(event) => setLinkDraft((prev) => ({ ...prev, title: event.target.value }))} autoComplete="off" />
              </Field>
              <Field>
                <FieldLabel>Категория</FieldLabel>
                <Input value={linkDraft.category} onChange={(event) => setLinkDraft((prev) => ({ ...prev, category: event.target.value }))} placeholder="Регламенты" autoComplete="off" />
              </Field>
            </FieldGroup>
            <Field>
              <FieldLabel>Ссылка</FieldLabel>
              <Input value={linkDraft.external_url} onChange={(event) => setLinkDraft((prev) => ({ ...prev, external_url: event.target.value }))} placeholder="https://..." autoComplete="off" />
            </Field>
            <Field>
              <FieldLabel>Описание</FieldLabel>
              <Textarea value={linkDraft.description} onChange={(event) => setLinkDraft((prev) => ({ ...prev, description: event.target.value }))} rows={3} />
            </Field>
            <Field orientation="horizontal">
              <Checkbox checked={linkDraft.is_active} onCheckedChange={() => setLinkDraft((prev) => ({ ...prev, is_active: !prev.is_active }))} />
              <FieldContent>
                <FieldTitle>Документ активен</FieldTitle>
              </FieldContent>
            </Field>
            <div className="flex justify-end">
              <Button
                onClick={() =>
                  refreshFromApi(
                    requestJson<Workspace>("/api/documents/links", {
                      method: "POST",
                      body: JSON.stringify(linkDraft),
                    }),
                    "Ссылка добавлена",
                  ).then(() => setLinkDraft({ title: "", description: "", category: "", external_url: "", is_active: true }))
                }
              >
                <Plus data-icon="inline-start" />
                Добавить ссылку
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="border border-border/80 bg-card shadow-none ring-0">
          <CardHeader className="border-b border-border/70 pb-4">
            <CardTitle className="text-base font-semibold">Загрузить файл</CardTitle>
            <CardDescription>PDF, DOCX, изображения и другие файлы для отправки ботом.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 pt-5">
            <FieldGroup className="grid gap-4 md:grid-cols-2">
              <Field>
                <FieldLabel>Название</FieldLabel>
                <Input value={fileDraft.title} onChange={(event) => setFileDraft((prev) => ({ ...prev, title: event.target.value }))} autoComplete="off" />
              </Field>
              <Field>
                <FieldLabel>Категория</FieldLabel>
                <Input value={fileDraft.category} onChange={(event) => setFileDraft((prev) => ({ ...prev, category: event.target.value }))} placeholder="Оформление" autoComplete="off" />
              </Field>
            </FieldGroup>
            <Field>
              <FieldLabel>Описание</FieldLabel>
              <Textarea value={fileDraft.description} onChange={(event) => setFileDraft((prev) => ({ ...prev, description: event.target.value }))} rows={3} />
            </Field>
            <Field>
              <FieldLabel>Файл</FieldLabel>
              <Input
                ref={fileInputRef}
                type="file"
                className="sr-only"
                onChange={(event) => setFileDraft((prev) => ({ ...prev, upload: event.target.files?.[0] || null }))}
              />
              <div className="flex min-w-0 items-center gap-3">
                <Button type="button" variant="outline" onClick={() => fileInputRef.current?.click()}>
                  <Upload data-icon="inline-start" />
                  Выбрать файл
                </Button>
                <span className="min-w-0 truncate text-sm text-muted-foreground">
                  {fileDraft.upload?.name || "Файл не выбран"}
                </span>
              </div>
            </Field>
            <Field orientation="horizontal">
              <Checkbox checked={fileDraft.is_active} onCheckedChange={() => setFileDraft((prev) => ({ ...prev, is_active: !prev.is_active }))} />
              <FieldContent>
                <FieldTitle>Документ активен</FieldTitle>
              </FieldContent>
            </Field>
            <div className="flex justify-end">
              <Button
                onClick={() => {
                  if (!fileDraft.upload) {
                    setError("Выберите файл для загрузки");
                    return;
                  }
                  const formData = new FormData();
                  formData.append("title", fileDraft.title);
                  formData.append("description", fileDraft.description);
                  formData.append("category", fileDraft.category);
                  formData.append("is_active", fileDraft.is_active ? "true" : "false");
                  formData.append("upload", fileDraft.upload);
                  refreshFromApi(
                    fetch("/api/documents/files", {
                      method: "POST",
                      credentials: "same-origin",
                      headers: { Accept: "application/json" },
                      body: formData,
                    }).then(async (response) => {
                      if (!response.ok) {
                        const payload = await response.json().catch(() => ({}));
                        throw new Error(payload.detail || "Не удалось загрузить файл");
                      }
                      return response.json();
                    }),
                    "Файл добавлен",
                  ).then(() => setFileDraft({ title: "", description: "", category: "", is_active: true, upload: null }));
                }}
              >
                <Upload data-icon="inline-start" />
                Загрузить файл
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="border border-border/80 bg-card shadow-none ring-0">
        <CardHeader className="border-b border-border/70 pb-4">
          <CardTitle className="text-base font-semibold">Библиотека</CardTitle>
          <CardDescription>Эти документы потом можно привязывать к кнопкам в меню бота.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 pt-5">
          {workspace.items.length ? (
            workspace.items.map((item) => (
              <div key={item.id} className="grid gap-4 rounded-xl border border-border bg-background p-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.85fr)_auto] xl:items-start">
                <div className="grid gap-4">
                  <FieldGroup className="grid gap-4 md:grid-cols-2">
                    <Field>
                      <FieldLabel>Название</FieldLabel>
                      <Input
                        value={item.title}
                        onChange={(event) =>
                          setWorkspace((current) =>
                            current
                              ? {
                                  ...current,
                                  items: current.items.map((entry) => (entry.id === item.id ? { ...entry, title: event.target.value } : entry)),
                                }
                              : current,
                          )
                        }
                      />
                    </Field>
                    <Field>
                      <FieldLabel>Тип</FieldLabel>
                      <div className="rounded-md border border-input bg-muted/35 px-3 py-2 text-sm text-foreground">
                        {item.item_kind_label}
                      </div>
                    </Field>
                  </FieldGroup>
                  <FieldGroup className="grid gap-4 md:grid-cols-2">
                    <Field>
                      <FieldLabel>Категория</FieldLabel>
                      <Input
                        value={item.category}
                        onChange={(event) =>
                          setWorkspace((current) =>
                            current
                              ? {
                                  ...current,
                                  items: current.items.map((entry) => (entry.id === item.id ? { ...entry, category: event.target.value } : entry)),
                                }
                              : current,
                          )
                        }
                      />
                    </Field>
                    <Field orientation="horizontal" className="rounded-lg border border-border bg-muted/35 px-3 py-2">
                      <Checkbox
                        checked={item.is_active}
                        onCheckedChange={() =>
                          setWorkspace((current) =>
                            current
                              ? {
                                  ...current,
                                  items: current.items.map((entry) => (entry.id === item.id ? { ...entry, is_active: !entry.is_active } : entry)),
                                }
                              : current,
                          )
                        }
                      />
                      <FieldContent>
                        <FieldTitle>Активен</FieldTitle>
                      </FieldContent>
                    </Field>
                  </FieldGroup>
                  {item.item_kind === "link" ? (
                    <Field>
                      <FieldLabel>Ссылка</FieldLabel>
                      <Input
                        value={item.external_url}
                        onChange={(event) =>
                          setWorkspace((current) =>
                            current
                              ? {
                                  ...current,
                                  items: current.items.map((entry) => (entry.id === item.id ? { ...entry, external_url: event.target.value } : entry)),
                                }
                              : current,
                          )
                        }
                      />
                    </Field>
                  ) : (
                    <div className="rounded-lg border border-border bg-muted/35 px-3 py-2 text-sm text-muted-foreground">
                      {item.original_filename || "Файл не указан"} · {formatFileSize(item.file_size)}
                    </div>
                  )}
                  <Field>
                    <FieldLabel>Описание</FieldLabel>
                    <Textarea
                      value={item.description}
                      onChange={(event) =>
                        setWorkspace((current) =>
                          current
                            ? {
                                ...current,
                                items: current.items.map((entry) => (entry.id === item.id ? { ...entry, description: event.target.value } : entry)),
                              }
                            : current,
                        )
                      }
                      rows={3}
                    />
                  </Field>
                </div>

                <div className="grid gap-2 rounded-xl border border-border bg-muted/20 p-3 text-sm text-muted-foreground">
                  <div>
                    <div className="font-medium text-foreground">{item.item_kind_label}</div>
                    <div className="mt-1">{item.item_kind === "file" ? item.original_filename || "—" : item.external_url || "—"}</div>
                  </div>
                  <div>Создан: {item.created_at_label}</div>
                  <div>Обновлен: {item.updated_at_label}</div>
                </div>

                <div className="flex flex-wrap gap-2 xl:flex-col xl:items-stretch">
                  <Button
                    variant="secondary"
                    onClick={() =>
                      refreshFromApi(
                        requestJson<Workspace>(`/api/documents/${item.id}`, {
                          method: "POST",
                          body: JSON.stringify(item),
                        }),
                        "Документ сохранен",
                      )
                    }
                  >
                    <Save data-icon="inline-start" />
                    Сохранить
                  </Button>
                  {item.item_kind === "file" && item.download_url ? (
                    <Button render={<a href={item.download_url} />} variant="outline">
                      <Download data-icon="inline-start" />
                      Скачать
                    </Button>
                  ) : item.external_url ? (
                    <Button render={<a href={item.external_url} target="_blank" rel="noreferrer" />} variant="outline">
                      <Link2 data-icon="inline-start" />
                      Открыть
                    </Button>
                  ) : null}
                  <ConfirmAction
                    title="Удалить документ?"
                    description={`Документ «${item.title || "Без названия"}» будет удалён из библиотеки.`}
                    onConfirm={() =>
                      refreshFromApi(requestJson<Workspace>(`/api/documents/${item.id}`, { method: "DELETE" }), "Документ удален")
                    }
                  >
                    <Button variant="outline">
                      <Trash2 data-icon="inline-start" />
                      Удалить
                    </Button>
                  </ConfirmAction>
                </div>
              </div>
            ))
          ) : (
            <div className="rounded-xl border border-dashed border-border bg-muted/20 p-8 text-sm text-muted-foreground">
              Библиотека пока пустая.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
