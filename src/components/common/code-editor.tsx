import { useMemo } from "react";
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
   * 可见行数。
   */
  rows?: number;
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
 * 带行号的轻量代码编辑器。
 */
export function CodeEditor({
  value,
  onChange,
  placeholder,
  rows = 16,
  disabled,
  required,
  className,
  "aria-label": ariaLabel,
}: CodeEditorProps): JSX.Element {
  const lineCount = useMemo(() => Math.max(value.split("\n").length, rows), [rows, value]);
  const lineNumbers = useMemo(
    () => Array.from({ length: lineCount }, (_, index) => index + 1).join("\n"),
    [lineCount],
  );

  return (
    <div
      className={cn(
        // 容器自身滚动: 行号与文本同步, 避免外层弹窗再出滚动条.
        "flex overflow-auto rounded-md border border-input bg-transparent shadow-sm focus-within:border-ring focus-within:ring-1 focus-within:ring-ring/30",
        disabled && "cursor-not-allowed opacity-70",
        className,
      )}
    >
      <pre
        aria-hidden="true"
        className="select-none border-r border-input bg-muted/40 px-2 py-2 text-right font-mono text-xs leading-5 text-muted-foreground"
      >
        {lineNumbers}
      </pre>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        rows={lineCount}
        disabled={disabled}
        required={required}
        spellCheck={false}
        aria-label={ariaLabel}
        className="min-h-24 w-full resize-none overflow-hidden bg-transparent px-3 py-2 font-mono text-xs leading-5 outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
      />
    </div>
  );
}
