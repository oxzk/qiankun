import type { ReactElement } from 'react'
import { Button } from "@/components/ui/button"

export interface PaginationBarProps {
  /**
   * 当前页码（从 1 起）。
   */
  page: number;
  /**
   * 每页条数。
   */
  pageSize?: number;
  /**
   * 总条数。
   */
  total?: number;
  /**
   * 页码变更回调。
   */
  onChange: (page: number) => void;
  /**
   * 是否禁用。
   */
  disabled?: boolean;
}

/**
 * 通用分页条。
 */
export function PaginationBar({
  page,
  pageSize = 20,
  total = 0,
  onChange,
  disabled = false,
}: PaginationBarProps): ReactElement {
  const totalPages = Math.max(1, Math.ceil(total / (pageSize || 20)));
  const canPrev = page > 1;
  const canNext = page < totalPages;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card px-4 py-3 text-sm">
      <span className="text-muted-foreground">
        第 {page} / {totalPages} 页 · 每页 {pageSize} 条 · 共 {total} 条
      </span>
      <div className="flex items-center gap-1.5">
        <Button
          size="sm"
          variant="secondary"
          disabled={!canPrev || disabled}
          onClick={() => onChange(1)}
        >
          首页
        </Button>
        <Button
          size="sm"
          variant="secondary"
          disabled={!canPrev || disabled}
          onClick={() => onChange(page - 1)}
        >
          上一页
        </Button>
        <Button
          size="sm"
          variant="secondary"
          disabled={!canNext || disabled}
          onClick={() => onChange(page + 1)}
        >
          下一页
        </Button>
        <Button
          size="sm"
          variant="secondary"
          disabled={!canNext || disabled}
          onClick={() => onChange(totalPages)}
        >
          末页
        </Button>
      </div>
    </div>
  );
}
