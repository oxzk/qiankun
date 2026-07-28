export interface EmptyStateProps {
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
 * 空状态展示。
 */
export function EmptyState({ title, description }: EmptyStateProps): JSX.Element {
  return (
    <div className="flex min-h-36 flex-col items-center justify-center gap-2 p-8 text-center">
      <div className="text-sm font-medium">{title}</div>
      {description ? <div className="max-w-md text-xs text-muted-foreground">{description}</div> : null}
    </div>
  );
}
