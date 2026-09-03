import React from "react";
import { CalendarClock, Play } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
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
import { ScrollArea } from "@/components/ui/scroll-area";

import {
  defaultTargets,
  requestJson,
  TargetPicker,
  targetPayload,
  type Preview,
  type TargetState,
  type TargetingWorkspace,
} from "./targeting";

/**
 * Диалог массовой рассылки сценария или опроса.
 *
 * Открывается из шапки детали записи: рассылка — действие над тем, что
 * оператор уже открыл и видит. Раньше для неё нужно было уйти на страницу
 * массовых действий и заново найти запись в селекте — без вопросов
 * перед глазами.
 *
 * Контракт безопасности прежний: немедленный запуск заблокирован, пока
 * предпросмотр не показал число получателей больше нуля, и требует
 * подтверждения через ConfirmAction. Счётчик считает только фильтры
 * аудитории — собственная аудитория записи вычитается уже при отправке,
 * поэтому реально уйти может меньше.
 */
export function BroadcastDialog(props: {
  open: boolean;
  flowKey: string;
  itemTitle: string;
  kind: "scenario" | "survey";
  onOpenChange: (open: boolean) => void;
}) {
  const { open, flowKey, itemTitle, kind, onOpenChange } = props;
  const apiBase = kind === "survey" ? "/api/bulk-actions/surveys" : "/api/bulk-actions/scenarios";
  const itemLabelGenitive = kind === "survey" ? "опроса" : "сценария";

  const [workspace, setWorkspace] = React.useState<TargetingWorkspace | null>(null);
  const [targets, setTargets] = React.useState<TargetState>(defaultTargets);
  const [preview, setPreview] = React.useState<Preview | null>(null);
  const [requestedAt, setRequestedAt] = React.useState("");
  const [state, setState] = React.useState({ working: false, message: "", error: false });

  /*
   * Опции аудитории грузятся при каждом открытии, а не один раз: список
   * сотрудников и этапов меняется, а диалог живёт столько же, сколько
   * страница детали.
   */
  React.useEffect(() => {
    if (!open) return;
    setTargets(defaultTargets);
    setPreview(null);
    setRequestedAt("");
    setState({ working: false, message: "", error: false });
    requestJson<TargetingWorkspace>("/api/bulk-actions/workspace")
      .then(setWorkspace)
      .catch((loadError: Error) => {
        setState({ working: false, message: loadError.message || "Не удалось загрузить аудиторию", error: true });
      });
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
      setState({ working: false, message: successMessage, error: false });
    } catch (mutationError) {
      setState({
        working: false,
        message: mutationError instanceof Error ? mutationError.message : "Операция не выполнена",
        error: true,
      });
    }
  };

  // null означает «число получателей неизвестно», а не «любое»: без построенного
  // предпросмотра немедленный запуск остаётся недоступен.
  const canRunImmediate = preview !== null && preview.recipient_count > 0 && !state.working;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {/*
        sm:max-w-[640px] обязателен: базовый DialogContent несёт sm:max-w-sm,
        и без переопределения диалог сжимался до 384px — подписи чекбоксов
        аудитории ломались посреди слова.
      */}
      <DialogContent className="flex h-[min(760px,calc(100vh-40px))] w-[min(640px,calc(100vw-32px))] flex-col gap-0 overflow-hidden p-0 sm:max-w-[640px]">
        <DialogHeader className="shrink-0 border-b border-border px-5 py-4">
          <DialogTitle>Рассылка {itemLabelGenitive}</DialogTitle>
          <DialogDescription>{itemTitle || "Загружаю данные"}</DialogDescription>
        </DialogHeader>
        {!workspace ? (
          <div className="px-5 py-8 text-sm font-medium text-muted-foreground">
            {state.error ? state.message : "Загружаю аудиторию…"}
          </div>
        ) : (
          <>
            <ScrollArea className="min-h-0 flex-1 rounded-none">
              <div className="grid gap-4 px-5 py-4">
                <TargetPicker workspace={workspace} targets={targets} onChange={updateTargets} />
                {preview ? (
                  <Alert className="border-primary/30 bg-primary/5">
                    <AlertTitle>{preview.recipient_count} получателей</AlertTitle>
                    <AlertDescription>
                      {preview.recipient_scope}. Аудитория самой записи учитывается при отправке, поэтому реально
                      уйти может меньше.
                    </AlertDescription>
                  </Alert>
                ) : (
                  <Alert className="border-warning/40 bg-warning/10">
                    <AlertTitle>Число получателей неизвестно</AlertTitle>
                    <AlertDescription>
                      Предпросмотр не построен, поэтому немедленный запуск недоступен. Выберите аудиторию заново.
                    </AlertDescription>
                  </Alert>
                )}
                <label className="grid min-w-0 gap-2.5">
                  <span className="text-sm font-semibold text-foreground/75">Дата и время для расписания</span>
                  <DateTimePicker value={requestedAt} onValueChange={setRequestedAt} />
                </label>
                {state.message ? (
                  <p className={`text-sm ${state.error ? "text-destructive" : "text-muted-foreground"}`}>
                    {state.message}
                  </p>
                ) : null}
              </div>
            </ScrollArea>
            <DialogFooter className="!m-0 shrink-0 border-t border-border px-5 py-4">
              <Button variant="secondary" onClick={() => onOpenChange(false)}>
                Закрыть
              </Button>
              <Button
                variant="secondary"
                disabled={!requestedAt || state.working}
                onClick={() =>
                  runMutation(
                    `${apiBase}/schedule`,
                    { ...targetPayload(targets), flow_key: flowKey, requested_at: requestedAt },
                    "Рассылка запланирована",
                  )
                }
              >
                <CalendarClock data-icon="inline-start" />
                Запланировать
              </Button>
              <ConfirmAction
                title={`Запустить ${kind === "survey" ? "опрос" : "сценарий"} сейчас?`}
                description={`Получателей: ${preview?.recipient_count ?? 0}${
                  preview?.recipient_scope ? ` — ${preview.recipient_scope}` : ""
                }. Запуск немедленный, отменить его нельзя.`}
                actionLabel="Запустить"
                onConfirm={() =>
                  runMutation(
                    `${apiBase}/launch`,
                    { ...targetPayload(targets), flow_key: flowKey, confirmed: true },
                    "Рассылка запущена",
                  )
                }
              >
                <Button disabled={!canRunImmediate}>
                  <Play data-icon="inline-start" />
                  Сейчас
                </Button>
              </ConfirmAction>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
