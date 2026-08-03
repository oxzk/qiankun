import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/**
 * 骨架屏占位组件。
 */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>): JSX.Element {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} {...props} />;
}
