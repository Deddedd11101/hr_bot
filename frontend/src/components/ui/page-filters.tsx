import React from "react";
import { Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group";
import { cn } from "@/lib/utils";

/**
 * Полоса фильтров страницы.
 *
 * Идёт сразу за полосой заголовка и ни во что не завёрнута: карточка только
 * ради фильтров даёт ощущение карточки в карточке, когда ниже начинаются
 * карточки записей. До этого фильтры лежали в трёх разных местах — голой
 * строкой в потоке, внутри приглушённой полосы внутри Card и сбоку
 * в навигации, — и на каждом экране в своём порядке.
 *
 * Поэтому порядок задан слотами, а не разметкой вызывающего кода: автор
 * выбирает, что положить, но не куда. Поиск забирает свободное место, чтобы
 * полоса тянулась от края до края; переключатель представления прижат вправо,
 * потому что меняет не выборку, а её показ.
 *
 * Форма создания записи фильтром не является и в полосу не кладётся: она
 * разворачивается под ней.
 */
export interface PageFiltersProps extends React.ComponentProps<"div"> {
  /** Чипы-табы набора: Сотрудники / Кандидаты. */
  scope?: React.ReactNode;
  /** Одно поле поиска. Растягивается на всё свободное место. */
  search?: React.ReactNode;
  /** Селекты выборки: статус, сортировка. */
  controls?: React.ReactNode;
  /** Переключатель представления. Прижат к правому краю. */
  view?: React.ReactNode;
}

export function PageFilters({
  scope,
  search,
  controls,
  view,
  className,
  ...props
}: PageFiltersProps) {
  return (
    <div
      data-slot="page-filters"
      className={cn("flex flex-wrap items-center gap-2", className)}
      {...props}
    >
      {scope ? (
        <div data-slot="page-filters-scope" className="flex shrink-0 flex-wrap items-center gap-2">
          {scope}
        </div>
      ) : null}
      {search ? (
        <div data-slot="page-filters-search" className="min-w-[280px] flex-1">
          {search}
        </div>
      ) : null}
      {controls ? (
        <div data-slot="page-filters-controls" className="flex shrink-0 flex-wrap items-center gap-2">
          {controls}
        </div>
      ) : null}
      {view ? (
        <div data-slot="page-filters-view" className="ml-auto flex shrink-0 items-center">
          {view}
        </div>
      ) : null}
    </div>
  );
}

/**
 * Поле поиска по выдаче.
 *
 * Раньше собиралось вручную на каждом экране и всякий раз по-своему: pl-9
 * в списке сотрудников, h-8 pl-8 в конструкторе, h-9 pl-8 в навигации
 * каталога. Собрано из InputGroup, который для этого в ките и лежит.
 */
export interface PageFiltersSearchProps
  extends Omit<React.ComponentProps<"input">, "onChange" | "value"> {
  value: string;
  onValueChange: (next: string) => void;
  /** Служит и подписью поля: у поиска нет видимого label. */
  placeholder: string;
  groupClassName?: string;
}

export function PageFiltersSearch({
  value,
  onValueChange,
  placeholder,
  groupClassName,
  className,
  ...props
}: PageFiltersSearchProps) {
  return (
    <InputGroup className={cn("w-full", groupClassName)}>
      <InputGroupAddon>
        <Search />
      </InputGroupAddon>
      <InputGroupInput
        type="search"
        value={value}
        placeholder={placeholder}
        aria-label={placeholder}
        onChange={(event) => onValueChange(event.target.value)}
        className={className}
        {...props}
      />
    </InputGroup>
  );
}

export interface SegmentOption {
  value: string;
  label: string;
  icon?: React.ReactNode;
}

/**
 * Сегментный переключатель: набор списка или представление выдачи.
 *
 * Высота коробки — те же 32px, что у поиска и селектов, иначе полоса
 * разъезжается по вертикали: коробка p-1 с кнопкой в 28px давала 38px.
 * Отсюда p-0.5 и кнопки размера xs.
 *
 * Выбранный сегмент выделен нейтральной заливкой, без цвета и без рамки.
 * Заливка --secondary не годилась: в светлой теме она расходится
 * с --background на 0.018 светлоты, и выбор был не виден. Цветные варианты
 * тоже отпали — сплошной primary спорит с единственным основным действием
 * на экране, а мягкий тон с зелёной подписью давал 3.88:1 при пороге 4.5
 * (подпись здесь 12px, послабление для крупного текста не применяется).
 *
 * Отсюда --foreground с малой прозрачностью: в светлой теме он затемняет
 * сегмент, в тёмной осветляет, то есть шаг от фона одинаково заметен в обеих
 * и не заводит нового значения в заблокированную палитру.
 *
 * Активный сегмент исключён из приглушения по наведению: состояние уже
 * выделено цветом, и подмешивание фона гасило бы его контраст.
 */
export interface PageFiltersSegmentsProps {
  value: string;
  options: SegmentOption[];
  onValueChange: (next: string) => void;
  /** Доступное имя группы: без него ряд кнопок ничего не сообщает о своей роли. */
  label: string;
  /** Только иконки. Подпись уходит в доступное имя кнопки, а не пропадает. */
  iconOnly?: boolean;
  className?: string;
}

export function PageFiltersSegments({
  value,
  options,
  onValueChange,
  label,
  iconOnly = false,
  className,
}: PageFiltersSegmentsProps) {
  return (
    <div
      role="group"
      aria-label={label}
      data-slot="page-filters-segments"
      className={cn(
        "flex h-8 shrink-0 items-center gap-0.5 rounded-lg border border-border bg-background p-0.5",
        className,
      )}
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <Button
            key={option.value}
            variant="ghost"
            size={iconOnly ? "icon-xs" : "xs"}
            aria-pressed={active}
            title={iconOnly ? option.label : undefined}
            aria-label={iconOnly ? option.label : undefined}
            onClick={() => onValueChange(option.value)}
            className={
              active
                ? "bg-foreground/12 font-medium text-foreground hover:bg-foreground/16 hover:text-foreground"
                : "text-muted-foreground"
            }
          >
            {option.icon}
            {iconOnly ? null : option.label}
          </Button>
        );
      })}
    </div>
  );
}
