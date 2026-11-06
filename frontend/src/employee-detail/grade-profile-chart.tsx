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

export function GradeProfileChart({ categories, withTarget, secondaryLabel = "Цель", currentLabel = "Текущий" }: { categories: Category[]; withTarget: boolean; secondaryLabel?: string; currentLabel?: string }) {
  const percentCategories = categories.map(c => ({...c, current: c.current / 4 * 100, target: c.target / 4 * 100}));
  if (!categories.length) return <p className="text-muted-foreground">Нет категорий для профиля навыков.</p>;
  return <figure className="space-y-3">
    {categories.length >= RADAR_MIN_CATEGORIES
      ? <ChartContainer config={{ current: { label: currentLabel, color: "var(--primary)" }, target: { label: secondaryLabel, color: "var(--info)" } }} className="mx-auto aspect-[4/3] w-full max-w-96" aria-label={withTarget ? `Радар: ${currentLabel} и ${secondaryLabel}` : "Радар фактической оценки"}>
        <RadarChart data={percentCategories} outerRadius="65%" margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <PolarGrid /><PolarAngleAxis dataKey="categoryName" tickFormatter={(_name, index) => String(index + 1)} /><PolarRadiusAxis domain={[0, 100]} tickCount={5} axisLine={false} tick={false} />
          {withTarget && <Radar name={secondaryLabel} dataKey="target" stroke="var(--color-target)" fill="var(--color-target)" fillOpacity={0.08} strokeDasharray="4 3" isAnimationActive={false} />}
          <Radar name={currentLabel} dataKey="current" stroke="var(--color-current)" fill="var(--color-current)" fillOpacity={0.25} isAnimationActive={false} />
          <ChartTooltip content={<ChartTooltipContent formatter={value => `${Number(value).toFixed(1)}%`} />} />
        </RadarChart>
      </ChartContainer>
      : <ul className="space-y-3" aria-label={withTarget ? `Уровни: текущая оценка и ${secondaryLabel}` : "Фактические уровни по категориям"}>{categories.map(c => <li key={c.categoryId} className="space-y-1.5">
        <p className="text-sm break-words">{c.categoryName}</p>
        <LevelBar label={currentLabel} value={c.current} className="bg-primary" />
        {withTarget && <LevelBar label={secondaryLabel} value={c.target} className="border border-dashed border-info bg-info/10" />}
      </li>)}</ul>}
    <figcaption className="flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
      <span className="inline-flex items-center gap-1.5"><span aria-hidden="true" className="h-2.5 w-4 shrink-0 rounded-sm bg-primary" />{currentLabel} (сплошная)</span>
      {withTarget && <span className="inline-flex items-center gap-1.5"><span aria-hidden="true" className="h-2.5 w-4 rounded-sm border border-dashed border-info bg-info/10" />{secondaryLabel} (пунктир)</span>}
    </figcaption>
    {categories.length >= RADAR_MIN_CATEGORIES && <ol className="space-y-1.5 text-xs" aria-label="Категории графика">{categories.map((category, index) => <li key={category.categoryId} className="flex min-w-0 items-baseline gap-2">
      <span className="shrink-0 tabular-nums text-muted-foreground">{index + 1}.</span>
      <span className="min-w-0 break-words [overflow-wrap:anywhere]">{category.categoryName}</span>
      <span className="ml-auto shrink-0 tabular-nums">{(category.current / 4 * 100).toFixed(1)}%{withTarget && ` / ${(category.target / 4 * 100).toFixed(1)}%`}</span>
    </li>)}</ol>}
  </figure>;
}

function LevelBar({ label, value, className }: { label: string; value: number; className: string }) {
  return <div className="grid grid-cols-[minmax(0,8rem)_minmax(0,1fr)_2.5rem] items-center gap-2 text-xs">
    <span className="break-words text-muted-foreground">{label}</span>
    <span className="h-2.5 rounded-sm bg-muted" role="img" aria-label={`${label}: ${(value / 4 * 100).toFixed(1)}%`}><span className={`block h-full rounded-sm ${className}`} style={{ width: `${Math.max(0, Math.min(1, value / 4)) * 100}%` }} /></span>
    <span className="text-right tabular-nums">{(value / 4 * 100).toFixed(0)}%</span>
  </div>;
}
