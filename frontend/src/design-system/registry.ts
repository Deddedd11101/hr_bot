/**
 * Реестр каталога дизайн-системы.
 *
 * Это источник правды: навигация, порядок, связи и проверки строятся отсюда,
 * а не поддерживаются отдельными ручными списками. Страница обязана
 * отрисовывать ровно те блоки, которые здесь описаны, и с теми же id.
 *
 * Уровни каталога намеренно не смешиваются:
 *   foundations — токены, типографика, ритм, радиусы;
 *   primitives  — базовые элементы интерфейса;
 *   patterns    — повторяемые композиции экранов;
 *   review      — правила ревью и определение долга.
 *
 * Уровня `product` (готовые модули и journeys) пока нет: продуктовые экраны
 * не описаны как композиции. Это известный пробел, а не упущение реестра.
 */

export type KitGroup = "foundations" | "primitives" | "patterns" | "review";

export type KitFamily =
  | "tokens"
  | "type"
  | "layout"
  | "actions"
  | "fields"
  | "navigation"
  | "overlays"
  | "feedback"
  | "collections"
  | "cards"
  | "display"
  | "composition"
  | "process";

export type DocCanvas = "standard" | "workspace";

/**
 * Где компонент реально живёт.
 *
 * Каталог документирует весь кит, но не делает вид, что всё в нём
 * работает: статус отвечает на вопрос «это в продукте или мёртвый груз»
 * прямо на странице записи.
 */
export type EntryStatus =
  /** Импортируется хотя бы одним экраном продукта. */
  | "product"
  /** Существует только в этом каталоге. */
  | "showcase"
  /** Наружу не экспонируется, но нужен другому компоненту кита. */
  | "internal"
  /** Не импортируется нигде. */
  | "unused"
  /** Не компонент кита: токены, паттерны, правила. */
  | "not-a-component";

export const STATUS_LABELS: Record<EntryStatus, string> = {
  product: "В продукте",
  showcase: "Только в каталоге",
  internal: "Внутри кита",
  unused: "Не используется",
  "not-a-component": "",
};

export type CatalogEntry = {
  /** Уникальный стабильный идентификатор. Совпадает с id секции в DOM. */
  id: string;
  /**
   * Имя записи. Для компонентов кита — корневой экспорт из `sourceRef`,
   * ровно как он называется в коде. Для токенов, паттернов и правил —
   * устоявшееся английское имя: экспорта у них нет, и придумывать его нельзя.
   *
   * Человеческое объяснение живёт в `summary`, русские синонимы — в `aliases`,
   * поэтому поиск по-русски продолжает работать.
   */
  title: string;
  group: KitGroup;
  /** Смысловой раздел внутри группы. Должен существовать в NAVIGATION_SECTIONS. */
  section: string;
  /** Порядок внутри section. Уникален в паре group + section. */
  order: number;
  /** Канонический адрес блока. */
  href: string;
  /** Одно-два предложения о назначении. */
  summary: string;
  /** Путь к исходнику, если у блока есть один основной потребитель. */
  sourceRef?: string;
  tags: string[];
  aliases: string[];
  /** Только id других записей. */
  related: string[];
  canvas: DocCanvas;
  family: KitFamily;
  /**
   * Проверяется автоматически: заявленный статус обязан совпадать с
   * фактическим использованием, посчитанным из исходников.
   * См. scripts/check-registry.mjs.
   */
  status: EntryStatus;
  /**
   * Есть ли на странице живой образец. false — у компонента нет потребителя
   * в продукте, поэтому пример не поддерживается: он устареет молча.
   */
  hasLiveExample?: boolean;
  /** Состояния, которые блок обязан показывать. Пустой список — осознанный выбор. */
  requiredStates: string[];
  /**
   * Состояния из контракта семейства, которые к этому блоку не применимы.
   * Причина обязательна: это способ честно объявить исключение, а не
   * тихо вычеркнуть требование. Валидатор принимает такие пропуски.
   */
  notApplicableStates?: { state: string; reason: string }[];
  public: boolean;
};

export type NavigationSection = {
  id: string;
  group: KitGroup;
  label: string;
  order: number;
  /** Показывать папкой даже если элементов меньше трёх. */
  forceFolder?: boolean;
};

export const GROUP_LABELS: Record<KitGroup, string> = {
  foundations: "Foundations",
  primitives: "Primitives",
  patterns: "Patterns",
  review: "Review rules",
};

export const GROUP_ORDER: KitGroup[] = ["foundations", "primitives", "patterns", "review"];

export const NAVIGATION_SECTIONS: NavigationSection[] = [
  { id: "foundations-core", group: "foundations", label: "Основа", order: 1 },
  { id: "primitives-actions", group: "primitives", label: "Действия", order: 1 },
  { id: "primitives-fields", group: "primitives", label: "Поля", order: 2 },
  { id: "primitives-display", group: "primitives", label: "Отображение", order: 3 },
  { id: "primitives-overlays", group: "primitives", label: "Оверлеи", order: 4 },
  { id: "primitives-collections", group: "primitives", label: "Коллекции", order: 5 },
  { id: "primitives-navigation", group: "primitives", label: "Навигация", order: 6 },
  { id: "primitives-unused", group: "primitives", label: "Не используется", order: 7 },
  { id: "patterns-screens", group: "patterns", label: "Экраны", order: 1 },
  { id: "patterns-blocks", group: "patterns", label: "Блоки экранов", order: 2 },
  { id: "review-rules", group: "review", label: "Правила", order: 1 },
];

/**
 * Минимальные состояния по семействам.
 * Список можно дополнять под доменную семантику, но не сокращать.
 */
export const REQUIRED_STATES_BY_FAMILY: Partial<Record<KitFamily, string[]>> = {
  actions: ["default", "hover", "focus", "pending", "disabled"],
  fields: ["default", "hover", "focus", "filled", "error", "disabled"],
  navigation: ["default", "hover", "focus", "active", "keyboard"],
  overlays: ["open", "dismiss", "keyboard", "focus-return"],
  feedback: ["success", "loading", "empty", "error"],
  collections: ["hover", "focus", "selected", "empty", "long-content"],
  cards: ["default", "hover", "focus", "disabled"],
  display: ["default", "long-content"],
};

