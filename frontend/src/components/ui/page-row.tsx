import React from "react";

import { cn } from "@/lib/utils";

/**
 * Полоса модулей страницы.
 *
 * На одной полосе все модули одной ширины. До этого дашборд шёл четырьмя
 * разными шаблонами подряд: 1.45fr к 0.85fr, затем 0.9fr к 1.1fr — пропорция
 * обратная предыдущей строке, — и общей вертикали между полосами не было.
 *
 * Поэтому компонент принимает не шаблон колонок, а их количество. Дробей,
 * col-span и minmax(...px, ...) в страничной сетке быть не может: модуль,
 * которому мало доли, занимает собственную полосу целиком, а не полторы.
 *
 * Лестница брейкпоинтов записана здесь один раз и одинакова для всех полос.
 * Каждый её шаг — целое деление полосы, поэтому сирот на переносе не бывает:
 * три доли не превращаются в 2 + 1, а сразу идут в одну колонку.
 */
export type PageRowColumns = 1 | 2 | 3 | 4;

const COLUMN_CLASSES: Record<PageRowColumns, string> = {
  1: "",
  2: "md:grid-cols-2",
  3: "lg:grid-cols-3",
  4: "md:grid-cols-2 xl:grid-cols-4",
};

export interface PageRowProps extends React.ComponentProps<"div"> {
  /** Сколько равных долей на полосе. Больше четырёх не бывает: доля станет уже 400px. */
  columns?: PageRowColumns;
}

export function PageRow({ columns = 1, className, ...props }: PageRowProps) {
  return (
    <div
      data-slot="page-row"
      data-columns={columns}
      /*
       * Растяжение по высоте намеренно оставлено умолчанием grid: модули
       * на одной полосе выравниваются и по низу, а не только по ширине.
       * Шаг берётся из токена, чтобы страницы перестали назначать его каждая
       * по-своему — было gap-5 в обычном состоянии и gap-4 в состоянии ошибки.
       */
      className={cn(
        "grid grid-cols-1 gap-[var(--admin-page-gap)]",
        COLUMN_CLASSES[columns],
        className,
      )}
      {...props}
    />
  );
}
