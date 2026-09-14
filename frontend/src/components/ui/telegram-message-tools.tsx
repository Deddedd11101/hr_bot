import React from "react";
import { Smile, Tag } from "lucide-react";

import { Button } from "@/components/ui/button";

export type TelegramTemplateTag = {
  label: string;
  template: string;
  description?: string;
};

export type TelegramCustomEmoji = {
  id: number;
  title: string;
  emoji_id: string;
  fallback: string;
  is_active?: boolean;
};

export const DEFAULT_TELEGRAM_TEMPLATE_TAGS: TelegramTemplateTag[] = [
  { label: "ФИО", template: "{employee_full_name}", description: "ФИО сотрудника или кандидата" },
  { label: "Имя", template: "{first_name}", description: "Имя из карточки" },
  { label: "Должность", template: "{position}", description: "Должность из карточки" },
  { label: "Первый рабочий день", template: "{first_workday}", description: "Дата первого рабочего дня" },
];

export function TelegramMessageTools({
  tags,
  customEmojis = [],
  onInsertTag,
  onInsertEmoji,
}: {
  tags: TelegramTemplateTag[];
  customEmojis?: TelegramCustomEmoji[];
  onInsertTag: (template: string) => void;
  onInsertEmoji?: (emojiId: string) => void;
}) {
  const activeEmojis = customEmojis.filter((item) => item.is_active !== false && /^\d+$/.test(item.emoji_id));
  if (!tags.length && (!onInsertEmoji || !activeEmojis.length)) return null;

  return (
    <div className="grid gap-2 rounded-lg border border-border/70 bg-muted/35 p-2">
      {tags.length ? (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 inline-flex items-center gap-1 text-xs font-medium text-muted-foreground">
            <Tag className="size-3.5" />
            Теги
          </span>
          {tags.map((tag) => (
            <Button
              key={tag.template}
              type="button"
              variant="outline"
              size="xs"
              title={tag.description || tag.template}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => onInsertTag(tag.template)}
            >
              {tag.label}
            </Button>
          ))}
        </div>
      ) : null}
      {onInsertEmoji && activeEmojis.length ? (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 inline-flex items-center gap-1 text-xs font-medium text-muted-foreground">
            <Smile className="size-3.5" />
            Иконки
          </span>
          {activeEmojis.map((emoji) => (
            <Button
              key={emoji.id}
              type="button"
              variant="ghost"
              size="xs"
              title={emoji.title}
              aria-label={`Вставить ${emoji.title}`}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => onInsertEmoji(emoji.emoji_id)}
            >
              <span aria-hidden="true">{emoji.fallback || "✨"}</span>
              <span className="sr-only">{emoji.title}</span>
            </Button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