export const CATALOG: CatalogEntry[] = [
  // ---------------------------------------------------------------- foundations
  {
    id: "palette",
    title: "Palette",
    group: "foundations",
    section: "foundations-core",
    order: 1,
    href: "#palette",
    summary:
      "Семантические роли цвета и их значения в светлой и тёмной теме. Роли, а не конкретные значения, являются контрактом.",
    sourceRef: "frontend/src/index.css",
    tags: ["tokens", "color", "theme", "oklch"],
    aliases: ["палитра", "цвета", "токены", "colors"],
    related: ["typography", "radius-and-depth"],
    canvas: "standard",
    family: "tokens",
    status: "not-a-component",
    requiredStates: [],
    public: true,
  },
  {
    id: "typography",
    title: "Typography",
    group: "foundations",
    section: "foundations-core",
    order: 2,
    href: "#typography",
    summary: "Шкала размеров, начертаний и межстрочных интервалов.",
    sourceRef: "frontend/src/index.css",
    tags: ["type", "scale", "font"],
    aliases: ["типографика", "шрифт", "текст"],
    related: ["palette"],
    canvas: "standard",
    family: "type",
    status: "not-a-component",
    requiredStates: [],
    public: true,
  },
  {
    id: "spacing-rhythm",
    title: "Spacing rhythm",
    group: "foundations",
    section: "foundations-core",
    order: 3,
    href: "#spacing-rhythm",
    summary: "Шаг сетки и правила вертикального ритма между блоками.",
    tags: ["spacing", "layout", "rhythm"],
    aliases: ["ритм отступов", "отступы", "сетка"],
    related: ["radius-and-depth"],
    canvas: "standard",
    family: "layout",
    status: "not-a-component",
    requiredStates: [],
    public: true,
  },
  {
    id: "radius-and-depth",
    title: "Radius and depth",
    group: "foundations",
    section: "foundations-core",
    order: 4,
    href: "#radius-and-depth",
    summary: "Шкала скруглений и правила использования границ вместо теней.",
    tags: ["radius", "shadow", "border"],
    aliases: ["радиусы и глубина", "скругления", "тени"],
    related: ["palette", "card"],
    canvas: "standard",
    family: "layout",
    status: "not-a-component",
    requiredStates: [],
    public: true,
  },

  // ----------------------------------------------------------------- primitives
  {
    id: "buttons",
    title: "Button",
    group: "primitives",
    section: "primitives-actions",
    order: 1,
    href: "#buttons",
    summary: "Варианты и размеры кнопок, включая иконочные и деструктивные.",
    sourceRef: "frontend/src/components/ui/button.tsx",
    tags: ["action", "button", "variant"],
    aliases: ["кнопки", "button", "кнопка"],
    related: ["field", "confirmation-dialog"],
    canvas: "standard",
    family: "actions",
    status: "product",
    requiredStates: ["default", "hover", "focus", "pending", "disabled"],
    public: true,
  },
  {
    id: "field",
    title: "Field",
    group: "primitives",
    section: "primitives-fields",
    order: 1,
    href: "#field",
    summary: "Подпись, пояснение и сообщение об ошибке вокруг любого контрола. Единая обвязка для всех полей формы.",
    sourceRef: "frontend/src/components/ui/field.tsx",
    tags: ["form", "label", "wrapper"],
    aliases: ["обёртка поля", "обёртка", "подпись"],
    related: ["input", "select"],
    canvas: "standard",
    family: "fields",
    status: "product",
    requiredStates: ["default", "hover", "focus", "filled", "error", "disabled"],
    public: true,
  },
  {
    id: "input",
    title: "Input",
    group: "primitives",
    section: "primitives-fields",
    order: 2,
    href: "#input",
    summary: "Однострочный ввод текста.",
    sourceRef: "frontend/src/components/ui/input.tsx",
    tags: ["input", "text", "form"],
    aliases: ["текстовое поле", "инпут", "поле ввода"],
    related: ["field", "textarea"],
    canvas: "standard",
    family: "fields",
    status: "product",
    requiredStates: ["default", "hover", "focus", "filled", "error", "disabled"],
    public: true,
  },
  {
    id: "textarea",
    title: "Textarea",
    group: "primitives",
    section: "primitives-fields",
    order: 3,
    href: "#textarea",
    summary: "Ввод текста в несколько строк: описания, тексты сообщений бота.",
    sourceRef: "frontend/src/components/ui/textarea.tsx",
    tags: ["textarea", "multiline"],
    aliases: ["многострочное поле", "текстовая область"],
    related: ["input", "field"],
    canvas: "standard",
    family: "fields",
    status: "product",
    requiredStates: ["default", "hover", "focus", "filled", "error", "disabled"],
    public: true,
  },
  {
    id: "telegram-rich-text-editor",
    title: "TelegramRichTextEditor",
    group: "primitives",
    section: "primitives-fields",
    order: 4,
    href: "#telegram-rich-text-editor",
    summary: "Визуальный редактор ограниченного TelegramSafeHTML-подмножества с тегами, ссылками и undo/redo.",
    sourceRef: "frontend/src/components/ui/telegram-rich-text-editor.tsx",
    tags: ["editor", "telegram", "rich text", "formatting"],
    aliases: ["редактор сообщений", "форматированный текст"],
    related: ["textarea", "field"],
    canvas: "standard",
    family: "fields",
    status: "product",
    requiredStates: ["default", "hover", "focus", "filled", "error", "disabled", "keyboard"],
    public: true,
  },
  {
    id: "select",
    title: "Select",
    group: "primitives",
    section: "primitives-fields",
    order: 5,
    href: "#select",
    summary: "Выбор одного значения из списка. Отдаёт null при очистке — обработчик обязан это учитывать.",
    sourceRef: "frontend/src/components/ui/select.tsx",
    tags: ["select", "dropdown", "choice"],
    aliases: ["выбор из списка", "селект", "выпадающий список"],
    related: ["field"],
    canvas: "standard",
    family: "fields",
    status: "product",
    /*
     * open добавлен сверх минимума семейства: у селекта открытое состояние
     * несёт и подсветку триггера, и поворот шеврона, и его надо проверять.
     */
    requiredStates: ["default", "hover", "focus", "open", "filled", "error", "disabled"],
    public: true,
  },
  {
    id: "checkbox",
    title: "Checkbox",
    group: "primitives",
    section: "primitives-fields",
    order: 6,
    href: "#checkbox",
    summary: "Независимый переключатель да/нет.",
    sourceRef: "frontend/src/components/ui/checkbox.tsx",
    tags: ["checkbox", "boolean"],
    aliases: ["флажок", "чекбокс", "галочка"],
    related: ["switch", "radio-group"],
    canvas: "standard",
    family: "fields",
    status: "product",
    requiredStates: ["default", "hover", "focus", "filled", "error", "disabled"],
    public: true,
  },
  {
    id: "radio-group",
    title: "RadioGroup",
    group: "primitives",
    section: "primitives-fields",
    order: 7,
    href: "#radio-group",
    summary: "Выбор ровно одного варианта изнескольких взаимоисключающих.",
    sourceRef: "frontend/src/components/ui/radio-group.tsx",
    tags: ["radio", "choice"],
    aliases: ["выбор одного", "радиокнопки"],
    related: ["checkbox", "select"],
    canvas: "standard",
    family: "fields",
    status: "showcase",
    requiredStates: ["default", "hover", "focus", "filled", "error", "disabled"],
    public: true,
  },
  {
    id: "switch",
    title: "Switch",
    group: "primitives",
    section: "primitives-fields",
    order: 8,
    href: "#switch",
    summary: "Немедленное включение или выключение режима. В отличие от флажка не требует подтверждения формой.",
    sourceRef: "frontend/src/components/ui/switch.tsx",
    tags: ["switch", "toggle"],
    aliases: ["тумблер", "переключатель"],
    related: ["checkbox"],
    canvas: "standard",
    family: "fields",
    status: "showcase",
    requiredStates: ["default", "hover", "focus", "filled", "error", "disabled"],
    public: true,
  },
  {
    id: "date-picker",
    title: "DatePicker",
    group: "primitives",
    section: "primitives-fields",
    order: 9,
    href: "#date-picker",
    summary: "Выбор даты, времени и даты со временем. Календарь и список времени вместо нативных браузерных попапов.",
    sourceRef: "frontend/src/components/ui/date-picker.tsx",
    tags: ["date", "time", "calendar"],
    aliases: ["дата и время", "дата", "календарь", "время"],
    related: ["field", "select"],
    canvas: "standard",
    family: "fields",
    status: "product",
    requiredStates: ["default", "hover", "focus", "filled", "error", "disabled"],
    public: true,
  },
  {
    id: "theme-switch",
    title: "ThemeSwitch",
    group: "primitives",
    section: "primitives-actions",
    order: 2,
    href: "#theme-switch",
    summary: "Переключение светлой и тёмной темы с анимацией раскрытия. Живёт в настройках админки.",
    sourceRef: "frontend/src/components/ui/theme-switch.tsx",
    tags: ["theme", "toggle", "motion"],
    aliases: ["переключатель темы", "тема", "тёмная тема"],
    related: ["palette"],
    canvas: "standard",
    family: "actions",
    status: "product",
    requiredStates: ["default", "hover", "focus", "disabled", "reduced-motion"],
    notApplicableStates: [
      { state: "pending", reason: "переключение темы синхронное, ожидания нет" },
    ],
    public: true,
  },

  {
    id: "badge",
    title: "Badge",
    group: "primitives",
    section: "primitives-display",
    order: 1,
    href: "#badge",
    summary: "Короткая метка состояния: стадия сотрудника, этап кандидата, тип записи.",
    sourceRef: "frontend/src/components/ui/badge.tsx",
    tags: ["badge", "status", "label"],
    aliases: ["бейдж", "статус", "метка"],
    related: ["card", "list-page-item"],
    canvas: "standard",
    family: "display",
    status: "product",
    requiredStates: ["default", "long-content"],
    public: true,
  },
  {
    id: "card",
    title: "Card",
    group: "primitives",
    section: "primitives-display",
    order: 2,
    href: "#card",
    summary: "Поверхность контента: карточки, панели, блоки экрана.",
    sourceRef: "frontend/src/components/ui/card.tsx",
    tags: ["card", "surface", "panel"],
    aliases: ["карточка", "панель"],
    related: ["badge", "radius-and-depth"],
    canvas: "standard",
    family: "cards",
    status: "product",
    requiredStates: ["default", "hover", "focus", "disabled"],
    public: true,
  },
  {
    id: "avatar",
    title: "Avatar",
    group: "primitives",
    section: "primitives-display",
    order: 3,
    href: "#avatar",
    summary: "Изображение или инициалы человека. В продукте пока не применяется.",
    sourceRef: "frontend/src/components/ui/avatar.tsx",
    tags: ["avatar", "person"],
    aliases: ["аватар"],
    related: ["badge"],
    canvas: "standard",
    family: "display",
    status: "showcase",
    requiredStates: ["default", "long-content"],
    public: true,
  },
  {
    id: "progress",
    title: "Progress",
    group: "primitives",
    section: "primitives-display",
    order: 4,
    href: "#progress",
    summary: "Полоса выполнения, в том числе прогресс оценки к целевому грейду.",
    sourceRef: "frontend/src/components/ui/progress.tsx",
    tags: ["progress", "bar"],
    aliases: ["прогресс", "полоса"],
    related: ["skeleton"],
    canvas: "standard",
    family: "display",
    status: "product",
    requiredStates: ["default", "long-content"],
    public: true,
  },
  {
    id: "skeleton",
    title: "Skeleton",
    group: "primitives",
    section: "primitives-display",
    order: 5,
    href: "#skeleton",
    summary: "Заглушка на время загрузки. Держит раскладку, пока данные не пришли.",
    sourceRef: "frontend/src/components/ui/skeleton.tsx",
    tags: ["skeleton", "loading"],
    aliases: ["скелетон", "загрузка"],
    related: ["progress"],
    canvas: "standard",
    family: "display",
    status: "product",
    requiredStates: ["default", "long-content"],
    public: true,
  },
  {
    id: "dialog",
    title: "Dialog",
    group: "primitives",
    section: "primitives-overlays",
    order: 1,
    href: "#dialog",
    summary: "Модальное окно для задачи, которую нельзя выполнить на месте.",
    sourceRef: "frontend/src/components/ui/dialog.tsx",
    tags: ["dialog", "modal"],
    aliases: ["диалог", "модалка"],
    related: ["confirm-action", "dropdown-menu"],
    canvas: "standard",
    family: "overlays",
    status: "product",
    requiredStates: ["open", "dismiss", "keyboard", "focus-return"],
    public: true,
  },
  {
    id: "confirm-action",
    title: "ConfirmAction",
    group: "primitives",
    section: "primitives-overlays",
    order: 2,
    href: "#confirm-action",
    summary: "Подтверждение необратимого действия. Обязателен для удаления и массовых рассылок вместо window.confirm.",
    sourceRef: "frontend/src/components/ui/confirm-action.tsx",
    tags: ["confirm", "destructive"],
    aliases: ["подтверждение", "удаление"],
    related: ["dialog", "buttons"],
    canvas: "standard",
    family: "overlays",
    status: "product",
    requiredStates: ["open", "dismiss", "keyboard", "focus-return"],
    public: true,
  },
  {
    id: "dropdown-menu",
    title: "DropdownMenu",
    group: "primitives",
    section: "primitives-overlays",
    order: 3,
    href: "#dropdown-menu",
    summary: "Меню действий у элемента. В продукте пока не применяется — действия вынесены отдельными кнопками.",
    sourceRef: "frontend/src/components/ui/dropdown-menu.tsx",
    tags: ["menu", "dropdown", "actions"],
    aliases: ["выпадающее меню", "меню", "действия"],
    related: ["dialog"],
    canvas: "standard",
    family: "overlays",
    status: "showcase",
    requiredStates: ["open", "dismiss", "keyboard", "focus-return"],
    public: true,
  },
  {
    id: "tooltip",
    title: "Tooltip",
    group: "primitives",
    section: "primitives-overlays",
    order: 4,
    href: "#tooltip",
    summary: "Короткое пояснение при наведении. Не заменяет подпись: с клавиатуры и на сенсоре недоступна.",
    sourceRef: "frontend/src/components/ui/tooltip.tsx",
    tags: ["tooltip", "hint"],
    aliases: ["подсказка"],
    related: ["dropdown-menu"],
    canvas: "standard",
    family: "overlays",
    status: "showcase",
    requiredStates: ["open", "dismiss", "keyboard"],
    notApplicableStates: [{ state: "focus-return", reason: "подсказка не забирает фокус, возвращать нечего" }],
    public: true,
  },
  {
    id: "table",
    title: "Table",
    group: "primitives",
    section: "primitives-collections",
    order: 1,
    href: "#table",
    summary:
      "Табличное представление данных. Используется в списке людей: вся выдача — одна карточка, строки разделены линиями, шапка сортирует по колонкам. Строку открывает ссылка в ячейке имени и клик по её площади.",
    sourceRef: "frontend/src/components/ui/table.tsx",
    tags: ["table", "data", "rows", "sort"],
    aliases: ["таблица"],
    related: ["list-page-item", "badge"],
    canvas: "workspace",
    family: "collections",
    status: "product",
    requiredStates: ["hover", "focus", "empty", "long-content"],
    notApplicableStates: [{ state: "selected", reason: "выбор строк не реализован в компоненте" }],
    public: true,
  },
  {
    id: "scroll-area",
    title: "ScrollArea",
    group: "primitives",
    section: "primitives-collections",
    order: 2,
    href: "#scroll-area",
    summary: "Прокручиваемая область с оформленной полосой вместо системной.",
    sourceRef: "frontend/src/components/ui/scroll-area.tsx",
    tags: ["scroll", "overflow"],
    aliases: ["область прокрутки", "прокрутка"],
    related: ["table"],
    canvas: "standard",
    family: "collections",
    status: "product",
    requiredStates: ["hover", "focus", "empty", "long-content"],
    notApplicableStates: [{ state: "selected", reason: "область прокрутки не имеет выбираемых элементов" }],
    public: true,
  },
  {
    id: "emoji-picker",
    title: "EmojiPickerPopover",
    group: "primitives",
    section: "primitives-collections",
    order: 3,
    href: "#emoji-picker",
    summary: "Вставка эмодзи в текст сообщения бота.",
    sourceRef: "frontend/src/components/ui/emoji-picker-popover.tsx",
    tags: ["emoji", "picker"],
    aliases: ["выбор эмодзи", "эмодзи", "смайлы"],
    related: ["textarea"],
    canvas: "standard",
    family: "fields",
    status: "product",
    requiredStates: ["default", "hover", "focus", "disabled"],
    notApplicableStates: [{ state: "filled", reason: "выбор эмодзи не имеет собственного значения" }, { state: "error", reason: "ошибочного состояния у выбора эмодзи нет" }],
    public: true,
  },
  {
    id: "record-card",
    title: "RecordCard",
    group: "primitives",
    section: "primitives-collections",
    order: 4,
    href: "#record-card",
    summary:
      "Карточка записи в выдаче: заголовок и подзаголовок слева сверху, ряд тегов под ними, действия по наведению справа. Открывает запись вся карточка — кнопки со словом в подвале нет.",
    sourceRef: "frontend/src/components/ui/record-card.tsx",
    tags: ["card", "record", "list", "collection"],
    aliases: ["карточка записи", "элемент выдачи", "карточка списка"],
    related: ["card", "badge", "checkbox", "list-page-item"],
    canvas: "standard",
    family: "collections",
    status: "product",
    requiredStates: ["hover", "focus", "selected", "empty", "long-content"],
    public: true,
  },
  {
    id: "breadcrumb",
    title: "Breadcrumb",
    group: "primitives",
    section: "primitives-navigation",
    order: 1,
    href: "#breadcrumb",
    summary: "Путь до текущего экрана. В продукте пока не применяется: навигация собрана вручную в шелле.",
    sourceRef: "frontend/src/components/ui/breadcrumb.tsx",
    tags: ["breadcrumb", "path"],
    aliases: ["хлебные крошки", "крошки", "путь"],
    related: ["tabs"],
    canvas: "standard",
    family: "navigation",
    status: "showcase",
    requiredStates: ["default", "hover", "focus", "active", "keyboard"],
    public: true,
  },
  {
    id: "tabs",
    title: "Tabs",
    group: "primitives",
    section: "primitives-navigation",
    order: 2,
    href: "#tabs",
    summary: "Переключение между видами одного экрана без смены адреса.",
    sourceRef: "frontend/src/components/ui/tabs.tsx",
    tags: ["tabs", "switch"],
    aliases: ["вкладки", "табы"],
    related: ["breadcrumb"],
    canvas: "standard",
    family: "navigation",
    status: "product",
    requiredStates: ["default", "hover", "focus", "active", "keyboard"],
    public: true,
  },

  {
    id: "alert",
    title: "Alert",
    group: "primitives",
    section: "primitives-display",
    order: 6,
    href: "#alert",
    summary: "Постоянное сообщение в потоке страницы: ошибка операции, предупреждение, пояснение.",
    sourceRef: "frontend/src/components/ui/alert.tsx",
    tags: ["alert"],
    aliases: ["сообщение"],
    related: [],
    canvas: "standard",
    family: "feedback",
    status: "product",
    hasLiveExample: true,
    requiredStates: ["success", "loading", "empty", "error"],
    public: true,
  },
  {
    id: "empty",
    title: "Empty",
    group: "primitives",
    section: "primitives-display",
    order: 7,
    href: "#empty",
    summary: "Что показать, когда данных нет. Объясняет причину и подсказывает следующий шаг.",
    sourceRef: "frontend/src/components/ui/empty.tsx",
    tags: ["empty"],
    aliases: ["пустое состояние"],
    related: [],
    canvas: "standard",
    family: "feedback",
    status: "product",
    hasLiveExample: true,
    requiredStates: ["success", "loading", "empty", "error"],
    public: true,
  },
  {
    id: "popover",
    title: "Popover",
    group: "primitives",
    section: "primitives-overlays",
    order: 5,
    href: "#popover",
    summary: "Всплывающая панель у элемента. В отличие от диалога не блокирует остальную страницу.",
    sourceRef: "frontend/src/components/ui/popover.tsx",
    tags: ["popover"],
    aliases: ["поповер"],
    related: [],
    canvas: "standard",
    family: "overlays",
    status: "product",
    hasLiveExample: true,
    requiredStates: ["open", "dismiss", "keyboard", "focus-return"],
    public: true,
  },
  {
    id: "separator",
    title: "Separator",
    group: "primitives",
    section: "primitives-display",
    order: 8,
    href: "#separator",
    summary: "Линия между смысловыми частями блока.",
    sourceRef: "frontend/src/components/ui/separator.tsx",
    tags: ["separator"],
    aliases: ["разделитель"],
    related: [],
    canvas: "standard",
    family: "display",
    status: "product",
    hasLiveExample: true,
    requiredStates: ["default", "long-content"],
    public: true,
  },
  {
    id: "page-header",
    title: "PageHeader",
    group: "primitives",
    section: "primitives-display",
    order: 9,
    href: "#page-header",
    summary:
      "Две полосы заголовка общей геометрии: списочная с именем раздела и счётчиком и детальная с хлебной крошкой «Раздел / Имя записи». Не карточка — только разделитель снизу.",
    sourceRef: "frontend/src/components/ui/page-header.tsx",
    tags: ["header", "page", "layout", "title"],
    aliases: ["полоса заголовка", "шапка страницы", "заголовок"],
    related: ["separator", "breadcrumb", "page-filters"],
    canvas: "standard",
    family: "layout",
    status: "product",
    requiredStates: [],
    public: true,
  },
  {
    id: "page-filters",
    title: "PageFilters",
    group: "primitives",
    section: "primitives-display",
    order: 10,
    href: "#page-filters",
    summary:
      "Полоса фильтров выдачи: набор, поиск, селекты, представление. Идёт сразу за заголовком и ни во что не завёрнута.",
    sourceRef: "frontend/src/components/ui/page-filters.tsx",
    tags: ["filters", "search", "toolbar", "layout"],
    aliases: ["полоса фильтров", "фильтры", "поиск", "тулбар"],
    related: ["page-header", "input-group", "select"],
    canvas: "standard",
    family: "layout",
    status: "product",
    requiredStates: ["default", "long-content"],
    public: true,
  },
  {
    id: "page-row",
    title: "PageRow",
    group: "primitives",
    section: "primitives-display",
    order: 11,
    href: "#page-row",
    summary:
      "Полоса страницы с равными долями. Принимает количество колонок, а не шаблон: дробей и col-span в страничной сетке не бывает.",
    sourceRef: "frontend/src/components/ui/page-row.tsx",
    tags: ["grid", "row", "columns", "layout"],
    aliases: ["полоса модулей", "сетка", "полоса", "колонки"],
    related: ["page-section", "spacing-rhythm"],
    canvas: "standard",
    family: "layout",
    status: "product",
    requiredStates: [],
    public: true,
  },
  {
    id: "page-section",
    title: "PageSection",
    group: "primitives",
    section: "primitives-display",
    order: 12,
    href: "#page-section",
    summary:
      "Модуль страницы: шапка постоянной высоты и одно из тел под ней. Описания под заголовком нет — оно ломало полосу равных долей.",
    sourceRef: "frontend/src/components/ui/page-section.tsx",
    tags: ["section", "module", "card", "layout"],
    aliases: ["модуль страницы", "модуль", "секция", "блок"],
    related: ["card", "page-row", "empty", "composition-rules"],
    canvas: "standard",
    family: "layout",
    status: "product",
    requiredStates: ["default", "empty", "long-content"],
    public: true,
  },
  {
    id: "alert-dialog",
    title: "AlertDialog",
    group: "primitives",
    section: "primitives-overlays",
    order: 6,
    href: "#alert-dialog",
    summary: "Основа для ConfirmAction. Напрямую не применяется: подтверждения идут через ConfirmAction.",
    sourceRef: "frontend/src/components/ui/alert-dialog.tsx",
    tags: ["alert-dialog"],
    aliases: ["диалог подтверждения"],
    related: [],
    canvas: "standard",
    family: "overlays",
    status: "internal",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "calendar",
    title: "Calendar",
    group: "primitives",
    section: "primitives-fields",
    order: 10,
    href: "#calendar",
    summary: "Основа для DatePicker. Напрямую не применяется. Локализован на английский — расхождение с русским интерфейсом.",
    sourceRef: "frontend/src/components/ui/calendar.tsx",
    tags: ["calendar"],
    aliases: ["календарь"],
    related: [],
    canvas: "standard",
    family: "fields",
    status: "internal",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "label",
    title: "Label",
    group: "primitives",
    section: "primitives-fields",
    order: 11,
    href: "#label",
    summary: "Основа для FieldLabel. Напрямую не применяется: подписи ставятся через Field.",
    sourceRef: "frontend/src/components/ui/label.tsx",
    tags: ["label"],
    aliases: ["подпись"],
    related: [],
    canvas: "standard",
    family: "fields",
    status: "internal",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "accordion",
    title: "Accordion",
    group: "primitives",
    section: "primitives-unused",
    order: 1,
    href: "#accordion",
    summary: "Сворачиваемые секции списка.",
    sourceRef: "frontend/src/components/ui/accordion.tsx",
    tags: ["accordion"],
    aliases: ["аккордеон"],
    related: [],
    canvas: "standard",
    family: "collections",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "aspect-ratio",
    title: "AspectRatio",
    group: "primitives",
    section: "primitives-unused",
    order: 2,
    href: "#aspect-ratio",
    summary: "Контейнер с фиксированным соотношением сторон.",
    sourceRef: "frontend/src/components/ui/aspect-ratio.tsx",
    tags: ["aspect-ratio"],
    aliases: ["пропорции"],
    related: [],
    canvas: "standard",
    family: "layout",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "button-group",
    title: "ButtonGroup",
    group: "primitives",
    section: "primitives-unused",
    order: 3,
    href: "#button-group",
    summary: "Несколько кнопок как единый контрол.",
    sourceRef: "frontend/src/components/ui/button-group.tsx",
    tags: ["button-group"],
    aliases: ["группа кнопок"],
    related: [],
    canvas: "standard",
    family: "actions",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "carousel",
    title: "Carousel",
    group: "primitives",
    section: "primitives-unused",
    order: 4,
    href: "#carousel",
    summary: "Горизонтальная лента с перелистыванием.",
    sourceRef: "frontend/src/components/ui/carousel.tsx",
    tags: ["carousel"],
    aliases: ["карусель"],
    related: [],
    canvas: "standard",
    family: "collections",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "chart",
    title: "ChartContainer",
    group: "primitives",
    section: "primitives-unused",
    order: 5,
    href: "#chart",
    summary: "Обёртка над recharts. Радар текущих и целевых уровней в оценке грейда.",
    sourceRef: "frontend/src/components/ui/chart.tsx",
    tags: ["chart"],
    aliases: ["график"],
    related: [],
    canvas: "standard",
    family: "collections",
    status: "product",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "collapsible",
    title: "Collapsible",
    group: "primitives",
    section: "primitives-unused",
    order: 6,
    href: "#collapsible",
    summary: "Одна сворачиваемая секция.",
    sourceRef: "frontend/src/components/ui/collapsible.tsx",
    tags: ["collapsible"],
    aliases: ["сворачиваемый блок"],
    related: [],
    canvas: "standard",
    family: "collections",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "command",
    title: "Command",
    group: "primitives",
    section: "primitives-unused",
    order: 7,
    href: "#command",
    summary: "Поиск по действиям с клавиатуры. Тянет за собой input-group, который применяется и сам по себе.",
    sourceRef: "frontend/src/components/ui/command.tsx",
    tags: ["command"],
    aliases: ["командная палитра"],
    related: [],
    canvas: "standard",
    family: "overlays",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "context-menu",
    title: "ContextMenu",
    group: "primitives",
    section: "primitives-unused",
    order: 8,
    href: "#context-menu",
    summary: "Меню по правой кнопке мыши.",
    sourceRef: "frontend/src/components/ui/context-menu.tsx",
    tags: ["context-menu"],
    aliases: ["контекстное меню"],
    related: [],
    canvas: "standard",
    family: "overlays",
    status: "internal",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "direction",
    title: "DirectionProvider",
    group: "primitives",
    section: "primitives-unused",
    order: 9,
    href: "#direction",
    summary: "Провайдер направления письма для RTL.",
    sourceRef: "frontend/src/components/ui/direction.tsx",
    tags: ["direction"],
    aliases: ["направление текста"],
    related: [],
    canvas: "standard",
    family: "layout",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "drawer",
    title: "Drawer",
    group: "primitives",
    section: "primitives-unused",
    order: 10,
    href: "#drawer",
    summary: "Панель, выезжающая снизу. Мобильный аналог диалога.",
    sourceRef: "frontend/src/components/ui/drawer.tsx",
    tags: ["drawer"],
    aliases: ["выдвижная панель"],
    related: [],
    canvas: "standard",
    family: "overlays",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "hover-card",
    title: "HoverCard",
    group: "primitives",
    section: "primitives-unused",
    order: 11,
    href: "#hover-card",
    summary: "Расширенная подсказка с содержимым.",
    sourceRef: "frontend/src/components/ui/hover-card.tsx",
    tags: ["hover-card"],
    aliases: ["карточка при наведении"],
    related: [],
    canvas: "standard",
    family: "overlays",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "input-group",
    title: "InputGroup",
    group: "primitives",
    section: "primitives-fields",
    order: 12,
    href: "#input-group",
    summary: "Поле с приставками и кнопками внутри. На нём собрано поле поиска в полосе фильтров.",
    sourceRef: "frontend/src/components/ui/input-group.tsx",
    tags: ["input-group"],
    aliases: ["группа полей"],
    related: ["input", "page-filters"],
    canvas: "standard",
    family: "fields",
    status: "internal",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "input-otp",
    title: "InputOTP",
    group: "primitives",
    section: "primitives-unused",
    order: 13,
    href: "#input-otp",
    summary: "Посимвольный ввод одноразового кода.",
    sourceRef: "frontend/src/components/ui/input-otp.tsx",
    tags: ["input-otp"],
    aliases: ["ввод кода"],
    related: [],
    canvas: "standard",
    family: "fields",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "item",
    title: "Item",
    group: "primitives",
    section: "primitives-unused",
    order: 14,
    href: "#item",
    summary: "Универсальная строка списка с медиа и действиями.",
    sourceRef: "frontend/src/components/ui/item.tsx",
    tags: ["item"],
    aliases: ["элемент списка"],
    related: [],
    canvas: "standard",
    family: "collections",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "kbd",
    title: "Kbd",
    group: "primitives",
    section: "primitives-unused",
    order: 15,
    href: "#kbd",
    summary: "Отображение клавиатурного сочетания.",
    sourceRef: "frontend/src/components/ui/kbd.tsx",
    tags: ["kbd"],
    aliases: ["клавиша"],
    related: [],
    canvas: "standard",
    family: "display",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "menubar",
    title: "Menubar",
    group: "primitives",
    section: "primitives-unused",
    order: 16,
    href: "#menubar",
    summary: "Горизонтальная строка меню как в настольных приложениях.",
    sourceRef: "frontend/src/components/ui/menubar.tsx",
    tags: ["menubar"],
    aliases: ["строка меню"],
    related: [],
    canvas: "standard",
    family: "navigation",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "native-select",
    title: "NativeSelect",
    group: "primitives",
    section: "primitives-unused",
    order: 17,
    href: "#native-select",
    summary: "Системный выпадающий список. Оформлению не поддаётся и различается между браузерами.",
    sourceRef: "frontend/src/components/ui/native-select.tsx",
    tags: ["native-select"],
    aliases: ["нативный select"],
    related: [],
    canvas: "standard",
    family: "fields",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "navigation-menu",
    title: "NavigationMenu",
    group: "primitives",
    section: "primitives-unused",
    order: 18,
    href: "#navigation-menu",
    summary: "Горизонтальное меню с выпадающими разделами.",
    sourceRef: "frontend/src/components/ui/navigation-menu.tsx",
    tags: ["navigation-menu"],
    aliases: ["меню навигации"],
    related: [],
    canvas: "standard",
    family: "navigation",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "pagination",
    title: "Pagination",
    group: "primitives",
    section: "primitives-unused",
    order: 19,
    href: "#pagination",
    summary: "Переход по страницам списка. Списки в продукте пока грузятся целиком.",
    sourceRef: "frontend/src/components/ui/pagination.tsx",
    tags: ["pagination"],
    aliases: ["постраничная навигация"],
    related: [],
    canvas: "standard",
    family: "navigation",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "resizable",
    title: "ResizablePanelGroup",
    group: "primitives",
    section: "primitives-unused",
    order: 20,
    href: "#resizable",
    summary: "Панели с перетаскиваемой границей.",
    sourceRef: "frontend/src/components/ui/resizable.tsx",
    tags: ["resizable"],
    aliases: ["изменяемые панели"],
    related: [],
    canvas: "standard",
    family: "layout",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "sheet",
    title: "Sheet",
    group: "primitives",
    section: "primitives-unused",
    order: 21,
    href: "#sheet",
    summary: "Панель, выезжающая сбоку.",
    sourceRef: "frontend/src/components/ui/sheet.tsx",
    tags: ["sheet"],
    aliases: ["боковая панель"],
    related: [],
    canvas: "standard",
    family: "overlays",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "slider",
    title: "Slider",
    group: "primitives",
    section: "primitives-unused",
    order: 22,
    href: "#slider",
    summary: "Выбор значения из диапазона.",
    sourceRef: "frontend/src/components/ui/slider.tsx",
    tags: ["slider"],
    aliases: ["ползунок"],
    related: [],
    canvas: "standard",
    family: "fields",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "sonner",
    title: "Toaster",
    group: "primitives",
    section: "primitives-unused",
    order: 23,
    href: "#sonner",
    summary: "Обёртка над тостами, настраивающая тему и токены по контракту. Не используется никем: единственное место с тостами импортирует библиотеку напрямую, минуя обёртку.",
    sourceRef: "frontend/src/components/ui/sonner.tsx",
    tags: ["sonner"],
    aliases: ["тосты"],
    related: [],
    canvas: "standard",
    family: "feedback",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "spinner",
    title: "Spinner",
    group: "primitives",
    section: "primitives-unused",
    order: 24,
    href: "#spinner",
    summary: "Единственный компонент кита с состоянием загрузки — и он не используется.",
    sourceRef: "frontend/src/components/ui/spinner.tsx",
    tags: ["spinner"],
    aliases: ["индикатор загрузки"],
    related: [],
    canvas: "standard",
    family: "feedback",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "time-picker",
    title: "TimePicker",
    group: "primitives",
    section: "primitives-unused",
    order: 25,
    href: "#time-picker",
    summary: "Отдельный компонент выбора времени. Дублирует TimeSelect из date-picker, который и применяется.",
    sourceRef: "frontend/src/components/ui/time-picker.tsx",
    tags: ["time-picker"],
    aliases: ["выбор времени"],
    related: [],
    canvas: "standard",
    family: "fields",
    status: "unused",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "toggle",
    title: "Toggle",
    group: "primitives",
    section: "primitives-unused",
    order: 26,
    href: "#toggle",
    summary: "Кнопка с состоянием нажато. Используется только компонентом toggle-group, который сам не применяется.",
    sourceRef: "frontend/src/components/ui/toggle.tsx",
    tags: ["toggle"],
    aliases: ["переключатель-кнопка"],
    related: [],
    canvas: "standard",
    family: "actions",
    status: "internal",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },
  {
    id: "toggle-group",
    title: "ToggleGroup",
    group: "primitives",
    section: "primitives-unused",
    order: 27,
    href: "#toggle-group",
    summary: "Несколько переключателей как единый выбор.",
    sourceRef: "frontend/src/components/ui/toggle-group.tsx",
    tags: ["toggle-group"],
    aliases: ["группа переключателей"],
    related: [],
    canvas: "standard",
    family: "actions",
    status: "product",
    hasLiveExample: false,
    requiredStates: [],
    public: true,
  },

  // ------------------------------------------------------------------- patterns
  {
    id: "record-with-tabs",
    title: "Record with tabs",
    group: "patterns",
    section: "patterns-screens",
    order: 7,
    href: "#record-with-tabs",
    summary: "Общая шапка записи, независимые вкладки профиля и оценки. Состояние формы сохраняется при переключении.",
    sourceRef: "frontend/src/employee-detail/page.tsx",
    tags: ["record", "tabs", "detail"],
    aliases: ["грейд"],
    related: ["tabs", "detail-page-blocks"],
    canvas: "workspace",
    family: "composition",
    status: "not-a-component",
    requiredStates: ["default", "empty", "loading", "error", "keyboard"],
    public: true,
  },
  {
    id: "settings-form",
    title: "Settings form",
    group: "patterns",
    section: "patterns-screens",
    order: 1,
    href: "#settings-form",
    summary: "Композиция экрана настроек: группы полей и сохранение.",
    sourceRef: "frontend/src/settings/page.tsx",
    tags: ["settings", "form", "screen"],
    aliases: ["форма настроек", "настройки"],
    related: ["field"],
    canvas: "workspace",
    family: "composition",
    status: "not-a-component",
    requiredStates: ["default", "loading", "error"],
    public: true,
  },
  {
    id: "bot-menu-editor",
    title: "Bot menu editor",
    group: "patterns",
    section: "patterns-screens",
    order: 2,
    href: "#bot-menu-editor",
    summary: "Композиция редактора меню бота: наборы, кнопки, привязка документов.",
    sourceRef: "frontend/src/bot-menu/page.tsx",
    tags: ["bot", "menu", "editor"],
    aliases: ["редактор меню бота", "меню бота"],
    related: ["settings-form"],
    canvas: "workspace",
    family: "composition",
    status: "not-a-component",
    requiredStates: ["default", "empty", "loading", "error"],
    public: true,
  },
  {
    id: "shell-sidebar-pattern",
    title: "Shell sidebar",
    group: "patterns",
    section: "patterns-screens",
    order: 3,
    href: "#shell-sidebar-pattern",
    summary: "Оболочка админки: боковая навигация, роль оператора и выход. Живёт вне сборки Vite, со своей палитрой --shell-*.",
    sourceRef: "frontend/src/shell-sidebar/page.tsx",
    tags: ["shell", "sidebar", "nav"],
    aliases: ["каркас и сайдбар", "каркас", "оболочка"],
    related: ["breadcrumb"],
    canvas: "workspace",
    family: "navigation",
    status: "not-a-component",
    requiredStates: ["default", "hover", "focus", "active", "keyboard"],
    public: true,
  },
  {
    id: "bulk-action-console",
    title: "Mass broadcast",
    group: "patterns",
    section: "patterns-screens",
    order: 4,
    href: "#bulk-action-console",
    summary:
      "Выбор аудитории, предпросмотр охвата и подтверждение немедленного запуска. Живёт диалогом в детали сценария и опроса и страницей сообщений; общий журнал — на дашборде.",
    sourceRef: "frontend/src/mass-broadcast/broadcast-dialog.tsx",
    tags: ["bulk", "audience", "preview", "broadcast"],
    aliases: ["рассылка", "массовые действия", "сообщения"],
    related: ["confirmation-dialog"],
    canvas: "workspace",
    family: "composition",
    status: "not-a-component",
    requiredStates: ["default", "empty", "loading", "error"],
    public: true,
  },
  {
    id: "workspace-builder",
    title: "Workspace builder",
    group: "patterns",
    section: "patterns-screens",
    order: 5,
    href: "#workspace-builder",
    summary: "Мастер-деталь конструктора: список шагов слева, редактор справа.",
    sourceRef: "frontend/src/scenario-workspace/page.tsx",
    tags: ["workspace", "builder", "master-detail"],
    aliases: ["конструктор сценариев", "сценарии", "конструктор"],
    related: ["detail-page-blocks"],
    canvas: "workspace",
    family: "composition",
    status: "not-a-component",
    requiredStates: ["default", "empty", "loading", "error"],
    public: true,
  },
  {
    id: "auth-form",
    title: "Auth form",
    group: "patterns",
    section: "patterns-screens",
    order: 6,
    href: "#auth-form",
    summary: "Экран входа: минимальная форма и сообщение об ошибке.",
    sourceRef: "frontend/src/login/page.tsx",
    tags: ["auth", "login", "form"],
    aliases: ["форма входа", "логин", "вход"],
    related: ["field"],
    canvas: "standard",
    family: "composition",
    status: "not-a-component",
    requiredStates: ["default", "error", "loading"],
    public: true,
  },
  {
    id: "confirmation-dialog",
    title: "Confirmation dialog",
    group: "patterns",
    section: "patterns-blocks",
    order: 1,
    href: "#confirmation-dialog",
    summary: "Подтверждение необратимого действия. Обязательно для удаления и рассылок.",
    sourceRef: "frontend/src/components/ui/confirm-action.tsx",
    tags: ["confirm", "destructive", "dialog"],
    aliases: ["подтверждение", "удаление"],
    related: ["buttons", "bulk-action-console"],
    canvas: "standard",
    family: "overlays",
    status: "product",
    requiredStates: ["open", "dismiss", "keyboard", "focus-return"],
    public: true,
  },
  {
    id: "detail-page-blocks",
    title: "Detail page building blocks",
    group: "patterns",
    section: "patterns-blocks",
    order: 2,
    href: "#detail-page-blocks",
    summary:
      "Сборка карточки сотрудника из PageRow и PageSection: полосы равных долей, форма записи вокруг своих полос, записи в модулях разделены линиями.",
    sourceRef: "frontend/src/employee-detail/sections.tsx",
    tags: ["detail", "card", "history"],
    aliases: ["блоки карточки", "карточка сотрудника"],
    related: ["page-row", "page-section", "card"],
    canvas: "workspace",
    family: "composition",
    status: "not-a-component",
    requiredStates: ["default", "empty", "long-content"],
    public: true,
  },
  {
    id: "list-page-item",
    title: "List page item",
    group: "patterns",
    section: "patterns-blocks",
    order: 3,
    href: "#list-page-item",
    summary:
      "Сборка выдачи из карточек записей и строк таблицы. Запись открывает сама запись: в сетке — RecordCard целиком, в таблице — строка со ссылкой в ячейке имени.",
    sourceRef: "frontend/src/employees-list/components.tsx",
    tags: ["list", "row", "card"],
    aliases: ["элемент списка", "список сотрудников"],
    related: ["table", "badge", "record-card"],
    canvas: "workspace",
    family: "collections",
    status: "not-a-component",
    requiredStates: ["hover", "focus", "selected", "empty", "long-content"],
    public: true,
  },

  // --------------------------------------------------------------------- review
  {
    id: "composition-rules",
    title: "Composition rules",
    group: "review",
    section: "review-rules",
    order: 1,
    href: "#composition-rules",
    summary: "Общие принципы сборки экранов: плотность, порядок блоков, отказ от декоративного шума.",
    tags: ["rules", "composition", "density"],
    aliases: ["правила композиции", "принципы", "композиция"],
    related: ["design-debt", "review-checklist"],
    canvas: "standard",
    family: "process",
    status: "not-a-component",
    requiredStates: [],
    public: true,
  },
  {
    id: "design-debt",
    title: "What counts as design debt",
    group: "review",
    section: "review-rules",
    order: 2,
    href: "#design-debt",
    summary: "Признаки, по которым правка считается долгом, а не решением.",
    tags: ["review", "debt", "process"],
    aliases: ["что считать долгом", "долг", "техдолг"],
    related: ["review-checklist"],
    canvas: "standard",
    family: "process",
    status: "not-a-component",
    requiredStates: [],
    public: true,
  },
  {
    id: "review-checklist",
    title: "What reviews and watchdogs should check",
    group: "review",
    section: "review-rules",
    order: 3,
    href: "#review-checklist",
    summary: "Что проверяет ревьюер и что должно ловиться автоматически.",
    tags: ["review", "checklist", "ci"],
    aliases: ["чек-лист ревью", "ревью", "чеклист"],
    related: ["design-debt"],
    canvas: "standard",
    family: "process",
    status: "not-a-component",
    requiredStates: [],
    public: true,
  },
];

