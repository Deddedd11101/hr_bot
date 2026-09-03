import React from "react";
import { AlertTriangle, CalendarClock, Plus, Send, Trash2 } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmAction } from "@/components/ui/confirm-action";
import { DateTimePicker } from "@/components/ui/date-picker";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { RecordCard } from "@/components/ui/record-card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { ПРОЯВЛЕНИЕ } from "@/lib/reveal";

import {
  defaultTargets,
  requestJson,
  TargetPicker,
  targetPayload,
  type Preview,
  type TargetState,
  type TargetingWorkspace,
} from "@/mass-broadcast/targeting";

/**
 * Страница массовых сообщений.
 *
 * Устроена как каталог опросов: в шапке одно действие «Новое сообщение», ниже
 * карточками лежат уже созданные рассылки — запланированные и отправленные.
 * Сама отправка живёт в диалоге: текст, аудитория, живой счётчик получателей
 * и прежний контракт «сначала preview, затем confirmed=true».
 *
 * Записи здесь — журнал, а не черновики: сообщение нельзя открыть
 * и отредактировать, можно только снять запланированное до срока.
 */

type MessageAction = {
  id: number;
  message_text?: string;
  requested_at_label: string;
  processed_at_label: string;
  recipient_count: number;
  recipient_scope: string;
};

type Workspace = TargetingWorkspace & {
  document_tag_titles: string[];
  scheduled_message_actions: MessageAction[];
  manual_message_history: MessageAction[];
};

export type MessagesPageProps = {
  apiUrl: string;
};

