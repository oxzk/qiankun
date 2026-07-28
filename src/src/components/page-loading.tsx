import { Skeleton } from "@/components/ui/skeleton";

/**
 * 路由懒加载占位。
 */
export function PageLoading(): JSX.Element {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Skeleton className="h-7 w-40" />
        <Skeleton className="h-4 w-72 max-w-full" />
      </div>
      <Skeleton className="h-64 w-full rounded-lg" />
    </div>
  );
}