/** Проблема реестра: что именно нарушено и где. */
export type RegistryIssue = { entry: string; problem: string };

/**
 * Проверки из playbook. Вызывается тестом и может быть подключена в CI,
 * чтобы каталог не расходился со страницей.
 */
export function validateRegistry(
  catalog: CatalogEntry[] = CATALOG,
  sections: NavigationSection[] = NAVIGATION_SECTIONS,
): RegistryIssue[] {
  const issues: RegistryIssue[] = [];
  const ids = new Set<string>();
  const hrefs = new Set<string>();
  const sectionById = new Map(sections.map((section) => [section.id, section]));
  const orderKeys = new Set<string>();

  for (const section of sections) {
    if (!GROUP_ORDER.includes(section.group)) {
      issues.push({ entry: section.id, problem: `неизвестная группа ${section.group}` });
    }
  }

  for (const entry of catalog) {
    if (ids.has(entry.id)) {
      issues.push({ entry: entry.id, problem: "id не уникален" });
    }
    ids.add(entry.id);

    if (hrefs.has(entry.href)) {
      issues.push({ entry: entry.id, problem: `href ${entry.href} не уникален` });
    }
    hrefs.add(entry.href);

    if (entry.href !== `#${entry.id}`) {
      issues.push({ entry: entry.id, problem: `href ${entry.href} не совпадает с id` });
    }

    const section = sectionById.get(entry.section);
    if (!section) {
      issues.push({ entry: entry.id, problem: `раздел ${entry.section} не объявлен` });
    } else if (section.group !== entry.group) {
      issues.push({
        entry: entry.id,
        problem: `раздел ${entry.section} принадлежит группе ${section.group}, а запись — ${entry.group}`,
      });
    }

    const orderKey = `${entry.group}/${entry.section}/${entry.order}`;
    if (orderKeys.has(orderKey)) {
      issues.push({ entry: entry.id, problem: `порядок ${entry.order} занят в ${entry.section}` });
    }
    orderKeys.add(orderKey);

    // Состояния требуются только там, где их есть где показать.
    // Заявленное, но неотрисованное состояние — обещание без проверки.
    const expectedStates =
      entry.hasLiveExample === false ? undefined : REQUIRED_STATES_BY_FAMILY[entry.family];
    if (expectedStates) {
      const excused = new Set((entry.notApplicableStates || []).map((item) => item.state));
      const missing = expectedStates.filter(
        (state) => !entry.requiredStates.includes(state) && !excused.has(state),
      );
      if (missing.length) {
        issues.push({
          entry: entry.id,
          problem: `для семейства ${entry.family} не заявлены состояния: ${missing.join(", ")}`,
        });
      }
    }

    for (const excuse of entry.notApplicableStates || []) {
      if (!excuse.reason.trim()) {
        issues.push({ entry: entry.id, problem: `исключение для ${excuse.state} без причины` });
      }
      if (entry.requiredStates.includes(excuse.state)) {
        issues.push({
          entry: entry.id,
          problem: `${excuse.state} одновременно объявлено обязательным и неприменимым`,
        });
      }
    }
  }

  for (const entry of catalog) {
    if (entry.related.includes(entry.id)) {
      issues.push({ entry: entry.id, problem: "ссылается сам на себя" });
    }
    if (new Set(entry.related).size !== entry.related.length) {
      issues.push({ entry: entry.id, problem: "дубликаты в related" });
    }
    for (const relatedId of entry.related) {
      if (!ids.has(relatedId)) {
        issues.push({ entry: entry.id, problem: `related ссылается на несуществующий ${relatedId}` });
      }
    }
  }

  return issues;
}

