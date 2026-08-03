import { useCallback, useMemo, useRef, type KeyboardEvent, type UIEvent } from "react";
import { cn } from "@/lib/utils";

export interface CodeEditorProps {
  /**
   * 编辑器内容。
   */
  value: string;
  /**
   * 内容变更回调。
   */
  onChange: (value: string) => void;
  /**
   * 占位文案。
   */
  placeholder?: string;
  /**
   * 最少行数。
   */
  minLines?: number;
  /**
   * 是否禁用。
   */
  disabled?: boolean;
  /**
   * 是否必填。
   */
  required?: boolean;
  /**
   * 额外 className。
   */
  className?: string;
  /**
   * 无障碍标签。
   */
  "aria-label"?: string;
}

/**
 * 带行号与 Tab 缩进支持的代码编辑器。
 */
export function CodeEditor({
  value,
  onChange,
  placeholder,
  minLines = 16,
  disabled,
  required,
  className,
  "aria-label": ariaLabel,
}: CodeEditorProps): JSX.Element {
  const lineNumbersRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const lines = useMemo(() => value.split("\n"), [value]);
  const lineCount = useMemo(() => Math.max(lines.length, minLines), [lines.length, minLines]);

  const lineNumbers = useMemo(
    () => Array.from({ length: lineCount }, (_, index) => index + 1).join("\n"),
    [lineCount],
  );

  /**
   * 保持行号区域与文本编辑区垂直滚动严格同步。
   */
  const handleScroll = useCallback((event: UIEvent<HTMLTextAreaElement>) => {
    if (lineNumbersRef.current) {
      lineNumbersRef.current.scrollTop = event.currentTarget.scrollTop;
    }
  }, []);

  /**
   * 支持 Tab 键插入 4 个空格缩进，避免按 Tab 焦点跳出。
   */
  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === "Tab" && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey) {
        event.preventDefault();
        const textarea = textareaRef.current;
        if (!textarea) return;

        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const insertSpaces = "    ";
        const nextValue = value.substring(0, start) + insertSpaces + value.substring(end);

        onChange(nextValue);

        requestAnimationFrame(() => {
          if (textareaRef.current) {
            textareaRef.current.selectionStart = textareaRef.current.selectionEnd = start + insertSpaces.length;
          }
        });
      }
    },
    [onChange, value],
  );

  return (
    <div
      className={cn(
        "relative flex w-full overflow-hidden rounded-lg border border-input bg-card shadow-xs focus-within:border-ring focus-within:ring-1 focus-within:ring-ring/30",
        disabled && "cursor-not-allowed opacity-70",
        className,
      )}
    >
      {/* 行号侧边栏 */}
      <div
        ref={lineNumbersRef}
        aria-hidden="true"
        className="shrink-0 select-none overflow-hidden border-r border-border/60 bg-muted/40 px-3 py-3 text-right font-mono text-xs leading-5 text-muted-foreground/70"
      >
        <pre className="m-0 p-0 font-mono text-xs leading-5">{lineNumbers}</pre>
      </div>

      {/* 文本输入区：禁止软折行以保证行号 1:1 严格对齐，支持双向滚动 */}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onScroll={handleScroll}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        required={required}
        spellCheck={false}
        wrap="off"
        aria-label={ariaLabel}
        style={{ tabSize: 4 }}
        className="min-h-0 w-full flex-1 resize-none overflow-auto bg-transparent px-3 py-3 font-mono text-xs leading-5 outline-none placeholder:text-muted-foreground whitespace-pre disabled:cursor-not-allowed"
      />
    </div>
  );
}
