import { EmptyState } from "./empty-state";

export interface TableEmptyStateProps {
  /**
   * 空状态标题。
   */
  title: string;
  /**
   * 空状态说明。
   */
  description?: string;
}

/**
 * 表格空状态区域。
 */
export function TableEmptyState({ title, description }: TableEmptyStateProps): JSX.Element {
  return (
    <div className="p-4">
      <EmptyState title={title} description={description} />
    </div>
  );
}
