import * as React from "react";
import { ChevronRight, Search } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

import {
  buildNavigationTree,
  searchCatalog,
  type CatalogEntry,
} from "./registry";

type NavEntry = Pick<CatalogEntry, "id" | "navLabel" | "href" | "summary" | "status">;

/**
 * Активная запись задаётся адресом страницы.
 *
 * Раньше здесь жило слежение за прокруткой: каталог был одним полотном,
 * и текущий блок приходилось вычислять по положению. С переходом на
 * страницу-на-запись вычислять нечего — источником правды стал hash.
 */
export function useHashEntry(fallbackId: string) {
  const read = React.useCallback(
    () => window.location.hash.slice(1) || fallbackId,
    [fallbackId],
  );
  const [activeId, setActiveId] = React.useState(read);

  React.useEffect(() => {
    const sync = () => setActiveId(read());
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, [read]);

  return activeId;
}

function NavLink({
  entry,
  isActive,
  reduceMotion,
  onSelect,
}: {
  entry: NavEntry;
  isActive: boolean;
  reduceMotion: boolean;
  onSelect: (entry: NavEntry) => void;
}) {
  return (
    <a
      href={entry.href}
      title={entry.summary}
      aria-current={isActive ? "page" : undefined}
      onClick={(event) => {
        event.preventDefault();
        onSelect(entry);
      }}
      className={cn(
        "group relative flex items-center gap-2 rounded-lg py-1.5 pl-4 pr-2 text-sm outline-none transition-colors",
        "focus-visible:ring-3 focus-visible:ring-ring/50",
        isActive
          ? "font-medium text-foreground"
          : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
        // Неиспользуемое видно, но не притягивает взгляд наравне с рабочим.
        entry.status === "unused" && !isActive ? "text-muted-foreground/55" : "",
      )}
    >
      {isActive ? (
        <motion.span
          aria-hidden="true"
          layoutId="docs-nav-active"
          className="absolute left-0 top-1 bottom-1 w-0.5 rounded-full bg-primary"
          transition={
            reduceMotion
              ? { duration: 0 }
              : { type: "spring", stiffness: 520, damping: 38, mass: 0.7 }
          }
        />
      ) : (
        <span
          aria-hidden="true"
          className="absolute left-0 top-1/2 h-1 w-0.5 -translate-y-1/2 rounded-full bg-border opacity-0 transition-opacity group-hover:opacity-100"
        />
      )}
      <span className="truncate">{entry.navLabel}</span>
      {entry.status === "unused" ? (
        <span
          aria-hidden="true"
          title="Компонент не используется нигде"
          className="ml-auto size-1.5 shrink-0 rounded-full bg-muted-foreground/40"
        />
      ) : null}
    </a>
  );
}

function NavSection({
  label,
  entries,
  activeId,
  reduceMotion,
  forceOpen,
  onSelect,
}: {
  label: string;
  entries: NavEntry[];
  activeId: string;
  reduceMotion: boolean;
  forceOpen: boolean;
  onSelect: (entry: NavEntry) => void;
}) {
  const contentId = React.useId();
  const holdsActive = entries.some((entry) => entry.id === activeId);
  const [open, setOpen] = React.useState(true);

  // Раздел с активным блоком всегда раскрыт: иначе активный пункт не виден.
  const expanded = forceOpen || holdsActive || open;

  const list = (
    <div id={contentId} className="mt-0.5 flex flex-col gap-0.5 border-l border-border/70 pl-1">
      {entries.map((entry) => (
        <NavLink
          key={entry.id}
          entry={entry}
          isActive={entry.id === activeId}
          reduceMotion={reduceMotion}
          onSelect={onSelect}
        />
      ))}
    </div>
  );

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls={contentId}
        onClick={() => setOpen((previous) => !previous)}
        className={cn(
          // Второй уровень отличается от первого только размером и приглушённостью:
          // одинаковая грамматика делает дерево читаемым на любой глубине.
          "flex w-full items-center gap-1.5 rounded-lg px-1 py-1 text-left text-[0.82rem] font-medium outline-none transition-colors",
          "text-muted-foreground hover:bg-accent/50 hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50",
        )}
      >
        <ChevronRight
          aria-hidden="true"
          className={cn(
            "size-3 shrink-0 transition-transform",
            reduceMotion ? "" : "duration-200",
            expanded ? "rotate-90" : "",
          )}
        />
        <span className="min-w-0 truncate">{label}</span>
        <span className="ml-auto shrink-0 text-xs font-normal tabular-nums text-muted-foreground/60">
          {entries.length}
        </span>
      </button>
      {expanded ? list : null}
    </div>
  );
}

