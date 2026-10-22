import { Skeleton } from "@/components/ui/skeleton";

export interface TableSkeletonColumn {
  /**
   * 骨架宽度 class。
   */
  widthClass: string;
  /**
   * 是否右对齐。
   */
  align?: "left" | "right";
}

export interface TableSkeletonProps {
  /**
   * 列定义。
   */
  columns: readonly TableSkeletonColumn[];
  /**
   * 行数。
   */
  rows?: number;
}

/**
 * 通用表格骨架屏。
 */
export function TableSkeleton({ columns, rows = 8 }: TableSkeletonProps): JSX.Element {
  return (
    <>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <tr key={rowIndex}>
          {columns.map((column, columnIndex) => (
            <td key={columnIndex} className={column.align === "right" ? "text-right" : undefined}>
              <Skeleton
                className={`h-4 ${column.widthClass} ${column.align === "right" ? "ml-auto" : ""}`}
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}
