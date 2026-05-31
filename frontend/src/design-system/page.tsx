import React from "react";
import {
  ChevronRight,
  Columns2,
  CircleHelp,
  LayoutPanelTop,
  Layers3,
  ListFilter,
  Moon,
  MousePointer2,
  Palette,
  Rows3,
  Sun,
} from "lucide-react";
import { Toaster as SonnerToaster, toast } from "sonner";

import { Avatar, AvatarFallback, AvatarGroup, AvatarGroupCount } from "@/components/ui/avatar";
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
  FieldSet,
  FieldTitle,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Progress, ProgressLabel, ProgressValue } from "@/components/ui/progress";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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

const THEME_STORAGE_KEY = "theme";

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
      { label: "Background", variable: "--background", value: "#FAFAF9 / #141412" },
      { label: "Card", variable: "--card", value: "#FFFFFF / #1C1B18" },
      { label: "Muted", variable: "--muted", value: "#F5F4F2 / #252420" },
      { label: "Border", variable: "--border", value: "#E8E6E1 / #2E2C28" },
    ],
  },
  {
    title: "Text",
    items: [
      { label: "Foreground", variable: "--foreground", value: "#1A1916 / #F5F3EF" },
      { label: "Muted foreground", variable: "--muted-foreground", value: "#6B6963 / #8C8880" },
      { label: "Primary foreground", variable: "--primary-foreground", value: "#FFFFFF" },
    ],
  },
  {
    title: "Action",
    items: [
      { label: "Primary", variable: "--primary", value: "#339160 / #4AAD7A" },
      { label: "Secondary", variable: "--secondary", value: "#F5F4F2 / #252420" },
      { label: "Ring", variable: "--ring", value: "#339160 / #4AAD7A" },
      { label: "Destructive", variable: "--destructive", value: "#DC2626 / #EF4444" },
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

const radiusScale = [
  { label: "rounded-md", className: "rounded-md" },
  { label: "rounded-lg", className: "rounded-lg" },
  { label: "rounded-xl", className: "rounded-xl" },
  { label: "rounded-2xl", className: "rounded-2xl" },
];

const principles = [
  "Desktop-first, documentation-style плотность, без маркетинговой декоративности.",
  "Один primary accent и один destructive signal. Всё остальное должно читаться как нейтральная структура.",
  "Новый экран должен объясняться через существующие примитивы и page patterns, а не через локальные хаки.",
];

const antiPatterns = [
  "Page-local button styles и ad-hoc wrappers внутри конкретного `page.tsx`.",
  "Hover-эффекты, которые меняют геометрию интерфейса сильнее, чем объясняют affordance.",
  "Смешивание classic-визуала и новых React primitives внутри одной рабочей секции.",
  "Новые “особенные” компоненты до попытки починить существующий primitive centrally.",
];

const reviewChecks = [
  "Используются semantic tokens, а не hardcoded white/black/green.",
  "Кнопки и поля идут через shared UI API, а не через локальные div-based имитации.",
  "Основные секции страницы собираются из повторяемых panel/pattern блоков.",
  "Legacy fallback links не притворяются полезными действиями, если они просто редиректят обратно в React.",
  "Никаких теней как основного depth-сигнала: MVP UI держится на contrast, border и spacing.",
];

const exampleCode = {
  button: `<div className="flex flex-wrap gap-2">
  <Button>Сохранить</Button>
  <Button variant="secondary">Применить позже</Button>
  <Button variant="outline">Открыть детали</Button>
  <Button variant="destructive">Удалить</Button>
</div>`,
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
  const [theme, setTheme] = React.useState<"light" | "dark">("light");

  React.useEffect(() => {
    const root = document.documentElement;
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    const nextTheme = stored === "dark" ? "dark" : "light";

    root.classList.toggle("dark", nextTheme === "dark");
    setTheme(nextTheme);
  }, []);

  const toggleTheme = React.useCallback(() => {
    const root = document.documentElement;

    setTheme((currentTheme) => {
      const nextTheme = currentTheme === "dark" ? "light" : "dark";
      root.classList.toggle("dark", nextTheme === "dark");
      window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
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

function FoundationsSection() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 xl:grid-cols-3">
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
  const [notes, setNotes] = React.useState(
    "Новые страницы должны собираться из shared primitives, а не из локально нарисованных контролов.",
  );
  const [checkboxValue, setCheckboxValue] = React.useState(true);
  const [radioValue, setRadioValue] = React.useState("operators");
  const [denseMode, setDenseMode] = React.useState(true);
  const [progressValue, setProgressValue] = React.useState(72);

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
                <Button variant="destructive">Удалить</Button>
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
                    <SelectContent>
                      <SelectItem value="draft">Draft</SelectItem>
                      <SelectItem value="review">Review</SelectItem>
                      <SelectItem value="ready">Ready</SelectItem>
                    </SelectContent>
                  </Select>
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
            <div className="flex flex-wrap gap-2">
              <Dialog>
                <DialogTrigger render={<Button variant="outline" />}>Открыть modal</DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Применить новые правила</DialogTitle>
                    <DialogDescription>
                      Confirm action example.
                    </DialogDescription>
                  </DialogHeader>
                  <DialogFooter>
                    <Button variant="secondary">Отложить</Button>
                    <Button>Применить</Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>

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
          title="Workspace page"
          icon={LayoutPanelTop}
          body="Navigation, canvas, detail."
          checklist={[
            "Navigation column.",
            "Canvas column.",
            "Detail column.",
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
    <div className="mx-auto grid w-full max-w-[1720px] gap-6 pb-10">
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

      <Card className="sticky top-4 z-0 border border-border/80 bg-background/96 shadow-none ring-0 backdrop-blur supports-[backdrop-filter]:bg-background/88">
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
