import * as React from "react";
import { Code2, Eye, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

export type PlaygroundTab = {
  /** Стабильный идентификатор варианта. */
  id: string;
  /** Подпись на табе. */
  label: string;
  /** Одна строка о том, что показывает вариант. */
  caption?: string;
  /** Живой пример. */
  render: () => React.ReactNode;
  /** Исходник примера. Без него вкладка «Код» для этого варианта скрыта. */
  code?: string;
};

/**
 * Плейграунд записи каталога.
 *
 * Доказывает работу элемента, а не служит скриншотом: варианты
 * переключаются табами, у каждого своя сцена и свой исходник.
 * Переключатель Preview/Code и сброс живут в одной панели с табами,
 * чтобы страницы всех записей читались одинаково.
 *
 * Сетевых запросов и необратимых операций здесь быть не должно —
 * только локальные детерминированные данные.
 */
export function Playground({
  tabs,
  className,
}: {
  tabs: PlaygroundTab[];
  className?: string;
}) {
  const [activeTab, setActiveTab] = React.useState(tabs[0]?.id ?? "");
  const [mode, setMode] = React.useState<"preview" | "code">("preview");
  /** Меняется при сбросе — размонтирует сцену и возвращает исходное состояние. */
  const [resetKey, setResetKey] = React.useState(0);

  if (!tabs.length) return null;

  const current = tabs.find((tab) => tab.id === activeTab) ?? tabs[0];
  const hasCode = Boolean(current.code);

  return (
    <Card
      /*
       * Витрина: внутри сцены стоят те самые компоненты, которые она
       * показывает, и среди них бывают карточки. Вложенность здесь приём,
       * а не дефект, поэтому она объявлена явно — проверка «нет карточки
       * в карточке» пропускает всё под этим признаком.
       */
      data-showcase=""
      className={cn("overflow-hidden border border-border/80 bg-card shadow-none ring-0", className)}
    >
      <Tabs
        value={current.id}
        onValueChange={(next) => {
          setActiveTab(String(next ?? tabs[0].id));
          setMode("preview");
        }}
        // Направление задаётся явно: вариант data-horizontal из кита
        // опирается на другой атрибут и здесь не срабатывает.
        className="flex w-full min-w-0 flex-col gap-0"
      >
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/70 px-3 py-2.5">
          {tabs.length > 1 ? (
            <TabsList variant="line" className="h-8">
              {tabs.map((tab) => (
                <TabsTrigger key={tab.id} value={tab.id} className="text-sm">
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>
          ) : (
            <div className="text-sm font-medium text-muted-foreground">{current.label}</div>
          )}

          <div className="flex items-center gap-1">
            <Button
              type="button"
              size="sm"
              variant={mode === "preview" ? "secondary" : "ghost"}
              aria-pressed={mode === "preview"}
              onClick={() => setMode("preview")}
            >
              <Eye data-icon="inline-start" />
              Вид
            </Button>
            {hasCode ? (
              <Button
                type="button"
                size="sm"
                variant={mode === "code" ? "secondary" : "ghost"}
                aria-pressed={mode === "code"}
                onClick={() => setMode("code")}
              >
                <Code2 data-icon="inline-start" />
                Код
              </Button>
            ) : null}
            <Separator orientation="vertical" className="mx-1 h-5" />
            <Button
              type="button"
              size="sm"
              variant="ghost"
              aria-label="Сбросить пример к исходному состоянию"
              onClick={() => {
                setResetKey((value) => value + 1);
                setMode("preview");
              }}
            >
              <RotateCcw />
            </Button>
          </div>
        </div>

        {tabs.map((tab) => (
          <TabsContent key={tab.id} value={tab.id} className="m-0">
            {tab.caption ? (
              <div className="border-b border-border/70 bg-muted/30 px-4 py-2 text-sm leading-6 text-muted-foreground">
                {tab.caption}
              </div>
            ) : null}
            <CardContent className="p-0">
              {mode === "code" && tab.code ? (
                <pre className="overflow-x-auto bg-muted/20 p-4 text-xs leading-5 text-foreground/85">
                  <code>{tab.code}</code>
                </pre>
              ) : (
                <div key={resetKey} className="flex min-h-[8rem] flex-wrap items-center gap-3 p-5">
                  {tab.render()}
                </div>
              )}
            </CardContent>
          </TabsContent>
        ))}
      </Tabs>
    </Card>
  );
}
