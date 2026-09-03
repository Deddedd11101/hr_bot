import React from "react";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { cn } from "@/lib/utils";

/**
 * Модуль страницы: шапка постоянной высоты и одно из тел под ней.
 *
 * Один и тот же код был скопирован под четырьмя именами — SectionCard на
 * дашборде, SurfaceCard в массовых действиях, SettingsCard в настройках
 * и в меню бота, DetailCard в карточке сотрудника.
 *
 * Описания под заголовком нет и слота под него тоже. Оно ломало полосу:
 * в трёхколоночной полосе дашборда шапка с описанием оказывалась на 44px
 * выше соседней, разделитель шёл по трём разным линиям, а содержимое
 * начиналось настолько же ниже. При этом на 26 модулей продукта приходилось
 * шесть описаний — слот стоил дороже, чем приносил. Заголовок обязан
 * объяснять модуль сам.
 *
 * Рамку несёт модуль. Записи внутри своей рамки не имеют — иначе выходит
 * карточка в карточке; для них есть PageSectionRows.
 */
export interface PageSectionProps extends Omit<React.ComponentProps<typeof Card>, "title"> {
  /** Имя модуля. Показывается заголовком, поэтому обязательно. */
  title: React.ReactNode;
  /**
   * Количество записей. Стоит у имени, а не среди действий: это свойство
   * содержимого, а не то, что можно нажать. Пишется приглушённо, без бейджа
   * и рамки — как счётчик в полосе заголовка страницы.
   *
   * Ноль не показывается. Он ничего не сообщает: пустоту модуля видно
   * по его телу, а рядом с именем ноль читается как поломка данных.
   * Счётчик начинается с единицы.
   */
  counter?: number;
  /** Одно компактное действие справа. Набор действий сюда не помещается. */
  action?: React.ReactNode;
  /** Класс для тела модуля, а не для его рамки. */
  contentClassName?: string;
}

export function PageSection({
  title,
  counter,
  action,
  className,
  contentClassName,
  children,
  ...props
}: PageSectionProps) {
  return (
    <Card
      data-section=""
      className={cn("border border-border/80 bg-card shadow-none ring-0", className)}
      {...props}
    >
      <CardHeader className="border-b border-border/70 pb-4">
        {/*
          * min-h-7 стоит на строке, а не на шапке: у шапки есть нижний
          * паддинг, и заданный ей минимум оказался бы ниже фактической
          * высоты и ни на что не влиял. На строке он работает — 28px это
          * высота кнопки размера sm, самого крупного контрола, который сюда
          * допускается. Значение сверено с button.tsx, а не взято по памяти:
          * подпись с высотой контрола в этом проекте уже была неверной.
          */}
        <div className="flex min-h-7 items-center gap-3">
          <div className="flex min-w-0 items-baseline gap-2">
            {/*
              * h2, а не div: имя модуля — заголовок раздела страницы, и
              * дерево доступности обязано это показывать. У CardTitle из кита
              * тег не переопределяется, поэтому заголовок собран здесь,
              * со слотом и классами кита. Уровень второй: первый занят
              * именем страницы в полосе заголовка.
              */}
            <h2
              data-slot="card-title"
              className="min-w-0 truncate text-base leading-snug font-semibold"
            >
              {title}
            </h2>
            {counter !== undefined && counter > 0 ? (
              <span className="shrink-0 text-sm tabular-nums text-muted-foreground">{counter}</span>
            ) : null}
          </div>
          {action ? (
            <div
              /*
               * Слот назван своим именем, а не card-action: у CardHeader на
               * card-action висит переключение на двухколоночный грид, и
               * правило вступило бы в спор с этой строкой.
               */
              data-slot="page-section-action"
              className="ml-auto flex shrink-0 items-center"
            >
              {action}
            </div>
          ) : null}
        </div>
      </CardHeader>
      {/*
       * Тело растёт: модуль вытягивается до высоты соседей по полосе,
       * и пустое состояние встаёт в середину этой высоты, а не липнет
       * к заголовку.
       */}
      <CardContent className={cn("flex min-h-0 flex-1 flex-col pt-4", contentClassName)}>
        {children}
      </CardContent>
    </Card>
  );
}

/**
 * Коллекция однотипных записей внутри модуля.
 *
 * Записи разделяются линиями, а не собственными рамками: поверхность на
 * уровень одна. Рамку в этой связке уже несёт модуль, и вторая рамка внутри
 * читается как карточка в карточке — так было на восьми экранах из девяти.
 *
 * Отступы задаются детям, а не оборачивают каждого в свой компонент: строкой
 * бывает и div, и ссылка, и кнопка, и подменять им тег ради раскладки незачем.
 */
export function PageSectionRows({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="page-section-rows"
      className={cn(
        "divide-y divide-border/70 [&>*]:py-3 [&>*:first-child]:pt-0 [&>*:last-child]:pb-0",
        className,
      )}
      {...props}
    />
  );
}

/**
 * Сетка равных плиток внутри модуля.
 *
 * Принцип тот же, что у PageRow: количество долей, а не шаблон колонок.
 * Порог перестроения один, а не лестница: модуль уже стоит в доле полосы,
 * и ширина окна о его собственной ширине ничего не сообщает. Пять колонок
 * внутри половины полосы давали плитку в 170px, где подпись обрывалась
 * на первом слове.
 */
export type PageSectionGridColumns = 2 | 3;

const GRID_COLUMNS: Record<PageSectionGridColumns, string> = {
  2: "sm:grid-cols-2",
  3: "sm:grid-cols-3",
};

export interface PageSectionGridProps extends React.ComponentProps<"div"> {
  columns?: PageSectionGridColumns;
}

export function PageSectionGrid({ columns = 2, className, ...props }: PageSectionGridProps) {
  return (
    <div
      data-slot="page-section-grid"
      data-columns={columns}
      className={cn("grid grid-cols-1 gap-1", GRID_COLUMNS[columns], className)}
      {...props}
    />
  );
}

/**
 * Пустое состояние модуля.
 *
 * Одно оформление вместо пяти: в проекте пустота рисовалась и блоком в 144px
 * без рамки, и пунктиром в 96px с заливкой, и 118px пунктиром из CSS,
 * и сплошной рамкой в 220px, и четырьмя самодельными div с разными радиусами.
 *
 * Своей рамки нет: поверхность на уровень остаётся одна. Блок центрируется
 * по доступной высоте — Empty уже несёт flex-1 и justify-center, а тело
 * модуля растёт под него.
 */
export interface PageSectionEmptyProps extends Omit<React.ComponentProps<"div">, "title"> {
  /** Иконка сцены. Без неё пустота читается как сбой отрисовки. */
  icon?: React.ReactNode;
  title: React.ReactNode;
  /** Что появится здесь и откуда. Одна строка. */
  description?: React.ReactNode;
}

export function PageSectionEmpty({
  icon,
  title,
  description,
  className,
  ...props
}: PageSectionEmptyProps) {
  return (
    <Empty data-slot="page-section-empty" className={cn("min-h-36", className)} {...props}>
      <EmptyHeader>
        {icon ? <EmptyMedia variant="icon">{icon}</EmptyMedia> : null}
        <EmptyTitle>{title}</EmptyTitle>
        {description ? <EmptyDescription>{description}</EmptyDescription> : null}
      </EmptyHeader>
    </Empty>
  );
}
