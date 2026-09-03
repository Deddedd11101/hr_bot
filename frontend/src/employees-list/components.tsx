import * as React from "react";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  SlidersHorizontal,
  BadgeCheck,
  CalendarDays,
  ExternalLink,
  FileClock,
  MessageCircle,
  Timer,
  Workflow,
} from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { RecordCard, RecordCardTag, type RecordCardTagSpec } from "@/components/ui/record-card";
import { ПРОЯВЛЕНИЕ } from "@/lib/reveal";
import { cn } from "@/lib/utils";

import { Checkbox } from "@/components/ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import { HIDEABLE_COLUMNS, buildSort, columnLabel, defaultDirection, parseSort } from "./data";
import type { ColumnKey, EmployeeItem, ListKind, Option, SortDirection, SortField } from "./types";

export function SinglePicker({
  value,
  options,
  onChange,
  icon,
  className,
}: {
  value: string;
  options: Option[];
  onChange: (next: string) => void;
  icon?: React.ReactNode;
  className?: string;
}) {
  const selected = options.find((option) => option.value === value) || options[0];

  return (
    <Select items={options} value={selected?.value || value} onValueChange={(next) => onChange(next ?? value)}>
      <SelectTrigger
        /*
         * Своей заливки у селекта нет: набор рисует его рамкой на прозрачном
         * фоне, как поле поиска рядом. Прежний page-local override
         * border-transparent + bg-secondary делал контрол почти невидимым
         * в полосе фильтров — граница пропадала, а серая заливка на фоне
         * страницы не читалась как поле.
         */
        className={cn("min-w-48", className)}
        size="default"
      >
        <span className="inline-flex min-w-0 items-center gap-2 truncate">
          {icon}
          <SelectValue className="truncate" />
        </span>
      </SelectTrigger>
      <SelectContent align="start" alignItemWithTrigger={false} className="w-48">
        <SelectGroup>
          {options.map((option) => (
            <SelectItem value={option.value} key={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}

/**
 * Действия записи: чат и переход в карточку.
 *
 * В покое скрыты, проявляются по наведению и при фокусе внутри записи —
 * правила в lib/reveal.ts.
 *
 * Переход в карточку отдельной иконкой нужен только в таблице: в сетке
 * запись открывает сама карточка (RecordCard), и вторая точка входа
 * рядом с ней только дублировала бы действие.
 */
function ItemActions({ item, внутри }: { item: EmployeeItem; внутри: "card" | "row" }) {
  return (
    /*
     * Переносить действия нельзя: в карточке это ломало бы строку постоянной
     * высоты, в таблице — растягивало ячейку в столбик. Колонка под них
     * рассчитана точно: 2×32 кнопки + 8 зазор + 2×16 отступы ячейки = 104.
     */
    <div className="flex shrink-0 items-center gap-2 whitespace-nowrap">
      {item.chat_link ? (
        <a
          href={item.chat_link}
          target="_blank"
          rel="noreferrer noopener"
          className={cn(buttonVariants({ variant: "outline", size: "icon" }), ПРОЯВЛЕНИЕ[внутри])}
          title="Открыть чат"
          aria-label="Открыть чат"
        >
          <MessageCircle />
        </a>
      ) : null}
      {внутри === "row" ? (
        <a
          href={item.react_edit_url || item.edit_url}
          className={cn(buttonVariants({ variant: "outline", size: "icon" }), ПРОЯВЛЕНИЕ[внутри])}
          title="Открыть карточку"
          aria-label="Открыть карточку"
        >
          <ExternalLink />
        </a>
      ) : null}
    </div>
  );
}

/**
 * Карточка человека в сетке.
 *
 * Собрана из RecordCard: имя и должность слева сверху, ряд чипов под ними,
 * чат по наведению справа. Отдельной иконки «Открыть карточку» больше нет —
 * запись открывает вся карточка, и об этом говорят курсор, рамка
 * и небольшое увеличение.
 *
 * Статус переехал из строки имени в ряд чипов: анатомия карточки записи одна
 * на все выдачи, и второго элемента рядом с именем в ней не предусмотрено.
 *
 * Прежняя версия держала один ряд чипов жёстко и сворачивала лишнее
 * в счётчик «+N» с замером ширин на ResizeObserver. Счётчик убран вместе
 * со всей машинерией: он появлялся не на узких экранах, а на длинных
 * подписях, и вопрос решается их сокращением.
 */
export function EmployeeCard({ item }: { item: EmployeeItem }) {
  const isCandidate = item.list_kind === "candidates";
  const statusValue = isCandidate ? item.candidate_work_stage_label : item.status_label;
  const dateLabel = isCandidate ? item.test_task_due_at_label : item.first_workday_label;
  /*
   * Слова в подписи чипа даты нет — только число. Но смысл у него разный:
   * у сотрудника это дата выхода, у кандидата дедлайн тестового. Различие
   * несут иконка и доступное имя, иначе читалка экрана произносит голую
   * дату, и сокращение подписи превращается в потерю данных.
   */
  const dateTitle = isCandidate ? "Дедлайн тестового" : "Дата выхода";

  const чипы: RecordCardTagSpec[] = [
    {
      label: statusValue || "Без статуса",
      icon: isCandidate ? <FileClock className="size-3.5" /> : <BadgeCheck className="size-3.5" />,
    },
    {
      label: item.chat_id || item.chat_handle || "Без канала",
      icon: <MessageCircle className="size-3.5" />,
    },
  ];
  /* Чип без значения не рисуется: прочерк в чипе ничего не сообщает. */
  if (dateLabel && dateLabel !== "—") {
    чипы.push({
      label: dateLabel,
      icon: isCandidate ? <Timer className="size-3.5" /> : <CalendarDays className="size-3.5" />,
      title: `${dateTitle}: ${dateLabel}`,
      "aria-label": `${dateTitle}: ${dateLabel}`,
    });
  }
  if (item.planned_scenario_title && item.planned_scenario_title !== "—") {
    чипы.push({ label: item.planned_scenario_title, icon: <Workflow className="size-3.5" /> });
  }

  return (
    <RecordCard
      title={item.full_name || "Без имени"}
      subtitle={item.position || "Без должности"}
      tags={чипы}
      href={item.react_edit_url || item.edit_url}
      actions={<ItemActions item={item} внутри="card" />}
    />
  );
}

/**
 * Колонки таблицы. Порядок, ширины и признак скрываемости заданы здесь,
 * а не в трёх местах сразу.
 *
 * Ширины в пикселях, а не в процентах: при процентах таблица всегда ровно
 * по контейнеру и горизонтальной прокрутки не бывает в принципе. С пикселями
 * сумма видимых колонок может превысить контейнер, и полоса появляется сама.
 *
 * У колонки действий нет подписи. Место под кнопки зарезервировано, но
 * заголовка над ним быть не должно; доступное имя уходит в sr-only, иначе
 * читалка экрана называет колонку пустой.
 */
type ColumnSpec = {
  key: ColumnKey | null;
  field: SortField | null;
  label: (kind: ListKind) => string;
  width: number;
  align?: string;
  labelHidden?: boolean;
};

const КОЛОНКИ: ColumnSpec[] = [
  { key: null, field: "name", label: () => "ФИО", width: 260 },
  { key: "position", field: "position", label: () => "Должность", width: 200 },
  { key: "status", field: "status", label: (kind) => (kind === "candidates" ? "Этап" : "Статус"), width: 170 },
  { key: "channel", field: "channel", label: () => "Канал", width: 190 },
  { key: "date", field: "date", label: (kind) => (kind === "candidates" ? "Дедлайн" : "Выход"), width: 130 },
  { key: "scenario", field: "scenario", label: () => "Сценарий", width: 220 },
  { key: null, field: null, label: () => "Действия", width: 112, align: "text-right", labelHidden: true },
];

function видимыеКолонки(columns: Record<ColumnKey, boolean>): ColumnSpec[] {
  return КОЛОНКИ.filter((колонка) => колонка.key === null || columns[колонка.key]);
}

/**
 * Шапка таблицы с сортировкой по колонкам.
 *
 * Заголовок — настоящая кнопка внутри th, а не кликабельный div: иначе
 * сортировка недостижима с клавиатуры и не объявляется читалкой экрана.
 * Направление объявляется через aria-sort на самой ячейке — это то, что
 * читалка сообщает, стрелка рядом лишь дублирует его глазами.
 */
export function EmployeeTableHeader({
  listKind,
  sortMode,
  columns,
  onSortChange,
}: {
  listKind: ListKind;
  sortMode: string;
  columns: Record<ColumnKey, boolean>;
  onSortChange: (mode: string) => void;
}) {
  const текущая = parseSort(sortMode);

  return (
    <TableHeader>
      <TableRow className="hover:bg-transparent">
        {видимыеКолонки(columns).map((колонка) => {
          const активна = колонка.field !== null && колонка.field === текущая.field;
          const направление: SortDirection = активна
            ? текущая.direction
            : defaultDirection(колонка.field ?? "id");
          const Стрелка = !активна ? ArrowUpDown : направление === "asc" ? ArrowUp : ArrowDown;

          return (
            <TableHead
              key={колонка.label(listKind)}
              /*
               * Без uppercase и широкого трекинга: у сортируемых колонок
               * подпись лежит внутри button, а preflight сбрасывает кнопкам
               * text-transform. Из-за этого «Действия» шли капсом, а
               * остальные пять — обычным регистром, и колонки выглядели
               * набранными разными шрифтами.
               */
              style={{ width: колонка.width }}
              className={cn(
                "h-9 px-4 text-[0.7rem] font-semibold text-muted-foreground",
                колонка.align,
                /* z выше, чем у ячеек строк: шапка перекрывает их при прокрутке. */
                колонка.field === null && "sticky right-0 z-[2] bg-card",
              )}
              aria-sort={активна ? (направление === "asc" ? "ascending" : "descending") : undefined}
            >
              {колонка.field === null ? (
                <span className="sr-only">{колонка.label(listKind)}</span>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    const поле = колонка.field as SortField;
                    /* Повторное нажатие по той же колонке переворачивает порядок. */
                    const следующее: SortDirection = активна
                      ? направление === "asc"
                        ? "desc"
                        : "asc"
                      : defaultDirection(поле);
                    onSortChange(buildSort(поле, следующее, listKind));
                  }}
                  className={cn(
                    "-mx-1 inline-flex max-w-full items-center gap-1 rounded px-1 py-0.5 transition-colors hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
                    активна && "text-foreground",
                  )}
                >
                  <span className="truncate">{колонка.label(listKind)}</span>
                  <Стрелка className={cn("size-3 shrink-0", !активна && "opacity-40")} />
                </button>
              )}
            </TableHead>
          );
        })}
      </TableRow>
    </TableHeader>
  );
}

/**
 * Таблица людей.
 *
 * Вся выдача — одна карточка, записи разделены линиями: рамку несёт
 * контейнер, строки своей не имеют. Прежняя версия собирала строки из
 * article с собственной рамкой у каждой — получалась карточка в карточке,
 * а в дереве доступности таблицы не было вовсе: только набор блоков.
 *
 * Компонент Table взят из кита. До этого он числился showcase — «в продукте
 * пока не применяется: список сотрудников собран из блоков вручную».
 */
export function EmployeeTable({
  items,
  listKind,
  sortMode,
  columns,
  onSortChange,
}: {
  items: EmployeeItem[];
  listKind: ListKind;
  sortMode: string;
  columns: Record<ColumnKey, boolean>;
  onSortChange: (mode: string) => void;
}) {
  const ширина = видимыеКолонки(columns).reduce((сумма, колонка) => сумма + колонка.width, 0);
  return (
    /*
     * py-1.5 вместо прежних 12px: отступ над шапкой был вдвое больше нужного.
     * Горизонтальный отступ, наоборот, вырос вдвое — он задан ячейками
     * (px-4), потому что у карточки его нет вовсе: таблица должна доходить
     * до самых краёв, иначе разделители строк обрываются, не дойдя до рамки.
     */
    <Card className="w-full min-w-0 overflow-hidden border border-border bg-card px-0 py-1.5 shadow-none ring-0">
      {/*
        * min-width по сумме видимых колонок. Пока места хватает, таблица
        * тянется на всю ширину; как только колонок добавили больше, чем
        * помещается, она перестаёт сжиматься и контейнер даёт горизонтальную
        * полосу — overflow-x-auto у него уже есть в ките.
        */}
      <Table className="table-fixed" style={{ minWidth: ширина }}>
        <EmployeeTableHeader
          listKind={listKind}
          sortMode={sortMode}
          columns={columns}
          onSortChange={onSortChange}
        />
        <TableBody>
          {items.map((item) => (
            <EmployeeTableRow key={item.id} item={item} columns={columns} />
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

export function EmployeeTableRow({
  item,
  columns,
}: {
  item: EmployeeItem;
  columns: Record<ColumnKey, boolean>;
}) {
  const isCandidate = item.list_kind === "candidates";
  const statusValue = isCandidate ? item.candidate_work_stage_label : item.status_label;
  const dateLabel = isCandidate ? item.test_task_due_at_label : item.first_workday_label;

  const значение: Record<ColumnKey, string> = {
    position: item.position || "—",
    status: statusValue || "—",
    channel: item.chat_id || item.chat_handle || "—",
    date: dateLabel || "—",
    scenario: item.planned_scenario_title || "—",
  };

  return (
    <TableRow className="group/row">
      <TableCell className="overflow-hidden px-4 py-2.5 font-semibold">
        <span className="block truncate">{item.full_name || "Без имени"}</span>
      </TableCell>
      {HIDEABLE_COLUMNS.filter((ключ) => columns[ключ]).map((ключ) => (
        <TableCell key={ключ} className="overflow-hidden px-4 py-2.5 text-muted-foreground">
          <span className="block truncate">{значение[ключ]}</span>
        </TableCell>
      ))}
      {/*
        * Действия липнут к правому краю прокручиваемой области и перекрывают
        * уезжающее под них содержимое. Иначе при горизонтальной прокрутке
        * основные действия по записи оказывались бы за краем экрана.
        *
        * Фон непрозрачный, иначе текст просвечивал бы сквозь. В покое это
        * bg-card — тот же цвет, что у карточки под таблицей; по наведению
        * bg-muted/50, ровно как у строки, и поверх того же bg-card, так что
        * оттенок совпадает пиксель в пиксель.
        */}
      <TableCell className="sticky right-0 z-[1] bg-card px-4 py-2.5 text-right group-hover/row:bg-muted/50">
        <div className="flex items-center justify-end">
          <ItemActions item={item} внутри="row" />
        </div>
      </TableCell>
    </TableRow>
  );
}

/**
 * Выбор видимых колонок.
 *
 * Кнопка появляется только в табличном виде: в карточках колонок нет,
 * и настраивать там нечего.
 */
export function EmployeeColumnsPicker({
  listKind,
  columns,
  onChange,
}: {
  listKind: ListKind;
  columns: Record<ColumnKey, boolean>;
  onChange: (columns: Record<ColumnKey, boolean>) => void;
}) {
  const скрыто = HIDEABLE_COLUMNS.filter((ключ) => !columns[ключ]).length;

  return (
    <Popover>
      <PopoverTrigger
        render={
          <Button variant="outline" size="icon" title="Настроить колонки" aria-label="Настроить колонки">
            <SlidersHorizontal />
          </Button>
        }
      />
      <PopoverContent align="end" className="w-56 p-2">
        <div className="px-2 pt-1 pb-2 text-[0.7rem] font-semibold text-muted-foreground">
          Колонки{подписьСкрытого(скрыто)}
        </div>
        <div className="grid gap-0.5">
          {HIDEABLE_COLUMNS.map((ключ) => (
            <label
              key={ключ}
              className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted/60"
            >
              <Checkbox
                checked={columns[ключ]}
                onCheckedChange={(next) => onChange({ ...columns, [ключ]: next === true })}
              />
              {columnLabel(ключ, listKind)}
            </label>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}

/** Счётчик скрытого рядом с заголовком: без него не видно, что что-то выключено. */
function подписьСкрытого(количество: number): string {
  return количество > 0 ? ` · скрыто ${количество}` : "";
}
