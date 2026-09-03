import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { ПРОЯВЛЕНИЕ } from "@/lib/reveal";
import { cn } from "@/lib/utils";

/**
 * Карточка записи в коллекции.
 *
 * Анатомия одна на все выдачи: заголовок и подзаголовок слева сверху, под ними
 * ряд тегов, справа сверху — действия, проявляющиеся по наведению. До этого
 * карточка была написана трижды и каждый раз по-своему: в списке людей
 * наведение обозначалось рамкой, в каталоге сценариев — заливкой; запись
 * открывалась то иконкой, то кнопкой со словом внизу, то кликом по всему блоку.
 *
 * Кнопки «Открыть» здесь нет: кликабельна вся карточка, и об этом говорят
 * курсор и рамка. Слово в подвале называло то, что
 * в сетке записей и так значит «перейти», и занимало отдельную строку
 * у каждой карточки.
 */

export type RecordCardTagSpec = {
  label: string;
  icon?: React.ReactNode;
  variant?: React.ComponentProps<typeof Badge>["variant"];
  /** Подсказка и доступное имя, когда подпись — голое значение без слова. */
  title?: string;
  "aria-label"?: string;
};

export function RecordCardTag({
  icon,
  label,
  /*
   * Вариант забирается в деструктуризацию, а не остаётся в спреде. Иначе
   * вызывающий код, передавший variant={undefined}, перезаписывал бы им
   * значение по умолчанию, и дальше срабатывал бы дефолт самого Badge —
   * "default", то есть акцентная заливка. Так теги записей однажды и стали
   * зелёными.
   */
  variant = "secondary",
  className,
  ...props
}: React.ComponentProps<typeof Badge> & {
  icon?: React.ReactNode;
  label: string;
}) {
  return (
    /*
     * shrink-0 обязателен: в ряду постоянной высоты чип не должен сжиматься
     * под соседей — иначе подпись схлопывается в многоточие раньше времени.
     */
    <Badge variant={variant} className={cn("h-6 max-w-full shrink-0 px-2.5", className)} {...props}>
      {icon}
      <span className="truncate">{label}</span>
    </Badge>
  );
}

export type RecordCardProps = Omit<React.ComponentProps<"article">, "title" | "onSelect"> & {
  title: string;
  /** Описание или должность. Пусто — строка не рисуется. */
  subtitle?: React.ReactNode;
  tags?: RecordCardTagSpec[];
  /** Правый верх. Проявляется по наведению на карточку и по фокусу внутри неё. */
  actions?: React.ReactNode;
  /** Чекбокс массового выбора в той же группе, что и остальные действия. */
  selectable?: boolean;
  checked?: boolean;
  onCheckedChange?: () => void;
  /** Адрес записи. Делает карточку настоящей ссылкой. */
  href?: string;
  /** Открыть запись. Без href — выбор без навигации. */
  onOpen?: (event: React.MouseEvent<HTMLElement>) => void;
  /** Запись выбрана: её детали показаны в соседней панели. */
  selected?: boolean;
  density?: "default" | "compact";
  dragging?: boolean;
  dropTarget?: boolean;
};

const ПЛОТНОСТЬ = {
  default: { корпус: "gap-3 p-4", заголовок: "text-[1rem]" },
  compact: { корпус: "gap-2 p-3", заголовок: "text-[0.95rem]" },
};

