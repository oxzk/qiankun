import { Button } from "@/components/ui/button";

export interface PaginationBarProps {
  /**
   * 当前页码。
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
  onPageChange: (page: number) => void;
}

/**
 * 分页操作栏。
 */
export function PaginationBar({ page, pageSize, total, onPageChange }: PaginationBarProps): JSX.Element {
  const resolvedTotal = total ?? 0;
  const resolvedPageSize = pageSize ?? 0;
  const canNext = resolvedPageSize > 0 && page * resolvedPageSize < resolvedTotal;

  return (
    <div className="flex items-center justify-end gap-2">
      <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
        上一页
      </Button>
      <div className="text-sm text-muted-foreground">
        第 {page} 页, 共 {resolvedTotal} 条
      </div>
      <Button variant="outline" size="sm" disabled={!canNext} onClick={() => onPageChange(page + 1)}>
        下一页
      </Button>
    </div>
  );
}
