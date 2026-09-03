import React from "react";

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

import { cn } from "@/lib/utils";

/**
 * Полоса заголовка страницы.
 *
 * Заголовок — не блок контента, поэтому он не лежит на карточке: ни рамки,
 * ни заливки, только разделитель снизу. До этого пять страниц из семи рисовали
 * шапку карточкой, а две обходились без заголовка вовсе.
 *
 * В полосе помещаются только имя страницы и компактные действия. Всё, что
 * крупнее, уезжает в контент — иначе высота полосы разъедется от страницы
 * к странице, а именно её постоянство и создаёт ощущение единой системы.
 *
 * Разделитель тянется на всю ширину поля контента: отрицательный отступ
 * выводит полосу за горизонтальный паддинг контейнера (20px), а внутренний
 * возвращает содержимое на место.
 *
 * Поэтому полосу нельзя класть внутрь .admin-page-stack или .admin-page-shell:
 * они ограничены --admin-page-max-width и центрированы, и полоса обрезалась бы
 * вместе с содержимым. На 2200px это давало по 127px пустоты с каждой стороны.
 * Полоса рисуется перед ними, а отступ до содержимого задан здесь же, чтобы
 * страницы не назначали его каждая по-своему.
 *
 * Разделитель — во всю ширину поля, а содержимое полосы — нет: оно
 * ограничено тем же пределом, что и содержимое страницы. Иначе на 2200px имя
 * страницы стоит на 127px левее первой карточки, и левого края у страницы
 * оказывается два.
 */
export interface PageHeaderProps {
  /** Имя страницы. Одно короткое существительное, как в боковом меню. */
  title: string;
  /**
   * Количество записей на странице. Стоит рядом с именем, а не среди действий:
   * это свойство содержимого, а не то, что можно нажать. Пишется приглушённо,
   * без бейджа и рамки — иначе спорит с заголовком за внимание.
   *
   * Ноль не показывается: пустоту видно по содержимому страницы, а рядом
   * с именем ноль читается как поломка данных. Счётчик начинается с единицы.
   */
  counter?: number;
  /** Компактные действия справа: кнопка, бейдж, переключатель. */
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({ title, counter, actions, className }: PageHeaderProps) {
  return (
    <header
      className={cn(
        /*
         * Высоту задаёт min-h-14, а отступы намеренно малы, чтобы содержимое
         * её не превышало: 56 = 8 + контент + 8 + 1px границы, то есть контрол
         * до 39px укладывается ровно. С py-3 переключатель темы (36px) давал
         * 61px, с py-2.5 — 57px из-за той самой границы снизу.
         */
        "-mx-5 mb-5 flex min-h-14 items-center border-b border-border px-5 py-2",
        className,
      )}
    >
      <div className="mx-auto flex w-full max-w-[var(--admin-page-max-width)] items-center justify-between gap-4">
        <div className="flex min-w-0 items-baseline gap-2">
          <h1 className="min-w-0 truncate text-lg font-semibold tracking-tight">{title}</h1>
          {counter !== undefined && counter > 0 ? (
            <span className="shrink-0 text-sm tabular-nums text-muted-foreground">{counter}</span>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
      </div>
    </header>
  );
}

/**
 * Полоса заголовка детали.
 *
 * Та же полоса, что и списочная, но вместо имени раздела — хлебная крошка:
 * «Опросы / Название опроса». Раздел кликабелен и уводит в каталог, имя
 * записи остаётся заголовком страницы. Раньше здесь была отдельная строка
 * возврата «К списку опросов» над именем — две строки на то, что крошка
 * говорит одной, и деталь была выше списка на целую строку.
 *
 * Двух шапок на странице не бывает — деталь сценария начиналась с полосы
 * «Сценарии» и карточки с именем под ней, и это читалось как два заголовка
 * подряд. Крошка решает то же самое: раздел и запись живут в одной строке.
 *
 * Высота совпадает со списочной полосой: постоянство высоты и есть то,
 * ради чего полоса не пускает внутрь ничего крупного.
 */
export interface PageDetailHeaderProps {
  /** Имя открытой записи. */
  title: string;
  /** Имя раздела в крошке: «Опросы». Как в боковом меню, без «К списку…». */
  sectionTitle: string;
  /** Переход к разделу для SPA-каталога. Если раздел — отдельная страница, вместо колбэка передаётся backHref. */
  onBack?: () => void;
  /** Адрес раздела для перехода обычной ссылкой. */
  backHref?: string;
  /** Компактные действия справа от имени. */
  actions?: React.ReactNode;
  className?: string;
}

export function PageDetailHeader({ title, sectionTitle, onBack, backHref, actions, className }: PageDetailHeaderProps) {
  return (
    <header
      className={cn(
        "-mx-5 mb-5 flex min-h-14 items-center border-b border-border px-5 py-2",
        className,
      )}
    >
      <div className="mx-auto flex w-full max-w-[var(--admin-page-max-width)] items-center justify-between gap-4">
        <Breadcrumb className="min-w-0">
          {/*
            Размер поднят до заголовочного: крошка здесь и есть заголовок
            страницы, а не служебная строка над ним. Раздел не сжимается,
            обрезается имя записи — раздел короткий и без него крошка
            перестаёт быть путём.
          */}
          <BreadcrumbList className="min-w-0 flex-nowrap gap-2 text-lg tracking-tight">
            <BreadcrumbItem className="shrink-0">
              {backHref ? (
                <BreadcrumbLink href={backHref}>{sectionTitle}</BreadcrumbLink>
              ) : (
                <BreadcrumbLink render={<button type="button" onClick={onBack} />} className="cursor-pointer">
                  {sectionTitle}
                </BreadcrumbLink>
              )}
            </BreadcrumbItem>
            <BreadcrumbSeparator className="shrink-0">/</BreadcrumbSeparator>
            <BreadcrumbItem className="min-w-0">
              <h1 className="min-w-0 truncate font-semibold text-foreground">{title}</h1>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
      </div>
    </header>
  );
}
