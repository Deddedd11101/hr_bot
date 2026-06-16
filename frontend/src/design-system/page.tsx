import React from "react";
import {
  AlertTriangle,
  CalendarClock,
  ChevronRight,
  Columns2,
  CircleHelp,
  Download,
  ExternalLink,
  FileText,
  LayoutDashboard,
  LayoutPanelTop,
  Layers3,
  ListFilter,
  MessageCircle,
  Moon,
  MousePointer2,
  Palette,
  Play,
  Plus,
  Rows3,
  Save,
  Send,
  Shield,
  Sun,
  Trash2,
} from "lucide-react";
import { Toaster as SonnerToaster, toast } from "sonner";

import { Avatar, AvatarFallback, AvatarGroup, AvatarGroupCount } from "@/components/ui/avatar";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
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

const sectionLinks = [
  { id: "foundations", label: "Foundations", icon: Palette },
  { id: "primitives", label: "Primitives", icon: Layers3 },
  { id: "patterns", label: "Patterns", icon: LayoutPanelTop },
  { id: "review-rules", label: "Review rules", icon: CircleHelp },
] as const;

const tokenGroups = [
  {
    title: "Surface",
    items: [
      { label: "Background", variable: "--background", value: "oklch(0.985 0.001 106.4) / oklch(0.190 0.004 106.8)" },
      { label: "Card", variable: "--card", value: "oklch(1 0 89.9) / oklch(0.222 0.006 91.6)" },
      { label: "Muted", variable: "--muted", value: "oklch(0.967 0.003 84.6) / oklch(0.260 0.007 95.3)" },
      { label: "Border", variable: "--border", value: "oklch(0.925 0.007 88.6) / oklch(0.294 0.008 84.6)" },
    ],
  },
  {
    title: "Text",
    items: [
      { label: "Foreground", variable: "--foreground", value: "oklch(0.213 0.006 91.6) / oklch(0.965 0.006 84.6)" },
      { label: "Muted foreground", variable: "--muted-foreground", value: "oklch(0.521 0.010 91.6) / oklch(0.628 0.013 84.6)" },
      { label: "Primary foreground", variable: "--primary-foreground", value: "oklch(1 0 0) / oklch(0.190 0.004 106.8)" },
    ],
  },
  {
    title: "Action",
    items: [
      { label: "Primary", variable: "--primary", value: "oklch(0.588 0.116 156.9) / oklch(0.675 0.121 158.2)" },
      { label: "Secondary", variable: "--secondary", value: "oklch(0.967 0.003 84.6) / oklch(0.260 0.007 95.3)" },
      { label: "Ring", variable: "--ring", value: "oklch(0.588 0.116 156.9) / oklch(0.675 0.121 158.2)" },
      { label: "Destructive", variable: "--destructive", value: "oklch(0.577 0.245 27.3) / oklch(0.640 0.245 27.3)" },
    ],
  },
  {
    title: "Semantic",
    items: [
      { label: "Success", variable: "--success", value: "oklch(0.627 0.194 145.6) / oklch(0.694 0.195 145.6)" },
      { label: "Warning", variable: "--warning", value: "oklch(0.703 0.161 73.5) / oklch(0.769 0.161 73.5)" },
      { label: "Info", variable: "--info", value: "oklch(0.546 0.215 264.1) / oklch(0.618 0.215 264.1)" },
      { label: "Accent", variable: "--accent", value: "neutral hover token, not green tint" },
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
];

const antiPatterns = [
  "Page-local button styles и ad-hoc wrappers внутри конкретного `page.tsx`.",
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
  "Legacy fallback links не притворяются полезными действиями, если они просто редиректят обратно в React.",
  "Никаких теней как основного depth-сигнала: MVP UI держится на contrast, border и spacing.",
];

const exampleCode = {
  button: `<div className="flex flex-wrap gap-2">
  <Button>Сохранить</Button>
  <Button variant="secondary">Применить позже</Button>
  <Button variant="outline">Открыть детали</Button>
</div>`,
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

  const toggleTheme = React.useCallback(() => {
    setTheme((currentTheme) => {
      const nextTheme = currentTheme === "dark" ? "light" : "dark";
      applyDocumentTheme(nextTheme);
      return nextTheme;
    });
  }, []);

  return { theme, toggleTheme };
}

function useActiveSection(sectionIds: readonly string[]) {
  const [activeSection, setActiveSection] = React.useState(sectionIds[0] ?? "");

  React.useEffect(() => {
    const sections = sectionIds
      .map((id) => document.getElementById(id))
      .filter((section): section is HTMLElement => Boolean(section));

    if (!sections.length) {
      return undefined;
    }

    const updateActiveSection = () => {
      const threshold = 180;
      const currentSection =
        [...sections]
          .reverse()
          .find((section) => section.getBoundingClientRect().top <= threshold) ?? sections[0];

      if (currentSection?.id) {
        setActiveSection(currentSection.id);
      }
    };

    updateActiveSection();
    window.addEventListener("scroll", updateActiveSection, { passive: true });
    window.addEventListener("resize", updateActiveSection);

    return () => {
      window.removeEventListener("scroll", updateActiveSection);
      window.removeEventListener("resize", updateActiveSection);
    };
  }, [sectionIds]);

  return activeSection;
}

function SectionShell({
  id,
  icon: Icon,
  title,
  description,
  children,
}: {
  id: string;
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24">
      <Card className="border border-border/80 bg-card shadow-none ring-0">
        <CardHeader className="gap-2 border-b border-border/70 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-xl border border-border/80 bg-muted/40 text-muted-foreground">
              <Icon className="size-4" />
            </div>
            <div className="space-y-1">
              <div className="text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                System section
              </div>
              <CardTitle className="text-2xl font-semibold tracking-tight">{title}</CardTitle>
            </div>
          </div>
          {description ? (
            <CardDescription className="max-w-3xl text-sm leading-6 text-muted-foreground">
              {description}
            </CardDescription>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-6 pt-6">{children}</CardContent>
      </Card>
    </section>
  );
}

function ExampleBlock({
  title,
  description,
  code,
  children,
}: {
  title: string;
  description?: string;
  code?: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="border border-border/80 bg-muted/30 shadow-none ring-0">
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

function TokenGroupCard({
  title,
  items,
}: {
  title: string;
  items: ReadonlyArray<{ label: string; variable: string; value: string }>;
}) {
  return (
    <Card className="border border-border/80 bg-card shadow-none ring-0">
      <CardHeader className="pb-0">
        <CardTitle className="text-base font-semibold">{title}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 pt-4">
        {items.map((item) => (
          <div key={item.variable} className="rounded-xl border border-border/80 bg-muted/40 p-3">
            <div
              className="mb-3 h-16 rounded-lg border border-border/70"
              style={{ backgroundColor: `var(${item.variable})` }}
            />
            <div className="space-y-1">
              <div className="text-sm font-medium">{item.label}</div>
              <div className="font-mono text-xs text-muted-foreground">{item.variable}</div>
              <div className="text-xs text-muted-foreground">{item.value}</div>
            </div>
          </div>
        ))}
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
  title,
  icon: Icon,
  body,
  checklist,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  body?: string;
  checklist: string[];
}) {
  return (
    <Card className="border border-border/80 bg-card shadow-none ring-0">
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
          <CardTitle className="text-base font-semibold">Audience filters</CardTitle>
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
                  { value: "9", label: "Востриков Антон" },
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
      <div className="grid gap-4 xl:grid-cols-4">
        {tokenGroups.map((group) => (
          <TokenGroupCard key={group.title} title={group.title} items={group.items} />
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <ExampleBlock title="Typography">
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
        <ExampleBlock title="Spacing rhythm">
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

        <ExampleBlock title="Radius and depth">
            <div className="grid gap-3">
              {radiusScale.map((radius) => (
                <div key={radius.label} className="flex items-center justify-between gap-3 rounded-xl border border-border/70 bg-muted/30 p-3">
                  <div className="text-sm font-medium">{radius.label}</div>
                  <div className={`h-12 w-20 border border-border bg-card ${radius.className}`} />
                </div>
              ))}
              <div className="rounded-xl border border-dashed border-border bg-muted/40 p-3 text-sm text-muted-foreground">
                Shadows disabled in MVP baseline.
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
        <ExampleBlock
          title="Buttons"
          code={exampleCode.button}
        >
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Button>Сохранить</Button>
                <Button variant="secondary">Применить позже</Button>
                <Button variant="outline">Открыть детали</Button>
                <Button variant="ghost">Тихое действие</Button>
                <Button variant="link">Связанный документ</Button>
              </div>
              <Separator />
              <div className="flex flex-wrap items-center gap-2">
                <Button size="xs">XS</Button>
                <Button size="sm">SM</Button>
                <Button>Default</Button>
                <Button size="lg">LG</Button>
                <Button size="icon" aria-label="icon demo">
                  <MousePointer2 className="size-4" />
                </Button>
                <Button variant="secondary" disabled>
                  Disabled
                </Button>
              </div>
            </div>
          </ExampleBlock>

          <ExampleBlock title="Status language">
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Badge>Primary</Badge>
                <Badge variant="secondary">Secondary</Badge>
                <Badge variant="outline">Neutral</Badge>
                <Badge variant="destructive">Risk</Badge>
                <span className="rounded-md bg-success/15 px-2 py-1 text-xs font-medium text-success">Success</span>
                <span className="rounded-md bg-warning/15 px-2 py-1 text-xs font-medium text-warning">Warning</span>
                <span className="rounded-md bg-info/15 px-2 py-1 text-xs font-medium text-info">Info</span>
              </div>
              <div className="rounded-xl border border-border/70 bg-muted/40 p-3 text-sm text-muted-foreground">
                Status, scope, compact metadata.
              </div>
            </div>
          </ExampleBlock>
        </div>

        <ExampleBlock
          title="Form primitives"
          code={exampleCode.field}
        >
          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <FieldGroup>
              <FieldSet>
                <FieldTitle>Content fields</FieldTitle>
                <FieldDescription>
                  Shared form fields.
                </FieldDescription>
              </FieldSet>

              <div className="grid gap-4 md:grid-cols-2">
                <Field>
                  <FieldLabel htmlFor="kit-title">Название блока</FieldLabel>
                  <Input id="kit-title" defaultValue="Operator workspace baseline" />
                </Field>
                <Field>
                  <FieldLabel htmlFor="kit-status">Стадия</FieldLabel>
                  <Select value={selectValue} onValueChange={setSelectValue}>
                    <SelectTrigger id="kit-status" className="w-full">
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
                </Field>
                <Field>
                  <FieldLabel htmlFor="kit-long-select">Длинный список</FieldLabel>
                  <Select value={longSelectValue} onValueChange={setLongSelectValue} items={longSelectItems}>
                    <SelectTrigger id="kit-long-select" className="w-full">
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
                  <FieldDescription>Scrollable after max content height.</FieldDescription>
                </Field>
              </div>

              <Field>
                <FieldLabel htmlFor="kit-notes">Описание и правила</FieldLabel>
                <Textarea
                  id="kit-notes"
                  rows={5}
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                />
              <FieldDescription>
                  Multiline field example.
              </FieldDescription>
              </Field>

              <div className="grid gap-4 lg:grid-cols-3">
                <Field>
                  <FieldLabel>Date picker</FieldLabel>
                  <DatePicker value={dateValue} onValueChange={setDateValue} />
                  <FieldDescription>Popover + Calendar.</FieldDescription>
                </Field>
                <Field>
                  <FieldLabel>Time select</FieldLabel>
                  <TimeSelect value={timeValue} onValueChange={setTimeValue} />
                  <FieldDescription>Base Select, no native browser popup.</FieldDescription>
                </Field>
                <Field>
                  <FieldLabel>Date time</FieldLabel>
                  <DateTimePicker value={dateTimeValue} onValueChange={setDateTimeValue} />
                  <FieldDescription>Calendar plus tokenized time select.</FieldDescription>
                </Field>
              </div>
            </FieldGroup>

            <div className="space-y-4">
              <Card className="border border-border/80 bg-card shadow-none ring-0">
                <CardHeader className="pb-0">
                  <CardTitle className="text-base font-semibold">Selection states</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 pt-4">
                  <Field orientation="horizontal">
                    <Checkbox
                      checked={checkboxValue}
                      onCheckedChange={(value) => setCheckboxValue(Boolean(value))}
                      aria-label="Утверждено для MVP"
                    />
                    <FieldContent>
                      <FieldTitle>Утверждено для MVP</FieldTitle>
                      <FieldDescription>Checkbox example.</FieldDescription>
                    </FieldContent>
                  </Field>

                  <RadioGroup value={radioValue} onValueChange={setRadioValue}>
                    <Field orientation="horizontal">
                      <RadioGroupItem value="operators" aria-label="Для операторов" />
                      <FieldContent>
                        <FieldTitle>Для операторов</FieldTitle>
                        <FieldDescription>Operator mode.</FieldDescription>
                      </FieldContent>
                    </Field>
                    <Field orientation="horizontal">
                      <RadioGroupItem value="admins" aria-label="Для админов" />
                      <FieldContent>
                        <FieldTitle>Для админов</FieldTitle>
                        <FieldDescription>Admin mode.</FieldDescription>
                      </FieldContent>
                    </Field>
                  </RadioGroup>

                  <div className="space-y-3 pt-2">
                    <div className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                      Interface policy
                    </div>
                    <Separator className="mb-1" />
                  </div>

                  <Field orientation="horizontal" className="pt-1">
                    <Switch checked={denseMode} onCheckedChange={(value) => setDenseMode(Boolean(value))} />
                    <FieldContent>
                      <FieldTitle>Dense mode</FieldTitle>
                      <FieldDescription>
                        Dense layout example.
                      </FieldDescription>
                    </FieldContent>
                  </Field>
                </CardContent>
              </Card>
            </div>
          </div>
        </ExampleBlock>

        <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
          <ExampleBlock title="Cards and panels">
            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="border border-border/80 bg-card shadow-none ring-0">
                <CardHeader className="border-b border-border/70 pb-4">
                  <CardTitle className="text-base font-semibold">Default panel</CardTitle>
                </CardHeader>
                <CardContent className="pt-4 text-sm text-muted-foreground">
                  Main panel example.
                </CardContent>
                <CardFooter className="justify-between gap-2">
                  <span className="text-sm text-muted-foreground">Scope: settings</span>
                  <Button variant="secondary" size="sm">Открыть</Button>
                </CardFooter>
              </Card>

              <Card className="border border-border/80 bg-muted/30 shadow-none ring-0">
                <CardHeader className="border-b border-border/70 pb-4">
                  <CardTitle className="text-base font-semibold">Support panel</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 pt-4 text-sm text-muted-foreground">
                  <div className="rounded-lg border border-border/80 bg-card p-3">Secondary info row.</div>
                  <div className="rounded-lg border border-border/80 bg-card p-3">Secondary action row.</div>
                </CardContent>
              </Card>
            </div>
          </ExampleBlock>

          <ExampleBlock title="Feedback and utilities">
            <div className="grid gap-4">
              <div className="grid gap-2">
                <p className="text-sm font-semibold">ScrollArea</p>
                <ScrollArea className="h-36 rounded-lg border border-border bg-muted/30 p-3">
                  <div className="grid gap-2 pr-3 text-sm text-muted-foreground">
                    {Array.from({ length: 8 }).map((_, index) => (
                      <div key={index} className="rounded-md border border-border bg-card px-3 py-2">
                        Workspace row {index + 1}
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </div>

              <EmojiPickerExample />

              <div className="flex flex-wrap gap-2">
                <Dialog>
                  <DialogTrigger render={<Button variant="outline" />}>Открыть modal</DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Применить новые правила</DialogTitle>
                      <DialogDescription>Confirm action example.</DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                      <Button variant="secondary">Отложить</Button>
                      <Button>Применить</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>

                <ConfirmAction
                  title="Удалить запись?"
                  description="Действие нельзя отменить."
                  onConfirm={() => undefined}
                >
                  <Button variant="outline">
                    <Trash2 data-icon="inline-start" />
                    Confirm delete
                  </Button>
                </ConfirmAction>

              <DropdownMenu>
                <DropdownMenuTrigger render={<Button variant="outline" />}>
                  Открыть menu
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuItem>Использовать в employees</DropdownMenuItem>
                  <DropdownMenuItem>Использовать в settings</DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem variant="destructive">Пометить drift</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              <Tooltip>
                <TooltipTrigger render={<Button variant="outline" />}>Hover hint</TooltipTrigger>
                <TooltipContent>
                  Tooltip example.
                </TooltipContent>
              </Tooltip>

              <Button
                variant="secondary"
                onClick={() =>
                  toast("Baseline saved", {
                    description: "Toast example.",
                  })
                }
              >
                Trigger toast
              </Button>
              </div>
            </div>
          </ExampleBlock>
        </div>

        <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
          <ExampleBlock
            title="Navigation primitives"
            code={exampleCode.navigation}
          >
            <div className="space-y-5">
              <Breadcrumb>
                <BreadcrumbList>
                  <BreadcrumbItem>
                    <BreadcrumbLink href="/app/design-system">Admin</BreadcrumbLink>
                  </BreadcrumbItem>
                  <BreadcrumbSeparator>
                    <ChevronRight className="size-3.5" />
                  </BreadcrumbSeparator>
                  <BreadcrumbItem>
                    <BreadcrumbLink href="#patterns">Patterns</BreadcrumbLink>
                  </BreadcrumbItem>
                  <BreadcrumbSeparator />
                  <BreadcrumbItem>
                    <BreadcrumbPage>Detail page</BreadcrumbPage>
                  </BreadcrumbItem>
                </BreadcrumbList>
              </Breadcrumb>

              <Tabs defaultValue="list" className="gap-4">
                <TabsList>
                  <TabsTrigger value="list">List page</TabsTrigger>
                  <TabsTrigger value="detail">Detail page</TabsTrigger>
                  <TabsTrigger value="workspace">Workspace</TabsTrigger>
                </TabsList>
                <TabsContent value="list" className="rounded-xl border border-border/80 bg-muted/30 p-4 text-sm text-muted-foreground">
                  List page block.
                </TabsContent>
                <TabsContent value="detail" className="rounded-xl border border-border/80 bg-muted/30 p-4 text-sm text-muted-foreground">
                  Detail page block.
                </TabsContent>
                <TabsContent value="workspace" className="rounded-xl border border-border/80 bg-muted/30 p-4 text-sm text-muted-foreground">
                  Workspace block.
                </TabsContent>
              </Tabs>
            </div>
          </ExampleBlock>

          <ExampleBlock
            title="Data primitives"
            code={exampleCode.data}
          >
            <div className="space-y-5">
              <Table className="min-w-[560px]">
                <TableHeader>
                  <TableRow className="border-border/80">
                    <TableHead>Entity</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Owner</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow className="border-border/80">
                    <TableCell className="font-medium">Employees list</TableCell>
                    <TableCell><Badge variant="secondary">stable</Badge></TableCell>
                    <TableCell>HR</TableCell>
                    <TableCell className="text-right"><Button size="sm" variant="ghost">Open</Button></TableCell>
                  </TableRow>
                  <TableRow className="border-border/80">
                    <TableCell className="font-medium">Scenario workspace</TableCell>
                    <TableCell><Badge variant="outline">heavy</Badge></TableCell>
                    <TableCell>Ops</TableCell>
                    <TableCell className="text-right"><Button size="sm" variant="ghost">Inspect</Button></TableCell>
                  </TableRow>
                </TableBody>
              </Table>

              <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
                <Card className="border border-border/80 bg-card shadow-none ring-0">
                  <CardContent className="space-y-3 pt-4">
                    <Progress value={progressValue}>
                      <ProgressLabel>React parity pass</ProgressLabel>
                      <ProgressValue>{progressValue}%</ProgressValue>
                    </Progress>
                    <div className="flex gap-2">
                      <Button size="sm" variant="secondary" onClick={() => setProgressValue((value) => Math.max(0, value - 8))}>
                        -8
                      </Button>
                      <Button size="sm" onClick={() => setProgressValue((value) => Math.min(100, value + 8))}>
                        +8
                      </Button>
                    </div>
                  </CardContent>
                </Card>

                <div className="space-y-4">
                  <AvatarGroup>
                    <Avatar>
                      <AvatarFallback>HR</AvatarFallback>
                    </Avatar>
                    <Avatar>
                      <AvatarFallback>OP</AvatarFallback>
                    </Avatar>
                    <Avatar size="lg">
                      <AvatarFallback>QA</AvatarFallback>
                    </Avatar>
                    <AvatarGroupCount>+2</AvatarGroupCount>
                  </AvatarGroup>
                  <div className="flex items-center gap-3">
                    <Skeleton className="h-9 w-28 rounded-xl" />
                    <Skeleton className="h-9 w-40 rounded-xl" />
                  </div>
                </div>
              </div>
            </div>
          </ExampleBlock>
        </div>
      </div>
    </TooltipProvider>
  );
}

function PatternsSection() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 xl:grid-cols-2">
        <PatternCard
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
          title="Shell sidebar"
          icon={LayoutDashboard}
          body="Rail and overlay navigation."
          checklist={[
            "Dashboard uses LayoutDashboard.",
            "Bot pages keep bot/message iconography.",
            "Icon-only links keep aria labels.",
          ]}
        />
        <PatternCard
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

      <Card className="border border-border/80 bg-card shadow-none ring-0">
        <CardHeader className="border-b border-border/70 pb-4">
          <CardTitle className="text-base font-semibold">Composition rules</CardTitle>
        </CardHeader>
        <CardContent className="pt-5">
          <RuleList items={principles} />
        </CardContent>
      </Card>

      <ExampleBlock title="Settings form">
        <SettingsPatternExample />
      </ExampleBlock>

      <ExampleBlock title="Bot menu editor">
        <BotMenuPatternExample />
      </ExampleBlock>

      <ExampleBlock title="Shell sidebar">
        <ShellSidebarPatternExample />
      </ExampleBlock>

      <ExampleBlock title="Confirmation dialog">
        <ConfirmationPatternExample />
      </ExampleBlock>

      <ExampleBlock title="Bulk action console">
        <BulkActionsPatternExample />
      </ExampleBlock>

      <ExampleBlock title="Auth form">
        <AuthPatternExample />
      </ExampleBlock>

      <ExampleBlock title="Detail page building blocks">
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

      <ExampleBlock title="List page item">
        <Card className="w-full min-w-0 rounded-lg border border-border bg-card shadow-none ring-0 transition-colors hover:bg-accent/60">
          <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 space-y-1.5">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="truncate text-[1rem] font-semibold">Востриков Антон Сергеевич</h3>
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
              @AVstrkv
            </Badge>
            <Badge variant="secondary">Выход: 19.06.2026</Badge>
            <Badge variant="secondary">OC от коллег</Badge>
          </CardContent>
        </Card>
      </ExampleBlock>

      <ExampleBlock title="Workspace builder">
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
      <ExampleBlock title="What counts as design debt">
        <RuleList items={antiPatterns} tone="danger" />
      </ExampleBlock>

      <ExampleBlock title="What reviews and watchdogs should check">
        <RuleList items={reviewChecks} />
      </ExampleBlock>
    </div>
  );
}

export function DesignSystemPage() {
  const { theme, toggleTheme } = useDocumentTheme();
  const activeSection = useActiveSection(sectionLinks.map((link) => link.id));
  const handleSectionJump = React.useCallback((sectionId: string) => {
    const target = document.getElementById(sectionId);
    if (!target) return;

    const stickyOffset = 112;
    const top = target.getBoundingClientRect().top + window.scrollY - stickyOffset;

    window.history.replaceState(null, "", `#${sectionId}`);
    window.scrollTo({ top, behavior: "smooth" });
  }, []);

  return (
    <div className="admin-page-stack gap-6 pb-10">
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

      <Card className="sticky top-4 z-40 isolate border border-border/80 bg-background/96 shadow-none ring-0 backdrop-blur supports-[backdrop-filter]:bg-background/88">
        <CardHeader className="gap-4 border-b border-border/70 pb-4">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div className="space-y-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge>HRBot UI baseline</Badge>
                <Badge variant="secondary">Desktop-first</Badge>
                <Badge variant="outline">Shared primitives first</Badge>
                <Badge variant="destructive">No decorative noise yet</Badge>
              </div>
              <div className="space-y-1.5">
                <CardTitle className="text-3xl font-semibold tracking-tight lg:text-[2.15rem]">
                  Design System
                </CardTitle>
                <CardDescription className="max-w-3xl text-sm leading-6 text-muted-foreground">
                  UI baseline.
                </CardDescription>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 xl:justify-end">
              <Button variant="secondary" onClick={toggleTheme}>
                {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
                {theme === "dark" ? "Light mode" : "Dark mode"}
              </Button>
              <Button variant="outline" onClick={() => window.location.assign("/app/settings")}>
                Open live settings
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="flex flex-wrap gap-2">
            {sectionLinks.map(({ id, label, icon: Icon }) => (
              <Button
                key={id}
                variant={activeSection === id ? "secondary" : "ghost"}
                size="sm"
                render={<a href={`#${id}`} />}
                onClick={(event) => {
                  event.preventDefault();
                  handleSectionJump(id);
                }}
              >
                <Icon className="size-4" />
                {label}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      <SectionShell
        id="foundations"
        icon={Palette}
        title="Foundations"
      >
        <FoundationsSection />
      </SectionShell>

      <SectionShell
        id="primitives"
        icon={Layers3}
        title="Primitives"
      >
        <PrimitivesSection />
      </SectionShell>

      <SectionShell
        id="patterns"
        icon={LayoutPanelTop}
        title="Patterns"
      >
        <PatternsSection />
      </SectionShell>

      <SectionShell
        id="review-rules"
        icon={CircleHelp}
        title="Review rules"
      >
        <ReviewRulesSection />
      </SectionShell>

      <Card className="border border-border/80 bg-muted/30 shadow-none ring-0">
        <CardHeader className="border-b border-border/70 pb-4">
          <CardTitle className="text-lg font-semibold">Rollout</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 pt-5 text-sm leading-6 text-foreground/85 xl:grid-cols-3">
          <div className="rounded-lg border border-border/80 bg-card p-4">
            1. Stabilize `Button`, `Input`, `Select`, `Card`, `Table`.
          </div>
          <div className="rounded-lg border border-border/80 bg-card p-4">
            2. Align `/app/employees`, `/app/settings`, `/app/bulk-actions`.
          </div>
          <div className="rounded-lg border border-border/80 bg-card p-4">
            3. Add corporate layer after layout lock.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