/** Дерево для навигации: группы по GROUP_ORDER, разделы и записи по order. */
export function buildNavigationTree(
  catalog: CatalogEntry[] = CATALOG,
  sections: NavigationSection[] = NAVIGATION_SECTIONS,
) {
  return GROUP_ORDER.map((group) => ({
    group,
    label: GROUP_LABELS[group],
    sections: sections
      .filter((section) => section.group === group)
      .sort((left, right) => left.order - right.order)
      .map((section) => ({
        ...section,
        entries: catalog
          .filter((entry) => entry.public && entry.section === section.id)
          .sort((left, right) => left.order - right.order),
      }))
      .filter((section) => section.entries.length > 0),
  })).filter((group) => group.sections.length > 0);
}

/** Поиск по title, aliases, tags и summary с рангами. */
export function searchCatalog(query: string, catalog: CatalogEntry[] = CATALOG): CatalogEntry[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return [];

  const ranked = catalog
    .filter((entry) => entry.public)
    .map((entry, index) => {
      const title = entry.title.toLowerCase();
      const aliases = entry.aliases.map((alias) => alias.toLowerCase());
      const tags = entry.tags.map((tag) => tag.toLowerCase());

      let rank = -1;
      if (title === needle || aliases.includes(needle)) rank = 0;
      else if (title.startsWith(needle)) rank = 1;
      else if (aliases.some((alias) => alias.startsWith(needle))) rank = 2;
      else if (title.includes(needle)) rank = 3;
      else if (aliases.some((alias) => alias.includes(needle))) rank = 4;
      else if (tags.some((tag) => tag.includes(needle))) rank = 5;
      else if (entry.summary.toLowerCase().includes(needle)) rank = 6;

      return { entry, rank, index };
    })
    .filter((row) => row.rank >= 0);

  ranked.sort((left, right) => left.rank - right.rank || left.index - right.index);
  return ranked.map((row) => row.entry);
}
