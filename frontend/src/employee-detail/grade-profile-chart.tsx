import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart } from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import type { Assessment } from "@/grades/types";

type Category = Assessment["categories"][number];

/*
 * Профиль навыков по категориям.
 *
 * Паутинка имеет смысл только от трёх осей: одна категория даёт отрезок,
 * две — линию, и оба варианта читались как сломанный график. Ниже трёх
 * категорий показываем те же числа парой полос на категорию; арифметика
 * и payload не меняются, меняется только представление.
 *
 * Размер радара ограничен сам по себе, а не шириной колонки: в одноколоночной
 * раскладке `aspect-square w-full` растягивал его на весь экран и уводил
 * прогресс и пробелы за нижнюю границу окна.
 */
const RADAR_MIN_CATEGORIES = 3;
const LABEL_LIMIT = 10;

function shortLabel(name: unknown) {
  const text = String(name);
  return text.length > LABEL_LIMIT ? `${text.slice(0, LABEL_LIMIT - 1)}…` : text;
}

export function GradeProfileChart({ categories, withTarget }: { categories: Category[]; withTarget: boolean }) {
  if (!categories.length) return <p className="text-muted-foreground">Нет категорий для профиля навыков.</p>;
  return <figure className="space-y-3">
    {categories.length >= RADAR_MIN_CATEGORIES
      ? <ChartContainer config={{ current: { label: "Текущий", color: "var(--primary)" }, target: { label: "Цель", color: "var(--info)" } }} className="mx-auto aspect-[4/3] w-full max-w-80" aria-label="Радар по категориям: текущие и целевые уровни">
        <RadarChart data={categories} outerRadius="65%" margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <PolarGrid /><PolarAngleAxis dataKey="categoryName" tickFormatter={shortLabel} /><PolarRadiusAxis domain={[0, 4]} tickCount={5} axisLine={false} tick={false} />
          {withTarget && <Radar name="Цель" dataKey="target" stroke="var(--color-target)" fill="var(--color-target)" fillOpacity={0.08} strokeDasharray="4 3" isAnimationActive={false} />}
          <Radar name="Текущий" dataKey="current" stroke="var(--color-current)" fill="var(--color-current)" fillOpacity={0.25} isAnimationActive={false} />
          <ChartTooltip content={<ChartTooltipContent />} />
        </RadarChart>
      </ChartContainer>
      : <ul className="space-y-3" aria-label="Уровни по категориям: текущие и целевые">{categories.map(c => <li key={c.categoryId} className="space-y-1.5">
        <p className="text-sm break-words">{c.categoryName}</p>
        <LevelBar label="Текущий" value={c.current} className="bg-primary" />
        {withTarget && <LevelBar label="Цель" value={c.target} className="border border-dashed border-info bg-info/10" />}
      </li>)}</ul>}
    <figcaption className="flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
      <span className="inline-flex items-center gap-1.5"><span aria-hidden="true" className="h-2.5 w-4 rounded-sm bg-primary" />Текущий (сплошная)</span>
      {withTarget && <span className="inline-flex items-center gap-1.5"><span aria-hidden="true" className="h-2.5 w-4 rounded-sm border border-dashed border-info bg-info/10" />Цель (пунктир)</span>}
    </figcaption>
  </figure>;
}

function LevelBar({ label, value, className }: { label: string; value: number; className: string }) {
  return <div className="grid grid-cols-[4.5rem_minmax(0,1fr)_2.5rem] items-center gap-2 text-xs">
    <span className="text-muted-foreground">{label}</span>
    <span className="h-2.5 rounded-sm bg-muted" role="img" aria-label={`${label}: ${value.toFixed(1)} из 4`}><span className={`block h-full rounded-sm ${className}`} style={{ width: `${Math.max(0, Math.min(1, value / 4)) * 100}%` }} /></span>
    <span className="text-right tabular-nums">{value.toFixed(1)}</span>
  </div>;
}