export function RecordCard({
  title,
  subtitle,
  tags,
  actions,
  selectable = false,
  checked = false,
  onCheckedChange,
  href,
  onOpen,
  selected = false,
  density = "default",
  dragging = false,
  dropTarget = false,
  className,
  ...props
}: RecordCardProps) {
  const кликабельна = Boolean(href || onOpen);
  const шаг = ПЛОТНОСТЬ[density];
  const естьДействия = selectable || Boolean(actions);
  /*
   * Тег без подписи не рисуется. Пустой чип занимает место и не сообщает
   * ничего — по этому же правилу карточка человека не показывает чип даты
   * со значением «—». Ловится здесь, а не у вызывающего кода: поле, которого
   * бэкенд не прислал, приходит пустым в любой выдаче.
   */
  const видимыеТеги = (tags || []).filter((tag) => tag.label && tag.label.trim());

  /*
   * Открывает запись растянутая ссылка, а не role="button" на всей карточке.
   * Псевдоэлемент ссылки накрывает карточку целиком, поэтому:
   *
   *   — точка табуляции одна, а не «карточка, потом всё, что внутри неё»;
   *   — курсор-указатель появляется на всей площади сам собой;
   *   — у ссылки работают средняя кнопка мыши и «копировать адрес»;
   *   — чекбокс и кнопки лежат выше накладки (z-10) и не спорят с ней.
   *
   * Последнее и есть причина отказа от role="button": интерактивные элементы
   * внутри кнопки недостижимы с клавиатуры и требуют ручного stopPropagation
   * на каждом.
   */
  const Открывалка = href ? "a" : "button";

  return (
    <article
      data-slot="record-card"
      data-selected={selected ? "" : undefined}
      className={cn(
        "group/card relative flex h-full w-full min-w-0 flex-col rounded-lg border bg-card text-left",
        "transition-[border-color,background-color,box-shadow,transform,opacity] duration-200",
        шаг.корпус,
        selected ? "border-primary/70 bg-muted/50" : "border-border",
        /*
         * Наведение обозначается рамкой, а не заливкой: заливка целой карточки
         * в плотной сетке читается как выбор, а не как наведение. Тон взят
         * от muted-foreground — в светлой теме рамка темнеет, в тёмной
         * светлеет, то есть в обеих становится заметнее.
         *
         * Рамка наведения выключается на время перетаскивания, а не
         * перебивается им: у hover-варианта специфичность выше.
         */
        dragging
          ? "scale-[0.985] border-primary/40 bg-muted/70 opacity-50"
          : кликабельна && "hover:border-muted-foreground/35",
        dropTarget && "border-primary bg-primary/5 ring-2 ring-primary/20",
        /*
         * Фокус подсвечивает карточку целиком, а не одну ссылку внутри неё.
         * Селектор сужен до накладки: у чекбокса и кнопок действий свои
         * кольца, и дублировать их рамкой всей карточки не нужно.
         */
        "has-[[data-record-card-open]:focus-visible]:border-ring has-[[data-record-card-open]:focus-visible]:ring-2 has-[[data-record-card-open]:focus-visible]:ring-ring/50",
        className,
      )}
      {...props}
    >
      {dropTarget ? (
        <span className="pointer-events-none absolute inset-x-3 -top-1 h-0.5 rounded-full bg-primary" />
      ) : null}

      {/*
        Заголовок с подзаголовком — один блок с шагом в 4px, а не две строки,
        разведённые шагом корпуса: между именем и описанием нужен один шаг,
        а не тот, что отделяет их от ряда тегов.

        min-h-8 держится только там, где есть действия: 32px — высота кнопки,
        и карточка без них этот пол не обязана держать. Скачка при наведении
        не будет: действия скрыты непрозрачностью, а не display, и место
        занимают всегда.
      */}
      <div className="flex flex-col gap-1">
        <div className={cn("flex items-center justify-between gap-3", естьДействия && "min-h-8")}>
          <h3 className={cn("min-w-0 font-semibold", шаг.заголовок)}>
            {кликабельна ? (
              <Открывалка
                data-record-card-open=""
                href={href}
                type={href ? undefined : "button"}
                aria-current={selected ? "true" : undefined}
                onClick={onOpen}
                className="block w-full truncate text-left outline-none after:absolute after:inset-0 after:content-['']"
              >
                {title}
              </Открывалка>
            ) : (
              <span className="block truncate">{title}</span>
            )}
          </h3>
          {естьДействия ? (
            /* z-10 поднимает действия над накладкой ссылки, иначе клик уходит в неё. */
            <div className="relative z-10 flex shrink-0 items-center gap-2 whitespace-nowrap">
              {selectable ? (
                <Checkbox
                  checked={checked}
                  onCheckedChange={onCheckedChange}
                  aria-label={`Выбрать: ${title}`}
                  /* Отмеченный чекбокс виден всегда — иначе выбор нельзя было бы снять. */
                  className={cn(!checked && ПРОЯВЛЕНИЕ.card)}
                />
              ) : null}
              {actions}
            </div>
          ) : null}
        </div>

        {/*
          Подзаголовок — две строки максимум: описание в 320-пиксельной
          карточке, обрезанное до одной, теряет половину смысла, а заголовки
          записей в полосе всё равно стоят на одной линии — они выше.
        */}
        {subtitle ? (
          <p className="line-clamp-2 text-[0.9rem] leading-5 text-muted-foreground">{subtitle}</p>
        ) : null}
      </div>

      {/* Ряд тегов переносится: высоту полосы выравнивает сетка. */}
      {видимыеТеги.length ? (
        <div className="flex flex-wrap items-center gap-2">
          {видимыеТеги.map((tag, index) => (
            <RecordCardTag
              key={`${tag.label}-${index}`}
              icon={tag.icon}
              label={tag.label}
              variant={tag.variant}
              title={tag.title}
              aria-label={tag["aria-label"]}
            />
          ))}
        </div>
      ) : null}
    </article>
  );
}
