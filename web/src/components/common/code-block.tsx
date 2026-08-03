import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";
import { TooltipIconButton } from "@/components/common/tooltip-icon-button";

export interface CodeBlockProps {
  /**
   * 展示文本。
   */
  content: string;
  /**
   * 空内容占位。
   */
  emptyText?: string;
  /**
   * 额外 className。
   */
  className?: string;
  /**
   * 是否展示复制按钮。
   */
  copyable?: boolean;
}

/**
 * 可复制代码/日志块。
 */
export function CodeBlock({
  content,
  emptyText = "暂无内容",
  className,
  copyable = true,
}: CodeBlockProps): JSX.Element {
  const [copied, setCopied] = useState(false);
  const text = content.trim() ? content : emptyText;
  const canCopy = copyable && Boolean(content.trim());

  /**
   * 复制内容到剪贴板。
   */
  async function handleCopy(): Promise<void> {
    if (!canCopy) return;
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="relative">
      {canCopy ? (
        <div className="absolute right-2 top-2 z-10">
          <TooltipIconButton
            label={copied ? "已复制" : "复制"}
            variant="outline"
            className="h-7 w-7"
            onClick={() => {
              void handleCopy();
            }}
          >
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          </TooltipIconButton>
        </div>
      ) : null}
      <pre className={cn("code-block", canCopy && "pr-10", className)}>{text}</pre>
    </div>
  );
}
