import React from "react";
import {
  AlertTriangle,
  CalendarClock,
  ChevronRight,
  ClipboardList,
  Columns2,
  CircleHelp,
  Download,
  ExternalLink,
  FileText,
  LayoutDashboard,
  LayoutGrid,
  LayoutPanelTop,
  Layers3,
  List as ListIcon,
  ListFilter,
  MessageCircle,
  MousePointer2,
  Palette,
  Play,
  Plus,
  Rows3,
  Save,
  Send,
  Shield,
  Trash2,
  Workflow,
} from "lucide-react";
import { Toaster as SonnerToaster, toast } from "sonner";

import { Avatar, AvatarFallback, AvatarGroup, AvatarGroupCount } from "@/components/ui/avatar";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { PageDetailHeader, PageHeader } from "@/components/ui/page-header";
import {
  PageFilters,
  PageFiltersSearch,
  PageFiltersSegments,
} from "@/components/ui/page-filters";
import { PageRow, type PageRowColumns } from "@/components/ui/page-row";
import { RecordCard } from "@/components/ui/record-card";
import { ПРОЯВЛЕНИЕ } from "@/lib/reveal";
import {
  PageSection,
  PageSectionEmpty,
  PageSectionGrid,
  PageSectionRows,
} from "@/components/ui/page-section";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmAction } from "@/components/ui/confirm-action";
import { EmojiPickerPopover } from "@/components/ui/emoji-picker-popover";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
  FieldTitle,
} from "@/components/ui/field";
import { DatePicker, DateTimePicker, TimeSelect } from "@/components/ui/date-picker";
import { Input } from "@/components/ui/input";
import { Progress, ProgressLabel, ProgressValue } from "@/components/ui/progress";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { ThemeSwitch } from "@/components/ui/theme-switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  applyDocumentTheme,
  readDocumentTheme,
  readStoredTheme,
  THEME_CHANGE_EVENT,
  type AppTheme,
} from "@/lib/theme";

import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

import { DocsNav, useHashEntry } from "./docs-nav";
import { Playground } from "./playground";
import { SpecimenList, SpecimenMatrix } from "./specimen";
import {
  CATALOG,
  GROUP_LABELS,
  NAVIGATION_SECTIONS,
  STATUS_LABELS,
  type CatalogEntry,
} from "./registry";

type ButtonVariant = "default" | "secondary" | "outline" | "ghost" | "destructive" | "link";
type ButtonSize = "xs" | "sm" | "default" | "lg";

/** Оси матрицы кнопок. Совпадают с cva-вариантами в button.tsx. */
const BUTTON_VARIANTS = [
  { id: "default", label: "default", hint: "основное действие" },
  { id: "secondary", label: "secondary", hint: "второстепенное" },
  { id: "outline", label: "outline", hint: "нейтральное" },
  { id: "ghost", label: "ghost", hint: "тихое" },
  { id: "destructive", label: "destructive", hint: "необратимое" },
  { id: "link", label: "link", hint: "переход" },
];

const BUTTON_SIZES = [
  { id: "xs", label: "xs", hint: "24px" },
  { id: "sm", label: "sm", hint: "28px" },
  { id: "default", label: "default", hint: "32px" },
  { id: "lg", label: "lg", hint: "36px" },
];

const tokenGroups = [
  {
    title: "Surface",
    items: [
      { label: "Background", variable: "--background", purpose: "Фон всей страницы — самый нижний слой.", value: "oklch(0.985 0.001 106.4) / oklch(0.190 0.004 106.8)" },
      { label: "Card", variable: "--card", purpose: "Поверхность карточек и панелей поверх фона.", value: "oklch(1 0 89.9) / oklch(0.222 0.006 91.6)" },
      { label: "Muted", variable: "--muted", purpose: "Приглушённая подложка: вложенные блоки, шапки таблиц.", value: "oklch(0.967 0.003 84.6) / oklch(0.260 0.007 95.3)" },
      { label: "Border", variable: "--border", purpose: "Границы карточек, полей ввода и разделителей.", value: "oklch(0.925 0.007 88.6) / oklch(0.294 0.008 84.6)" },
    ],
  },
  {
    title: "Text",
    items: [
      { label: "Foreground", variable: "--foreground", purpose: "Основной текст.", value: "oklch(0.213 0.006 91.6) / oklch(0.965 0.006 84.6)" },
      { label: "Muted foreground", variable: "--muted-foreground", purpose: "Второстепенный текст: подписи, пояснения, плейсхолдеры.", value: "oklch(0.521 0.010 91.6) / oklch(0.628 0.013 84.6)" },
      { label: "Primary foreground", variable: "--primary-foreground", purpose: "Текст поверх заливки основного действия.", value: "oklch(1 0 0) / oklch(0.190 0.004 106.8)" },
    ],
  },
  {
    title: "Action",
    items: [
      { label: "Primary", variable: "--primary", purpose: "Основное действие: главная кнопка, активный пункт навигации.", value: "oklch(0.548 0.116 156.9) / oklch(0.675 0.121 158.2)" },
      { label: "Secondary", variable: "--secondary", purpose: "Второстепенное действие и нейтральная заливка.", value: "oklch(0.967 0.003 84.6) / oklch(0.260 0.007 95.3)" },
      { label: "Ring", variable: "--ring", purpose: "Кольцо фокуса. Совпадает с primary, чтобы фокус читался как действие.", value: "oklch(0.548 0.116 156.9) / oklch(0.675 0.121 158.2)" },
      { label: "Destructive", variable: "--destructive", purpose: "Необратимое действие: удаление, отмена, отказ.", value: "oklch(0.577 0.245 27.3) / oklch(0.640 0.245 27.3)" },
    ],
  },
  {
    title: "Semantic",
    items: [
      { label: "Success", variable: "--success", purpose: "Операция завершилась успешно.", value: "oklch(0.627 0.194 145.6) / oklch(0.694 0.195 145.6)" },
      { label: "Warning", variable: "--warning", purpose: "Требует внимания, но не блокирует работу.", value: "oklch(0.703 0.161 73.5) / oklch(0.769 0.161 73.5)" },
      { label: "Info", variable: "--info", purpose: "Нейтральное информационное сообщение.", value: "oklch(0.546 0.215 264.1) / oklch(0.618 0.215 264.1)" },
      { label: "Accent", variable: "--accent", purpose: "Подложка при наведении. Намеренно нейтральная, не зелёная.", value: "neutral hover token, not green tint" },
    ],
  },
] as const;

const typeScale = [
  { label: "Page title", classes: "text-4xl font-semibold tracking-tight", sample: "Дизайн-система админки" },
  { label: "Section heading", classes: "text-2xl font-semibold tracking-tight", sample: "Структура и иерархия интерфейса" },
  { label: "Card title", classes: "text-base font-medium", sample: "Реальный компонент, а не декоративный блок" },
  { label: "Body", classes: "text-sm leading-6 text-foreground/85", sample: "Новые страницы должны читаться спокойно, плотно и без визуальной суеты." },
  { label: "Helper", classes: "text-sm text-muted-foreground", sample: "Подсказки, meta и вторичная информация не должны бороться с основным контентом." },
  { label: "Label", classes: "text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-muted-foreground", sample: "SYSTEM LABEL" },
];

const spacingScale = [8, 12, 16, 24, 32, 48];

const responseTypeItems = [
  { value: "text", label: "Текстовый ответ" },
  { value: "file", label: "Загрузка файла" },
  { value: "none", label: "Без ответа" },
];

const settingsMenuItems = [
  { value: "main", label: "Главное меню" },
  { value: "candidate", label: "Кандидаты" },
  { value: "employee", label: "Сотрудники" },
];

const settingsRoleItems = [
  { value: "admin", label: "Администратор" },
  { value: "hr", label: "HR" },
  { value: "viewer", label: "Наблюдатель" },
];

const bulkAudienceItems = [
  { value: "all", label: "Все роли" },
  { value: "sales", label: "Отдел продаж" },
  { value: "ops", label: "Операционный блок" },
];

const bulkScenarioItems = [
  { value: "candidate-screening", label: "Первичный отбор кандидата" },
  { value: "onboarding", label: "Адаптация сотрудника" },
  { value: "feedback", label: "Сбор обратной связи" },
];

const radiusScale = [
  { label: "rounded-md", className: "rounded-md" },
  { label: "rounded-lg", className: "rounded-lg" },
  { label: "rounded-xl", className: "rounded-xl" },
  { label: "rounded-2xl", className: "rounded-2xl" },
];

const principles = [
  "Desktop-first, documentation-style плотность, без маркетинговой декоративности.",
  "Один primary action. Destructive action подтверждается через AlertDialog.",
  "Новый экран должен объясняться через существующие примитивы и page patterns, а не через локальные хаки.",
  "Порядок сверху вниз один на все страницы: полоса заголовка, полоса фильтров, содержимое. Между ними ничего не вставляется, а форма создания записи фильтром не является и идёт под полосой.",
  "Одна поверхность на уровень. На странице-списке рамку несут карточки записей и внешней обёртки нет; в модуле с заголовком рамку несёт модуль, а записи разделяются линиями. Третьего уровня вложенности не бывает.",
  "На полосе все модули одной ширины. Долей бывает 1, 2, 3 или 4; модулю, которому мало доли, отдаётся собственная полоса целиком.",
  "Текста на фоне страницы не бывает: всё содержимое лежит в блоках. Подпись вне блока не принадлежит ничему и обычно пересказывает то, что уже написано на модулях.",
  "Шапка модуля — одна строка постоянной высоты: имя, приглушённый счётчик, одно компактное действие. Описания под заголовком нет: оно ломало полосу равных долей.",
  "Имя модуля размечено заголовком, а не обычным текстом: это раздел страницы, и дерево доступности обязано это показывать.",
  "Скелет загрузки повторяет раскладку, которая придёт ему на смену, — тем же PageRow и тем же числом долей.",
  "Шаг между полосами один и берётся из --admin-page-gap, а не назначается классом на каждой странице.",
];

const antiPatterns = [
  "Page-local button styles и ad-hoc wrappers внутри конкретного `page.tsx`.",
  "Карточка, существующая только ради фильтров, и карточка внутри карточки под ней.",
  "Пояснительный абзац под полосой заголовка, лежащий прямо на фоне страницы.",
  "Дроби в страничной сетке: grid-cols-[1.45fr_0.85fr], col-span и minmax(...px, ...) вместо равных долей.",
  "Ручная сборка поиска из div.relative и абсолютной иконки вместо PageFiltersSearch.",
  "Своё оформление пустоты вместо PageSectionEmpty: в проекте их успело завестись пять.",
  "window.confirm в React admin pages.",
  "Hover-эффекты, которые меняют геометрию интерфейса сильнее, чем объясняют affordance.",
  "Смешивание classic-визуала и новых React primitives внутри одной рабочей секции.",
  "Новые “особенные” компоненты до попытки починить существующий primitive centrally.",
];

const reviewChecks = [
  "Используются semantic tokens, а не hardcoded white/black/green.",
  "Кнопки и поля идут через shared UI API, а не через локальные div-based имитации.",
  "Удаление идет через ConfirmAction, не через window.confirm.",
  "Dashboard brand использует LayoutDashboard; bot-specific пункты используют bot/message icon.",
  "Основные секции страницы собираются из повторяемых panel/pattern блоков.",
  "Доли одной полосы равны по ширине, а скелет загрузки повторяет ту же раскладку.",
  "Внутри карточки нет второй карточки: рамку несёт либо контейнер, либо записи.",
  "Legacy fallback links не притворяются полезными действиями, если они просто редиректят обратно в React.",
  "Поверхности в потоке держатся на contrast, border и spacing — теней у них нет. Тень остаётся только у слоёв, всплывающих над страницей, и идёт там вместе с рамкой.",
];

const exampleCode = {
  button: `<div className="flex flex-wrap gap-2">
  <Button>Сохранить</Button>
  <Button variant="secondary">Применить позже</Button>
  <Button variant="outline">Открыть детали</Button>
</div>`,
  themeSwitch: `<ThemeSwitch />
<ThemeSwitch iconSize={20} />`,
  confirmAction: `<ConfirmAction
  title="Удалить запись?"
  description="Действие нельзя отменить."
  onConfirm={handleDelete}
>
  <Button variant="outline" size="icon" aria-label="Удалить">
    <Trash2 />
  </Button>
</ConfirmAction>`,
  field: `<FieldGroup>
  <Field>
    <FieldLabel htmlFor="title">Название блока</FieldLabel>
    <Input id="title" />
    <FieldDescription>Один shared primitive, без локальных page styles.</FieldDescription>
  </Field>
</FieldGroup>`,
  navigation: `<Tabs defaultValue="list">
  <TabsList>
    <TabsTrigger value="list">List page</TabsTrigger>
    <TabsTrigger value="detail">Detail page</TabsTrigger>
  </TabsList>
</Tabs>`,
  data: `<Table>
  <TableHeader>
    <TableRow>
      <TableHead>Сущность</TableHead>
      <TableHead>Статус</TableHead>
    </TableRow>
  </TableHeader>
</Table>`,
};

