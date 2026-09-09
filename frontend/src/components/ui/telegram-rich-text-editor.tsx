import * as React from "react";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import Link from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import {
  Bold,
  Code2,
  Italic,
  Link2,
  Redo2,
  Strikethrough,
  Underline as UnderlineIcon,
  Undo2,
  Unlink,
} from "lucide-react";

import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

type TelegramEditorNode = {
  type?: string;
  text?: string;
  attrs?: Record<string, unknown>;
  marks?: Array<{ type?: string; attrs?: Record<string, unknown> }>;
  content?: TelegramEditorNode[];
};

type FormatAction = "bold" | "italic" | "underline" | "strike" | "code";

const SAFE_LINK_SCHEMES = ["http:", "https:", "mailto:"];

function escapeText(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function escapeAttribute(value: string) {
  return escapeText(value).replace(/"/g, "&quot;");
}

function isSafeLink(value: unknown): value is string {
  if (typeof value !== "string") return false;
  const href = value.trim();
  return SAFE_LINK_SCHEMES.some((scheme) => href.toLowerCase().startsWith(scheme));
}

function serializeInline(node: TelegramEditorNode): string {
  if (node.type === "hardBreak") return "\n";
  if (node.type !== "text") {
    return (node.content || []).map(serializeInline).join("");
  }

  const text = escapeText(node.text || "");
  return (node.marks || []).reduce((result, mark) => {
    const href = mark.attrs?.href;
    switch (mark.type) {
      case "bold":
        return `<b>${result}</b>`;
      case "italic":
        return `<i>${result}</i>`;
      case "underline":
        return `<u>${result}</u>`;
      case "strike":
        return `<s>${result}</s>`;
      case "code":
        return `<code>${result}</code>`;
      case "link":
        return isSafeLink(href) ? `<a href="${escapeAttribute(href.trim())}">${result}</a>` : result;
      default:
        return result;
    }
  }, text);
}

function serializeTelegramDocument(document: TelegramEditorNode) {
  return (document.content || [])
    .map((node) => {
      if (node.type === "hardBreak") return "\n";
      return (node.content || []).map(serializeInline).join("");
    })
    .join("\n");
}

function normalizeEditorContent(value: string) {
  return value.trim() ? value : "";
}

function ToolbarButton({
  editor,
  action,
  label,
  children,
}: {
  editor: Editor;
  action: FormatAction;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <Button
      type="button"
      size="icon-xs"
      variant={editor.isActive(action) ? "secondary" : "ghost"}
      aria-label={label}
      title={label}
      onMouseDown={(event) => event.preventDefault()}
      onClick={() => editor.chain().focus().toggleMark(action).run()}
    >
      {children}
    </Button>
  );
}

function LinkEditor({ editor }: { editor: Editor }) {
  const [open, setOpen] = React.useState(false);
  const [href, setHref] = React.useState("");

  React.useEffect(() => {
    if (open) {
      setHref(editor.getAttributes("link").href || "");
    }
  }, [editor, open]);

  const applyLink = () => {
    const normalizedHref = href.trim();
    if (!normalizedHref || !isSafeLink(normalizedHref)) return;
    if (editor.state.selection.empty) {
      editor
        .chain()
        .focus()
        .insertContent({
          type: "text",
          text: "текст ссылки",
          marks: [{ type: "link", attrs: { href: normalizedHref } }],
        })
        .run();
    } else {
      editor.chain().focus().setLink({ href: normalizedHref }).run();
    }
    setOpen(false);
  };

  const removeLink = () => {
    editor.chain().focus().unsetLink().run();
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button
            type="button"
            size="icon-xs"
            variant={editor.isActive("link") ? "secondary" : "ghost"}
            aria-label="Ссылка"
            title="Ссылка"
            onMouseDown={(event) => event.preventDefault()}
          />
        }
      >
        <Link2 />
      </PopoverTrigger>
      <PopoverContent className="w-80" align="start">
        <div className="grid gap-2">
          <div className="text-sm font-medium">Адрес ссылки</div>
          <Input
            value={href}
            onChange={(event) => setHref(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") applyLink();
            }}
            placeholder="https://example.com"
            autoFocus
          />
          <div className="flex items-center justify-end gap-2">
            {editor.isActive("link") ? (
              <Button type="button" size="sm" variant="ghost" onClick={removeLink}>
                <Unlink data-icon="inline-start" />
                Удалить
              </Button>
            ) : null}
            <Button
              type="button"
              size="sm"
              onClick={applyLink}
              disabled={!isSafeLink(href.trim())}
            >
              {editor.isActive("link") ? "Изменить" : "Вставить"}
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

function EditorToolbar({ editor }: { editor: Editor }) {
  return (
    <div
      className="flex flex-wrap items-center gap-1 rounded-lg border border-border/70 bg-muted/35 p-1"
      role="toolbar"
      aria-label="Форматирование Telegram"
    >
      <ToolbarButton editor={editor} action="bold" label="Жирный">
        <Bold />
      </ToolbarButton>
      <ToolbarButton editor={editor} action="italic" label="Курсив">
        <Italic />
      </ToolbarButton>
      <ToolbarButton editor={editor} action="underline" label="Подчеркнутый">
        <UnderlineIcon />
      </ToolbarButton>
      <ToolbarButton editor={editor} action="strike" label="Зачеркнутый">
        <Strikethrough />
      </ToolbarButton>
      <ToolbarButton editor={editor} action="code" label="Код">
        <Code2 />
      </ToolbarButton>
      <LinkEditor editor={editor} />
      <span className="mx-1 h-4 w-px bg-border" aria-hidden="true" />
      <Button
        type="button"
        size="icon-xs"
        variant="ghost"
        aria-label="Отменить"
        title="Отменить"
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => editor.chain().focus().undo().run()}
        disabled={!editor.can().undo()}
      >
        <Undo2 />
      </Button>
      <Button
        type="button"
        size="icon-xs"
        variant="ghost"
        aria-label="Повторить"
        title="Повторить"
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => editor.chain().focus().redo().run()}
        disabled={!editor.can().redo()}
      >
        <Redo2 />
      </Button>
    </div>
  );
}

export type TelegramRichTextEditorProps = {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  editorClassName?: string;
  insertRef?: React.MutableRefObject<((text: string) => void) | null>;
};

export function TelegramRichTextEditor({
  value,
  onChange,
  placeholder = "Введите текст",
  disabled = false,
  className,
  editorClassName,
  insertRef,
}: TelegramRichTextEditorProps) {
  const lastEmittedValue = React.useRef(value);
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        blockquote: false,
        bulletList: false,
        codeBlock: false,
        heading: false,
        horizontalRule: false,
        orderedList: false,
        link: false,
        underline: false,
      }),
      Underline,
      Link.configure({
        autolink: false,
        linkOnPaste: false,
        openOnClick: false,
        protocols: ["http", "https", "mailto"],
      }),
      Placeholder.configure({ placeholder }),
    ],
    content: value || "",
    parseOptions: { preserveWhitespace: "full" },
    editable: !disabled,
    onUpdate: ({ editor: nextEditor }) => {
      const nextValue = normalizeEditorContent(serializeTelegramDocument(nextEditor.getJSON()));
      lastEmittedValue.current = nextValue;
      onChange(nextValue);
    },
  });

  React.useEffect(() => {
    if (!editor) return;
    editor.setEditable(!disabled);
  }, [disabled, editor]);

  React.useEffect(() => {
    if (!editor || value === lastEmittedValue.current) return;
    const currentValue = normalizeEditorContent(serializeTelegramDocument(editor.getJSON()));
    if (currentValue !== value) {
      editor.commands.setContent(value || "", {
        emitUpdate: false,
        parseOptions: { preserveWhitespace: "full" },
      });
    }
    lastEmittedValue.current = value;
  }, [editor, value]);

  React.useEffect(() => {
    if (!insertRef) return;
    insertRef.current = (text: string) => {
      if (!editor || disabled) return;
      editor.chain().focus().insertContent(text).run();
    };
    return () => {
      insertRef.current = null;
    };
  }, [disabled, editor, insertRef]);

  if (!editor) return null;

  const runContextAction = (action: FormatAction) => {
    editor.chain().focus().toggleMark(action).run();
  };

  return (
    <div className={cn("grid min-w-0 gap-2", className)}>
      <EditorToolbar editor={editor} />
      <ContextMenu>
        <ContextMenuTrigger>
          <div
            className={cn(
              "telegram-rich-text-editor min-h-[140px] w-full rounded-lg border border-input bg-transparent px-3 py-3 text-sm text-foreground outline-none transition-colors focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50 dark:bg-input/30",
              disabled && "cursor-not-allowed bg-input/50 opacity-50",
              editorClassName,
            )}
          >
            <EditorContent editor={editor} />
          </div>
        </ContextMenuTrigger>
        <ContextMenuContent>
          <ContextMenuItem onClick={() => runContextAction("bold")}>
            <Bold />
            Жирный
          </ContextMenuItem>
          <ContextMenuItem onClick={() => runContextAction("italic")}>
            <Italic />
            Курсив
          </ContextMenuItem>
          <ContextMenuItem onClick={() => runContextAction("underline")}>
            <UnderlineIcon />
            Подчеркнутый
          </ContextMenuItem>
          <ContextMenuItem onClick={() => runContextAction("strike")}>
            <Strikethrough />
            Зачеркнутый
          </ContextMenuItem>
          <ContextMenuItem onClick={() => runContextAction("code")}>
            <Code2 />
            Код
          </ContextMenuItem>
          <ContextMenuSeparator />
          <ContextMenuItem onClick={() => editor.chain().focus().undo().run()} disabled={!editor.can().undo()}>
            <Undo2 />
            Отменить
          </ContextMenuItem>
          <ContextMenuItem onClick={() => editor.chain().focus().redo().run()} disabled={!editor.can().redo()}>
            <Redo2 />
            Повторить
          </ContextMenuItem>
        </ContextMenuContent>
      </ContextMenu>
    </div>
  );
}
