import * as React from "react";
import { Primitive } from "@radix-ui/react-primitive";
import { cn } from "@/lib/utils";

/**
 * 通用卡片容器。
 */
export function Card({ className, ...props }: React.ComponentPropsWithoutRef<typeof Primitive.div>): JSX.Element {
  return <Primitive.div className={cn("glass-card rounded-lg text-card-foreground shadow-apple", className)} {...props} />;
}

/**
 * 卡片头部。
 */
export function CardHeader({ className, ...props }: React.ComponentPropsWithoutRef<typeof Primitive.div>): JSX.Element {
  return <Primitive.div className={cn("flex flex-col gap-1.5 p-5", className)} {...props} />;
}

/**
 * 卡片标题。
 */
export function CardTitle({ className, ...props }: React.ComponentPropsWithoutRef<typeof Primitive.h3>): JSX.Element {
  return <Primitive.h3 className={cn("text-base font-semibold leading-none tracking-normal", className)} {...props} />;
}

/**
 * 卡片描述。
 */
export function CardDescription({ className, ...props }: React.ComponentPropsWithoutRef<typeof Primitive.p>): JSX.Element {
  return <Primitive.p className={cn("text-sm text-muted-foreground", className)} {...props} />;
}

/**
 * 卡片主体。
 */
export function CardContent({ className, ...props }: React.ComponentPropsWithoutRef<typeof Primitive.div>): JSX.Element {
  return <Primitive.div className={cn("p-5 pt-0", className)} {...props} />;
}