function useDocumentTheme() {
  const [theme, setTheme] = React.useState<AppTheme>("light");

  React.useEffect(() => {
    const nextTheme = readStoredTheme();

    applyDocumentTheme(nextTheme, { persist: false });
    setTheme(nextTheme);

    function handleThemeChange() {
      setTheme(readDocumentTheme());
    }

    window.addEventListener(THEME_CHANGE_EVENT, handleThemeChange);
    window.addEventListener("storage", handleThemeChange);
    return () => {
      window.removeEventListener(THEME_CHANGE_EVENT, handleThemeChange);
      window.removeEventListener("storage", handleThemeChange);
    };
  }, []);

  return theme;
}


/**
 * Какая запись каталога сейчас открыта.
 *
 * Каталог показывает одну запись за раз, а содержимое исторически лежит
 * четырьмя большими секциями. Контекст позволяет отдавать нужный блок,
 * не растаскивая 1900 строк JSX по отдельным файлам: блок сам решает,
 * его ли сейчас очередь.
 */
const ActiveEntryContext = React.createContext<string>("");

/** Показывать ли блок с этим id на текущей странице каталога. */
function useIsActiveEntry(id?: string) {
  const activeId = React.useContext(ActiveEntryContext);
  if (!activeId) return true;
  return id === activeId;
}

