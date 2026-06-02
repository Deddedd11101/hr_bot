import * as React from "react";
import { Smile } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  readDocumentTheme,
  THEME_CHANGE_EVENT,
  type AppTheme,
} from "@/lib/theme";

import type { EmojiClickData, PickerProps } from "emoji-picker-react";

const LazyEmojiPicker = React.lazy(async () => {
  const module = await import("emoji-picker-react");
  return { default: module.default };
});

function usePickerTheme() {
  const [theme, setTheme] = React.useState<AppTheme>(() => readDocumentTheme());

  React.useEffect(() => {
    function syncTheme() {
      setTheme(readDocumentTheme());
    }

    syncTheme();
    window.addEventListener(THEME_CHANGE_EVENT, syncTheme);
    window.addEventListener("storage", syncTheme);
    return () => {
      window.removeEventListener(THEME_CHANGE_EVENT, syncTheme);
      window.removeEventListener("storage", syncTheme);
    };
  }, []);

  return theme as NonNullable<PickerProps["theme"]>;
}

function pickerStyle(): React.CSSProperties {
  return {
    "--epr-bg-color": "var(--popover)",
    "--epr-text-color": "var(--popover-foreground)",
    "--epr-picker-border-color": "var(--border)",
    "--epr-picker-border-radius": "var(--radius)",
    "--epr-search-input-bg-color": "var(--background)",
    "--epr-search-input-bg-color-active": "var(--background)",
    "--epr-highlight-color": "var(--primary)",
    "--epr-hover-bg-color": "var(--muted)",
    "--epr-focus-bg-color": "var(--muted)",
    "--epr-category-label-bg-color": "var(--popover)",
  } as React.CSSProperties;
}

export function EmojiPickerPopover({ onEmojiSelect }: { onEmojiSelect: (emoji: string) => void }) {
  const [open, setOpen] = React.useState(false);
  const theme = usePickerTheme();

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button
            type="button"
            variant="outline"
            size="icon"
            aria-label="Добавить эмоджи"
            title="Добавить эмоджи"
          />
        }
      >
        <Smile />
      </PopoverTrigger>
      <PopoverContent className="w-auto p-1" align="end">
        <React.Suspense
          fallback={
            <div className="grid h-[380px] w-[320px] place-items-center text-sm text-muted-foreground">
              Загружаю эмоджи…
            </div>
          }
        >
          <LazyEmojiPicker
            lazyLoadEmojis
            skinTonesDisabled
            width={320}
            height={380}
            theme={theme}
            style={pickerStyle()}
            onEmojiClick={(emojiData: EmojiClickData) => {
              onEmojiSelect(emojiData.emoji);
              setOpen(false);
            }}
          />
        </React.Suspense>
      </PopoverContent>
    </Popover>
  );
}
