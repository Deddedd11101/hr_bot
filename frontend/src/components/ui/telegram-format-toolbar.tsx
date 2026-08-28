import * as React from "react";
import { Bold, Code2, Italic, Link, Strikethrough, Underline } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type TelegramFormatAction = "bold" | "italic" | "underline" | "strike" | "code" | "link";

type FormatConfig = {
  action: TelegramFormatAction;
  label: string;
  before: string;
  after: string;
  placeholder: string;
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
};

const FORMATS: FormatConfig[] = [
  {
    action: "bold",
    label: "Жирный",
    before: "<b>",
    after: "</b>",
    placeholder: "текст",
    icon: Bold,
  },
  {
    action: "italic",
    label: "Курсив",
    before: "<i>",
    after: "</i>",
    placeholder: "текст",
    icon: Italic,
  },
  {
    action: "underline",
    label: "Подчеркнутый",
    before: "<u>",
    after: "</u>",
    placeholder: "текст",
    icon: Underline,
  },
  {
    action: "strike",
    label: "Зачеркнутый",
    before: "<s>",
    after: "</s>",
    placeholder: "текст",
    icon: Strikethrough,
  },
  {
    action: "code",
    label: "Код",
    before: "<code>",
    after: "</code>",
    placeholder: "код",
    icon: Code2,
  },
  {
    action: "link",
    label: "Ссылка",
    before: '<a href="https://example.com">',
    after: "</a>",
    placeholder: "текст ссылки",
    icon: Link,
  },
];

function applyTelegramFormat(
  value: string,
  selectionStart: number,
  selectionEnd: number,
  format: FormatConfig,
) {
  const start = Math.max(0, Math.min(selectionStart, value.length));
  const end = Math.max(start, Math.min(selectionEnd, value.length));
  const selectedText = value.slice(start, end) || format.placeholder;
  const wrappedText = `${format.before}${selectedText}${format.after}`;
  const nextValue = `${value.slice(0, start)}${wrappedText}${value.slice(end)}`;
  const nextSelectionStart = start + format.before.length;
  const nextSelectionEnd = nextSelectionStart + selectedText.length;

  return {
    value: nextValue,
    selectionStart: nextSelectionStart,
    selectionEnd: nextSelectionEnd,
  };
}

export function TelegramFormatToolbar({
  value,
  textareaRef,
  onChange,
  disabled = false,
  className,
}: {
  value: string;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  onChange: (nextValue: string) => void;
  disabled?: boolean;
  className?: string;
}) {
  const handleFormat = React.useCallback(
    (format: FormatConfig) => {
      const textarea = textareaRef.current;
      const selectionStart = textarea?.selectionStart ?? value.length;
      const selectionEnd = textarea?.selectionEnd ?? value.length;
      const next = applyTelegramFormat(value, selectionStart, selectionEnd, format);

      onChange(next.value);
      requestAnimationFrame(() => {
        const currentTextarea = textareaRef.current;
        if (!currentTextarea) {
          return;
        }
        currentTextarea.focus();
        currentTextarea.setSelectionRange(next.selectionStart, next.selectionEnd);
      });
    },
    [onChange, textareaRef, value],
  );

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-1 rounded-lg border border-border/70 bg-muted/35 p-1",
        className,
      )}
      role="toolbar"
      aria-label="Форматирование Telegram"
    >
      {FORMATS.map((format) => {
        const Icon = format.icon;
        return (
          <Button
            key={format.action}
            type="button"
            variant="ghost"
            size="icon-xs"
            onClick={() => handleFormat(format)}
            disabled={disabled}
            aria-label={format.label}
            title={format.label}
          >
            <Icon />
          </Button>
        );
      })}
    </div>
  );
}
