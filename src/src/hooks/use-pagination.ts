import { useUrlPage } from "@/hooks/use-url-state";

/**
 * 管理分页页码并在依赖变化时回到第一页。
 * 页码同步到 URL `page` 查询参数。
 */
export function usePagination(resetDeps: readonly unknown[] = []): {
  page: number;
  setPage: (page: number | ((page: number) => number)) => void;
} {
  return useUrlPage(resetDeps);
}
