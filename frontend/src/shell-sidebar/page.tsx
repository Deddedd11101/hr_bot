import React from "react";
import {
  BadgeCheck,
  Bot,
  Braces,
  FileCheck2,
  LogOut,
  Moon,
  PanelLeft,
  Settings,
  Sparkles,
  Sun,
  Users,
  Workflow,
  X,
} from "lucide-react";

import {
  applyDocumentTheme,
  readDocumentTheme,
  readStoredTheme,
  THEME_CHANGE_EVENT,
  type AppTheme,
} from "@/lib/theme";

type SidebarPageProps = {
  activeTab: string;
  roleLabel: string;
};

const OPEN_KEY = "app-shell-sidebar-open";

const primaryItems = [
  { key: "employees", label: "Сотрудники", href: "/app/employees", icon: Users },
  { key: "bulk_actions", label: "Массовые действия", href: "/app/bulk-actions", icon: Sparkles },
  { key: "flows", label: "Сценарии", href: "/app/flows/workspace-v2", icon: Workflow },
  { key: "surveys", label: "Опросы", href: "/app/surveys/workspace", icon: FileCheck2 },
] as const;

const secondaryItems = [
  { key: "design_system", label: "Дизайн-система", href: "/app/design-system", icon: Braces },
  { key: "settings", label: "Настройки", href: "/app/settings", icon: Settings },
] as const;

function normalizeActiveTab(activeTab: string) {
  if (activeTab === "candidates") return "employees";
  return activeTab;
}

function useInitialOpenState() {
  return React.useMemo(() => {
    if (typeof window === "undefined") return false;
    return window.sessionStorage.getItem(OPEN_KEY) === "1";
  }, []);
}

