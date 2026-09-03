import React from "react";
import {
  BadgeCheck,
  Bot,
  ChevronLeft,
  ChevronRight,
  FolderOpen,
  FileCheck2,
  LayoutDashboard,
  LogOut,
  Send,
  Settings,
  Users,
  Workflow,
} from "lucide-react";

import { applyDocumentTheme, readStoredTheme, THEME_CHANGE_EVENT } from "@/lib/theme";

type SidebarPageProps = {
  activeTab: string;
  roleLabel: string;
};

const OPEN_KEY = "app-shell-sidebar-open";

/**
 * Ниже этой ширины раздвигать контент некуда: рельс 86px плюс раскрытие
 * до 252px не оставляет места. Там раскрытый рельс ложится поверх контента,
 * и только там уместны затемнение и закрытие по Escape.
 */
const OVERLAY_QUERY = "(max-width: 900px)";

/**
 * Один список: системные разделы стоят вместе с остальными, отдельной группы
 * внизу больше нет. Снизу остаётся только карточка роли.
 */
const navItems = [
  { key: "dashboard", label: "Дашборд", href: "/app/dashboard", icon: LayoutDashboard },
  { key: "employees", label: "Люди", href: "/app/employees", icon: Users },
  { key: "messages", label: "Сообщения", href: "/app/messages", icon: Send },
  { key: "flows", label: "Сценарии", href: "/app/flows/workspace-v2", icon: Workflow },
  { key: "surveys", label: "Опросы", href: "/app/surveys/workspace", icon: FileCheck2 },
  { key: "bot_menu", label: "Меню бота", href: "/app/bot-menu", icon: Bot },
  { key: "documents", label: "Документы", href: "/app/documents", icon: FolderOpen },
  { key: "settings", label: "Настройки", href: "/app/settings", icon: Settings },
] as const;

function normalizeActiveTab(activeTab: string) {
  if (activeTab === "candidates") return "employees";
  return activeTab;
}

/**
 * Состояние живёт в localStorage, а не в sessionStorage: раскрытое меню —
 * это предпочтение пользователя, оно не должно сбрасываться в новой вкладке.
 */
function useInitialOpenState() {
  return React.useMemo(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem(OPEN_KEY) === "1";
  }, []);
}

function useOverlayMode() {
  const [overlay, setOverlay] = React.useState(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia(OVERLAY_QUERY).matches;
  });

  React.useEffect(() => {
    const query = window.matchMedia(OVERLAY_QUERY);
    setOverlay(query.matches);

    function handleChange(event: MediaQueryListEvent) {
      setOverlay(event.matches);
    }

    query.addEventListener("change", handleChange);
    return () => query.removeEventListener("change", handleChange);
  }, []);

  return overlay;
}

/**
 * Переключатель темы переехал в «Настройки», но синхронизация осталась здесь:
 * сайдбар есть на каждой странице, и без него смена темы в одной вкладке
 * не доезжала бы до остальных до перезагрузки. UI тут больше нет — только
 * применение чужого изменения.
 */
function useThemeSync() {
  React.useEffect(() => {
    applyDocumentTheme(readStoredTheme(), { persist: false });

    function handleThemeChange() {
      applyDocumentTheme(readStoredTheme(), { persist: false });
    }

    window.addEventListener(THEME_CHANGE_EVENT, handleThemeChange);
    window.addEventListener("storage", handleThemeChange);
    return () => {
      window.removeEventListener(THEME_CHANGE_EVENT, handleThemeChange);
      window.removeEventListener("storage", handleThemeChange);
    };
  }, []);
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
      className={`app-shell-nav-link${active ? " is-active" : ""}`}
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
  const overlayMode = useOverlayMode();
  const compact = !open;

  useThemeSync();

  React.useEffect(() => {
    document.documentElement.toggleAttribute("data-shell-sidebar-open", open);
    window.localStorage.setItem(OPEN_KEY, open ? "1" : "0");
  }, [open]);

  /**
   * Escape закрывает меню только в режиме накладки. На широком экране это
   * постоянная навигация, а не модалка: там Escape из любого поля или диалога
   * не должен схлопывать её.
   */
  React.useEffect(() => {
    if (!overlayMode || !open) return;

    function handleKeydown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, [overlayMode, open]);

  const handleClose = React.useCallback(() => setOpen(false), []);
  const handleToggle = React.useCallback(() => setOpen((value) => !value), []);

  /** Переход по ссылке уводит со страницы: состояние фиксируем до ухода. */
  const persistCurrentState = React.useCallback(() => {
    window.localStorage.setItem(OPEN_KEY, open ? "1" : "0");
  }, [open]);

  return (
    <div className={`app-shell-sidebar-root${open ? " is-open" : ""}`}>
      {overlayMode ? (
        <button
          type="button"
          className="app-shell-sidebar-backdrop"
          onClick={handleClose}
          aria-label="Закрыть навигацию"
          tabIndex={open ? 0 : -1}
          aria-hidden={!open}
        />
      ) : null}

      <div className="app-shell-sidebar-rail">
        <div className="app-shell-sidebar-rail-group">
          <nav className="app-shell-rail-nav" aria-label="Основная навигация">
            {navItems.map((item) => (
              <SidebarNavLink
                key={item.key}
                href={item.href}
                label={item.label}
                icon={item.icon}
                compact={compact}
                active={normalizedActiveTab === item.key}
                onNavigate={persistCurrentState}
              />
            ))}
          </nav>
        </div>

        {/*
          Снизу только роль. Выход живёт внутри её карточки: в свёрнутом виде
          карточка становится вертикальной, чтобы обе иконки остались доступны.
        */}
        <div className="app-shell-role-card">
          <span className="app-shell-nav-icon app-shell-role-mark" aria-hidden="true">
            <BadgeCheck className="size-5" />
          </span>
          {open ? <span className="app-shell-role-name">{roleLabel}</span> : null}

          <form method="post" action="/logout" className="app-shell-logout-form">
            <button type="submit" className="app-shell-logout-button" aria-label="Выйти" title="Выйти">
              <span className="app-shell-nav-icon" aria-hidden="true">
                <LogOut className="size-5" />
              </span>
            </button>
          </form>
        </div>
      </div>

      {/*
        Кнопка сидит на линии, отделяющей сайдбар от контента, напротив первого
        пункта меню. Вынесена из рельса намеренно: у рельса overflow-x: hidden,
        который прячет подписи во время анимации ширины, и внутри он обрезал бы
        кнопку, выступающую за границу.
      */}
      <button
        type="button"
        className="app-shell-collapse-toggle"
        onClick={handleToggle}
        aria-label={open ? "Свернуть навигацию" : "Развернуть навигацию"}
        aria-expanded={open}
      >
        {open ? <ChevronLeft className="size-4" /> : <ChevronRight className="size-4" />}
      </button>
    </div>
  );
}
