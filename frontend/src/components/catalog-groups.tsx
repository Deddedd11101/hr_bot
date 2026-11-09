import * as React from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  useDraggable,
  useDroppable,
} from "@dnd-kit/core";
import {
  Folder,
  FolderInput,
  Plus,
  Pencil,
  Trash2,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";

type Group = { id: number; name: string; revision: number };
type Data = {
  groups: Group[];
  memberships: Record<string, number>;
  created_group_id?: number;
};
type Scope = "people" | "scenarios";
type Context = {
  data: Data;
  selected: string;
  setSelected: (value: string) => void;
  ready: boolean;
  busy: boolean;
  error: string;
  filter: <T extends { id: number }>(items: T[]) => T[];
  startDrag: (event: React.DragEvent, id: number) => void;
  drop: (event: React.DragEvent, group: string) => void;
  acceptsDrag: (event: React.DragEvent) => boolean;
  openCreate: () => void;
  openRename: () => void;
  openDelete: () => void;
  openMove: (id: number) => void;
  reload: () => void;
};
const Groups = React.createContext<Context | null>(null);
const mime = "application/x-hrbot-catalog-item";
export function useCatalogGroups() {
  const value = React.useContext(Groups);
  if (!value) throw new Error("CatalogGroupsProvider missing");
  return value;
}

export function CatalogGroupsProvider({
  scope,
  children,
}: {
  scope: Scope;
  children: React.ReactNode;
}) {
  const [data, setData] = React.useState<Data>({ groups: [], memberships: {} });
  const [selected, setSelected] = React.useState("all");
  const [ready, setReady] = React.useState(false);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  );
  const pointerPayload = React.useRef<{
    id: number;
    expected: number | null;
  } | null>(null);
  const [dragLabel, setDragLabel] = React.useState<string | null>(null);
  const generation = React.useRef(0);
  const inFlight = React.useRef(false);
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [edit, setEdit] = React.useState<"create" | "rename" | "delete" | null>(
    null,
  );
  const [name, setName] = React.useState("");
  const [moving, setMoving] = React.useState<number | null>(null);
  const [target, setTarget] = React.useState("none");
  const [revision, reload] = React.useReducer((n) => n + 1, 0);
  const group = data.groups.find((g) => String(g.id) === selected);
  const accept = (next: Data) => {
    setData(next);
    setReady(true);
    setError("");
  };
  React.useEffect(() => {
    const controller = new AbortController();
    const ticket = ++generation.current;
    fetch(`/api/catalog-groups?scope=${scope}`, { signal: controller.signal })
      .then(async (r) => {
        if (!r.ok) throw new Error("Не удалось загрузить группы");
        const next = await r.json();
        if (!controller.signal.aborted && ticket === generation.current)
          accept(next);
      })
      .catch((e) => {
        if (!controller.signal.aborted)
          setError(e instanceof Error ? e.message : "Ошибка групп");
      });
    return () => controller.abort();
  }, [scope, revision]);
  React.useEffect(() => {
    if (ready && selected !== "all" && selected !== "none" && !group)
      setSelected("all");
  }, [ready, selected, group]);
  React.useEffect(() => {
    const refresh = () => {
      if (!busy && !edit && moving === null) reload();
    };
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [busy, edit, moving]);
  async function send(url: string, method: string, body?: object) {
    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    const next = await response.json();
    if (!response.ok)
      throw new Error(
        typeof next.detail === "string"
          ? next.detail
          : "Не удалось сохранить группу",
      );
    generation.current += 1;
    accept(next);
    return next as Data;
  }
  async function move(
    id: number,
    destination: string,
    expected = data.memberships[String(id)] || null,
  ) {
    if (inFlight.current || !ready) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      await send("/api/catalog-group-membership", "PUT", {
        scope,
        object_id: id,
        group_id: destination === "none" ? null : Number(destination),
        expected_group_id: expected,
      });
      setMoving(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось переместить");
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  async function save() {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      if (edit === "delete" && group) {
        await send(
          `/api/catalog-groups/${group.id}?scope=${scope}&expected_revision=${group.revision}`,
          "DELETE",
        );
        setSelected("none");
      } else if (edit === "rename" && group) {
        await send(`/api/catalog-groups/${group.id}`, "PATCH", {
          scope,
          name,
          expected_revision: group.revision,
        });
      } else if (edit === "create") {
        const next = await send("/api/catalog-groups", "POST", { scope, name });
        if (next.created_group_id) setSelected(String(next.created_group_id));
      }
      setEdit(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения");
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  const context: Context = {
    data,
    selected,
    setSelected,
    ready,
    busy,
    error,
    reload,
    filter: (items) =>
      items.filter(
        (item) =>
          selected === "all" ||
          (selected === "none"
            ? !data.memberships[String(item.id)]
            : String(data.memberships[String(item.id)]) === selected),
      ),
    startDrag: (event, id) => {
      event.dataTransfer.setData(
        mime,
        JSON.stringify({
          scope,
          id,
          expected: data.memberships[String(id)] || null,
        }),
      );
      event.dataTransfer.effectAllowed = "move";
    },
    acceptsDrag: (event) => event.dataTransfer.types.includes(mime),
    drop: (event, destination) => {
      event.preventDefault();
      event.stopPropagation();
      try {
        const source = JSON.parse(event.dataTransfer.getData(mime));
        if (source.scope === scope && Number.isInteger(source.id))
          void move(source.id, destination, source.expected);
      } catch {
        setError("Не удалось прочитать перетаскиваемую запись");
      }
    },
    openCreate: () => {
      setName("");
      setEdit("create");
      setError("");
    },
    openRename: () => {
      setName(group?.name || "");
      setEdit("rename");
      setError("");
    },
    openDelete: () => {
      setEdit("delete");
      setError("");
    },
    openMove: (id) => {
      setMoving(id);
      setTarget(String(data.memberships[String(id)] || "none"));
      setError("");
    },
  };
  return (
    <DndContext
      sensors={sensors}
      accessibility={{
        screenReaderInstructions: {
          draggable:
            "Нажмите кнопку, чтобы выбрать группу. Перетаскивание доступно мышью.",
        },
        announcements: {
          onDragStart: ({ active }) =>
            `Перемещение: ${active.data.current?.name || "запись"}`,
          onDragOver: ({ over }) =>
            over
              ? "Выбрана группа для переноса"
              : "Выберите группу для переноса",
          onDragEnd: ({ over }) =>
            over ? "Перенос в группу запрошен" : "Перенос отменён",
          onDragCancel: () => "Перенос отменён",
        },
      }}
      onDragStart={(event) => {
        const source = event.active.data.current;
        if (source) {
          pointerPayload.current = {
            id: source.objectId,
            expected: data.memberships[String(source.objectId)] || null,
          };
          setDragLabel(source.name);
        }
      }}
      onDragEnd={(event) => {
        const source = pointerPayload.current;
        pointerPayload.current = null;
        setDragLabel(null);
        const destination = event.over?.data.current?.destination;
        if (source && typeof destination === "string")
          void move(source.id, destination, source.expected);
      }}
      onDragCancel={() => {
        pointerPayload.current = null;
        setDragLabel(null);
      }}
    >
      <Groups.Provider value={context}>
        {children}
        <Dialog
          open={edit !== null}
          onOpenChange={(open) => {
            if (!open && !busy) setEdit(null);
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {edit === "create"
                  ? "Новая группа"
                  : edit === "rename"
                    ? "Переименовать группу"
                    : "Удалить группу?"}
              </DialogTitle>
              <DialogDescription>
                {edit === "delete"
                  ? `Группа «${group?.name}» будет удалена. Записи останутся в «Без группы»; сценарии и сотрудники не удаляются.`
                  : "Группа общая для команды HR."}
              </DialogDescription>
            </DialogHeader>
            {edit !== "delete" && (
              <Input
                aria-label="Название группы"
                autoFocus
                maxLength={80}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            )}
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => setEdit(null)}
              >
                Отмена
              </Button>
              <Button
                variant={edit === "delete" ? "destructive" : "default"}
                disabled={busy || (edit !== "delete" && !name.trim())}
                onClick={() => void save()}
              >
                {busy
                  ? "Сохранение..."
                  : edit === "delete"
                    ? "Удалить группу"
                    : "Сохранить"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
        <Dialog
          open={moving !== null}
          onOpenChange={(open) => {
            if (!open && !busy) setMoving(null);
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Переместить в группу</DialogTitle>
            </DialogHeader>
            <Select
              value={target}
              onValueChange={(v) => setTarget(v || "none")}
            >
              <SelectTrigger className="w-full" aria-label="Группа записи">
                <SelectValue>
                  {target === "none"
                    ? "Без группы"
                    : data.groups.find((g) => String(g.id) === target)?.name ||
                      "Выберите группу"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Без группы</SelectItem>
                {data.groups.map((g) => (
                  <SelectItem key={g.id} value={String(g.id)}>
                    {g.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => setMoving(null)}
              >
                Отмена
              </Button>
              <Button
                disabled={busy || moving === null}
                onClick={() => {
                  if (moving !== null) void move(moving, target);
                }}
              >
                Переместить
              </Button>
            </div>
          </DialogContent>
        </Dialog>
        <DragOverlay>
          {dragLabel && (
            <div className="max-w-xs rounded-lg border border-border bg-popover px-3 py-2 text-sm text-popover-foreground">
              {dragLabel}
            </div>
          )}
        </DragOverlay>
      </Groups.Provider>
    </DndContext>
  );
}

function FolderTarget({
  folder,
  count,
}: {
  folder: { id: string; name: string };
  count: number;
}) {
  const c = useCatalogGroups();
  const [nativeOver, setNativeOver] = React.useState(false);
  const { isOver, setNodeRef } = useDroppable({
    id: `folder:${folder.id}`,
    disabled: folder.id === "all" || !c.ready || c.busy,
    data: { destination: folder.id },
  });
  return (
    <Button
      ref={setNodeRef}
      title={folder.name}
      variant={
        c.selected === folder.id || isOver || nativeOver
          ? "secondary"
          : "outline"
      }
      size="sm"
      disabled={c.busy || !c.ready}
      aria-pressed={c.selected === folder.id}
      onClick={() => c.setSelected(folder.id)}
      onDragOver={(event) => {
        if (folder.id !== "all" && c.acceptsDrag(event)) {
          event.preventDefault();
          setNativeOver(true);
        }
      }}
      onDragLeave={() => setNativeOver(false)}
      onDrop={(event) => {
        setNativeOver(false);
        if (folder.id !== "all") c.drop(event, folder.id);
      }}
    >
      <Folder className="size-4" />
      <span className="max-w-48 truncate">{folder.name}</span>
      <span className="text-muted-foreground">{count}</span>
    </Button>
  );
}

export function CatalogGroupToolbar({ ids }: { ids: number[] }) {
  const c = useCatalogGroups();
  const folders = [
    { id: "all", name: "Все" },
    { id: "none", name: "Без группы" },
    ...c.data.groups.map((g) => ({ id: String(g.id), name: g.name })),
  ];
  const count = (id: string) =>
    ids.filter(
      (item) =>
        id === "all" ||
        (id === "none"
          ? !c.data.memberships[String(item)]
          : String(c.data.memberships[String(item)]) === id),
    ).length;
  return (
    <div className="min-w-0 space-y-2">
      <nav
        aria-label="Группы каталога"
        className="flex flex-wrap items-center gap-2"
      >
        {folders.map((f) => (
          <FolderTarget key={f.id} folder={f} count={count(f.id)} />
        ))}
        <Button
          size="sm"
          variant="ghost"
          disabled={c.busy || !c.ready}
          onClick={c.openCreate}
        >
          <Plus /> Группа
        </Button>
        {c.selected !== "all" && c.selected !== "none" && (
          <>
            <Button
              size="icon-sm"
              variant="ghost"
              title="Переименовать группу"
              aria-label="Переименовать группу"
              onClick={c.openRename}
            >
              <Pencil />
            </Button>
            <Button
              size="icon-sm"
              variant="ghost"
              title="Удалить группу"
              aria-label="Удалить группу"
              onClick={c.openDelete}
            >
              <Trash2 />
            </Button>
          </>
        )}
        <Button
          size="icon-sm"
          variant="ghost"
          title="Обновить группы"
          aria-label="Обновить группы"
          onClick={c.reload}
        >
          <RefreshCw />
        </Button>
      </nav>
      {!c.ready && !c.error && (
        <p role="status" className="text-xs text-muted-foreground">
          Загрузка групп...
        </p>
      )}
      {c.error && (
        <p role="alert" className="text-sm text-destructive">
          {c.error}
        </p>
      )}
    </div>
  );
}

export function GroupMoveButton({
  objectId,
  name = `Запись №${objectId}`,
}: {
  objectId: number;
  name?: string;
}) {
  const c = useCatalogGroups();
  const { attributes, listeners, setNodeRef } = useDraggable({
    id: `object:${objectId}`,
    data: { objectId, name },
    disabled: !c.ready || c.busy,
  });
  return (
    <Button
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      className="touch-none"
      type="button"
      size="icon-sm"
      variant="ghost"
      title="Переместить в группу"
      aria-label={`Переместить запись №${objectId} в группу`}
      disabled={!c.ready || c.busy}
      draggable={false}
      onDragStart={(event) => {
        event.preventDefault();
        event.stopPropagation();
      }}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        c.openMove(objectId);
      }}
    >
      <FolderInput />
    </Button>
  );
}
