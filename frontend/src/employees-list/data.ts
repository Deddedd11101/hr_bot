import type { ListKind, Option, ViewMode } from "./types";

export function listKindOptions(): Option[] {
  return [
    { value: "employees", label: "Сотрудники" },
    { value: "candidates", label: "Кандидаты" },
  ];
}

export function statusOptions(listKind: ListKind): Option[] {
  if (listKind === "candidates") {
    return [
      { value: "all", label: "Все этапы" },
      { value: "Тестирование", label: "Тестирование" },
      { value: "Оффер", label: "Оффер" },
      { value: "Отказ кандидата", label: "Отказ кандидата" },
      { value: "Наш отказ", label: "Наш отказ" },
      { value: "Преонбординг", label: "Преонбординг" },
      { value: "Заключение договора", label: "Заключение договора" },
    ];
  }

  return [
    { value: "all", label: "Все статусы" },
    { value: "Адаптация", label: "Адаптация" },
    { value: "ИПР", label: "ИПР" },
    { value: "В штате", label: "В штате" },
  ];
}

export function sortOptions(listKind: ListKind): Option[] {
  const base = [
    { value: "id_desc", label: "Сначала новые" },
    { value: "name_asc", label: "По имени А-Я" },
    { value: "name_desc", label: "По имени Я-А" },
  ];

  if (listKind === "candidates") {
    return base.concat([
      { value: "deadline_asc", label: "Ближайший дедлайн" },
      { value: "deadline_desc", label: "Поздний дедлайн" },
    ]);
  }

  return base.concat([
    { value: "workday_asc", label: "Ближайший выход" },
    { value: "workday_desc", label: "Поздний выход" },
  ]);
}

/**
 * Сортировка: поле и направление.
 *
 * Режим хранится строкой вида «поле_направление», потому что тем же значением
 * пользуется селект в полосе фильтров. Поле даты называется по-разному
 * у сотрудников и кандидатов — workday и deadline, — поэтому разбор и сборка
 * знают про вид списка и приводят их к общему «date».
 */
export type SortField =
  | "id"
  | "name"
  | "position"
  | "status"
  | "channel"
  | "date"
  | "scenario";
export type SortDirection = "asc" | "desc";

export function parseSort(mode: string): { field: SortField; direction: SortDirection } {
  const граница = mode.lastIndexOf("_");
  const поле = граница === -1 ? mode : mode.slice(0, граница);
  const напр = граница === -1 ? "desc" : mode.slice(граница + 1);
  const направление: SortDirection = напр === "asc" ? "asc" : "desc";

  if (поле === "workday" || поле === "deadline") return { field: "date", direction: направление };
  if (
    поле === "name" ||
    поле === "position" ||
    поле === "status" ||
    поле === "channel" ||
    поле === "scenario"
  ) {
    return { field: поле, direction: направление };
  }
  return { field: "id", direction: направление };
}

export function buildSort(field: SortField, direction: SortDirection, listKind: ListKind): string {
  if (field === "date") {
    return `${listKind === "candidates" ? "deadline" : "workday"}_${direction}`;
  }
  return `${field}_${direction}`;
}

/** Направление, с которого начинается сортировка по полю при первом нажатии. */
export function defaultDirection(field: SortField): SortDirection {
  /* У даты и у порядка добавления полезнее сначала свежее и ближайшее. */
  return field === "id" ? "desc" : "asc";
}

/**
 * Селект показывает не все поля — только пять привычных.
 *
 * Заголовки таблицы умеют больше, и после сортировки по статусу селект
 * оказался бы пустым: значения нет в списке. Поэтому текущий режим,
 * если его там нет, добавляется отдельным пунктом — селект всегда
 * показывает правду о состоянии.
 */
