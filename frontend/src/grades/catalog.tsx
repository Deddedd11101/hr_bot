import { useState } from "react";
import { Archive, Pencil, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ConfirmAction } from "@/components/ui/confirm-action";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Choice, Feedback, useAction, useUnsaved } from "./components";
import { request } from "./data";
import type { CatalogItem, EntityKind, Workspace } from "./types";

const titles: Record<EntityKind, string> = { grades: "Грейды", specializations: "Специализации", categories: "Категории", skills: "Навыки" };

export function CatalogEditor({ kind, workspace, onSaved }: { kind: EntityKind; workspace: Workspace; onSaved: (w: Workspace) => void }) {
  const action = useAction();
  const [editing, setEditing] = useState<CatalogItem | null | undefined>(undefined);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState(false);
  useUnsaved(dirty);
  function edit(item: CatalogItem | null) {
    const initial: Record<string, string> = { name: "", slug: "", rank: "1", sort_order: "0", description: "", category_id: String(workspace.categories.find(c => c.active)?.id || ""), position_slug: "none" };
    if (item) Object.entries(item).forEach(([k, v]) => { initial[k] = v == null ? (k === "position_slug" ? "none" : "") : String(v); });
    setFields(initial); setEditing(item); setDirty(false); action.setError("");
  }
  function change(key: string, value: string) { setFields(f => ({ ...f, [key]: value })); setDirty(true); }
  async function save() {
    const body: Record<string, unknown> = { name: fields.name.trim(), sort_order: Number(fields.sort_order) };
    if (kind === "grades" || kind === "specializations") body.slug = fields.slug.trim();
    if (kind === "grades") body.rank = Number(fields.rank);
    if (kind === "specializations") { body.description = fields.description; body.position_slug = fields.position_slug === "none" ? null : fields.position_slug; }
    if (kind === "skills") body.category_id = Number(fields.category_id);
    onSaved(await request<Workspace>(`/api/grades/${kind}${editing ? `/${editing.id}` : ""}`, editing ? "PUT" : "POST", body));
    setDirty(false); setEditing(undefined);
  }
  return <section className="space-y-4">
    <div className="flex items-center justify-between gap-3"><h2 className="text-base font-semibold">{titles[kind]}</h2><Button size="sm" onClick={() => edit(null)} disabled={action.busy}><Plus />Добавить</Button></div>
    {editing === undefined && <Feedback error={action.error} message={action.message} />}
    <Table><TableHeader><TableRow><TableHead>Название</TableHead><TableHead>{kind === "grades" ? "Ранг" : kind === "specializations" ? "Должность" : kind === "skills" ? "Категория" : "Порядок"}</TableHead><TableHead>Статус</TableHead><TableHead><span className="sr-only">Действия</span></TableHead></TableRow></TableHeader>
      <TableBody>{workspace[kind].map(item => <TableRow key={item.id} className="group">
        <TableCell className="whitespace-normal break-words">{item.name}</TableCell>
        <TableCell>{kind === "grades" ? workspace.grades.find(g => g.id === item.id)?.rank : kind === "skills" ? workspace.categories.find(c => c.id === workspace.skills.find(s => s.id === item.id)?.category_id)?.name : kind === "specializations" ? workspace.specializations.find(s => s.id === item.id)?.position_slug || "Не связана" : item.sort_order}</TableCell>
        <TableCell><Badge variant="outline">{item.active ? "Активен" : "Архив"}</Badge></TableCell>
        <TableCell><div className="flex justify-end gap-1 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 [@media(hover:none)]:opacity-100">
          <Button variant="ghost" size="icon-sm" title={`Изменить: ${item.name}`} aria-label={`Изменить: ${item.name}`} onClick={() => edit(item)} disabled={action.busy}><Pencil /></Button>
          {item.active ? <ConfirmAction title={`Архивировать «${item.name}»?`} description="Запись станет неактивной. Завершённые оценки сохранят свой снимок каталога." actionLabel="Архивировать" onConfirm={() => void action.run(async () => onSaved(await request<Workspace>(`/api/grades/${kind}/${item.id}`, "DELETE")), "Запись архивирована")}>
            <Button variant="ghost" size="icon-sm" title={`Архивировать: ${item.name}`} aria-label={`Архивировать: ${item.name}`} disabled={action.busy}><Archive /></Button>
          </ConfirmAction> : <Button variant="ghost" size="sm" disabled={action.busy} onClick={() => void action.run(async () => onSaved(await request<Workspace>(`/api/grades/${kind}/${item.id}`, "PUT", { active: true })), "Запись восстановлена")}>Восстановить</Button>}
        </div></TableCell>
      </TableRow>)}</TableBody></Table>
    {!workspace[kind].length && <p className="p-6 text-center text-muted-foreground">Записей пока нет</p>}
    <Dialog open={editing !== undefined} onOpenChange={open => { if (!open && !action.busy && !dirty) setEditing(undefined); }}>
      <DialogContent><DialogHeader><DialogTitle>{editing ? "Изменить запись" : "Новая запись"}</DialogTitle></DialogHeader>
        <form onSubmit={e => { e.preventDefault(); void action.run(save); }} className="space-y-4">
          <FieldGroup>
            <Field><FieldLabel htmlFor={`${kind}-name`}>Название</FieldLabel><Input id={`${kind}-name`} required value={fields.name || ""} onChange={e => change("name", e.target.value)} disabled={action.busy} /></Field>
            {(kind === "grades" || kind === "specializations") && <Field><FieldLabel htmlFor={`${kind}-slug`}>Код</FieldLabel><Input id={`${kind}-slug`} required pattern="[a-z0-9_-]+" value={fields.slug || ""} onChange={e => change("slug", e.target.value)} disabled={action.busy} /></Field>}
            {kind === "grades" && <Field><FieldLabel htmlFor="grade-rank">Ранг</FieldLabel><Input id="grade-rank" type="number" required min={1} step={1} value={fields.rank || ""} onChange={e => change("rank", e.target.value)} disabled={action.busy} /></Field>}
            {kind === "specializations" && <><Field><FieldLabel htmlFor="spec-description">Описание</FieldLabel><Input id="spec-description" value={fields.description || ""} onChange={e => change("description", e.target.value)} disabled={action.busy} /></Field>
              <Choice label="Должность" value={fields.position_slug || "none"} onChange={v => change("position_slug", v)} disabled={action.busy} options={[{ value: "none", label: "Без привязки" }, ...workspace.positions.map(p => ({ value: p.slug, label: p.name || p.title || p.label || p.slug }))]} /></>}
            {kind === "skills" && <Choice label="Категория" value={fields.category_id || ""} onChange={v => change("category_id", v)} disabled={action.busy} options={workspace.categories.filter(c => c.active).map(c => ({ value: String(c.id), label: c.name }))} />}
            <Field><FieldLabel htmlFor={`${kind}-sort`}>Порядок</FieldLabel><Input id={`${kind}-sort`} type="number" step={1} required value={fields.sort_order || "0"} onChange={e => change("sort_order", e.target.value)} disabled={action.busy} /></Field>
          </FieldGroup>
          <Feedback error={action.error} />
          <div className="flex justify-end gap-2">
            {dirty ? <ConfirmAction title="Отменить изменения?" description="Несохранённые изменения будут потеряны." actionLabel="Отменить изменения" onConfirm={() => { setDirty(false); setEditing(undefined); }}><Button type="button" variant="outline" disabled={action.busy}>Отмена</Button></ConfirmAction> : <Button type="button" variant="outline" disabled={action.busy} onClick={() => setEditing(undefined)}>Отмена</Button>}
            <Button type="submit" disabled={action.busy || !fields.name?.trim() || (kind === "skills" && !fields.category_id)}>{action.busy ? "Сохранение..." : "Сохранить"}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  </section>;
}
