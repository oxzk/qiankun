import type { ReactNode } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface FilterBarProps {
  /**
   * 筛选控件。
   */
  children: ReactNode;
  /**
   * 当前是否存在有效筛选。
   */
  hasActiveFilters?: boolean;
  /**
   * 清空筛选回调。
   */
  onClear?: () => void;
}

/**
 * 列表页筛选工具栏。
 */
export function FilterBar({ children, hasActiveFilters = false, onClear }: FilterBarProps): JSX.Element {
  return (
    <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-end">
      {children}
      {hasActiveFilters && onClear ? (
        <Button type="button" size="sm" variant="ghost" onClick={onClear}>
          <X className="mr-1 h-4 w-4" />
          清空筛选
        </Button>
      ) : null}
    </div>
  );
}
