import type { ListKind, Option } from "./types";

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