export function sortOptionsWithCurrent(listKind: ListKind, mode: string): Option[] {
  const базовые = sortOptions(listKind);
  if (базовые.some((о) => о.value === mode)) return базовые;

  const { field, direction } = parseSort(mode);
  const имя: Record<SortField, string> = {
    id: "порядку добавления",
    name: "имени",
    position: "должности",
    status: listKind === "candidates" ? "этапу" : "статусу",
    channel: "каналу",
    date: listKind === "candidates" ? "дедлайну" : "дате выхода",
    scenario: "сценарию",
  };
  return [
    { value: mode, label: `По ${имя[field]}${direction === "desc" ? ", обратно" : ""}` },
    ...базовые,
  ];
}

/**
 * Колонки таблицы, которые можно скрывать.
 *
 * ФИО и действий здесь нет намеренно: первое опознаёт запись, второе —
 * единственный способ её открыть. Таблицу, из которой убрали и то и другое,
 * чинить пришлось бы через очистку хранилища.
 */
export type ColumnKey = "position" | "status" | "channel" | "date" | "scenario";

export const HIDEABLE_COLUMNS: ColumnKey[] = ["position", "status", "channel", "date", "scenario"];

export function columnLabel(key: ColumnKey, listKind: ListKind): string {
  if (key === "position") return "Должность";
  if (key === "status") return listKind === "candidates" ? "Этап" : "Статус";
  if (key === "channel") return "Канал";
  if (key === "date") return listKind === "candidates" ? "Дедлайн" : "Выход";
  return "Сценарий";
}

export function defaultVisibleColumns(): Record<ColumnKey, boolean> {
  return { position: true, status: true, channel: true, date: true, scenario: true };
}

/*
 * Ключи хранилища. Префикс раздела обязателен: рядом уже лежат «theme»
 * и ключ сайдбара, и безымянный «view» ничего бы про себя не сообщал.
 */
export const VIEW_STORAGE_KEY = "hrbot:employees:view";
export const COLUMNS_STORAGE_KEY = "hrbot:employees:columns";

/**
 * Чтение выполняется в инициализаторе useState, а не в эффекте: иначе первый
 * кадр рисуется значением по умолчанию, и раскладка успевает прыгнуть. Тот же
 * приём — в shell-sidebar/page.tsx для раскрытого меню.
 */
export function readStoredView(): ViewMode {
  if (typeof window === "undefined") return "table";
  return window.localStorage.getItem(VIEW_STORAGE_KEY) === "cards" ? "cards" : "table";
}

export function readStoredColumns(): Record<ColumnKey, boolean> {
  const поумолчанию = defaultVisibleColumns();
  if (typeof window === "undefined") return поумолчанию;

  try {
    const сырое = window.localStorage.getItem(COLUMNS_STORAGE_KEY);
    if (!сырое) return поумолчанию;
    const разобранное = JSON.parse(сырое) as Partial<Record<ColumnKey, boolean>>;
    /* Незнакомые и отсутствующие ключи берутся из умолчаний: набор колонок
       со временем меняется, а в хранилище остаётся прежний. */
    for (const ключ of HIDEABLE_COLUMNS) {
      if (typeof разобранное?.[ключ] === "boolean") поумолчанию[ключ] = разобранное[ключ] as boolean;
    }
    return поумолчанию;
  } catch {
    /* Испорченный JSON не должен ронять страницу — молча возвращаем умолчания. */
    return поумолчанию;
  }
}

export function kindCreateOptions(): Option[] {
  return [
    { value: "employees", label: "Сотрудник" },
    { value: "candidates", label: "Кандидат" },
  ];
}

export function employeeStageCreateOptions(): Option[] {
  return [
    { value: "staff", label: "В штате" },
    { value: "adaptation", label: "Адаптация" },
    { value: "ipr", label: "ИПР" },
  ];
}

export function candidateStageCreateOptions(): Option[] {
  return [
    { value: "testing", label: "Тестирование" },
    { value: "offer", label: "Оффер" },
    { value: "candidate_decline", label: "Отказ кандидата" },
    { value: "company_decline", label: "Наш отказ" },
    { value: "preonboarding", label: "Преонбординг" },
    { value: "contract", label: "Заключение договора" },
  ];
}
