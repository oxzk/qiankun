import { RefreshCcw } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";

export interface SectionHeaderProps {
  /**
   * 分区标题。
   */
  title: string;
  /**
   * 分区说明。
   */
  description?: string;
  /**
   * 右侧操作区。
   */
  actions?: ReactNode;
  /**
   * 刷新回调。
   */
  onRefresh?: () => void;
  /**
   * 是否处于加载中。
   */
  loading?: boolean;
}

/**
 * 页面分区头部。
 */
export function SectionHeader({ title, description, actions, onRefresh, loading }: SectionHeaderProps): JSX.Element {
  return (
    <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h2 className="text-lg font-semibold tracking-normal">{title}</h2>
        {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
      </div>
      {actions || onRefresh ? (
        <div className="flex flex-wrap gap-2">
          {actions}
          {onRefresh ? (
            <Button variant="outline" size="sm" onClick={onRefresh} disabled={loading}>
              <RefreshCcw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
              刷新
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
