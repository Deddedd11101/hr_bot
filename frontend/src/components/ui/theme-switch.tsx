import React from "react";
import { Moon, Sun } from "lucide-react";

import { cn } from "@/lib/utils";
import {
  applyDocumentTheme,
  readDocumentTheme,
  readStoredTheme,
  THEME_CHANGE_EVENT,
  type AppTheme,
} from "@/lib/theme";

type ViewTransitionDocument = Document & {
  startViewTransition?: (update: () => void) => {
    ready: Promise<unknown>;
    finished: Promise<unknown>;
  };
};

export interface ThemeSwitchProps {
  iconSize?: number;
  className?: string;
}

function applyWithTransition(origin: { x: number; y: number }, apply: () => void) {
  const transitionDocument = document as ViewTransitionDocument;
  const root = document.documentElement;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (!transitionDocument.startViewTransition || window.innerWidth > 1800 || reduceMotion) {
    apply();
    return;
  }

  const { x, y } = origin;
  const endRadius = Math.hypot(
    Math.max(x, window.innerWidth - x),
    Math.max(y, window.innerHeight - y),
  );

  document.documentElement.style.setProperty("--theme-switch-x", `${x}px`);
  document.documentElement.style.setProperty("--theme-switch-y", `${y}px`);
  document.documentElement.style.setProperty("--theme-switch-radius", `${endRadius}px`);
  root.dataset.themeSwitchTransition = "true";

  try {
    const transition = transitionDocument.startViewTransition(apply);
    transition.ready.catch(() => undefined);
    transition.finished
      .finally(() => {
        delete root.dataset.themeSwitchTransition;
      })
      .catch(() => undefined);
  } catch {
    delete root.dataset.themeSwitchTransition;
    apply();
  }
}

export function ThemeSwitch({ iconSize = 16, className }: ThemeSwitchProps) {
  const [theme, setTheme] = React.useState<AppTheme>(() => readStoredTheme());

  React.useEffect(() => {
    const syncTheme = () => setTheme(readDocumentTheme());

    syncTheme();
    window.addEventListener(THEME_CHANGE_EVENT, syncTheme);
    window.addEventListener("storage", syncTheme);
    return () => {
      window.removeEventListener(THEME_CHANGE_EVENT, syncTheme);
      window.removeEventListener("storage", syncTheme);
    };
  }, []);

  const isDark = theme === "dark";

  const toggleTheme = (event: React.MouseEvent<HTMLButtonElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const origin = event.detail === 0
      ? { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
      : { x: event.clientX, y: event.clientY };
    const nextTheme: AppTheme = isDark ? "light" : "dark";

    applyWithTransition(origin, () => applyDocumentTheme(nextTheme));
  };

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={cn(
        "relative flex size-9 cursor-pointer items-center justify-center overflow-hidden rounded-full border border-border bg-accent text-foreground outline-none transition-transform duration-200",
        "hover:scale-105 active:scale-95 motion-reduce:transition-none motion-reduce:hover:scale-100 motion-reduce:active:scale-100",
        "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        className,
      )}
      aria-label="Тёмная тема"
      aria-pressed={isDark}
      title={isDark ? "Включить светлую тему" : "Включить тёмную тему"}
    >
      <span
        className={cn(
          "absolute inset-0 flex items-center justify-center transition-[opacity,transform] duration-200 motion-reduce:transition-none",
          isDark ? "scale-75 rotate-45 opacity-0" : "scale-100 rotate-0 opacity-100",
        )}
      >
        <Sun aria-hidden="true" size={iconSize} />
      </span>
      <span
        className={cn(
          "absolute inset-0 flex items-center justify-center transition-[opacity,transform] duration-200 motion-reduce:transition-none",
          isDark ? "scale-100 rotate-0 opacity-100" : "scale-75 -rotate-45 opacity-0",
        )}
      >
        <Moon aria-hidden="true" size={iconSize} />
      </span>
    </button>
  );
}