function ExampleBlock({
  id,
  title,
  description,
  code,
  playground,
  children,
}: {
  /** Совпадает с id записи в registry.ts — по нему работают навигация и адрес. */
  id?: string;
  title: string;
  description?: string;
  code?: string;
  /** Содержимое само является плейграундом и приносит свою карточку и заголовок. */
  playground?: boolean;
  children: React.ReactNode;
}) {
  if (!useIsActiveEntry(id)) return null;

  if (playground) {
    return (
      <div id={id} className="col-span-full w-full min-w-0">
        {children}
      </div>
    );
  }

  return (
    <Card
      id={id}
      /* Витрина: внутри примера стоят компоненты, среди которых бывают карточки. */
      data-showcase=""
      className="col-span-full w-full min-w-0 border border-border/80 bg-muted/30 shadow-none ring-0"
    >
      <CardHeader className="gap-2 border-b border-border/70 pb-4">
        <CardTitle className="text-base font-semibold">{title}</CardTitle>
        {description ? (
          <CardDescription className="text-sm leading-6 text-muted-foreground">
            {description}
          </CardDescription>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-4 pt-5">
        <div className="rounded-xl border border-border/80 bg-card p-4">{children}</div>
        {code ? (
          <details className="group rounded-lg border border-border/80 bg-card/80">
            <summary className="cursor-pointer list-none px-3 py-2 text-sm font-medium text-muted-foreground marker:hidden">
              <span className="group-open:hidden">Показать пример JSX</span>
              <span className="hidden group-open:inline">Скрыть пример JSX</span>
            </summary>
            <Separator />
            <pre className="overflow-x-auto p-3 text-xs leading-5 text-foreground/85">
              <code>{code}</code>
            </pre>
          </details>
        ) : null}
      </CardContent>
    </Card>
  );
}

function EmojiPickerExample() {
  const [value, setValue] = React.useState("Добро пожаловать");

  return (
    <div className="grid gap-2">
      <p className="text-sm font-semibold">EmojiPickerPopover</p>
      <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-2">
        <Input value={value} onChange={(event) => setValue(event.target.value)} />
        <EmojiPickerPopover onEmojiSelect={(emoji) => setValue((current) => `${current}${emoji}`)} />
      </div>
    </div>
  );
}

/**
 * Палитра списком, а не сеткой карточек: строка читается за один проход —
 * миниатюра, имя, назначение, значения в обеих темах.
 */
function PaletteBlock() {
  if (!useIsActiveEntry("palette")) return null;

  return (
    <Card id="palette" className="col-span-full w-full min-w-0 border border-border/80 bg-muted/30 shadow-none ring-0">
      <CardHeader className="gap-2 border-b border-border/70 pb-4">
        <CardTitle className="text-base font-semibold">Роли цвета</CardTitle>
        <CardDescription className="text-sm leading-6 text-muted-foreground">
          Контрактом является роль, а не значение. Значения даны для светлой и тёмной темы.
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-5">
        <div className="flex flex-col gap-6">
          {tokenGroups.map((group) => (
            <div key={group.title} className="flex flex-col gap-2">
              <div className="text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                {group.title}
              </div>
              <div className="overflow-hidden rounded-xl border border-border/80 bg-card">
                {group.items.map((item, index) => (
                  <div
                    key={item.variable}
                    className={cn(
                      "grid items-center gap-x-4 gap-y-1 px-3 py-2.5",
                      "grid-cols-[2.5rem_minmax(0,1fr)] md:grid-cols-[2.5rem_11rem_minmax(0,1fr)_auto]",
                      index ? "border-t border-border/70" : "",
                    )}
                  >
                    <div
                      aria-hidden="true"
                      className="size-10 rounded-lg border border-border/70"
                      style={{ backgroundColor: `var(${item.variable})` }}
                    />
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">{item.label}</div>
                      <div className="truncate font-mono text-xs text-muted-foreground">
                        {item.variable}
                      </div>
                    </div>
                    <div className="col-span-2 text-sm leading-6 text-muted-foreground md:col-span-1">
                      {item.purpose}
                    </div>
                    <div className="col-span-2 font-mono text-[0.7rem] leading-5 text-muted-foreground/80 md:col-span-1 md:text-right">
                      {item.value}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

/** Общие принципы сборки — отдельная запись каталога, а не хвост каждой страницы. */
function CompositionRules() {
  if (!useIsActiveEntry("composition-rules")) return null;

  return (
    <Card id="composition-rules" className="col-span-full w-full min-w-0 border border-border/80 bg-card shadow-none ring-0">
      <CardHeader className="border-b border-border/70 pb-4">
        <CardTitle className="text-base font-semibold">Composition rules</CardTitle>
      </CardHeader>
      <CardContent className="pt-5">
        <RuleList items={principles} />
      </CardContent>
    </Card>
  );
}

function RuleList({ items, tone = "default" }: { items: string[]; tone?: "default" | "danger" }) {
  const bulletClass = tone === "danger" ? "bg-destructive" : "bg-primary";

  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={item} className="flex gap-3 text-sm leading-6 text-foreground/85">
          <span className={`mt-2 size-1.5 shrink-0 rounded-full ${bulletClass}`} />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function PatternCard({
  entryId,
  title,
  icon: Icon,
  body,
  checklist,
}: {
  /** Запись каталога, к странице которой относится этот чек-лист. */
  entryId?: string;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  body?: string;
  checklist: string[];
}) {
  if (!useIsActiveEntry(entryId)) return null;

  return (
    <Card className="col-span-full w-full min-w-0 border border-border/80 bg-card shadow-none ring-0">
      <CardHeader className="gap-2 border-b border-border/70 pb-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Icon className="size-4 text-primary" />
          <span>{title}</span>
        </div>
        {body ? (
          <CardDescription className="text-sm leading-6 text-muted-foreground">
            {body}
          </CardDescription>
        ) : null}
      </CardHeader>
      <CardContent className="pt-5">
        <RuleList items={checklist} />
      </CardContent>
    </Card>
  );
}

/** Одни и те же строки во всех вкладках: сравнивают шапки, а не содержимое. */
const телеграмСтроки = [
  ["Абрамова Виктория Станиславовна", "@abramova"],
  ["Гринёв Пётр", "@grinev"],
  ["Ким Ольга", "id 481923"],
].map(([имя, канал]) => (
  <div key={канал} className="flex min-w-0 items-center justify-between gap-3">
    <span className="truncate text-sm font-medium">{имя}</span>
    <span className="shrink-0 text-xs text-muted-foreground">{канал}</span>
  </div>
));

/** Полоса фильтров живая: без состояния она не показывает, что чем управляет. */
function PageFiltersExample({ longNames = false }: { longNames?: boolean }) {
  const [scope, setScope] = React.useState("employees");
  const [query, setQuery] = React.useState("");
  const [view, setView] = React.useState("cards");

  return (
    <PageFilters
      scope={
        <PageFiltersSegments
          label="Набор списка"
          value={scope}
          onValueChange={setScope}
          options={
            longNames
              ? [
                  { value: "employees", label: "Сотрудники на испытательном сроке" },
                  { value: "candidates", label: "Кандидаты в работе" },
                ]
              : [
                  { value: "employees", label: "Сотрудники" },
                  { value: "candidates", label: "Кандидаты" },
                ]
          }
        />
      }
      search={
        <PageFiltersSearch
          value={query}
          onValueChange={setQuery}
          placeholder="Поиск по сотрудникам"
        />
      }
      controls={
        <SelectExample
          items={[
            { value: "all", label: "Любой статус" },
            { value: "active", label: "В работе" },
          ]}
          defaultValue="all"
        />
      }
      view={
        <PageFiltersSegments
          label="Представление выдачи"
          iconOnly
          value={view}
          onValueChange={setView}
          options={[
            { value: "cards", label: "Карточки", icon: <LayoutGrid /> },
            { value: "table", label: "Таблица", icon: <ListIcon /> },
          ]}
        />
      }
    />
  );
}

/** Доли полосы подписаны: без подписи видно, что они разные, но не видно, какие. */
function PageRowExample({ columns }: { columns: PageRowColumns }) {
  return (
    <PageRow columns={columns}>
      {Array.from({ length: columns }).map((_, index) => (
        <div
          key={index}
          className="flex h-16 items-center justify-center rounded-lg border border-border bg-muted/40 text-sm text-muted-foreground"
        >
          1/{columns}
        </div>
      ))}
    </PageRow>
  );
}

function SelectExample({
  items,
  defaultValue,
}: {
  items: Array<{ value: string; label: string }>;
  defaultValue: string;
}) {
  return (
    <Select items={items} defaultValue={defaultValue}>
      <SelectTrigger className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent align="start" alignItemWithTrigger={false}>
        <SelectGroup>
          {items.map((item) => (
            <SelectItem value={item.value} key={item.value}>
              {item.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}

function AuthPatternExample() {
  return (
    <div className="grid place-items-center rounded-xl border border-border/80 bg-background p-6">
      <Card className="w-full max-w-[420px] border border-border/80 bg-card shadow-none ring-0">
        <CardHeader className="border-b border-border/70 pb-4">
          <CardTitle className="text-2xl font-semibold tracking-tight">Вход</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-5 pt-5">
          <Alert variant="destructive">
            <AlertTriangle data-icon="inline-start" />
            <AlertTitle>Ошибка входа</AlertTitle>
            <AlertDescription>Неверный логин или пароль.</AlertDescription>
          </Alert>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="auth-pattern-login">Логин</FieldLabel>
              <Input id="auth-pattern-login" autoComplete="username" />
            </Field>
            <Field>
              <FieldLabel htmlFor="auth-pattern-password">Пароль</FieldLabel>
              <Input id="auth-pattern-password" type="password" autoComplete="current-password" />
            </Field>
            <Button className="w-full" size="lg">
              Войти
            </Button>
          </FieldGroup>
        </CardContent>
      </Card>
    </div>
  );
}

function SettingsPatternExample() {
  return (
    <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
      <Card className="border border-border/80 bg-card shadow-none ring-0">
        <CardHeader className="border-b border-border/70 pb-4">
          <CardTitle className="text-base font-semibold">HR-настройки</CardTitle>
          <CardDescription>FieldGroup, Checkbox, semantic feedback.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 pt-5">
          <FieldGroup className="grid gap-4 md:grid-cols-2">
            <Field>
              <FieldLabel>Имя HR</FieldLabel>
              <Input defaultValue="Иван Петров" autoComplete="name" />
            </Field>
            <Field>
              <FieldLabel>Основной ID получателя</FieldLabel>
              <Input defaultValue="123456789" inputMode="numeric" />
            </Field>
          </FieldGroup>
          <FieldSet className="rounded-lg border border-border bg-muted/35 p-3 md:col-span-2">
            <FieldLegend className="sr-only">Уведомления</FieldLegend>
            <FieldGroup className="grid gap-2 xl:grid-cols-3">
              {["По завершению сценариев", "По получению тестового задания", "По действиям пользователей"].map((label) => (
                <Field orientation="horizontal" key={label}>
                  <Checkbox defaultChecked />
                  <FieldContent>
                    <FieldTitle>{label}</FieldTitle>
                  </FieldContent>
                </Field>
              ))}
            </FieldGroup>
          </FieldSet>
          <Alert className="border-primary/30 bg-primary/5">
            <AlertTitle>Настройки сохранены</AlertTitle>
            <AlertDescription>Сообщения и ошибки показываются через tokenized Alert.</AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      <Card className="border border-border/80 bg-card shadow-none ring-0">
        <CardHeader className="border-b border-border/70 pb-4">
          <CardTitle className="text-base font-semibold">Admin access row</CardTitle>
          <CardDescription>Dense rows use explicit columns and icon-only actions.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 pt-5">
          <div className="grid gap-2 rounded-lg border border-border bg-background p-3 xl:grid-cols-[1fr_0.8fr_0.75fr_1fr_auto]">
            <Input defaultValue="admin" autoComplete="username" />
            <SelectExample items={settingsRoleItems} defaultValue="admin" />
            <SelectExample
              items={[
                { value: "true", label: "Активен" },
                { value: "false", label: "Отключен" },
              ]}
              defaultValue="true"
            />
            <Input type="password" placeholder="Новый пароль" autoComplete="new-password" />
            <div className="flex gap-2">
              <Button variant="secondary" size="icon" aria-label="Сохранить">
                <Save />
              </Button>
              <ConfirmAction
                title="Удалить аккаунт?"
                description="Аккаунт потеряет доступ к админке. Это действие нельзя отменить."
                onConfirm={() => undefined}
              >
                <Button variant="outline" size="icon" aria-label="Удалить">
                  <Trash2 />
                </Button>
              </ConfirmAction>
            </div>
          </div>
          <Button className="justify-self-end">
            <Shield data-icon="inline-start" />
            Создать аккаунт
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function BulkActionsPatternExample() {
  const [dateTimeValue, setDateTimeValue] = React.useState("2026-06-19T10:00");

  return (
    <div className="grid gap-4">
      <Card className="border border-border/80 bg-card shadow-none ring-0">
        <CardHeader className="border-b border-border/70 pb-4">
          <CardTitle className="flex items-center gap-2 text-base font-semibold">
            <ClipboardList data-icon="inline-start" />
            Audience filters
          </CardTitle>
          <CardDescription>Select, checkbox groups and preview alert.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 pt-5">
          <div className="grid gap-4 lg:grid-cols-2">
            <Field>
              <FieldLabel>Привязка к должности</FieldLabel>
              <SelectExample items={bulkAudienceItems} defaultValue="all" />
            </Field>
            <Field>
              <FieldLabel>Сотрудник/кандидат</FieldLabel>
              <SelectExample
                items={[
                  { value: "none", label: "Не выбран" },
                  { value: "9", label: "Соколова Мария" },
                  { value: "12", label: "Кандидат: Мария Орлова" },
                ]}
                defaultValue="none"
              />
            </Field>
          </div>
          <Field>
            <FieldLabel>Этапы</FieldLabel>
            <div className="rounded-lg border border-border bg-muted/35 p-3">
              <ScrollArea className="max-h-40 pr-2">
                <FieldGroup className="grid gap-2 sm:grid-cols-2">
                  {["Оформление", "Адаптация", "Кандидат", "Новый"].map((label) => (
                    <Field orientation="horizontal" key={label}>
                      <Checkbox defaultChecked={label !== "Новый"} />
                      <FieldContent>
                        <FieldTitle>{label}</FieldTitle>
                      </FieldContent>
                    </Field>
                  ))}
                </FieldGroup>
              </ScrollArea>
            </div>
          </Field>
          <Alert className="border-warning/40 bg-warning/10">
            <AlertTriangle />
            <AlertTitle>42 получателя</AlertTitle>
            <AlertDescription>Preview обязан быть видимым до запуска действия.</AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-3">
        {["Сценарии", "Сообщения", "Опросы"].map((title) => (
          <Card key={title} className="border border-border/80 bg-card shadow-none ring-0">
            <CardHeader>
              <CardTitle className="text-base font-semibold">{title}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 pt-0">
              <Field>
                <FieldLabel>{title === "Сообщения" ? "Текст" : title === "Опросы" ? "Опрос" : "Сценарий"}</FieldLabel>
                {title === "Сообщения" ? (
                  <Textarea defaultValue="Добрый день, {name}." rows={4} />
                ) : (
                  <SelectExample items={bulkScenarioItems} defaultValue={bulkScenarioItems[0].value} />
                )}
              </Field>
              <Field>
                <FieldLabel>Дата и время</FieldLabel>
                <DateTimePicker value={dateTimeValue} onValueChange={setDateTimeValue} />
              </Field>
              <div className="flex flex-wrap justify-end gap-2">
                <Button variant="secondary">
                  <CalendarClock data-icon="inline-start" />
                  Запланировать
                </Button>
                <Button>
                  <Play data-icon="inline-start" />
                  Сейчас
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function BotMenuPatternExample() {
  return (
    <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
      <Card className="border border-border/80 bg-card shadow-none ring-0">
        <CardHeader className="border-b border-border/70 pb-4">
          <CardTitle className="text-base font-semibold">Новый набор</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 pt-5">
          <div className="grid gap-3 rounded-lg border border-border bg-muted/35 p-3 md:grid-cols-[minmax(220px,1fr)_auto] md:items-end">
            <Field>
              <FieldLabel>Новый набор кнопок</FieldLabel>
              <Input placeholder="Главное меню" autoComplete="off" />
            </Field>
            <Button>
              <Plus data-icon="inline-start" />
              Создать
            </Button>
          </div>
          <Alert className="border-primary/30 bg-primary/5">
            <AlertTitle>Меню бота вынесено из настроек</AlertTitle>
            <AlertDescription>Settings не должен владеть наборами кнопок.</AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      <Card className="border border-border/80 bg-card shadow-none ring-0">
        <CardHeader className="border-b border-border/70 pb-4">
          <div className="grid gap-3 xl:grid-cols-[1fr_1fr_auto] xl:items-end">
            <Field>
              <FieldLabel>Название набора</FieldLabel>
              <Input defaultValue="Главное меню" autoComplete="off" />
            </Field>
            <Field>
              <FieldLabel>Описание</FieldLabel>
              <Input defaultValue="Основные действия" autoComplete="off" />
            </Field>
            <div className="flex gap-2 xl:justify-end">
              <Button variant="secondary">
                <Save data-icon="inline-start" />
                Сохранить
              </Button>
              <ConfirmAction
                title="Удалить набор меню?"
                description="Набор и его кнопки будут удалены из меню бота. Это действие нельзя отменить."
                onConfirm={() => undefined}
              >
                <Button variant="outline" size="icon" aria-label="Удалить набор">
                  <Trash2 />
                </Button>
              </ConfirmAction>
            </div>
          </div>
        </CardHeader>
        <CardContent className="grid gap-3 pt-4">
          <div className="grid gap-4 rounded-lg border border-border bg-muted/35 p-3 lg:grid-cols-2">
            <Field>
              <FieldLabel>Аудитория</FieldLabel>
              <SelectExample
                items={[
                  { value: "all", label: "Для всех сотрудников и кандидатов" },
                  { value: "employees", label: "Для сотрудников" },
                  { value: "candidates", label: "Для кандидатов" },
                ]}
                defaultValue="all"
              />
            </Field>
            <Field>
              <FieldLabel>Должность</FieldLabel>
              <SelectExample items={settingsRoleItems} defaultValue="hr" />
            </Field>
          </div>

          <div className="grid gap-2 rounded-lg border border-border bg-muted/35 p-3 xl:grid-cols-[1.1fr_0.8fr_1fr_1fr_auto]">
            <Input defaultValue="Запустить адаптацию" autoComplete="off" />
            <SelectExample
              items={[
                { value: "inactive", label: "Неактивна" },
                { value: "launch_scenario", label: "Запуск сценария" },
                { value: "open_set", label: "Переход к набору" },
              ]}
              defaultValue="launch_scenario"
            />
            <SelectExample items={bulkScenarioItems} defaultValue="onboarding" />
            <SelectExample items={settingsMenuItems} defaultValue="main" />
            <div className="flex gap-2 xl:justify-end">
              <Button variant="secondary" size="icon" aria-label="Сохранить кнопку">
                <Save />
              </Button>
              <ConfirmAction
                title="Удалить кнопку?"
                description="Кнопка исчезнет из этого набора меню. Это действие нельзя отменить."
                onConfirm={() => undefined}
              >
                <Button variant="outline" size="icon" aria-label="Удалить кнопку">
                  <Trash2 />
                </Button>
              </ConfirmAction>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function ShellSidebarPatternExample() {
  return (
    <div className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
      <Card className="border border-border/80 bg-card shadow-none ring-0">
        <CardHeader className="border-b border-border/70 pb-4">
          <CardTitle className="text-base font-semibold">Icon ownership</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 pt-5">
          <div className="flex items-center gap-3 rounded-lg border border-border bg-muted/35 p-3">
            <div className="grid size-10 place-items-center rounded-xl border border-border bg-background">
              <LayoutDashboard className="size-5" />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold">Dashboard</div>
              <div className="text-xs text-muted-foreground">Обзор и стартовый вход.</div>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-lg border border-border bg-muted/35 p-3">
            <div className="grid size-10 place-items-center rounded-xl border border-border bg-background">
              <MessageCircle className="size-5" />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold">Bot surfaces</div>
              <div className="text-xs text-muted-foreground">Только bot/menu actions.</div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="border border-border/80 bg-card shadow-none ring-0">
        <CardHeader className="border-b border-border/70 pb-4">
          <CardTitle className="text-base font-semibold">Sidebar review rule</CardTitle>
        </CardHeader>
        <CardContent className="pt-5">
          <RuleList
            items={[
              "Dashboard brand использует LayoutDashboard, не Bot.",
              "Bot/menu pages сохраняют bot или message iconography.",
              "Icon-only rail links сохраняют title и aria-current state.",
            ]}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function ConfirmationPatternExample() {
  return (
    <div className="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
      <Card className="border border-border/80 bg-card shadow-none ring-0">
        <CardHeader className="border-b border-border/70 pb-4">
          <CardTitle className="text-base font-semibold">Confirmation action</CardTitle>
          <CardDescription>Для destructive admin actions используется ConfirmAction.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2 pt-5">
          <ConfirmAction
            title="Удалить запись?"
            description="Действие нельзя отменить."
            onConfirm={() => undefined}
          >
            <Button variant="outline" size="icon" aria-label="Удалить">
              <Trash2 />
            </Button>
          </ConfirmAction>
          <Button variant="secondary">
            <Save data-icon="inline-start" />
            Сохранить
          </Button>
        </CardContent>
      </Card>

      <Card className="border border-border/80 bg-card shadow-none ring-0">
        <CardHeader className="border-b border-border/70 pb-4">
          <CardTitle className="text-base font-semibold">Rules</CardTitle>
        </CardHeader>
        <CardContent className="pt-5">
          <RuleList
            items={[
              "Delete icons остаются outline или ghost в dense grids.",
              "Destructive color появляется только на финальном действии в dialog.",
              "Никакого native browser confirm в React admin pages.",
            ]}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function FoundationsSection() {
  return (
    <div className="space-y-6">
      <PaletteBlock />

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <ExampleBlock
          id="typography" title="Typography">
          <div className="space-y-4">
            {typeScale.map((item) => (
              <div key={item.label} className="grid gap-2 rounded-xl border border-border/70 bg-muted/30 p-3 lg:grid-cols-[160px_minmax(0,1fr)]">
                <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                  {item.label}
                </div>
                <div className={item.classes}>{item.sample}</div>
              </div>
            ))}
          </div>
        </ExampleBlock>

        <div className="space-y-4">
        <ExampleBlock
          id="spacing-rhythm" title="Spacing rhythm">
            <div className="space-y-3">
              {spacingScale.map((size) => (
                <div key={size} className="grid items-center gap-3 lg:grid-cols-[72px_minmax(0,1fr)]">
                  <div className="font-mono text-xs text-muted-foreground">{size}px</div>
                  <div className="flex items-center gap-3">
                    <div className="h-3 rounded-full bg-primary/20" style={{ width: `${size * 4}px` }} />
                    <div className="text-sm text-muted-foreground">rhythm / gap / stack</div>
                  </div>
                </div>
              ))}
            </div>
          </ExampleBlock>

        <ExampleBlock
          id="radius-and-depth" title="Radius and depth">
            <div className="grid gap-3">
              {radiusScale.map((radius) => (
                <div key={radius.label} className="flex items-center justify-between gap-3 rounded-xl border border-border/70 bg-muted/30 p-3">
                  <div className="text-sm font-medium">{radius.label}</div>
                  <div className={`h-12 w-20 border border-border bg-card ${radius.className}`} />
                </div>
              ))}
              <div className="rounded-xl border border-dashed border-border bg-muted/40 p-3 text-sm text-muted-foreground">
                У поверхностей в потоке теней нет: глубину дают контраст, рамка и отступы.
                Тень остаётся только у слоёв, всплывающих над страницей, — токен
                <code className="px-1 font-mono text-xs">--shadow-overlay</code> вместе с рамкой.
              </div>
            </div>
          </ExampleBlock>
        </div>
      </div>
    </div>
  );
}

function PrimitivesSection() {
  const [selectValue, setSelectValue] = React.useState("review");
  const [longSelectValue, setLongSelectValue] = React.useState("item-01");
  const [notes, setNotes] = React.useState(
    "Новые страницы должны собираться из shared primitives, а не из локально нарисованных контролов.",
  );
  const [checkboxValue, setCheckboxValue] = React.useState(true);
  const [radioValue, setRadioValue] = React.useState("operators");
  const [denseMode, setDenseMode] = React.useState(true);
  const [progressValue, setProgressValue] = React.useState(72);
  const [dateValue, setDateValue] = React.useState("");
  const [dateTimeValue, setDateTimeValue] = React.useState("");
  const [timeValue, setTimeValue] = React.useState("");
  const longSelectItems = React.useMemo(
    () =>
      Array.from({ length: 24 }, (_, index) => {
        const number = String(index + 1).padStart(2, "0");
        return { value: `item-${number}`, label: `Длинный список ${number}` };
      }),
    [],
  );

  return (
    <TooltipProvider>
      <div className="space-y-6">
        <div className="grid gap-4 xl:grid-cols-2">
        <ExampleBlock id="buttons" title="Buttons" playground>
          <Playground
            tabs={[
              {
                id: "matrix",
                label: "Варианты и размеры",
                caption:
                  "Обе оси видны сразу: вариант читается по строке, размер — по колонке.",
                code: exampleCode.button,
                render: () => (
                  <SpecimenMatrix
                    rows={BUTTON_VARIANTS}
                    columns={BUTTON_SIZES}
                    caption="Высоты: xs — 24px, sm — 28px, default — 32px, lg — 36px."
                    render={(variant, size) => (
                      <Button
                        variant={variant as ButtonVariant}
                        size={size as ButtonSize}
                      >
                        Действие
                      </Button>
                    )}
                  />
                ),
              },
              {
                id: "icon",
                label: "Иконочные",
                caption:
                  "Иконочная кнопка квадратная и обязана иметь aria-label: текста внутри нет.",
                code: `<Button size="icon" aria-label="Открыть карточку">
  <ExternalLink />
</Button>`,
                render: () => (
                  <SpecimenList
                    items={[
                      {
                        label: "icon",
                        hint: "32px, квадрат",
                        render: () => (
                          <Button size="icon" aria-label="Пример иконочной кнопки">
                            <MousePointer2 />
                          </Button>
                        ),
                      },
                      {
                        label: "icon + variant",
                        hint: "тот же размер, другой вариант",
                        render: () => (
                          <>
                            <Button size="icon" variant="outline" aria-label="Пример outline">
                              <MousePointer2 />
                            </Button>
                            <Button size="icon" variant="ghost" aria-label="Пример ghost">
                              <MousePointer2 />
                            </Button>
                            <Button size="icon" variant="destructive" aria-label="Пример destructive">
                              <Trash2 />
                            </Button>
                          </>
                        ),
                      },
                    ]}
                  />
                ),
              },
              {
                id: "states",
                label: "Состояния",
                caption:
                  "Состояния ожидания у кнопки нет — это заявленный пробел кита. Защита от повторного нажатия при сохранении и рассылке ложится на вызывающий код.",
                code: `<Button disabled>Сохранить</Button>`,
                render: () => (
                  <SpecimenList
                    items={[
                      {
                        label: "default",
                        hint: "исходное состояние",
                        render: () => <Button>Сохранить</Button>,
                      },
                      {
                        label: "disabled",
                        hint: "opacity 50%, события не проходят",
                        render: () => (
                          <>
                            <Button disabled>Сохранить</Button>
                            <Button variant="outline" disabled>
                              Открыть детали
                            </Button>
                          </>
                        ),
                      },
                      {
                        label: "hover / focus",
                        hint: "наведите курсор или пройдите табом — состояния живут в CSS",
                        render: () => (
                          <>
                            <Button>Наведите</Button>
                            <Button variant="outline">Или таб</Button>
                          </>
                        ),
                      },
                      {
                        label: "pending",
                        hint: "не реализовано в button.tsx",
                        render: () => (
                          <span className="text-sm text-muted-foreground">
                            Нет в компоненте
                          </span>
                        ),
                      },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

          <ExampleBlock
          id="theme-switch" title="Theme switch" code={exampleCode.themeSwitch}>
            <div className="flex flex-wrap items-end gap-6">
              {[14, 16, 20].map((iconSize) => (
                <div key={iconSize} className="grid justify-items-center gap-2">
                  <ThemeSwitch iconSize={iconSize} />
                  <span className="text-xs text-muted-foreground">{iconSize}px</span>
                </div>
              ))}
            </div>
          </ExampleBlock>


        </div>

        <ExampleBlock id="field" title="Field" playground>
          <Playground
            tabs={[
              {
                id: "anatomy",
                label: "Анатомия",
                caption:
                  "Подпись, контрол, пояснение. Ошибка занимает место пояснения, а не добавляется снизу.",
                code: exampleCode.field,
                render: () => (
                  <SpecimenList
                    items={[
                      {
                        label: "label + control",
                        render: () => (
                          <Field className="w-full max-w-sm">
                            <FieldLabel htmlFor="sp-field-1">Название блока</FieldLabel>
                            <Input id="sp-field-1" defaultValue="Operator workspace baseline" />
                          </Field>
                        ),
                      },
                      {
                        label: "+ description",
                        render: () => (
                          <Field className="w-full max-w-sm">
                            <FieldLabel htmlFor="sp-field-2">Стадия</FieldLabel>
                            <Input id="sp-field-2" defaultValue="Адаптация" />
                            <FieldDescription>Пояснение под контролом.</FieldDescription>
                          </Field>
                        ),
                      },
                      {
                        label: "orientation=horizontal",
                        hint: "для флажков и тумблеров",
                        render: () => (
                          <Field orientation="horizontal">
                            <Checkbox aria-label="Пример" defaultChecked />
                            <FieldContent>
                              <FieldTitle>Утверждено для MVP</FieldTitle>
                              <FieldDescription>Подпись справа от контрола.</FieldDescription>
                            </FieldContent>
                          </Field>
                        ),
                      },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="input" title="Input" playground>
          <Playground
            tabs={[
              {
                id: "states",
                label: "Состояния",
                caption:
                  "Заполненность визуально не отличается от пустоты: data-filled из Base UI не используется. Это заявленный пробел кита.",
                code: exampleCode.field,
                render: () => (
                  <SpecimenList
                    items={[
                      { label: "default", hint: "пусто, с плейсхолдером", render: () => <Input className="max-w-sm" placeholder="Введите значение" /> },
                      { label: "filled", hint: "значение введено", render: () => <Input className="max-w-sm" defaultValue="Ковалёва Анастасия" /> },
                      { label: "error", hint: "aria-invalid", render: () => <Input className="max-w-sm" aria-invalid defaultValue="не тот формат" /> },
                      { label: "disabled", render: () => <Input className="max-w-sm" disabled defaultValue="Недоступно" /> },
                      { label: "long-content", hint: "длинное значение", render: () => <Input className="max-w-sm" defaultValue="Абдурахманов-Загоскин Владислав Кириллович" /> },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="textarea" title="Textarea" playground>
          <Playground
            tabs={[
              {
                id: "states",
                label: "Состояния",
                caption:
                  "Используется для текстов сообщений бота — значит должна переживать длинный текст без потери подписи.",
                render: () => (
                  <SpecimenList
                    items={[
                      { label: "default", render: () => <Textarea className="max-w-sm" rows={3} placeholder="Текст сообщения" /> },
                      { label: "filled", render: () => <Textarea className="max-w-sm" rows={3} defaultValue="Привет! Я HR-бот. Завтра твой первый рабочий день." /> },
                      { label: "error", hint: "aria-invalid", render: () => <Textarea className="max-w-sm" rows={3} aria-invalid defaultValue="Слишком коротко" /> },
                      { label: "disabled", render: () => <Textarea className="max-w-sm" rows={3} disabled defaultValue="Недоступно" /> },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="select" title="Select" playground>
          <Playground
            tabs={[
              {
                id: "states",
                label: "Состояния",
                caption:
                  "Отдаёт null при очистке значения. Обработчик обязан это учитывать, иначе получит null там, где ждёт строку. Наведение, нажатие и открытие подсвечивают триггер приглушённым фоном, шеврон при открытии переворачивается — статичным образцом это не показать, надо потрогать.",
                render: () => (
                  <SpecimenList
                    items={[
                      {
                        label: "default",
                        render: () => (
                          <Select value={selectValue} onValueChange={(next) => setSelectValue(next ?? "")}>
                            <SelectTrigger className="w-56">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent align="start" alignItemWithTrigger={false}>
                              <SelectGroup>
                                <SelectItem value="draft">Draft</SelectItem>
                                <SelectItem value="review">Review</SelectItem>
                                <SelectItem value="ready">Ready</SelectItem>
                              </SelectGroup>
                            </SelectContent>
                          </Select>
                        ),
                      },
                      {
                        label: "long list",
                        hint: "прокрутка после предельной высоты",
                        render: () => (
                          <Select
                            value={longSelectValue}
                            onValueChange={(next) => setLongSelectValue(next ?? "")}
                            items={longSelectItems}
                          >
                            <SelectTrigger className="w-56">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent align="start" alignItemWithTrigger={false}>
                              <SelectGroup>
                                {longSelectItems.map((item) => (
                                  <SelectItem value={item.value} key={item.value}>
                                    {item.label}
                                  </SelectItem>
                                ))}
                              </SelectGroup>
                            </SelectContent>
                          </Select>
                        ),
                      },
                      {
                        label: "open",
                        hint: "нажми: фон триггера подсвечивается, шеврон переворачивается",
                        render: () => (
                          <Select value={selectValue} onValueChange={(next) => setSelectValue(next ?? "")}>
                            <SelectTrigger className="w-56">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent align="start" alignItemWithTrigger={false}>
                              <SelectGroup>
                                <SelectItem value="draft">Draft</SelectItem>
                                <SelectItem value="review">Review</SelectItem>
                                <SelectItem value="ready">Ready</SelectItem>
                              </SelectGroup>
                            </SelectContent>
                          </Select>
                        ),
                      },
                      {
                        label: "disabled",
                        render: () => (
                          <Select value={selectValue} onValueChange={(next) => setSelectValue(next ?? "")}>
                            <SelectTrigger className="w-56" disabled>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectGroup>
                                <SelectItem value="draft">Draft</SelectItem>
                              </SelectGroup>
                            </SelectContent>
                          </Select>
                        ),
                      },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="checkbox" title="Checkbox" playground>
          <Playground
            tabs={[
              {
                id: "states",
                label: "Состояния",
                caption:
                  "Флажок отражает значение формы и применяется вместе с ней. Для немедленного действия используется тумблер.",
                render: () => (
                  <SpecimenList
                    items={[
                      { label: "unchecked", render: () => <Checkbox aria-label="Не отмечено" /> },
                      { label: "checked", render: () => <Checkbox defaultChecked aria-label="Отмечено" /> },
                      {
                        label: "disabled",
                        render: () => (
                          <>
                            <Checkbox disabled aria-label="Недоступно" />
                            <Checkbox disabled defaultChecked aria-label="Недоступно, отмечено" />
                          </>
                        ),
                      },
                      {
                        label: "в составе Field",
                        render: () => (
                          <Field orientation="horizontal">
                            <Checkbox
                              checked={checkboxValue}
                              onCheckedChange={(value) => setCheckboxValue(Boolean(value))}
                              aria-label="Утверждено для MVP"
                            />
                            <FieldContent>
                              <FieldTitle>Утверждено для MVP</FieldTitle>
                            </FieldContent>
                          </Field>
                        ),
                      },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="radio-group" title="Radio group" playground>
          <Playground
            tabs={[
              {
                id: "states",
                label: "Состояния",
                caption:
                  "Ровно один вариант из нескольких. Если вариантов больше пяти — это Select, а не радиокнопки.",
                render: () => (
                  <SpecimenList
                    items={[
                      {
                        label: "group",
                        render: () => (
                          <RadioGroup value={radioValue} onValueChange={setRadioValue}>
                            <Field orientation="horizontal">
                              <RadioGroupItem value="operators" aria-label="Для операторов" />
                              <FieldContent>
                                <FieldTitle>Для операторов</FieldTitle>
                              </FieldContent>
                            </Field>
                            <Field orientation="horizontal">
                              <RadioGroupItem value="admins" aria-label="Для админов" />
                              <FieldContent>
                                <FieldTitle>Для админов</FieldTitle>
                              </FieldContent>
                            </Field>
                          </RadioGroup>
                        ),
                      },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="switch" title="Switch" playground>
          <Playground
            tabs={[
              {
                id: "states",
                label: "Состояния",
                caption:
                  "Тумблер применяет изменение сразу. Если действие требует сохранения формы — это флажок, а не тумблер.",
                render: () => (
                  <SpecimenList
                    items={[
                      { label: "off", render: () => <Switch aria-label="Выключено" /> },
                      { label: "on", render: () => <Switch defaultChecked aria-label="Включено" /> },
                      {
                        label: "disabled",
                        render: () => (
                          <>
                            <Switch disabled aria-label="Недоступно" />
                            <Switch disabled defaultChecked aria-label="Недоступно, включено" />
                          </>
                        ),
                      },
                      {
                        label: "в составе Field",
                        render: () => (
                          <Field orientation="horizontal">
                            <Switch checked={denseMode} onCheckedChange={(value) => setDenseMode(Boolean(value))} />
                            <FieldContent>
                              <FieldTitle>Плотный режим</FieldTitle>
                            </FieldContent>
                          </Field>
                        ),
                      },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="date-picker" title="Date picker" playground>
          <Playground
            tabs={[
              {
                id: "variants",
                label: "Варианты",
                caption:
                  "Календарь и список времени вместо нативных браузерных попапов: те не поддаются оформлению и различаются между браузерами.",
                render: () => (
                  <SpecimenList
                    items={[
                      { label: "DatePicker", hint: "Popover + Calendar", render: () => <DatePicker value={dateValue} onValueChange={setDateValue} /> },
                      { label: "TimeSelect", hint: "Base Select", render: () => <TimeSelect value={timeValue} onValueChange={setTimeValue} /> },
                      { label: "DateTimePicker", hint: "календарь плюс время", render: () => <DateTimePicker value={dateTimeValue} onValueChange={setDateTimeValue} /> },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">



        </div>

        <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">



        </div>
      </div>
        <ExampleBlock id="badge" title="Badge" playground>
          <Playground
            tabs={[
              {
                id: "variants",
                label: "Варианты",
                caption:
                  "Вариант выбирается по смыслу состояния, а не по желаемому цвету. Постоянное значение на всех записях бейджем не показывают — оно не несёт информации.",
                render: () => (
                  <SpecimenList
                    items={[
                      { label: "default", hint: "нейтральное состояние", render: () => <Badge>Primary</Badge> },
                      { label: "secondary", hint: "второстепенная метка", render: () => <Badge variant="secondary">Secondary</Badge> },
                      { label: "outline", hint: "без заливки", render: () => <Badge variant="outline">Neutral</Badge> },
                      { label: "destructive", hint: "риск, отказ, ошибка", render: () => <Badge variant="destructive">Risk</Badge> },
                      { label: "long-content", hint: "длинная метка", render: () => <Badge variant="secondary">Собеседование с руководителем</Badge> },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="card" title="Card" playground>
          <Playground
            tabs={[
              {
                id: "anatomy",
                label: "Анатомия",
                caption:
                  "Шапка, содержимое, подвал. Это поверхность, а не запись: focus-состояния у неё нет, и кликать по ней нечего. Кликабельная карточка в выдаче — RecordCard, у неё фокус есть.",
                render: () => (
                  <SpecimenList
                    items={[
                      {
                        label: "header + content",
                        render: () => (
                          <Card className="w-full max-w-sm border border-border/80 bg-card shadow-none ring-0">
                            <CardHeader className="border-b border-border/70 pb-4">
                              <CardTitle className="text-base font-semibold">Панель</CardTitle>
                            </CardHeader>
                            <CardContent className="pt-4 text-sm text-muted-foreground">Содержимое панели.</CardContent>
                          </Card>
                        ),
                      },
                      {
                        label: "+ footer",
                        render: () => (
                          <Card className="w-full max-w-sm border border-border/80 bg-card shadow-none ring-0">
                            <CardHeader className="border-b border-border/70 pb-4">
                              <CardTitle className="text-base font-semibold">С подвалом</CardTitle>
                            </CardHeader>
                            <CardContent className="pt-4 text-sm text-muted-foreground">Содержимое.</CardContent>
                            <CardFooter className="justify-between gap-2">
                              <span className="text-sm text-muted-foreground">Scope: settings</span>
                              <Button variant="secondary" size="sm">Открыть</Button>
                            </CardFooter>
                          </Card>
                        ),
                      },
                      {
                        label: "muted",
                        hint: "вложенная поверхность",
                        render: () => (
                          <Card className="w-full max-w-sm border border-border/80 bg-muted/30 shadow-none ring-0">
                            <CardContent className="pt-4 text-sm text-muted-foreground">Приглушённая подложка.</CardContent>
                          </Card>
                        ),
                      },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="avatar" title="Avatar" playground>
          <Playground
            tabs={[
              {
                id: "variants",
                label: "Варианты",
                caption: "В продукте не применяется. Инициалы — запасной вариант, когда изображения нет.",
                render: () => (
                  <SpecimenList
                    items={[
                      { label: "fallback", hint: "инициалы", render: () => (<Avatar><AvatarFallback>КА</AvatarFallback></Avatar>) },
                      { label: "group", hint: "несколько человек", render: () => (
                        <AvatarGroup>
                          <Avatar><AvatarFallback>КА</AvatarFallback></Avatar>
                          <Avatar><AvatarFallback>ДП</AvatarFallback></Avatar>
                          <Avatar><AvatarFallback>СМ</AvatarFallback></Avatar>
                        </AvatarGroup>
                      )},
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="progress" title="Progress" playground>
          <Playground
            tabs={[
              {
                id: "states",
                label: "Состояния",
                caption:
                  "Значение отрисовывается render-функцией, а не двумя дочерними узлами: Base UI ждёт функцию.",
                render: () => (
                  <SpecimenList
                    items={[
                      { label: "0%", render: () => (<Progress value={0} className="w-full max-w-sm"><ProgressLabel>Старт</ProgressLabel><ProgressValue>{(_f, v) => `${v ?? 0}%`}</ProgressValue></Progress>) },
                      { label: "72%", render: () => (<Progress value={progressValue} className="w-full max-w-sm"><ProgressLabel>React parity pass</ProgressLabel><ProgressValue>{(_f, v) => `${v ?? 0}%`}</ProgressValue></Progress>) },
                      { label: "100%", render: () => (<Progress value={100} className="w-full max-w-sm"><ProgressLabel>Готово</ProgressLabel><ProgressValue>{(_f, v) => `${v ?? 0}%`}</ProgressValue></Progress>) },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="skeleton" title="Skeleton" playground>
          <Playground
            tabs={[
              {
                id: "shapes",
                label: "Формы",
                caption:
                  "Скелетон держит раскладку, пока данные не пришли. Он должен повторять форму будущего содержимого, иначе экран прыгнет при загрузке.",
                render: () => (
                  <SpecimenList
                    items={[
                      { label: "строка текста", render: () => <Skeleton className="h-4 w-48" /> },
                      { label: "блок", render: () => <Skeleton className="h-20 w-full max-w-sm" /> },
                      { label: "строка списка", render: () => (
                        <div className="flex w-full max-w-sm items-center gap-3">
                          <Skeleton className="size-10 shrink-0 rounded-lg" />
                          <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                            <Skeleton className="h-4 w-2/3" />
                            <Skeleton className="h-3 w-1/3" />
                          </div>
                        </div>
                      )},
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="dialog" title="Dialog" playground>
          <Playground
            tabs={[
              {
                id: "open",
                label: "Открытие",
                caption:
                  "Модальное окно для задачи, которую нельзя выполнить на месте. Для подтверждения необратимого действия есть отдельный компонент.",
                render: () => (
                  <SpecimenList
                    items={[
                      {
                        label: "open / dismiss",
                        hint: "Escape и клик вне окна закрывают",
                        render: () => (
                          <Dialog>
                            <DialogTrigger render={<Button variant="secondary">Открыть диалог</Button>} />
                            <DialogContent>
                              <DialogHeader>
                                <DialogTitle>Пример диалога</DialogTitle>
                                <DialogDescription>Задача, которую нельзя выполнить на месте.</DialogDescription>
                              </DialogHeader>
                              <DialogFooter>
                                <Button variant="outline">Отмена</Button>
                                <Button>Готово</Button>
                              </DialogFooter>
                            </DialogContent>
                          </Dialog>
                        ),
                      },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="confirm-action" title="Confirm action" playground>
          <Playground
            tabs={[
              {
                id: "usage",
                label: "Применение",
                caption:
                  "Обязателен для удаления и массовых рассылок. window.confirm запрещён: он не оформляется, не переводится и блокирует поток.",
                render: () => (
                  <SpecimenList
                    items={[
                      {
                        label: "destructive",
                        hint: "удаление записи",
                        render: () => (
                          <ConfirmAction
                            title="Удалить запись?"
                            description="Действие нельзя отменить."
                            actionLabel="Удалить"
                            onConfirm={() => undefined}
                          >
                            <Button variant="outline">
                              <Trash2 data-icon="inline-start" />
                              Удалить
                            </Button>
                          </ConfirmAction>
                        ),
                      },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="dropdown-menu" title="Dropdown menu" playground>
          <Playground
            tabs={[
              {
                id: "usage",
                label: "Применение",
                caption:
                  "В продукте не применяется: действия у записей вынесены отдельными кнопками. Меню имеет смысл, когда действий больше трёх.",
                render: () => (
                  <SpecimenList
                    items={[
                      {
                        label: "menu",
                        render: () => (
                          <DropdownMenu>
                            <DropdownMenuTrigger render={<Button variant="outline" size="sm">Действия</Button>} />
                            <DropdownMenuContent align="start">
                              <DropdownMenuItem>Открыть карточку</DropdownMenuItem>
                              <DropdownMenuItem>Отправить сообщение</DropdownMenuItem>
                              <DropdownMenuItem>Запустить сценарий</DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        ),
                      },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="tooltip" title="Tooltip" playground>
          <Playground
            tabs={[
              {
                id: "usage",
                label: "Применение",
                caption:
                  "Подсказка не заменяет подпись: с клавиатуры и на сенсорном экране она недоступна. Если смысл элемента понятен только из подсказки — нужна видимая подпись.",
                render: () => (
                  <SpecimenList
                    items={[
                      {
                        label: "hover",
                        render: () => (
                          <TooltipProvider>
                            <Tooltip>
                              <TooltipTrigger render={<Button variant="outline" size="sm">Наведите</Button>} />
                              <TooltipContent>Короткое пояснение</TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                        ),
                      },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="table" title="Table" playground>
          <Playground
            tabs={[
              {
                id: "anatomy",
                label: "Анатомия",
                caption:
                  "В продукте не применяется: табличный вид списка сотрудников собран из блоков вручную и по этой причине не является таблицей для скринридера.",
                code: exampleCode.data,
                render: () => (
                  <div className="w-full overflow-x-auto rounded-xl border border-border/80">
                    <Table className="min-w-[560px]">
                      <TableHeader>
                        <TableRow className="border-border/80">
                          <TableHead>Сущность</TableHead>
                          <TableHead>Статус</TableHead>
                          <TableHead>Владелец</TableHead>
                          <TableHead className="text-right">Действие</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        <TableRow className="border-border/80">
                          <TableCell className="font-medium">Список сотрудников</TableCell>
                          <TableCell><Badge variant="secondary">стабильно</Badge></TableCell>
                          <TableCell>HR</TableCell>
                          <TableCell className="text-right"><Button size="sm" variant="ghost">Открыть</Button></TableCell>
                        </TableRow>
                        <TableRow className="border-border/80">
                          <TableCell className="font-medium">Конструктор сценариев</TableCell>
                          <TableCell><Badge variant="outline">тяжёлый</Badge></TableCell>
                          <TableCell>Ops</TableCell>
                          <TableCell className="text-right"><Button size="sm" variant="ghost">Проверить</Button></TableCell>
                        </TableRow>
                      </TableBody>
                    </Table>
                  </div>
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="scroll-area" title="Scroll area" playground>
          <Playground
            tabs={[
              {
                id: "usage",
                label: "Применение",
                caption: "Оформленная полоса прокрутки вместо системной. Высота задаётся снаружи.",
                render: () => (
                  <ScrollArea className="h-36 w-full max-w-sm rounded-lg border border-border bg-muted/30 p-3">
                    <div className="space-y-2 text-sm text-muted-foreground">
                      {Array.from({ length: 12 }, (_, index) => (
                        <div key={index}>Строка списка {index + 1}</div>
                      ))}
                    </div>
                  </ScrollArea>
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="emoji-picker" title="Emoji picker" playground>
          <Playground
            tabs={[
              {
                id: "usage",
                label: "Применение",
                caption: "Вставка эмодзи в текст сообщения бота.",
                render: () => <EmojiPickerExample />,
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="record-card" title="RecordCard" playground>
          <Playground
            tabs={[
              {
                id: "anatomy",
                label: "Анатомия",
                caption:
                  "Заголовок и подзаголовок слева сверху, ряд тегов под ними, действия справа сверху. Открывает запись вся карточка: курсор, рамка и увеличение на 1% и есть обещание клика, поэтому кнопки «Открыть» в подвале нет — она занимала отдельную строку у каждой записи. Открывает не кнопка на всей карточке, а растянутая ссылка: точка табуляции одна, а чекбокс и кнопки внутри остаются достижимыми.",
                render: () => (
                  <div className="grid w-full gap-3 [grid-template-columns:repeat(auto-fill,minmax(320px,1fr))]">
                    <RecordCard
                      title="Как прошла первая неделя"
                      subtitle="Короткий пульс новичка в конце первой рабочей недели."
                      tags={[
                        { label: "Для всех ролей" },
                        { label: "Для всех сотрудников" },
                        { label: "3 вопроса", variant: "outline" },
                      ]}
                      href="#record-card"
                      selectable
                      actions={
                        <Button
                          size="icon"
                          variant="outline"
                          className={ПРОЯВЛЕНИЕ.card}
                          title="Открыть чат"
                          aria-label="Открыть чат"
                        >
                          <MessageCircle />
                        </Button>
                      }
                    />
                  </div>
                ),
              },
              {
                id: "states",
                label: "Состояния",
                caption:
                  "Наведение обозначается рамкой, а не заливкой: заливка целой карточки в плотной сетке читается как выбор. Выбранная запись — та, чьи детали показаны в соседней панели, — держит акцентную рамку постоянно. Перетаскивание и место вставки выключают наведение, а не спорят с ним за transform.",
                render: () => (
                  <SpecimenList
                    items={[
                      {
                        label: "default",
                        hint: "наведи курсор или пройди Tab",
                        render: () => (
                          <RecordCard
                            className="max-w-sm"
                            title="Итоги испытательного срока"
                            subtitle="Ручное итоговое сообщение по завершению ИС."
                            tags={[{ label: "Только вручную" }, { label: "2 вопроса", variant: "outline" }]}
                            href="#record-card"
                          />
                        ),
                      },
                      {
                        label: "selected",
                        render: () => (
                          <RecordCard
                            className="max-w-sm"
                            density="compact"
                            title="Понятность процесса"
                            subtitle="Был ли процесс отбора понятным?"
                            tags={[{ label: "Выбор кнопками" }, { label: "Ждёт ответ" }]}
                            selected
                            onOpen={() => undefined}
                          />
                        ),
                      },
                      {
                        label: "dragging",
                        render: () => (
                          <RecordCard
                            className="max-w-sm"
                            title="Середина испытательного срока"
                            subtitle="Сверка ожиданий: задачи, обратная связь, риски."
                            tags={[{ label: "4 вопроса", variant: "outline" }]}
                            href="#record-card"
                            dragging
                          />
                        ),
                      },
                      {
                        label: "dropTarget",
                        hint: "место вставки при перетаскивании",
                        render: () => (
                          <RecordCard
                            className="max-w-sm"
                            title="eNPS"
                            subtitle="Один вопрос раз в квартал."
                            tags={[{ label: "1 вопрос", variant: "outline" }]}
                            href="#record-card"
                            dropTarget
                          />
                        ),
                      },
                    ]}
                  />
                ),
              },
              {
                id: "empty",
                label: "Без описания и тегов",
                caption:
                  "Пустые строки не рисуются, а не превращаются в прочерк: чип с «—» занимает место, ничего не сообщая. Карточка сжимается до одного заголовка, и сетка выравнивает её по соседям.",
                render: () => (
                  <div className="grid w-full gap-3 [grid-template-columns:repeat(auto-fill,minmax(320px,1fr))]">
                    <RecordCard title="Черновик без описания" href="#record-card" />
                    <RecordCard
                      title="С описанием, но без тегов"
                      subtitle="Описание есть, теги ещё не заведены."
                      href="#record-card"
                    />
                  </div>
                ),
              },
              {
                id: "long-content",
                label: "Длинное содержимое",
                caption:
                  "Заголовок обрезается в одну строку, описание — в две: в карточке шириной 320px описание, обрезанное до одной строки, теряет половину смысла. Ряд тегов переносится, высоту полосы выравнивает сетка.",
                render: () => (
                  <div className="grid w-full gap-3 [grid-template-columns:repeat(auto-fill,minmax(320px,1fr))]">
                    <RecordCard
                      title="Обратная связь кандидата после отказа на этапе технического интервью"
                      subtitle="Отправляется вручную кандидатам, получившим отказ. Помогает понять, где процесс подбора теряет людей и что стоит поправить в первую очередь."
                      tags={[
                        { label: "Для всех ролей" },
                        { label: "Для всех кандидатов" },
                        { label: "Только вручную" },
                        { label: "Руководитель подразделения" },
                        { label: "3 вопроса", variant: "outline" },
                      ]}
                      href="#record-card"
                      selectable
                      actions={
                        <Button
                          size="icon"
                          variant="outline"
                          className={ПРОЯВЛЕНИЕ.card}
                          title="Настройки"
                          aria-label="Настройки"
                        >
                          <ExternalLink />
                        </Button>
                      }
                    />
                  </div>
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="breadcrumb" title="Breadcrumb" playground>
          <Playground
            tabs={[
              {
                id: "usage",
                label: "Применение",
                caption:
                  "Отвечает на вопрос «откуда я пришёл». В продукте не применяется: навигация собрана вручную в шелле.",
                code: exampleCode.navigation,
                render: () => (
                  <Breadcrumb>
                    <BreadcrumbList>
                      <BreadcrumbItem>
                        <BreadcrumbLink href="#breadcrumb">Админка</BreadcrumbLink>
                      </BreadcrumbItem>
                      <BreadcrumbSeparator />
                      <BreadcrumbItem>
                        <BreadcrumbLink href="#breadcrumb">Сотрудники</BreadcrumbLink>
                      </BreadcrumbItem>
                      <BreadcrumbSeparator />
                      <BreadcrumbItem>
                        <BreadcrumbPage>Карточка</BreadcrumbPage>
                      </BreadcrumbItem>
                    </BreadcrumbList>
                  </Breadcrumb>
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="tabs" title="Tabs" playground>
          <Playground
            tabs={[
              {
                id: "usage",
                label: "Применение",
                caption:
                  "Переключение видов одного экрана без смены адреса. Если содержимое заслуживает своей ссылки — это страница, а не вкладка.",
                render: () => (
                  <Tabs defaultValue="list" className="w-full max-w-md gap-3">
                    <TabsList>
                      <TabsTrigger value="list">Список</TabsTrigger>
                      <TabsTrigger value="detail">Карточка</TabsTrigger>
                    </TabsList>
                    <TabsContent value="list" className="text-sm text-muted-foreground">
                      Содержимое вкладки «Список».
                    </TabsContent>
                    <TabsContent value="detail" className="text-sm text-muted-foreground">
                      Содержимое вкладки «Карточка».
                    </TabsContent>
                  </Tabs>
                ),
              },
            ]}
          />
        </ExampleBlock>
        <ExampleBlock id="alert" title="Alert" playground>
          <Playground
            tabs={[
              {
                id: "variants",
                label: "Варианты",
                caption:
                  "Постоянное сообщение в потоке страницы. Для мгновенной обратной связи после действия нужен тост — но обёртка тостов в продукте не используется.",
                render: () => (
                  <SpecimenList
                    items={[
                      {
                        label: "default",
                        render: () => (
                          <Alert className="w-full max-w-lg">
                            <AlertTitle>Preview не построен</AlertTitle>
                            <AlertDescription>Preview обновится после выбора аудитории.</AlertDescription>
                          </Alert>
                        ),
                      },
                      {
                        label: "destructive",
                        hint: "ошибка операции",
                        render: () => (
                          <Alert variant="destructive" className="w-full max-w-lg">
                            <AlertTitle>Не удалось сохранить</AlertTitle>
                            <AlertDescription>Проверьте обязательные поля и повторите.</AlertDescription>
                          </Alert>
                        ),
                      },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="empty" title="Empty" playground>
          <Playground
            tabs={[
              {
                id: "usage",
                label: "Применение",
                caption:
                  "Пустое состояние объясняет причину и подсказывает следующий шаг. Пустая область без объяснения читается как поломка.",
                render: () => (
                  <SpecimenList
                    items={[
                      {
                        label: "empty",
                        render: () => (
                          <Empty className="w-full max-w-lg">
                            <EmptyHeader>
                              <EmptyMedia variant="icon">
                                <FileText />
                              </EmptyMedia>
                              <EmptyTitle>Документов нет</EmptyTitle>
                            </EmptyHeader>
                          </Empty>
                        ),
                      },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="popover" title="Popover" playground>
          <Playground
            tabs={[
              {
                id: "usage",
                label: "Применение",
                caption:
                  "Всплывающая панель у элемента. В отличие от диалога не блокирует страницу, поэтому годится для выбора и фильтров, но не для необратимых действий.",
                render: () => (
                  <SpecimenList
                    items={[
                      {
                        label: "open",
                        render: () => (
                          <Popover>
                            <PopoverTrigger render={<Button variant="secondary">Открыть панель</Button>} />
                            <PopoverContent align="start" className="w-64">
                              <div className="text-sm text-muted-foreground">
                                Содержимое поповера. Страница остаётся доступной.
                              </div>
                            </PopoverContent>
                          </Popover>
                        ),
                      },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>

        <ExampleBlock id="separator" title="Separator" playground>
          <Playground
            tabs={[
              {
                id: "orientation",
                label: "Ориентация",
                caption:
                  "Линия между смысловыми частями. Декоративный разделитель не должен попадать в дерево доступности как значимый элемент.",
                render: () => (
                  <SpecimenList
                    items={[
                      {
                        label: "horizontal",
                        render: () => (
                          <div className="w-full max-w-sm">
                            <div className="text-sm text-muted-foreground">Блок сверху</div>
                            <Separator className="my-3" />
                            <div className="text-sm text-muted-foreground">Блок снизу</div>
                          </div>
                        ),
                      },
                      {
                        label: "vertical",
                        render: () => (
                          <div className="flex h-10 items-center gap-3">
                            <span className="text-sm text-muted-foreground">Слева</span>
                            <Separator orientation="vertical" />
                            <span className="text-sm text-muted-foreground">Справа</span>
                          </div>
                        ),
                      },
                    ]}
                  />
                ),
              },
            ]}
          />
        </ExampleBlock>
        <ExampleBlock id="page-header" title="PageHeader" playground>
          <Playground
            tabs={[
              {
                id: "composition",
                label: "Состав",
                caption:
                  "Полоса заголовка страницы. Не карточка: ни рамки, ни заливки, только разделитель снизу. В неё помещаются имя страницы, счётчик записей и компактные действия — всё крупнее уезжает в контент, иначе высота полосы разъедется от страницы к странице. Счётчик стоит у имени, а не среди действий: это свойство содержимого, а не то, что можно нажать.",
                render: () => (
                  <div className="flex flex-col gap-4">
                    <div className="overflow-hidden rounded-xl border border-border/80 px-5">
                      <PageHeader title="Настройки" />
                    </div>
                    <div className="overflow-hidden rounded-xl border border-border/80 px-5">
                      <PageHeader
                        title="Документы"
                        actions={
                          <>
                            <Badge variant="secondary">12 файлов</Badge>
                            <Button size="sm">Загрузить</Button>
                          </>
                        }
                      />
                    </div>
                    <div className="overflow-hidden rounded-xl border border-border/80 px-5">
                      <PageHeader
                        title="Сценарии"
                        counter={8}
                        actions={<Button size="sm">Создать</Button>}
                      />
                    </div>
                  </div>
                ),
              },
              {
                id: "detail",
                label: "Полоса детали",
                caption:
                  "У детали вместо имени раздела — хлебная крошка: раздел кликабелен и уводит в каталог, имя записи остаётся заголовком страницы. Крошка заменяет строку возврата «К списку…»: раздел и запись живут в одной строке, и высота детали совпадает со списочной полосой. Раздел не сжимается, при нехватке места обрезается имя записи.",
                render: () => (
                  <div className="flex flex-col gap-4">
                    <div className="overflow-hidden rounded-xl border border-border/80 px-5">
                      <PageDetailHeader
                        title="Первый рабочий день"
                        sectionTitle="Сценарии"
                        onBack={() => undefined}
                        actions={<Button size="sm" variant="outline">Настройки</Button>}
                      />
                    </div>
                    <div className="overflow-hidden rounded-xl border border-border/80 px-5">
                      <PageDetailHeader
                        title="Как прошла первая неделя"
                        sectionTitle="Опросы"
                        onBack={() => undefined}
                      />
                    </div>
                    <div className="overflow-hidden rounded-xl border border-border/80 px-5">
                      <PageDetailHeader
                        title="Обратная связь кандидата после отказа на этапе технического интервью"
                        sectionTitle="Опросы"
                        onBack={() => undefined}
                        actions={<Button size="sm" variant="outline">Настройки</Button>}
                      />
                    </div>
                  </div>
                ),
              },
              {
                id: "long-content",
                label: "Длинное имя",
                caption:
                  "Имя обрезается многоточием, а действия не сжимаются: потерять кнопку хуже, чем хвост заголовка.",
                render: () => (
                  <div className="overflow-hidden rounded-xl border border-border/80 px-5">
                    <PageHeader
                      title="Массовые действия и запланированные рассылки сотрудникам"
                      actions={<Button size="sm">Создать</Button>}
                    />
                  </div>
                ),
              },
            ]}
          />
        </ExampleBlock>
        <ExampleBlock id="page-filters" title="PageFilters" playground>
          <Playground
            tabs={[
              {
                id: "composition",
                label: "Состав",
                caption:
                  "Полоса фильтров идёт сразу за заголовком и ни во что не завёрнута: карточка ради фильтров даёт ощущение карточки в карточке, когда ниже начинаются карточки записей. Порядок задан слотами, а не вызывающим кодом: набор, поиск, селекты, представление. Поиск забирает свободное место, поэтому полоса тянется от края до края; переключатель представления прижат вправо, потому что меняет не выборку, а её показ. Все контролы полосы — 32px в высоту.",
                render: () => <PageFiltersExample />,
              },
              {
                id: "long-content",
                label: "Длинные подписи",
                caption:
                  "Полоса переносится, а не сжимает поиск до нечитаемого: минимальная ширина поля — 280px.",
                render: () => <PageFiltersExample longNames />,
              },
            ]}
          />
        </ExampleBlock>
        <ExampleBlock id="page-row" title="PageRow" playground>
          <Playground
            tabs={[
              {
                id: "columns",
                label: "Доли",
                caption:
                  "На одной полосе все модули одной ширины. Компонент принимает количество долей, а не шаблон колонок: дробей, col-span и minmax(...px, ...) в страничной сетке не бывает. Модулю, которому мало доли, отдаётся собственная полоса целиком, а не полторы.",
                render: () => (
                  <div className="flex flex-col gap-4">
                    <PageRowExample columns={2} />
                    <PageRowExample columns={3} />
                    <PageRowExample columns={4} />
                  </div>
                ),
              },
              {
                id: "breakpoints",
                label: "Лестница",
                caption:
                  "Каждый шаг лестницы — целое деление полосы, поэтому сирот на переносе не бывает: три доли не превращаются в 2 + 1, а сразу идут в одну колонку.",
                render: () => (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[28rem] text-sm">
                      <thead className="text-xs uppercase tracking-wide text-muted-foreground">
                        <tr>
                          <th className="py-2 text-left font-medium">Долей</th>
                          <th className="py-2 text-left font-medium">&lt;768</th>
                          <th className="py-2 text-left font-medium">768–1023</th>
                          <th className="py-2 text-left font-medium">1024–1279</th>
                          <th className="py-2 text-left font-medium">≥1280</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/70 tabular-nums">
                        {[
                          [2, 1, 2, 2, 2],
                          [3, 1, 1, 3, 3],
                          [4, 1, 2, 2, 4],
                        ].map((строка) => (
                          <tr key={строка[0]}>
                            {строка.map((значение, индекс) => (
                              <td key={индекс} className={индекс === 0 ? "py-2 font-medium" : "py-2 text-muted-foreground"}>
                                {значение}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ),
              },
            ]}
          />
        </ExampleBlock>
        <ExampleBlock id="page-section" title="PageSection" playground>
          <Playground
            tabs={[
              {
                id: "default",
                label: "Шапка",
                caption:
                  "Шапка — одна строка постоянной высоты: имя модуля, приглушённый счётчик рядом с ним и одно компактное действие справа. Описания под заголовком нет и слота под него тоже: оно ломало полосу — шапка с описанием оказывалась на 44px выше соседней, и содержимое модуля начиналось настолько же ниже. Высота одинакова во всех трёх модулях ниже, хотя наполнение шапки разное.",
                render: () => (
                  <div className="flex flex-col gap-4">
                    <PageSection title="Требует внимания">
                      <PageSectionRows>{телеграмСтроки}</PageSectionRows>
                    </PageSection>
                    <PageSection title="Свежие Telegram-привязки" counter={3}>
                      <PageSectionRows>{телеграмСтроки}</PageSectionRows>
                    </PageSection>
                    <PageSection
                      title="Входящие документы"
                      counter={3}
                      action={<Button size="sm">Обновить</Button>}
                    >
                      <PageSectionRows>{телеграмСтроки}</PageSectionRows>
                    </PageSection>
                  </div>
                ),
              },
              {
                id: "empty",
                label: "Пусто",
                caption:
                  "Пустота центрируется по доступной высоте: модуль вытягивается до высоты соседа по полосе, и сообщение встаёт в середину, а не липнет к заголовку. Своей рамки у него нет — поверхность на уровень остаётся одна. Счётчику справа передан ноль, и он не показан: пустоту видно по телу модуля, а ноль рядом с именем читается как поломка данных. Счётчик начинается с единицы.",
                render: () => (
                  <PageRow columns={2}>
                    <PageSection title="Требует внимания" counter={3}>
                      <PageSectionRows>{телеграмСтроки}</PageSectionRows>
                    </PageSection>
                    <PageSection title="Свежие Telegram-привязки" counter={0}>
                      <PageSectionEmpty
                        icon={<MessageCircle />}
                        title="Свежих привязок нет"
                        description="Новые Telegram-привязки кандидатов появятся здесь."
                      />
                    </PageSection>
                  </PageRow>
                ),
              },
              {
                id: "grid",
                label: "Плитки",
                caption:
                  "Сетка плиток внутри модуля живёт по тому же принципу, что и полоса: количество долей, а не шаблон колонок. Порог перестроения один, а не лестница — модуль уже стоит в доле полосы, и ширина окна о его собственной ширине ничего не сообщает.",
                render: () => (
                  <PageSection title="Модули">
                    <PageSectionGrid columns={2}>
                      {[
                        ["Сотрудники", "Карточки сотрудников и кандидатов"],
                        ["Массовые действия", "Запуски сценариев, опросов и сообщений"],
                        ["Сценарии", "Конструктор сценариев"],
                        ["Опросы", "Конструктор опросов"],
                      ].map(([имя, пояснение]) => (
                        <div key={имя} className="-mx-2 rounded-lg px-2 py-2">
                          <div className="truncate text-sm font-semibold">{имя}</div>
                          <div className="truncate text-xs text-muted-foreground">{пояснение}</div>
                        </div>
                      ))}
                    </PageSectionGrid>
                  </PageSection>
                ),
              },
              {
                id: "long-content",
                label: "Длинное имя",
                caption:
                  "Имя обрезается многоточием, счётчик и действие не сжимаются: потерять кнопку хуже, чем хвост заголовка.",
                render: () => (
                  <PageSection
                    title="Запланированные сценарии, опросы и массовые сообщения на ближайшие дни"
                    counter={128}
                    action={<Button size="sm">Обновить</Button>}
                  >
                    <PageSectionRows>{телеграмСтроки}</PageSectionRows>
                  </PageSection>
                ),
              },
            ]}
          />
        </ExampleBlock>
    </TooltipProvider>
  );
}

function PatternsSection() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 xl:grid-cols-2">
        <PatternCard
          entryId="list-page-item"
          title="List page"
          icon={Rows3}
          body="Page header, filter bar, table or list."
          checklist={[
            "Page header.",
            "Filter bar.",
            "Table or list.",
          ]}
        />
        <PatternCard
          entryId="detail-page-blocks"
          title="Detail page"
          icon={Columns2}
          body="Primary content plus side section."
          checklist={[
            "Primary content.",
            "Side section.",
            "Separated destructive actions.",
          ]}
        />
        <PatternCard
          entryId="settings-form"
          title="Settings page"
          icon={ListFilter}
          body="Repeatable settings sections and form groups."
          checklist={[
            "Named sections.",
            "Shared form rhythm.",
            "Separated bulk actions.",
          ]}
        />
        <PatternCard
          entryId="bot-menu-editor"
          title="Bot menu page"
          icon={MessageCircle}
          body="Menu sets, audience rules, button actions."
          checklist={[
            "Separate from settings.",
            "Dense menu rows.",
            "Confirm destructive edits.",
          ]}
        />
        <PatternCard
          entryId="shell-sidebar-pattern"
          title="Shell sidebar"
          icon={LayoutDashboard}
          body="Rail and overlay navigation."
          checklist={[
            "Dashboard uses LayoutDashboard.",
            "Bulk actions use ClipboardList.",
            "Bot pages keep bot/message iconography.",
            "Icon-only links keep aria labels.",
          ]}
        />
        <PatternCard
          entryId="confirmation-dialog"
          title="Confirmation"
          icon={Trash2}
          body="Destructive action confirmation."
          checklist={[
            "Use ConfirmAction.",
            "Не использовать window.confirm.",
            "Destructive color only inside dialog.",
          ]}
        />
        <PatternCard
          entryId="workspace-builder"
          title="Workspace page"
          icon={LayoutPanelTop}
          body="Navigation, canvas, detail."
          checklist={[
            "Navigation column.",
            "Canvas column.",
            "Detail column.",
          ]}
        />
        <PatternCard
          entryId="auth-form"
          title="Auth page"
          icon={Shield}
          body="Pre-auth standalone React form."
          checklist={[
            "Standalone mount.",
            "Shared Card/Field/Input/Button.",
            "Native POST to auth route.",
          ]}
        />
      </div>

      <CompositionRules />

      <ExampleBlock
          id="settings-form" title="Settings form">
        <SettingsPatternExample />
      </ExampleBlock>

      <ExampleBlock
          id="bot-menu-editor" title="Bot menu editor">
        <BotMenuPatternExample />
      </ExampleBlock>

      <ExampleBlock
          id="shell-sidebar-pattern" title="Shell sidebar">
        <ShellSidebarPatternExample />
      </ExampleBlock>

      <ExampleBlock
          id="confirmation-dialog" title="Confirmation dialog">
        <ConfirmationPatternExample />
      </ExampleBlock>

      <ExampleBlock
          id="bulk-action-console" title="Mass broadcast">
        <BulkActionsPatternExample />
      </ExampleBlock>

      <ExampleBlock
          id="auth-form" title="Auth form">
        <AuthPatternExample />
      </ExampleBlock>

      <ExampleBlock
          id="detail-page-blocks" title="Detail page building blocks">
        <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
          <div className="flex flex-col gap-3">
            <Card className="border border-border/80 bg-card shadow-none ring-0">
              <CardHeader>
                <CardTitle className="text-base font-semibold">Сопровождение</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 pt-0">
                <FieldGroup className="grid gap-3">
                  <Field>
                    <FieldLabel>Руководитель сотрудника</FieldLabel>
                    <Input placeholder="Telegram id" />
                  </Field>
                  <Field>
                    <FieldLabel>Наставник адаптации</FieldLabel>
                    <Input placeholder="Telegram id" />
                  </Field>
                  <Field orientation="horizontal">
                    <Checkbox defaultChecked />
                    <FieldContent>
                      <FieldTitle>Согласие на ПДн</FieldTitle>
                    </FieldContent>
                  </Field>
                </FieldGroup>
              </CardContent>
            </Card>
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">В штате</Badge>
              <Badge variant="outline">Стаж: 0 лет</Badge>
            </div>
          </div>

          <Card className="border border-border/80 bg-card shadow-none ring-0">
            <CardHeader>
              <CardTitle className="text-base font-semibold">Document row</CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="grid grid-cols-[34px_minmax(0,1fr)_max-content] items-center gap-3 rounded-lg border border-border bg-background p-2.5">
                <div className="grid size-[34px] place-items-center rounded-md bg-muted text-muted-foreground">
                  <FileText className="size-4" />
                </div>
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold">СТО.pdf</div>
                  <div className="truncate text-xs text-muted-foreground">От HR · 31.05.2026 17:58</div>
                </div>
                <div className="flex items-center justify-end gap-2">
                  <Button variant="outline" size="icon-sm" aria-label="Скачать" title="Скачать">
                    <Download />
                  </Button>
                  <Button variant="secondary" size="icon-sm" aria-label="Отправить" title="Отправить">
                    <Send />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </ExampleBlock>

      <ExampleBlock
          id="list-page-item" title="List page item">
        <Card className="w-full min-w-0 rounded-lg border border-border bg-card shadow-none ring-0 transition-colors hover:bg-accent/60">
          <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 space-y-1.5">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="truncate text-[1rem] font-semibold">Соколова Мария Андреевна</h3>
                <Badge variant="secondary">В штате</Badge>
              </div>
              <div className="text-[0.92rem] text-muted-foreground">Аналитик</div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" size="icon" aria-label="Открыть чат" title="Открыть чат">
                <MessageCircle />
              </Button>
              <Button variant="outline" size="icon" aria-label="Открыть карточку" title="Открыть карточку">
                <ExternalLink />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">
              <MessageCircle data-icon="inline-start" />
              @m_sokolova
            </Badge>
            <Badge variant="secondary">Выход: 19.06.2026</Badge>
            <Badge variant="secondary">
              <Workflow data-icon="inline-start" />
              OC от коллег
            </Badge>
          </CardContent>
        </Card>
      </ExampleBlock>

      <ExampleBlock
          id="workspace-builder" title="Workspace builder">
        <div className="grid gap-3 xl:grid-cols-[280px_minmax(0,1fr)_320px]">
          <Card className="border border-border/80 bg-card shadow-none ring-0">
            <CardHeader className="gap-3 border-b border-border/70 pb-4">
              <CardTitle className="text-base font-semibold">Сценарии</CardTitle>
              <Button variant="outline" className="w-full justify-center border-dashed">
                <Plus data-icon="inline-start" />
                Создать сценарий
              </Button>
              <Input placeholder="Найти сценарий" />
            </CardHeader>
            <CardContent className="grid gap-2 pt-4">
              <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-2.5">
                <Checkbox checked aria-label="Выбрать сценарий" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold">Первичный отбор кандидата</div>
                  <div className="text-xs text-muted-foreground">Для всех ролей</div>
                </div>
              </div>
              <div className="grid gap-2 rounded-lg border border-border bg-muted/35 p-2.5">
                <div className="text-sm font-semibold">Стартовый сценарий</div>
                <div className="flex flex-wrap gap-1.5">
                  <Badge variant="secondary">Кандидаты</Badge>
                  <Badge variant="secondary">Автостарт</Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border border-border/80 bg-card shadow-none ring-0">
            <CardHeader className="flex flex-row items-start justify-between gap-3 border-b border-border/70 pb-4">
              <div>
                <Badge variant="secondary">Первичный отбор кандидата</Badge>
                <CardTitle className="mt-3 text-base font-semibold">Шаги сценария</CardTitle>
              </div>
              <Button size="sm">
                <Plus data-icon="inline-start" />
                Добавить шаг
              </Button>
            </CardHeader>
            <CardContent className="grid gap-2 pt-4">
              <Card className="border border-primary/70 bg-muted/40 shadow-none ring-0">
                <CardContent className="grid gap-2 pt-4">
                  <div className="font-semibold">Запрос ФИО</div>
                  <div className="text-sm text-muted-foreground">Напиши, как тебя зовут.</div>
                  <Badge variant="secondary">Текстовый ответ</Badge>
                </CardContent>
              </Card>
              <Card className="border border-border bg-background shadow-none ring-0">
                <CardContent className="grid gap-2 pt-4">
                  <div className="font-semibold">Запрос информации о должности</div>
                  <div className="flex flex-wrap gap-1.5">
                    <Badge variant="secondary">Ветвление</Badge>
                    <Badge variant="secondary">Кнопки: 3</Badge>
                  </div>
                </CardContent>
              </Card>
            </CardContent>
          </Card>

          <Card className="border border-border/80 bg-card shadow-none ring-0">
            <CardHeader className="border-b border-border/70 pb-4">
              <CardTitle className="text-base font-semibold">Детали</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 pt-4">
              <Field>
                <FieldLabel>Название</FieldLabel>
                <Input defaultValue="Запрос ФИО" />
              </Field>
              <Field>
                <FieldLabel>Текст</FieldLabel>
                <Textarea defaultValue="Давай знакомиться. Напиши, как тебя зовут." />
              </Field>
              <Field>
                <FieldLabel>Тип ответа</FieldLabel>
                <Select items={responseTypeItems} defaultValue="text">
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent align="start" alignItemWithTrigger={false}>
                    <SelectGroup>
                      {responseTypeItems.map((item) => (
                        <SelectItem value={item.value} key={item.value}>
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
              <Button className="justify-self-end">Сохранить</Button>
            </CardContent>
          </Card>
        </div>
      </ExampleBlock>
    </div>
  );
}

function ReviewRulesSection() {
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
      <ExampleBlock
          id="design-debt" title="What counts as design debt">
        <RuleList items={antiPatterns} tone="danger" />
      </ExampleBlock>

      <ExampleBlock
          id="review-checklist" title="What reviews and watchdogs should check">
        <RuleList items={reviewChecks} />
      </ExampleBlock>
    </div>
  );
}

/** Шапка страницы каталога: имя системы и переключатель темы. Больше ничего. */
/*
 * Каталог пользуется тем же примитивом, что и остальные страницы. Своя шапка
 * с двухстрочным брендом давала полосу 69px против 56px везде — витрина
 * дизайн-системы не должна расходиться с описываемым ею контрактом.
 *
 * Надстрочник «HRBot» убран как избыточный: мы и так внутри админки HRBot.
 */
function CatalogHeader() {
  return <PageHeader title="Дизайн-система" actions={<ThemeSwitch />} />;
}

/**
 * Страница одной записи каталога.
 *
 * Порядок блоков закреплён и одинаков для всех записей: контекст, имя,
 * назначение, источник, затем содержимое и связанные элементы. Автор
 * не может случайно поставить API раньше основного примера.
 */
/**
 * Страница компонента, у которого нет живого образца.
 *
 * Пример без потребителя в продукте устаревает молча: его никто не
 * открывает, и расхождение с кодом обнаруживается через полгода. Честнее
 * показать, что компонент есть, но не проверяется, чем поддерживать
 * витринную сцену, за которую никто не отвечает.
 */
function NoLiveExample({ entry }: { entry: CatalogEntry }) {
  const reason =
    entry.status === "internal"
      ? "Компонент не применяется напрямую: он нужен другому компоненту кита."
      : "Компонент не импортируется ни одним экраном и ни одним другим компонентом.";

  return (
    <Alert>
      <AlertTitle>Живого образца нет</AlertTitle>
      <AlertDescription>
        <p>{reason}</p>
        <p>
          Сцена не поддерживается сознательно: пример без потребителя устаревает молча.
          Исходник — <code className="font-mono text-xs">{entry.sourceRef}</code>.
        </p>
      </AlertDescription>
    </Alert>
  );
}

function EntryPage({ entry }: { entry: CatalogEntry }) {
  const section = NAVIGATION_SECTIONS.find((item) => item.id === entry.section);
  const related = entry.related
    .map((id) => CATALOG.find((item) => item.id === id))
    .filter((item): item is CatalogEntry => Boolean(item));
  const excused = entry.notApplicableStates || [];

  return (
    <article className="flex min-w-0 flex-col gap-6">
      <div className="flex flex-col gap-2">
        <div className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          {GROUP_LABELS[entry.group]}
          {section ? ` · ${section.label}` : ""}
        </div>
        <h2 className="text-3xl font-semibold tracking-tight">{entry.navLabel}</h2>
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">{entry.summary}</p>
        <div className="flex flex-wrap items-center gap-2">
          {entry.status !== "not-a-component" ? (
            <Badge
              variant={
                entry.status === "product"
                  ? "default"
                  : entry.status === "unused"
                    ? "destructive"
                    : "secondary"
              }
            >
              {STATUS_LABELS[entry.status]}
            </Badge>
          ) : null}
          {/* Английское имя — техническое: по нему компонент называется в коде. */}
          <code className="rounded-md border border-border/80 bg-muted/50 px-2 py-1 font-mono text-xs text-muted-foreground">
            {entry.title}
          </code>
          {entry.sourceRef ? (
            <code className="rounded-md border border-border/80 bg-muted/50 px-2 py-1 font-mono text-xs text-muted-foreground">
              {entry.sourceRef}
            </code>
          ) : null}
        </div>
      </div>

      {entry.hasLiveExample === false ? (
        <NoLiveExample entry={entry} />
      ) : (
        <ActiveEntryContext.Provider value={entry.id}>
          <FoundationsSection />
          <PrimitivesSection />
          <PatternsSection />
          <ReviewRulesSection />
        </ActiveEntryContext.Provider>
      )}

      {entry.requiredStates.length || excused.length ? (
        <section className="flex flex-col gap-2">
          <h3 className="text-base font-semibold">Обязательные состояния</h3>
          <div className="flex flex-wrap gap-1.5">
            {entry.requiredStates.map((state) => (
              <Badge key={state} variant="secondary" className="font-mono text-xs">
                {state}
              </Badge>
            ))}
          </div>
          {excused.map((item) => (
            <div key={item.state} className="text-sm leading-6 text-muted-foreground">
              <span className="font-mono text-xs">{item.state}</span> — не применимо: {item.reason}
            </div>
          ))}
        </section>
      ) : null}

      {related.length ? (
        <section className="flex flex-col gap-2">
          <h3 className="text-base font-semibold">Связанные</h3>
          <div className="flex flex-wrap gap-2">
            {related.map((item) => (
              <a
                key={item.id}
                href={item.href}
                className="rounded-lg border border-border/80 bg-card px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent/60 hover:text-foreground"
              >
                {item.navLabel}
              </a>
            ))}
          </div>
        </section>
      ) : null}
    </article>
  );
}

export function DesignSystemPage() {
  const theme = useDocumentTheme();
  const activeId = useHashEntry(CATALOG[0].id);
  const entry = CATALOG.find((item) => item.id === activeId) || CATALOG[0];

  return (
    <>
      {/* Шапка вне ограниченной колонки: иначе её разделитель обрезается по 1820px. */}
      <CatalogHeader />

      <div className="admin-page-stack gap-0 pb-10">
        <SonnerToaster
          position="bottom-right"
          richColors
          theme={theme}
          toastOptions={{
            style: {
              background: "var(--popover)",
              color: "var(--popover-foreground)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
            },
          }}
        />

        <div className="grid gap-8 pt-6 lg:grid-cols-[248px_minmax(0,1fr)] lg:items-start">
          <aside className="lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto lg:pr-1">
            <DocsNav activeId={activeId} />
          </aside>
          <EntryPage entry={entry} />
        </div>
      </div>
    </>
  );
}