type NavSectionData = {
  id: string;
  label: string;
  entries: NavEntry[];
};

/**
 * Первый уровень навигации: группа каталога. Раскрывается так же, как
 * раздел внутри неё, поэтому дерево читается одинаково на всех уровнях.
 */
function NavGroup({
  label,
  sections,
  activeId,
  reduceMotion,
  forceOpen,
  onSelect,
}: {
  label: string;
  sections: NavSectionData[];
  activeId: string;
  reduceMotion: boolean;
  forceOpen: boolean;
  onSelect: (entry: NavEntry) => void;
}) {
  const contentId = React.useId();
  const holdsActive = sections.some((section) =>
    section.entries.some((entry) => entry.id === activeId),
  );
  const [open, setOpen] = React.useState(true);
  const expanded = forceOpen || holdsActive || open;
  const total = sections.reduce((sum, section) => sum + section.entries.length, 0);

  return (
    <div className="flex flex-col">
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls={contentId}
        onClick={() => setOpen((previous) => !previous)}
        className={cn(
          "flex w-full items-center gap-1.5 rounded-lg px-1 py-1.5 text-left text-sm font-semibold outline-none transition-colors",
          "text-foreground hover:bg-accent/50 focus-visible:ring-3 focus-visible:ring-ring/50",
        )}
      >
        <ChevronRight
          aria-hidden="true"
          className={cn(
            "size-3.5 shrink-0 text-muted-foreground transition-transform",
            reduceMotion ? "" : "duration-200",
            expanded ? "rotate-90" : "",
          )}
        />
        <span className="min-w-0 truncate">{label}</span>
        <span className="ml-auto shrink-0 text-xs font-normal tabular-nums text-muted-foreground/60">
          {total}
        </span>
      </button>

      {expanded ? (
        <div id={contentId} className="mt-1 flex flex-col gap-2.5 pl-3">
          {sections.map((section) => (
            <NavSection
              key={section.id}
              label={section.label}
              entries={section.entries}
              activeId={activeId}
              reduceMotion={reduceMotion}
              forceOpen={forceOpen}
              onSelect={onSelect}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function DocsNav({
  activeId,
  className,
}: {
  activeId: string;
  className?: string;
}) {
  const reduceMotion = Boolean(useReducedMotion());
  const [query, setQuery] = React.useState("");

  const tree = React.useMemo(() => buildNavigationTree(), []);

  const matches = React.useMemo(() => {
    if (!query.trim()) return null;
    return new Set(searchCatalog(query).map((entry) => entry.id));
  }, [query]);

  const selectEntry = React.useCallback((entry: NavEntry) => {
    // Смена страницы каталога — это новая запись в истории: «назад»
    // должен возвращать на предыдущую запись, а не выкидывать со страницы.
    window.location.hash = entry.id;
    window.scrollTo({ top: 0, behavior: "auto" });
  }, []);

  const visibleTree = tree
    .map((group) => ({
      ...group,
      sections: group.sections
        .map((section) => ({
          ...section,
          entries: matches ? section.entries.filter((entry) => matches.has(entry.id)) : section.entries,
        }))
        .filter((section) => section.entries.length > 0),
    }))
    .filter((group) => group.sections.length > 0);

  return (
    <nav aria-label="Разделы дизайн-системы" className={cn("flex flex-col gap-4", className)}>
      <div className="relative">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Найти блок"
          aria-label="Поиск по каталогу дизайн-системы"
          className="h-9 pl-8"
        />
      </div>

      {visibleTree.length ? (
        <div className="flex flex-col gap-1.5">
          {visibleTree.map((group) => (
            <NavGroup
              key={group.group}
              label={group.label}
              sections={group.sections}
              activeId={activeId}
              reduceMotion={reduceMotion}
              forceOpen={Boolean(matches)}
              onSelect={selectEntry}
            />
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-border/80 bg-muted/30 px-3 py-6 text-center text-sm text-muted-foreground">
          Ничего не найдено по запросу «{query}»
        </div>
      )}
    </nav>
  );
}
