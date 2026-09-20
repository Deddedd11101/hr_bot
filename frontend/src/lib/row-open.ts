import type * as React from "react";

/** Вложенные управляющие элементы: клик по ним — не клик по строке. */
const УПРАВЛЕНИЕ = "a, button, input, label, select, textarea, [role=button], [role=menuitem]";

/**
 * Клик по площади строки таблицы открывает запись — как клик по карточке.
 *
 * Настоящая ссылка стоит в ячейке имени: у неё точка табуляции, Enter,
 * средняя кнопка мыши и «копировать адрес». Обработчик на tr лишь дублирует
 * её для мыши, поэтому не берёт клики с модификаторами (у ссылки они значат
 * «в новой вкладке», у строки не значили бы ничего), клики по вложенным
 * контролам и отпускание кнопки после выделения текста.
 *
 * Растянутая ссылка, как в RecordCard, здесь невозможна: WebKit не считает
 * position:relative на tr содержащим блоком (bug 240961), и накладка легла
 * бы на всю таблицу — последняя строка забирала бы клики всех остальных.
 */
export function открытьЗаписьПоСтроке(event: React.MouseEvent<HTMLElement>, href: string) {
  if (event.defaultPrevented || event.button !== 0) return;
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  if ((event.target as Element).closest(УПРАВЛЕНИЕ)) return;
  if (window.getSelection()?.toString()) return;
  window.location.assign(href);
}
