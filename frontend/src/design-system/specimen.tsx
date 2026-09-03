import * as React from "react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

/**
 * Образец — единица визуальной проверки.
 *
 * Подпись всегда рядом с самим элементом, а не в общем заголовке сцены.
 * Иначе ряд из пяти кнопок читается как куча: видно, что они разные,
 * но нельзя сказать, какая из них ghost, а какая link.
 */
export function Specimen({
  label,
  hint,
  children,
  className,
}: {
  label: string;
  /** Уточнение под подписью: значение, размер, ограничение. */
  hint?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="font-mono text-xs text-muted-foreground">{label}</span>
        {hint ? <span className="text-xs text-muted-foreground/70">{hint}</span> : null}
      </div>
      <div className="flex min-w-0 flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}

export type SpecimenRow = {
  /** Совпадает с именем варианта в коде: по нему образец и опознают. */
  label: string;
  hint?: string;
  render: () => React.ReactNode;
};

/**
 * Список образцов: по одному в строке, подпись слева.
 *
 * Применяется, когда ось одна — например состояния поля или варианты
 * сообщения. Для двух осей есть SpecimenMatrix.
 */
export function SpecimenList({
  items,
  className,
}: {
  items: SpecimenRow[];
  className?: string;
}) {
  return (
    <div className={cn("w-full min-w-0 overflow-hidden rounded-xl border border-border/80", className)}>
      {items.map((item, index) => (
        <div
          key={item.label}
          className={cn(
            "grid items-center gap-x-4 gap-y-2 px-4 py-3",
            "grid-cols-1 sm:grid-cols-[minmax(9rem,14rem)_minmax(0,1fr)]",
            index ? "border-t border-border/70" : "",
          )}
        >
          <div className="flex flex-col">
            <span className="font-mono text-xs text-muted-foreground">{item.label}</span>
            {item.hint ? (
              <span className="text-xs leading-5 text-muted-foreground/70">{item.hint}</span>
            ) : null}
          </div>
          <div className="flex min-w-0 flex-wrap items-center gap-2">{item.render()}</div>
        </div>
      ))}
    </div>
  );
}

/**
 * Матрица образцов: строки и колонки подписаны.
 *
 * Применяется, когда осей две — например варианты кнопки против её
 * размеров. Сравнение идёт и по строке, и по колонке, а это ровно то,
 * что нужно для сверки глазами.
 */
export function SpecimenMatrix({
  columns,
  rows,
  render,
  caption,
  className,
}: {
  /** Подписи колонок — вторая ось. */
  columns: { id: string; label: string; hint?: string }[];
  /** Подписи строк — первая ось. */
  rows: { id: string; label: string; hint?: string }[];
  /** Что показать на пересечении. */
  render: (rowId: string, columnId: string) => React.ReactNode;
  caption?: string;
  className?: string;
}) {
  return (
    <div className={cn("w-full min-w-0", className)}>
      <div className="w-full overflow-x-auto rounded-xl border border-border/80">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-[12rem] text-xs font-medium text-muted-foreground">
                вариант \ размер
              </TableHead>
              {columns.map((column) => (
                <TableHead key={column.id} className="text-xs font-medium text-muted-foreground">
                  <span className="font-mono">{column.label}</span>
                  {column.hint ? (
                    <span className="ml-1.5 font-normal text-muted-foreground/70">{column.hint}</span>
                  ) : null}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id} className="hover:bg-transparent">
                <TableCell className="align-middle">
                  <span className="font-mono text-xs text-muted-foreground">{row.label}</span>
                  {row.hint ? (
                    <div className="text-xs leading-5 text-muted-foreground/70">{row.hint}</div>
                  ) : null}
                </TableCell>
                {columns.map((column) => (
                  <TableCell key={column.id} className="align-middle">
                    {render(row.id, column.id)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {caption ? (
        <div className="px-1 pt-2 text-xs leading-5 text-muted-foreground/80">{caption}</div>
      ) : null}
    </div>
  );
}
