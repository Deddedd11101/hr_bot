import { useEffect, useState } from "react";
import { PageHeader } from "@/components/ui/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CatalogEditor } from "./catalog";
import { CatalogImport } from "./import";
import { Matrix } from "./matrix";
import { LoadingError } from "./components";
import { errorMessage, request } from "./data";
import type { EntityKind, Workspace } from "./types";

export function GradesPage() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [error, setError] = useState("");
  const [attempt, retry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    request<Workspace>("/api/grades/workspace", "GET", undefined, controller.signal).then(setWorkspace).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)); });
    return () => controller.abort();
  }, [attempt]);
  return <><PageHeader title="Грейды" /><div className="admin-page-stack min-w-0">
    {!workspace ? <LoadingError loading={!error} error={error} retry={() => retry(n => n + 1)} /> :
      <Tabs defaultValue="matrix" className="admin-page-surface min-w-0 flex-col p-4">
        <TabsList variant="line" className="max-w-full flex-wrap h-auto!" aria-label="Настройки грейдов">
          {[['matrix', 'Матрица'], ['grades', 'Грейды'], ['specializations', 'Специализации'], ['categories', 'Категории'], ['skills', 'Навыки'], ['import', 'Импорт']].map(([key, label]) => <TabsTrigger key={key} value={key}>{label}</TabsTrigger>)}
        </TabsList>
        <TabsContent value="matrix" keepMounted className="pt-4 min-w-0"><Matrix workspace={workspace} onSaved={setWorkspace} /></TabsContent>
        {(["grades", "specializations", "categories", "skills"] as EntityKind[]).map(kind => <TabsContent key={kind} value={kind} keepMounted className="pt-4 min-w-0"><CatalogEditor kind={kind} workspace={workspace} onSaved={setWorkspace} /></TabsContent>)}
        <TabsContent value="import" keepMounted className="pt-4 min-w-0"><CatalogImport workspace={workspace} onSaved={setWorkspace} /></TabsContent>
      </Tabs>}
  </div></>;
}
