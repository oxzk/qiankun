import type { ReactNode } from "react";

export interface DataTableShellProps {
  /**
   * 表格内容。
   */
  children: ReactNode;
}

/**
 * 数据表外层容器。
 */
export function DataTableShell({ children }: DataTableShellProps): JSX.Element {
  return <div className="table-shell">{children}</div>;
}