function useShellTheme() {
  const [theme, setTheme] = React.useState<AppTheme>(() => {
    if (typeof window === "undefined") return "light";
    return readStoredTheme();
  });

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

function SidebarNavLink({
  href,
  label,
  active,
  compact = false,
  onNavigate,
  icon: Icon,
}: {
  href: string;
  label: string;
  active: boolean;
  compact?: boolean;
  onNavigate: () => void;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <a
      href={href}
      title={label}
      className={`app-shell-nav-link${compact ? " is-compact" : ""}${active ? " is-active" : ""}`}
      aria-current={active ? "page" : undefined}
      onClick={onNavigate}
    >
      <span className="app-shell-nav-icon" aria-hidden="true">
        <Icon className="size-5" />
      </span>
      {!compact ? <span className="app-shell-nav-text">{label}</span> : null}
    </a>
  );
}

export function ShellSidebarPage({ activeTab, roleLabel }: SidebarPageProps) {
  const normalizedActiveTab = normalizeActiveTab(activeTab);
  const initialOpen = useInitialOpenState();
  const [open, setOpen] = React.useState(initialOpen);
  const { theme, toggleTheme } = useShellTheme();
  const ThemeIcon = theme === "dark" ? Sun : Moon;
  const themeLabel = theme === "dark" ? "Включить светлую тему" : "Включить темную тему";

  React.useEffect(() => {
    document.documentElement.toggleAttribute("data-shell-sidebar-open", open);
    window.sessionStorage.setItem(OPEN_KEY, open ? "1" : "0");
  }, [open]);

  React.useEffect(() => {
    function handleKeydown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, []);

  const handleClose = React.useCallback(() => setOpen(false), []);
  const handleToggle = React.useCallback(() => setOpen((value) => !value), []);

  const persistCurrentState = React.useCallback(() => {
    window.sessionStorage.setItem(OPEN_KEY, open ? "1" : "0");
  }, [open]);

  const persistOpenState = React.useCallback(() => {
    window.sessionStorage.setItem(OPEN_KEY, "1");
  }, []);

  return (
    <div className={`app-shell-sidebar-root${open ? " is-open" : ""}`}>
      <div className="app-shell-sidebar-rail">
        <div className="app-shell-sidebar-rail-group">
          <button
            type="button"
            className="app-shell-trigger"
            onClick={handleToggle}
            aria-label={open ? "Закрыть навигацию" : "Открыть навигацию"}
            aria-expanded={open}
          >
            {open ? <X className="size-5" /> : <PanelLeft className="size-5" />}
          </button>

          <a
            href="/app/employees"
            className="app-shell-brand"
            aria-label="HR Bot Admin"
            onClick={persistCurrentState}
          >
            <span className="app-shell-brand-icon" aria-hidden="true">
              <Bot className="size-5" />
            </span>
          </a>

          <nav className="app-shell-rail-nav" aria-label="Основная навигация">
            {primaryItems.map((item) => (
              <SidebarNavLink
                key={item.key}
                href={item.href}
                label={item.label}
                icon={item.icon}
                compact
                active={normalizedActiveTab === item.key}
                onNavigate={persistCurrentState}
              />
            ))}
          </nav>
        </div>

        <div className="app-shell-sidebar-rail-group">
          <nav className="app-shell-rail-nav" aria-label="Системная навигация">
            {secondaryItems.map((item) => (
              <SidebarNavLink
                key={item.key}
                href={item.href}
                label={item.label}
                icon={item.icon}
                compact
                active={normalizedActiveTab === item.key}
                onNavigate={persistCurrentState}
              />
            ))}
          </nav>

          <div className="app-shell-rail-chip" title={roleLabel}>
            <BadgeCheck className="size-5" />
          </div>

          <button
            type="button"
            className="app-shell-rail-button"
            aria-label={themeLabel}
            title={themeLabel}
            onClick={toggleTheme}
          >
            <ThemeIcon className="size-5" />
          </button>

          <form method="post" action="/logout" className="app-shell-logout-form">
            <button type="submit" className="app-shell-rail-button" aria-label="Выйти">
              <LogOut className="size-5" />
            </button>
          </form>
        </div>
      </div>

      <div className="app-shell-sidebar-overlay" aria-hidden={!open}>
        <button
          type="button"
          className="app-shell-sidebar-backdrop"
          onClick={handleClose}
          aria-label="Закрыть навигацию"
          tabIndex={open ? 0 : -1}
        />

        <aside className="app-shell-sidebar-panel" aria-label="Навигация">
          <div className="app-shell-sidebar-panel-head">
            <a
              href="/app/employees"
              className="app-shell-panel-brand"
              aria-label="HR Bot Admin"
              onClick={persistOpenState}
            >
              <span className="app-shell-brand-icon" aria-hidden="true">
                <Bot className="size-5" />
              </span>
              <span className="app-shell-panel-brand-copy">
                <span className="app-shell-panel-brand-title">HR Bot Admin</span>
                <span className="app-shell-panel-brand-subtitle">Operator shell</span>
              </span>
            </a>

            <button
              type="button"
              className="app-shell-panel-close"
              onClick={handleClose}
              aria-label="Закрыть навигацию"
            >
              <X className="size-5" />
            </button>
          </div>

          <div className="app-shell-sidebar-panel-body">
            <nav className="app-shell-panel-nav" aria-label="Основная навигация">
              {primaryItems.map((item) => (
                <SidebarNavLink
                  key={item.key}
                  href={item.href}
                  label={item.label}
                  icon={item.icon}
                  active={normalizedActiveTab === item.key}
                  onNavigate={persistOpenState}
                />
              ))}
            </nav>

            <div className="app-shell-panel-section-label">System</div>

            <nav className="app-shell-panel-nav" aria-label="Системная навигация">
              {secondaryItems.map((item) => (
                <SidebarNavLink
                  key={item.key}
                  href={item.href}
                  label={item.label}
                  icon={item.icon}
                  active={normalizedActiveTab === item.key}
                  onNavigate={persistOpenState}
                />
              ))}
            </nav>
          </div>

          <div className="app-shell-sidebar-panel-foot">
            <div className="app-shell-role-pill">
              <BadgeCheck className="size-4" />
              <span>{roleLabel}</span>
            </div>

            <button type="button" className="app-shell-nav-link" onClick={toggleTheme}>
              <span className="app-shell-nav-icon" aria-hidden="true">
                <ThemeIcon className="size-5" />
              </span>
              <span className="app-shell-nav-text">
                {theme === "dark" ? "Светлая тема" : "Темная тема"}
              </span>
            </button>

            <form method="post" action="/logout" className="app-shell-logout-form">
              <button type="submit" className="app-shell-nav-link">
                <span className="app-shell-nav-icon" aria-hidden="true">
                  <LogOut className="size-5" />
                </span>
                <span className="app-shell-nav-text">Выйти</span>
              </button>
            </form>
          </div>
        </aside>
      </div>

    </div>
  );
}