function StatusAlert({ message, type }: { message: string; type: "success" | "error" }) {
  if (!message) return null;
  return (
    <Alert
      variant={type === "error" ? "destructive" : "default"}
      className={type === "success" ? "border-primary/30 bg-primary/5" : undefined}
    >
      <AlertTitle>{type === "success" ? "Готово" : "Ошибка"}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}

/**
 * Диалог новой рассылки: текст сообщения плюс общий блок аудитории.
 * Той же анатомии, что диалог рассылки сценария и опроса в детали записи.
 */
function ComposeDialog({
  open,
  workspace,
  onOpenChange,
  onDone,
}: {
  open: boolean;
  workspace: Workspace;
  onOpenChange: (open: boolean) => void;
  onDone: (message: string) => void;
}) {
  const [targets, setTargets] = React.useState<TargetState>(defaultTargets);
  const [preview, setPreview] = React.useState<Preview | null>(null);
  const [requestedAt, setRequestedAt] = React.useState("");
  const [messageText, setMessageText] = React.useState("");
  const [state, setState] = React.useState({ working: false, message: "", error: false });

  React.useEffect(() => {
    if (!open) return;
    setTargets(defaultTargets);
    setPreview(null);
    setRequestedAt("");
    setMessageText("");
    setState({ working: false, message: "", error: false });
    void buildPreview(defaultTargets);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const buildPreview = async (nextTargets: TargetState) => {
    try {
      const nextPreview = await requestJson<Preview>("/api/bulk-actions/preview", {
        method: "POST",
        body: JSON.stringify(targetPayload(nextTargets)),
      });
      setPreview(nextPreview);
    } catch (previewError) {
      setPreview(null);
      setState({
        working: false,
        message: previewError instanceof Error ? previewError.message : "Не удалось посчитать получателей",
        error: true,
      });
    }
  };

  const updateTargets = (nextTargets: TargetState) => {
    setTargets(nextTargets);
    void buildPreview(nextTargets);
  };

  const runMutation = async (path: string, body: Record<string, unknown>, successMessage: string) => {
    setState({ working: true, message: "", error: false });
    try {
      await requestJson(path, { method: "POST", body: JSON.stringify(body) });
      onOpenChange(false);
      onDone(successMessage);
    } catch (mutationError) {
      setState({
        working: false,
        message: mutationError instanceof Error ? mutationError.message : "Операция не выполнена",
        error: true,
      });
    }
  };

  // null означает «число получателей неизвестно», а не «любое»: немедленная
  // отправка недоступна, пока предпросмотр не построен.
  const canRunImmediate = preview !== null && preview.recipient_count > 0 && !state.working && messageText.trim().length > 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {/* sm:max-w-[640px] перебивает sm:max-w-sm базового DialogContent — без него диалог сжимался до 384px. */}
      <DialogContent className="flex h-[min(760px,calc(100vh-40px))] w-[min(640px,calc(100vw-32px))] flex-col gap-0 overflow-hidden p-0 sm:max-w-[640px]">
        <DialogHeader className="shrink-0 border-b border-border px-5 py-4">
          <DialogTitle>Новое сообщение</DialogTitle>
          <DialogDescription>Свободный текст группе людей в Telegram</DialogDescription>
        </DialogHeader>
        <ScrollArea className="min-h-0 flex-1 rounded-none">
          <div className="grid gap-4 px-5 py-4">
            <label className="grid min-w-0 gap-2.5">
              <span className="text-sm font-semibold text-foreground/75">Текст сообщения</span>
              <Textarea
                value={messageText}
                onChange={(event) => setMessageText(event.target.value)}
                rows={5}
                placeholder="Введите сообщение"
                autoComplete="off"
              />
            </label>
            <div className="flex flex-wrap gap-2">
              {["{name}", "{full_name}"]
                .concat(workspace.document_tag_titles.map((title) => `{doc:${title}}`))
                .map((token) => (
                  <Button
                    key={token}
                    type="button"
                    variant="secondary"
                    size="xs"
                    onClick={() => setMessageText((current) => `${current}${token}`)}
                  >
                    {token}
                  </Button>
                ))}
            </div>
            <TargetPicker workspace={workspace} targets={targets} onChange={updateTargets} />
            {preview ? (
              <Alert className="border-primary/30 bg-primary/5">
                <AlertTitle>{preview.recipient_count} получателей</AlertTitle>
                <AlertDescription>{preview.recipient_scope}</AlertDescription>
              </Alert>
            ) : (
              <Alert className="border-warning/40 bg-warning/10">
                <AlertTriangle />
                <AlertTitle>Число получателей неизвестно</AlertTitle>
                <AlertDescription>
                  Предпросмотр не построен, поэтому немедленная отправка недоступна. Выберите аудиторию заново.
                </AlertDescription>
              </Alert>
            )}
            <label className="grid min-w-0 gap-2.5">
              <span className="text-sm font-semibold text-foreground/75">Дата и время для расписания</span>
              <DateTimePicker value={requestedAt} onValueChange={setRequestedAt} />
            </label>
            {state.message ? (
              <p className={`text-sm ${state.error ? "text-destructive" : "text-muted-foreground"}`}>{state.message}</p>
            ) : null}
          </div>
        </ScrollArea>
        <DialogFooter className="!m-0 shrink-0 border-t border-border px-5 py-4">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Закрыть
          </Button>
          <Button
            variant="secondary"
            disabled={!requestedAt || !messageText.trim() || state.working}
            onClick={() =>
              runMutation(
                "/api/bulk-actions/messages/schedule",
                { ...targetPayload(targets), message_text: messageText, requested_at: requestedAt },
                "Сообщение запланировано",
              )
            }
          >
            <CalendarClock data-icon="inline-start" />
            Запланировать
          </Button>
          <ConfirmAction
            title="Отправить сообщение сейчас?"
            description={`Получателей: ${preview?.recipient_count ?? 0}${
              preview?.recipient_scope ? ` — ${preview.recipient_scope}` : ""
            }. Сообщение уйдёт в Telegram, отозвать его нельзя.`}
            actionLabel="Отправить"
            onConfirm={() =>
              runMutation(
                "/api/bulk-actions/messages/send",
                { ...targetPayload(targets), message_text: messageText, confirmed: true },
                "Сообщение отправлено",
              )
            }
          >
            <Button disabled={!canRunImmediate}>
              <Send data-icon="inline-start" />
              Сейчас
            </Button>
          </ConfirmAction>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Карточка рассылки. Не открывается: запись — журнал, а не черновик. */
function MessageCard({
  action,
  scheduled,
  onDelete,
}: {
  action: MessageAction;
  scheduled: boolean;
  onDelete?: (id: number) => void;
}) {
  const text = (action.message_text || "").trim() || "Сообщение";
  return (
    <RecordCard
      title={text}
      subtitle={action.recipient_scope}
      tags={[
        {
          label: scheduled ? `Запланировано на ${action.requested_at_label}` : `Отправлено ${action.processed_at_label}`,
          variant: scheduled ? "default" : "secondary",
          icon: scheduled ? <CalendarClock className="size-3.5" /> : <Send className="size-3.5" />,
        },
        { label: `${action.recipient_count} получ.`, variant: "outline" },
      ]}
      actions={
        scheduled && onDelete ? (
          <ConfirmAction
            title="Удалить запланированное сообщение?"
            description="Сообщение будет удалено из расписания. Уже выполненные отправки не затрагиваются."
            actionLabel="Удалить"
            onConfirm={() => onDelete(action.id)}
          >
            {/* Действие проявляется по наведению на карточку — как у остальных записей. */}
            <Button variant="outline" size="icon" aria-label={`Удалить: ${text}`} className={ПРОЯВЛЕНИЕ.card}>
              <Trash2 />
            </Button>
          </ConfirmAction>
        ) : undefined
      }
    />
  );
}

export function MessagesPage({ apiUrl }: MessagesPageProps) {
  const [workspace, setWorkspace] = React.useState<Workspace | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [message, setMessage] = React.useState("");
  const [error, setError] = React.useState("");
  const [composeOpen, setComposeOpen] = React.useState(false);

  const refresh = React.useCallback(() => {
    return requestJson<Workspace>(apiUrl)
      .then(setWorkspace)
      .catch((err) => setError(err instanceof Error ? err.message : "Не удалось загрузить сообщения"));
  }, [apiUrl]);

  React.useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  const deleteScheduled = async (id: number) => {
    setError("");
    setMessage("");
    try {
      await requestJson(`/api/bulk-actions/messages/${id}`, { method: "DELETE" });
      await refresh();
      setMessage("Запланированная отправка удалена");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить отправку");
    }
  };

  if (loading) {
    return (
      <Card className="admin-page-shell border border-border/80 bg-card shadow-none ring-0">
        <CardContent className="p-8 text-sm text-muted-foreground">Загружаю сообщения...</CardContent>
      </Card>
    );
  }

  if (!workspace) {
    return (
      <div className="admin-page-stack gap-4">
        <StatusAlert type="error" message={error || "Сообщения не загружены"} />
      </div>
    );
  }

  const scheduled = workspace.scheduled_message_actions;
  const sent = workspace.manual_message_history;
  const total = scheduled.length + sent.length;

  return (
    <>
      <PageHeader
        title="Сообщения"
        counter={total}
        actions={
          <Button size="sm" onClick={() => setComposeOpen(true)}>
            <Plus data-icon="inline-start" />
            Новое сообщение
          </Button>
        }
      />
      <ComposeDialog
        open={composeOpen}
        workspace={workspace}
        onOpenChange={setComposeOpen}
        onDone={(successMessage) => {
          setMessage(successMessage);
          setError("");
          void refresh();
        }}
      />
      <div className="admin-page-shell">
        <StatusAlert type="success" message={message} />
        <StatusAlert type="error" message={error} />
        {total === 0 ? (
          <Empty className="min-h-40 border border-dashed border-border bg-muted/20">
            <EmptyHeader>
              <EmptyTitle>Рассылок ещё не было</EmptyTitle>
              <EmptyDescription>Нажмите «Новое сообщение», чтобы написать первой группе людей.</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          /*
           * Одна сетка, той же формы, что каталог опросов. Запланированные
           * идут первыми: их ещё можно снять, и им нужна кнопка удаления;
           * отправленные — неизменяемая история.
           */
          <div className="grid grid-cols-[repeat(auto-fill,minmax(320px,1fr))] gap-3 pb-1">
            {scheduled.map((action) => (
              <MessageCard key={`scheduled-${action.id}`} action={action} scheduled onDelete={deleteScheduled} />
            ))}
            {sent.map((action) => (
              <MessageCard key={`sent-${action.id}`} action={action} scheduled={false} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
